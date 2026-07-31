#!/usr/bin/env python3
"""Run branched NL-to-Spectra reconstruction experiments.

The runner creates one shared core reconstruction per NL description and then
starts comparable feedback branches from the same core Spectra.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DESCRIPTIONS_MANIFEST = "dataset/nl_descriptions/descriptions.jsonl"
DEFAULT_OUTPUT_DIR = "experiments/branched_runs"
DEFAULT_AGENT_COMMAND = "codex --ask-for-approval never exec --ephemeral --sandbox danger-full-access -"
DEFAULT_CORE_SKILL = "respect-core"
DEFAULT_SELF_TEST_SKILL = "respect-self-test-from-core"
DEFAULT_SPEC_REPAIR_SKILL = "respect-spec-tester"
DEFAULT_TEST_WRITER_SKILL = "respect-test-writer"
DEFAULT_CROSS_INCUMBENT_SKILL = "respect-broker-from-core"
DEFAULT_CROSS_CHALLENGER_SKILL = "respect-broker"
DEFAULT_CROSS_RUNNER = "experiments/cross_repair_from_core.py"
DEFAULT_BRANCHES = ("no_test", "self_test", "independent_test", "cross_repair")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--descriptions-manifest", default=DEFAULT_DESCRIPTIONS_MANIFEST)
    parser.add_argument("--signature-root", required=True)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--agent-command", default=DEFAULT_AGENT_COMMAND)
    parser.add_argument("--agent-model", default=None)
    parser.add_argument("--core-skill", default=DEFAULT_CORE_SKILL)
    parser.add_argument("--self-test-skill", default=DEFAULT_SELF_TEST_SKILL)
    parser.add_argument("--spec-repair-skill", default=DEFAULT_SPEC_REPAIR_SKILL)
    parser.add_argument("--test-writer-skill", default=DEFAULT_TEST_WRITER_SKILL)
    parser.add_argument("--cross-incumbent-skill", default=DEFAULT_CROSS_INCUMBENT_SKILL)
    parser.add_argument("--cross-challenger-skill", default=DEFAULT_CROSS_CHALLENGER_SKILL)
    parser.add_argument("--cross-runner", default=DEFAULT_CROSS_RUNNER)
    parser.add_argument("--broker-timeout", type=float, default=600.0)
    parser.add_argument("--branches", nargs="+", choices=DEFAULT_BRANCHES, default=list(DEFAULT_BRANCHES))
    parser.add_argument("--timeout", type=float, default=1800.0)
    parser.add_argument("--max-feedback-rounds", type=int, default=3)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_repo_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return (REPO_ROOT / path).resolve()


def repo_relative_path(path: str | Path | None) -> str | None:
    if path is None:
        return None
    resolved = Path(path).resolve()
    try:
        return str(resolved.relative_to(REPO_ROOT))
    except ValueError:
        return str(resolved)


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
    return Path(*[safe_path_part(part) for part in relative_parts]).with_suffix("")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not path.is_file():
        return records
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return records


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def write_text(path: Path, content: str | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content or "", encoding="utf-8")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def signature_file_for(record: dict[str, Any], signature_root: Path) -> Path:
    if record.get("signature_file"):
        return resolve_repo_path(record["signature_file"])
    candidates: list[Path] = []
    if record.get("description_id"):
        candidates.append(signature_root / f"{safe_path_part(str(record['description_id']))}.json")
    if record.get("dataset_id"):
        candidates.append(signature_root / f"{safe_path_part(str(record['dataset_id']))}.json")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0] if candidates else signature_root / "missing.json"


def run_key(record: dict[str, Any], args: argparse.Namespace, signature_file: Path) -> str:
    signature_hash = sha256_text(signature_file.read_text(encoding="utf-8")) if signature_file.is_file() else None
    return sha256_text(
        json.dumps(
            {
                "agent_command": args.agent_command,
                "agent_model": args.agent_model,
                "broker_timeout": args.broker_timeout,
                "branches": args.branches,
                "core_skill": args.core_skill,
                "cross_challenger_skill": args.cross_challenger_skill,
                "cross_incumbent_skill": args.cross_incumbent_skill,
                "cross_runner": args.cross_runner,
                "description_id": record.get("description_id"),
                "description_response_sha256": record.get("response_sha256"),
                "max_feedback_rounds": args.max_feedback_rounds,
                "prompt_version": "branched_reconstruction_v1",
                "self_test_skill": args.self_test_skill,
                "signature_file": str(signature_file),
                "signature_sha256": signature_hash,
                "spec_repair_skill": args.spec_repair_skill,
                "test_writer_skill": args.test_writer_skill,
                "timeout": args.timeout,
            },
            sort_keys=True,
        )
    )


def completed_run_keys(runs_manifest: Path) -> set[str]:
    completed = {"success", "partial_success"}
    return {
        record["run_key"]
        for record in load_jsonl(runs_manifest)
        if record.get("status") in completed and record.get("run_key")
    }


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
    agent_command: str,
    prompt: str,
    prompt_file: Path,
    stdout_file: Path,
    stderr_file: Path,
    timeout: float,
) -> tuple[int | None, dict[str, Any] | None, str | None]:
    write_text(prompt_file, prompt)
    command, pass_prompt_on_stdin = build_command(agent_command, prompt_file)
    try:
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            input=prompt if pass_prompt_on_stdin else None,
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


def archive_skill_artifacts(parsed_result: dict[str, Any] | None, destination_dir: Path) -> dict[str, Any]:
    archived = {
        "artifact_dir": None,
        "broker_feedback_files": [],
        "diagnostic_files": [],
        "repair_log_file": None,
        "intermediate_spectra_files": {},
        "test_files": [],
        "spectra_file": None,
        "controller_output_dir": None,
        "core_context_full_file": None,
        "core_context_test_writer_file": None,
    }
    if not parsed_result:
        return archived

    source_artifact_dir = extract_path_value(parsed_result.get("artifact_dir"))
    if source_artifact_dir and source_artifact_dir.is_dir():
        target_artifact_dir = destination_dir / "skill_artifacts"
        source_specs_dir = source_artifact_dir / "specs"
        if source_specs_dir.is_dir():
            for source_spec in sorted(source_specs_dir.glob("*.spectra")):
                target = target_artifact_dir / "specs" / source_spec.name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_spec, target)
                archived["intermediate_spectra_files"][source_spec.stem] = repo_relative_path(target)

        for name, key in (
            ("final.spectra", "spectra_file"),
            ("repair_log.jsonl", "repair_log_file"),
            ("core_context.full.json", "core_context_full_file"),
            ("core_context.test_writer.json", "core_context_test_writer_file"),
        ):
            source = source_artifact_dir / name
            if source.is_file():
                target = target_artifact_dir / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                archived[key] = repo_relative_path(target)
        if any(archived[key] for key in ("spectra_file", "repair_log_file", "core_context_full_file", "core_context_test_writer_file")):
            archived["artifact_dir"] = repo_relative_path(target_artifact_dir)

        for dirname, archive_key in (
            ("diagnostics", "diagnostic_files"),
            ("broker", "broker_feedback_files"),
            ("tests", "test_files"),
        ):
            source_dir = source_artifact_dir / dirname
            if source_dir.is_dir():
                target_dir = target_artifact_dir / dirname
                shutil.copytree(source_dir, target_dir, dirs_exist_ok=True)
                archived[archive_key] = [
                    repo_relative_path(path)
                    for path in sorted(target_dir.rglob("*"))
                    if path.is_file()
                ]
                archived["artifact_dir"] = repo_relative_path(target_artifact_dir)

    reported_spectra = extract_path_value(parsed_result.get("spectra_file"))
    if archived["spectra_file"] is None and reported_spectra and reported_spectra.is_file():
        target = destination_dir / "final.spectra"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(reported_spectra, target)
        archived["spectra_file"] = repo_relative_path(target)
        archived["intermediate_spectra_files"]["final"] = archived["spectra_file"]

    for reported_key, archive_key, filename in (
        ("core_context_full_file", "core_context_full_file", "core_context.full.json"),
        ("core_context_test_writer_file", "core_context_test_writer_file", "core_context.test_writer.json"),
    ):
        reported_path = extract_path_value(parsed_result.get(reported_key))
        if archived[archive_key] is None and reported_path and reported_path.is_file():
            target = destination_dir / "skill_artifacts" / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(reported_path, target)
            archived[archive_key] = repo_relative_path(target)
            archived["artifact_dir"] = archived["artifact_dir"] or repo_relative_path(target.parent)

    reported_controller = extract_path_value(parsed_result.get("controller_output_dir"))
    archived["controller_output_dir"] = repo_relative_path(reported_controller) if reported_controller else None
    if archived["spectra_file"]:
        archived["intermediate_spectra_files"].setdefault("final", archived["spectra_file"])
    return archived


def signature_names(signature: dict[str, Any], key: str) -> list[str]:
    names: list[str] = []
    for item in signature.get(key) or []:
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict) and isinstance(item.get("name"), str):
            names.append(item["name"])
    return names


def infer_spec_name(spectra_file: Path | None, signature: dict[str, Any]) -> str:
    if signature.get("spec_name"):
        return str(signature["spec_name"])
    if spectra_file and spectra_file.is_file():
        match = re.search(r"^\s*spec\s+([A-Za-z_][A-Za-z0-9_]*)", spectra_file.read_text(encoding="utf-8"), re.MULTILINE)
        if match:
            return match.group(1)
    return spectra_file.stem if spectra_file else "GeneratedSpec"


def controller_jit_dir(controller_output_dir: Path | None) -> Path | None:
    if controller_output_dir is None:
        return None
    return controller_output_dir if controller_output_dir.name == "jit" else controller_output_dir / "jit"


def build_core_prompt(skill: str, run_dir: Path, natural_language: str, signature_json: str) -> str:
    return f"""Use ${skill}.

