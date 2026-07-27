#!/usr/bin/env python3
"""Interactive wizard for ReSpect user-study conditions B and C.

The wizard keeps the participant-facing workflow simple: inspect/edit a file,
press Enter, then continue. It starts fresh Codex skill processes for proposal
phases and stores all prompts, outputs, review files, and command results in a
single run directory.
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
DEFAULT_OUTPUT_DIR = REPO_ROOT / "experiments" / "user_study_runs"
DEFAULT_SPEC_SKILL = "respect-interactive-spec"
DEFAULT_SPEC_TESTER_SKILL = "respect-interactive-spec-tester"
DEFAULT_TEST_SKILL = "respect-interactive-test-writer"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("description_file", nargs="?", help="Natural-language task file.")
    parser.add_argument(
        "--tests",
        action="store_true",
        help="Enable the additional TestDSL skill and test-feedback repair phase.",
    )
    parsed = parser.parse_args()

    description_path = choose_description_file(parsed.description_file)
    use_tests = parsed.tests if parsed.description_file else ask_yes_no("Use TestDSL support for this task?", default=False)
    task_id = safe_path_part(description_path.stem)
    parsed.participant = "study"
    parsed.task = task_id
    parsed.condition = "spec-skill-tests" if use_tests else "spec-skill"
    parsed.signature_file = infer_signature_file(description_path)
    parsed.output_dir = str(DEFAULT_OUTPUT_DIR)
    parsed.run_id = None
    parsed.spec_skill = DEFAULT_SPEC_TESTER_SKILL if use_tests else DEFAULT_SPEC_SKILL
    parsed.test_skill = DEFAULT_TEST_SKILL
    parsed.agent_command = DEFAULT_AGENT_COMMAND
    parsed.timeout = 1800.0
    parsed.max_feedback_rounds = 1
    parsed.non_interactive = False
    parsed.dry_run = False
    parsed.description_file = str(description_path)
    parsed.tests = use_tests
    return parsed


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_repo_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return (REPO_ROOT / path).resolve()


def safe_path_part(value: str, max_length: int = 80) -> str:
    safe = re.sub(r"[^A-Za-z0-9._=-]+", "_", value).strip("_")
    return (safe or "value")[:max_length]


def ask_yes_no(question: str, *, default: bool) -> bool:
    suffix = "Y/n" if default else "y/N"
    while True:
        answer = input(f"{question} [{suffix}] ").strip().lower()
        if not answer:
            return default
        if answer in {"y", "yes", "j", "ja"}:
            return True
        if answer in {"n", "no", "nein"}:
            return False
        print("Please answer yes or no.")


def choose_description_file(argument_value: str | None) -> Path:
    if argument_value:
        return resolve_repo_path(argument_value)

    tasks_dir = REPO_ROOT / "user_study" / "tasks"
    task_files = sorted(tasks_dir.glob("*.txt")) if tasks_dir.is_dir() else []
    if task_files:
        print("Available tasks:")
        for index, path in enumerate(task_files, start=1):
            print(f"  {index}. {path.relative_to(REPO_ROOT)}")
        print("  n. Create a new task from text input")
        while True:
            answer = input("Select a task number or enter a path: ").strip()
            if answer.lower() in {"n", "new", "neu"}:
                return create_ad_hoc_task()
            if re.fullmatch(r"\d+", answer):
                selected = int(answer)
                if 1 <= selected <= len(task_files):
                    return task_files[selected - 1].resolve()
            if answer:
                return resolve_repo_path(answer)
            print("Please select a task number or enter a path.")

    while True:
        answer = input("No tasks found. Create a new task from text input? [Y/n] ").strip().lower()
        if answer in {"", "y", "yes", "j", "ja"}:
            return create_ad_hoc_task()
        if answer in {"n", "no", "nein"}:
            path_answer = input("Path to the natural-language task file: ").strip().strip('"')
            if path_answer:
                return resolve_repo_path(path_answer)
        print("Please choose text input or enter a task file path.")


def create_ad_hoc_task() -> Path:
    title = input("Task name (optional): ").strip()
    slug_source = title or datetime.now(timezone.utc).strftime("task_%Y%m%dT%H%M%SZ")
    task_id = safe_path_part(slug_source)
    task_dir = REPO_ROOT / "user_study" / "ad_hoc_tasks"
    task_file = task_dir / f"{task_id}.txt"

    print("Enter the natural-language requirements. Finish with a line containing only END.")
    lines: list[str] = []
    while True:
        line = input()
        if line.strip() == "END":
            break
        lines.append(line)

    text = "\n".join(lines).strip() + "\n"
    if not text.strip():
        raise SystemExit("No task text was entered.")
    write_text(task_file, text)
    print(f"Saved task to: {task_file}")
    return task_file.resolve()


def infer_signature_file(description_file: Path) -> Path | None:
    candidates = [
        description_file.with_suffix(".signature.json"),
        description_file.with_suffix(".json"),
        description_file.parent / "signature.json",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def write_text(path: Path, content: str | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content or "", encoding="utf-8")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def copy_if_exists(source: Path, destination: Path) -> bool:
    if not source.is_file():
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return True


def normalize_result_value(value: str) -> Any:
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
    decoder = json.JSONDecoder()
    for start in range(len(text) - 1, -1, -1):
        if text[start] != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(text[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def extract_key_value_result(text: str) -> dict[str, Any] | None:
    result: dict[str, Any] = {}
    for line in text.splitlines():
        match = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*?)\s*$", line)
        if match:
            result[match.group(1)] = normalize_result_value(match.group(2))
    return result or None


def extract_agent_result(text: str) -> dict[str, Any] | None:
    return extract_last_json_object(text) or extract_key_value_result(text)


def extract_path_value(value: Any) -> Path | None:
    if value is None:
        return None
    text = str(value).strip()
    markdown_match = re.match(r"^\[[^\]]+\]\(([^)]+)\)$", text)
    if markdown_match:
        text = markdown_match.group(1)
    text = text.strip().strip("`").strip("\"'")
    if text.lower() in {"", "none", "null"}:
        return None
    return resolve_repo_path(text)


def build_command(agent_command: str, prompt_file: Path) -> tuple[str, bool]:
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
    dry_run: bool,
) -> tuple[int | None, dict[str, Any] | None, str | None]:
    write_text(prompt_file, prompt)
    if dry_run:
        write_text(stdout_file, "")
        write_text(stderr_file, "dry run: agent not started\n")
        return 0, {"status": "dry_run", "prompt_file": str(prompt_file)}, None

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


def prompt_review(message: str, files: list[Path], *, non_interactive: bool) -> None:
    print("\n" + message)
    for path in files:
        print(f"  {path}")
    if non_interactive:
        print("Non-interactive mode: continuing.")
        return
    input("Review/edit the file(s), then press Enter to continue...")


def signature_names(signature: dict[str, Any], key: str) -> list[str]:
    names: list[str] = []
    for item in signature.get(key) or []:
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict) and isinstance(item.get("name"), str):
            names.append(item["name"])
    return names


def infer_spec_name(spectra_file: Path) -> str | None:
    if not spectra_file.is_file():
        return None
    match = re.search(r"^\s*spec\s+([A-Za-z_][A-Za-z0-9_]*)", spectra_file.read_text(encoding="utf-8"), re.MULTILINE)
    return match.group(1) if match else None


def build_controller_tests(dry_run: bool) -> subprocess.CompletedProcess[str]:
    if dry_run:
        return subprocess.CompletedProcess(args=["javac"], returncode=0, stdout="", stderr="dry run\n")
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


def compile_test_plan(rtest_file: Path, json_file: Path, dry_run: bool) -> subprocess.CompletedProcess[str]:
    if dry_run:
        return subprocess.CompletedProcess(args=["compile_test_plan"], returncode=0, stdout="", stderr="dry run\n")
    return subprocess.run(
        [sys.executable, "controller_tests/compile_test_plan.py", str(rtest_file), "-o", str(json_file)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def run_controller_tests(plan_file: Path, result_file: Path, dry_run: bool) -> subprocess.CompletedProcess[str]:
    if dry_run:
        write_json(result_file, {"results": []})
        return subprocess.CompletedProcess(args=["TestRunner"], returncode=0, stdout="", stderr="dry run\n")
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
    plan = load_json(source_plan)
    plan["spec_name"] = spec_name
    plan["spectra_file"] = str(spectra_file)
    plan["controller_dir"] = str(controller_dir)
    write_json(target_plan, plan)


def test_counts(result_file: Path) -> tuple[int, int, int]:
    if not result_file.is_file():
        return 0, 0, 0
    payload = load_json(result_file)
    tests = payload.get("results") or payload.get("tests") or []
    total = len(tests)
    passed = sum(1 for item in tests if item.get("passed") is True)
    return total, passed, total - passed


def phase_prompt_header(skill: str, phase: str, run_dir: Path) -> str:
    return f"""Use ${skill}.

