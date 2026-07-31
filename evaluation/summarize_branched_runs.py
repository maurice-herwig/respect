#!/usr/bin/env python3
"""Summarize per-run branched evaluation JSON files.

This script is intentionally small and dependency-light. It collects the
`evaluation.json` files written by `evaluate_branched_runs.py`, flattens their
artifact metrics, and writes basic aggregate tables for quick inspection.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_ROOT = "evaluation/branched_runs"
DEFAULT_OUTPUT_DIR = "evaluation/branched_summary"
LOGGER = logging.getLogger("summarize_branched_runs")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the summary script."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", default=DEFAULT_INPUT_ROOT, help="Root containing */evaluation.json files.")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Directory for summary JSON/CSV/plots.")
    parser.add_argument("--limit", type=int, default=None, help="Read at most this many evaluation files.")
    parser.add_argument("--no-plots", action="store_true", help="Skip optional matplotlib PNG output.")
    parser.add_argument("--log-level", default="INFO", choices=("DEBUG", "INFO", "WARNING", "ERROR"))
    parser.add_argument("--log-file", default=None)
    return parser.parse_args()


def configure_logging(log_level: str, log_file: str | None) -> None:
    """Configure console and optional file logging."""
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
    """Resolve repository-relative paths."""
    path = Path(path_value)
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def repo_relative(path: str | Path) -> str:
    """Return a repository-relative path if possible."""
    resolved = Path(path).resolve()
    try:
        return str(resolved.relative_to(REPO_ROOT))
    except ValueError:
        return str(resolved)


def load_json(path: Path) -> dict[str, Any]:
    """Load one UTF-8 JSON object."""
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    """Write stable, readable JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    """Write rows as CSV, creating an empty header-only table if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def find_evaluation_files(input_root: Path, limit: int | None) -> list[Path]:
    """Find per-run evaluation files in deterministic order."""
    files = sorted(input_root.glob("*/evaluation.json"))
    return files[:limit] if limit is not None else files


def bool_key(value: Any) -> str:
    """Convert tri-state booleans to stable counter keys."""
    if value is True:
        return "true"
    if value is False:
        return "false"
    return "unknown"


def number_or_none(value: Any) -> float | None:
    """Coerce numeric JSON values to float while preserving missing values."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def stats(values: list[float]) -> dict[str, float | int | None]:
    """Return basic descriptive statistics for one numeric metric."""
    if not values:
        return {"count": 0, "mean": None, "median": None, "min": None, "max": None}
    return {
        "count": len(values),
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }


def flatten_artifact(run_file: Path, payload: dict[str, Any], artifact: dict[str, Any]) -> dict[str, Any]:
    """Flatten one artifact entry into a compact row."""
    validation = artifact.get("validation") or {}
    distance = artifact.get("distance") or {}
    run = payload.get("run") or {}
    evaluation = payload.get("evaluation") or {}
    return {
        "run_id": payload.get("run_id") or run.get("run_id") or run_file.parent.name,
        "description_id": run.get("description_id"),
        "dataset_id": run.get("dataset_id"),
        "source_spectra_file": run.get("source_spectra_file"),
        "evaluation_file": repo_relative(run_file),
        "branch": artifact.get("branch"),
        "lineage": artifact.get("lineage"),
        "role": artifact.get("role"),
        "stage": artifact.get("stage"),
        "branch_status": artifact.get("branch_status"),
        "artifact_file": artifact.get("file"),
        "syntax_ok": validation.get("syntax_ok"),
        "realizable": validation.get("realizable"),
        "well_separated": validation.get("well_separated"),
        "cli_status": validation.get("cli_status"),
        "distance_status": distance.get("status"),
        "distance": distance.get("distance"),
        "bounded_semantic_distance": distance.get("bounded_semantic_distance"),
        "repair_loops": artifact.get("repair_loops"),
        "syntax_repair_loops": artifact.get("syntax_repair_loops"),
        "unrealizable_repair_loops": artifact.get("unrealizable_repair_loops"),
        "well_separation_repair_loops": artifact.get("well_separation_repair_loops"),
        "test_repair_loops": artifact.get("test_repair_loops"),
        "broker_repair_loops": artifact.get("broker_repair_loops"),
        "artifact_count_for_run": evaluation.get("artifact_count"),
    }


