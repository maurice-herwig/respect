#!/usr/bin/env python3
"""Unit tests for controller output-distance metrics."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from evaluation.evaluate_controller_distances import (
    aggregate_distance_results,
    compare_trace_outputs,
    exhaustive_traces,
    parse_spectra_signature,
    random_traces,
    signatures_compatible,
)
from evaluation.signature_mapping import apply_hoa_ap_mapping, validate_mapping


def runner_output(traces):
    return {
        "status": "success",
        "total_traces": len(traces),
        "traces": traces,
    }


def step(inputs, outputs):
    return {
        "inputs": inputs,
        "outputs": outputs,
    }


class ControllerDistanceMetricTests(unittest.TestCase):
    def test_compare_trace_outputs_zero_distance_for_identical_outputs(self):
        traces = [
            [
                step({"i": "false"}, {"x": "false", "y": "true"}),
                step({"i": "true"}, {"x": "true", "y": "true"}),
            ]
        ]

        result = compare_trace_outputs(runner_output(traces), runner_output(traces), ["x", "y"])

        self.assertEqual(result["total_traces"], 1)
        self.assertEqual(result["mismatching_traces"], 0)
        self.assertEqual(result["trace_mismatch_rate"], 0.0)
        self.assertEqual(result["mismatching_steps"], 0)
        self.assertEqual(result["step_mismatch_rate"], 0.0)
        self.assertEqual(result["mismatching_output_comparisons"], 0)
        self.assertEqual(result["output_hamming_mismatch_rate"], 0.0)
        self.assertIsNone(result["first_mismatch"])

    def test_compare_trace_outputs_known_mismatch_rates(self):
        left = runner_output(
            [
                [
                    step({"i": "0"}, {"x": "0", "y": "0"}),
                    step({"i": "1"}, {"x": "1", "y": "0"}),
                    step({"i": "2"}, {"x": "1", "y": "1"}),
                ],
                [
                    step({"i": "3"}, {"x": "0", "y": "0"}),
                    step({"i": "4"}, {"x": "0", "y": "1"}),
                    step({"i": "5"}, {"x": "0", "y": "1"}),
                ],
            ]
        )
        right = runner_output(
            [
                [
                    step({"i": "0"}, {"x": "0", "y": "0"}),
                    step({"i": "1"}, {"x": "0", "y": "0"}),
                    step({"i": "2"}, {"x": "1", "y": "1"}),
                ],
                [
                    step({"i": "3"}, {"x": "0", "y": "0"}),
                    step({"i": "4"}, {"x": "1", "y": "0"}),
                    step({"i": "5"}, {"x": "0", "y": "1"}),
                ],
            ]
        )

        result = compare_trace_outputs(left, right, ["x", "y"])

        self.assertEqual(result["total_traces"], 2)
        self.assertEqual(result["mismatching_traces"], 2)
        self.assertEqual(result["trace_mismatch_rate"], 1.0)
        self.assertEqual(result["total_steps"], 6)
        self.assertEqual(result["mismatching_steps"], 2)
        self.assertAlmostEqual(result["step_mismatch_rate"], 2 / 6)
        self.assertEqual(result["total_output_comparisons"], 12)
        self.assertEqual(result["mismatching_output_comparisons"], 3)
        self.assertAlmostEqual(result["output_hamming_mismatch_rate"], 3 / 12)
        self.assertEqual(result["first_mismatch"]["trace_index"], 0)
        self.assertEqual(result["first_mismatch"]["step_index"], 1)
        self.assertEqual(result["first_mismatch"]["differing_outputs"], ["x"])

    def test_compare_trace_outputs_rejects_misaligned_runner_outputs(self):
        left = runner_output([[step({"i": "0"}, {"x": "0"})]])
        right = runner_output([])

        with self.assertRaises(ValueError):
            compare_trace_outputs(left, right, ["x"])

    def test_aggregate_distance_results_sums_counts_and_preserves_first_mismatch(self):
        first = {
            "total_traces": 2,
            "mismatching_traces": 1,
            "total_steps": 4,
            "mismatching_steps": 1,
            "total_output_comparisons": 8,
            "mismatching_output_comparisons": 2,
            "first_mismatch": {"trace_index": 1},
        }
        second = {
            "total_traces": 3,
            "mismatching_traces": 2,
            "total_steps": 6,
            "mismatching_steps": 3,
            "total_output_comparisons": 12,
            "mismatching_output_comparisons": 4,
            "first_mismatch": {"trace_index": 0},
        }

        result = aggregate_distance_results([first, second])

        self.assertEqual(result["total_traces"], 5)
        self.assertEqual(result["mismatching_traces"], 3)
        self.assertAlmostEqual(result["trace_mismatch_rate"], 3 / 5)
        self.assertEqual(result["total_steps"], 10)
        self.assertEqual(result["mismatching_steps"], 4)
        self.assertAlmostEqual(result["step_mismatch_rate"], 4 / 10)
        self.assertEqual(result["total_output_comparisons"], 20)
        self.assertEqual(result["mismatching_output_comparisons"], 6)
        self.assertAlmostEqual(result["output_hamming_mismatch_rate"], 6 / 20)
        self.assertEqual(result["first_mismatch"], {"trace_index": 1})
        self.assertEqual(result["batches"], 2)


class ControllerTraceGenerationTests(unittest.TestCase):
    def test_exhaustive_traces_enumerates_cartesian_power_up_to_cap(self):
        env = {
            "a": ["false", "true"],
            "b": ["false", "true"],
        }

        all_traces = exhaustive_traces(env, max_depth=2, max_paths=100)
        capped_traces = exhaustive_traces(env, max_depth=2, max_paths=5)

        self.assertEqual(len(all_traces), 16)
        self.assertEqual(len(capped_traces), 5)
        self.assertTrue(all(len(trace) == 2 for trace in all_traces))
        self.assertEqual(
            all_traces[0],
            [
                {"a": "false", "b": "false"},
                {"a": "false", "b": "false"},
            ],
        )

    def test_random_traces_are_reproducible_for_seed(self):
        env = {
            "a": ["false", "true"],
            "mode": ["LOW", "HIGH"],
        }

        first = random_traces(env, max_depth=4, runs=3, seed=7)
        second = random_traces(env, max_depth=4, runs=3, seed=7)
        different = random_traces(env, max_depth=4, runs=3, seed=8)

        self.assertEqual(first, second)
        self.assertNotEqual(first, different)
        self.assertEqual(len(first), 3)
        self.assertTrue(all(len(trace) == 4 for trace in first))


class SpectraSignatureTests(unittest.TestCase):
    def parse_source(self, source: str):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "fixture.spectra"
            path.write_text(source, encoding="utf-8")
            return parse_spectra_signature(path)

    def test_parse_spectra_signature_supports_scalar_domains(self):
        signature = self.parse_source(
            """
            spec Fixture
            type Mode = {LOW, HIGH};
            env boolean request;
            env Int(0..2) level;
            env Mode mode;
            sys boolean grant;
            sys {OPEN, CLOSED} door;
            """
        )

        self.assertEqual(signature["status"], "success")
        self.assertEqual(signature["spec_name"], "Fixture")
        self.assertEqual(signature["env"]["request"], ["false", "true"])
        self.assertEqual(signature["env"]["level"], ["0", "1", "2"])
        self.assertEqual(signature["env"]["mode"], ["LOW", "HIGH"])
        self.assertEqual(signature["sys"]["grant"], ["false", "true"])
        self.assertEqual(signature["sys"]["door"], ["OPEN", "CLOSED"])

    def test_parse_spectra_signature_reports_unsupported_arrays(self):
        signature = self.parse_source(
            """
            spec Fixture
            type Coord = Int(0..4);
            env Coord[2] robot;
            sys boolean ok;
            """
        )

        self.assertEqual(signature["status"], "unsupported_signature")
        self.assertIn("unsupported array type", signature["error"])

    def test_signatures_compatible_detects_domain_and_name_changes(self):
        baseline = {
            "status": "success",
            "env": {"request": ["false", "true"]},
            "sys": {"grant": ["false", "true"]},
        }
        generated_domain_change = {
            "status": "success",
            "env": {"request": ["false", "true"]},
            "sys": {"grant": ["LOW", "HIGH"]},
        }
        generated_name_change = {
            "status": "success",
            "env": {"req": ["false", "true"]},
            "sys": {"grant": ["false", "true"]},
        }

        compatible, reason = signatures_compatible(baseline, baseline)
        self.assertTrue(compatible)
        self.assertIsNone(reason)

        compatible, reason = signatures_compatible(baseline, generated_domain_change)
        self.assertFalse(compatible)
        self.assertEqual(reason, "system_signature_mismatch")

        compatible, reason = signatures_compatible(baseline, generated_name_change)
        self.assertFalse(compatible)
        self.assertEqual(reason, "environment_signature_mismatch")


class SignatureMappingTests(unittest.TestCase):
    def test_validate_mapping_accepts_complete_one_to_one_domain_match(self):
        baseline = {
            "env": {"button": ["false", "true"]},
            "sys": {"leftM": ["FWD", "BWD", "STP"], "rightM": ["FWD", "BWD", "STP"]},
        }
        generated = {
            "env": {"button": ["false", "true"]},
            "sys": {"leftMotor": ["FWD", "BWD", "STP"], "rightMotor": ["FWD", "BWD", "STP"]},
        }
        mapping = {
            "env": {"button": "button"},
            "sys": {"leftM": "leftMotor", "rightM": "rightMotor"},
            "confidence": "high",
        }

        validated, errors = validate_mapping(mapping, baseline, generated)

        self.assertEqual(errors, [])
        self.assertTrue(validated["complete"])
        self.assertEqual(validated["sys"]["leftM"], "leftMotor")

    def test_validate_mapping_rejects_domain_mismatch_and_duplicate_targets(self):
        baseline = {
            "env": {},
            "sys": {"a": ["0", "1"], "b": ["0", "1"]},
        }
        generated = {
            "env": {},
            "sys": {"x": ["0", "1"], "y": ["LOW", "HIGH"]},
        }
        mapping = {"env": {}, "sys": {"a": "x", "b": "x"}}

        validated, errors = validate_mapping(mapping, baseline, generated)

        self.assertFalse(validated["complete"])
        self.assertTrue(any("mapped more than once" in error for error in errors))

    def test_apply_hoa_ap_mapping_renames_generated_variable_names_only(self):
        hoa = 'AP: 2 "leftMotor=FWD" "rightMotor=STP"\n--BODY--\nState: 0\n[0&1] 0\n--END--\n'

        mapped = apply_hoa_ap_mapping(hoa, {"leftMotor": "leftM", "rightMotor": "rightM"})

        self.assertIn('"leftM=FWD"', mapped)
        self.assertIn('"rightM=STP"', mapped)
        self.assertNotIn('"leftMotor=FWD"', mapped)


if __name__ == "__main__":
    unittest.main()