User-study interactive mode.
Phase: {phase}
Run directory: {run_dir}

Follow only the requested phase. Save every requested file exactly at the path
given in this prompt. The participant will review/edit files after this agent
process exits.
"""


def build_setup_prompt(skill: str, run_dir: Path, natural_language: str, signature_file: Path | None) -> str:
    initial_signature = "No starting signature file was provided."
    if signature_file:
        initial_signature = f"Starting signature file: {signature_file}\n\n```json\n{signature_file.read_text(encoding='utf-8')}\n```"
    return f"""{phase_prompt_header(skill, "setup", run_dir)}

Required output files:
- signature proposal: {run_dir / "signature.proposed.json"}
- decomposition proposal: {run_dir / "decomposition.proposed.md"}

{initial_signature}

Natural-language requirements:

{natural_language}
"""


def build_draft_prompt(skill: str, run_dir: Path, natural_language: str, signature_file: Path, decomposition_file: Path) -> str:
    return f"""{phase_prompt_header(skill, "draft", run_dir)}

Reviewed signature file: {signature_file}
Reviewed decomposition file: {decomposition_file}
Required Spectra proposal file: {run_dir / "spec.proposed.spectra"}

Natural-language requirements:

{natural_language}
"""


def build_validate_prompt(skill: str, run_dir: Path, natural_language: str, spectra_file: Path, round_index: int) -> str:
    artifact_dir = run_dir / f"spec-validation-round-{round_index:02d}"
    return f"""{phase_prompt_header(skill, "validate_and_synthesize", artifact_dir)}

