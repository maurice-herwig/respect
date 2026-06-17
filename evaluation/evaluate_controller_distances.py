#!/usr/bin/env python3
"""Evaluate bounded output-disagreement distances between synthesized controllers."""

from __future__ import annotations

import argparse
import copy
import json
import random
import re
import statistics
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evaluation.evaluate_reconstruction_distances import (  # noqa: E402
    DEFAULT_RUNS_MANIFEST,
    append_jsonl,
    default_output_jsonl as _distance_default_output_jsonl,
    java_major_version,
    load_completed_run_ids,
    load_jsonl,
    percent,
    repo_relative_or_absolute,
    resolve_existing_path,
    resolve_input_path,
    safe_path_part,
    select_matching_runs,
    sha256_file,
)


DEFAULT_OUTPUT_ROOT = REPO_ROOT / "evaluation" / "controller_distance_results"
DEFAULT_JAR = REPO_ROOT / "spectra-cli.jar"
DEFAULT_EXECUTOR_JAR = REPO_ROOT / "assets" / "examples" / "E2_execution" / "executor.jar"
CONTROLLER_TEST_SRC = REPO_ROOT / "controller_tests" / "src" / "main" / "java"
CONTROLLER_TEST_CLASSES = REPO_ROOT / "controller_tests" / "build" / "classes"
DECLARATION_RE = re.compile(r"^\s*(env|sys)\s+(.+?)\s+([A-Za-z_][A-Za-z0-9_]*)\s*;", re.MULTILINE)
SPEC_RE = re.compile(r"^\s*spec\s+([A-Za-z_][A-Za-z0-9_]*)\b", re.MULTILINE)
TYPE_RE = re.compile(r"^\s*type\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+?)\s*;", re.MULTILINE)
INLINE_ENUM_RE = re.compile(r"^\{\s*([^{}]+?)\s*\}$")
INT_RE = re.compile(r"^Int\s*\(\s*(-?\d+)\s*\.\.\s*(-?\d+)\s*\)$")


def strip_line_comments(source: str) -> str:
    return "\n".join(line.split("//", 1)[0] for line in source.splitlines())


def parse_domain(type_expr: str, type_defs: dict[str, str]) -> tuple[list[str] | None, str | None]:
    type_expr = type_expr.strip()
    if "[" in type_expr or "]" in type_expr:
        return None, f"unsupported array type: {type_expr}"
    seen: set[str] = set()
    while type_expr in type_defs:
        if type_expr in seen:
            return None, f"cyclic type alias: {type_expr}"
        seen.add(type_expr)
        type_expr = type_defs[type_expr].strip()
    if type_expr == "boolean":
        return ["false", "true"], None
    enum_match = INLINE_ENUM_RE.match(type_expr)
    if enum_match:
        values = [value.strip() for value in enum_match.group(1).split(",") if value.strip()]
        if not values:
            return None, f"empty enum type: {type_expr}"
        return values, None
    int_match = INT_RE.match(type_expr)
    if int_match:
        low = int(int_match.group(1))
        high = int(int_match.group(2))
        if high < low:
            return None, f"invalid Int range: {type_expr}"
        return [str(value) for value in range(low, high + 1)], None
    return None, f"unsupported type: {type_expr}"


def parse_spectra_signature(path: Path) -> dict[str, Any]:
    source = strip_line_comments(path.read_text(encoding="utf-8", errors="replace"))
    spec_match = SPEC_RE.search(source)
    if not spec_match:
        return {"status": "error", "error": "missing spec declaration", "path": repo_relative_or_absolute(path)}
    type_defs = {match.group(1): match.group(2).strip() for match in TYPE_RE.finditer(source)}
    env: dict[str, list[str]] = {}
    sys_vars: dict[str, list[str]] = {}
    errors: list[str] = []
    for match in DECLARATION_RE.finditer(source):
        owner, type_expr, variable = match.group(1), match.group(2).strip(), match.group(3)
        domain, error = parse_domain(type_expr, type_defs)
        if error is not None or domain is None:
            errors.append(f"{owner} {variable}: {error}")
            continue
        target = env if owner == "env" else sys_vars
        target[variable] = domain
    return {
        "status": "success" if not errors else "unsupported_signature",
        "error": "; ".join(errors) if errors else None,
        "path": repo_relative_or_absolute(path),
        "spec_name": spec_match.group(1),
        "env": env,
        "sys": sys_vars,
    }


