#!/usr/bin/env python3
"""Create one evaluation JSON for each complete branched reconstruction run.

The evaluator reads `experiments/branched_runs/runs.jsonl`, skips incomplete
runs, validates every recorded generated Spectra artifact, and compares each
artifact against the original dataset Spectra file with the Buchi/Markov-chain
distance pipeline.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import multiprocessing
import re
import subprocess
import sys
import time
import os
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evaluation.buchi import buchi_distance, bounded_semantic_distance
from evaluation.buchi.evaluate_reconstruction_distances import (
    alphabet_diagnostics,
    apply_hoa_ap_mapping,
    automata_are_structurally_compatible,
    automaton_summary,
    export_hoa,
    generated_to_baseline,
    get_or_create_llm_mapping,
    maybe_determinize_automata,
    normalize_hoa_file,
    parse_spectra_signature,
)
from evaluation.buchi.evaluate_reconstruction_distances import (
    DEFAULT_JAR as DEFAULT_HOA_JAR,
)
from evaluation.signature_mapping import DEFAULT_MAPPING_FILE


DEFAULT_RUNS_MANIFEST = REPO_ROOT / "experiments" / "branched_runs" / "runs.jsonl"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "evaluation" / "branched_runs"
DEFAULT_CLI_WRAPPER = REPO_ROOT / ".agents" / "skills" / "respect" / "scripts" / "run_spectra_cli.py"
COMPLETE_BRANCH_STATUSES = {"success", "completed", "tests_passed"}
LOGGER = logging.getLogger("evaluate_branched_runs")


def parse_args() -> argparse.Namespace:
    """Parse command-line options for per-run branched evaluation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-manifest", default=str(DEFAULT_RUNS_MANIFEST))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--artifact-limit", type=int, default=None, help="Debug option: evaluate at most N Spectra artifacts per run.")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--cli-wrapper", default=str(DEFAULT_CLI_WRAPPER))
    parser.add_argument("--cli-timeout", type=float, default=120.0)
    parser.add_argument("--distance-timeout", type=float, default=120.0)
    parser.add_argument("--run-timeout", type=float, default=240.0)
    parser.add_argument("--hoa-jar", default=str(DEFAULT_HOA_JAR))
    parser.add_argument("--max-states", type=int, default=100_000)
    parser.add_argument("--jtlv", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--normalize-hoa", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--add-rejecting-sink", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--determinize", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--signature-mapping", choices=("strict", "llm"), default="llm")
    parser.add_argument(
        "--preflight-spot",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Require Spot Python bindings before evaluating. Enabled by default.",
    )
    parser.add_argument(
        "--allow-missing-spot",
        action="store_true",
        help="Continue without Spot and record distance_unavailable for distance metrics.",
    )
    parser.add_argument("--signature-mapping-file", default=str(DEFAULT_MAPPING_FILE))
    parser.add_argument("--mapping-model", default=None)
    parser.add_argument("--mapping-base-url", default=None)
    parser.add_argument("--mapping-timeout", type=float, default=120.0)
    parser.add_argument("--force-signature-mapping", action="store_true")
    parser.add_argument("--include-raw-output", action="store_true")
    parser.add_argument("--raw-output-tail-chars", type=int, default=1000)
    parser.add_argument("--bounded-semantic-distance", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--bounded-depth", type=int, default=10)
    parser.add_argument("--bounded-mode", choices=("random", "exhaustive"), default="random")
    parser.add_argument("--bounded-samples", type=int, default=1000)
    parser.add_argument("--bounded-seed", type=int, default=1)
    parser.add_argument("--bounded-max-prefixes", type=int, default=None)
    parser.add_argument("--debug-distance", action="store_true")
    parser.add_argument("--log-file", default=None)
    parser.add_argument("--log-level", default="INFO", choices=("DEBUG", "INFO", "WARNING", "ERROR"))
    return parser.parse_args()


def configure_logging(log_level: str, log_file: str | None) -> None:
    """Configure stderr and optional file logging for long evaluation runs."""
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    if log_file:
        log_path = resolve_repo_path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_path, encoding="utf-8"))
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
        force=True,
    )