Participant-reviewed Spectra file: {spectra_file}
Required final Spectra file: {artifact_dir / "final.spectra"}
Required repair notes file: {artifact_dir / "repair_notes.md"}

Natural-language requirements:

{natural_language}
"""


def build_test_prompt(
    *,
    skill: str,
    run_dir: Path,
    natural_language: str,
    signature_file: Path,
    spec_name: str,
    spectra_file: Path,
    controller_dir: Path,
) -> str:
    test_dir = run_dir / "tests"
    return f"""{phase_prompt_header(skill, "test_plan_proposal", test_dir)}

Required proposed TestDSL file: {test_dir / "test-plan.proposed.rtest"}
Reviewed signature file: {signature_file}

Controller metadata:
- spec_name: {spec_name}
- controller_dir: {controller_dir}
- spectra_file: {spectra_file}

Do not open or inspect the generated Spectra file. Use spectra_file only as a
top-level DSL path.

Natural-language requirements:

{natural_language}
"""


def build_feedback_prompt(
    *,
    skill: str,
    run_dir: Path,
    natural_language: str,
    spectra_file: Path,
    test_result_file: Path,
    round_index: int,
) -> str:
    artifact_dir = run_dir / f"test-feedback-repair-round-{round_index:02d}"
    return f"""{phase_prompt_header(skill, "test_feedback_repair", artifact_dir)}

Current generated Spectra file: {spectra_file}
Independent reviewed test result file: {test_result_file}
Required repair proposal file: {run_dir / f"spec.repair_proposed_{round_index:02d}.spectra"}
Required final Spectra file after validation/synthesis: {artifact_dir / "final.spectra"}

