#!/usr/bin/env python3
"""Regression tests for the Buchi/Markov-chain distance helpers."""

from __future__ import annotations

import math
import shutil
import subprocess
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

from evaluation.buchi import buchi_distance
from evaluation.buchi import bounded_semantic_distance
from evaluation.evaluate_branched_runs import evaluate_distance


REPO_ROOT = Path(__file__).resolve().parents[2]
HOA_JAR = REPO_ROOT / "assets" / "cli_with_hoa_export" / "spectra-cli.jar"


def require_spot_or_skip(test_case: unittest.TestCase):
    try:
        return buchi_distance.require_spot()
    except SystemExit as exc:
        test_case.skipTest(str(exc))


def require_java_and_hoa_jar_or_skip(test_case: unittest.TestCase) -> None:
    if shutil.which("java") is None:
        test_case.skipTest("Java is required for Spectra HOA export.")
    if not HOA_JAR.is_file():
        test_case.skipTest(f"Spectra HOA export jar not found: {HOA_JAR}")


class BuchiDistanceFormulaTests(unittest.TestCase):
    """Exercise the pure Spot distance on formulas with known outcomes."""

    def test_identical_automata_have_zero_distance(self) -> None:
        spot = require_spot_or_skip(self)
        automaton = spot.translate("G(req -> F grant)", "BA", "deterministic")

        distance = buchi_distance.compute_buchi_distance(automaton, automaton)

        self.assertTrue(math.isclose(distance, 0.0, abs_tol=1e-12), distance)

    def test_true_vs_false_has_distance_one(self) -> None:
        spot = require_spot_or_skip(self)
        true_automaton = spot.translate("1", "BA", "deterministic")
        false_automaton = spot.translate("0", "BA", "deterministic")

        distance = buchi_distance.compute_buchi_distance(true_automaton, false_automaton)

        self.assertTrue(math.isclose(distance, 1.0, abs_tol=1e-12), distance)

    def test_prefix_difference_has_distance_between_zero_and_one(self) -> None:
        spot = require_spot_or_skip(self)
        unconstrained = spot.translate("G(req | !req)", "BA", "deterministic")
        initially_req = spot.translate("req", "BA", "deterministic")

        distance = buchi_distance.compute_buchi_distance(unconstrained, initially_req)

        self.assertGreater(distance, 0.0)
        self.assertLess(distance, 1.0)

    def test_bounded_semantic_distance_reports_prefix_mismatch(self) -> None:
        spot = require_spot_or_skip(self)
        eventually_req = spot.translate("F(req)", "BA", "deterministic")
        always_req = spot.translate("G(req)", "BA", "deterministic")

        result = bounded_semantic_distance.compute_bounded_semantic_distance(
            eventually_req,
            always_req,
            depth=4,
            mode="exhaustive",
        )

        self.assertGreater(result["mismatch_rate"], 0.0)
        self.assertLess(result["mismatch_rate"], 1.0)


class SpectraDistanceIntegrationTests(unittest.TestCase):
    """Run small Spectra files through the same export/normalization pipeline."""

    def setUp(self) -> None:
        require_spot_or_skip(self)
        require_java_and_hoa_jar_or_skip(self)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write_spectra(self, name: str, guarantee: str) -> Path:
        path = self.root / f"{name}.spectra"
        path.write_text(
            "\n".join(
                [
                    f"spec {name}",
                    "",
                    "sys boolean grant;",
                    "",
                    f"gar {guarantee};",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        self.assert_valid_spectra(path)
        return path

    def assert_valid_spectra(self, path: Path) -> None:
        completed = subprocess.run(
            ["java", "-jar", str(HOA_JAR), "-i", str(path), "--jtlv"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        if completed.returncode != 0:
            self.fail(f"Spectra fixture is invalid: {path}\n{completed.stdout}\n{completed.stderr}")

    def distance_between(self, left: Path, right: Path) -> dict:
        args = Namespace(
            force=True,
            include_raw_output=False,
            raw_output_tail_chars=1000,
        )
        settings = SimpleNamespace(
            max_states=100_000,
            timeout=30.0,
            jtlv=True,
            normalize_hoa=True,
            add_rejecting_sink=False,
            determinize=True,
            signature_mapping="strict",
            signature_mapping_file=str(REPO_ROOT / "evaluation" / "signature_mappings.jsonl"),
            mapping_model=None,
            mapping_base_url=None,
            mapping_timeout=30.0,
            force_signature_mapping=False,
            bounded_semantic_distance=True,
            bounded_depth=10,
            bounded_mode="random",
            bounded_samples=1000,
            bounded_seed=1,
            bounded_max_prefixes=None,
            debug_distance=False,
            jar_sha256=None,
        )
        return evaluate_distance(
            source_spectra=left,
            generated_spectra=right,
            output_dir=self.root / "distance" / f"{left.stem}_vs_{right.stem}",
            args=args,
            settings=settings,
            jar_path=HOA_JAR,
        )

    def test_identical_spectra_have_zero_distance(self) -> None:
        spec = self.write_spectra("Same", "true")

        result = self.distance_between(spec, spec)

        self.assertEqual(result["status"], "success", result)
        self.assertTrue(math.isclose(result["distance"], 0.0, abs_tol=1e-12), result)

    def test_persistent_safety_spectra_difference_has_bounded_mismatch(self) -> None:
        true_spec = self.write_spectra("AlwaysTrue", "true")
        always_grant_spec = self.write_spectra("AlwaysGrant", "alw grant")

        result = self.distance_between(true_spec, always_grant_spec)

        self.assertEqual(result["status"], "success", result)
        bounded = result.get("bounded_semantic_distance") or {}
        self.assertGreater(bounded.get("mismatch_rate"), 0.0, result)
        self.assertLessEqual(bounded.get("mismatch_rate"), 1.0, result)


if __name__ == "__main__":
    unittest.main()
