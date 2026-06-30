#!/usr/bin/env python3
"""Run two cross-broker reconstruction agents for one NL description.

This is the minimal orchestrator for the broker-based experiment condition. It
does not compare Spectra files itself. Instead, it starts two long-running agent
processes with shared run metadata so that the agents can synchronize through
`experiments/cross_broker.py` while keeping their own session context.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "experiments" / "cross_runs"
DEFAULT_AGENT_COMMAND = "codex --ask-for-approval never exec --ephemeral --sandbox danger-full-access -"
DEFAULT_SKILL = "respect-method-cross-broker"
DEFAULT_AGENTS = ("agent_a", "agent_b")


def utc_now() -> str:
    """Return an ISO-8601 UTC timestamp for run metadata."""
    return datetime.now(timezone.utc).isoformat()


def parse_args() -> argparse.Namespace:
    """Parse CLI options for one two-agent cross-broker run."""
    parser = argparse.ArgumentParser(description="Run two cross-broker skill agents in parallel.")
    parser.add_argument("--description-file", required=True)
    parser.add_argument("--skill", default=DEFAULT_SKILL)
    parser.add_argument("--agent-command", default=DEFAULT_AGENT_COMMAND)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--round", type=int, default=0, dest="round_id")
    parser.add_argument("--agent-ids", nargs=2, default=list(DEFAULT_AGENTS))
    parser.add_argument("--timeout", type=float, default=1800.0)
    parser.add_argument("--broker-timeout", type=float, default=600.0)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def resolve_repo_path(path_value: str) -> Path:
    """Resolve relative paths against the repository root."""
    path = Path(path_value)
    if path.is_absolute():
        return path
    return (REPO_ROOT / path).resolve()


def write_text(path: Path, content: str) -> None:
    """Write a UTF-8 text artifact, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, payload: dict) -> None:
    """Write a JSON artifact with stable formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_prompt(
    *,
    skill: str,
    agent_id: str,
    peer_agent_id: str,
    run_id: str,
    round_id: int,
    agent_run_dir: Path,
    broker_timeout: float,
    expected_agents: list[str],
    natural_language_description: str,
) -> str:
    """Build the per-agent prompt with mirrored broker metadata.

    The prompt gives each agent the same natural-language requirements but a
    different `agent_id`. The skill is responsible for calling the broker after
    successful synthesis.
    """
    expected_agents_text = " ".join(expected_agents)
    return f"""Use ${skill}.

This is a ReSpect cross-broker reconstruction run.

Run metadata:
- run_dir: {agent_run_dir}
- run_id: {run_id}
- agent_id: {agent_id}
- peer_agent_id: {peer_agent_id}
- round_id: {round_id}
- broker_timeout_seconds: {broker_timeout}
- expected_agents: {expected_agents_text}

After successful synthesis, call the broker with:

```powershell
python experiments\\cross_broker.py submit-and-wait --run-id {run_id} --round {round_id} --agent {agent_id} --spec <path-to-current-spectra-file> --expected-agents {expected_agents_text} --timeout {broker_timeout}
```

Natural-language requirements:

{natural_language_description}
"""


def build_command(agent_command: str, prompt_file: Path) -> tuple[str, bool]:
    """Return the command string and whether the prompt should go to stdin.

    Commands containing `{prompt_file}` are expected to read the prompt from
    that file. Other commands receive the prompt through stdin, matching the
    existing `reconstruct_with_skill.py` behavior.
    """
    if "{prompt_file}" in agent_command:
        return agent_command.format(prompt_file=str(prompt_file)), False
    return agent_command, True


def start_agent(command: str, prompt: str | None) -> subprocess.Popen[str]:
    """Start one agent process without waiting for it to finish."""
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


def finish_agent(process: subprocess.Popen[str], prompt: str | None, timeout: float) -> tuple[int | None, str, str, str | None]:
    """Wait for an agent process and return captured output plus any timeout."""
    try:
        stdout, stderr = process.communicate(input=prompt, timeout=timeout)
        return process.returncode, stdout, stderr, None
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate()
        return None, stdout, stderr, f"Agent timed out after {timeout} seconds."


def main() -> int:
    """Create prompts, run both agents in parallel, and write a summary."""
    args = parse_args()
    description_file = resolve_repo_path(args.description_file)
    natural_language_description = description_file.read_text(encoding="utf-8")

    run_id = args.run_id or f"cross-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    output_dir = resolve_repo_path(args.output_dir)
    run_dir = output_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    write_text(run_dir / "input_description.txt", natural_language_description)
    write_json(
        run_dir / "config.json",
        {
            "agent_command": args.agent_command,
            "agent_ids": args.agent_ids,
            "broker_timeout_seconds": args.broker_timeout,
            "description_file": str(description_file),
            "round": args.round_id,
            "run_id": run_id,
            "skill": args.skill,
            "timeout_seconds": args.timeout,
        },
    )

    prompts: dict[str, str] = {}
    commands: dict[str, tuple[str, bool]] = {}
    for agent_id in args.agent_ids:
        peer_ids = [candidate for candidate in args.agent_ids if candidate != agent_id]
        agent_run_dir = run_dir / agent_id
        prompt = build_prompt(
            skill=args.skill,
            agent_id=agent_id,
            peer_agent_id=peer_ids[0],
            run_id=run_id,
            round_id=args.round_id,
            agent_run_dir=agent_run_dir,
            broker_timeout=args.broker_timeout,
            expected_agents=args.agent_ids,
            natural_language_description=natural_language_description,
        )
        prompt_file = agent_run_dir / "agent_prompt.txt"
        write_text(prompt_file, prompt)
        prompts[agent_id] = prompt
        commands[agent_id] = build_command(args.agent_command, prompt_file)

    if args.dry_run:
        summary = {"status": "dry_run", "run_id": run_id, "run_dir": str(run_dir)}
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0

    started_at = utc_now()
    started = time.perf_counter()
    processes: dict[str, subprocess.Popen[str]] = {}

    # Start both agents before waiting for either one. This is required because
    # each agent may block inside cross_broker.py until the peer submits.
    for agent_id, (command, pass_prompt_on_stdin) in commands.items():
        processes[agent_id] = start_agent(command, prompts[agent_id] if pass_prompt_on_stdin else None)

    results = {}
    for agent_id, process in processes.items():
        _, pass_prompt_on_stdin = commands[agent_id]
        exit_code, stdout, stderr, error = finish_agent(
            process,
            prompts[agent_id] if pass_prompt_on_stdin else None,
            args.timeout,
        )
        agent_dir = run_dir / agent_id
        write_text(agent_dir / "agent_stdout.txt", stdout)
        write_text(agent_dir / "agent_stderr.txt", stderr)
        results[agent_id] = {
            "exit_code": exit_code,
            "error": error,
            "stdout_file": str(agent_dir / "agent_stdout.txt"),
            "stderr_file": str(agent_dir / "agent_stderr.txt"),
        }

    summary = {
        "status": "success" if all(result["exit_code"] == 0 for result in results.values()) else "agent_error",
        "run_id": run_id,
        "run_dir": str(run_dir),
        "run_started_at": started_at,
        "run_finished_at": utc_now(),
        "duration_ms": int((time.perf_counter() - started) * 1000),
        "results": results,
    }
    write_json(run_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
