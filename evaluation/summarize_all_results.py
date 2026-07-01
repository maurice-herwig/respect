#!/usr/bin/env python3
"""Combine all available ReSpect evaluation summaries for one model/skill."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evaluation.evaluate_controller_distances import (  # noqa: E402
    DEFAULT_OUTPUT_ROOT as DEFAULT_CONTROLLER_DISTANCE_ROOT,
)
from evaluation.buchi.evaluate_reconstruction_distances import (  # noqa: E402
    DEFAULT_OUTPUT_ROOT as DEFAULT_BUCHI_DISTANCE_ROOT,
    DEFAULT_RUNS_MANIFEST,
    load_jsonl,
    percent,
    resolve_existing_path,
    safe_path_part,
    select_matching_runs,
)
from evaluation.summarize_reconstruction_runs import summarize as summarize_reconstruction_runs  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill", required=True, help="Skill/method to summarize, e.g. respect-method-2.")
    parser.add_argument("--model", required=True, help="Model label, e.g. llama-3.")
    parser.add_argument("--runs-manifest", default=str(DEFAULT_RUNS_MANIFEST))
    parser.add_argument("--buchi-distance-root", default=str(DEFAULT_BUCHI_DISTANCE_ROOT))
    parser.add_argument("--controller-distance-root", default=str(DEFAULT_CONTROLLER_DISTANCE_ROOT))
    parser.add_argument("--buchi-distance-jsonl", default=None)
    parser.add_argument("--controller-distance-jsonl", default=None)
    parser.add_argument("--include-dry-run", action="store_true")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser.parse_args()


def resolve_repo_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def distance_jsonl_path(root: str | Path, skill: str, model: str, file_name: str) -> Path:
    root_path = resolve_repo_path(root)
    return root_path / safe_path_part(skill) / safe_path_part(model) / file_name


def stats(values: list[float]) -> dict[str, float | int | None]:
    return {
        "count": len(values),
        "mean": statistics.fmean(values) if values else None,
        "median": statistics.median(values) if values else None,
        "min": min(values) if values else None,
        "max": max(values) if values else None,
    }


def status_counts(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter(str(record.get("status")) for record in records)
    total = len(records)
    return [
        {
            "status": status,
            "count": count,
            "percent": percent(count, total),
        }
        for status, count in sorted(counts.items())
    ]


def missing_distance_summary(path: Path, matching_synthesized_runs: int) -> dict[str, Any]:
    return {
        "available": False,
        "skipped": True,
        "skip_reason": "file_not_found",
        "output_jsonl": str(path),
        "matching_synthesized_runs": matching_synthesized_runs,
        "evaluated_runs": 0,
        "status_counts": [],
        "skipped_counts": {},
    }


def summarize_buchi_distance(path: Path, matching_synthesized_runs: int, skipped: Counter[str]) -> dict[str, Any]:
    exists = path.is_file()
    if not exists:
        summary = missing_distance_summary(path, matching_synthesized_runs)
        summary.update(
            {
                "distance": stats([]),
                "bounded_mismatch_rate": stats([]),
                "bounded_false_negative_rate": stats([]),
                "bounded_false_positive_rate": stats([]),
                "bounded_jaccard_distance": stats([]),
            }
        )
        return summary

    records = load_jsonl(path)
    distances = [float(record["distance"]) for record in records if record.get("status") == "success" and record.get("distance") is not None]
    pre_mapping_alphabet_mismatch = sum(
        1 for record in records if record.get("pre_mapping_alphabet_mismatch") is True
    )
    signature_mapping_attempted = sum(
        1 for record in records if record.get("signature_mapping_attempted") is True
    )
    signature_mapping_usable = sum(
        1 for record in records if record.get("signature_mapping_usable") is True
    )
    signature_mapping_used = sum(
        1 for record in records if record.get("signature_mapping_used") is True
    )
    run_timeouts = sum(1 for record in records if record.get("status") == "run_timeout")

    def bounded_values(key: str) -> list[float]:
        values: list[float] = []
        for record in records:
            if record.get("status") != "success":
                continue
            bounded = record.get("bounded_semantic_distance") or {}
            if bounded.get(key) is not None:
                values.append(float(bounded[key]))
        return values

    return {
        "available": exists,
        "skipped": False,
        "skip_reason": None,
        "output_jsonl": str(path),
        "matching_synthesized_runs": matching_synthesized_runs,
        "evaluated_runs": len(records),
        "status_counts": status_counts(records),
        "skipped_counts": dict(sorted(skipped.items())),
        "distance": stats(distances),
        "run_timeouts": {
            "count": run_timeouts,
            "percent": percent(run_timeouts, len(records)),
        },
        "alphabet_mapping": {
            "pre_mapping_alphabet_mismatch": {
                "count": pre_mapping_alphabet_mismatch,
                "percent": percent(pre_mapping_alphabet_mismatch, len(records)),
            },
            "signature_mapping_attempted": {
                "count": signature_mapping_attempted,
                "percent": percent(signature_mapping_attempted, len(records)),
            },
            "signature_mapping_usable": {
                "count": signature_mapping_usable,
                "percent": percent(signature_mapping_usable, len(records)),
                "percent_of_attempted": percent(signature_mapping_usable, signature_mapping_attempted),
            },
            "signature_mapping_used": {
                "count": signature_mapping_used,
                "percent": percent(signature_mapping_used, len(records)),
                "percent_of_pre_mapping_mismatches": percent(signature_mapping_used, pre_mapping_alphabet_mismatch),
            },
        },
        "bounded_mismatch_rate": stats(bounded_values("mismatch_rate")),
        "bounded_false_negative_rate": stats(bounded_values("false_negative_rate")),
        "bounded_false_positive_rate": stats(bounded_values("false_positive_rate")),
        "bounded_jaccard_distance": stats(bounded_values("jaccard_distance")),
    }


def summarize_controller_distance(path: Path, matching_synthesized_runs: int, skipped: Counter[str]) -> dict[str, Any]:
    exists = path.is_file()
    if not exists:
        summary = missing_distance_summary(path, matching_synthesized_runs)
        summary.update(
            {
                "trace_mismatch_rate": stats([]),
                "step_mismatch_rate": stats([]),
                "output_hamming_mismatch_rate": stats([]),
            }
        )
        return summary

    records = load_jsonl(path)

    def rate_values(key: str) -> list[float]:
        values: list[float] = []
        for record in records:
            if record.get("status") != "success":
                continue
            distance = record.get("distance") or {}
            if distance.get(key) is not None:
                values.append(float(distance[key]))
        return values

    return {
        "available": exists,
        "skipped": False,
        "skip_reason": None,
        "output_jsonl": str(path),
        "matching_synthesized_runs": matching_synthesized_runs,
        "evaluated_runs": len(records),
        "status_counts": status_counts(records),
        "skipped_counts": dict(sorted(skipped.items())),
        "trace_mismatch_rate": stats(rate_values("trace_mismatch_rate")),
        "step_mismatch_rate": stats(rate_values("step_mismatch_rate")),
        "output_hamming_mismatch_rate": stats(rate_values("output_hamming_mismatch_rate")),
    }


def print_distribution(title: str, items: list[dict[str, Any]], key_name: str = "status") -> None:
    print(title)
    if not items:
        print("    none")
        return
    for item in items:
        print(f"    {item[key_name]}: {item['count']} ({item['percent']:.2f}%)")


def print_stats(title: str, values: dict[str, Any]) -> None:
    print(title)
    print(f"    count: {values['count']}")
    if values["count"]:
        print(f"    mean: {values['mean']:.6g}")
        print(f"    median: {values['median']:.6g}")
        print(f"    min: {values['min']:.6g}")
        print(f"    max: {values['max']:.6g}")


def print_skipped_counts(skipped_counts: dict[str, int]) -> None:
    print("  skipped_counts:")
    if not skipped_counts:
        print("    none")
        return
    for status, count in sorted(skipped_counts.items()):
        print(f"    {status}: {count}")


def print_text_summary(summary: dict[str, Any]) -> None:
    print(f"Skill: {summary['skill']}")
    print(f"Model: {summary['model']}")
    print(f"Runs manifest: {summary['runs_manifest']}")
    print()

    reconstruction = summary["reconstruction_runs"]
    print("Reconstruction runs")
    print(f"  total_runs: {reconstruction['total_runs']}")
    print(f"  skipped_without_model: {reconstruction['skipped_without_model']}")
    print_distribution("  cli_status:", reconstruction["cli_status"])
    print_distribution("  repair_loops:", reconstruction["repair_loops"], key_name="repair_loops")
    if any(item["syntax_repair_loops"] != "missing" for item in reconstruction["syntax_repair_loops"]):
        print_distribution("  syntax_repair_loops:", reconstruction["syntax_repair_loops"], key_name="syntax_repair_loops")
    if any(item["unrealizable_repair_loops"] != "missing" for item in reconstruction["unrealizable_repair_loops"]):
        print_distribution(
            "  unrealizable_repair_loops:",
            reconstruction["unrealizable_repair_loops"],
            key_name="unrealizable_repair_loops",
        )
    if any(item["test_repair_loops"] != "missing" for item in reconstruction["test_repair_loops"]):
        print_distribution("  test_repair_loops:", reconstruction["test_repair_loops"], key_name="test_repair_loops")
    print(
        "  synthesized_with_zero_repair_loops: "
        f"{reconstruction['synthesized_with_zero_repair_loops']['count']} "
        f"({reconstruction['synthesized_with_zero_repair_loops']['percent']:.2f}%)"
    )
    print(
        "  repair_attempted: "
        f"{reconstruction['repair_attempted']['count']} "
        f"({reconstruction['repair_attempted']['percent']:.2f}%)"
    )
    print(
        "  synthesized_after_repair: "
        f"{reconstruction['synthesized_after_repair']['count']} "
        f"({reconstruction['synthesized_after_repair']['percent_of_all']:.2f}% of all, "
        f"{reconstruction['synthesized_after_repair']['percent_of_repair_attempts']:.2f}% of repair attempts)"
    )
    if reconstruction["counter_strategy_used"]["count"] or reconstruction["blocked_by_nl_conflict"]["count"]:
        print(
            "  counter_strategy_used: "
            f"{reconstruction['counter_strategy_used']['count']} "
            f"({reconstruction['counter_strategy_used']['percent']:.2f}%)"
        )
        print(
            "  blocked_by_nl_conflict: "
            f"{reconstruction['blocked_by_nl_conflict']['count']} "
            f"({reconstruction['blocked_by_nl_conflict']['percent']:.2f}%)"
        )
    tests = reconstruction["controller_tests"]
    if tests["runs_reported"]:
        print(f"  controller_test_runs_reported: {tests['runs_reported']}")
        print(
            "  controller_tests: "
            f"{tests['tests_passed']}/{tests['tests_total']} passed "
            f"({tests['tests_passed_percent']:.2f}%), failed={tests['tests_failed']}"
        )
    print()

    buchi = summary["buchi_distance"]
    print("Buchi/specification distance")
    print(f"  available: {buchi['available']}")
    print(f"  output_jsonl: {buchi['output_jsonl']}")
    print(f"  matching_synthesized_runs: {buchi['matching_synthesized_runs']}")
    if buchi.get("skipped"):
        print(f"  skipped: {buchi['skip_reason']}")
        print()
    else:
        print(f"  evaluated_runs: {buchi['evaluated_runs']}")
        print_distribution("  status_counts:", buchi["status_counts"])
        print_skipped_counts(buchi["skipped_counts"])
        print_stats("  distance:", buchi["distance"])
        if "run_timeouts" in buchi:
            timeouts = buchi["run_timeouts"]
            print(f"  run_timeouts: {timeouts['count']} ({timeouts['percent']:.2f}%)")
        alphabet_mapping = buchi.get("alphabet_mapping") or {}
        if alphabet_mapping:
            mismatch = alphabet_mapping["pre_mapping_alphabet_mismatch"]
            attempted = alphabet_mapping["signature_mapping_attempted"]
            usable = alphabet_mapping["signature_mapping_usable"]
            used = alphabet_mapping["signature_mapping_used"]
            print(
                "  pre_mapping_alphabet_mismatch: "
                f"{mismatch['count']} ({mismatch['percent']:.2f}%)"
            )
            print(
                "  signature_mapping_attempted: "
                f"{attempted['count']} ({attempted['percent']:.2f}%)"
            )
            print(
                "  signature_mapping_usable: "
                f"{usable['count']} ({usable['percent']:.2f}% of evaluated, "
                f"{usable['percent_of_attempted']:.2f}% of attempted)"
            )
            print(
                "  signature_mapping_used: "
                f"{used['count']} ({used['percent']:.2f}% of evaluated, "
                f"{used['percent_of_pre_mapping_mismatches']:.2f}% of pre-mapping mismatches)"
            )
        print_stats("  bounded_mismatch_rate:", buchi["bounded_mismatch_rate"])
        print_stats("  bounded_false_negative_rate:", buchi["bounded_false_negative_rate"])
        print_stats("  bounded_false_positive_rate:", buchi["bounded_false_positive_rate"])
        print_stats("  bounded_jaccard_distance:", buchi["bounded_jaccard_distance"])
        print()

    controller = summary["controller_distance"]
    print("Controller output distance")
    print(f"  available: {controller['available']}")
    print(f"  output_jsonl: {controller['output_jsonl']}")
    print(f"  matching_synthesized_runs: {controller['matching_synthesized_runs']}")
    if controller.get("skipped"):
        print(f"  skipped: {controller['skip_reason']}")
    else:
        print(f"  evaluated_runs: {controller['evaluated_runs']}")
        print_distribution("  status_counts:", controller["status_counts"])
        print_skipped_counts(controller["skipped_counts"])
        print_stats("  trace_mismatch_rate:", controller["trace_mismatch_rate"])
        print_stats("  step_mismatch_rate:", controller["step_mismatch_rate"])
        print_stats("  output_hamming_mismatch_rate:", controller["output_hamming_mismatch_rate"])


def main() -> int:
    args = parse_args()
    runs_manifest = resolve_existing_path(args.runs_manifest)
    records = load_jsonl(runs_manifest)
    matching, skipped = select_matching_runs(records, args.skill, args.model)
    matching_synthesized_runs = len(matching)

    buchi_path = (
        resolve_repo_path(args.buchi_distance_jsonl)
        if args.buchi_distance_jsonl
        else distance_jsonl_path(args.buchi_distance_root, args.skill, args.model, "distances.jsonl")
    )
    controller_path = (
        resolve_repo_path(args.controller_distance_jsonl)
        if args.controller_distance_jsonl
        else distance_jsonl_path(args.controller_distance_root, args.skill, args.model, "controller_distances.jsonl")
    )

    summary = {
        "skill": args.skill,
        "model": args.model,
        "runs_manifest": str(runs_manifest),
        "reconstruction_runs": summarize_reconstruction_runs(records, args.skill, args.model, args.include_dry_run),
        "buchi_distance": summarize_buchi_distance(buchi_path, matching_synthesized_runs, skipped),
        "controller_distance": summarize_controller_distance(controller_path, matching_synthesized_runs, skipped),
    }

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print_text_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