def signatures_compatible(baseline: dict[str, Any], generated: dict[str, Any]) -> tuple[bool, str | None]:
    if baseline.get("status") != "success":
        return False, f"baseline_{baseline.get('status')}: {baseline.get('error')}"
    if generated.get("status") != "success":
        return False, f"generated_{generated.get('status')}: {generated.get('error')}"
    if baseline.get("env") != generated.get("env"):
        return False, "environment_signature_mismatch"
    if baseline.get("sys") != generated.get("sys"):
        return False, "system_signature_mismatch"
    if not baseline.get("env"):
        return False, "missing_environment_variables"
    if not baseline.get("sys"):
        return False, "missing_system_variables"
    return True, None


def build_controller_tests(executor_jar: Path) -> dict[str, Any]:
    java_files = sorted(str(path) for path in CONTROLLER_TEST_SRC.rglob("*.java"))
    CONTROLLER_TEST_CLASSES.mkdir(parents=True, exist_ok=True)
    command = ["javac", "-cp", str(executor_jar), "-d", str(CONTROLLER_TEST_CLASSES), *java_files]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    return {
        "status": "success" if completed.returncode == 0 else "failed",
        "command": command,
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def synthesize_controller(
    *,
    spectra_file: Path,
    output_dir: Path,
    jar_path: Path,
    timeout: float,
    force: bool,
) -> tuple[dict[str, Any], bool]:
    controller_dir = output_dir / "jit"
    if controller_dir.is_dir() and not force:
        return (
            {
                "status": "reused",
                "spectra_file": repo_relative_or_absolute(spectra_file),
                "spectra_sha256": sha256_file(spectra_file),
                "output_dir": repo_relative_or_absolute(output_dir),
                "controller_dir": repo_relative_or_absolute(controller_dir),
                "jar": repo_relative_or_absolute(jar_path),
                "jar_sha256": sha256_file(jar_path),
                "timeout_seconds": timeout,
            },
            True,
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    command = ["java", "-jar", str(jar_path), "-i", str(spectra_file), "-s", "-o", str(output_dir)]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raw_output = "\n".join(part.decode("utf-8", errors="replace") if isinstance(part, bytes) else part for part in (exc.stdout, exc.stderr) if part)
        return (
            {
                "status": "timeout",
                "spectra_file": repo_relative_or_absolute(spectra_file),
                "output_dir": repo_relative_or_absolute(output_dir),
                "controller_dir": repo_relative_or_absolute(controller_dir),
                "command": command,
                "exit_code": None,
                "timeout_seconds": timeout,
                "raw_output_tail": raw_output[-1000:],
            },
            False,
        )
    raw_output = "\n".join(part for part in (completed.stdout, completed.stderr) if part)
    ok = completed.returncode == 0 and controller_dir.is_dir()
    return (
        {
            "status": "synthesized" if ok else "failed",
            "spectra_file": repo_relative_or_absolute(spectra_file),
            "spectra_sha256": sha256_file(spectra_file),
            "output_dir": repo_relative_or_absolute(output_dir),
            "controller_dir": repo_relative_or_absolute(controller_dir),
            "jar": repo_relative_or_absolute(jar_path),
            "jar_sha256": sha256_file(jar_path),
            "command": command,
            "exit_code": completed.returncode,
            "timeout_seconds": timeout,
            "raw_output_tail": raw_output[-1000:],
        },
        ok,
    )

def write_trace_plan(
    *,
    path: Path,
    controller_dir: Path,
    spec_name: str,
    outputs: list[str],
    traces: list[list[dict[str, str]]],
) -> None:
    plan = {
        "controller": {
            "controller_dir": str(controller_dir),
            "spec_name": spec_name,
        },
        "outputs": outputs,
        "mode": "traces",
        "traces": traces,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_controller_trace(
    *,
    plan_path: Path,
    output_path: Path,
    executor_jar: Path,
    timeout: float,
) -> tuple[dict[str, Any], bool]:
    classpath = f"{CONTROLLER_TEST_CLASSES};{executor_jar}" if sys.platform.startswith("win") else f"{CONTROLLER_TEST_CLASSES}:{executor_jar}"
    command = [
        "java",
        "-Djava.library.path=.",
        "-cp",
        classpath,
        "respect.controller_tests.ControllerTraceRunner",
        "--plan",
        str(plan_path),
        "--output",
        str(output_path),
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raw_output = "\n".join(part.decode("utf-8", errors="replace") if isinstance(part, bytes) else part for part in (exc.stdout, exc.stderr) if part)
        return (
            {
                "status": "timeout",
                "command": command,
                "exit_code": None,
                "timeout_seconds": timeout,
                "raw_output_tail": raw_output[-1000:],
            },
            False,
        )
    if output_path.is_file():
        result = json.loads(output_path.read_text(encoding="utf-8"))
        result["command"] = command
        result["exit_code"] = completed.returncode
        return result, completed.returncode == 0
    raw_output = "\n".join(part for part in (completed.stdout, completed.stderr) if part)
    return (
        {
            "status": "failed",
            "command": command,
            "exit_code": completed.returncode,
            "raw_output_tail": raw_output[-1000:],
        },
        False,
    )


def compare_trace_outputs(left: dict[str, Any], right: dict[str, Any], outputs: list[str]) -> dict[str, Any]:
    left_traces = left.get("traces") or []
    right_traces = right.get("traces") or []
    if len(left_traces) != len(right_traces):
        raise ValueError("Trace runner outputs contain different trace counts.")
    total_traces = len(left_traces)
    mismatching_traces = 0
    total_steps = 0
    mismatching_steps = 0
    total_output_comparisons = 0
    mismatching_output_comparisons = 0
    first_mismatch = None

    for trace_index, (left_trace, right_trace) in enumerate(zip(left_traces, right_traces)):
        if len(left_trace) != len(right_trace):
            raise ValueError(f"Trace {trace_index} has different step counts.")
        trace_mismatched = False
        input_trace: list[dict[str, str]] = []
        for step_index, (left_step, right_step) in enumerate(zip(left_trace, right_trace)):
            left_outputs = dict(left_step.get("outputs") or {})
            right_outputs = dict(right_step.get("outputs") or {})
            inputs = dict(left_step.get("inputs") or {})
            input_trace.append(inputs)
            total_steps += 1
            total_output_comparisons += len(outputs)
            differing_outputs = [output for output in outputs if left_outputs.get(output) != right_outputs.get(output)]
            if differing_outputs:
                mismatching_steps += 1
                mismatching_output_comparisons += len(differing_outputs)
                if not trace_mismatched:
                    mismatching_traces += 1
                    trace_mismatched = True
                if first_mismatch is None:
                    first_mismatch = {
                        "trace_index": trace_index,
                        "step_index": step_index,
                        "input_trace": input_trace,
                        "inputs": inputs,
                        "controller_a_outputs": left_outputs,
                        "controller_b_outputs": right_outputs,
                        "differing_outputs": differing_outputs,
                    }

    return {
        "status": "success",
        "total_traces": total_traces,
        "mismatching_traces": mismatching_traces,
        "trace_mismatch_rate": 0.0 if total_traces == 0 else mismatching_traces / total_traces,
        "total_steps": total_steps,
        "mismatching_steps": mismatching_steps,
        "step_mismatch_rate": 0.0 if total_steps == 0 else mismatching_steps / total_steps,
        "total_output_comparisons": total_output_comparisons,
        "mismatching_output_comparisons": mismatching_output_comparisons,
        "output_hamming_mismatch_rate": (
            0.0 if total_output_comparisons == 0 else mismatching_output_comparisons / total_output_comparisons
        ),
        "first_mismatch": first_mismatch,
    }


def valuations(env: dict[str, list[str]]) -> list[dict[str, str]]:
    variables = list(env.keys())
    result: list[dict[str, str]] = []

    def build(index: int, current: dict[str, str]) -> None:
        if index == len(variables):
            result.append(dict(current))
            return
        variable = variables[index]
        for value in env[variable]:
            current[variable] = value
            build(index + 1, current)
        current.pop(variable, None)

    build(0, {})
    return result


def exhaustive_traces(env: dict[str, list[str]], max_depth: int, max_paths: int) -> list[list[dict[str, str]]]:
    one_step = valuations(env)
    traces: list[list[dict[str, str]]] = []

    def build(prefix: list[dict[str, str]]) -> None:
        if len(traces) >= max_paths:
            return
        if len(prefix) == max_depth:
            traces.append([dict(step) for step in prefix])
            return
        for valuation in one_step:
            prefix.append(valuation)
            build(prefix)
            prefix.pop()
            if len(traces) >= max_paths:
                return

    build([])
    return traces


def random_traces(env: dict[str, list[str]], max_depth: int, runs: int, seed: int) -> list[list[dict[str, str]]]:
    rng = random.Random(seed)
    variables = list(env.keys())
    traces: list[list[dict[str, str]]] = []
    for _run in range(runs):
        trace: list[dict[str, str]] = []
        for _step in range(max_depth):
            trace.append({variable: rng.choice(env[variable]) for variable in variables})
        traces.append(trace)
    return traces


def chunked(values: list[Any], chunk_size: int) -> list[list[Any]]:
    return [values[index : index + chunk_size] for index in range(0, len(values), chunk_size)]


def aggregate_distance_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    total_traces = sum(int(result.get("total_traces") or 0) for result in results)
    mismatching_traces = sum(int(result.get("mismatching_traces") or 0) for result in results)
    total_steps = sum(int(result.get("total_steps") or 0) for result in results)
    mismatching_steps = sum(int(result.get("mismatching_steps") or 0) for result in results)
    total_output_comparisons = sum(int(result.get("total_output_comparisons") or 0) for result in results)
    mismatching_output_comparisons = sum(int(result.get("mismatching_output_comparisons") or 0) for result in results)
    first_mismatch = next((result.get("first_mismatch") for result in results if result.get("first_mismatch") is not None), None)
    return {
        "status": "success",
        "total_traces": total_traces,
        "mismatching_traces": mismatching_traces,
        "trace_mismatch_rate": 0.0 if total_traces == 0 else mismatching_traces / total_traces,
        "total_steps": total_steps,
        "mismatching_steps": mismatching_steps,
        "step_mismatch_rate": 0.0 if total_steps == 0 else mismatching_steps / total_steps,
        "total_output_comparisons": total_output_comparisons,
        "mismatching_output_comparisons": mismatching_output_comparisons,
        "output_hamming_mismatch_rate": (
            0.0 if total_output_comparisons == 0 else mismatching_output_comparisons / total_output_comparisons
        ),
        "first_mismatch": first_mismatch,
        "batches": len(results),
    }


def run_id_from_result(record: dict[str, Any]) -> str | None:
    run = record.get("run")
    if isinstance(run, dict) and isinstance(run.get("run_id"), str):
        return run["run_id"]
    return None


def result_pair_key(record: dict[str, Any]) -> tuple[Any, ...] | None:
    metadata = record.get("cache_metadata") or {}
    baseline_sha = metadata.get("baseline_sha256")
    generated_sha = metadata.get("generated_sha256")
    settings = metadata.get("settings")
    if not baseline_sha or not generated_sha or not isinstance(settings, dict):
        baseline_synthesis = record.get("baseline_synthesis") or {}
        generated_synthesis = record.get("generated_synthesis") or {}
        baseline_sha = baseline_synthesis.get("spectra_sha256")
        generated_sha = generated_synthesis.get("spectra_sha256")
        distance = record.get("distance") or {}
        settings = {
            "mode": distance.get("mode"),
            "max_depth": distance.get("max_depth"),
            "trace_batch_size": distance.get("trace_batch_size"),
        }
    if not baseline_sha or not generated_sha:
        return None
    return ("controller_distance", baseline_sha, generated_sha, json.dumps(settings, sort_keys=True))


def current_pair_key(record: dict[str, Any], args: argparse.Namespace, jar_path: Path, executor_jar: Path) -> tuple[Any, ...]:
    baseline_spectra = resolve_input_path(str(record["source_spectra_file"]))
    generated_spectra = resolve_input_path(str(record["reconstructed_spectra_file"]))
    settings = {
        "jar_sha256": sha256_file(jar_path),
        "executor_jar_sha256": sha256_file(executor_jar),
        "mode": args.mode,
        "max_depth": args.max_depth,
        "max_paths": args.max_paths if args.mode == "exhaustive" else None,
        "runs": args.runs if args.mode == "random" else None,
        "seed": args.seed if args.mode == "random" else None,
        "trace_batch_size": max(1, int(args.trace_batch_size)),
    }
    return (
        "controller_distance",
        sha256_file(baseline_spectra),
        sha256_file(generated_spectra),
        json.dumps(settings, sort_keys=True),
    )


def load_pair_cache(path: Path) -> dict[tuple[Any, ...], dict[str, Any]]:
    cache: dict[tuple[Any, ...], dict[str, Any]] = {}
    if not path.is_file():
        return cache
    for record in load_jsonl(path):
        key = result_pair_key(record)
        if key is not None:
            cache[key] = record
    return cache


def cached_record_for_run(cached: dict[str, Any], run_record: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    reused = copy.deepcopy(cached)
    reused["run"] = summarize_run(run_record, args.include_run_record)
    reused["comparison_id"] = safe_path_part(str(run_record.get("run_id") or run_record.get("run_key") or run_record.get("dataset_id") or "run"))
    reused["cache_reused"] = True
    reused["cache_source_comparison_id"] = cached.get("comparison_id")
    return reused


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--runs-manifest", default=str(DEFAULT_RUNS_MANIFEST))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--output-jsonl", default=None)
    parser.add_argument("--jar", default=str(DEFAULT_JAR))
    parser.add_argument("--executor-jar", default=str(DEFAULT_EXECUTOR_JAR))
    parser.add_argument("--mode", choices=("exhaustive", "random"), default="exhaustive")
    parser.add_argument("--max-depth", type=int, default=6)
    parser.add_argument("--max-paths", type=int, default=10000)
    parser.add_argument("--runs", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument(
        "--trace-batch-size",
        type=int,
        default=1,
        help="Number of concrete input traces per Java runner process. Keep at 1 if CUDD is unstable.",
    )
    parser.add_argument("--synthesis-timeout", type=float, default=120.0)
    parser.add_argument("--runner-timeout", type=float, default=120.0)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--reuse-existing",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Reuse existing JSONL distance records for the same baseline/generated Spectra file hashes "
            "and controller-distance settings. Enabled by default; use --no-reuse-existing to rebuild the JSONL."
        ),
    )
    parser.add_argument("--build-controller-tests", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--preflight-java", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--include-run-record", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def output_root(args: argparse.Namespace) -> Path:
    path = Path(args.output_root)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path / safe_path_part(args.skill) / safe_path_part(args.model)


def default_output_jsonl(args: argparse.Namespace) -> Path:
    if args.output_jsonl:
        path = Path(args.output_jsonl)
        return path if path.is_absolute() else REPO_ROOT / path
    return output_root(args) / "controller_distances.jsonl"


def summarize_run(record: dict[str, Any], include_full_record: bool) -> dict[str, Any]:
    if include_full_record:
        return record
    keys = (
        "run_id",
        "run_key",
        "dataset_id",
        "skill",
        "status",
        "reported_cli_status",
        "reported_repair_loops",
        "source_repository_full_name",
        "source_path",
        "source_spectra_file",
        "reconstructed_spectra_file",
        "description_id",
        "description_relative_stem",
    )
    return {key: record.get(key) for key in keys if key in record}


def evaluate_one_run(record: dict[str, Any], args: argparse.Namespace, jar_path: Path, executor_jar: Path, artifacts_root: Path) -> dict[str, Any]:
    comparison_id = safe_path_part(str(record.get("run_id") or record.get("run_key") or record.get("dataset_id") or "run"))
    pair_dir = artifacts_root / "comparisons" / comparison_id
    baseline_spectra = resolve_input_path(str(record["source_spectra_file"]))
    generated_spectra = resolve_input_path(str(record["reconstructed_spectra_file"]))
    result: dict[str, Any] = {
        "status": "started",
        "comparison_id": comparison_id,
        "run": summarize_run(record, args.include_run_record),
        "baseline_signature": None,
        "generated_signature": None,
        "baseline_synthesis": None,
        "generated_synthesis": None,
        "plan_file": repo_relative_or_absolute(pair_dir / "controller-distance-plan.json"),
        "result_file": repo_relative_or_absolute(pair_dir / "controller-distance-result.json"),
        "distance": None,
        "error": None,
    }
    try:
        baseline_signature = parse_spectra_signature(baseline_spectra)
        generated_signature = parse_spectra_signature(generated_spectra)
        result["cache_metadata"] = {
            "baseline_sha256": sha256_file(baseline_spectra),
            "generated_sha256": sha256_file(generated_spectra),
            "settings": {
                "jar_sha256": sha256_file(jar_path),
                "executor_jar_sha256": sha256_file(executor_jar),
                "mode": args.mode,
                "max_depth": args.max_depth,
                "max_paths": args.max_paths if args.mode == "exhaustive" else None,
                "runs": args.runs if args.mode == "random" else None,
                "seed": args.seed if args.mode == "random" else None,
                "trace_batch_size": max(1, int(args.trace_batch_size)),
            },
        }
        result["baseline_signature"] = baseline_signature
        result["generated_signature"] = generated_signature
        compatible, incompatibility = signatures_compatible(baseline_signature, generated_signature)
        if not compatible:
            result["status"] = "signature_mismatch" if "mismatch" in str(incompatibility) else "unsupported_signature"
            result["error"] = incompatibility
            return result

        baseline_synthesis, baseline_ok = synthesize_controller(
            spectra_file=baseline_spectra,
            output_dir=pair_dir / "baseline-controller",
            jar_path=jar_path,
            timeout=args.synthesis_timeout,
            force=args.force,
        )
        generated_synthesis, generated_ok = synthesize_controller(
            spectra_file=generated_spectra,
            output_dir=pair_dir / "generated-controller",
            jar_path=jar_path,
            timeout=args.synthesis_timeout,
            force=args.force,
        )
        result["baseline_synthesis"] = baseline_synthesis
        result["generated_synthesis"] = generated_synthesis
        if not (baseline_ok and generated_ok):
            result["status"] = "synthesis_failed"
            return result

        if args.mode == "exhaustive":
            traces = exhaustive_traces(baseline_signature["env"], args.max_depth, args.max_paths)
        else:
            traces = random_traces(baseline_signature["env"], args.max_depth, args.runs, args.seed)
        if not traces:
            result["status"] = "failed"
            result["error"] = "no input traces generated"
            return result

        batch_size = max(1, int(args.trace_batch_size))
        batch_results: list[dict[str, Any]] = []
        for batch_index, trace_batch in enumerate(chunked(traces, batch_size), start=1):
            baseline_plan_path = pair_dir / "batches" / f"baseline-trace-plan-{batch_index:05d}.json"
            generated_plan_path = pair_dir / "batches" / f"generated-trace-plan-{batch_index:05d}.json"
            baseline_trace_output = pair_dir / "batches" / f"baseline-trace-result-{batch_index:05d}.json"
            generated_trace_output = pair_dir / "batches" / f"generated-trace-result-{batch_index:05d}.json"
            outputs = list(baseline_signature["sys"].keys())
            write_trace_plan(
                path=baseline_plan_path,
                controller_dir=pair_dir / "baseline-controller" / "jit",
                spec_name=str(baseline_signature["spec_name"]),
                outputs=outputs,
                traces=trace_batch,
            )
            write_trace_plan(
                path=generated_plan_path,
                controller_dir=pair_dir / "generated-controller" / "jit",
                spec_name=str(generated_signature["spec_name"]),
                outputs=outputs,
                traces=trace_batch,
            )
            baseline_trace, baseline_runner_ok = run_controller_trace(
                plan_path=baseline_plan_path,
                output_path=baseline_trace_output,
                executor_jar=executor_jar,
                timeout=args.runner_timeout,
            )
            if not baseline_runner_ok:
                result["distance"] = baseline_trace
                result["status"] = "runner_failed"
                result["error"] = f"baseline controller trace runner failed in batch {batch_index}"
                return result
            generated_trace, generated_runner_ok = run_controller_trace(
                plan_path=generated_plan_path,
                output_path=generated_trace_output,
                executor_jar=executor_jar,
                timeout=args.runner_timeout,
            )
            if not generated_runner_ok:
                result["distance"] = generated_trace
                result["status"] = "runner_failed"
                result["error"] = f"generated controller trace runner failed in batch {batch_index}"
                return result
            distance_result = compare_trace_outputs(baseline_trace, generated_trace, outputs)
            batch_results.append(distance_result)

        result["plan_file"] = repo_relative_or_absolute(pair_dir / "batches")
        result["result_file"] = repo_relative_or_absolute(pair_dir / "batches")
        result["distance"] = aggregate_distance_results(batch_results)
        result["distance"]["mode"] = args.mode
        result["distance"]["max_depth"] = args.max_depth
        result["distance"]["trace_batch_size"] = batch_size
        result["status"] = "success"
        return result
    except Exception as exc:
        result["status"] = "failed"
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result


def summarize_results(args: argparse.Namespace, total_matching_runs: int, selected_runs: int, records: list[dict[str, Any]], skipped: Counter[str], output_jsonl: Path) -> dict[str, Any]:
    statuses = Counter(str(record.get("status")) for record in records)
    trace_rates = [
        float((record.get("distance") or {}).get("trace_mismatch_rate"))
        for record in records
        if record.get("status") == "success" and (record.get("distance") or {}).get("trace_mismatch_rate") is not None
    ]
    step_rates = [
        float((record.get("distance") or {}).get("step_mismatch_rate"))
        for record in records
        if record.get("status") == "success" and (record.get("distance") or {}).get("step_mismatch_rate") is not None
    ]
    hamming_rates = [
        float((record.get("distance") or {}).get("output_hamming_mismatch_rate"))
        for record in records
        if record.get("status") == "success" and (record.get("distance") or {}).get("output_hamming_mismatch_rate") is not None
    ]

    def stats(values: list[float]) -> dict[str, float | int | None]:
        return {
            "count": len(values),
            "mean": statistics.fmean(values) if values else None,
            "median": statistics.median(values) if values else None,
            "min": min(values) if values else None,
            "max": max(values) if values else None,
        }

    return {
        "skill": args.skill,
        "model": args.model,
        "mode": args.mode,
        "max_depth": args.max_depth,
        "max_paths": args.max_paths if args.mode == "exhaustive" else None,
        "runs": args.runs if args.mode == "random" else None,
        "matching_synthesized_runs": total_matching_runs,
        "selected_runs": selected_runs,
        "evaluated_runs": len(records),
        "output_jsonl": str(output_jsonl),
        "status_counts": [
            {"status": status, "count": count, "percent": percent(count, len(records))}
            for status, count in sorted(statuses.items())
        ],
        "skipped_counts": dict(sorted(skipped.items())),
        "trace_mismatch_rate": stats(trace_rates),
        "step_mismatch_rate": stats(step_rates),
        "output_hamming_mismatch_rate": stats(hamming_rates),
    }


def print_text_summary(summary: dict[str, Any]) -> None:
    print(f"Skill: {summary['skill']}")
    print(f"Model: {summary['model']}")
    print(f"Mode: {summary['mode']}, max_depth={summary['max_depth']}")
    print(f"Matching synthesized runs: {summary['matching_synthesized_runs']}")
    print(f"Selected runs: {summary['selected_runs']}")
    print(f"Evaluated runs: {summary['evaluated_runs']}")
    print(f"Results: {summary['output_jsonl']}")
    print()
    print("Statuses:")
    for item in summary["status_counts"]:
        print(f"  {item['status']}: {item['count']} ({item['percent']:.2f}%)")
    for key in ("trace_mismatch_rate", "step_mismatch_rate", "output_hamming_mismatch_rate"):
        values = summary[key]
        print()
        print(f"{key}: count={values['count']}")
        if values["count"]:
            print(f"  mean: {values['mean']:.6g}")
            print(f"  median: {values['median']:.6g}")
            print(f"  min: {values['min']:.6g}")
            print(f"  max: {values['max']:.6g}")


def print_intermediate_result(index: int, total: int, run_id: str, result: dict[str, Any]) -> None:
    status = result.get("status")
    distance = result.get("distance") or {}
    if status == "success":
        detail = (
            f"trace={float(distance.get('trace_mismatch_rate', 0.0)):.6g} "
            f"step={float(distance.get('step_mismatch_rate', 0.0)):.6g} "
            f"hamming={float(distance.get('output_hamming_mismatch_rate', 0.0)):.6g}"
        )
    else:
        error = result.get("error")
        detail = f"error={error}" if error else "distance=none"
    print(
        f"[{index}/{total}] result run_id={run_id or 'missing'} status={status} {detail}",
        file=sys.stderr,
    )


def main() -> int:
    args = parse_args()
    runs_manifest = resolve_existing_path(args.runs_manifest)
    records = load_jsonl(runs_manifest)
    matching, skipped = select_matching_runs(records, args.skill, args.model)
    total_matching_runs = len(matching)
    if args.limit is not None:
        matching = matching[: args.limit]

    output_jsonl = default_output_jsonl(args)
    artifacts_root = output_root(args)
    jar_path = resolve_existing_path(args.jar)
    executor_jar = resolve_existing_path(args.executor_jar)
    if not jar_path.is_file():
        print(f"spectra-cli.jar not found: {jar_path}")
        return 2
    if not executor_jar.is_file():
        print(f"executor.jar not found: {executor_jar}")
        return 2

    if args.preflight_java:
        major, java_output = java_major_version()
        if major is None or major < 17:
            print(f"Java 17 or newer is required. Detected: {major if major is not None else 'unknown'}\n{java_output}")
            return 1

    if args.build_controller_tests:
        build = build_controller_tests(executor_jar)
        if build["status"] != "success":
            print(json.dumps(build, indent=2, sort_keys=True) if args.json else build["stderr"])
            return 1

    completed_run_ids = load_completed_run_ids(output_jsonl) if args.resume else set()
    existing_run_ids = load_completed_run_ids(output_jsonl)
    pair_cache = load_pair_cache(output_jsonl) if args.reuse_existing and not args.force else {}
    evaluated_records: list[dict[str, Any]] = []
    if not args.resume and not args.reuse_existing and output_jsonl.exists():
        output_jsonl.unlink()

    for index, record in enumerate(matching, start=1):
        run_id = str(record.get("run_id") or "")
        if args.resume and run_id and run_id in completed_run_ids:
            continue
        if args.reuse_existing and not args.force:
            try:
                key = current_pair_key(record, args, jar_path, executor_jar)
            except Exception:
                key = None
            if key is not None and key in pair_cache:
                print(f"[{index}/{len(matching)}] reusing cached controller distance run_id={run_id or 'missing'}", file=sys.stderr)
                if not (run_id and run_id in existing_run_ids):
                    result = cached_record_for_run(pair_cache[key], record, args)
                    append_jsonl(output_jsonl, result)
                    if run_id:
                        existing_run_ids.add(run_id)
                    evaluated_records.append(result)
                continue
        print(f"[{index}/{len(matching)}] evaluating controller distance run_id={run_id or 'missing'}", file=sys.stderr)
        result = evaluate_one_run(record, args, jar_path, executor_jar, artifacts_root)
        print_intermediate_result(index, len(matching), run_id, result)
        append_jsonl(output_jsonl, result)
        evaluated_records.append(result)
        key = result_pair_key(result)
        if key is not None:
            pair_cache[key] = result

    if (args.resume or args.reuse_existing) and output_jsonl.is_file():
        evaluated_records = load_jsonl(output_jsonl)

    summary = summarize_results(args, total_matching_runs, len(matching), evaluated_records, skipped, output_jsonl)
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print_text_summary(summary)
    return 0 if all(record.get("status") == "success" for record in evaluated_records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
