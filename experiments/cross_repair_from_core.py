#!/usr/bin/env python3
"""Run asymmetric cross-repair from a shared core Spectra.

The incumbent starts from core_final.spectra. The challenger starts fresh from
NL plus the fixed signature. Both synchronize through cross_broker.py.
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.branched_reconstruction import (  # noqa: E402
    archive_skill_artifacts,
    build_command,
    extract_agent_result,
    repo_relative_path,
    resolve_repo_path,
    write_json,
    write_text,
)


DEFAULT_AGENT_COMMAND = "codex --ask-for-approval never exec --ephemeral --sandbox danger-full-access -"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "experiments" / "branched_runs" / "cross_standalone"
DEFAULT_INCUMBENT_SKILL = "respect-broker-from-core"
DEFAULT_CHALLENGER_SKILL = "respect-broker"
DEFAULT_AGENT_IDS = ("incumbent", "challenger")
DEFAULT_AGENT_TIMEOUT_SECONDS = 7200.0
DEFAULT_BROKER_TIMEOUT_SECONDS = 1800.0
LOGGER = logging.getLogger("cross_repair_from_core")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--description-file", required=True)
    parser.add_argument("--signature-file", required=True)
    parser.add_argument("--core-spectra-file", required=True)
    parser.add_argument("--core-context-file", default=None)
    parser.add_argument("--core-controller-output-dir", default=None)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--agent-command", default=DEFAULT_AGENT_COMMAND)
    parser.add_argument("--incumbent-skill", default=DEFAULT_INCUMBENT_SKILL)
    parser.add_argument("--challenger-skill", default=DEFAULT_CHALLENGER_SKILL)
    parser.add_argument("--agent-ids", nargs=2, default=list(DEFAULT_AGENT_IDS))
    parser.add_argument("--round", type=int, default=0, dest="round_id")
    parser.add_argument("--timeout", type=float, default=DEFAULT_AGENT_TIMEOUT_SECONDS)
    parser.add_argument("--broker-timeout", type=float, default=DEFAULT_BROKER_TIMEOUT_SECONDS)
    parser.add_argument("--max-broker-repair-loops", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--log-file", default=None)
    parser.add_argument("--log-level", default="INFO", choices=("DEBUG", "INFO", "WARNING", "ERROR"))
    return parser.parse_args()


def configure_logging(log_level: str = "INFO", log_file: str | None = None) -> None:
    """Configure console/file logging for a cross-from-core run."""
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


def utc_now() -> str:
    """Return an ISO-8601 UTC timestamp for cross-run summaries."""
    return datetime.now(timezone.utc).isoformat()


def start_agent(command: str, prompt: str | None) -> subprocess.Popen[str]:
    """Start one long-running agent process without waiting for completion."""
    return subprocess.Popen(
        command,
        cwd=REPO_ROOT,
        stdin=subprocess.PIPE if prompt is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=True,
    )


def stream_pipe(pipe, label: str, output_stream, chunks: list[str]) -> None:
    """Mirror a subprocess stream to console while preserving captured text."""
    if pipe is None:
        return
    for line in iter(pipe.readline, ""):
        chunks.append(line)
        print(f"[{label}] {line}", end="", file=output_stream, flush=True)


def finish_agent_live(
    process: subprocess.Popen[str],
    prompt: str | None,
    timeout: float,
    agent_id: str,
) -> tuple[int | None, str, str, str | None]:
    """Wait for one agent, stream output, and enforce its equal time budget."""
    stdout_chunks: list[str] = []
    stderr_chunks: list[str] = []
    stdout_thread = threading.Thread(
        target=stream_pipe,
        args=(process.stdout, f"{agent_id} stdout", sys.stdout, stdout_chunks),
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=stream_pipe,
        args=(process.stderr, f"{agent_id} stderr", sys.stderr, stderr_chunks),
        daemon=True,
    )
    stdout_thread.start()
    stderr_thread.start()

    if prompt is not None and process.stdin is not None:
        try:
            process.stdin.write(prompt)
            process.stdin.close()
        except BrokenPipeError:
            pass

    try:
        exit_code = process.wait(timeout=timeout)
        error = None
    except subprocess.TimeoutExpired:
        process.kill()
        exit_code = None
        error = f"Agent timed out after {timeout} seconds."
        LOGGER.warning("Cross agent timed out: agent=%s timeout=%ss", agent_id, timeout)

    stdout_thread.join(timeout=5)
    stderr_thread.join(timeout=5)
    return exit_code, "".join(stdout_chunks), "".join(stderr_chunks), error


def build_incumbent_prompt(
    *,
    skill: str,
    run_dir: Path,
    run_id: str,
    agent_id: str,
    peer_agent_id: str,
    broker_runs_root: Path,
    round_id: int,
    broker_timeout: float,
    max_broker_repair_loops: int,
    timeout: float,
    expected_agents: list[str],
    natural_language: str,
    signature_json: str,
    core_spectra_file: Path,
    core_context_file: Path | None,
    core_controller_output_dir: Path | None,
) -> str:
    """Build the incumbent prompt with full core context and broker metadata."""
    expected_agents_text = " ".join(expected_agents)
    return f"""Use ${skill}.