Run directory: {run_dir}

Fixed env/sys signature JSON:

```json
{signature_json}
```

Generate the shared core reconstruction. Stop after successful synthesis and
write both core context files.

Natural-language requirements:

{natural_language}
"""


def build_self_test_prompt(
    *,
    skill: str,
    run_dir: Path,
    natural_language: str,
    signature_json: str,
    core_spectra_file: Path,
    core_context_file: Path | None,
    controller_output_dir: Path | None,
    max_feedback_rounds: int,
) -> str:
    return f"""Use ${skill}.

Run directory: {run_dir}
Maximum feedback rounds: {max_feedback_rounds}

Fixed env/sys signature JSON:

```json
{signature_json}
```

Core artifacts:
- core_final_spectra_file: {core_spectra_file}
- core_context_full_file: {core_context_file or "none"}
- core_controller_output_dir: {controller_output_dir or "none"}

Start from the core Spectra. Do not redraft from scratch.

Natural-language requirements:

{natural_language}
"""


def build_test_writer_prompt(
    *,
    skill: str,
    output_dir: Path,
    natural_language: str,
    signature_json: str,
    spec_name: str,
    spectra_file: Path,
    controller_dir: Path,
) -> str:
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
- Do not read core_context.full.json, repair logs, source Spectra, benchmark oracles, or distance results.
- Derive expected behavior only from the natural-language requirements and fixed signature.

Natural-language requirements:

{natural_language}
"""


