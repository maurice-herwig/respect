#!/usr/bin/env python3
"""
Run spectra-cli.jar and normalize its output for ReSpect broker workflows.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


def default_jar_path() -> Path:
    return Path(__file__).resolve().parents[4] / "spectra-cli.jar"


def default_unrealizable_core_jar_path() -> Path:
    return Path(__file__).resolve().parents[4] / "assets" / "cli_with_unrealizable_core" / "spectra-cli-with-un-core.jar"


def detect_status(stdout: str, synthesize: bool) -> str:
    if "Result: Found unrealizable core" in stdout:
        return "unrealizable_core_found"
    if "Error: Cannot compute unrealizable core for a realizable specification" in stdout:
        return "no_unrealizable_core"
    if "Could not prepare game input from Spectra file" in stdout or "ErrorsInSpectraException" in stdout:
        return "syntax_error"
    if "Result: Specification is non-well-separated" in stdout:
        return "non_well_separated"
    if "Result: Specification is well-separated" in stdout:
        return "well_separated"
    if "Result: Specification is unrealizable" in stdout:
        return "unrealizable"
    if "Result: Specification is realizable" in stdout:
        if synthesize and "Successfully synthesized" in stdout:
            return "synthesized"
        return "realizable"
    return "unknown"


def parse_unrealizable_core(stdout: str) -> tuple[int | None, list[int]]:
    match = re.search(r"Result: Found unrealizable core with (\d+) guarantees, at lines <([^>]*)>", stdout)
    if not match:
        return None, []
    return int(match.group(1)), [int(value) for value in re.findall(r"\d+", match.group(2))]


def build_command(
    jar_path: Path,
    input_path: Path,
    output_dir: Path | None,
    synthesize: bool,
    counter_strategy: bool,
    counter_strategy_jtlv_format: bool,
    well_separation: bool,
    unrealizable_core: bool,
) -> list[str]:
    command = ["java", "-jar", str(jar_path), "-i", str(input_path)]
    if synthesize:
        command.append("-s")
    if output_dir is not None:
        command.extend(["-o", str(output_dir)])
    if counter_strategy_jtlv_format:
        command.append("--counter-strategy-jtlv-format")
    elif counter_strategy:
        command.append("--counter-strategy")
    if well_separation:
        command.append("--well-separation")
    if unrealizable_core:
        command.append("--unrealizable-core")
    return command


def main() -> int:
    parser = argparse.ArgumentParser(description="Run spectra-cli.jar and summarize the result.")
    parser.add_argument("--input", required=True, help="Path to the .spectra file to check")
    parser.add_argument("--jar", default=str(default_jar_path()), help="Path to spectra-cli.jar")
    parser.add_argument(
        "--unrealizable-core-jar",
        default=str(default_unrealizable_core_jar_path()),
        help="Path to the Spectra CLI JAR that supports --unrealizable-core",
    )
    parser.add_argument("--output-dir", help="Output directory for synthesis artifacts")
    parser.add_argument("--synthesize", action="store_true", help="Run controller synthesis with -s")
    parser.add_argument(
        "--counter-strategy",
        action="store_true",
        help="Generate a counter-strategy for an unrealizable specification",
    )
    parser.add_argument(
        "--counter-strategy-jtlv-format",
        action="store_true",
        help="Generate a counter-strategy and print it in JTLV text format",
    )
    parser.add_argument(
        "--well-separation",
        action="store_true",
        help="Check whether the specification is well-separated",
    )
    parser.add_argument(
        "--unrealizable-core",
        action="store_true",
        help="Compute an unrealizable core for an unrealizable specification",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="Maximum seconds to wait for spectra-cli.jar before returning status timeout",
    )
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    jar_path = Path(args.unrealizable_core_jar if args.unrealizable_core else args.jar).resolve()
    output_dir = Path(args.output_dir).resolve() if args.output_dir else None
    counter_strategy = args.counter_strategy or args.counter_strategy_jtlv_format

    if sum(bool(flag) for flag in (args.synthesize, counter_strategy, args.well_separation, args.unrealizable_core)) > 1:
        print(json.dumps({"status": "error", "message": "Cannot combine synthesis, counter-strategy diagnostics, well-separation checks, and unrealizable-core diagnostics."}))
        return 2

    if not input_path.is_file():
        print(json.dumps({"status": "error", "message": f"Input file not found: {input_path}"}))
        return 2

    if not jar_path.is_file():
        print(json.dumps({"status": "error", "message": f"spectra-cli.jar not found: {jar_path}"}))
        return 2

    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)

    command = build_command(
        jar_path,
        input_path,
        output_dir,
        args.synthesize,
        args.counter_strategy,
        args.counter_strategy_jtlv_format,
        args.well_separation,
        args.unrealizable_core,
    )
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False, timeout=args.timeout)
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        combined_output = stdout if not stderr else f"{stdout}\n{stderr}".strip()
        result = {
            "status": "timeout",
            "input": str(input_path),
            "jar": str(jar_path),
            "command": command,
            "exit_code": None,
            "synthesize": args.synthesize,
            "counter_strategy": counter_strategy,
            "counter_strategy_format": "jtlv" if args.counter_strategy_jtlv_format else "default",
            "well_separation": args.well_separation,
            "unrealizable_core": args.unrealizable_core,
            "unrealizable_core_size": None,
            "unrealizable_core_lines": [],
            "output_dir": str(output_dir) if output_dir else None,
            "timeout_seconds": args.timeout,
            "raw_output": combined_output,
        }
        print(json.dumps(result, indent=2))
        return 0

    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    combined_output = stdout if not stderr else f"{stdout}\n{stderr}".strip()
    unrealizable_core_size, unrealizable_core_lines = parse_unrealizable_core(combined_output)

    result = {
        "status": detect_status(combined_output, args.synthesize),
        "input": str(input_path),
        "jar": str(jar_path),
        "command": command,
        "exit_code": completed.returncode,
        "synthesize": args.synthesize,
        "counter_strategy": counter_strategy,
        "counter_strategy_format": "jtlv" if args.counter_strategy_jtlv_format else "default",
        "well_separation": args.well_separation,
        "unrealizable_core": args.unrealizable_core,
        "unrealizable_core_size": unrealizable_core_size,
        "unrealizable_core_lines": unrealizable_core_lines,
        "output_dir": str(output_dir) if output_dir else None,
        "timeout_seconds": args.timeout,
        "raw_output": combined_output,
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