def resolve_repo_path(path_value: str | Path) -> Path:
    """Resolve a path relative to the repository root when needed."""
    normalized = normalize_path_value_for_platform(str(path_value))
    path = Path(normalized)
    if path.is_absolute():
        return path
    return (REPO_ROOT / path).resolve()


def normalize_path_value_for_platform(path_value: str) -> str:
    """Normalize manifest paths written on Windows so they also work in WSL."""
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


def repo_relative_or_absolute(path: Path | None) -> str | None:
    """Return a compact repo-relative path when possible."""
    if path is None:
        return None
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(REPO_ROOT))
    except ValueError:
        return str(resolved)


def safe_path_part(value: str, max_length: int = 120) -> str:
    """Sanitize text for one path segment."""
    safe = "".join(char if char.isalnum() or char in "._=-" else "_" for char in value).strip("_")
    return (safe or "value")[:max_length]


def load_json(path: Path) -> Any:
    """Load a JSON file."""
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    """Write stable UTF-8 JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load non-empty JSONL records."""
    records: list[dict[str, Any]] = []
    if not path.is_file():
        return records
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return records


def sha256_file(path: Path) -> str:
    """Hash a file for distance cache metadata."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def output_fields(raw_output: str, include_raw_output: bool, tail_chars: int) -> dict[str, Any]:
    """Keep raw CLI output only when explicitly requested."""
    if include_raw_output:
        return {"raw_output": raw_output}
    tail = raw_output[-tail_chars:] if tail_chars > 0 else ""
    return {"raw_output_truncated": len(raw_output) > len(tail), "raw_output_tail": tail}


def run_cli_check(input_path: Path, args: argparse.Namespace, *, well_separation: bool = False) -> dict[str, Any]:
    """Run the normalized Spectra CLI wrapper for realizability or well-separation."""
    command = [sys.executable, str(resolve_repo_path(args.cli_wrapper)), "--input", str(input_path), "--timeout", str(args.cli_timeout)]
    if well_separation:
        command.append("--well-separation")
    LOGGER.debug("Running CLI check: input=%s well_separation=%s timeout=%s", repo_relative_or_absolute(input_path), well_separation, args.cli_timeout)
    try:
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=args.cli_timeout + 30,
        )
    except subprocess.TimeoutExpired as exc:
        raw_output = "\n".join(part for part in (exc.stdout or "", exc.stderr or "") if part).strip()
        result = {
            "status": "timeout",
            "exit_code": None,
            "command": command,
            "timeout_seconds": args.cli_timeout,
        }
        result.update(output_fields(raw_output, args.include_raw_output, args.raw_output_tail_chars))
        LOGGER.warning("CLI check timed out: input=%s well_separation=%s", repo_relative_or_absolute(input_path), well_separation)
        return result

    raw_output = "\n".join(part for part in (completed.stdout, completed.stderr) if part).strip()
    try:
        parsed = json.loads(completed.stdout) if completed.stdout.strip() else {}
    except json.JSONDecodeError:
        parsed = {"status": "unknown"}
    parsed["exit_code"] = completed.returncode
    parsed["command"] = command
    raw_fields = output_fields(str(parsed.pop("raw_output", raw_output)), args.include_raw_output, args.raw_output_tail_chars)
    parsed.update(raw_fields)
    LOGGER.debug(
        "CLI check finished: input=%s well_separation=%s status=%s exit_code=%s",
        repo_relative_or_absolute(input_path),
        well_separation,
        parsed.get("status"),
        parsed.get("exit_code"),
    )
    return parsed


def count_repair_log_entries(path_value: str | None) -> int | None:
    """Count JSONL repair-log entries when a branch reported a log."""
    if not path_value:
        return None
    path = resolve_repo_path(path_value)
    if not path.is_file():
        return None
    return len(load_jsonl(path))


def is_complete_record(record: dict[str, Any]) -> tuple[bool, str | None]:
    """Keep only fully finished branched runs for evaluation."""
    if record.get("dry_run"):
        return False, "dry_run"
    if record.get("status") != "success":
        return False, f"run_status_{record.get('status') or 'missing'}"
    branches = record.get("branches")
    if not isinstance(branches, dict) or not branches:
        return False, "missing_branches"
    requested = record.get("branches_requested") or []
    for branch_name in requested:
        branch = branches.get(branch_name)
        if not isinstance(branch, dict):
            return False, f"missing_branch_{branch_name}"
        if branch.get("status") not in COMPLETE_BRANCH_STATUSES:
            return False, f"branch_{branch_name}_status_{branch.get('status') or 'missing'}"
    return True, None


def walk_branch_nodes(branch_name: str, value: Any, path: tuple[str, ...] = ()) -> list[dict[str, Any]]:
    """Find nested branch result dictionaries that reference Spectra files."""
    nodes: list[dict[str, Any]] = []
    if isinstance(value, dict):
        # Cross repair nests the incumbent/challenger agent results below the
        # branch summary, while other branches keep their artifacts directly at
        # branch level. Recursing here gives the evaluator one uniform view.
        has_spectra = bool(value.get("final_spectra_file") or value.get("intermediate_spectra_files"))
        if has_spectra:
            nodes.append(
                {
                    "branch": branch_name,
                    "path": list(path),
                    "lineage": value.get("lineage"),
                    "role": value.get("role") or (path[-1] if path else branch_name),
                    "status": value.get("status"),
                    "reported": value.get("reported") if isinstance(value.get("reported"), dict) else {},
                    "repair_log_file": value.get("repair_log_file"),
                    "diagnostic_files": value.get("diagnostic_files") or [],
                    "broker_feedback_files": value.get("broker_feedback_files") or [],
                    "test_files": value.get("test_files") or [],
                    "final_spectra_file": value.get("final_spectra_file"),
                    "intermediate_spectra_files": value.get("intermediate_spectra_files") or {},
                }
            )
        for key, child in value.items():
            if key in {"reported", "intermediate_spectra_files"}:
                continue
            nodes.extend(walk_branch_nodes(branch_name, child, (*path, str(key))))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            nodes.extend(walk_branch_nodes(branch_name, child, (*path, str(index))))
    return nodes


def collect_spectra_records(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten all generated Spectra artifacts recorded in one branched run."""
    collected: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    branches = record.get("branches") or {}
    for branch_name, branch in branches.items():
        for node in walk_branch_nodes(branch_name, branch):
            spectra_by_stage = dict(node["intermediate_spectra_files"])
            if node["final_spectra_file"] and "final" not in spectra_by_stage:
                spectra_by_stage["final"] = node["final_spectra_file"]
            for stage, spectra_value in sorted(spectra_by_stage.items()):
                if not spectra_value:
                    continue
                key = (
                    branch_name,
                    str(node.get("lineage") or ""),
                    str(stage),
                    str(spectra_value),
                )
                if key in seen:
                    continue
                seen.add(key)
                reported = node["reported"]
                collected.append(
                    {
                        "branch": branch_name,
                        "lineage": node.get("lineage"),
                        "role": node.get("role"),
                        "node_path": node.get("path"),
                        "branch_status": node.get("status"),
                        "stage": stage,
                        "spectra_file": str(spectra_value),
                        "reported_cli_status": reported.get("cli_status"),
                        "reported_well_separation_status": reported.get("well_separation_status"),
                        "repair_loops": reported.get("repair_loops"),
                        "syntax_repair_loops": reported.get("syntax_repair_loops"),
                        "unrealizable_repair_loops": reported.get("unrealizable_repair_loops"),
                        "well_separation_repair_loops": reported.get("well_separation_repair_loops"),
                        "test_repair_loops": reported.get("test_repair_loops"),
                        "broker_repair_loops": reported.get("broker_repair_loops"),
                        "repair_log_entries": count_repair_log_entries(node.get("repair_log_file")),
                        "diagnostic_file_count": len(node.get("diagnostic_files") or []),
                        "broker_feedback_file_count": len(node.get("broker_feedback_files") or []),
                        "test_file_count": len(node.get("test_files") or []),
                        "tests_total": reported.get("tests_total"),
                        "tests_passed": reported.get("tests_passed"),
                        "tests_failed": reported.get("tests_failed"),
                    }
                )
    return collected


