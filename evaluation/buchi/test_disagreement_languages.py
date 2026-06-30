"""Tests for directed Buchi language-disagreement construction."""

from __future__ import annotations

import unittest

from evaluation.buchi import buchi_distance
from evaluation.buchi import disagreement_languages


class DisagreementLanguageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        buchi_distance.require_spot()

    def translate(self, formula: str):
        spot = buchi_distance.require_spot()
        return spot.translate(formula, "generic", "deterministic", "complete")

    def assert_difference_flags(self, left_formula: str, right_formula: str, expected_left_only: bool, expected_right_only: bool) -> None:
        left = self.translate(left_formula)
        right = self.translate(right_formula)

        differences, result = disagreement_languages.compute_disagreement_language_sets(left, right)

        self.assertEqual(result["status"], "success", result)
        self.assertIsNotNone(differences)
        self.assertEqual(result["left_minus_right"]["nonempty"], expected_left_only, result)
        self.assertEqual(result["right_minus_left"]["nonempty"], expected_right_only, result)

    def test_equivalent_languages_have_empty_directed_differences(self):
        self.assert_difference_flags(
            "GF a",
            "GF a",
            expected_left_only=False,
            expected_right_only=False,
        )

    def test_strict_subset_has_one_nonempty_direction(self):
        # L(G a) is a strict subset of L(F a). A word where `a` is initially
        # false and then always true is in F a but not in G a.
        self.assert_difference_flags(
            "F a",
            "G a",
            expected_left_only=True,
            expected_right_only=False,
        )

    def test_incomparable_languages_have_both_nonempty_directions(self):
        self.assert_difference_flags(
            "GF a",
            "GF !a",
            expected_left_only=True,
            expected_right_only=True,
        )

    def test_alphabet_mismatch_is_reported(self):
        left = self.translate("GF a")
        right = self.translate("GF b")

        differences, result = disagreement_languages.compute_disagreement_language_sets(left, right)

        self.assertIsNone(differences)
        self.assertEqual(result["status"], "alphabet_mismatch", result)
        self.assertIn("alphabet_diagnostics", result)


if __name__ == "__main__":
    unittest.main()