def build_spec_repair_prompt(
    *,
    skill: str,
    run_dir: Path,
    natural_language: str,
    signature_json: str,
    core_spectra_file: Path,
    core_context_file: Path | None,
    test_result_file: Path,
    max_feedback_rounds: int,
    round_index: int,
) -> str:
    return f"""Use ${skill}.

Run directory: {run_dir}
Feedback round: {round_index} of {max_feedback_rounds}

Fixed env/sys signature JSON:

```json
{signature_json}
```

Start from this shared core generated Spectra file:
{core_spectra_file}

Full core context file:
{core_context_file or "none"}

Aggregated independent test result file:
{test_result_file}

Read the core Spectra, full core context when present, and aggregated test
results. Repair the Spectra only when a failing test is justified by the
natural-language requirements. After any Spectra edit, rerun validation,
well-separation, and synthesis. Do not write tests yourself.

Natural-language requirements:

{natural_language}
"""


def compile_test_plan(rtest_file: Path, json_file: Path) -> subprocess.CompletedProcess[str]:
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
    classpath_sep = ";" if sys.platform.startswith("win") else ":"
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


def process_no_test(core_artifacts: dict[str, Any], branch_dir: Path) -> dict[str, Any]:
    branch_dir.mkdir(parents=True, exist_ok=True)
    source = resolve_repo_path(core_artifacts["final_spectra_file"]) if core_artifacts.get("final_spectra_file") else None
    final_file = branch_dir / "final.spectra"
    intermediate: dict[str, str] = {}
    if source and source.is_file():
        shutil.copy2(source, final_file)
        intermediate["final"] = repo_relative_path(final_file) or str(final_file)
    return {
        "status": "success" if intermediate else "missing_core_spectra",
        "lineage": "no_test",
        "role": "baseline",
        "start_source": "core_final",
        "parent_spectra_file": core_artifacts.get("final_spectra_file"),
        "final_spectra_file": repo_relative_path(final_file) if final_file.is_file() else None,
        "intermediate_spectra_files": intermediate,
        "controller_output_dir": core_artifacts.get("controller_output_dir"),
    }


