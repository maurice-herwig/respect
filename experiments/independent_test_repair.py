#!/usr/bin/env python3
"""Run one independent-test ReSpect repair experiment.

The runner keeps the specification agent and test-writer agent in separate
processes. The spec agent sees NL requirements, the fixed signature, and test
feedback from previous rounds. The test writer sees NL requirements, the fixed
signature, and controller metadata, but not generated Spectra contents.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AGENT_COMMAND = "codex --ask-for-approval never exec --ephemeral --sandbox danger-full-access -"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "experiments" / "independent_test_runs"
DEFAULT_SPEC_SKILL = "respect-spec-tester"
DEFAULT_TEST_SKILL = "respect-test-writer"


def parse_args() -> argparse.Namespace:
    """Parse command-line options for one independent-test feedback run."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--description-file", required=True)
    parser.add_argument("--signature-file", required=True)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--spec-skill", default=DEFAULT_SPEC_SKILL)
    parser.add_argument("--test-skill", default=DEFAULT_TEST_SKILL)
    parser.add_argument("--agent-command", default=DEFAULT_AGENT_COMMAND)
    parser.add_argument("--timeout", type=float, default=1800.0)
    parser.add_argument("--max-feedback-rounds", type=int, default=3)
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


def extract_path_value(value: Any) -> Path | None:
    """Normalize agent-reported paths, including Markdown links, to repo paths."""
    if value is None:
        return None
    text = str(value).strip()
    markdown_match = re.match(r"^\[[^\]]+\]\(([^)]+)\)$", text)
    if markdown_match:
        text = markdown_match.group(1)
    if text.lower() in {"", "none", "null"}:
        return None
    return resolve_repo_path(text)


def write_text(path: Path, content: str | None) -> None:
    """Write UTF-8 text to a file, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content or "", encoding="utf-8")


def write_json(path: Path, payload: Any) -> None:
    """Write stable, pretty-printed JSON to a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_json(path: Path) -> Any:
    """Load a JSON document from a UTF-8 file."""
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_result_value(value: str) -> Any:
    """Coerce key-value result text into Python booleans, integers, or None."""
    stripped = value.strip()
    if stripped.lower() in {"none", "null", ""}:
        return None
    if stripped.lower() in {"true", "false"}:
        return stripped.lower() == "true"
    if re.fullmatch(r"-?\d+", stripped):
        return int(stripped)
    if stripped.startswith(("[", "{")):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass
    return stripped


