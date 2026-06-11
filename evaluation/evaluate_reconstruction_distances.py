#!/usr/bin/env python3
"""Batch distance evaluation for synthesized reconstruction runs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evaluation import buchi_distance
from evaluation.summarize_reconstruction_runs import extract_model_label


DEFAULT_RUNS_MANIFEST = REPO_ROOT / "experiments" / "runs" / "runs.jsonl"
DEFAULT_JAR = REPO_ROOT / "assets" / "cli_with_hoa_export" / "spectra-cli.jar"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "evaluation" / "distance_results"
STATE_RE = re.compile(r"^State:\s+(\d+)(?:\s+\[(.*)\])?(?:\s+(\{[^}]*\}))?\s*$")
EDGE_RE = re.compile(r"^\[(.*)\]\s+(\d+)(?:\s+(\{[^}]*\}))?\s*$")
STATES_RE = re.compile(r"^States:\s+(\d+)\s*$")
PROPERTIES_RE = re.compile(r"^properties:\s+(.*)$")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not path.is_file():
        raise FileNotFoundError(f"JSONL file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in {path} at line {line_number}: {exc}") from exc
    return records


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def repo_relative_or_absolute(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path.resolve())


def normalize_path_value_for_platform(path_value: str) -> str:
    value = path_value.strip().strip('"').strip("'")
    if os.name == "nt":
        return value

    windows_drive_match = re.fullmatch(r"([A-Za-z]):[\\/](.*)", value)
    if windows_drive_match:
        drive = windows_drive_match.group(1).lower()
        rest = windows_drive_match.group(2).replace("\\", "/")
        return f"/mnt/{drive}/{rest}"

    if "\\" in value and not value.startswith("\\\\"):
        return value.replace("\\", "/")
    return value


def resolve_input_path(path_value: str) -> Path:
    path = Path(normalize_path_value_for_platform(path_value))
    candidates = [path]
    if not path.is_absolute():
        candidates.append(REPO_ROOT / path)
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_file():
            return resolved
    return candidates[0].resolve()


def resolve_existing_path(path_value: str | Path) -> Path:
    path = Path(normalize_path_value_for_platform(str(path_value)))
    candidates = [path]
    if not path.is_absolute():
        candidates.append(REPO_ROOT / path)
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.exists():
            return resolved
    return candidates[0].resolve()


def safe_path_part(value: str, max_length: int = 120) -> str:
    safe = "".join(char if char.isalnum() or char in "._=-" else "_" for char in value).strip("_")
    return (safe or "value")[:max_length]


def model_matches(record: dict[str, Any], model: str | None) -> bool:
    if model is None:
        return True
    return extract_model_label(record) == model


def summarize_run(record: dict[str, Any] | None, include_full_record: bool) -> dict[str, Any] | None:
    if record is None:
        return None
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


def build_export_command(jar_path: Path, input_path: Path, output_path: Path, max_states: int, use_jtlv: bool) -> list[str]:
    command = ["java", "-jar", str(jar_path), "-i", str(input_path)]
    if use_jtlv:
        command.append("--jtlv")
    command.extend(["--export-hoa", "--hoa-output", str(output_path), "--max-states", str(max_states)])
    return command


def output_fields(raw_output: str, include_raw_output: bool, tail_chars: int) -> dict[str, Any]:
    if include_raw_output:
        return {"raw_output": raw_output}
    if tail_chars <= 0:
        return {"raw_output_truncated": len(raw_output) > 0, "raw_output_tail": ""}
    return {"raw_output_truncated": len(raw_output) > tail_chars, "raw_output_tail": raw_output[-tail_chars:]}


def export_hoa(
    *,
    input_path: Path,
    output_path: Path,
    jar_path: Path,
    max_states: int,
    timeout: float,
    use_jtlv: bool,
    force: bool,
    include_raw_output: bool,
    raw_output_tail_chars: int,
) -> tuple[dict[str, Any], bool]:
    if output_path.exists() and not force:
        return (
            {
                "status": "reused",
                "input": repo_relative_or_absolute(input_path),
                "input_sha256": sha256_file(input_path),
                "hoa_file": repo_relative_or_absolute(output_path),
                "hoa_exists": True,
                "hoa_size_bytes": output_path.stat().st_size,
                "jar": repo_relative_or_absolute(jar_path),
                "jar_sha256": sha256_file(jar_path),
                "max_states": max_states,
                "timeout_seconds": timeout,
                "jtlv": use_jtlv,
            },
            True,
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists() and force:
        output_path.unlink()

    command = build_export_command(jar_path, input_path, output_path, max_states, use_jtlv)
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raw_output = "\n".join(part for part in (exc.stdout or "", exc.stderr or "") if part).strip()
        if output_path.exists():
            output_path.unlink()
        result = {
            "status": "timeout",
            "input": repo_relative_or_absolute(input_path),
            "hoa_file": repo_relative_or_absolute(output_path),
            "hoa_exists": False,
            "jar": repo_relative_or_absolute(jar_path),
            "command": command,
            "exit_code": None,
            "max_states": max_states,
            "timeout_seconds": timeout,
            "jtlv": use_jtlv,
        }
        result.update(output_fields(raw_output, include_raw_output, raw_output_tail_chars))
        return result, False

    raw_output = completed.stdout or ""
    if completed.stderr:
        raw_output = f"{raw_output}\n{completed.stderr}".strip()
    hoa_exists = output_path.is_file()
    hoa_size_bytes = output_path.stat().st_size if hoa_exists else None
    ok = completed.returncode == 0 and bool(hoa_size_bytes)
    if not ok and hoa_exists:
        output_path.unlink()
        hoa_exists = False
        hoa_size_bytes = None

    result = {
        "status": "exported" if ok else "error",
        "input": repo_relative_or_absolute(input_path),
        "input_sha256": sha256_file(input_path),
        "hoa_file": repo_relative_or_absolute(output_path),
        "hoa_exists": hoa_exists,
        "hoa_size_bytes": hoa_size_bytes,
        "jar": repo_relative_or_absolute(jar_path),
        "jar_sha256": sha256_file(jar_path),
        "command": command,
        "exit_code": completed.returncode,
        "max_states": max_states,
        "timeout_seconds": timeout,
        "jtlv": use_jtlv,
    }
    result.update(output_fields(raw_output, include_raw_output, raw_output_tail_chars))
    return result, ok


def normalize_condition(condition: str | None) -> str:
    if condition is None or not condition.strip():
        return "t"
    return condition.strip()


def missing_condition(conditions: list[str]) -> str:
    if not conditions:
        return "t"
    if len(conditions) == 1:
        return f"!({conditions[0]})"
    return "!(" + " | ".join(f"({condition})" for condition in conditions) + ")"


def normalize_properties(line: str) -> str:
    match = PROPERTIES_RE.match(line)
    if not match:
        return line
    properties = match.group(1).split()
    rewritten: list[str] = []
    for prop in properties:
        if prop == "state-labels":
            prop = "trans-labels"
        elif prop == "state-acc":
            prop = "trans-acc"
        if prop not in rewritten:
            rewritten.append(prop)
    if "trans-labels" not in rewritten:
        rewritten.append("trans-labels")
    if "explicit-labels" not in rewritten:
        rewritten.append("explicit-labels")
    return "properties: " + " ".join(rewritten)


def transform_hoa_state_labels_to_transitions(input_text: str, *, add_rejecting_sink: bool = True) -> tuple[str, dict[str, Any]]:
    lines = input_text.splitlines()
    body_index = lines.index("--BODY--")
    end_index = lines.index("--END--")
    header = lines[:body_index]
    body = lines[body_index + 1 : end_index]
    footer = lines[end_index:]

    state_labels: dict[int, str] = {}
    state_acceptance: dict[int, str | None] = {}
    transitions: dict[int, list[tuple[int, str | None]]] = {}
    state_order: list[int] = []
    current_state: int | None = None

    for line in body:
        if not line.strip():
            continue
        state_match = STATE_RE.match(line)
        if state_match:
            current_state = int(state_match.group(1))
            state_order.append(current_state)
            state_labels[current_state] = normalize_condition(state_match.group(2))
            state_acceptance[current_state] = state_match.group(3).strip() if state_match.group(3) else None
            transitions.setdefault(current_state, [])
            continue
        edge_match = EDGE_RE.match(line)
        if edge_match:
            if current_state is None:
                raise ValueError(f"Transition before first state: {line}")
            transitions.setdefault(current_state, []).append((int(edge_match.group(2)), edge_match.group(3)))
            continue
        raise ValueError(f"Unsupported HOA body line: {line}")

    missing_targets = sorted({target for edges in transitions.values() for target, _ in edges} - set(state_labels))
    if missing_targets:
        raise ValueError(f"Transitions reference missing states: {missing_targets}")

    declared_states = None
    for line in header:
        states_match = STATES_RE.match(line)
        if states_match:
            declared_states = int(states_match.group(1))
            break
    if declared_states is None:
        declared_states = max(state_order) + 1

    sink_state = max(state_order) + 1 if add_rejecting_sink else None
    output_state_count = max(declared_states, max(state_order) + 1)
    if sink_state is not None:
        output_state_count = max(output_state_count, sink_state + 1)

    final_header: list[str] = []
    inserted_states = False
    for line in header:
        if STATES_RE.match(line):
            final_header.append(f"States: {output_state_count}")
            inserted_states = True
        elif PROPERTIES_RE.match(line):
            final_header.append(normalize_properties(line))
        else:
            final_header.append(line)
    if not inserted_states:
        final_header.append(f"States: {output_state_count}")

    output_body: list[str] = []
    added_sink_edges = 0
    for state in state_order:
        output_body.append(f"State: {state}")
        edge_conditions: list[str] = []
        for target, edge_acceptance in transitions.get(state, []):
            condition = state_labels[target]
            acceptance = edge_acceptance or state_acceptance.get(target)
            suffix = f" {acceptance}" if acceptance else ""
            output_body.append(f"[{condition}] {target}{suffix}")
            edge_conditions.append(condition)
        if sink_state is not None:
            output_body.append(f"[{missing_condition(edge_conditions)}] {sink_state}")
            added_sink_edges += 1
    if sink_state is not None:
        output_body.append(f"State: {sink_state}")
        output_body.append("[t] " + str(sink_state))

    metadata = {
        "states_in": len(state_order),
        "states_out": output_state_count,
        "sink_added": sink_state is not None,
        "sink_state": sink_state,
        "sink_edges_added": added_sink_edges,
        "transition_label_source": "target_state_label",
        "acceptance_source": "target_state_acceptance",
    }
    return "\n".join(final_header + ["--BODY--"] + output_body + footer) + "\n", metadata


def normalize_hoa_file(input_path: Path, output_path: Path, add_rejecting_sink: bool, force: bool) -> dict[str, Any]:
    if output_path.exists() and not force:
        return {
            "status": "reused",
            "input": repo_relative_or_absolute(input_path),
            "output": repo_relative_or_absolute(output_path),
            "output_size_bytes": output_path.stat().st_size,
        }
    normalized, metadata = transform_hoa_state_labels_to_transitions(
        input_path.read_text(encoding="utf-8"),
        add_rejecting_sink=add_rejecting_sink,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(normalized, encoding="utf-8")
    return {
        "status": "normalized",
        "input": repo_relative_or_absolute(input_path),
        "output": repo_relative_or_absolute(output_path),
        "output_size_bytes": output_path.stat().st_size,
        **metadata,
    }


def alphabet_diagnostics(result: dict[str, Any]) -> dict[str, Any]:
    baseline_ap = list((result.get("baseline_automaton") or {}).get("ap") or [])
    generated_ap = list((result.get("generated_automaton") or {}).get("ap") or [])
    return {
        "baseline_ap": baseline_ap,
        "generated_ap": generated_ap,
        "baseline_only": sorted(set(baseline_ap) - set(generated_ap)),
        "generated_only": sorted(set(generated_ap) - set(baseline_ap)),
    }


def automata_are_structurally_compatible(result: dict[str, Any]) -> tuple[bool, str | None]:
    baseline = result.get("baseline_automaton") or {}
    generated = result.get("generated_automaton") or {}
    if baseline.get("deterministic") is not True or generated.get("deterministic") is not True:
        return False, "nondeterministic_automaton"
    if baseline.get("complete") != "yes" or generated.get("complete") != "yes":
        return False, "incomplete_automaton"
    return True, None


def determinize_automaton_for_distance(automaton):
    spot = buchi_distance.require_spot()
    candidates = [
        ("generic", ("generic", "deterministic", "complete")),
        ("parity", ("parity", "deterministic", "complete")),
        ("rabin", ("rabin", "deterministic", "complete")),
        ("deterministic_complete", ("deterministic", "complete")),
    ]
    errors: list[str] = []
    for name, options in candidates:
        try:
            processed = spot.postprocess(automaton, *options)
        except Exception as exc:
            errors.append(f"{name}: {type(exc).__name__}: {exc}")
            continue
        if processed.is_deterministic() and str(processed.prop_complete()) == "yes":
            return processed, {
                "status": "determinized",
                "method": f"spot.postprocess({', '.join(options)})",
                "states_before": automaton.num_states(),
                "states_after": processed.num_states(),
                "acceptance_before": str(automaton.get_acceptance()),
                "acceptance_after": str(processed.get_acceptance()),
            }
        errors.append(
            f"{name}: produced deterministic={processed.is_deterministic()} "
            f"complete={processed.prop_complete()} states={processed.num_states()}"
        )
    raise ValueError("Could not determinize automaton with Spot. Attempts: " + " | ".join(errors))


def maybe_determinize_automata(baseline_automaton, generated_automaton, *, enabled: bool) -> tuple[Any, Any, dict[str, Any], dict[str, Any]]:
    baseline_info = {
        "status": "not_needed" if baseline_automaton.is_deterministic() else "disabled",
        "states_before": baseline_automaton.num_states(),
        "states_after": baseline_automaton.num_states(),
    }
    generated_info = {
        "status": "not_needed" if generated_automaton.is_deterministic() else "disabled",
        "states_before": generated_automaton.num_states(),
        "states_after": generated_automaton.num_states(),
    }
    if not enabled:
        return baseline_automaton, generated_automaton, baseline_info, generated_info
    if not baseline_automaton.is_deterministic() or str(baseline_automaton.prop_complete()) != "yes":
        baseline_automaton, baseline_info = determinize_automaton_for_distance(baseline_automaton)
    if not generated_automaton.is_deterministic() or str(generated_automaton.prop_complete()) != "yes":
        generated_automaton, generated_info = determinize_automaton_for_distance(generated_automaton)
    return baseline_automaton, generated_automaton, baseline_info, generated_info


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate all synthesized reconstructed Spectra files for one model/skill combination "
            "against their accepted-dataset baselines."
        )
    )
    parser.add_argument("--skill", required=True, help="Skill/method to evaluate, e.g. respect-method-2.")
    parser.add_argument("--model", required=True, help="Model label, e.g. llama-3.")
    parser.add_argument("--runs-manifest", default=str(DEFAULT_RUNS_MANIFEST))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--output-jsonl", default=None, help="Explicit JSONL result path.")
    parser.add_argument("--jar", default=str(DEFAULT_JAR), help="Path to the modified spectra-cli.jar.")
    parser.add_argument("--max-states", type=int, default=100_000)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--limit", type=int, default=None, help="Evaluate at most N matching runs.")
    parser.add_argument(
        "--jtlv",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use Java BDD backend for HOA export. Enabled by default.",
    )
    parser.add_argument(
        "--normalize-hoa",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Move Spectra CLI state labels to transition labels before Spot import.",
    )
    parser.add_argument(
        "--add-rejecting-sink",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="During normalization, add a rejecting sink for missing valuations.",
    )
    parser.add_argument(
        "--determinize",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use Spot postprocessing to determinize nondeterministic automata before distance computation.",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing HOA artifacts.")
    parser.add_argument("--resume", action="store_true", help="Skip run_ids already present in the output JSONL.")
    parser.add_argument(
        "--preflight-spot",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Check Spot availability before exporting any HOA files. Enabled by default.",
    )
    parser.add_argument(
        "--preflight-java",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Check that Java is new enough for the modified Spectra CLI before exporting. Enabled by default.",
    )
    parser.add_argument("--include-raw-output", action="store_true")
    parser.add_argument("--raw-output-tail-chars", type=int, default=1000)
    parser.add_argument("--include-run-record", action="store_true")
    parser.add_argument("--debug-distance", action="store_true")
    parser.add_argument("--json", action="store_true", help="Print machine-readable summary.")
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
    return output_root(args) / "distances.jsonl"


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def java_major_version() -> tuple[int | None, str]:
    try:
        completed = subprocess.run(["java", "-version"], capture_output=True, text=True, check=False, timeout=10)
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"

    output = "\n".join(part for part in (completed.stderr, completed.stdout) if part).strip()
    match = re.search(r'version\s+"([^"]+)"', output)
    if not match:
        return None, output

    version = match.group(1)
    if version.startswith("1."):
        parts = version.split(".")
        try:
            return int(parts[1]), output
        except (IndexError, ValueError):
            return None, output
    try:
        return int(version.split(".", 1)[0]), output
    except ValueError:
        return None, output


def load_completed_run_ids(path: Path) -> set[str]:
    completed: set[str] = set()
    if not path.is_file():
        return completed
    for record in load_jsonl(path):
        run = record.get("run")
        if isinstance(run, dict) and isinstance(run.get("run_id"), str):
            completed.add(run["run_id"])
    return completed


def select_matching_runs(records: list[dict[str, Any]], skill: str, model: str) -> tuple[list[dict[str, Any]], Counter[str]]:
    skipped: Counter[str] = Counter()
    selected: list[dict[str, Any]] = []

    for record in records:
        if record.get("skill") != skill:
            skipped["other_skill"] += 1
            continue
        if not model_matches(record, model):
            skipped["other_model"] += 1
            continue
        if record.get("status") != "success":
            skipped["run_not_success"] += 1
            continue
        if record.get("reported_cli_status") != "synthesized":
            skipped[f"cli_status_{record.get('reported_cli_status') or 'missing'}"] += 1
            continue
        if not record.get("reconstructed_spectra_file"):
            skipped["missing_reconstructed_spectra_file"] += 1
            continue
        if not record.get("source_spectra_file"):
            skipped["missing_source_spectra_file"] += 1
            continue
        selected.append(record)

    return selected, skipped


def automaton_summary(automaton) -> dict[str, Any]:
    return {
        "states": automaton.num_states(),
        "ap": [str(ap) for ap in automaton.ap()],
        "deterministic": bool(automaton.is_deterministic()),
        "complete": str(automaton.prop_complete()),
    }


def evaluate_one_run(
    *,
    record: dict[str, Any],
    args: argparse.Namespace,
    jar_path: Path,
    artifacts_root: Path,
) -> dict[str, Any]:
    comparison_id = safe_path_part(str(record.get("run_id") or record.get("run_key") or record.get("dataset_id") or "run"))
    pair_output_dir = artifacts_root / "hoa" / comparison_id
    baseline_hoa = pair_output_dir / "baseline.hoa"
    generated_hoa = pair_output_dir / "generated.hoa"
    baseline_distance_hoa = pair_output_dir / "baseline.normalized.hoa"
    generated_distance_hoa = pair_output_dir / "generated.normalized.hoa"

    result: dict[str, Any] = {
        "status": "started",
        "comparison_id": comparison_id,
        "run": summarize_run(record, args.include_run_record),
        "baseline_export": None,
        "generated_export": None,
        "baseline_normalization": None,
        "generated_normalization": None,
        "baseline_determinization": None,
        "generated_determinization": None,
        "alphabet_diagnostics": None,
        "baseline_automaton": None,
        "generated_automaton": None,
        "baseline_automaton_after_determinization": None,
        "generated_automaton_after_determinization": None,
        "distance": None,
        "error": None,
    }

    try:
        baseline_spectra = resolve_input_path(str(record["source_spectra_file"]))
        generated_spectra = resolve_input_path(str(record["reconstructed_spectra_file"]))
        if not baseline_spectra.is_file():
            raise FileNotFoundError(f"Baseline Spectra file not found: {baseline_spectra}")
        if not generated_spectra.is_file():
            raise FileNotFoundError(f"Generated Spectra file not found: {generated_spectra}")

        baseline_export, baseline_ok = export_hoa(
            input_path=baseline_spectra,
            output_path=baseline_hoa,
            jar_path=jar_path,
            max_states=args.max_states,
            timeout=args.timeout,
            use_jtlv=args.jtlv,
            force=args.force,
            include_raw_output=args.include_raw_output,
            raw_output_tail_chars=args.raw_output_tail_chars,
        )
        generated_export, generated_ok = export_hoa(
            input_path=generated_spectra,
            output_path=generated_hoa,
            jar_path=jar_path,
            max_states=args.max_states,
            timeout=args.timeout,
            use_jtlv=args.jtlv,
            force=args.force,
            include_raw_output=args.include_raw_output,
            raw_output_tail_chars=args.raw_output_tail_chars,
        )
        result["baseline_export"] = baseline_export
        result["generated_export"] = generated_export

        if not (baseline_ok and generated_ok):
            result["status"] = "export_failed"
            return result

        if args.normalize_hoa:
            result["baseline_normalization"] = normalize_hoa_file(
                baseline_hoa,
                baseline_distance_hoa,
                add_rejecting_sink=args.add_rejecting_sink,
                force=args.force,
            )
            result["generated_normalization"] = normalize_hoa_file(
                generated_hoa,
                generated_distance_hoa,
                add_rejecting_sink=args.add_rejecting_sink,
                force=args.force,
            )
        else:
            baseline_distance_hoa = baseline_hoa
            generated_distance_hoa = generated_hoa

        spot = buchi_distance.require_spot()
        baseline_automaton = spot.automaton(str(baseline_distance_hoa))
        generated_automaton = spot.automaton(str(generated_distance_hoa))
        result["baseline_automaton"] = automaton_summary(baseline_automaton)
        result["generated_automaton"] = automaton_summary(generated_automaton)

        if result["baseline_automaton"]["ap"] != result["generated_automaton"]["ap"]:
            result["status"] = "alphabet_mismatch"
            result["error"] = "Cannot compute distance: alphabet_mismatch"
            result["alphabet_diagnostics"] = alphabet_diagnostics(result)
            return result

        baseline_automaton, generated_automaton, baseline_det, generated_det = maybe_determinize_automata(
            baseline_automaton,
            generated_automaton,
            enabled=args.determinize,
        )
        result["baseline_determinization"] = baseline_det
        result["generated_determinization"] = generated_det
        result["baseline_automaton_after_determinization"] = automaton_summary(baseline_automaton)
        result["generated_automaton_after_determinization"] = automaton_summary(generated_automaton)

        compatible_result = {
            "baseline_automaton": result["baseline_automaton_after_determinization"],
            "generated_automaton": result["generated_automaton_after_determinization"],
        }
        compatible, incompatibility = automata_are_structurally_compatible(compatible_result)
        if not compatible:
            result["status"] = incompatibility
            result["error"] = f"Cannot compute distance: {incompatibility}"
            return result
        result["distance"] = buchi_distance.compute_buchi_distance(
            baseline_automaton,
            generated_automaton,
            debug=args.debug_distance,
        )
        result["status"] = "success"
        return result
    except SystemExit as exc:
        result["status"] = "distance_unavailable"
        result["error"] = str(exc)
        return result
    except Exception as exc:
        result["status"] = "failed"
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result


def percent(count: int, total: int) -> float:
    return 0.0 if total == 0 else 100.0 * count / total


def summarize_results(
    *,
    args: argparse.Namespace,
    total_matching_runs: int,
    selected_runs: int,
    evaluated_records: list[dict[str, Any]],
    skipped: Counter[str],
    output_jsonl: Path,
) -> dict[str, Any]:
    statuses = Counter(str(record.get("status")) for record in evaluated_records)
    distances = [float(record["distance"]) for record in evaluated_records if record.get("status") == "success"]
    summary: dict[str, Any] = {
        "skill": args.skill,
        "model": args.model,
        "matching_synthesized_runs": total_matching_runs,
        "selected_runs": selected_runs,
        "evaluated_runs": len(evaluated_records),
        "output_jsonl": str(output_jsonl),
        "status_counts": [
            {"status": status, "count": count, "percent": percent(count, len(evaluated_records))}
            for status, count in sorted(statuses.items())
        ],
        "skipped_counts": dict(sorted(skipped.items())),
        "distance": {
            "count": len(distances),
            "mean": statistics.fmean(distances) if distances else None,
            "median": statistics.median(distances) if distances else None,
            "min": min(distances) if distances else None,
            "max": max(distances) if distances else None,
        },
    }
    return summary


def print_text_summary(summary: dict[str, Any]) -> None:
    print(f"Skill: {summary['skill']}")
    print(f"Model: {summary['model']}")
    print(f"Matching synthesized runs: {summary['matching_synthesized_runs']}")
    print(f"Selected runs: {summary['selected_runs']}")
    print(f"Evaluated runs: {summary['evaluated_runs']}")
    print(f"Results: {summary['output_jsonl']}")
    print()
    print("Statuses:")
    for item in summary["status_counts"]:
        print(f"  {item['status']}: {item['count']} ({item['percent']:.2f}%)")
    if summary["skipped_counts"]:
        print()
        print("Skipped while filtering:")
        for status, count in summary["skipped_counts"].items():
            print(f"  {status}: {count}")
    distance = summary["distance"]
    print()
    print(f"Successful distances: {distance['count']}")
    if distance["count"]:
        print(f"  mean: {distance['mean']:.6g}")
        print(f"  median: {distance['median']:.6g}")
        print(f"  min: {distance['min']:.6g}")
        print(f"  max: {distance['max']:.6g}")


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
    if not jar_path.is_file():
        print(json.dumps({"status": "error", "message": f"Modified spectra-cli.jar not found: {jar_path}"}, indent=2))
        return 2

    if args.preflight_java:
        major, java_output = java_major_version()
        if major is None or major < 17:
            summary = {
                "status": "java_unavailable" if major is None else "java_too_old",
                "message": (
                    "The modified Spectra CLI requires Java 17 or newer. "
                    f"Detected Java major version: {major if major is not None else 'unknown'}."
                ),
                "java_version_output": java_output,
                "skill": args.skill,
                "model": args.model,
                "matching_synthesized_runs": total_matching_runs,
                "selected_runs": len(matching),
                "output_jsonl": str(output_jsonl),
            }
            print(json.dumps(summary, indent=2, sort_keys=True) if args.json else summary["message"])
            return 1

    if args.preflight_spot:
        try:
            buchi_distance.require_spot()
        except SystemExit as exc:
            summary = {
                "status": "distance_unavailable",
                "message": str(exc),
                "skill": args.skill,
                "model": args.model,
                "matching_synthesized_runs": total_matching_runs,
                "selected_runs": len(matching),
                "output_jsonl": str(output_jsonl),
            }
            print(json.dumps(summary, indent=2, sort_keys=True) if args.json else summary["message"])
            return 1

    completed_run_ids = load_completed_run_ids(output_jsonl) if args.resume else set()
    evaluated_records: list[dict[str, Any]] = []
    if not args.resume and output_jsonl.exists():
        output_jsonl.unlink()

    for index, record in enumerate(matching, start=1):
        run_id = str(record.get("run_id") or "")
        if args.resume and run_id and run_id in completed_run_ids:
            continue
        print(f"[{index}/{len(matching)}] evaluating run_id={run_id or 'missing'}", file=sys.stderr)
        result = evaluate_one_run(record=record, args=args, jar_path=jar_path, artifacts_root=artifacts_root)
        if result.get("status") == "alphabet_mismatch":
            diagnostics = result.get("alphabet_diagnostics") or {}
            print(f"[{index}/{len(matching)}] alphabet mismatch for run_id={run_id or 'missing'}", file=sys.stderr)
            print(f"  baseline_ap: {diagnostics.get('baseline_ap')}", file=sys.stderr)
            print(f"  generated_ap: {diagnostics.get('generated_ap')}", file=sys.stderr)
            print(f"  baseline_only: {diagnostics.get('baseline_only')}", file=sys.stderr)
            print(f"  generated_only: {diagnostics.get('generated_only')}", file=sys.stderr)
        append_jsonl(output_jsonl, result)
        evaluated_records.append(result)

    if args.resume and output_jsonl.is_file():
        evaluated_records = load_jsonl(output_jsonl)

    summary = summarize_results(
        args=args,
        total_matching_runs=total_matching_runs,
        selected_runs=len(matching),
        evaluated_records=evaluated_records,
        skipped=skipped,
        output_jsonl=output_jsonl,
    )
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print_text_summary(summary)
    return 0 if all(record.get("status") == "success" for record in evaluated_records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