def process_agent_branch(
    *,
    branch: str,
    role: str,
    prompt: str,
    branch_dir: Path,
    args: argparse.Namespace,
    dry_run_status: str = "dry_run",
) -> dict[str, Any]:
    exit_code: int | None = None
    parsed_result: dict[str, Any] | None = None
    error: str | None = None
    if args.dry_run:
        write_text(branch_dir / "agent_prompt.txt", prompt)
        write_text(branch_dir / "agent_stdout.txt", "")
        write_text(branch_dir / "agent_stderr.txt", "")
        status = dry_run_status
    else:
        exit_code, parsed_result, error = run_agent(
            agent_command=args.agent_command,
            prompt=prompt,
            prompt_file=branch_dir / "agent_prompt.txt",
            stdout_file=branch_dir / "agent_stdout.txt",
            stderr_file=branch_dir / "agent_stderr.txt",
            timeout=args.timeout,
        )
        if parsed_result:
            write_json(branch_dir / "parsed_result.json", parsed_result)
        status = "success" if exit_code == 0 and parsed_result else "agent_error"
    artifacts = archive_skill_artifacts(parsed_result, branch_dir)
    return {
        "status": status,
        "lineage": branch,
        "role": role,
        "agent_exit_code": exit_code,
        "agent_error": error,
        "parsed_result_file": repo_relative_path(branch_dir / "parsed_result.json") if (branch_dir / "parsed_result.json").is_file() else None,
        "agent_prompt_file": repo_relative_path(branch_dir / "agent_prompt.txt"),
        "agent_stdout_file": repo_relative_path(branch_dir / "agent_stdout.txt"),
        "agent_stderr_file": repo_relative_path(branch_dir / "agent_stderr.txt"),
        "reported": parsed_result,
        "artifact_dir": artifacts["artifact_dir"],
        "broker_feedback_files": artifacts["broker_feedback_files"],
        "diagnostic_files": artifacts["diagnostic_files"],
        "repair_log_file": artifacts["repair_log_file"],
        "intermediate_spectra_files": artifacts["intermediate_spectra_files"],
        "test_files": artifacts["test_files"],
        "final_spectra_file": artifacts["spectra_file"],
        "controller_output_dir": artifacts["controller_output_dir"],
        "core_context_full_file": artifacts["core_context_full_file"],
        "core_context_test_writer_file": artifacts["core_context_test_writer_file"],
    }