def collect_rows(evaluation_files: list[Path]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Collect artifact rows and branch-status rows from all evaluation files."""
    artifact_rows: list[dict[str, Any]] = []
    branch_rows: list[dict[str, Any]] = []
    for run_file in evaluation_files:
        LOGGER.info("Reading evaluation file: %s", repo_relative(run_file))
        payload = load_json(run_file)
        run_id = payload.get("run_id") or (payload.get("run") or {}).get("run_id") or run_file.parent.name
        for artifact in payload.get("artifacts") or []:
            artifact_rows.append(flatten_artifact(run_file, payload, artifact))
        branch_statuses = (payload.get("evaluation") or {}).get("branch_statuses") or {}
        for branch, status in branch_statuses.items():
            if not isinstance(status, dict):
                continue
            row = {"run_id": run_id, "branch": branch, **status}
            branch_rows.append(row)
        if not branch_statuses:
            statuses_by_branch: dict[str, set[str]] = defaultdict(set)
            for artifact in payload.get("artifacts") or []:
                branch = artifact.get("branch")
                status = artifact.get("branch_status")
                if branch and status:
                    statuses_by_branch[str(branch)].add(str(status))
            for branch, statuses in sorted(statuses_by_branch.items()):
                branch_rows.append(
                    {
                        "run_id": run_id,
                        "branch": branch,
                        "status": ",".join(sorted(statuses)),
                        "terminal_reason": None,
                        "complete_for_evaluation": all(status in {"success", "tests_passed"} for status in statuses),
                        "source": "artifact_branch_status_fallback",
                    }
                )
    return artifact_rows, branch_rows


def summarize_group(rows: list[dict[str, Any]], group_fields: tuple[str, ...]) -> list[dict[str, Any]]:
    """Aggregate artifact metrics by the requested grouping fields."""
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(row.get(field) for field in group_fields)].append(row)

    summaries: list[dict[str, Any]] = []
    for key, items in sorted(grouped.items(), key=lambda item: tuple(str(part) for part in item[0])):
        validation_counts = Counter()
        distance_status_counts = Counter()
        distances: list[float] = []
        bounded_distances: list[float] = []
        repair_values: dict[str, list[float]] = defaultdict(list)

        for item in items:
            validation_counts[f"syntax_ok_{bool_key(item.get('syntax_ok'))}"] += 1
            validation_counts[f"realizable_{bool_key(item.get('realizable'))}"] += 1
            validation_counts[f"well_separated_{bool_key(item.get('well_separated'))}"] += 1
            distance_status_counts[str(item.get("distance_status") or "missing")] += 1
            distance_value = number_or_none(item.get("distance"))
            if distance_value is not None:
                distances.append(distance_value)
            bounded_value = number_or_none(item.get("bounded_semantic_distance"))
            if bounded_value is not None:
                bounded_distances.append(bounded_value)
            for repair_key in (
                "repair_loops",
                "syntax_repair_loops",
                "unrealizable_repair_loops",
                "well_separation_repair_loops",
                "test_repair_loops",
                "broker_repair_loops",
            ):
                repair_value = number_or_none(item.get(repair_key))
                if repair_value is not None:
                    repair_values[repair_key].append(repair_value)

        summary = {field: key[index] for index, field in enumerate(group_fields)}
        summary.update(
            {
                "artifact_count": len(items),
                "run_count": len({item.get("run_id") for item in items}),
                "syntax_ok_true": validation_counts["syntax_ok_true"],
                "syntax_ok_false": validation_counts["syntax_ok_false"],
                "syntax_ok_unknown": validation_counts["syntax_ok_unknown"],
                "realizable_true": validation_counts["realizable_true"],
                "realizable_false": validation_counts["realizable_false"],
                "realizable_unknown": validation_counts["realizable_unknown"],
                "well_separated_true": validation_counts["well_separated_true"],
                "well_separated_false": validation_counts["well_separated_false"],
                "well_separated_unknown": validation_counts["well_separated_unknown"],
                "distance_status_counts": dict(distance_status_counts),
                "distance": stats(distances),
                "bounded_semantic_distance": stats(bounded_distances),
                "repair_loops": {repair_key: stats(values) for repair_key, values in sorted(repair_values.items())},
            }
        )
        summaries.append(summary)
    return summaries


def flatten_summary_for_csv(summary: dict[str, Any]) -> dict[str, Any]:
    """Flatten nested metric summaries into a CSV-friendly row."""
    row = dict(summary)
    distance = row.pop("distance", {}) or {}
    bounded = row.pop("bounded_semantic_distance", {}) or {}
    row.pop("distance_status_counts", None)
    row.pop("repair_loops", None)
    for prefix, metric in (("distance", distance), ("bounded_semantic_distance", bounded)):
        for key in ("count", "mean", "median", "min", "max"):
            row[f"{prefix}_{key}"] = metric.get(key)
    return row


def write_summary_tables(output_dir: Path, rows: list[dict[str, Any]], branch_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Write JSON and CSV summary tables and return the complete summary object."""
    by_branch = summarize_group(rows, ("branch",))
    by_lineage = summarize_group(rows, ("branch", "lineage"))
    by_stage = summarize_group(rows, ("branch", "lineage", "stage"))
    final_only = [row for row in rows if row.get("stage") == "final"]
    final_by_branch = summarize_group(final_only, ("branch",))

    summary = {
        "schema_version": "branched_evaluation_summary_v1",
        "run_count": len({row.get("run_id") for row in rows}),
        "artifact_count": len(rows),
        "branch_status_count": len(branch_rows),
        "by_branch": by_branch,
        "by_lineage": by_lineage,
        "by_stage": by_stage,
        "final_by_branch": final_by_branch,
        "branch_statuses": branch_rows,
    }
    write_json(output_dir / "summary.json", summary)

    artifact_fields = [
        "run_id",
        "description_id",
        "dataset_id",
        "branch",
        "lineage",
        "role",
        "stage",
        "branch_status",
        "syntax_ok",
        "realizable",
        "well_separated",
        "cli_status",
        "distance_status",
        "distance",
        "bounded_semantic_distance",
        "repair_loops",
        "syntax_repair_loops",
        "unrealizable_repair_loops",
        "well_separation_repair_loops",
        "test_repair_loops",
        "broker_repair_loops",
        "artifact_file",
        "evaluation_file",
    ]
    write_csv(output_dir / "artifacts.csv", rows, artifact_fields)
    write_csv(output_dir / "branch_statuses.csv", branch_rows, sorted({key for row in branch_rows for key in row.keys()}))
    write_csv(output_dir / "by_branch.csv", [flatten_summary_for_csv(row) for row in by_branch], list(flatten_summary_for_csv(by_branch[0]).keys()) if by_branch else [])
    write_csv(output_dir / "by_lineage.csv", [flatten_summary_for_csv(row) for row in by_lineage], list(flatten_summary_for_csv(by_lineage[0]).keys()) if by_lineage else [])
    write_csv(output_dir / "by_stage.csv", [flatten_summary_for_csv(row) for row in by_stage], list(flatten_summary_for_csv(by_stage[0]).keys()) if by_stage else [])
    write_csv(output_dir / "final_by_branch.csv", [flatten_summary_for_csv(row) for row in final_by_branch], list(flatten_summary_for_csv(final_by_branch[0]).keys()) if final_by_branch else [])
    return summary


def maybe_write_plots(output_dir: Path, summary: dict[str, Any], *, no_plots: bool) -> list[str]:
    """Write simple plots when matplotlib is available."""
    if no_plots:
        return []
    try:
        import matplotlib.pyplot as plt  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on optional package
        LOGGER.warning("Skipping plots because matplotlib is unavailable: %s", exc)
        return []

    plot_dir = output_dir / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []

    final_rows = summary.get("final_by_branch") or []
    if final_rows:
        labels = [str(row.get("branch")) for row in final_rows]
        values = [(row.get("distance") or {}).get("mean") or 0 for row in final_rows]
        plt.figure(figsize=(max(6, len(labels) * 1.2), 4))
        plt.bar(labels, values)
        plt.ylabel("Mean distance")
        plt.xlabel("Branch")
        plt.title("Final artifacts: mean distance by branch")
        plt.xticks(rotation=30, ha="right")
        plt.tight_layout()
        path = plot_dir / "final_distance_mean_by_branch.png"
        plt.savefig(path)
        plt.close()
        written.append(repo_relative(path))

    branch_rows = summary.get("by_branch") or []
    if branch_rows:
        labels = [str(row.get("branch")) for row in branch_rows]
        syntax_ok = [row.get("syntax_ok_true") or 0 for row in branch_rows]
        syntax_bad = [row.get("syntax_ok_false") or 0 for row in branch_rows]
        plt.figure(figsize=(max(6, len(labels) * 1.2), 4))
        plt.bar(labels, syntax_ok, label="syntax ok")
        plt.bar(labels, syntax_bad, bottom=syntax_ok, label="syntax not ok")
        plt.ylabel("Artifacts")
        plt.xlabel("Branch")
        plt.title("Syntax validation by branch")
        plt.xticks(rotation=30, ha="right")
        plt.legend()
        plt.tight_layout()
        path = plot_dir / "syntax_by_branch.png"
        plt.savefig(path)
        plt.close()
        written.append(repo_relative(path))

    return written


def main() -> int:
    """Run the summary aggregation."""
    args = parse_args()
    configure_logging(args.log_level, args.log_file)
    input_root = resolve_repo_path(args.input_root)
    output_dir = resolve_repo_path(args.output_dir)
    evaluation_files = find_evaluation_files(input_root, args.limit)
    LOGGER.info("Starting summary: input=%s files=%s output=%s", repo_relative(input_root), len(evaluation_files), repo_relative(output_dir))
    if not evaluation_files:
        LOGGER.error("No evaluation.json files found below %s", input_root)
        return 2

    artifact_rows, branch_rows = collect_rows(evaluation_files)
    summary = write_summary_tables(output_dir, artifact_rows, branch_rows)
    plots = maybe_write_plots(output_dir, summary, no_plots=args.no_plots)
    summary["plots"] = plots
    write_json(output_dir / "summary.json", summary)

    result = {
        "input_root": str(input_root),
        "output_dir": str(output_dir),
        "evaluation_files": len(evaluation_files),
        "run_count": summary["run_count"],
        "artifact_count": summary["artifact_count"],
        "plots": plots,
        "summary_file": str(output_dir / "summary.json"),
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    LOGGER.info("Finished summary: runs=%s artifacts=%s", summary["run_count"], summary["artifact_count"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