def extract_last_json_object(text: str) -> dict[str, Any] | None:
    """Return the last JSON object embedded in agent stdout, if one exists.

    Agent final answers often wrap JSON in Markdown fences. `raw_decode` lets us
    parse the object prefix without requiring the rest of stdout to be JSON.
    """
    decoder = json.JSONDecoder()
    matches: list[dict[str, Any]] = []
    for start in range(len(text) - 1, -1, -1):
        if text[start] != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(text[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            matches.append(parsed)
    return matches[0] if matches else None


def extract_key_value_result(text: str) -> dict[str, Any] | None:
    """Parse final `key: value` result blocks from agent stdout."""
    result: dict[str, Any] = {}
    for line in text.splitlines():
        match = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*?)\s*$", line)
        if match:
            result[match.group(1)] = normalize_result_value(match.group(2))
    return result or None


def extract_agent_result(text: str) -> dict[str, Any] | None:
    """Extract an agent's final result, preferring JSON over key-value text."""
    return extract_last_json_object(text) or extract_key_value_result(text)


def extract_string_list(value: Any) -> list[str]:
    """Normalize agent-reported string lists from JSON or key-value output."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped or stripped.lower() in {"none", "null", "[]"}:
            return []
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            return [part.strip() for part in stripped.split(",") if part.strip()]
        return extract_string_list(parsed)
    return [str(value).strip()] if str(value).strip() else []


def invalid_test_names_from_result(spec_result: dict[str, Any] | None) -> list[str]:
    """Extract rejected independent-test names from a spec-agent result."""
    if not spec_result:
        return []
    names = extract_string_list(spec_result.get("invalid_test_names"))
    names.extend(extract_string_list(spec_result.get("rejected_invalid_test_names")))
    return sorted(set(names))


def build_command(agent_command: str, prompt_file: Path) -> tuple[str, bool]:
    """Render the agent command and report whether the prompt goes to stdin."""
    if "{prompt_file}" in agent_command:
        return agent_command.format(prompt_file=str(prompt_file)), False
    return agent_command, True


def run_agent(
    *,
    command_template: str,
    prompt: str,
    prompt_file: Path,
    stdout_file: Path,
    stderr_file: Path,
    timeout: float,
) -> tuple[int | None, dict[str, Any] | None, str | None]:
    """Run one agent process and persist prompt/stdout/stderr artifacts."""
    write_text(prompt_file, prompt)
    command, pass_stdin = build_command(command_template, prompt_file)
    try:
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            input=prompt if pass_stdin else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            shell=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        write_text(stdout_file, exc.stdout or "")
        write_text(stderr_file, exc.stderr or "")
        return None, None, f"Agent timed out after {timeout} seconds."

    write_text(stdout_file, completed.stdout)
    write_text(stderr_file, completed.stderr)
    return completed.returncode, extract_agent_result(completed.stdout), None


def signature_names(signature: dict[str, Any], key: str) -> list[str]:
    """Extract variable names from a signature section of strings or objects."""
    values = signature.get(key) or []
    names: list[str] = []
    for item in values:
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict) and isinstance(item.get("name"), str):
            names.append(item["name"])
    return names


def infer_spec_name(spectra_file: Path) -> str | None:
    """Read the generated Spectra module name when no signature name is set."""
    if not spectra_file.is_file():
        return None
    match = re.search(r"^\s*spec\s+([A-Za-z_][A-Za-z0-9_]*)", spectra_file.read_text(encoding="utf-8"), re.MULTILINE)
    return match.group(1) if match else None


def build_spec_prompt(
    *,
    skill: str,
    run_dir: Path,
    natural_language: str,
    signature_json: str,
    round_index: int,
    previous_spectra_file: Path | None,
    test_result_file: Path | None,
    max_feedback_rounds: int,
) -> str:
    """Build the prompt for the specification agent for one feedback round."""
    feedback = "No independent test feedback is available for this initial round."
    if previous_spectra_file and test_result_file:
        feedback = f"""Repair round {round_index}.

Previous generated Spectra file: {previous_spectra_file}
Aggregated independent test result file: {test_result_file}

Read the previous generated Spectra and aggregated test results. The aggregate
contains all valid independent test plans accumulated so far, rerun against the
latest controller from the previous round. Repair the Spectra only when a
failing test is justified by the natural-language requirements. After any
Spectra edit, rerun validation, well-separation, and synthesis.
"""
    return f"""Use ${skill}.

Run directory: {run_dir}
Feedback round: {round_index} of {max_feedback_rounds}

Fixed env/sys signature JSON:

```json
{signature_json}
```

{feedback}

Natural-language requirements:

{natural_language}
"""


def build_test_prompt(
    *,
    skill: str,
    run_dir: Path,
    natural_language: str,
    signature_json: str,
    spec_name: str,
    spectra_file: Path,
    controller_dir: Path,
    output_dir: Path,
) -> str:
    """Build the independent test-writer prompt without leaking Spectra content."""
    return f"""Use ${skill}.

Write independent controller tests in the controller_tests .rtest DSL.

Output directory: {output_dir}
Required test plan path: {output_dir / "test-plan.rtest"}

Fixed env/sys signature JSON:

```json
{signature_json}
```

Controller metadata:
- spec_name: {spec_name}
- controller_dir: {controller_dir}
- spectra_file: {spectra_file}

Important boundaries:
- Do not open or inspect the generated Spectra file. Use spectra_file only as a DSL path.
- Do not read the specification agent stdout, repair logs, source Spectra, benchmark oracles, or distance results.
- Derive expected behavior only from the natural-language requirements and fixed signature.
- Do not write only happy-path tests. Include adversarial bounded tests such as simultaneous requests, no-request cases, persistent one-sided requests, alternating inputs, and boundary values when supported by the natural-language requirements.
- Do not turn unbounded liveness into a hard bounded deadline unless the natural-language requirements state that deadline.

Natural-language requirements:

{natural_language}
"""


def compile_test_plan(rtest_file: Path, json_file: Path) -> subprocess.CompletedProcess[str]:
    """Compile an `.rtest` DSL plan into the JSON consumed by the Java runner."""
    return subprocess.run(
        [sys.executable, "controller_tests/compile_test_plan.py", str(rtest_file), "-o", str(json_file)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def build_controller_tests() -> subprocess.CompletedProcess[str]:
    """Compile the Java controller-test harness before running test plans."""
    java_files = [str(path) for path in (REPO_ROOT / "controller_tests" / "src" / "main" / "java").rglob("*.java")]
    return subprocess.run(
        ["javac", "-cp", "assets/examples/E2_execution/executor.jar", "-d", "controller_tests/build/classes", *java_files],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def run_controller_tests(plan_file: Path, result_file: Path) -> subprocess.CompletedProcess[str]:
    """Execute a compiled controller-test plan against the synthesized controller."""
    classpath_sep = ";" if os.name == "nt" else ":"
    classpath = f"controller_tests/build/classes{classpath_sep}assets/examples/E2_execution/executor.jar"
    return subprocess.run(
        [
            "java",
            "-Djava.library.path=.",
            "-cp",
            classpath,
            "respect.controller_tests.TestRunner",
            "--plan",
            str(plan_file),
            "--output",
            str(result_file),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def rebind_test_plan(source_plan: Path, target_plan: Path, *, spec_name: str, spectra_file: Path, controller_dir: Path) -> None:
    """Copy a compiled test plan while pointing it at the current controller."""
    plan = load_json(source_plan)
    plan["spec_name"] = spec_name
    plan["spectra_file"] = str(spectra_file)
    plan["controller_dir"] = str(controller_dir)
    write_json(target_plan, plan)


def test_counts(result_file: Path) -> tuple[int, int, int]:
    """Return total, passed, and failed counts from a controller-test result file."""
    if not result_file.is_file():
        return 0, 0, 0
    payload = load_json(result_file)
    tests = payload.get("results") or payload.get("tests") or []
    total = len(tests)
    passed = sum(1 for item in tests if item.get("passed") is True)
    return total, passed, total - passed


def aggregate_test_results(
    result_files: list[tuple[int, Path]],
    aggregate_file: Path,
    invalid_test_names: set[str] | None = None,
) -> tuple[int, int, int, int]:
    """Merge controller-test results, excluding tests the spec agent rejected.

    Rejected tests are retained as metadata so the experiment can audit them,
    but they are not counted as active regression feedback in later rounds.
    """
    invalid_test_names = invalid_test_names or set()
    aggregate_results: list[dict[str, Any]] = []
    ignored_invalid_tests: list[dict[str, Any]] = []
    total = passed = failed = 0
    for source_round, result_file in result_files:
        payload = load_json(result_file)
        for result in payload.get("results") or payload.get("tests") or []:
            annotated = dict(result)
            annotated["source_test_round"] = source_round
            annotated["source_result_file"] = str(result_file)
            if str(result.get("name", "")).strip() in invalid_test_names:
                ignored_invalid_tests.append(annotated)
                continue
            aggregate_results.append(annotated)
            total += 1
            if result.get("passed") is True:
                passed += 1
            else:
                failed += 1

    write_json(
        aggregate_file,
        {
            "status": "passed" if failed == 0 else "failed",
            "total": total,
            "passed": passed,
            "failed": failed,
            "invalid_tests_filtered": len(ignored_invalid_tests),
            "invalid_test_names": sorted(invalid_test_names),
            "ignored_invalid_tests": ignored_invalid_tests,
            "results": aggregate_results,
        },
    )
    return total, passed, failed, len(ignored_invalid_tests)


def summarize_status(rounds: list[dict[str, Any]], final_spec_result: dict[str, Any] | None) -> str:
    """Classify the run outcome with experiment-specific terminal statuses."""
    if not final_spec_result or final_spec_result.get("cli_status") != "synthesized":
        return "spec_not_synthesized"
    if not rounds:
        return "spec_not_synthesized"

    last_round = rounds[-1]
    stop_reason = last_round.get("stop_reason")
    if stop_reason in {"test_agent_failed", "missing_test_plan_path", "test_plan_compile_failed"}:
        return "test_generation_failed"
    if last_round.get("stop_reason") == "tests_passed":
        if last_round.get("invalid_tests_filtered", 0):
            return "invalid_tests_rejected"
        return "tests_passed"
    if isinstance(last_round.get("tests_failed"), int) and last_round["tests_failed"] > 0:
        return "max_rounds_with_failures"
    if last_round.get("stop_reason") == "max_feedback_rounds_reached":
        return "max_rounds_with_failures"
    return "completed_without_test_success"


def main() -> int:
    """Coordinate spec generation, independent test writing, and repair rounds."""
    args = parse_args()
    description_file = resolve_repo_path(args.description_file)
    signature_file = resolve_repo_path(args.signature_file)
    natural_language = description_file.read_text(encoding="utf-8")
    signature = load_json(signature_file)
    signature_json = json.dumps(signature, indent=2, sort_keys=True)
    run_id = args.run_id or f"independent-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    run_dir = resolve_repo_path(args.output_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    write_text(run_dir / "input_description.txt", natural_language)
    shutil.copyfile(signature_file, run_dir / "signature.json")

    if args.dry_run:
        write_json(run_dir / "summary.json", {"status": "dry_run", "run_dir": str(run_dir)})
        print(json.dumps({"status": "dry_run", "run_dir": str(run_dir)}, indent=2, sort_keys=True))
        return 0

    build_result = build_controller_tests()
    write_text(run_dir / "build_controller_tests.stdout.txt", build_result.stdout)
    write_text(run_dir / "build_controller_tests.stderr.txt", build_result.stderr)
    if build_result.returncode != 0:
        summary = {"status": "controller_tests_build_failed", "run_dir": str(run_dir), "exit_code": build_result.returncode}
        write_json(run_dir / "summary.json", summary)
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 1

    started_at = utc_now()
    started = time.perf_counter()
    previous_spectra_file: Path | None = None
    previous_test_result_file: Path | None = None
    compiled_test_plans: list[tuple[int, Path]] = []
    rounds: list[dict[str, Any]] = []
    final_spec_result: dict[str, Any] | None = None
    invalid_test_names: set[str] = set()

    for round_index in range(args.max_feedback_rounds + 1):
        round_dir = run_dir / f"round-{round_index:02d}"
        spec_dir = round_dir / "spec-agent"
        spec_prompt = build_spec_prompt(
            skill=args.spec_skill,
            run_dir=spec_dir,
            natural_language=natural_language,
            signature_json=signature_json,
            round_index=round_index,
            previous_spectra_file=previous_spectra_file,
            test_result_file=previous_test_result_file,
            max_feedback_rounds=args.max_feedback_rounds,
        )
        spec_exit, spec_result, spec_error = run_agent(
            command_template=args.agent_command,
            prompt=spec_prompt,
            prompt_file=spec_dir / "agent_prompt.txt",
            stdout_file=spec_dir / "agent_stdout.txt",
            stderr_file=spec_dir / "agent_stderr.txt",
            timeout=args.timeout,
        )
        if spec_result:
            write_json(spec_dir / "parsed_result.json", spec_result)
        round_record: dict[str, Any] = {
            "round": round_index,
            "spec_agent_exit_code": spec_exit,
            "spec_agent_error": spec_error,
            "spec_result": spec_result,
        }
        rounds.append(round_record)
        final_spec_result = spec_result
        newly_invalid_tests = invalid_test_names_from_result(spec_result)
        invalid_test_names.update(newly_invalid_tests)
        round_record["new_invalid_test_names"] = newly_invalid_tests
        round_record["invalid_test_names"] = sorted(invalid_test_names)

        if spec_exit != 0 or not spec_result or spec_result.get("cli_status") != "synthesized":
            round_record["stop_reason"] = "spec_agent_not_synthesized"
            break

        spectra_file = extract_path_value(spec_result.get("spectra_file"))
        controller_output_dir = extract_path_value(spec_result.get("controller_output_dir"))
        if spectra_file is None or controller_output_dir is None:
            round_record["stop_reason"] = "missing_spec_artifact_path"
            break
        controller_dir = controller_output_dir / "jit" if controller_output_dir.name != "jit" else controller_output_dir
        spec_name = str(signature.get("spec_name") or infer_spec_name(spectra_file) or spectra_file.stem)
        test_dir = round_dir / "test-writer"
        test_prompt = build_test_prompt(
            skill=args.test_skill,
            run_dir=test_dir,
            natural_language=natural_language,
            signature_json=signature_json,
            spec_name=spec_name,
            spectra_file=spectra_file,
            controller_dir=controller_dir,
            output_dir=test_dir,
        )
        test_exit, test_result, test_error = run_agent(
            command_template=args.agent_command,
            prompt=test_prompt,
            prompt_file=test_dir / "agent_prompt.txt",
            stdout_file=test_dir / "agent_stdout.txt",
            stderr_file=test_dir / "agent_stderr.txt",
            timeout=args.timeout,
        )
        if test_result:
            write_json(test_dir / "parsed_result.json", test_result)
        round_record.update(
            {
                "test_agent_exit_code": test_exit,
                "test_agent_error": test_error,
                "test_result": test_result,
            }
        )
        if test_exit != 0 or not test_result or not test_result.get("test_plan_file"):
            round_record["stop_reason"] = "test_agent_failed"
            break

        rtest_file = extract_path_value(test_result.get("test_plan_file"))
        if rtest_file is None:
            round_record["stop_reason"] = "missing_test_plan_path"
            break
        compiled_file = test_dir / "test-plan.json"
        compile_result = compile_test_plan(rtest_file, compiled_file)
        write_text(test_dir / "compile.stdout.txt", compile_result.stdout)
        write_text(test_dir / "compile.stderr.txt", compile_result.stderr)
        round_record["compile_exit_code"] = compile_result.returncode
        if compile_result.returncode != 0:
            round_record["stop_reason"] = "test_plan_compile_failed"
            break

        compiled_test_plans.append((round_index, compiled_file))
        result_files: list[tuple[int, Path]] = []
        replay_records: list[dict[str, Any]] = []
        for source_round, source_plan in compiled_test_plans:
            replay_plan = test_dir / f"replay-plan-round-{source_round:02d}.json"
            replay_result = test_dir / f"test-results-round-{source_round:02d}.json"
            rebind_test_plan(
                source_plan,
                replay_plan,
                spec_name=spec_name,
                spectra_file=spectra_file,
                controller_dir=controller_dir,
            )
            run_result = run_controller_tests(replay_plan, replay_result)
            write_text(test_dir / f"test-run-round-{source_round:02d}.stdout.txt", run_result.stdout)
            write_text(test_dir / f"test-run-round-{source_round:02d}.stderr.txt", run_result.stderr)
            plan_total, plan_passed, plan_failed = test_counts(replay_result)
            result_files.append((source_round, replay_result))
            replay_records.append(
                {
                    "source_test_round": source_round,
                    "plan_file": str(replay_plan),
                    "result_file": str(replay_result),
                    "exit_code": run_result.returncode,
                    "tests_total": plan_total,
                    "tests_passed": plan_passed,
                    "tests_failed": plan_failed,
                }
            )

        result_file = test_dir / "test-results-aggregate.json"
        tests_total, tests_passed, tests_failed, invalid_tests_filtered = aggregate_test_results(
            result_files,
            result_file,
            invalid_test_names,
        )
        round_record.update(
            {
                "test_result_file": str(result_file),
                "replayed_test_plans": replay_records,
                "tests_total": tests_total,
                "tests_passed": tests_passed,
                "tests_failed": tests_failed,
                "invalid_tests_filtered": invalid_tests_filtered,
            }
        )

        previous_spectra_file = spectra_file
        previous_test_result_file = result_file
        if tests_failed == 0:
            round_record["stop_reason"] = "tests_passed"
            break
        if round_index >= args.max_feedback_rounds:
            round_record["stop_reason"] = "max_feedback_rounds_reached"
            break

    summary_status = summarize_status(rounds, final_spec_result)
    summary = {
        "status": summary_status,
        "run_id": run_id,
        "run_dir": str(run_dir),
        "run_started_at": started_at,
        "run_finished_at": utc_now(),
        "duration_ms": int((time.perf_counter() - started) * 1000),
        "description_file": str(description_file),
        "signature_file": str(signature_file),
        "spec_skill": args.spec_skill,
        "test_skill": args.test_skill,
        "max_feedback_rounds": args.max_feedback_rounds,
        "invalid_test_names": sorted(invalid_test_names),
        "rounds": rounds,
        "final_spec_result": final_spec_result,
    }
    write_json(run_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] in {"tests_passed", "invalid_tests_rejected", "max_rounds_with_failures"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
