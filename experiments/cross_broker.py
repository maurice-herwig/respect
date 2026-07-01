#!/usr/bin/env python3
"""Minimal file-based broker for cross-agent repair experiments.

The broker lets two independently running skills synchronize without a long
running server. Each skill submits its current Spectra file, blocks until the
peer has submitted too, and then receives JSON feedback. The comparison uses
the Buchi disagreement-language helper to report directed witness words when
one submitted specification accepts behavior that the other does not.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
DEFAULT_RUNS_ROOT = REPO_ROOT / "experiments" / "cross_runs"
DEFAULT_EXPECTED_AGENTS = ("agent_a", "agent_b")
DEFAULT_MAX_WITNESSES_PER_DIRECTION = 3


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


def repo_relative_or_absolute(path: Path) -> str:
    """Return a repo-relative path when possible, otherwise an absolute path."""
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path.resolve())


def words_for_agent(
    *,
    agent: str,
    left_agent: str,
    right_agent: str,
    left_words: dict[str, Any],
    right_words: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return directed disagreement words from the submitting agent's view."""
    if agent == left_agent:
        return list(left_words.get("words") or []), list(right_words.get("words") or [])
    if agent == right_agent:
        return list(right_words.get("words") or []), list(left_words.get("words") or [])
    return [], []


def rename_letter_variables(letter: dict[str, Any], mapping: dict[str, str]) -> dict[str, Any]:
    """Return one valuation with variable names translated through mapping."""
    return {mapping.get(name, name): value for name, value in letter.items()}


def translate_word_variables(word: dict[str, Any], mapping: dict[str, str]) -> dict[str, Any]:
    """Translate prefix/loop valuation variable names while preserving metadata."""
    translated = dict(word)
    for segment in ("prefix", "loop"):
        translated[segment] = [
            rename_letter_variables(letter, mapping)
            for letter in (word.get(segment) or [])
        ]
    return translated


def translate_words_for_agent(
    words: list[dict[str, Any]],
    *,
    agent: str,
    right_agent: str,
    left_to_right_mapping: dict[str, str],
) -> list[dict[str, Any]]:
    """Translate canonical-left witness words back to the receiver's alphabet."""
    if agent != right_agent or not left_to_right_mapping:
        return words
    return [translate_word_variables(word, left_to_right_mapping) for word in words]


def strip_raw_from_word(word: dict[str, Any]) -> dict[str, Any]:
    """Return a skill-facing word payload without automaton-debug metadata."""
    return {key: value for key, value in word.items() if key != "raw"}


