#!/usr/bin/env python3
"""Minimal file-based broker for cross-agent repair experiments.

The broker lets two independently running skills synchronize without a long
running server. Each skill submits its current Spectra file, blocks until the
peer has submitted too, and then receives JSON feedback. The current comparison
implementation is intentionally a dummy placeholder; the file protocol around
it is the part that the skills can already integrate with.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNS_ROOT = REPO_ROOT / "experiments" / "cross_runs"
DEFAULT_EXPECTED_AGENTS = ("agent_a", "agent_b")


def utc_now() -> str:
    """Return an ISO-8601 UTC timestamp for broker artifact metadata."""
    return datetime.now(timezone.utc).isoformat()


def parse_args() -> argparse.Namespace:
    """Parse the broker CLI.

    The first version exposes only one operation: submit a specification and
    wait for the comparison feedback for the submitting agent.
    """
    parser = argparse.ArgumentParser(description="Coordinate cross-agent Spectra comparison feedback.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    submit = subparsers.add_parser("submit-and-wait")
    submit.add_argument("--run-id", required=True)
    submit.add_argument("--round", type=int, required=True, dest="round_id")
    submit.add_argument("--agent", required=True)
    submit.add_argument("--spec", required=True)
    submit.add_argument("--timeout", type=float, default=600.0)
    submit.add_argument("--runs-root", default=str(DEFAULT_RUNS_ROOT))
    submit.add_argument("--expected-agents", nargs="+", default=list(DEFAULT_EXPECTED_AGENTS))
    submit.add_argument("--poll-interval", type=float, default=1.0)
    return parser.parse_args()


def validate_path_part(value: str, label: str) -> None:
    """Reject path traversal for values used as directory or file names."""
    if not value or value in {".", ".."}:
        raise ValueError(f"{label} must not be empty or relative traversal.")
    if any(separator in value for separator in ("/", "\\")) or ".." in Path(value).parts:
        raise ValueError(f"{label} must be a simple path segment: {value!r}")


def resolve_path(path_value: str) -> Path:
    """Resolve relative paths against the repository root."""
    path = Path(path_value)
    if path.is_absolute():
        return path
    return (REPO_ROOT / path).resolve()


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON via a temporary file and atomic rename.

    Skills may run in parallel and poll these files. Atomic replacement avoids
    readers observing half-written JSON.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp-{os.getpid()}")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp_path, path)


def read_json(path: Path) -> dict[str, Any]:
    """Read a JSON object from disk."""
    return json.loads(path.read_text(encoding="utf-8"))


def build_paths(runs_root: Path, run_id: str, round_id: int, agent: str) -> dict[str, Path]:
    """Return all broker artifact paths for one run, round, and agent."""
    round_dir = runs_root / run_id / f"round-{round_id}"
    return {
        "round_dir": round_dir,
        "submissions_dir": round_dir / "submissions",
        "specs_dir": round_dir / "specs",
        "comparison_dir": round_dir / "comparison",
        "submission": round_dir / "submissions" / f"{agent}.json",
        "spec": round_dir / "specs" / f"{agent}.spectra",
        "feedback": round_dir / "comparison" / f"feedback_for_{agent}.json",
        "status": round_dir / "comparison" / "status.json",
        "comparison": round_dir / "comparison" / "comparison.json",
        "lock": round_dir / "comparison" / "lock",
    }


def ensure_dirs(paths: dict[str, Path]) -> None:
    """Create the per-round broker directories."""
    paths["submissions_dir"].mkdir(parents=True, exist_ok=True)
    paths["specs_dir"].mkdir(parents=True, exist_ok=True)
    paths["comparison_dir"].mkdir(parents=True, exist_ok=True)


def copy_spec(source: Path, destination: Path) -> None:
    """Copy the submitted Spectra file into the broker artifact directory."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = destination.with_name(f"{destination.name}.tmp-{os.getpid()}")
    shutil.copy2(source, tmp_path)
    os.replace(tmp_path, destination)


def all_submissions_exist(paths: dict[str, Path], expected_agents: list[str]) -> bool:
    """Return true once every expected agent has submitted a spec."""
    return all((paths["submissions_dir"] / f"{agent}.json").is_file() for agent in expected_agents)


def acquire_lock(lock_path: Path) -> bool:
    """Acquire the comparison lock with exclusive file creation.

    Both agents can notice that all submissions are present. The lock ensures
    that only one process writes comparison and feedback artifacts.
    """
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(json.dumps({"pid": os.getpid(), "created_at": utc_now()}) + "\n")
    return True


def build_dummy_feedback(agent: str, peer: str | None, paths: dict[str, Path]) -> dict[str, Any]:
    """Build placeholder feedback in the shape expected by repair skills."""
    return {
        "status": "ready",
        "agent": agent,
        "peer": peer,
        "feedback_file": str(paths["comparison_dir"] / f"feedback_for_{agent}.json"),
        "witnesses": [],
        "message": "Dummy broker feedback; Buchi disagreement comparison is not implemented yet.",
        "instruction": (
            "Treat future broker witnesses as disagreement evidence, not as oracle counterexamples. "
            "Revise only when the natural-language requirements justify it."
        ),
    }