def distance_settings(args: argparse.Namespace, jar_path: Path) -> SimpleNamespace:
    """Build the small settings object expected by reused distance helpers."""
    return SimpleNamespace(
        max_states=args.max_states,
        timeout=args.distance_timeout,
        run_timeout=args.run_timeout,
        jtlv=args.jtlv,
        force=args.force,
        include_raw_output=args.include_raw_output,
        raw_output_tail_chars=args.raw_output_tail_chars,
        normalize_hoa=args.normalize_hoa,
        add_rejecting_sink=args.add_rejecting_sink,
        determinize=args.determinize,
        signature_mapping=args.signature_mapping,
        signature_mapping_file=args.signature_mapping_file,
        mapping_model=args.mapping_model,
        mapping_base_url=args.mapping_base_url,
        mapping_timeout=args.mapping_timeout,
        force_signature_mapping=args.force_signature_mapping,
        bounded_semantic_distance=args.bounded_semantic_distance,
        bounded_depth=args.bounded_depth,
        bounded_mode=args.bounded_mode,
        bounded_samples=args.bounded_samples,
        bounded_seed=args.bounded_seed,
        bounded_max_prefixes=args.bounded_max_prefixes,
        debug_distance=args.debug_distance,
        jar_sha256=sha256_file(jar_path) if jar_path.is_file() else None,
    )


