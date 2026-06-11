#!/usr/bin/env python3
"""Batch distance evaluation for synthesized reconstruction runs."""

from __future__ import annotations

import argparse
import json
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
from evaluation.compare_reconstruction_distance import (
    DEFAULT_RUNS_MANIFEST,
    alphabet_diagnostics,
    automata_are_distance_compatible,
    automata_are_structurally_compatible,
    maybe_determinize_automata,
    export_hoa,
    load_jsonl,
    model_matches,
    normalize_hoa_file,
    safe_path_part,
    summarize_run,
)
from evaluation.export_spectra_to_hoa import DEFAULT_JAR, resolve_existing_path, resolve_input_path


DEFAULT_OUTPUT_ROOT = REPO_ROOT / "evaluation" / "distance_results"


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
