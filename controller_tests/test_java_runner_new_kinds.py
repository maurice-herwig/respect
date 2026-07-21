#!/usr/bin/env python3
"""End-to-end tests for Java controller-test runner feedback on new test kinds."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
EXECUTOR_JAR = REPO_ROOT / "assets" / "examples" / "E2_execution" / "executor.jar"
CONTROLLER_DIR = REPO_ROOT / "assets" / "examples" / "E2_execution" / "out" / "jit"
CLASSES_DIR = REPO_ROOT / "controller_tests" / "build" / "classes"
FAILING_PLAN = REPO_ROOT / "controller_tests" / "examples" / "traffic_e2_new_kinds_failing_plan.json"


class JavaRunnerNewKindsTests(unittest.TestCase):
    """Smoke-test structured failure codes emitted by the Java runner."""

    @classmethod
    def setUpClass(cls):
        if not EXECUTOR_JAR.is_file():
            raise unittest.SkipTest(f"executor.jar is unavailable: {EXECUTOR_JAR}")
        if not CONTROLLER_DIR.is_dir():
            raise unittest.SkipTest(f"Synthesized TrafficE2 controller is unavailable: {CONTROLLER_DIR}")
        if not CLASSES_DIR.is_dir():
            raise unittest.SkipTest("controller_tests/build/classes is unavailable; run the Java build first.")

    def test_new_kinds_failing_plan_reports_expected_failure_codes_and_runs_all_tests(self):
        """Every new test kind should produce its own structured failure code."""

        completed = subprocess.run(
            [
                "java",
                "-Djava.library.path=.",
                "-cp",
                f"{CLASSES_DIR};{EXECUTOR_JAR}",
                "respect.controller_tests.TestRunner",
                "--plan",
                str(FAILING_PLAN),
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=120,
        )

        self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
        payload = json.loads(completed.stdout.splitlines()[-1])
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["passed"], 0)
        self.assertEqual(payload["failed"], 6)
        self.assertEqual(payload["total"], 6)
        self.assertEqual(
            {result["details"]["failure_code"] for result in payload["results"]},
            {
                "mutual_exclusion_violation",
                "one_hot_violation",
                "invariant_violation",
                "state_sequence_mismatch",
                "persistence_violation",
                "response_absence_violation",
            },
        )
        self.assertTrue(all("requirement" in result for result in payload["results"]))


if __name__ == "__main__":
    unittest.main()