def evaluate_distance(
    *,
    source_spectra: Path,
    generated_spectra: Path,
    output_dir: Path,
    args: argparse.Namespace,
    settings: SimpleNamespace,
    jar_path: Path,
) -> dict[str, Any]:
    """Compute the Buchi/Markov-chain distance for one generated Spectra file."""
    baseline_hoa = output_dir / "baseline.hoa"
    generated_hoa = output_dir / "generated.hoa"
    baseline_distance_hoa = output_dir / "baseline.normalized.hoa"
    generated_distance_hoa = output_dir / "generated.normalized.hoa"
    generated_mapped_hoa = output_dir / "generated.normalized.mapped.hoa"
    result: dict[str, Any] = {
        "status": "started",
        "distance": None,
        "bounded_semantic_distance": None,
        "error": None,
        "source_spectra_sha256": sha256_file(source_spectra) if source_spectra.is_file() else None,
        "generated_spectra_sha256": sha256_file(generated_spectra) if generated_spectra.is_file() else None,
        "settings": {
            "jar_sha256": settings.jar_sha256,
            "max_states": settings.max_states,
            "jtlv": settings.jtlv,
            "normalize_hoa": settings.normalize_hoa,
            "add_rejecting_sink": settings.add_rejecting_sink,
            "determinize": settings.determinize,
            "distance_semantics": "relative_bscc_raw_valid_letter_mean_coverage_v1",
            "signature_mapping": settings.signature_mapping,
        },
    }
    try:
        LOGGER.info(
            "Starting distance: source=%s generated=%s output=%s",
            repo_relative_or_absolute(source_spectra),
            repo_relative_or_absolute(generated_spectra),
            repo_relative_or_absolute(output_dir),
        )
        baseline_export, baseline_ok = export_hoa(
            input_path=source_spectra,
            output_path=baseline_hoa,
            jar_path=jar_path,
            max_states=settings.max_states,
            timeout=settings.timeout,
            use_jtlv=settings.jtlv,
            force=args.force,
            include_raw_output=args.include_raw_output,
            raw_output_tail_chars=args.raw_output_tail_chars,
        )
        generated_export, generated_ok = export_hoa(
            input_path=generated_spectra,
            output_path=generated_hoa,
            jar_path=jar_path,
            max_states=settings.max_states,
            timeout=settings.timeout,
            use_jtlv=settings.jtlv,
            force=args.force,
            include_raw_output=args.include_raw_output,
            raw_output_tail_chars=args.raw_output_tail_chars,
        )
        result["baseline_export"] = baseline_export
        result["generated_export"] = generated_export
        if not (baseline_ok and generated_ok):
            result["status"] = "export_failed"
            LOGGER.warning(
                "Distance export failed: generated=%s baseline_ok=%s generated_ok=%s",
                repo_relative_or_absolute(generated_spectra),
                baseline_ok,
                generated_ok,
            )
            return result

        # The Spectra CLI exports state-labeled HOA. The distance code expects
        # transition-labeled, complete automata over compatible AP alphabets.
        if settings.normalize_hoa:
            result["baseline_normalization"] = normalize_hoa_file(
                baseline_hoa,
                baseline_distance_hoa,
                add_rejecting_sink=settings.add_rejecting_sink,
                force=args.force,
            )
            result["generated_normalization"] = normalize_hoa_file(
                generated_hoa,
                generated_distance_hoa,
                add_rejecting_sink=settings.add_rejecting_sink,
                force=args.force,
            )
        else:
            baseline_distance_hoa = baseline_hoa
            generated_distance_hoa = generated_hoa

        spot = buchi_distance.require_spot()
        baseline_automaton = spot.automaton(str(baseline_distance_hoa))
        generated_automaton = spot.automaton(str(generated_distance_hoa))
        baseline_pre = automaton_summary(baseline_automaton)
        generated_pre = automaton_summary(generated_automaton)
        result["pre_mapping_alphabet_mismatch"] = baseline_pre["ap"] != generated_pre["ap"]

        if settings.signature_mapping == "llm" and result["pre_mapping_alphabet_mismatch"]:
            result["signature_mapping_attempted"] = True
            baseline_signature = parse_spectra_signature(source_spectra)
            generated_signature = parse_spectra_signature(generated_spectra)
            if baseline_signature.get("status") == "success" and generated_signature.get("status") == "success":
                mapping_record = get_or_create_llm_mapping(
                    baseline_signature=baseline_signature,
                    generated_signature=generated_signature,
                    mapping_file=resolve_repo_path(settings.signature_mapping_file),
                    model=settings.mapping_model,
                    base_url=settings.mapping_base_url,
                    timeout=settings.mapping_timeout,
                    force=settings.force_signature_mapping,
                )
                result["signature_mapping_record"] = {
                    "mapping_key": mapping_record.get("mapping_key"),
                    "api_status": mapping_record.get("api_status"),
                    "model": mapping_record.get("model"),
                    "usable": mapping_record.get("usable"),
                    "validation_errors": mapping_record.get("validation_errors"),
                }
                result["signature_mapping_usable"] = bool(mapping_record.get("usable"))
                result["signature_mapping"] = mapping_record.get("mapping")
                if mapping_record.get("usable"):
                    mapped_text = apply_hoa_ap_mapping(
                        generated_distance_hoa.read_text(encoding="utf-8", errors="replace"),
                        generated_to_baseline(mapping_record["mapping"]),
                    )
                    generated_mapped_hoa.write_text(mapped_text, encoding="utf-8")
                    generated_distance_hoa = generated_mapped_hoa
                    result["signature_mapping_used"] = True

        baseline_automaton = spot.automaton(str(baseline_distance_hoa))
        generated_automaton = spot.automaton(str(generated_distance_hoa))
        result["baseline_automaton"] = automaton_summary(baseline_automaton)
        result["generated_automaton"] = automaton_summary(generated_automaton)

        if result["baseline_automaton"]["ap"] != result["generated_automaton"]["ap"]:
            result["status"] = "alphabet_mismatch"
            result["error"] = "Cannot compute distance: alphabet_mismatch"
            result["alphabet_diagnostics"] = alphabet_diagnostics(result)
            LOGGER.warning("Distance alphabet mismatch: generated=%s", repo_relative_or_absolute(generated_spectra))
            return result

        baseline_automaton, generated_automaton, baseline_det, generated_det = maybe_determinize_automata(
            baseline_automaton,
            generated_automaton,
            enabled=settings.determinize,
        )
        result["baseline_determinization"] = baseline_det
        result["generated_determinization"] = generated_det
        result["baseline_automaton_after_determinization"] = automaton_summary(baseline_automaton)
        result["generated_automaton_after_determinization"] = automaton_summary(generated_automaton)

        compatible, incompatibility = automata_are_structurally_compatible(
            {
                "baseline_automaton": result["baseline_automaton_after_determinization"],
                "generated_automaton": result["generated_automaton_after_determinization"],
            }
        )
        if not compatible:
            result["status"] = incompatibility
            result["error"] = f"Cannot compute distance: {incompatibility}"
            return result

        result["distance"] = buchi_distance.compute_buchi_distance(
            baseline_automaton,
            generated_automaton,
            debug=settings.debug_distance,
        )
        if settings.bounded_semantic_distance:
            result["bounded_semantic_distance"] = bounded_semantic_distance.compute_bounded_semantic_distance(
                baseline_automaton,
                generated_automaton,
                depth=settings.bounded_depth,
                mode=settings.bounded_mode,
                samples=settings.bounded_samples,
                seed=settings.bounded_seed,
                max_prefixes=settings.bounded_max_prefixes,
            )
        result["status"] = "success"
        LOGGER.info(
            "Distance finished: generated=%s distance=%s",
            repo_relative_or_absolute(generated_spectra),
            result["distance"],
        )
        return result
    except SystemExit as exc:
        result["status"] = "distance_unavailable"
        result["error"] = str(exc)
        LOGGER.warning("Distance unavailable: generated=%s error=%s", repo_relative_or_absolute(generated_spectra), result["error"])
        return result
    except Exception as exc:
        result["status"] = "failed"
        result["error"] = f"{type(exc).__name__}: {exc}"
        LOGGER.exception("Distance failed: generated=%s", repo_relative_or_absolute(generated_spectra))
        return result