This is the incumbent side of an asymmetric branched cross-repair run.

Run metadata:
- run_dir: {run_dir}
- run_id: {run_id}
- agent_id: {agent_id}
- peer_agent_id: {peer_agent_id}
- round_id: {round_id}
- agent_timeout_budget_seconds: {timeout}
- broker_runs_root: {broker_runs_root}
- broker_timeout_seconds: {broker_timeout}
- max_broker_repair_loops: {max_broker_repair_loops}
- expected_agents: {expected_agents_text}

Fixed env/sys signature JSON:

```json
{signature_json}
```

Core artifacts:
- core_final_spectra_file: {core_spectra_file}
- core_context_full_file: {core_context_file or "none"}
- core_controller_output_dir: {core_controller_output_dir or "none"}

After successful synthesis, call the broker with the current round id:

```powershell
python experiments\\cross_broker.py submit-and-wait --runs-root {broker_runs_root} --run-id {run_id} --round {round_id} --agent {agent_id} --spec <path-to-current-spectra-file> --expected-agents {expected_agents_text} --timeout {broker_timeout}
```

If broker feedback justifies a Spectra repair under the natural-language
requirements, validate and synthesize the repaired Spectra, increment the round
id by 1, and call the same broker command with the new round id. Stop after at
most {max_broker_repair_loops} broker-repair loops. Use the same generous agent
timeout budget as the challenger; do not stop early unless a nested command
reports its own timeout or the broker-repair loop limit is reached.

Natural-language requirements:

{natural_language}
"""


def build_challenger_prompt(
    *,
    skill: str,
    run_dir: Path,
    run_id: str,
    agent_id: str,
    peer_agent_id: str,
    broker_runs_root: Path,
    round_id: int,
    broker_timeout: float,
    max_broker_repair_loops: int,
    timeout: float,
    expected_agents: list[str],
    natural_language: str,
    signature_json: str,
) -> str:
    """Build the fresh challenger prompt without any core artifacts."""
    expected_agents_text = " ".join(expected_agents)
    return f"""Use ${skill}.

This is the fresh challenger side of an asymmetric branched cross-repair run.

Run metadata:
- run_dir: {run_dir}
- run_id: {run_id}
- agent_id: {agent_id}
- peer_agent_id: {peer_agent_id}
- round_id: {round_id}
- agent_timeout_budget_seconds: {timeout}
- broker_runs_root: {broker_runs_root}
- broker_timeout_seconds: {broker_timeout}
- max_broker_repair_loops: {max_broker_repair_loops}
- expected_agents: {expected_agents_text}

Fixed env/sys signature JSON:

```json
{signature_json}
```

Start fresh from only the natural-language requirements and fixed signature.
Do not read core_final.spectra, core_context.full.json, incumbent artifacts,
source Spectra, benchmark oracles, or distance results.

After successful synthesis, call the broker with the current round id:

```powershell
python experiments\\cross_broker.py submit-and-wait --runs-root {broker_runs_root} --run-id {run_id} --round {round_id} --agent {agent_id} --spec <path-to-current-spectra-file> --expected-agents {expected_agents_text} --timeout {broker_timeout}
```

If broker feedback justifies a Spectra repair under the natural-language
requirements, validate and synthesize the repaired Spectra, increment the round
id by 1, and call the same broker command with the new round id. Stop after at
most {max_broker_repair_loops} broker-repair loops. Use the same generous agent
timeout budget as the incumbent; do not stop early unless a nested command
reports its own timeout or the broker-repair loop limit is reached.

