#!/usr/bin/env python3
"""Tests for the ReSpect controller-test DSL compiler.

The compiler is intended to be used by both humans and Method-3 agents, so the
tests focus on stable output shape and clear validation failures rather than
exercising the Java controller runner itself.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from controller_tests.compile_test_plan import DslError, compile_rtest


REPO_ROOT = Path(__file__).resolve().parents[1]


class RTestCompilerTests(unittest.TestCase):
    """Unit tests for representative `.rtest` compiler behavior."""

    maxDiff = None

    def test_compiles_traffic_example_to_existing_json_plan(self):
        """The checked-in DSL example should compile to the checked-in JSON plan."""

        source = (REPO_ROOT / "controller_tests" / "examples" / "traffic_e2_plan.rtest").read_text(encoding="utf-8")
        expected = json.loads(
            (REPO_ROOT / "controller_tests" / "examples" / "traffic_e2_plan.json").read_text(encoding="utf-8")
        )

        self.assertEqual(compile_rtest(source), expected)

    def test_translates_top_level_environment_and_system_to_runner_outputs(self):
        """Top-level DSL ownership metadata should be preserved and normalized."""

        source = textwrap.dedent("""
        controller_dir generated/out/jit
        spec_name Door
        spectra_file generated/Door.spectra
        environment request, reset
        system grant, alarm

        test declared:
          kind variable_ownership
        """)

        plan = compile_rtest(source)

        self.assertEqual(plan["controller_dir"], "generated/out/jit")
        self.assertEqual(plan["spec_name"], "Door")
        self.assertEqual(plan["spectra_file"], "generated/Door.spectra")
        self.assertEqual(plan["environment"], ["request", "reset"])
        self.assertEqual(plan["system"], ["grant", "alarm"])
        self.assertEqual(plan["outputs"], ["grant", "alarm"])
        self.assertEqual(
            plan["tests"],
            [
                {
                    "name": "declared",
                    "kind": "variable_ownership",
                    "env": ["request", "reset"],
                    "sys": ["grant", "alarm"],
                }
            ],
        )

    def test_translates_legacy_outputs_alias_to_system_and_outputs(self):
        """Old DSL files using `outputs` should still compile to the new shape."""

        source = textwrap.dedent("""
        controller_dir out/jit
        spec_name Fixture
        spectra_file fixture.spectra
        environment request
        outputs grant

        test declared:
          kind variable_ownership
        """)

        plan = compile_rtest(source)

        self.assertEqual(plan["system"], ["grant"])
        self.assertEqual(plan["outputs"], ["grant"])
        self.assertEqual(plan["tests"][0]["sys"], ["grant"])

    def test_translates_trace_block_and_valuations_to_json_strings(self):
        """Concrete traces and expected valuations should become JSON string maps."""

        source = textwrap.dedent("""
        controller_dir out/jit
        spec_name Fixture
        spectra_file fixture.spectra
        environment request, level
        system grant

        test concrete_response:
          kind eventually_response
          trace:
            request=true, level=0
            request=true, level=1
          when request=true
          eventually grant=true
          within_steps 2
          require_closed_obligations true
        """)

        plan = compile_rtest(source)
        test = plan["tests"][0]

        self.assertEqual(
            test,
            {
                "name": "concrete_response",
                "kind": "eventually_response",
                "trace": [
                    {"request": "true", "level": "0"},
                    {"request": "true", "level": "1"},
                ],
                "when": {"request": "true"},
                "eventually": {"grant": "true"},
                "within_steps": 2,
                "require_closed_obligations": True,
            },
        )

    def test_compiles_exhaustive_domains_block(self):
        """Exploration domains should become the JSON `env` domain map."""

        source = textwrap.dedent("""
        controller_dir out/jit
        spec_name Fixture
        spectra_file fixture.spectra
        environment request, reset
        system grant

        test no_grant_without_request:
          kind always_implication
          mode exhaustive
          max_depth 3
          max_paths 64
          domains:
            request false, true
            reset false, true
          when request=false
          then grant=false
        """)

        plan = compile_rtest(source)

        test = plan["tests"][0]
        self.assertEqual(test["env"], {"request": ["false", "true"], "reset": ["false", "true"]})
        self.assertEqual(plan["outputs"], ["grant"])
        self.assertEqual(test["mode"], "exhaustive")
        self.assertEqual(test["max_depth"], 3)
        self.assertEqual(test["then"], {"grant": "false"})

    def test_translates_random_exploration_settings(self):
        """Random exploration settings should compile without losing bounds."""

        source = textwrap.dedent("""
        controller_dir out/jit
        spec_name Fixture
        spectra_file fixture.spectra
        environment request, reset
        system error

        test random_no_error:
          kind exclusion
          mode random
          runs 25
          max_depth 8
          seed 99
          domains:
            request false, true
            reset false, true
          forbidden error=true
        """)

        plan = compile_rtest(source)

        self.assertEqual(
            plan["tests"][0],
            {
                "name": "random_no_error",
                "kind": "exclusion",
                "mode": "random",
                "runs": 25,
                "max_depth": 8,
                "seed": 99,
                "env": {
                    "request": ["false", "true"],
                    "reset": ["false", "true"],
                },
                "forbidden": {"error": "true"},
            },
        )

    def test_translates_test_level_environment_system_aliases(self):
        """Test-block `environment` and `system` aliases should become `env`/`sys`."""

        source = textwrap.dedent("""
        controller_dir out/jit
        spec_name Fixture
        spectra_file fixture.spectra
        environment request, cancel
        system grant, alarm

        test selected_ownership:
          kind variable_ownership
          environment request
          system grant
        """)

        plan = compile_rtest(source)

        self.assertEqual(
            plan["tests"][0],
            {
                "name": "selected_ownership",
                "kind": "variable_ownership",
                "env": ["request"],
                "sys": ["grant"],
            },
        )

    def test_rejects_trace_test_without_trace_block(self):
        """Trace-mode safety tests need concrete inputs to exercise the controller."""

        source = textwrap.dedent("""
        controller_dir out/jit
        spec_name Fixture
        spectra_file fixture.spectra
        environment request
        system grant

        test bad:
          kind exclusion
          forbidden grant=true
        """)

        with self.assertRaisesRegex(DslError, "requires a trace"):
            compile_rtest(source)

    def test_unknown_key_error_carries_code_line_and_hint(self):
        """Misspelled keys should produce repair-oriented structured metadata."""

        source = textwrap.dedent("""
        controller_dir out/jit
        spec_name Fixture
        spectra_file fixture.spectra
        environment request
        system grant

        test bad_key:
          kind exclusion
          trace:
            request=true
          forbid grant=true
        """)

        with self.assertRaises(DslError) as raised:
            compile_rtest(source)

        self.assertEqual(raised.exception.code, "unknown_key")
        self.assertEqual(raised.exception.line, 12)
        self.assertIn("forbidden", raised.exception.hint)

    def test_cli_writes_json_output(self):
        """The command-line compiler should create a JSON file for the Java runner."""

        source = textwrap.dedent("""
        controller_dir out/jit
        spec_name Fixture
        spectra_file fixture.spectra
        environment request
        system grant

        test declared:
          kind variable_ownership
        """)
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "plan.rtest"
            output_path = Path(temp_dir) / "plan.json"
            input_path.write_text(source, encoding="utf-8")

            completed = subprocess.run(
                [sys.executable, str(REPO_ROOT / "controller_tests" / "compile_test_plan.py"), str(input_path), "-o", str(output_path)],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            plan = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(plan["tests"][0]["name"], "declared")
            self.assertEqual(plan["tests"][0]["env"], ["request"])
            self.assertEqual(plan["tests"][0]["sys"], ["grant"])

    def test_cli_writes_success_diagnostics_json(self):
        """Successful compiles should write diagnostics that report success."""

        source = textwrap.dedent("""
        controller_dir out/jit
        spec_name Fixture
        spectra_file fixture.spectra
        environment request
        system grant

        test declared:
          kind variable_ownership
        """)
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "plan.rtest"
            diagnostics_path = Path(temp_dir) / "diagnostics.json"
            input_path.write_text(source, encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "controller_tests" / "compile_test_plan.py"),
                    str(input_path),
                    "--check",
                    "--diagnostics-json",
                    str(diagnostics_path),
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(diagnostics_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "success")
            self.assertEqual(payload["compiled_tests"], 1)
            self.assertEqual(payload["errors"], [])

    def test_cli_writes_failure_diagnostics_json_with_context(self):
        """Failed compiles should write structured diagnostics for LLM repair."""

        source = textwrap.dedent("""
        controller_dir out/jit
        spec_name Fixture
        spectra_file fixture.spectra
        environment request
        system grant

        test missing_forbidden:
          kind exclusion
          trace:
            request=true
        """)
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "plan.rtest"
            diagnostics_path = Path(temp_dir) / "diagnostics.json"
            input_path.write_text(source, encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "controller_tests" / "compile_test_plan.py"),
                    str(input_path),
                    "--check",
                    "--diagnostics-json",
                    str(diagnostics_path),
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 2)
            payload = json.loads(diagnostics_path.read_text(encoding="utf-8"))
            error = payload["errors"][0]
            self.assertEqual(payload["status"], "dsl_syntax_error")
            self.assertEqual(error["code"], "missing_required_field")
            self.assertEqual(error["line"], 8)
            self.assertIn("forbidden", error["hint"])
            self.assertTrue(any(item["is_error_line"] for item in error["context"]))
            self.assertIn("Repair only the .rtest", payload["repair_instruction"])


if __name__ == "__main__":
    unittest.main()