def distance_worker(queue: multiprocessing.Queue, kwargs: dict[str, Any]) -> None:
    """Run one distance computation in a child process for hard timeouts."""
    try:
        queue.put(evaluate_distance(**kwargs))
    except BaseException as exc:
        queue.put({"status": "failed", "distance": None, "error": f"{type(exc).__name__}: {exc}"})


def evaluate_distance_with_timeout(**kwargs: Any) -> dict[str, Any]:
    """Compute distance with a wall-clock timeout around the whole comparison."""
    args = kwargs["args"]
    run_timeout = float(args.run_timeout or 0)
    if run_timeout <= 0:
        return evaluate_distance(**kwargs)

    queue: multiprocessing.Queue = multiprocessing.Queue(maxsize=1)
    process = multiprocessing.Process(target=distance_worker, args=(queue, kwargs))
    process.start()
    process.join(run_timeout)
    if process.is_alive():
        process.terminate()
        process.join(5)
        if process.is_alive():
            process.kill()
            process.join(5)
        return {
            "status": "run_timeout",
            "distance": None,
            "bounded_semantic_distance": None,
            "error": f"Distance computation exceeded {run_timeout} seconds.",
            "settings": {
                "run_timeout": run_timeout,
            },
        }
    if not queue.empty():
        return queue.get()
    if process.exitcode == 0:
        return {"status": "failed", "distance": None, "error": "Distance worker exited without a result."}
    return {"status": "failed", "distance": None, "error": f"Distance worker exit code {process.exitcode}."}


