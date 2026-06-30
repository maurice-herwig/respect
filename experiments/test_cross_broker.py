"""Tests for the file-based cross-agent broker."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from contextlib import contextmanager
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BROKER = REPO_ROOT / "experiments" / "cross_broker.py"
LEFT_SPEC = REPO_ROOT / "assets" / "examples" / "E2_execution" / "TrafficE2.spectra"
RIGHT_SPEC = REPO_ROOT / "assets" / "examples" / "A1_firstController" / "TrafficA1.spectra"
VERBOSE = os.environ.get("RESPECT_TEST_VERBOSE", "1") != "0"
KEEP_ARTIFACTS = os.environ.get("RESPECT_TEST_KEEP_ARTIFACTS", "0") == "1"
SHOW_FEEDBACK_JSON = os.environ.get("RESPECT_TEST_SHOW_FEEDBACK_JSON", "0") == "1"


def log(message: str) -> None:
    if VERBOSE:
        print(f"[cross-broker-test] {message}", flush=True)


@contextmanager
def broker_runs_root():
    """Yield a broker runs root, optionally preserving it for inspection."""
    tmp_root = REPO_ROOT / "tmp"
    tmp_root.mkdir(exist_ok=True)
    if KEEP_ARTIFACTS:
        runs_root = tmp_root / "cross-broker-inspect"
        if runs_root.exists():
            shutil.rmtree(runs_root)
        runs_root.mkdir(parents=True)
        try:
            yield runs_root
        finally:
            log(f"kept artifacts at {runs_root}")
        return

    with tempfile.TemporaryDirectory(prefix="cross-broker-test-", dir=tmp_root) as tmp_dir:
        yield Path(tmp_dir)


def log_json_file(label: str, path: Path) -> None:
    """Print a formatted JSON artifact when inspection output is enabled."""
    if not SHOW_FEEDBACK_JSON:
        return
    payload = json.loads(path.read_text(encoding="utf-8"))
    print(f"[cross-broker-test] {label} {path}", flush=True)
    print(json.dumps(payload, indent=2, sort_keys=True), flush=True)


class CrossBrokerIntegrationTests(unittest.TestCase):
    def run_submit(
        self,
        *,
        runs_root: Path,
        run_id: str,
        agent: str,
        spec: Path,
        output: dict[str, tuple[int, dict, str]],
    ) -> None:
        command = [
            sys.executable,
            str(BROKER),
            "submit-and-wait",
            "--run-id",
            run_id,
            "--round",
            "0",
            "--agent",
            agent,
            "--spec",
            str(spec),
            "--runs-root",
            str(runs_root),
            "--expected-agents",
            "agent_a",
            "agent_b",
            "--timeout",
            "180",
            "--poll-interval",
            "0.2",
        ]
        log(f"starting {agent}: {' '.join(command)}")
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=240,
        )
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            payload = {"status": "invalid_json", "stdout": completed.stdout}
        log(
            f"finished {agent}: return_code={completed.returncode}, "
            f"status={payload.get('status')}, stderr_len={len(completed.stderr)}"
        )
        output[agent] = (completed.returncode, payload, completed.stderr)

    def test_submit_and_wait_returns_buchi_witness_feedback(self):
        if not LEFT_SPEC.is_file() or not RIGHT_SPEC.is_file():
            self.skipTest("Traffic example Spectra files are unavailable.")

        with broker_runs_root() as runs_root:
            run_id = "broker-buchi-test"
            log(f"runs_root={runs_root}")
            log(f"left_spec={LEFT_SPEC}")
            log(f"right_spec={RIGHT_SPEC}")
            outputs: dict[str, tuple[int, dict, str]] = {}
            threads = [
                threading.Thread(
                    target=self.run_submit,
                    kwargs={
                        "runs_root": runs_root,
                        "run_id": run_id,
                        "agent": "agent_a",
                        "spec": LEFT_SPEC,
                        "output": outputs,
                    },
                ),
                threading.Thread(
                    target=self.run_submit,
                    kwargs={
                        "runs_root": runs_root,
                        "run_id": run_id,
                        "agent": "agent_b",
                        "spec": RIGHT_SPEC,
                        "output": outputs,
                    },
                ),
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=260)

            self.assertEqual({"agent_a", "agent_b"}, set(outputs))
            statuses = {agent: payload.get("status") for agent, (_code, payload, _stderr) in outputs.items()}
            log(f"agent statuses={statuses}")
            unavailable = {"spot_unavailable", "export_failed"}
            if any(status in unavailable for status in statuses.values()):
                self.skipTest(f"Buchi broker dependencies unavailable: {statuses}")

            for agent, (return_code, payload, stderr) in outputs.items():
                feedback_file = Path(payload["feedback_file"]) if payload.get("feedback_file") else None
                log(
                    f"{agent} feedback: witness_count={payload.get('witness_count')}, "
                    f"semantic_relation={payload.get('semantic_relation')}, "
                    f"accepted_by_you={len(payload.get('accepted_by_you_rejected_by_peer') or [])}, "
                    f"rejected_by_you={len(payload.get('rejected_by_you_accepted_by_peer') or [])}, "
                    f"feedback_file={payload.get('feedback_file')}"
                )
                if feedback_file and feedback_file.is_file():
                    log_json_file(f"{agent} feedback json:", feedback_file)
                self.assertEqual(return_code, 0, (agent, payload, stderr))
                self.assertEqual(payload.get("status"), "ready", (agent, payload))
                self.assertEqual(payload.get("agent"), agent, payload)
                self.assertIn(payload.get("semantic_relation"), {"equivalent", "different", "unknown"})
                self.assertIn("accepted_by_you_rejected_by_peer", payload)
                self.assertIn("rejected_by_you_accepted_by_peer", payload)
                self.assertIsInstance(payload["accepted_by_you_rejected_by_peer"], list)
                self.assertIsInstance(payload["rejected_by_you_accepted_by_peer"], list)
                self.assertNotIn("witnesses", payload)

            comparison_file = runs_root / run_id / "round-0" / "comparison" / "comparison.json"
            log(f"comparison_file={comparison_file}")
            self.assertTrue(comparison_file.is_file())
            log_json_file("comparison json:", comparison_file)
            comparison = json.loads(comparison_file.read_text(encoding="utf-8"))
            log(
                "comparison: "
                f"status={comparison.get('status')}, "
                f"mode={comparison.get('mode')}, "
                f"witness_count={comparison.get('witness_count')}"
            )
            accepted_words = comparison.get("accepted_words", {})
            for direction in ("left_minus_right", "right_minus_left"):
                words = (accepted_words.get(direction) or {}).get("words") or []
                log(f"{direction}: words={len(words)}")
            self.assertEqual(comparison.get("mode"), "buchi_disagreement_languages", comparison)
            self.assertEqual(comparison.get("status"), "success", comparison)
            self.assertEqual(comparison.get("semantic_relation"), "different", comparison)
            self.assertIn("left_minus_right", comparison.get("accepted_words", {}))
            self.assertIn("right_minus_left", comparison.get("accepted_words", {}))

            agent_a = outputs["agent_a"][1]
            agent_b = outputs["agent_b"][1]
            self.assertEqual(len(agent_a["accepted_by_you_rejected_by_peer"]), 1, agent_a)
            self.assertEqual(len(agent_a["rejected_by_you_accepted_by_peer"]), 0, agent_a)
            self.assertEqual(len(agent_b["accepted_by_you_rejected_by_peer"]), 0, agent_b)
            self.assertEqual(len(agent_b["rejected_by_you_accepted_by_peer"]), 1, agent_b)


if __name__ == "__main__":
    unittest.main()