def process_independent_branch(
    *,
    branch_dir: Path,
    natural_language: str,
    signature: dict[str, Any],
    signature_json: str,
    core_spectra_file: Path,
    core_context_file: Path | None,
    core_controller_output_dir: Path | None,
    args: argparse.Namespace,
) -> dict[str, Any]:
    if args.dry_run:
        spec_name = infer_spec_name(core_spectra_file, signature)
        controller_dir = controller_jit_dir(core_controller_output_dir) or Path("<controller_dir>")
        test_dir = branch_dir / "round-00" / "test-writer"
        repair_dir = branch_dir / "round-00" / "spec-repair"
        write_text(
            test_dir / "agent_prompt.txt",
            build_test_writer_prompt(
                skill=args.test_writer_skill,
                output_dir=test_dir,
                natural_language=natural_language,
                signature_json=signature_json,
                spec_name=spec_name,
                spectra_file=core_spectra_file,
                controller_dir=controller_dir,
            ),
        )
        write_text(
            repair_dir / "agent_prompt.template.txt",
            build_spec_repair_prompt(
                skill=args.spec_repair_skill,
                run_dir=repair_dir,
                natural_language=natural_language,
                signature_json=signature_json,
                core_spectra_file=core_spectra_file,
                core_context_file=core_context_file,
                test_result_file=Path("<aggregate_test_result_file>"),
                max_feedback_rounds=args.max_feedback_rounds,
                round_index=0,
            ),
        )
        return {
            "status": "dry_run",
            "lineage": "independent_test",
            "role": "spec_repair_from_independent_tests",
            "start_source": "core_final",
            "parent_spectra_file": repo_relative_path(core_spectra_file),
            "test_writer_prompt_file": repo_relative_path(test_dir / "agent_prompt.txt"),
            "spec_repair_prompt_template_file": repo_relative_path(repair_dir / "agent_prompt.template.txt"),
        }

    build_result = build_controller_tests()
    write_text(branch_dir / "build_controller_tests.stdout.txt", build_result.stdout)
    write_text(branch_dir / "build_controller_tests.stderr.txt", build_result.stderr)
    if build_result.returncode != 0:
        return {"status": "controller_tests_build_failed", "lineage": "independent_test", "build_exit_code": build_result.returncode}

    current_spectra_file = core_spectra_file
    current_controller_output_dir = core_controller_output_dir
    compiled_test_plans: list[tuple[int, Path]] = []
    rounds: list[dict[str, Any]] = []
    final_spec_branch: dict[str, Any] | None = None

    for round_index in range(args.max_feedback_rounds + 1):
        round_dir = branch_dir / f"round-{round_index:02d}"
        spec_name = infer_spec_name(current_spectra_file, signature)
        controller_dir = controller_jit_dir(current_controller_output_dir)
        if controller_dir is None:
            return {"status": "missing_controller_dir", "lineage": "independent_test", "rounds": rounds}

        test_dir = round_dir / "test-writer"
        test_prompt = build_test_writer_prompt(
            skill=args.test_writer_skill,
            output_dir=test_dir,
            natural_language=natural_language,
            signature_json=signature_json,
            spec_name=spec_name,
            spectra_file=current_spectra_file,
            controller_dir=controller_dir,
        )
        test_exit, test_result, test_error = run_agent(
            agent_command=args.agent_command,
            prompt=test_prompt,
            prompt_file=test_dir / "agent_prompt.txt",
            stdout_file=test_dir / "agent_stdout.txt",
            stderr_file=test_dir / "agent_stderr.txt",
            timeout=args.timeout,
        )
        if test_result:
            write_json(test_dir / "parsed_result.json", test_result)
        round_record: dict[str, Any] = {
            "round": round_index,
            "test_agent_exit_code": test_exit,
            "test_agent_error": test_error,
            "test_result": test_result,
        }
        rounds.append(round_record)
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
        aggregate_results: list[dict[str, Any]] = []
        replay_records: list[dict[str, Any]] = []
        tests_total = tests_passed = tests_failed = 0
        for source_round, source_plan in compiled_test_plans:
            replay_plan = test_dir / f"replay-plan-round-{source_round:02d}.json"
            result_file = test_dir / f"test-results-round-{source_round:02d}.json"
            rebind_test_plan(
                source_plan,
                replay_plan,
                spec_name=spec_name,
                spectra_file=current_spectra_file,
                controller_dir=controller_dir,
            )
            run_result = run_controller_tests(replay_plan, result_file)
            write_text(test_dir / f"test-run-round-{source_round:02d}.stdout.txt", run_result.stdout)
            write_text(test_dir / f"test-run-round-{source_round:02d}.stderr.txt", run_result.stderr)
            plan_total, plan_passed, plan_failed = test_counts(result_file)
            tests_total += plan_total
            tests_passed += plan_passed
            tests_failed += plan_failed
            payload = load_json(result_file) if result_file.is_file() else {}
            for result in payload.get("results") or payload.get("tests") or []:
                annotated = dict(result)
                annotated["source_test_round"] = source_round
                annotated["source_result_file"] = str(result_file)
                aggregate_results.append(annotated)
            replay_records.append(
                {
                    "source_test_round": source_round,
                    "plan_file": repo_relative_path(replay_plan),
                    "result_file": repo_relative_path(result_file),
                    "exit_code": run_result.returncode,
                    "tests_total": plan_total,
                    "tests_passed": plan_passed,
                    "tests_failed": plan_failed,
                }
            )

        aggregate_file = test_dir / "test-results-aggregate.json"
        write_json(
            aggregate_file,
            {
                "status": "passed" if tests_failed == 0 else "failed",
                "total": tests_total,
                "passed": tests_passed,
                "failed": tests_failed,
                "replayed_test_plans": replay_records,
                "results": aggregate_results,
            },
        )
        round_record.update(
            {
                "aggregate_test_result_file": repo_relative_path(aggregate_file),
                "replayed_test_plans": replay_records,
                "tests_total": tests_total,
                "tests_passed": tests_passed,
                "tests_failed": tests_failed,
            }
        )
        if tests_failed == 0:
            round_record["stop_reason"] = "tests_passed"
            break
        if round_index >= args.max_feedback_rounds:
            round_record["stop_reason"] = "max_feedback_rounds_reached"
            break

        repair_dir = round_dir / "spec-repair"
        repair_prompt = build_spec_repair_prompt(
            skill=args.spec_repair_skill,
            run_dir=repair_dir,
            natural_language=natural_language,
            signature_json=signature_json,
            core_spectra_file=current_spectra_file,
            core_context_file=core_context_file,
            test_result_file=aggregate_file,
            max_feedback_rounds=args.max_feedback_rounds,
            round_index=round_index,
        )
        repair_branch = process_agent_branch(
            branch="independent_test",
            role="spec_repair",
            prompt=repair_prompt,
            branch_dir=repair_dir,
            args=args,
        )
        round_record["spec_repair_branch"] = repair_branch
        final_spec_branch = repair_branch
        if repair_branch.get("status") != "success" or not repair_branch.get("final_spectra_file"):
            round_record["stop_reason"] = "spec_repair_failed"
            break
        current_spectra_file = resolve_repo_path(repair_branch["final_spectra_file"])
        current_controller_output_dir = resolve_repo_path(repair_branch["controller_output_dir"]) if repair_branch.get("controller_output_dir") else None

    final_spectra = final_spec_branch.get("final_spectra_file") if final_spec_branch else repo_relative_path(core_spectra_file)
    return {
        "status": "tests_passed" if rounds and rounds[-1].get("stop_reason") == "tests_passed" else "completed",
        "lineage": "independent_test",
        "role": "spec_repair_from_independent_tests",
        "start_source": "core_final",
        "parent_spectra_file": repo_relative_path(core_spectra_file),
        "final_spectra_file": final_spectra,
        "rounds": rounds,
    }