def evaluate_spectra_artifact(
    *,
    artifact: dict[str, Any],
    source_spectra: Path,
    run_output_dir: Path,
    args: argparse.Namespace,
    settings: SimpleNamespace,
    jar_path: Path,
) -> dict[str, Any]:
    """Evaluate one generated Spectra artifact."""
    spectra_path = resolve_repo_path(artifact["spectra_file"])
    LOGGER.info(
        "Evaluating artifact: branch=%s lineage=%s role=%s stage=%s file=%s",
        artifact.get("branch"),
        artifact.get("lineage"),
        artifact.get("role"),
        artifact.get("stage"),
        repo_relative_or_absolute(spectra_path),
    )
    result = dict(artifact)
    result["spectra_file"] = repo_relative_or_absolute(spectra_path)
    result["exists"] = spectra_path.is_file()
    result["source_spectra_file"] = repo_relative_or_absolute(source_spectra)
    if not spectra_path.is_file():
        LOGGER.warning("Skipping missing Spectra artifact: %s", repo_relative_or_absolute(spectra_path))
        result["validation"] = {"status": "missing_file"}
        result["distance"] = {"status": "missing_file", "distance": None}
        return result

    cli_result = run_cli_check(spectra_path, args)
    cli_status = cli_result.get("status")
    syntax_ok = cli_status in {"unrealizable", "realizable", "synthesized"}
    realizable = cli_status in {"realizable", "synthesized"}
    validation: dict[str, Any] = {
        "cli": cli_result,
        "syntax_ok": syntax_ok,
        "realizable": realizable,
        "well_separation": None,
        "well_separated": None,
    }
    if realizable:
        well_result = run_cli_check(spectra_path, args, well_separation=True)
        validation["well_separation"] = well_result
        validation["well_separated"] = well_result.get("status") == "well_separated"
    result["validation"] = validation
    LOGGER.info(
        "Validation finished: file=%s syntax_ok=%s realizable=%s well_separated=%s",
        repo_relative_or_absolute(spectra_path),
        validation["syntax_ok"],
        validation["realizable"],
        validation["well_separated"],
    )

    distance_dir = run_output_dir / "distances" / safe_path_part(
        "__".join(
            str(value)
            for value in (
                artifact.get("branch"),
                artifact.get("lineage"),
                artifact.get("role"),
                artifact.get("stage"),
                sha256_file(spectra_path)[:12],
            )
            if value is not None
        )
    )
    result["distance"] = evaluate_distance_with_timeout(
        source_spectra=source_spectra,
        generated_spectra=spectra_path,
        output_dir=distance_dir,
        args=args,
        settings=settings,
        jar_path=jar_path,
    )
    LOGGER.info(
        "Artifact distance status: file=%s status=%s distance=%s",
        repo_relative_or_absolute(spectra_path),
        result["distance"].get("status"),
        result["distance"].get("distance"),
    )
    return result