Natural-language requirements:

{natural_language}
"""


def run_skill_phase(
    *,
    phase_name: str,
    prompt: str,
    phase_dir: Path,
    args: argparse.Namespace,
    timeline: Path,
) -> dict[str, Any] | None:
    print(f"\nRunning {phase_name}...")
    started = time.perf_counter()
    exit_code, result, error = run_agent(
        command_template=args.agent_command,
        prompt=prompt,
        prompt_file=phase_dir / "agent_prompt.txt",
        stdout_file=phase_dir / "agent_stdout.txt",
        stderr_file=phase_dir / "agent_stderr.txt",
        timeout=args.timeout,
        dry_run=args.dry_run,
    )
    record = {
        "event": "skill_phase",
        "phase": phase_name,
        "time": utc_now(),
        "duration_ms": int((time.perf_counter() - started) * 1000),
        "exit_code": exit_code,
        "error": error,
        "result": result,
    }
    append_jsonl(timeline, record)
    write_json(phase_dir / "parsed_result.json", result or {})
    if exit_code not in {0, None}:
        print(f"Warning: {phase_name} exited with code {exit_code}. Check {phase_dir / 'agent_stderr.txt'}.")
    if error:
        print(f"Warning: {error}")
    return result


def main() -> int:
    args = parse_args()
    description_file = resolve_repo_path(args.description_file)
    if not description_file.is_file():
        print(f"Description file not found: {description_file}", file=sys.stderr)
        return 2
    signature_file = resolve_repo_path(args.signature_file) if args.signature_file else None
    if signature_file and not signature_file.is_file():
        print(f"Signature file not found: {signature_file}", file=sys.stderr)
        return 2

    natural_language = description_file.read_text(encoding="utf-8")
    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = (
        resolve_repo_path(args.output_dir)
        / safe_path_part(args.participant)
        / safe_path_part(args.task)
        / safe_path_part(args.condition)
        / safe_path_part(run_id)
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    timeline = run_dir / "timeline.jsonl"

    write_text(run_dir / "input_description.txt", natural_language)
    write_json(
        run_dir / "run_config.json",
        {
            "participant": args.participant,
            "task": args.task,
            "condition": args.condition,
            "description_file": str(description_file),
            "signature_file": str(signature_file) if signature_file else None,
            "spec_skill": args.spec_skill,
            "test_skill": args.test_skill if args.condition == "spec-skill-tests" else None,
            "started_at": utc_now(),
            "dry_run": args.dry_run,
        },
    )

    print(f"Run directory:\n  {run_dir}")
    print(f"Condition: {args.condition}")

    setup_dir = run_dir / "phase-01-setup"
    run_skill_phase(
        phase_name="setup",
        prompt=build_setup_prompt(args.spec_skill, run_dir, natural_language, signature_file),
        phase_dir=setup_dir,
        args=args,
        timeline=timeline,
    )
    proposed_signature = run_dir / "signature.proposed.json"
    reviewed_signature = run_dir / "signature.reviewed.json"
    proposed_decomposition = run_dir / "decomposition.proposed.md"
    reviewed_decomposition = run_dir / "decomposition.reviewed.md"
    if not copy_if_exists(proposed_signature, reviewed_signature) and signature_file:
        shutil.copy2(signature_file, reviewed_signature)
    if not reviewed_signature.is_file():
        write_json(reviewed_signature, {"spec_name": args.task, "environment": [], "system": []})
    if not copy_if_exists(proposed_decomposition, reviewed_decomposition):
        write_text(reviewed_decomposition, "# Reviewed Decomposition\n\n")
    prompt_review("Step 1: review the signature and requirement decomposition.", [reviewed_signature, reviewed_decomposition], non_interactive=args.non_interactive)
    append_jsonl(timeline, {"event": "participant_review_complete", "phase": "setup", "time": utc_now()})

    draft_dir = run_dir / "phase-02-draft"
    run_skill_phase(
        phase_name="draft",
        prompt=build_draft_prompt(args.spec_skill, run_dir, natural_language, reviewed_signature, reviewed_decomposition),
        phase_dir=draft_dir,
        args=args,
        timeline=timeline,
    )
    proposed_spec = run_dir / "spec.proposed.spectra"
    reviewed_spec = run_dir / "spec.reviewed.spectra"
    if not copy_if_exists(proposed_spec, reviewed_spec):
        write_text(reviewed_spec, f"spec {safe_path_part(args.task).replace('-', '_')}\n")
    prompt_review("Step 2: review/edit the proposed Spectra draft.", [reviewed_spec], non_interactive=args.non_interactive)
    append_jsonl(timeline, {"event": "participant_review_complete", "phase": "draft", "time": utc_now()})

    validate_dir = run_dir / "phase-03-validate"
    spec_result = run_skill_phase(
        phase_name="validate_and_synthesize",
        prompt=build_validate_prompt(args.spec_skill, run_dir, natural_language, reviewed_spec, 0),
        phase_dir=validate_dir,
        args=args,
        timeline=timeline,
    )
    final_spec = extract_path_value(spec_result.get("spectra_file") if spec_result else None) if spec_result else None
    if final_spec is None:
        final_spec = run_dir / "spec-validation-round-00" / "final.spectra"
    if final_spec.is_file():
        shutil.copy2(final_spec, run_dir / "final.spectra")
        final_spec = run_dir / "final.spectra"
    prompt_review("Step 3: inspect validation/synthesis output and final Spectra.", [run_dir / "final.spectra", run_dir / "spec-validation-round-00" / "repair_notes.md"], non_interactive=args.non_interactive)

    tests_total = tests_passed = tests_failed = 0
    test_result_file: Path | None = None
    if args.condition == "spec-skill-tests":
        if not final_spec.is_file():
            print("Cannot run TestDSL phase because no final Spectra file exists.", file=sys.stderr)
        else:
            signature = load_json(reviewed_signature)
            controller_output_dir = extract_path_value(spec_result.get("controller_output_dir") if spec_result else None)
            controller_dir = controller_output_dir / "jit" if controller_output_dir and controller_output_dir.name != "jit" else controller_output_dir
            spec_name = str(signature.get("spec_name") or infer_spec_name(final_spec) or final_spec.stem)
            if controller_dir is None:
                print("Cannot run TestDSL phase because no controller_output_dir was reported.", file=sys.stderr)
            else:
                tests_dir = run_dir / "tests"
                test_agent_dir = run_dir / "phase-04-test-proposal"
                run_skill_phase(
                    phase_name="test_plan_proposal",
                    prompt=build_test_prompt(
                        skill=args.test_skill,
                        run_dir=run_dir,
                        natural_language=natural_language,
                        signature_file=reviewed_signature,
                        spec_name=spec_name,
                        spectra_file=final_spec,
                        controller_dir=controller_dir,
                    ),
                    phase_dir=test_agent_dir,
                    args=args,
                    timeline=timeline,
                )
                proposed_plan = tests_dir / "test-plan.proposed.rtest"
                reviewed_plan = tests_dir / "test-plan.reviewed.rtest"
                if not copy_if_exists(proposed_plan, reviewed_plan):
                    write_text(reviewed_plan, "")
                prompt_review("Step 4: review/edit the proposed TestDSL plan.", [reviewed_plan], non_interactive=args.non_interactive)
                append_jsonl(timeline, {"event": "participant_review_complete", "phase": "test_plan", "time": utc_now()})

                build_result = build_controller_tests(args.dry_run)
                write_text(tests_dir / "build_controller_tests.stdout.txt", build_result.stdout)
                write_text(tests_dir / "build_controller_tests.stderr.txt", build_result.stderr)
                compiled_plan = tests_dir / "test-plan.final.json"
                final_plan = tests_dir / "test-plan.final.rtest"
                shutil.copy2(reviewed_plan, final_plan)
                compile_result = compile_test_plan(final_plan, compiled_plan, args.dry_run)
                write_text(tests_dir / "compile.stdout.txt", compile_result.stdout)
                write_text(tests_dir / "compile.stderr.txt", compile_result.stderr)
                if build_result.returncode == 0 and compile_result.returncode == 0:
                    test_result_file = tests_dir / "test-results.json"
                    run_result = run_controller_tests(compiled_plan, test_result_file, args.dry_run)
                    write_text(tests_dir / "test-run.stdout.txt", run_result.stdout)
                    write_text(tests_dir / "test-run.stderr.txt", run_result.stderr)
                    tests_total, tests_passed, tests_failed = test_counts(test_result_file)
                    print(f"Tests: total={tests_total}, passed={tests_passed}, failed={tests_failed}")
                else:
                    print("Test build or DSL compilation failed. Check the tests directory.")

                for round_index in range(1, args.max_feedback_rounds + 1):
                    if not test_result_file or tests_failed == 0:
                        break
                    feedback_dir = run_dir / f"phase-05-test-feedback-round-{round_index:02d}"
                    repair_result = run_skill_phase(
                        phase_name=f"test_feedback_repair_{round_index:02d}",
                        prompt=build_feedback_prompt(
                            skill=args.spec_skill,
                            run_dir=run_dir,
                            natural_language=natural_language,
                            spectra_file=final_spec,
                            test_result_file=test_result_file,
                            round_index=round_index,
                        ),
                        phase_dir=feedback_dir,
                        args=args,
                        timeline=timeline,
                    )
                    repair_proposal = run_dir / f"spec.repair_proposed_{round_index:02d}.spectra"
                    if repair_proposal.is_file():
                        shutil.copy2(repair_proposal, reviewed_spec)
                    prompt_review("Step 5: review/edit the test-feedback repair proposal.", [reviewed_spec], non_interactive=args.non_interactive)
                    spec_result = run_skill_phase(
                        phase_name=f"validate_after_test_feedback_{round_index:02d}",
                        prompt=build_validate_prompt(args.spec_skill, run_dir, natural_language, reviewed_spec, round_index),
                        phase_dir=run_dir / f"phase-06-validate-round-{round_index:02d}",
                        args=args,
                        timeline=timeline,
                    )
                    final_spec = extract_path_value(spec_result.get("spectra_file") if spec_result else None) if spec_result else final_spec
                    if final_spec and final_spec.is_file():
                        shutil.copy2(final_spec, run_dir / "final.spectra")
                        final_spec = run_dir / "final.spectra"
                    controller_output_dir = extract_path_value(spec_result.get("controller_output_dir") if spec_result else None)
                    controller_dir = controller_output_dir / "jit" if controller_output_dir and controller_output_dir.name != "jit" else controller_output_dir
                    if controller_dir is None:
                        break
                    test_result_file = tests_dir / f"test-results-round-{round_index:02d}.json"
                    replay_plan = tests_dir / f"replay-plan-round-{round_index:02d}.json"
                    rebind_test_plan(
                        compiled_plan,
                        replay_plan,
                        spec_name=spec_name,
                        spectra_file=final_spec,
                        controller_dir=controller_dir,
                    )
                    run_result = run_controller_tests(replay_plan, test_result_file, args.dry_run)
                    write_text(tests_dir / f"test-run-round-{round_index:02d}.stdout.txt", run_result.stdout)
                    write_text(tests_dir / f"test-run-round-{round_index:02d}.stderr.txt", run_result.stderr)
                    tests_total, tests_passed, tests_failed = test_counts(test_result_file)
                    print(f"Retests: total={tests_total}, passed={tests_passed}, failed={tests_failed}")

    summary = {
        "status": "completed",
        "participant": args.participant,
        "task": args.task,
        "condition": args.condition,
        "run_dir": str(run_dir),
        "final_spectra_file": str(run_dir / "final.spectra") if (run_dir / "final.spectra").is_file() else None,
        "spec_result": spec_result,
        "test_result_file": str(test_result_file) if test_result_file else None,
        "tests_total": tests_total,
        "tests_passed": tests_passed,
        "tests_failed": tests_failed,
        "finished_at": utc_now(),
    }
    write_json(run_dir / "summary.json", summary)
    print("\nDone.")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