Natural-language requirements:

{natural_language}
"""


def archive_agent_result(agent_dir: Path, stdout: str) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Parse an agent final result and archive its reported artifacts."""
    parsed_result = extract_agent_result(stdout)
    if parsed_result:
        write_json(agent_dir / "parsed_result.json", parsed_result)
    return parsed_result, archive_skill_artifacts(parsed_result, agent_dir)


def main() -> int:
    """Run the asymmetric incumbent/challenger broker experiment."""
    args = parse_args()
    configure_logging(args.log_level, args.log_file)
    description_file = resolve_repo_path(args.description_file)
    signature_file = resolve_repo_path(args.signature_file)
    core_spectra_file = resolve_repo_path(args.core_spectra_file)
    core_context_file = resolve_repo_path(args.core_context_file) if args.core_context_file else None
    core_controller_output_dir = resolve_repo_path(args.core_controller_output_dir) if args.core_controller_output_dir else None
    output_dir = resolve_repo_path(args.output_dir)
    run_dir = output_dir / args.run_id
    broker_runs_root = run_dir / "broker_runs"
    run_dir.mkdir(parents=True, exist_ok=True)

    natural_language = description_file.read_text(encoding="utf-8")
    signature_json = signature_file.read_text(encoding="utf-8")
    incumbent_id, challenger_id = args.agent_ids
    expected_agents = [incumbent_id, challenger_id]
    started_at = utc_now()
    started = time.perf_counter()
    LOGGER.info(
        "Starting cross-from-core run: run_id=%s incumbent=%s challenger=%s timeout=%ss broker_timeout=%ss dry_run=%s",
        args.run_id,
        args.incumbent_skill,
        args.challenger_skill,
        args.timeout,
        args.broker_timeout,
        args.dry_run,
    )

    prompts = {
        incumbent_id: build_incumbent_prompt(
            skill=args.incumbent_skill,
            run_dir=run_dir / incumbent_id,
            run_id=args.run_id,
            agent_id=incumbent_id,
            peer_agent_id=challenger_id,
            broker_runs_root=broker_runs_root,
            round_id=args.round_id,
            broker_timeout=args.broker_timeout,
            max_broker_repair_loops=args.max_broker_repair_loops,
            timeout=args.timeout,
            expected_agents=expected_agents,
            natural_language=natural_language,
            signature_json=signature_json,
            core_spectra_file=core_spectra_file,
            core_context_file=core_context_file,
            core_controller_output_dir=core_controller_output_dir,
        ),
        challenger_id: build_challenger_prompt(
            skill=args.challenger_skill,
            run_dir=run_dir / challenger_id,
            run_id=args.run_id,
            agent_id=challenger_id,
            peer_agent_id=incumbent_id,
            broker_runs_root=broker_runs_root,
            round_id=args.round_id,
            broker_timeout=args.broker_timeout,
            max_broker_repair_loops=args.max_broker_repair_loops,
            timeout=args.timeout,
            expected_agents=expected_agents,
            natural_language=natural_language,
            signature_json=signature_json,
        ),
    }

    write_text(run_dir / "input_description.txt", natural_language)
    write_json(
        run_dir / "config.json",
        {
            "agent_command": args.agent_command,
            "agent_ids": expected_agents,
            "broker_runs_root": str(broker_runs_root),
            "broker_timeout_seconds": args.broker_timeout,
            "challenger_skill": args.challenger_skill,
            "core_context_file": str(core_context_file) if core_context_file else None,
            "core_controller_output_dir": str(core_controller_output_dir) if core_controller_output_dir else None,
            "core_spectra_file": str(core_spectra_file),
            "description_file": str(description_file),
            "incumbent_skill": args.incumbent_skill,
            "max_broker_repair_loops": args.max_broker_repair_loops,
            "round": args.round_id,
            "run_id": args.run_id,
            "signature_file": str(signature_file),
            "timeout_seconds": args.timeout,
        },
    )

    commands: dict[str, tuple[str, bool]] = {}
    for agent_id, prompt in prompts.items():
        agent_dir = run_dir / agent_id
        prompt_file = agent_dir / "agent_prompt.txt"
        write_text(prompt_file, prompt)
        commands[agent_id] = build_command(args.agent_command, prompt_file)

    if args.dry_run:
        summary = {
            "status": "dry_run",
            "run_id": args.run_id,
            "run_dir": str(run_dir),
            "results": {
                incumbent_id: {
                    "role": "incumbent",
                    "lineage": "cross_incumbent",
                    "start_source": "core_final",
                    "agent_prompt_file": repo_relative_path(run_dir / incumbent_id / "agent_prompt.txt"),
                },
                challenger_id: {
                    "role": "challenger",
                    "lineage": "cross_challenger",
                    "start_source": "fresh",
                    "agent_prompt_file": repo_relative_path(run_dir / challenger_id / "agent_prompt.txt"),
                },
            },
        }
        write_json(run_dir / "summary.json", summary)
        print(json.dumps(summary, indent=2, sort_keys=True))
        LOGGER.info("Finished cross-from-core dry-run: run_id=%s summary=%s", args.run_id, repo_relative_path(run_dir / "summary.json"))
        return 0

    processes: dict[str, subprocess.Popen[str]] = {}
    for agent_id, (command, pass_prompt_on_stdin) in commands.items():
        LOGGER.info("Starting cross agent: agent=%s command=%s", agent_id, command)
        processes[agent_id] = start_agent(command, prompts[agent_id] if pass_prompt_on_stdin else None)

    results: dict[str, dict[str, Any]] = {}

    def finish_and_record(agent_id: str, process: subprocess.Popen[str]) -> None:
        _, pass_prompt_on_stdin = commands[agent_id]
        exit_code, stdout, stderr, error = finish_agent_live(
            process,
            prompts[agent_id] if pass_prompt_on_stdin else None,
            args.timeout,
            agent_id,
        )
        agent_dir = run_dir / agent_id
        write_text(agent_dir / "agent_stdout.txt", stdout)
        write_text(agent_dir / "agent_stderr.txt", stderr)
        parsed_result, artifacts = archive_agent_result(agent_dir, stdout)
        role = "incumbent" if agent_id == incumbent_id else "challenger"
        results[agent_id] = {
            "status": "success" if exit_code == 0 and parsed_result else "agent_error",
            "role": role,
            "lineage": "cross_incumbent" if role == "incumbent" else "cross_challenger",
            "start_source": "core_final" if role == "incumbent" else "fresh",
            "parent_spectra_file": repo_relative_path(core_spectra_file) if role == "incumbent" else None,
            "agent_exit_code": exit_code,
            "agent_error": error,
            "agent_prompt_file": repo_relative_path(agent_dir / "agent_prompt.txt"),
            "agent_stdout_file": repo_relative_path(agent_dir / "agent_stdout.txt"),
            "agent_stderr_file": repo_relative_path(agent_dir / "agent_stderr.txt"),
            "parsed_result_file": repo_relative_path(agent_dir / "parsed_result.json") if (agent_dir / "parsed_result.json").is_file() else None,
            "reported": parsed_result,
            "artifact_dir": artifacts["artifact_dir"],
            "broker_feedback_files": artifacts["broker_feedback_files"],
            "diagnostic_files": artifacts["diagnostic_files"],
            "repair_log_file": artifacts["repair_log_file"],
            "intermediate_spectra_files": artifacts["intermediate_spectra_files"],
            "test_files": artifacts["test_files"],
            "final_spectra_file": artifacts["spectra_file"],
            "controller_output_dir": artifacts["controller_output_dir"],
        }
        LOGGER.info(
            "Finished cross agent: agent=%s role=%s status=%s exit_code=%s final=%s",
            agent_id,
            role,
            results[agent_id]["status"],
            exit_code,
            results[agent_id]["final_spectra_file"],
        )

    threads = [
        threading.Thread(target=finish_and_record, args=(agent_id, process), daemon=True)
        for agent_id, process in processes.items()
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    status = "success" if all(result.get("status") == "success" for result in results.values()) else "agent_error"
    summary = {
        "status": status,
        "run_id": args.run_id,
        "run_dir": str(run_dir),
        "run_started_at": started_at,
        "run_finished_at": utc_now(),
        "duration_ms": int((time.perf_counter() - started) * 1000),
        "broker_runs_root": str(broker_runs_root),
        "results": results,
    }
    write_json(run_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    LOGGER.info("Finished cross-from-core run: run_id=%s status=%s summary=%s", args.run_id, status, repo_relative_path(run_dir / "summary.json"))
    return 0 if status == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
