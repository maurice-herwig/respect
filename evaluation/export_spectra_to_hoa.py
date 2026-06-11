#!/usr/bin/env python3
"""Export one Spectra specification to HOA with the modified Spectra CLI."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JAR = REPO_ROOT / "assets" / "cli_with_hoa_export" / "spectra-cli.jar"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "evaluation" / "hoa_exports"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def resolve_input_path(path_value: str) -> Path:
    path = Path(path_value)
    candidates = [path]
    if not path.is_absolute():
        candidates.append(REPO_ROOT / path)

    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_file():
            return resolved

    return candidates[0].resolve()


def resolve_existing_path(path_value: str) -> Path:
    path = Path(path_value)
    candidates = [path]
    if not path.is_absolute():
        candidates.append(REPO_ROOT / path)

    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.exists():
            return resolved

    return candidates[0].resolve()


def default_output_path(input_path: Path) -> Path:
    digest = sha256_file(input_path)[:16]
    safe_stem = "".join(char if char.isalnum() or char in "._=-" else "_" for char in input_path.stem)
    return DEFAULT_OUTPUT_DIR / f"{safe_stem}__{digest}.hoa"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export a .spectra file to HOA using assets/cli_with_hoa_export/spectra-cli.jar."
    )
    parser.add_argument("--input", required=True, help="Path to the .spectra file to export.")
    parser.add_argument(
        "--output",
        default=None,
        help="Path for the generated .hoa file. Defaults to evaluation/hoa_exports/<name>__<sha>.hoa.",
    )
    parser.add_argument("--jar", default=str(DEFAULT_JAR), help="Path to the modified spectra-cli.jar.")
    parser.add_argument("--max-states", type=int, default=100_000, help="Maximum reachable states to enumerate.")
    parser.add_argument("--timeout", type=float, default=120.0, help="Maximum seconds for the CLI invocation.")
    parser.add_argument(
        "--jtlv",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use the Java BDD backend instead of native CUDD. Enabled by default.",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite an existing HOA output file.")
    parser.add_argument(
        "--keep-partial",
        action="store_true",
        help="Keep a partially written HOA file if the CLI exits unsuccessfully.",
    )
    parser.add_argument(
        "--include-raw-output",
        action="store_true",
        help="Include the full Spectra CLI stdout/stderr in the JSON result.",
    )
    parser.add_argument(
        "--raw-output-tail-chars",
        type=int,
        default=4000,
        help="Maximum CLI output tail characters to include when --include-raw-output is not set.",
    )
    return parser.parse_args()


def build_command(jar_path: Path, input_path: Path, output_path: Path, max_states: int, use_jtlv: bool) -> list[str]:
    command = [
        "java",
        "-jar",
        str(jar_path),
        "-i",
        str(input_path),
    ]
    if use_jtlv:
        command.append("--jtlv")
    command.extend(
        [
            "--export-hoa",
            "--hoa-output",
            str(output_path),
            "--max-states",
            str(max_states),
        ]
    )
    return command


def print_result(result: dict[str, Any]) -> None:
    print(json.dumps(result, indent=2, sort_keys=True))


def output_fields(raw_output: str, include_raw_output: bool, tail_chars: int) -> dict[str, Any]:
    if include_raw_output:
        return {"raw_output": raw_output}
    if tail_chars <= 0:
        return {"raw_output_truncated": len(raw_output) > 0, "raw_output_tail": ""}
    return {
        "raw_output_truncated": len(raw_output) > tail_chars,
        "raw_output_tail": raw_output[-tail_chars:],
    }


def main() -> int:
    args = parse_args()
    input_path = resolve_input_path(args.input)
    jar_path = resolve_existing_path(args.jar)

    if not input_path.is_file():
        print_result({"status": "error", "message": f"Input file not found: {input_path}"})
        return 2
    if input_path.suffix.lower() != ".spectra":
        print_result({"status": "error", "message": f"Input is not a .spectra file: {input_path}"})
        return 2
    if not jar_path.is_file():
        print_result({"status": "error", "message": f"Modified spectra-cli.jar not found: {jar_path}"})
        return 2

    output_path = Path(args.output).resolve() if args.output else default_output_path(input_path).resolve()
    if output_path.exists() and not args.force:
        print_result(
            {
                "status": "error",
                "message": f"Output file already exists: {output_path}. Use --force to overwrite it.",
                "hoa_file": str(output_path),
            }
        )
        return 2

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists() and args.force:
        output_path.unlink()

    command = build_command(jar_path, input_path, output_path, args.max_states, args.jtlv)
    started_at = utc_now()

    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False, timeout=args.timeout)
    except subprocess.TimeoutExpired as exc:
        if output_path.exists() and not args.keep_partial:
            output_path.unlink()
        raw_output = "\n".join(part for part in (exc.stdout or "", exc.stderr or "") if part).strip()
        result = {
                "status": "timeout",
                "input": repo_relative_or_absolute(input_path),
                "hoa_file": repo_relative_or_absolute(output_path),
                "jar": repo_relative_or_absolute(jar_path),
                "command": command,
                "exit_code": None,
                "max_states": args.max_states,
                "timeout_seconds": args.timeout,
                "jtlv": args.jtlv,
                "started_at": started_at,
                "finished_at": utc_now(),
            }
        result.update(output_fields(raw_output, args.include_raw_output, args.raw_output_tail_chars))
        print_result(result)
        return 1

    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    raw_output = stdout if not stderr else f"{stdout}\n{stderr}".strip()
    hoa_exists = output_path.is_file()
    hoa_size_bytes = output_path.stat().st_size if hoa_exists else None

    if completed.returncode == 0 and hoa_exists and hoa_size_bytes and hoa_size_bytes > 0:
        status = "exported"
        exit_status = 0
    else:
        status = "error"
        exit_status = 1
        if hoa_exists and not args.keep_partial:
            output_path.unlink()
            hoa_exists = False
            hoa_size_bytes = None

    result = {
        "status": status,
        "input": repo_relative_or_absolute(input_path),
        "input_sha256": sha256_file(input_path),
        "hoa_file": repo_relative_or_absolute(output_path),
        "hoa_exists": hoa_exists,
        "hoa_size_bytes": hoa_size_bytes,
        "jar": repo_relative_or_absolute(jar_path),
        "jar_sha256": sha256_file(jar_path),
        "command": command,
        "exit_code": completed.returncode,
        "max_states": args.max_states,
        "timeout_seconds": args.timeout,
        "jtlv": args.jtlv,
        "started_at": started_at,
        "finished_at": utc_now(),
    }
    result.update(output_fields(raw_output, args.include_raw_output, args.raw_output_tail_chars))
    print_result(result)
    return exit_status


if __name__ == "__main__":
    sys.exit(main())
