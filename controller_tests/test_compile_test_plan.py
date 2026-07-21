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

    def test_compiles_traffic_example_to_existing_json_plan(self):
        """The checked-in DSL example should compile to the checked-in JSON plan."""

        source = (REPO_ROOT / "controller_tests" / "examples" / "traffic_e2_plan.rtest").read_text(encoding="utf-8")
        expected = json.loads(
            (REPO_ROOT / "controller_tests" / "examples" / "traffic_e2_plan.json").read_text(encoding="utf-8")
        )

        self.assertEqual(compile_rtest(source), expected)

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


if __name__ == "__main__":
    unittest.main()