def evaluate_one_branched_run(record: dict[str, Any], args: argparse.Namespace, output_root: Path, jar_path: Path) -> dict[str, Any]:
    """Build and write the evaluation JSON for one complete branched run."""
    run_id = str(record.get("run_id") or record.get("core_run_id") or "run")
    run_output_dir = output_root / safe_path_part(run_id)
    source_spectra = resolve_repo_path(str(record["source_spectra_file"]))
    settings = distance_settings(args, jar_path)
    started = time.perf_counter()
    artifacts = collect_spectra_records(record)
    if args.artifact_limit is not None:
        artifacts = artifacts[: args.artifact_limit]
    LOGGER.info(
        "Evaluating branched run: run_id=%s source=%s artifacts=%s output=%s",
        run_id,
        repo_relative_or_absolute(source_spectra),
        len(artifacts),
        repo_relative_or_absolute(run_output_dir / "evaluation.json"),
    )
    evaluated_artifacts = [
        evaluate_spectra_artifact(
            artifact=artifact,
            source_spectra=source_spectra,
            run_output_dir=run_output_dir,
            args=args,
            settings=settings,
            jar_path=jar_path,
        )
        for artifact in artifacts
    ]
    validation_counts = Counter()
    distance_counts = Counter()
    for artifact in evaluated_artifacts:
        validation = artifact.get("validation") or {}
        validation_counts[f"syntax_ok_{bool(validation.get('syntax_ok'))}"] += 1
        validation_counts[f"realizable_{bool(validation.get('realizable'))}"] += 1
        if validation.get("well_separated") is not None:
            validation_counts[f"well_separated_{bool(validation.get('well_separated'))}"] += 1
        distance_counts[str((artifact.get("distance") or {}).get("status") or "missing")] += 1

    evaluation = {
        "schema_version": "branched_run_evaluation_v1",
        "run": {
            "run_id": record.get("run_id"),
            "run_key": record.get("run_key"),
            "core_run_id": record.get("core_run_id"),
            "status": record.get("status"),
            "description_id": record.get("description_id"),
            "dataset_id": record.get("dataset_id"),
            "description_file": record.get("description_file"),
            "source_spectra_file": repo_relative_or_absolute(source_spectra),
            "source_repository_full_name": record.get("source_repository_full_name"),
            "source_path": record.get("source_path"),
            "branches_requested": record.get("branches_requested"),
            "timeout_seconds": record.get("timeout_seconds"),
            "broker_timeout_seconds": record.get("broker_timeout_seconds"),
        },
        "evaluation": {
            "status": "success",
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "artifact_count": len(evaluated_artifacts),
            "validation_counts": dict(validation_counts),
            "distance_status_counts": dict(distance_counts),
        },
        "artifacts": evaluated_artifacts,
    }
    write_json(run_output_dir / "evaluation.json", evaluation)
    LOGGER.info(
        "Finished branched run evaluation: run_id=%s artifacts=%s duration_ms=%s",
        run_id,
        len(evaluated_artifacts),
        evaluation["evaluation"]["duration_ms"],
    )
    return evaluation


