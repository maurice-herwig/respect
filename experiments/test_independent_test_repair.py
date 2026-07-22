"""Unit tests for the independent-test repair orchestration helpers."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from experiments.independent_test_repair import (
    aggregate_test_results,
    extract_agent_result,
    invalid_test_names_from_result,
    rebind_test_plan,
    summarize_status,
    write_json,
)
from experiments.reconstruct_with_independent_tests import signature_file_for


class AgentResultParsingTests(unittest.TestCase):
    def test_extract_agent_result_reads_json_inside_markdown_fence(self):
        stdout = """Done.

```json
{
  "cli_status": "synthesized",
  "invalid_test_names": ["no_request_no_grant"]
}
```
"""

        self.assertEqual(
            extract_agent_result(stdout),
            {"cli_status": "synthesized", "invalid_test_names": ["no_request_no_grant"]},
        )

    def test_invalid_test_names_accepts_json_or_key_value_shapes(self):
        self.assertEqual(
            invalid_test_names_from_result({"invalid_test_names": '["a", "b"]'}),
            ["a", "b"],
        )
        self.assertEqual(
            invalid_test_names_from_result({"rejected_invalid_test_names": "b, a, b"}),
            ["a", "b"],
        )


class TestPlanReplayTests(unittest.TestCase):
    def test_rebind_test_plan_updates_controller_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.json"
            target = root / "target.json"
            write_json(
                source,
                {
                    "spec_name": "Old",
                    "spectra_file": "old.spectra",
                    "controller_dir": "old-controller",
                    "tests": [],
                },
            )

            rebind_test_plan(
                source,
                target,
                spec_name="NewSpec",
                spectra_file=root / "new.spectra",
                controller_dir=root / "jit",
            )

            payload = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(payload["spec_name"], "NewSpec")
            self.assertEqual(payload["spectra_file"], str(root / "new.spectra"))
            self.assertEqual(payload["controller_dir"], str(root / "jit"))


class AggregateFeedbackTests(unittest.TestCase):
    def test_aggregate_test_results_filters_rejected_invalid_tests(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_file = root / "results.json"
            aggregate_file = root / "aggregate.json"
            write_json(
                result_file,
                {
                    "results": [
                        {"name": "valid_failure", "passed": False},
                        {"name": "invalid_failure", "passed": False},
                        {"name": "valid_pass", "passed": True},
                    ]
                },
            )

            total, passed, failed, filtered = aggregate_test_results(
                [(0, result_file)],
                aggregate_file,
                {"invalid_failure"},
            )

            aggregate = json.loads(aggregate_file.read_text(encoding="utf-8"))
            self.assertEqual((total, passed, failed, filtered), (2, 1, 1, 1))
            self.assertEqual(aggregate["invalid_tests_filtered"], 1)
            self.assertEqual([item["name"] for item in aggregate["results"]], ["valid_failure", "valid_pass"])
            self.assertEqual(aggregate["ignored_invalid_tests"][0]["name"], "invalid_failure")


class StatusClassificationTests(unittest.TestCase):
    def test_summarize_status_reports_tests_passed(self):
        status = summarize_status(
            [{"stop_reason": "tests_passed", "tests_failed": 0, "invalid_tests_filtered": 0}],
            {"cli_status": "synthesized"},
        )
        self.assertEqual(status, "tests_passed")

    def test_summarize_status_reports_invalid_tests_rejected(self):
        status = summarize_status(
            [{"stop_reason": "tests_passed", "tests_failed": 0, "invalid_tests_filtered": 2}],
            {"cli_status": "synthesized"},
        )
        self.assertEqual(status, "invalid_tests_rejected")

    def test_summarize_status_reports_max_rounds_with_failures(self):
        status = summarize_status(
            [{"stop_reason": "max_feedback_rounds_reached", "tests_failed": 1}],
            {"cli_status": "synthesized"},
        )
        self.assertEqual(status, "max_rounds_with_failures")

    def test_summarize_status_reports_spec_not_synthesized(self):
        self.assertEqual(summarize_status([], {"cli_status": "unrealizable"}), "spec_not_synthesized")

    def test_summarize_status_reports_test_generation_failed(self):
        status = summarize_status(
            [{"stop_reason": "test_plan_compile_failed"}],
            {"cli_status": "synthesized"},
        )
        self.assertEqual(status, "test_generation_failed")


class SignatureSelectionTests(unittest.TestCase):
    def test_signature_file_for_prefers_description_id_then_dataset_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset_signature = root / "dataset.json"
            description_signature = root / "description.json"
            dataset_signature.write_text("{}", encoding="utf-8")
            description_signature.write_text("{}", encoding="utf-8")

            selected = signature_file_for(
                {"description_id": "description", "dataset_id": "dataset"},
                root,
            )
            self.assertEqual(selected, description_signature)

            description_signature.unlink()
            selected = signature_file_for(
                {"description_id": "description", "dataset_id": "dataset"},
                root,
            )
            self.assertEqual(selected, dataset_signature)


if __name__ == "__main__":
    unittest.main()
