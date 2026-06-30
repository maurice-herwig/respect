#!/usr/bin/env python3
"""Run cross-broker reconstruction experiments for a descriptions manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DESCRIPTIONS_MANIFEST = "dataset/nl_descriptions/descriptions.jsonl"
DEFAULT_OUTPUT_DIR = "experiments/cross_runs"
DEFAULT_CROSS_RUNNER = "experiments/cross_repair_with_broker.py"
DEFAULT_AGENT_COMMAND = "codex --ask-for-approval never exec --ephemeral --sandbox danger-full-access -"
DEFAULT_SKILL = "respect-method-cross-broker"
DEFAULT_AGENT_IDS = ("agent_a", "agent_b")
DEFAULT_MAX_BROKER_REPAIR_LOOPS = 3
PROMPT_VERSION = "cross_broker_prompt_v1"


def parse_args() -> argparse.Namespace:
    """Parse CLI options for the dataset-level cross-repair runner."""
    parser = argparse.ArgumentParser(description="Run cross-broker reconstruction for NL descriptions.")
    parser.add_argument("--skill", default=DEFAULT_SKILL)
    parser.add_argument("--descriptions-manifest", default=DEFAULT_DESCRIPTIONS_MANIFEST)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--cross-runner", default=DEFAULT_CROSS_RUNNER)
    parser.add_argument("--agent-command", default=DEFAULT_AGENT_COMMAND)
    parser.add_argument("--agent-model", default=None)
    parser.add_argument("--agent-ids", nargs=2, default=list(DEFAULT_AGENT_IDS))
    parser.add_argument("--timeout", type=float, default=1800.0)
    parser.add_argument("--broker-timeout", type=float, default=600.0)
    parser.add_argument("--max-broker-repair-loops", type=int, default=DEFAULT_MAX_BROKER_REPAIR_LOOPS)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--refresh-before", default=None)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def utc_now() -> str:
    """Return an ISO-8601 UTC timestamp for manifest records."""
    return datetime.now(timezone.utc).isoformat()


def parse_iso_datetime(value: str | None) -> datetime | None:
    """Parse an optional ISO timestamp as UTC."""
    if not value:
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def resolve_repo_path(path_value: str | Path) -> Path:
    """Resolve relative paths against the repository root."""
    path = Path(path_value)
    if path.is_absolute():
        return path
    return (REPO_ROOT / path).resolve()


def sha256_text(text: str) -> str:
    """Return the SHA-256 hex digest for text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def safe_path_part(value: str, max_length: int = 120) -> str:
    """Sanitize a string for use as one path segment."""
    safe = re.sub(r"[^A-Za-z0-9._=-]+", "_", value).strip("_")
    return (safe or "value")[:max_length]