def main() -> int:
    """Evaluate complete records from the branched-run manifest."""
    args = parse_args()
    configure_logging(args.log_level, args.log_file)
    if args.preflight_spot and not args.allow_missing_spot:
        try:
            buchi_distance.require_spot()
        except SystemExit as exc:
            LOGGER.error("%s", exc)
            LOGGER.error("Install/run in the Spot-enabled WSL/conda environment, or pass --allow-missing-spot for validation-only output.")
            return 2
    runs_manifest = resolve_repo_path(args.runs_manifest)
    output_root = resolve_repo_path(args.output_root)
    jar_path = resolve_repo_path(args.hoa_jar)
    records = load_jsonl(runs_manifest)
    LOGGER.info(
        "Starting branched evaluation: manifest=%s records=%s output=%s limit=%s",
        repo_relative_or_absolute(runs_manifest),
        len(records),
        repo_relative_or_absolute(output_root),
        args.limit,
    )
    stats: Counter[str] = Counter()
    evaluated = 0
    written: list[str] = []

    for record in records:
        complete, reason = is_complete_record(record)
        if not complete:
            stats[f"skipped_{reason}"] += 1
            LOGGER.debug("Skipping run_id=%s reason=%s", record.get("run_id"), reason)
            continue
        if args.limit is not None and evaluated >= args.limit:
            break
        run_id = str(record.get("run_id") or record.get("core_run_id") or "run")
        output_file = output_root / safe_path_part(run_id) / "evaluation.json"
        if output_file.is_file() and not args.force:
            stats["skipped_existing"] += 1
            LOGGER.info("Skipping existing evaluation: run_id=%s output=%s", run_id, repo_relative_or_absolute(output_file))
            continue
        evaluation = evaluate_one_branched_run(record, args, output_root, jar_path)
        evaluated += 1
        stats["evaluated"] += 1
        written.append(str(output_root / safe_path_part(run_id) / "evaluation.json"))
        print(
            f"evaluated run_id={run_id} artifacts={evaluation['evaluation']['artifact_count']} "
            f"output={repo_relative_or_absolute(output_root / safe_path_part(run_id) / 'evaluation.json')}",
            file=sys.stderr,
        )

    summary = {
        "runs_manifest": str(runs_manifest),
        "output_root": str(output_root),
        "stats": dict(stats),
        "written": written,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    LOGGER.info("Finished branched evaluation: stats=%s", dict(stats))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
