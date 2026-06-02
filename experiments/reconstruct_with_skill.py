#!/usr/bin/env python3
"""
Run a selected Codex skill once per natural-language description.

This script orchestrates the research reconstruction step. It does not generate
Spectra itself. Instead, it starts a fresh agent process for each description,
passes the selected skill in the prompt, and stores run artifacts outside the
dataset directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from string import Template
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from prompts import AGENT_RECONSTRUCTION_PROMPTS


DEFAULT_DESCRIPTIONS_MANIFEST = "dataset/nl_descriptions/descriptions.jsonl"
DEFAULT_OUTPUT_DIR = "experiments/runs"
DEFAULT_AGENT_COMMAND = "codex exec --ephemeral -"
LOGGER = logging.getLogger("reconstruct_with_skill")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a selected skill for each NL description.")
    parser.add_argument("--skill", required=True, help="Skill name, e.g. respect-method-2.")
    parser.add_argument("--descriptions-manifest", default=DEFAULT_DESCRIPTIONS_MANIFEST)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--agent-command",
        default=DEFAULT_AGENT_COMMAND,
        help=(
            "Command used to start a fresh agent process. The prompt is passed via stdin unless "
            "the command contains {prompt_file}. "
            f"Default: {DEFAULT_AGENT_COMMAND!r}"
        ),
    )
    parser.add_argument(
        "--agent-model",
        default=None,
        help="Optional label for the agent model/configuration; stored in metadata only.",
    )
    parser.add_argument(
        "--agent-prompt-name",
        choices=sorted(AGENT_RECONSTRUCTION_PROMPTS),
        default="agent_reconstruction_v1",
    )
    parser.add_argument("--timeout", type=float, default=1800.0, help="Timeout per agent run in seconds.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of descriptions to process.")
    parser.add_argument("--force", action="store_true", help="Run even if a matching successful run exists.")
    parser.add_argument(
        "--refresh-before",
        default=None,
        help="ISO timestamp. Existing runs before this timestamp are treated as stale.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Create prompts and metadata without running the agent.")
    parser.add_argument("--log-file", default=None)
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
    )
    return parser.parse_args()


def configure_logging(log_level: str, log_file: str | None) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_path, encoding="utf-8"))
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
    )


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def safe_path_part(value: str, max_length: int = 120) -> str:
    safe = re.sub(r"[^A-Za-z0-9._=-]+", "_", value).strip("_")
    return (safe or "value")[:max_length]


def description_relative_stem(response_file: Path) -> Path:
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


def resolve_reported_path(path_value: str | None) -> Path | None:
    if not path_value:
        return None
    path = Path(path_value)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve()


def copy_reconstructed_spectra(parsed_result: dict[str, Any] | None, destination: Path) -> str | None:
    source = resolve_reported_path(parsed_result.get("spectra_file") if parsed_result else None)
    if source is None or not source.is_file():
        return None

    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() != destination.resolve():
        shutil.copy2(source, destination)
    return str(destination)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not path.is_file():
        return records
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            records.append(json.loads(line))
    return records


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def record_is_fresh(record: dict[str, Any], refresh_before: datetime | None) -> bool:
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


def run_key(
    *,
    description_record: dict[str, Any],
    skill: str,
    agent_command: str,
    agent_model: str | None,
    agent_prompt_name: str,
    agent_prompt_sha256: str,
) -> str:
    return sha256_text(
        json.dumps(
            {
                "description_id": description_record.get("description_id"),
                "description_response_sha256": description_record.get("response_sha256"),
                "skill": skill,
                "agent_command": agent_command,
                "agent_model": agent_model,
                "agent_prompt_name": agent_prompt_name,
                "agent_prompt_sha256": agent_prompt_sha256,
            },
            sort_keys=True,
        )
    )


def completed_run_keys(runs_manifest: Path, refresh_before: datetime | None) -> set[str]:
    keys: set[str] = set()
    for record in load_jsonl(runs_manifest):
        if record.get("status") == "success" and record.get("run_key") and record_is_fresh(record, refresh_before):
            keys.add(record["run_key"])
    return keys


def render_agent_prompt(
    *,
    template: str,
    skill: str,
    run_dir: Path,
    natural_language_description: str,
) -> str:
    return Template(template).safe_substitute(
        skill_name=skill,
        run_dir=str(run_dir),
        natural_language_description=natural_language_description,
    )


def extract_last_json_object(text: str) -> dict[str, Any] | None:
    for start in range(len(text) - 1, -1, -1):
        if text[start] != "{":
            continue
        candidate = text[start:].strip()
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def build_command(agent_command: str, prompt_file: Path) -> tuple[str, bool]:
    if "{prompt_file}" in agent_command:
        return agent_command.format(prompt_file=str(prompt_file)), False
    return agent_command, True


def run_agent(command: str, prompt_text: str, pass_prompt_on_stdin: bool, timeout: float) -> subprocess.CompletedProcess[str]:
    LOGGER.info("Starting fresh agent process: %s", command)
    return subprocess.run(
        command,
        cwd=REPO_ROOT,
        input=prompt_text if pass_prompt_on_stdin else None,
        capture_output=True,
        text=True,
        check=False,
        shell=True,
        timeout=timeout,
    )


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def process_description(
    *,
    record: dict[str, Any],
    args: argparse.Namespace,
    output_dir: Path,
    runs_manifest: Path,
    known_completed: set[str],
    refresh_before: datetime | None,
) -> str:
    response_file = Path(record["response_file"])
    natural_language_description = response_file.read_text(encoding="utf-8")
    agent_template = AGENT_RECONSTRUCTION_PROMPTS[args.agent_prompt_name]

    provisional_prompt = render_agent_prompt(
        template=agent_template,
        skill=args.skill,
        run_dir=Path("<run_dir>"),
        natural_language_description=natural_language_description,
    )
    current_run_key = run_key(
        description_record=record,
        skill=args.skill,
        agent_command=args.agent_command,
        agent_model=args.agent_model,
        agent_prompt_name=args.agent_prompt_name,
        agent_prompt_sha256=sha256_text(provisional_prompt),
    )
    if not args.force and current_run_key in known_completed:
        LOGGER.info("Skipping already completed run for description_id=%s", record.get("description_id"))
        return "skipped"

    skill_dir = safe_path_part(args.skill)
    description_stem = description_relative_stem(response_file)
    run_id = current_run_key[:24]
    run_dir = output_dir / skill_dir / "runs" / description_stem
    artifacts_dir = run_dir / "artifacts"
    reconstructed_spectra_file = output_dir / skill_dir / "files" / description_stem / f"{skill_dir}.spectra"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    agent_prompt = render_agent_prompt(
        template=agent_template,
        skill=args.skill,
        run_dir=artifacts_dir,
        natural_language_description=natural_language_description,
    )
    prompt_file = run_dir / "agent_prompt.txt"
    input_file = run_dir / "input_description.txt"
    stdout_file = run_dir / "agent_stdout.txt"
    stderr_file = run_dir / "agent_stderr.txt"
    parsed_result_file = run_dir / "parsed_result.json"

    write_text(prompt_file, agent_prompt)
    write_text(input_file, natural_language_description)

    command, pass_prompt_on_stdin = build_command(args.agent_command, prompt_file)
    started_at = utc_now()
    started = time.perf_counter()

    status = "dry_run"
    exit_code: int | None = None
    parsed_result: dict[str, Any] | None = None
    error: str | None = None

    if args.dry_run:
        LOGGER.info("Dry run created prompt for description_id=%s at %s", record.get("description_id"), prompt_file)
        write_text(stdout_file, "")
        write_text(stderr_file, "")
    else:
        try:
            completed = run_agent(command, agent_prompt, pass_prompt_on_stdin, args.timeout)
            exit_code = completed.returncode
            write_text(stdout_file, completed.stdout)
            write_text(stderr_file, completed.stderr)
            parsed_result = extract_last_json_object(completed.stdout)
            if parsed_result is not None:
                parsed_result_file.write_text(json.dumps(parsed_result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            status = "success" if completed.returncode == 0 else "agent_error"
        except subprocess.TimeoutExpired as exc:
            status = "timeout"
            error = f"Agent command timed out after {args.timeout} seconds."
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            write_text(stdout_file, stdout)
            write_text(stderr_file, stderr)

    finished_at = utc_now()
    duration_ms = int((time.perf_counter() - started) * 1000)
    copied_spectra_file = None
    if status == "success":
        copied_spectra_file = copy_reconstructed_spectra(parsed_result, reconstructed_spectra_file)
        if copied_spectra_file:
            LOGGER.info("Copied reconstructed Spectra file to %s", copied_spectra_file)
        elif not args.dry_run:
            LOGGER.warning("Agent run succeeded but no reported spectra_file could be copied for %s", record.get("description_id"))

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
        "agent_command": args.agent_command,
        "resolved_agent_command": command,
        "prompt_passed_on_stdin": pass_prompt_on_stdin,
        "agent_model": args.agent_model,
        "agent_prompt_name": args.agent_prompt_name,
        "agent_prompt_sha256": sha256_text(agent_prompt),
        "run_dir": str(run_dir),
        "artifacts_dir": str(artifacts_dir),
        "description_relative_stem": str(description_stem),
        "reconstructed_spectra_file": copied_spectra_file,
        "expected_reconstructed_spectra_file": str(reconstructed_spectra_file),
        "agent_prompt_file": str(prompt_file),
        "input_description_file": str(input_file),
        "agent_stdout_file": str(stdout_file),
        "agent_stderr_file": str(stderr_file),
        "parsed_result_file": str(parsed_result_file) if parsed_result else None,
        "agent_exit_code": exit_code,
        "reported_cli_status": parsed_result.get("cli_status") if parsed_result else None,
        "reported_repair_loops": parsed_result.get("repair_loops") if parsed_result else None,
        "reported_spectra_file": parsed_result.get("spectra_file") if parsed_result else None,
        "reported_controller_output_dir": parsed_result.get("controller_output_dir") if parsed_result else None,
        "timeout_seconds": args.timeout,
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
    LOGGER.info("Finished run_id=%s status=%s description_id=%s", run_id, status, record.get("description_id"))
    return status


def main() -> int:
    args = parse_args()
    configure_logging(args.log_level, args.log_file)

    descriptions_manifest = Path(args.descriptions_manifest)
    descriptions = load_jsonl(descriptions_manifest)
    if not descriptions:
        LOGGER.error("No descriptions found in %s", descriptions_manifest)
        return 2

    output_dir = Path(args.output_dir)
    runs_manifest = output_dir / safe_path_part(args.skill) / "runs.jsonl"
    refresh_before = parse_iso_datetime(args.refresh_before)
    known_completed = set() if args.force else completed_run_keys(runs_manifest, refresh_before)

    LOGGER.info(
        "Starting reconstruction: descriptions=%s skill=%s prompt=%s completed=%s force=%s dry_run=%s",
        len(descriptions),
        args.skill,
        args.agent_prompt_name,
        len(known_completed),
        args.force,
        args.dry_run,
    )

    stats = {"processed": 0, "success": 0, "skipped": 0, "agent_error": 0, "timeout": 0, "dry_run": 0}
    for record in descriptions:
        if args.limit is not None and stats["processed"] >= args.limit:
            break
        result = process_description(
            record=record,
            args=args,
            output_dir=output_dir,
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
        "agent_prompt_name": args.agent_prompt_name,
        "agent_command": args.agent_command,
        "agent_model": args.agent_model,
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
