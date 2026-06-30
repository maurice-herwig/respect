"""Tests for the file-based cross-agent broker."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BROKER = REPO_ROOT / "experiments" / "cross_broker.py"
LEFT_SPEC = REPO_ROOT / "assets" / "examples" / "E2_execution" / "TrafficE2.spectra"
RIGHT_SPEC = REPO_ROOT / "assets" / "examples" / "A1_firstController" / "TrafficA1.spectra"


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
        output[agent] = (completed.returncode, payload, completed.stderr)

    def test_submit_and_wait_returns_buchi_witness_feedback(self):
        if not LEFT_SPEC.is_file() or not RIGHT_SPEC.is_file():
            self.skipTest("Traffic example Spectra files are unavailable.")

        tmp_root = REPO_ROOT / "tmp"
        tmp_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="cross-broker-test-", dir=tmp_root) as tmp_dir:
            runs_root = Path(tmp_dir)
            run_id = "broker-buchi-test"
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
            unavailable = {"spot_unavailable", "export_failed"}
            if any(status in unavailable for status in statuses.values()):
                self.skipTest(f"Buchi broker dependencies unavailable: {statuses}")

            for agent, (return_code, payload, stderr) in outputs.items():
                self.assertEqual(return_code, 0, (agent, payload, stderr))
                self.assertEqual(payload.get("status"), "ready", (agent, payload))
                self.assertEqual(payload.get("agent"), agent, payload)
                self.assertIn("witnesses", payload)
                self.assertIsInstance(payload["witnesses"], list)

            comparison_file = runs_root / run_id / "round-0" / "comparison" / "comparison.json"
            self.assertTrue(comparison_file.is_file())
            comparison = json.loads(comparison_file.read_text(encoding="utf-8"))
            self.assertEqual(comparison.get("mode"), "buchi_disagreement_languages", comparison)
            self.assertEqual(comparison.get("status"), "success", comparison)
            self.assertIn("left_minus_right", comparison.get("accepted_words", {}))
            self.assertIn("right_minus_left", comparison.get("accepted_words", {}))


if __name__ == "__main__":
    unittest.main()
