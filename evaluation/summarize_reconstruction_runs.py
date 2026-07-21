#!/usr/bin/env python3
"""Summarize reconstruction experiment results by model and skill."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_RUNS_MANIFEST = "experiments/runs/runs.jsonl"
REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize reconstruct_with_skill experiment runs.")
    parser.add_argument("--runs-manifest", default=DEFAULT_RUNS_MANIFEST, help="Path to experiments/runs/runs.jsonl.")
    parser.add_argument("--skill", required=True, help="Skill/method to summarize, e.g. respect.")
    parser.add_argument(
        "--model",
        required=True,
        help=(
            "Model label to summarize. This is matched against agent_model when present, "
            "otherwise against model=<label> path segments in run metadata."
        ),
    )
    parser.add_argument(
        "--include-dry-run",
        action="store_true",
        help="Include dry-run records. By default they are ignored.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON instead of a text summary.",
    )
    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not path.is_file():
        raise FileNotFoundError(f"Runs manifest not found: {path}")

    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in {path} at line {line_number}: {exc}") from exc
    return records


def resolve_repo_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    if path.is_absolute() or path.exists():
        return path
    return REPO_ROOT / path


def extract_model_label(record: dict[str, Any]) -> str | None:
    """Return the agent/model label stored for a run.

    Older manifests often have `agent_model = null`, while the NL generation
    model is encoded in paths such as `.../model=llama-3/...`. This function
    supports both representations.
    """
    agent_model = record.get("agent_model")
    if isinstance(agent_model, str) and agent_model:
        return agent_model

    candidates = [
        record.get("description_relative_stem"),
        record.get("run_dir"),
        record.get("description_file"),
        record.get("agent_prompt_file"),
    ]
    for candidate in candidates:
        if not isinstance(candidate, str):
            continue
        match = re.search(r"(?:^|[\\/])model=([^\\/]+)", candidate)
        if match:
            return match.group(1)
    return None


def percent(count: int, total: int) -> float:
    if total == 0:
        return 0.0
    return 100.0 * count / total


def summarize(records: list[dict[str, Any]], skill: str, model: str, include_dry_run: bool) -> dict[str, Any]:
    filtered: list[dict[str, Any]] = []
    skipped_without_model = 0

    for record in records:
        if record.get("skill") != skill:
            continue
        if not include_dry_run and record.get("dry_run"):
            continue

        model_label = extract_model_label(record)
        if model_label is None:
            skipped_without_model += 1
            continue
        if model_label != model:
            continue

        filtered.append(record)

    total = len(filtered)
    cli_status_counts: Counter[str] = Counter(str(record.get("reported_cli_status") or "missing") for record in filtered)
    repair_loop_counts: Counter[str] = Counter(
        str(record.get("reported_repair_loops") if record.get("reported_repair_loops") is not None else "missing")
        for record in filtered
    )
    syntax_repair_loop_counts: Counter[str] = Counter(
        str(record.get("reported_syntax_repair_loops") if record.get("reported_syntax_repair_loops") is not None else "missing")
        for record in filtered
    )
    unrealizable_repair_loop_counts: Counter[str] = Counter(
        str(
            record.get("reported_unrealizable_repair_loops")
            if record.get("reported_unrealizable_repair_loops") is not None
            else "missing"
        )
        for record in filtered
    )
    test_repair_loop_counts: Counter[str] = Counter(
        str(record.get("reported_test_repair_loops") if record.get("reported_test_repair_loops") is not None else "missing")
        for record in filtered
    )

    synthesized_without_repair = sum(
        1
        for record in filtered
        if record.get("reported_cli_status") == "synthesized" and record.get("reported_repair_loops") == 0
    )
    repair_attempted = sum(
        1
        for record in filtered
        if isinstance(record.get("reported_repair_loops"), int) and record["reported_repair_loops"] > 0
    )
    synthesized_after_repair = sum(
        1
        for record in filtered
        if record.get("reported_cli_status") == "synthesized"
        and isinstance(record.get("reported_repair_loops"), int)
        and record["reported_repair_loops"] > 0
    )
    counter_strategy_used = sum(1 for record in filtered if record.get("reported_used_counter_strategy") is True)
    blocked_by_nl_conflict = sum(1 for record in filtered if record.get("reported_blocked_by_nl_conflict") is True)
    test_runs_reported = sum(1 for record in filtered if isinstance(record.get("reported_tests_total"), int))
    tests_total = sum(record.get("reported_tests_total") for record in filtered if isinstance(record.get("reported_tests_total"), int))
    tests_passed = sum(record.get("reported_tests_passed") for record in filtered if isinstance(record.get("reported_tests_passed"), int))
    tests_failed = sum(record.get("reported_tests_failed") for record in filtered if isinstance(record.get("reported_tests_failed"), int))

    return {
        "skill": skill,
        "model": model,
        "total_runs": total,
        "skipped_without_model": skipped_without_model,
        "cli_status": [
            {
                "status": status,
                "count": count,
                "percent": percent(count, total),
            }
            for status, count in sorted(cli_status_counts.items())
        ],
        "repair_loops": [
            {
                "repair_loops": repair_loops,
                "count": count,
                "percent": percent(count, total),
            }
            for repair_loops, count in sorted(repair_loop_counts.items(), key=lambda item: (not item[0].isdigit(), item[0]))
        ],
        "syntax_repair_loops": [
            {
                "syntax_repair_loops": repair_loops,
                "count": count,
                "percent": percent(count, total),
            }
            for repair_loops, count in sorted(syntax_repair_loop_counts.items(), key=lambda item: (not item[0].isdigit(), item[0]))
        ],
        "unrealizable_repair_loops": [
            {
                "unrealizable_repair_loops": repair_loops,
                "count": count,
                "percent": percent(count, total),
            }
            for repair_loops, count in sorted(
                unrealizable_repair_loop_counts.items(), key=lambda item: (not item[0].isdigit(), item[0])
            )
        ],
        "test_repair_loops": [
            {
                "test_repair_loops": repair_loops,
                "count": count,
                "percent": percent(count, total),
            }
            for repair_loops, count in sorted(test_repair_loop_counts.items(), key=lambda item: (not item[0].isdigit(), item[0]))
        ],
        "synthesized_with_zero_repair_loops": {
            "count": synthesized_without_repair,
            "percent": percent(synthesized_without_repair, total),
        },
        "repair_attempted": {
            "count": repair_attempted,
            "percent": percent(repair_attempted, total),
        },
        "synthesized_after_repair": {
            "count": synthesized_after_repair,
            "percent_of_all": percent(synthesized_after_repair, total),
            "percent_of_repair_attempts": percent(synthesized_after_repair, repair_attempted),
        },
        "counter_strategy_used": {
            "count": counter_strategy_used,
            "percent": percent(counter_strategy_used, total),
        },
        "blocked_by_nl_conflict": {
            "count": blocked_by_nl_conflict,
            "percent": percent(blocked_by_nl_conflict, total),
        },
        "controller_tests": {
            "runs_reported": test_runs_reported,
            "tests_total": tests_total,
            "tests_passed": tests_passed,
            "tests_failed": tests_failed,
            "tests_passed_percent": percent(tests_passed, tests_total),
        },
    }


def print_text_summary(summary: dict[str, Any]) -> None:
    print(f"Skill: {summary['skill']}")
    print(f"Model: {summary['model']}")
    print(f"Total runs: {summary['total_runs']}")
    if summary["skipped_without_model"]:
        print(f"Skipped without model label: {summary['skipped_without_model']}")

    print()
    print("CLI status:")
    for item in summary["cli_status"]:
        print(f"  {item['status']}: {item['count']} ({item['percent']:.2f}%)")

    print()
    print("Repair loops:")
    for item in summary["repair_loops"]:
        print(f"  {item['repair_loops']}: {item['count']} ({item['percent']:.2f}%)")

    if any(item["syntax_repair_loops"] != "missing" for item in summary["syntax_repair_loops"]):
        print()
        print("Syntax repair loops:")
        for item in summary["syntax_repair_loops"]:
            print(f"  {item['syntax_repair_loops']}: {item['count']} ({item['percent']:.2f}%)")

    if any(item["unrealizable_repair_loops"] != "missing" for item in summary["unrealizable_repair_loops"]):
        print()
        print("Unrealizable repair loops:")
        for item in summary["unrealizable_repair_loops"]:
            print(f"  {item['unrealizable_repair_loops']}: {item['count']} ({item['percent']:.2f}%)")

    if any(item["test_repair_loops"] != "missing" for item in summary["test_repair_loops"]):
        print()
        print("Test repair loops:")
        for item in summary["test_repair_loops"]:
            print(f"  {item['test_repair_loops']}: {item['count']} ({item['percent']:.2f}%)")

    zero_repair = summary["synthesized_with_zero_repair_loops"]
    print()
    print(
        "Synthesized with repair_loops=0: "
        f"{zero_repair['count']} ({zero_repair['percent']:.2f}%)"
    )

    repair_attempted = summary["repair_attempted"]
    synthesized_after_repair = summary["synthesized_after_repair"]
    print(
        "Repair attempted: "
        f"{repair_attempted['count']} ({repair_attempted['percent']:.2f}%)"
    )
    print(
        "Synthesized after repair: "
        f"{synthesized_after_repair['count']} "
        f"({synthesized_after_repair['percent_of_all']:.2f}% of all, "
        f"{synthesized_after_repair['percent_of_repair_attempts']:.2f}% of repair attempts)"
    )

    if summary["counter_strategy_used"]["count"] or summary["blocked_by_nl_conflict"]["count"]:
        print()
        print(
            "Counter-strategy used: "
            f"{summary['counter_strategy_used']['count']} ({summary['counter_strategy_used']['percent']:.2f}%)"
        )
        print(
            "Blocked by NL conflict: "
            f"{summary['blocked_by_nl_conflict']['count']} ({summary['blocked_by_nl_conflict']['percent']:.2f}%)"
        )

    tests = summary["controller_tests"]
    if tests["runs_reported"]:
        print()
        print(f"Controller-test runs reported: {tests['runs_reported']}")
        print(
            "Controller tests: "
            f"{tests['tests_passed']}/{tests['tests_total']} passed "
            f"({tests['tests_passed_percent']:.2f}%), failed={tests['tests_failed']}"
        )


def main() -> int:
    args = parse_args()
    records = load_jsonl(resolve_repo_path(args.runs_manifest))
    summary = summarize(records, args.skill, args.model, args.include_dry_run)

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print_text_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
