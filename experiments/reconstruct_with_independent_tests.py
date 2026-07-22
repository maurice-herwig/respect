#!/usr/bin/env python3
"""Batch wrapper for independent-test ReSpect runs."""

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
DEFAULT_OUTPUT_DIR = "experiments/independent_test_runs"
DEFAULT_RUNNER = "experiments/independent_test_repair.py"
DEFAULT_AGENT_COMMAND = "codex --ask-for-approval never exec --ephemeral --sandbox danger-full-access -"
DEFAULT_SPEC_SKILL = "respect-spec-tester"
DEFAULT_TEST_SKILL = "respect-test-writer"
PROMPT_VERSION = "independent_tests_v1"


def parse_args() -> argparse.Namespace:
    """Parse command-line options for the dataset-level batch runner."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--descriptions-manifest", default=DEFAULT_DESCRIPTIONS_MANIFEST)
    parser.add_argument("--signature-root", required=True, help="Directory containing <description_id>.json signature files.")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--runner", default=DEFAULT_RUNNER)
    parser.add_argument("--spec-skill", default=DEFAULT_SPEC_SKILL)
    parser.add_argument("--test-skill", default=DEFAULT_TEST_SKILL)
    parser.add_argument("--agent-command", default=DEFAULT_AGENT_COMMAND)
    parser.add_argument("--agent-model", default=None)
    parser.add_argument("--timeout", type=float, default=1800.0)
    parser.add_argument("--max-feedback-rounds", type=int, default=3)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def utc_now() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def resolve_repo_path(path_value: str | Path) -> Path:
    """Resolve a path against the repository root unless it is already absolute."""
    path = Path(path_value)
    if path.is_absolute():
        return path
    return (REPO_ROOT / path).resolve()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load JSONL records from a file, ignoring blank lines."""
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
    """Write UTF-8 text to a file, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content or "", encoding="utf-8")


def load_json(path: Path) -> Any:
    """Load one JSON document from disk."""
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_text(text: str) -> str:
    """Return the SHA-256 hex digest for a text value."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def safe_path_part(value: str, max_length: int = 120) -> str:
    """Sanitize a value so it can be used as a single filesystem path segment."""
    safe = re.sub(r"[^A-Za-z0-9._=-]+", "_", value).strip("_")
    return (safe or "value")[:max_length]


def description_relative_stem(response_file: Path) -> Path:
    """Mirror dataset response paths into stable experiment output paths."""
    parts = response_file.parts
    try:
        responses_index = parts.index("responses")
        relative_parts = parts[responses_index + 1 :]
    except ValueError:
        relative_parts = (response_file.name,)
    return Path(*[safe_path_part(part) for part in relative_parts]).with_suffix("")


def completed_statuses() -> set[str]:
    """Return statuses that represent completed experiment runs."""
    return {"tests_passed", "invalid_tests_rejected", "max_rounds_with_failures"}


def completed_run_keys(runs_manifest: Path) -> set[str]:
    """Return completed run keys to support resume behavior."""
    return {record["run_key"] for record in load_jsonl(runs_manifest) if record.get("status") in completed_statuses() and record.get("run_key")}


def make_run_key(record: dict[str, Any], args: argparse.Namespace, signature_file: Path) -> str:
    """Build a deterministic run key from inputs that affect experiment output."""
    return sha256_text(
        json.dumps(
            {
                "agent_command": args.agent_command,
                "agent_model": args.agent_model,
                "description_id": record.get("description_id"),
                "description_response_sha256": record.get("response_sha256"),
                "max_feedback_rounds": args.max_feedback_rounds,
                "prompt_version": PROMPT_VERSION,
                "signature_file": str(signature_file),
                "signature_sha256": sha256_text(signature_file.read_text(encoding="utf-8")) if signature_file.is_file() else None,
                "spec_skill": args.spec_skill,
                "test_skill": args.test_skill,
                "timeout": args.timeout,
            },
            sort_keys=True,
        )
    )


def signature_file_for(record: dict[str, Any], signature_root: Path) -> Path:
    """Find the signature file for a description, preferring description id."""
    description_id = record.get("description_id")
    dataset_id = record.get("dataset_id")
    candidates = []
    if description_id:
        candidates.append(signature_root / f"{safe_path_part(str(description_id))}.json")
    if dataset_id:
        candidates.append(signature_root / f"{safe_path_part(str(dataset_id))}.json")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0] if candidates else signature_root / "missing.json"


