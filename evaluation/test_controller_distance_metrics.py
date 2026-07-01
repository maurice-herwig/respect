#!/usr/bin/env python3
"""Unit tests for controller output-distance metrics."""

from __future__ import annotations

import tempfile
import unittest
import os
import urllib.error
from pathlib import Path
from unittest.mock import patch

from evaluation.evaluate_controller_distances import (
    aggregate_distance_results,
    compare_trace_outputs,
    exhaustive_traces,
    parse_spectra_signature,
    random_traces,
    signatures_compatible,
)
from evaluation.signature_mapping import apply_hoa_ap_mapping, call_academic_cloud, get_or_create_llm_mapping, validate_mapping
from evaluation.signature_mapping import append_jsonl, mapping_key


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

    def test_parse_spectra_signature_accepts_module_header(self):
        signature = self.parse_source(
            """
            module Minepump
            env boolean highwater;
            env boolean methane;
            sys boolean pump;
            """
        )

        self.assertEqual(signature["status"], "success")
        self.assertEqual(signature["spec_name"], "Minepump")
        self.assertEqual(signature["env"]["highwater"], ["false", "true"])
        self.assertEqual(signature["sys"]["pump"], ["false", "true"])

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
    def test_call_academic_cloud_retries_once_after_http_500(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def read(self):
                return b'{"choices": [{"message": {"content": "{}"}}]}'

        http_500 = urllib.error.HTTPError(
            url="https://example.test/v1/chat/completions",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=None,
        )
        with patch("urllib.request.urlopen", side_effect=[http_500, FakeResponse()]) as urlopen:
            with patch("time.sleep") as sleep:
                response = call_academic_cloud(
                    api_key="test-key",
                    base_url="https://example.test/v1",
                    model="test-model",
                    system_prompt="system",
                    user_prompt="user",
                    temperature=0.0,
                    max_tokens=100,
                    timeout=1.0,
                    retries=1,
                    retry_delay_seconds=0.01,
                )

        self.assertEqual(urlopen.call_count, 2)
        sleep.assert_called_once()
        self.assertEqual(response["_respect_api_metadata"]["attempts"], 2)
        self.assertTrue(response["_respect_api_metadata"]["retried"])

    def parse_source(self, source: str):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "fixture.spectra"
            path.write_text(source, encoding="utf-8")
            return parse_spectra_signature(path)

    def get_mapping_with_mocked_response(self, response_text: str, baseline: dict, generated: dict):
        with tempfile.TemporaryDirectory() as temp_dir:
            mapping_file = Path(temp_dir) / "signature_mappings.jsonl"
            response = {"choices": [{"message": {"content": response_text}}]}
            with patch.dict("os.environ", {"ACADEMIC_CLOUD_API_KEY": "test-key"}, clear=False):
                with patch("evaluation.signature_mapping.call_academic_cloud", return_value=response):
                    return get_or_create_llm_mapping(
                        baseline_signature=baseline,
                        generated_signature=generated,
                        mapping_file=mapping_file,
                        model="test-model",
                        base_url="https://example.test/v1",
                    )

    def test_get_or_create_llm_mapping_accepts_obvious_variable_rename(self):
        baseline = {
            "status": "success",
            "env": {"HighW": ["false", "true"]},
            "sys": {"pump": ["false", "true"]},
        }
        generated = {
            "status": "success",
            "env": {"HighWater": ["false", "true"]},
            "sys": {"pump": ["false", "true"]},
        }
        response_text = """
        {
          "env": {"HighW": "HighWater"},
          "sys": {"pump": "pump"},
          "unmapped_baseline_env": [],
          "unmapped_generated_env": [],
          "unmapped_baseline_sys": [],
          "unmapped_generated_sys": [],
          "confidence": "high",
          "explanation": "HighW is an obvious abbreviation of HighWater; pump is identical."
        }
        """

        record = self.get_mapping_with_mocked_response(response_text, baseline, generated)

        self.assertTrue(record["usable"])
        self.assertEqual(record["validation_errors"], [])
        self.assertTrue(record["mapping"]["complete"])
        self.assertEqual(record["mapping"]["env"], {"HighW": "HighWater"})
        self.assertEqual(record["mapping"]["sys"], {"pump": "pump"})

    def test_get_or_create_llm_mapping_ignores_cached_api_error_record(self):
        baseline = {
            "status": "success",
            "env": {"HighW": ["false", "true"]},
            "sys": {"pump": ["false", "true"]},
        }
        generated = {
            "status": "success",
            "env": {"HighWater": ["false", "true"]},
            "sys": {"pump": ["false", "true"]},
        }
        response_text = """
        {
          "env": {"HighW": "HighWater"},
          "sys": {"pump": "pump"},
          "unmapped_baseline_env": [],
          "unmapped_generated_env": [],
          "unmapped_baseline_sys": [],
          "unmapped_generated_sys": [],
          "confidence": "high",
          "explanation": "HighW is an obvious abbreviation of HighWater; pump is identical."
        }
        """

        with tempfile.TemporaryDirectory() as temp_dir:
            mapping_file = Path(temp_dir) / "signature_mappings.jsonl"
            append_jsonl(
                mapping_file,
                {
                    "mapping_key": mapping_key(
                        baseline_signature=baseline,
                        generated_signature=generated,
                        model="test-model",
                        prompt_version="signature_mapping_v1",
                    ),
                    "api_status": "error",
                    "usable": False,
                    "validation_errors": ["Academic Cloud API request failed with HTTP 500:"],
                },
            )
            response = {"choices": [{"message": {"content": response_text}}]}
            with patch.dict("os.environ", {"ACADEMIC_CLOUD_API_KEY": "test-key"}, clear=False):
                with patch("evaluation.signature_mapping.call_academic_cloud", return_value=response) as call:
                    record = get_or_create_llm_mapping(
                        baseline_signature=baseline,
                        generated_signature=generated,
                        mapping_file=mapping_file,
                        model="test-model",
                        base_url="https://example.test/v1",
                    )

        call.assert_called_once()
        self.assertTrue(record["usable"])
        self.assertEqual(record["api_status"], "success")
        self.assertEqual(record["mapping"]["env"], {"HighW": "HighWater"})

    def test_spectra_specs_with_different_variable_names_can_align_hoa_alphabets(self):
        baseline = self.parse_source(
            """
            spec MinePumpBaseline
            env boolean HighW;
            sys boolean pump;
            """
        )
        generated = self.parse_source(
            """
            spec MinePumpGenerated
            env boolean HighWater;
            sys boolean pump;
            """
        )
        response_text = """
        {
          "env": {"HighW": "HighWater"},
          "sys": {"pump": "pump"},
          "unmapped_baseline_env": [],
          "unmapped_generated_env": [],
          "unmapped_baseline_sys": [],
          "unmapped_generated_sys": [],
          "confidence": "high",
          "explanation": "HighW is an obvious abbreviation of HighWater; pump is identical."
        }
        """

        record = self.get_mapping_with_mocked_response(response_text, baseline, generated)
        reverse_mapping = {"HighWater": "HighW", "pump": "pump"}
        generated_hoa = 'AP: 4 "HighWater=false" "HighWater=true" "pump=false" "pump=true"\n'

        mapped_hoa = apply_hoa_ap_mapping(generated_hoa, reverse_mapping)

        self.assertTrue(record["usable"])
        self.assertIn('"HighW=false"', mapped_hoa)
        self.assertIn('"HighW=true"', mapped_hoa)
        self.assertNotIn('"HighWater=false"', mapped_hoa)
        self.assertIn('"pump=false"', mapped_hoa)

    def test_get_or_create_llm_mapping_rejects_unmapped_ambiguous_variables(self):
        baseline = {
            "status": "success",
            "env": {"water": ["false", "true"]},
            "sys": {"motor": ["false", "true"]},
        }
        generated = {
            "status": "success",
            "env": {"highWater": ["false", "true"]},
            "sys": {"pump": ["false", "true"]},
        }
        response_text = """
        {
          "env": {},
          "sys": {},
          "unmapped_baseline_env": ["water"],
          "unmapped_generated_env": ["highWater"],
          "unmapped_baseline_sys": ["motor"],
          "unmapped_generated_sys": ["pump"],
          "confidence": "high",
          "explanation": "The names are related domain concepts but not obvious lexical variants."
        }
        """

        record = self.get_mapping_with_mocked_response(response_text, baseline, generated)

        self.assertFalse(record["usable"])
        self.assertEqual(record["validation_errors"], [])
        self.assertFalse(record["mapping"]["complete"])
        self.assertEqual(record["mapping"]["env"], {})
        self.assertEqual(record["mapping"]["sys"], {})
        self.assertEqual(record["mapping"]["unmapped_baseline_env"], ["water"])
        self.assertEqual(record["mapping"]["unmapped_generated_sys"], ["pump"])

    @unittest.skipUnless(
        os.environ.get("RUN_ACADEMIC_CLOUD_MAPPING_TEST") == "1",
        "Set RUN_ACADEMIC_CLOUD_MAPPING_TEST=1 to run the live Academic Cloud mapping test.",
    )
    def test_live_academic_cloud_mapping_request_accepts_obvious_variable_rename(self):
        baseline = {
            "status": "success",
            "env": {"HighW": ["false", "true"]},
            "sys": {"pump": ["false", "true"]},
        }
        generated = {
            "status": "success",
            "env": {"HighWater": ["false", "true"]},
            "sys": {"pump": ["false", "true"]},
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            record = get_or_create_llm_mapping(
                baseline_signature=baseline,
                generated_signature=generated,
                mapping_file=Path(temp_dir) / "signature_mappings.jsonl",
                force=True,
            )

        self.assertEqual(record["api_status"], "success")
        self.assertTrue(record["usable"], record)
        self.assertEqual(record["mapping"]["env"], {"HighW": "HighWater"})
        self.assertEqual(record["mapping"]["sys"], {"pump": "pump"})

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