def process_cross_branch(
    *,
    branch_dir: Path,
    description_file: Path,
    signature_file: Path,
    core_spectra_file: Path,
    core_context_file: Path | None,
    core_controller_output_dir: Path | None,
    core_run_id: str,
    args: argparse.Namespace,
) -> dict[str, Any]:
    cross_runner = resolve_repo_path(args.cross_runner)
    command = [
        sys.executable,
        str(cross_runner),
        "--description-file",
        str(description_file),
        "--signature-file",
        str(signature_file),
        "--core-spectra-file",
        str(core_spectra_file),
        "--output-dir",
        str(branch_dir),
        "--run-id",
        f"{core_run_id}-cross",
        "--agent-command",
        args.agent_command,
        "--incumbent-skill",
        args.cross_incumbent_skill,
        "--challenger-skill",
        args.cross_challenger_skill,
        "--timeout",
        str(args.timeout),
        "--broker-timeout",
        str(args.broker_timeout),
        "--max-broker-repair-loops",
        str(args.max_feedback_rounds),
    ]
    if core_context_file:
        command.extend(["--core-context-file", str(core_context_file)])
    if core_controller_output_dir:
        command.extend(["--core-controller-output-dir", str(core_controller_output_dir)])
    if args.dry_run:
        command.append("--dry-run")

    started = time.perf_counter()
    stdout_file = branch_dir / "cross_runner_stdout.txt"
    stderr_file = branch_dir / "cross_runner_stderr.txt"
    summary_file = branch_dir / f"{core_run_id}-cross" / "summary.json"
    error = None
    exit_code: int | None = None
    summary: dict[str, Any] | None = None
    try:
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=(args.timeout + args.broker_timeout + 120) if not args.dry_run else 120,
        )
        exit_code = completed.returncode
        write_text(stdout_file, completed.stdout)
        write_text(stderr_file, completed.stderr)
        if summary_file.is_file():
            summary = load_json(summary_file)
    except subprocess.TimeoutExpired as exc:
        error = "Cross-from-core runner timed out."
        write_text(stdout_file, exc.stdout or "")
        write_text(stderr_file, exc.stderr or "")

    status = "dry_run" if args.dry_run else ("success" if exit_code == 0 and summary and summary.get("status") == "success" else "agent_error")
    if summary and summary.get("status") == "dry_run":
        status = "dry_run"
    return {
        "status": status,
        "lineage": "cross_repair",
        "role": "asymmetric_cross_repair",
        "start_source": "core_final_and_fresh_challenger",
        "parent_spectra_file": repo_relative_path(core_spectra_file),
        "cross_runner": repo_relative_path(cross_runner),
        "cross_runner_exit_code": exit_code,
        "cross_runner_stdout_file": repo_relative_path(stdout_file),
        "cross_runner_stderr_file": repo_relative_path(stderr_file),
        "summary_file": repo_relative_path(summary_file) if summary_file.is_file() else None,
        "duration_ms": int((time.perf_counter() - started) * 1000),
        "error": error,
        "incumbent_skill": args.cross_incumbent_skill,
        "challenger_skill": args.cross_challenger_skill,
        "broker_timeout_seconds": args.broker_timeout,
        "summary": summary,
    }