def skill_facing_words(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove internal debug fields from words written to agent feedback files."""
    return [strip_raw_from_word(word) for word in words]


def semantic_relation(left_words: dict[str, Any], right_words: dict[str, Any]) -> str:
    """Classify the comparison from the extracted directed witness words."""
    if left_words.get("status") == "empty" and right_words.get("status") == "empty":
        return "equivalent"
    if left_words.get("words") or right_words.get("words"):
        return "different"
    return "unknown"


def build_feedback(
    *,
    agent: str,
    peer: str | None,
    paths: dict[str, Path],
    comparison: dict[str, Any],
    accepted_by_you_rejected_by_peer: list[dict[str, Any]],
    rejected_by_you_accepted_by_peer: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build per-agent feedback in the shape expected by repair skills."""
    status = comparison.get("status", "other")
    if status == "success":
        status = "ready"
    witness_count = len(accepted_by_you_rejected_by_peer) + len(rejected_by_you_accepted_by_peer)
    return {
        "status": status,
        "agent": agent,
        "peer": peer,
        "feedback_file": str(paths["comparison_dir"] / f"feedback_for_{agent}.json"),
        "comparison_file": str(paths["comparison"]),
        "semantic_relation": comparison.get("semantic_relation", "unknown"),
        "accepted_by_you_rejected_by_peer": skill_facing_words(accepted_by_you_rejected_by_peer),
        "rejected_by_you_accepted_by_peer": skill_facing_words(rejected_by_you_accepted_by_peer),
        "witness_count": witness_count,
        "message": comparison.get("message") or comparison.get("error") or "Buchi disagreement comparison completed.",
    }


def feedback_translation_mapping(comparison: dict[str, Any]) -> dict[str, str]:
    """Return left-agent variable names to right-agent variable names."""
    mapping = ((comparison.get("language_difference") or {}).get("signature_mapping") or {})
    if not mapping:
        return {}
    left_to_right: dict[str, str] = {}
    for owner in ("env", "sys"):
        for left_name, right_name in (mapping.get(owner) or {}).items():
            left_to_right[left_name] = right_name
    return left_to_right


def accepted_words_from_difference_hoa(path: Path, max_words: int) -> dict[str, Any]:
    """Extract accepted ultimately-periodic words from a difference HOA file."""
    from evaluation.buchi import disagreement_languages

    if not path.is_file():
        return {"status": "missing_hoa", "hoa_file": repo_relative_or_absolute(path), "words": []}
    try:
        return disagreement_languages.accepted_words_from_hoa(path, max_words=max_words)
    except SystemExit as exc:
        return {
            "status": "word_extraction_failed",
            "hoa_file": repo_relative_or_absolute(path),
            "error": str(exc),
            "words": [],
        }
    except Exception as exc:  # noqa: BLE001 - reported as structured broker feedback.
        return {
            "status": "word_extraction_failed",
            "hoa_file": repo_relative_or_absolute(path),
            "error": f"{type(exc).__name__}: {exc}",
            "words": [],
        }


def compute_buchi_comparison(
    paths: dict[str, Path],
    runs_root: Path,
    run_id: str,
    round_id: int,
    expected_agents: list[str],
) -> None:
    """Compute directed Buchi language differences and write feedback files."""
    from evaluation.buchi import disagreement_languages

    atomic_write_json(paths["status"], {"status": "running", "started_at": utc_now()})
    if len(expected_agents) != 2:
        raise ValueError("Buchi cross-broker comparison currently requires exactly two expected agents.")

    left_agent, right_agent = expected_agents
    left_paths = build_paths(runs_root, run_id, round_id, left_agent)
    right_paths = build_paths(runs_root, run_id, round_id, right_agent)
    left_spec = left_paths["spec"]
    right_spec = right_paths["spec"]
    comparison_output_dir = paths["comparison_dir"] / "buchi"

    result = disagreement_languages.compute_spectra_language_differences(
        left_spectra=left_spec,
        right_spectra=right_spec,
        output_dir=comparison_output_dir,
        jar_path=disagreement_languages.DEFAULT_JAR,
        write_difference_hoa=True,
        signature_mapping="llm",
    )

    left_words: dict[str, Any] = {"status": "not_computed", "words": []}
    right_words: dict[str, Any] = {"status": "not_computed", "words": []}
    if result.get("status") == "success":
        left_words = accepted_words_from_difference_hoa(
            comparison_output_dir / "left_minus_right.hoa",
            DEFAULT_MAX_WITNESSES_PER_DIRECTION,
        )
        right_words = accepted_words_from_difference_hoa(
            comparison_output_dir / "right_minus_left.hoa",
            DEFAULT_MAX_WITNESSES_PER_DIRECTION,
        )

    comparison = {
        "status": result.get("status"),
        "created_at": utc_now(),
        "mode": "buchi_disagreement_languages",
        "agents": expected_agents,
        "left_agent": left_agent,
        "right_agent": right_agent,
        "left_spectra": repo_relative_or_absolute(left_spec),
        "right_spectra": repo_relative_or_absolute(right_spec),
        "language_difference": result,
        "accepted_words": {
            "left_minus_right": left_words,
            "right_minus_left": right_words,
        },
        "semantic_relation": semantic_relation(left_words, right_words)
        if result.get("status") == "success"
        else "unknown",
        "witness_count": len(left_words.get("words") or []) + len(right_words.get("words") or []),
        "message": "Buchi disagreement comparison completed."
        if result.get("status") == "success"
        else result.get("error", "Buchi disagreement comparison did not produce witness feedback."),
    }
    left_to_right_mapping = feedback_translation_mapping(comparison)
    atomic_write_json(paths["comparison"], comparison)
    for agent in expected_agents:
        peers = [candidate for candidate in expected_agents if candidate != agent]
        peer = peers[0] if peers else None
        feedback_paths = build_paths(runs_root, run_id, round_id, agent)
        accepted_by_you, rejected_by_you = words_for_agent(
            agent=agent,
            left_agent=left_agent,
            right_agent=right_agent,
            left_words=left_words,
            right_words=right_words,
        )
        accepted_by_you = translate_words_for_agent(
            accepted_by_you,
            agent=agent,
            right_agent=right_agent,
            left_to_right_mapping=left_to_right_mapping,
        )
        rejected_by_you = translate_words_for_agent(
            rejected_by_you,
            agent=agent,
            right_agent=right_agent,
            left_to_right_mapping=left_to_right_mapping,
        )
        atomic_write_json(
            feedback_paths["feedback"],
            build_feedback(
                agent=agent,
                peer=peer,
                paths=feedback_paths,
                comparison=comparison,
                accepted_by_you_rejected_by_peer=accepted_by_you,
                rejected_by_you_accepted_by_peer=rejected_by_you,
            ),
        )
    final_status = "ready" if result.get("status") == "success" else result.get("status", "comparison_failed")
    atomic_write_json(paths["status"], {"status": final_status, "finished_at": utc_now()})


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
        compute_buchi_comparison(paths, runs_root, run_id, round_id, expected_agents)
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