def process_record(record: dict[str, Any], args: argparse.Namespace, output_dir: Path, runner: Path, runs_manifest: Path, completed: set[str]) -> str:
    """Run or skip one independent-test experiment and append a manifest row."""
    response_file = resolve_repo_path(record["response_file"])
    signature_file = signature_file_for(record, resolve_repo_path(args.signature_root))
    run_key = make_run_key(record, args, signature_file)
    if not args.force and run_key in completed:
        return "skipped"

    run_id = run_key[:24]
    run_dir = output_dir / description_relative_stem(response_file) / safe_path_part(args.spec_skill) / run_id
    stdout_file = run_dir / "independent_runner_stdout.txt"
    stderr_file = run_dir / "independent_runner_stderr.txt"
    summary_file = run_dir / "summary.json"
    started_at = utc_now()
    started = time.perf_counter()
    error = None
    status = "missing_input"
    exit_code = None

    if not response_file.is_file():
        error = f"Description file not found: {response_file}"
    elif not signature_file.is_file():
        error = f"Signature file not found: {signature_file}"
    else:
        command = [
            sys.executable,
            str(runner),
            "--description-file",
            str(response_file),
            "--signature-file",
            str(signature_file),
            "--output-dir",
            str(run_dir.parent),
            "--run-id",
            run_id,
            "--spec-skill",
            args.spec_skill,
            "--test-skill",
            args.test_skill,
            "--agent-command",
            args.agent_command,
            "--timeout",
            str(args.timeout),
            "--max-feedback-rounds",
            str(args.max_feedback_rounds),
        ]
        if args.dry_run:
            command.append("--dry-run")
        try:
            completed_process = subprocess.run(
                command,
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=(args.timeout * (args.max_feedback_rounds + 1) * 2) + 300,
            )
            exit_code = completed_process.returncode
            write_text(stdout_file, completed_process.stdout)
            write_text(stderr_file, completed_process.stderr)
            summary_status = load_json(summary_file).get("status") if summary_file.is_file() else None
            status = str(summary_status) if summary_status else ("agent_error" if exit_code != 0 else "tests_passed")
            if args.dry_run:
                status = "dry_run"
        except subprocess.TimeoutExpired as exc:
            status = "timeout"
            error = "Independent-test runner timed out."
            write_text(stdout_file, exc.stdout or "")
            write_text(stderr_file, exc.stderr or "")

    manifest_record = {
        "run_id": run_id,
        "run_key": run_key,
        "status": status,
        "spec_skill": args.spec_skill,
        "test_skill": args.test_skill,
        "description_id": record.get("description_id"),
        "dataset_id": record.get("dataset_id"),
        "description_file": str(response_file),
        "signature_file": str(signature_file),
        "source_spectra_file": record.get("source_spectra_file"),
        "source_repository_full_name": record.get("source_repository_full_name"),
        "source_path": record.get("source_path"),
        "agent_command": args.agent_command,
        "agent_model": args.agent_model,
        "run_dir": str(run_dir),
        "summary_file": str(summary_file) if summary_file.is_file() else None,
        "runner_stdout_file": str(stdout_file),
        "runner_stderr_file": str(stderr_file),
        "runner_exit_code": exit_code,
        "timeout_seconds": args.timeout,
        "max_feedback_rounds": args.max_feedback_rounds,
        "run_started_at": started_at,
        "run_finished_at": utc_now(),
        "duration_ms": int((time.perf_counter() - started) * 1000),
        "error": error,
        "dry_run": args.dry_run,
    }
    append_jsonl(runs_manifest, manifest_record)
    if status in completed_statuses():
        completed.add(run_key)
    return status


def main() -> int:
    """Run independent-test experiments for records in the descriptions manifest."""
    args = parse_args()
    descriptions = load_jsonl(resolve_repo_path(args.descriptions_manifest))
    output_dir = resolve_repo_path(args.output_dir)
    runner = resolve_repo_path(args.runner)
    runs_manifest = output_dir / "runs.jsonl"
    completed = set() if args.force else completed_run_keys(runs_manifest)
    stats = {
        "processed": 0,
        "tests_passed": 0,
        "invalid_tests_rejected": 0,
        "max_rounds_with_failures": 0,
        "spec_not_synthesized": 0,
        "test_generation_failed": 0,
        "completed_without_test_success": 0,
        "skipped": 0,
        "agent_error": 0,
        "timeout": 0,
        "dry_run": 0,
        "missing_input": 0,
    }
    for record in descriptions:
        if args.limit is not None and stats["processed"] >= args.limit:
            break
        result = process_record(record, args, output_dir, runner, runs_manifest, completed)
        stats["processed"] += 1
        stats[result] = stats.get(result, 0) + 1
    summary = {
        "descriptions_manifest": str(resolve_repo_path(args.descriptions_manifest)),
        "signature_root": str(resolve_repo_path(args.signature_root)),
        "output_dir": str(output_dir),
        "runs_manifest": str(runs_manifest),
        "spec_skill": args.spec_skill,
        "test_skill": args.test_skill,
        "max_feedback_rounds": args.max_feedback_rounds,
        "stats": stats,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if stats.get("agent_error", 0) == 0 and stats.get("timeout", 0) == 0 and stats.get("missing_input", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