def compute_dummy_comparison(
    paths: dict[str, Path],
    runs_root: Path,
    run_id: str,
    round_id: int,
    expected_agents: list[str],
) -> None:
    """Write dummy comparison artifacts and per-agent feedback files.

    Replace this function, or call into a future witness-generation module from
    here, when the Buchi language-difference implementation is ready.
    """
    atomic_write_json(paths["status"], {"status": "running", "started_at": utc_now()})
    comparison = {
        "status": "ready",
        "created_at": utc_now(),
        "mode": "dummy",
        "agents": expected_agents,
        "witnesses": [],
    }
    atomic_write_json(paths["comparison"], comparison)
    for agent in expected_agents:
        peers = [candidate for candidate in expected_agents if candidate != agent]
        peer = peers[0] if peers else None
        feedback_paths = build_paths(runs_root, run_id, round_id, agent)
        atomic_write_json(feedback_paths["feedback"], build_dummy_feedback(agent, peer, feedback_paths))
    atomic_write_json(paths["status"], {"status": "ready", "finished_at": utc_now()})


def maybe_compute_comparison(
    paths: dict[str, Path],
    runs_root: Path,
    run_id: str,
    round_id: int,
    expected_agents: list[str],
) -> None:
    """Run the comparison if all submissions are ready and no peer owns it."""
    if paths["status"].is_file():
        status = read_json(paths["status"])
        if status.get("status") in {"ready", "comparison_failed"}:
            return
    if not acquire_lock(paths["lock"]):
        return
    try:
        compute_dummy_comparison(paths, runs_root, run_id, round_id, expected_agents)
    except Exception as exc:  # noqa: BLE001 - surfaced as structured broker output.
        atomic_write_json(
            paths["status"],
            {"status": "comparison_failed", "finished_at": utc_now(), "error": str(exc)},
        )


def error_result(status: str, agent: str, message: str) -> dict[str, Any]:
    """Create a structured broker response for non-ready outcomes."""
    return {"status": status, "agent": agent, "message": message}


def submit_and_wait(args: argparse.Namespace) -> dict[str, Any]:
    """Register one agent's spec and wait for feedback or timeout."""
    validate_path_part(args.run_id, "run_id")
    validate_path_part(args.agent, "agent")
    for expected_agent in args.expected_agents:
        validate_path_part(expected_agent, "expected_agent")
    if args.agent not in args.expected_agents:
        return error_result("invalid_agent", args.agent, "Agent is not in --expected-agents.")

    spec_source = resolve_path(args.spec)
    if not spec_source.is_file():
        return error_result("missing_spec", args.agent, f"Spec file does not exist: {spec_source}")

    runs_root = resolve_path(args.runs_root)
    paths = build_paths(runs_root, args.run_id, args.round_id, args.agent)
    ensure_dirs(paths)

    # Keep a stable broker-owned copy. The submitting skill may continue editing
    # or deleting its temporary file after this call returns.
    copy_spec(spec_source, paths["spec"])
    atomic_write_json(
        paths["submission"],
        {
            "run_id": args.run_id,
            "round": args.round_id,
            "agent": args.agent,
            "original_spec_path": str(spec_source),
            "broker_spec_path": str(paths["spec"]),
            "submitted_at": utc_now(),
            "status": "submitted",
        },
    )

    deadline = time.monotonic() + args.timeout
    poll_interval = max(0.1, args.poll_interval)
    while time.monotonic() < deadline:
        # Fast path: another process already computed feedback for this agent.
        if paths["feedback"].is_file():
            return read_json(paths["feedback"])

        # Once both specs are present, either this process computes the
        # comparison or it observes that the peer process already took the lock.
        if all_submissions_exist(paths, args.expected_agents):
            maybe_compute_comparison(paths, runs_root, args.run_id, args.round_id, args.expected_agents)
        if paths["status"].is_file():
            status = read_json(paths["status"])
            if status.get("status") == "comparison_failed":
                return {
                    "status": "comparison_failed",
                    "agent": args.agent,
                    "message": status.get("error", "Comparison failed."),
                }
        time.sleep(poll_interval)

    return error_result(
        "timeout",
        args.agent,
        "Timed out waiting for peer submissions or comparison feedback.",
    )


def main() -> int:
    """Run the broker CLI and always print a JSON object for skill callers."""
    args = parse_args()
    try:
        if args.command == "submit-and-wait":
            result = submit_and_wait(args)
        else:
            result = {"status": "unknown_command", "message": args.command}
    except Exception as exc:  # noqa: BLE001 - CLI should return JSON for skill consumption.
        result = {"status": "broker_error", "message": str(exc)}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") in {"ready", "timeout"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