def description_relative_stem(response_file: Path) -> Path:
    """Mirror reconstruct_with_skill.py's description-based run path logic."""
    parts = response_file.parts
    try:
        responses_index = parts.index("responses")
        relative_parts = parts[responses_index + 1 :]
    except ValueError:
        relative_parts = (response_file.name,)

    if not relative_parts:
        return Path(safe_path_part(response_file.stem))

    sanitized_parts = [safe_path_part(part) for part in relative_parts]
    return Path(*sanitized_parts).with_suffix("")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load JSONL records, ignoring blank lines."""
    records: list[dict[str, Any]] = []
    if not path.is_file():
        return records
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return records


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    """Append one JSON object as a JSONL row."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def write_text(path: Path, content: str | None) -> None:
    """Write a UTF-8 text artifact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content or "", encoding="utf-8")


def record_is_fresh(record: dict[str, Any], refresh_before: datetime | None) -> bool:
    """Return whether an existing manifest record is fresh enough to skip."""
    if refresh_before is None:
        return True
    timestamp = record.get("run_finished_at") or record.get("run_started_at")
    if not timestamp:
        return False
    try:
        parsed = parse_iso_datetime(timestamp)
    except ValueError:
        return False
    return parsed is not None and parsed >= refresh_before


def completed_run_keys(runs_manifest: Path, refresh_before: datetime | None) -> set[str]:
    """Collect fresh successful run keys from an existing manifest."""
    keys: set[str] = set()
    for record in load_jsonl(runs_manifest):
        if record.get("status") == "success" and record.get("run_key") and record_is_fresh(record, refresh_before):
            keys.add(record["run_key"])
    return keys


def make_run_key(
    *,
    description_record: dict[str, Any],
    skill: str,
    agent_command: str,
    agent_model: str | None,
    agent_ids: list[str],
    timeout: float,
    broker_timeout: float,
    max_broker_repair_loops: int,
    cross_runner: str,
) -> str:
    """Create a deterministic key for skip/resume behavior."""
    return sha256_text(
        json.dumps(
            {
                "agent_command": agent_command,
                "agent_ids": agent_ids,
                "agent_model": agent_model,
                "broker_timeout": broker_timeout,
                "cross_runner": cross_runner,
                "description_id": description_record.get("description_id"),
                "description_response_sha256": description_record.get("response_sha256"),
                "max_broker_repair_loops": max_broker_repair_loops,
                "prompt_version": PROMPT_VERSION,
                "skill": skill,
                "timeout": timeout,
            },
            sort_keys=True,
        )
    )


def build_cross_runner_command(
    *,
    cross_runner: Path,
    description_file: Path,
    skill: str,
    agent_command: str,
    output_dir: Path,
    run_id: str,
    agent_ids: list[str],
    timeout: float,
    broker_timeout: float,
    max_broker_repair_loops: int,
    dry_run: bool,
) -> list[str]:
    """Build the single-description cross-runner command."""
    command = [
        sys.executable,
        str(cross_runner),
        "--description-file",
        str(description_file),
        "--skill",
        skill,
        "--agent-command",
        agent_command,
        "--output-dir",
        str(output_dir),
        "--run-id",
        run_id,
        "--agent-ids",
        agent_ids[0],
        agent_ids[1],
        "--timeout",
        str(timeout),
        "--broker-timeout",
        str(broker_timeout),
        "--max-broker-repair-loops",
        str(max_broker_repair_loops),
    ]
    if dry_run:
        command.append("--dry-run")
    return command


def load_summary(summary_file: Path) -> dict[str, Any] | None:
    """Load the cross-runner summary if it exists."""
    if not summary_file.is_file():
        return None
    return json.loads(summary_file.read_text(encoding="utf-8"))


def process_description(
    *,
    record: dict[str, Any],
    args: argparse.Namespace,
    output_dir: Path,
    cross_runner: Path,
    runs_manifest: Path,
    known_completed: set[str],
    refresh_before: datetime | None,
) -> str:
    """Run cross repair for one description record and append a manifest row."""
    response_file = resolve_repo_path(record["response_file"])
    current_run_key = make_run_key(
        description_record=record,
        skill=args.skill,
        agent_command=args.agent_command,
        agent_model=args.agent_model,
        agent_ids=args.agent_ids,
        timeout=args.timeout,
        broker_timeout=args.broker_timeout,
        max_broker_repair_loops=args.max_broker_repair_loops,
        cross_runner=str(cross_runner),
    )
    if not args.force and current_run_key in known_completed:
        return "skipped"

    run_id = current_run_key[:24]
    description_stem = description_relative_stem(response_file)
    run_dir = output_dir / description_stem / safe_path_part(args.skill) / run_id
    summary_file = run_dir / "summary.json"
    cross_stdout_file = run_dir / "cross_runner_stdout.txt"
    cross_stderr_file = run_dir / "cross_runner_stderr.txt"

    started_at = utc_now()
    started = time.perf_counter()
    status = "missing_description_file"
    exit_code: int | None = None
    error: str | None = None
    summary: dict[str, Any] | None = None

    if not response_file.is_file():
        error = f"Description response file not found: {response_file}"
        write_text(cross_stdout_file, "")
        write_text(cross_stderr_file, error)
    else:
        command = build_cross_runner_command(
            cross_runner=cross_runner,
            description_file=response_file,
            skill=args.skill,
            agent_command=args.agent_command,
            output_dir=run_dir.parent,
            run_id=run_id,
            agent_ids=args.agent_ids,
            timeout=args.timeout,
            broker_timeout=args.broker_timeout,
            max_broker_repair_loops=args.max_broker_repair_loops,
            dry_run=args.dry_run,
        )
        try:
            completed = subprocess.run(
                command,
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=args.timeout + args.broker_timeout + 60,
            )
            exit_code = completed.returncode
            write_text(cross_stdout_file, completed.stdout)
            write_text(cross_stderr_file, completed.stderr)
            summary = load_summary(summary_file)
            if args.dry_run:
                status = "dry_run"
            elif completed.returncode == 0 and summary and summary.get("status") == "success":
                status = "success"
            else:
                status = "agent_error"
        except subprocess.TimeoutExpired as exc:
            status = "timeout"
            error = f"Cross runner timed out after {args.timeout + args.broker_timeout + 60} seconds."
            write_text(cross_stdout_file, exc.stdout or "")
            write_text(cross_stderr_file, exc.stderr or "")

    finished_at = utc_now()
    duration_ms = int((time.perf_counter() - started) * 1000)
    results = summary.get("results", {}) if summary else {}
    manifest_record = {
        "run_id": run_id,
        "run_key": current_run_key,
        "status": status,
        "skill": args.skill,
        "description_id": record.get("description_id"),
        "dataset_id": record.get("dataset_id"),
        "description_file": str(response_file),
        "source_spectra_file": record.get("source_spectra_file"),
        "source_repository_full_name": record.get("source_repository_full_name"),
        "source_path": record.get("source_path"),
        "description_relative_stem": str(description_stem),
        "cross_runner": str(cross_runner),
        "agent_command": args.agent_command,
        "agent_model": args.agent_model,
        "agent_ids": args.agent_ids,
        "run_dir": str(run_dir),
        "summary_file": str(summary_file) if summary_file.is_file() else None,
        "cross_runner_stdout_file": str(cross_stdout_file),
        "cross_runner_stderr_file": str(cross_stderr_file),
        "agent_a_exit_code": results.get(args.agent_ids[0], {}).get("exit_code"),
        "agent_b_exit_code": results.get(args.agent_ids[1], {}).get("exit_code"),
        "agent_a_stdout_file": results.get(args.agent_ids[0], {}).get("stdout_file"),
        "agent_b_stdout_file": results.get(args.agent_ids[1], {}).get("stdout_file"),
        "agent_a_stderr_file": results.get(args.agent_ids[0], {}).get("stderr_file"),
        "agent_b_stderr_file": results.get(args.agent_ids[1], {}).get("stderr_file"),
        "cross_runner_exit_code": exit_code,
        "timeout_seconds": args.timeout,
        "broker_timeout_seconds": args.broker_timeout,
        "max_broker_repair_loops": args.max_broker_repair_loops,
        "run_started_at": started_at,
        "run_finished_at": finished_at,
        "duration_ms": duration_ms,
        "error": error,
        "dry_run": args.dry_run,
        "refresh_before": refresh_before.isoformat() if refresh_before else None,
    }
    append_jsonl(runs_manifest, manifest_record)
    if status == "success":
        known_completed.add(current_run_key)
    return status


def main() -> int:
    """Run the batch wrapper and print aggregate stats."""
    args = parse_args()
    descriptions_manifest = resolve_repo_path(args.descriptions_manifest)
    descriptions = load_jsonl(descriptions_manifest)
    if not descriptions:
        print(f"No descriptions found in {descriptions_manifest}", file=sys.stderr)
        return 2

    output_dir = resolve_repo_path(args.output_dir)
    cross_runner = resolve_repo_path(args.cross_runner)
    runs_manifest = output_dir / "runs.jsonl"
    refresh_before = parse_iso_datetime(args.refresh_before)
    known_completed = set() if args.force else completed_run_keys(runs_manifest, refresh_before)

    stats = {"processed": 0, "success": 0, "skipped": 0, "agent_error": 0, "timeout": 0, "dry_run": 0}
    for record in descriptions:
        if args.limit is not None and stats["processed"] >= args.limit:
            break
        result = process_description(
            record=record,
            args=args,
            output_dir=output_dir,
            cross_runner=cross_runner,
            runs_manifest=runs_manifest,
            known_completed=known_completed,
            refresh_before=refresh_before,
        )
        stats["processed"] += 1
        stats[result] = stats.get(result, 0) + 1

    summary = {
        "descriptions_manifest": str(descriptions_manifest),
        "output_dir": str(output_dir),
        "runs_manifest": str(runs_manifest),
        "skill": args.skill,
        "agent_command": args.agent_command,
        "agent_model": args.agent_model,
        "agent_ids": args.agent_ids,
        "cross_runner": str(cross_runner),
        "max_broker_repair_loops": args.max_broker_repair_loops,
        "force": args.force,
        "dry_run": args.dry_run,
        "refresh_before": refresh_before.isoformat() if refresh_before else None,
        "stats": stats,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if stats.get("agent_error", 0) == 0 and stats.get("timeout", 0) == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        raise SystemExit(130)