def process_record(record: dict[str, Any], args: argparse.Namespace, output_dir: Path, runs_manifest: Path, completed: set[str]) -> str:
    response_file = resolve_repo_path(record["response_file"])
    signature_file = signature_file_for(record, resolve_repo_path(args.signature_root))
    current_run_key = run_key(record, args, signature_file)
    if not args.force and current_run_key in completed:
        return "skipped"

    description_stem = description_relative_stem(response_file)
    core_run_id = current_run_key[:24]
    run_dir = output_dir / description_stem / core_run_id
    started_at = utc_now()
    started = time.perf_counter()
    error = None
    branches: dict[str, Any] = {}

    if not response_file.is_file():
        error = f"Description file not found: {response_file}"
    elif not signature_file.is_file():
        error = f"Signature file not found: {signature_file}"
    else:
        natural_language = response_file.read_text(encoding="utf-8")
        signature = load_json(signature_file)
        signature_json = json.dumps(signature, indent=2, sort_keys=True)
        core_dir = run_dir / "core"
        core_prompt = build_core_prompt(args.core_skill, core_dir, natural_language, signature_json)
        core_branch = process_agent_branch(
            branch="core",
            role="shared_core",
            prompt=core_prompt,
            branch_dir=core_dir,
            args=args,
        )
        core_branch.update({"start_source": "fresh", "parent_spectra_file": None})
        branches["core"] = core_branch

        core_spectra = resolve_repo_path(core_branch["final_spectra_file"]) if core_branch.get("final_spectra_file") else None
        core_context = resolve_repo_path(core_branch["core_context_full_file"]) if core_branch.get("core_context_full_file") else None
        core_controller = resolve_repo_path(core_branch["controller_output_dir"]) if core_branch.get("controller_output_dir") else None

        if args.dry_run or (core_branch.get("status") == "success" and core_spectra and core_spectra.is_file()):
            if "no_test" in args.branches:
                branches["no_test"] = (
                    {"status": "dry_run", "lineage": "no_test", "role": "baseline", "start_source": "core_final"}
                    if args.dry_run
                    else process_no_test(core_branch, run_dir / "branches" / "no_test")
                )
            if "self_test" in args.branches:
                self_prompt = build_self_test_prompt(
                    skill=args.self_test_skill,
                    run_dir=run_dir / "branches" / "self_test",
                    natural_language=natural_language,
                    signature_json=signature_json,
                    core_spectra_file=core_spectra or Path("<core_final.spectra>"),
                    core_context_file=core_context,
                    controller_output_dir=core_controller,
                    max_feedback_rounds=args.max_feedback_rounds,
                )
                self_branch = process_agent_branch(
                    branch="self_test",
                    role="self_test_from_core",
                    prompt=self_prompt,
                    branch_dir=run_dir / "branches" / "self_test",
                    args=args,
                )
                self_branch.update({"start_source": "core_final", "parent_spectra_file": repo_relative_path(core_spectra) if core_spectra else "<core_final.spectra>"})
                branches["self_test"] = self_branch
            if "independent_test" in args.branches:
                branches["independent_test"] = process_independent_branch(
                    branch_dir=run_dir / "branches" / "independent_test",
                    natural_language=natural_language,
                    signature=signature,
                    signature_json=signature_json,
                    core_spectra_file=core_spectra or Path("<core_final.spectra>"),
                    core_context_file=core_context,
                    core_controller_output_dir=core_controller,
                    args=args,
                )
            if "cross_repair" in args.branches:
                branches["cross_repair"] = process_cross_branch(
                    branch_dir=run_dir / "branches" / "cross_repair",
                    description_file=response_file,
                    signature_file=signature_file,
                    core_spectra_file=core_spectra or Path("<core_final.spectra>"),
                    core_context_file=core_context,
                    core_controller_output_dir=core_controller,
                    core_run_id=core_run_id,
                    args=args,
                )
        else:
            error = "Core branch did not produce a final Spectra file; branches were not run."

    branch_statuses = {name: branch.get("status") for name, branch in branches.items()}
    if error:
        status = "missing_input" if not branches else "partial_success"
    elif args.dry_run:
        status = "dry_run"
    elif all(value in {"success", "tests_passed", "completed"} for value in branch_statuses.values()):
        status = "success"
    else:
        status = "partial_success"

    manifest_record = {
        "run_id": core_run_id,
        "run_key": current_run_key,
        "core_run_id": core_run_id,
        "status": status,
        "description_id": record.get("description_id"),
        "dataset_id": record.get("dataset_id"),
        "description_file": str(response_file),
        "signature_file": str(signature_file),
        "source_spectra_file": record.get("source_spectra_file"),
        "source_repository_full_name": record.get("source_repository_full_name"),
        "source_path": record.get("source_path"),
        "agent_command": args.agent_command,
        "agent_model": args.agent_model,
        "core_skill": args.core_skill,
        "self_test_skill": args.self_test_skill,
        "spec_repair_skill": args.spec_repair_skill,
        "test_writer_skill": args.test_writer_skill,
        "cross_incumbent_skill": args.cross_incumbent_skill,
        "cross_challenger_skill": args.cross_challenger_skill,
        "cross_runner": args.cross_runner,
        "branches_requested": args.branches,
        "run_dir": str(run_dir),
        "runs_manifest": str(runs_manifest),
        "max_feedback_rounds": args.max_feedback_rounds,
        "broker_timeout_seconds": args.broker_timeout,
        "timeout_seconds": args.timeout,
        "run_started_at": started_at,
        "run_finished_at": utc_now(),
        "duration_ms": int((time.perf_counter() - started) * 1000),
        "error": error,
        "dry_run": args.dry_run,
        "branches": branches,
    }
    write_json(run_dir / "summary.json", manifest_record)
    append_jsonl(runs_manifest, manifest_record)
    if status in {"success", "partial_success", "dry_run"}:
        completed.add(current_run_key)
    return status


def main() -> int:
    args = parse_args()
    descriptions_manifest = resolve_repo_path(args.descriptions_manifest)
    descriptions = load_jsonl(descriptions_manifest)
    if not descriptions:
        print(f"No descriptions found in {descriptions_manifest}", file=sys.stderr)
        return 2

    output_dir = resolve_repo_path(args.output_dir)
    runs_manifest = output_dir / "runs.jsonl"
    completed = set() if args.force else completed_run_keys(runs_manifest)
    stats: dict[str, int] = {
        "processed": 0,
        "success": 0,
        "partial_success": 0,
        "dry_run": 0,
        "missing_input": 0,
        "skipped": 0,
    }
    for record in descriptions:
        if args.limit is not None and stats["processed"] >= args.limit:
            break
        result = process_record(record, args, output_dir, runs_manifest, completed)
        stats["processed"] += 1
        stats[result] = stats.get(result, 0) + 1

    summary = {
        "descriptions_manifest": str(descriptions_manifest),
        "signature_root": str(resolve_repo_path(args.signature_root)),
        "output_dir": str(output_dir),
        "runs_manifest": str(runs_manifest),
        "branches": args.branches,
        "stats": stats,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if stats.get("missing_input", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
