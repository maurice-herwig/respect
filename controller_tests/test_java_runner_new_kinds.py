#!/usr/bin/env python3
"""End-to-end tests for Java controller-test runner feedback on new test kinds."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from controller_tests.compile_test_plan import compile_rtest


REPO_ROOT = Path(__file__).resolve().parents[1]
EXECUTOR_JAR = REPO_ROOT / "assets" / "examples" / "E2_execution" / "executor.jar"
CONTROLLER_DIR = REPO_ROOT / "assets" / "examples" / "E2_execution" / "out" / "jit"
CLASSES_DIR = REPO_ROOT / "controller_tests" / "build" / "classes"
FAILING_PLAN = REPO_ROOT / "controller_tests" / "examples" / "traffic_e2_new_kinds_failing_plan.json"
NEW_KINDS_RTEST = REPO_ROOT / "controller_tests" / "examples" / "traffic_e2_new_kinds_plan.rtest"


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

        completed = self.run_java_runner(FAILING_PLAN)

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

    def test_new_kinds_rtest_compiles_and_runs_through_java_runner(self):
        """The intended Method-3 path should work: `.rtest` -> JSON -> Java runner."""

        plan = compile_rtest(NEW_KINDS_RTEST.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "tmp") as temp_dir:
            compiled_plan = Path(temp_dir) / "compiled-new-kinds.json"
            compiled_plan.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")

            completed = self.run_java_runner(compiled_plan)

        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        payload = json.loads(completed.stdout.splitlines()[-1])
        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["passed"], 6)
        self.assertEqual(payload["failed"], 0)
        self.assertEqual(payload["total"], 6)
        self.assertTrue(all("requirement" in result for result in payload["results"]))

    def test_missing_requirement_fails_one_test_and_allows_later_tests_to_run(self):
        """A missing requirement should be a local test failure, not a run abort."""

        plan = {
            "controller_dir": "assets/examples/E2_execution/out/jit",
            "spec_name": "TrafficE2",
            "spectra_file": "assets/examples/E2_execution/TrafficE2.spectra",
            "environment": ["carA", "carB"],
            "system": ["greenA", "greenB"],
            "outputs": ["greenA", "greenB"],
            "tests": [
                {
                    "kind": "exclusion",
                    "name": "missing_requirement_test",
                    "trace": [{"carA": "true", "carB": "false"}],
                    "forbidden": {"greenA": "true", "greenB": "true"},
                },
                {
                    "kind": "invariant",
                    "name": "still_runs_after_missing_requirement",
                    "requirement": "The supplied input valuation should be visible in the observed combined step.",
                    "trace": [{"carA": "true", "carB": "false"}],
                    "condition": {"carA": "true", "carB": "false"},
                },
            ],
        }
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "tmp") as temp_dir:
            plan_path = Path(temp_dir) / "missing-requirement.json"
            plan_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")

            completed = self.run_java_runner(plan_path)

        self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
        payload = json.loads(completed.stdout.splitlines()[-1])
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["passed"], 1)
        self.assertEqual(payload["failed"], 1)
        self.assertEqual(payload["total"], 2)
        self.assertEqual(payload["results"][0]["details"]["failure_code"], "missing_requirement")
        self.assertFalse(payload["results"][0]["passed"])
        self.assertTrue(payload["results"][1]["passed"])
        self.assertEqual(payload["results"][1]["name"], "still_runs_after_missing_requirement")

    def run_java_runner(self, plan_path: Path) -> subprocess.CompletedProcess[str]:
        """Run the Java TestRunner against a plan and return the completed process."""

        return subprocess.run(
            [
                "java",
                "-Djava.library.path=.",
                "-cp",
                f"{CLASSES_DIR};{EXECUTOR_JAR}",
                "respect.controller_tests.TestRunner",
                "--plan",
                str(plan_path),
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=120,
        )


if __name__ == "__main__":
    unittest.main()
