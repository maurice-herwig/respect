"""Unit tests for the Buchi-distance substochastic semantics."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from evaluation import buchi_distance


def load_hoa(source: str):
    spot = buchi_distance.require_spot()
    with tempfile.TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "fixture.hoa"
        path.write_text(source.strip() + "\n", encoding="utf-8")
        return spot.automaton(str(path))


class BuchiDistanceSemanticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            buchi_distance.require_spot()
            buchi_distance.require_buddy()
        except SystemExit as exc:
            raise unittest.SkipTest(str(exc)) from exc

    def test_partial_rows_are_allowed_without_renormalization(self):
        automaton = load_hoa(
            """
            HOA: v1
            States: 1
            Start: 0
            AP: 2 "x=false" "x=true"
            Acceptance: 1 Inf(0)
            properties: trans-labels explicit-labels trans-acc deterministic
            --BODY--
            State: 0
            [0 & !1] 0 {0}
            --END--
            """
        )

        markov_chain = buchi_distance.automaton_to_markov_chain(automaton)

        self.assertEqual(markov_chain.num_states, 1)
        self.assertAlmostEqual(markov_chain.row_probability_sums[0], 0.5)
        self.assertEqual(len(markov_chain.transitions[0]), 1)
        self.assertAlmostEqual(markov_chain.transitions[0][0].probability, 0.5)

    def test_zero_valid_letter_edges_are_ignored(self):
        automaton = load_hoa(
            """
            HOA: v1
            States: 1
            Start: 0
            AP: 2 "x=false" "x=true"
            Acceptance: 1 Inf(0)
            properties: trans-labels explicit-labels trans-acc deterministic
            --BODY--
            State: 0
            [0 & !1] 0 {0}
            [0 & 1] 0
            --END--
            """
        )

        markov_chain = buchi_distance.automaton_to_markov_chain(automaton)

        self.assertAlmostEqual(markov_chain.row_probability_sums[0], 0.5)
        self.assertEqual(len(markov_chain.transitions[0]), 1)
        self.assertEqual(markov_chain.transitions[0][0].acceptance_sets, frozenset({0}))

    def test_relative_bscc_can_be_accepting_with_partial_row(self):
        automaton = load_hoa(
            """
            HOA: v1
            States: 1
            Start: 0
            AP: 2 "x=false" "x=true"
            Acceptance: 1 Inf(0)
            properties: trans-labels explicit-labels trans-acc deterministic
            --BODY--
            State: 0
            [0 & !1] 0 {0}
            --END--
            """
        )
        markov_chain = buchi_distance.automaton_to_markov_chain(automaton)

        bsccs = buchi_distance.find_bsccs(markov_chain)
        accepting = buchi_distance.find_accepting_bsccs(markov_chain, bsccs)
        distance = buchi_distance.reachability_probability_exact(markov_chain, accepting, bsccs)

        self.assertEqual(bsccs, [{0}])
        self.assertEqual(accepting, [{0}])
        self.assertEqual(distance, 1.0)

    def test_transient_path_keeps_raw_probability_mass(self):
        automaton = load_hoa(
            """
            HOA: v1
            States: 2
            Start: 0
            AP: 2 "x=false" "x=true"
            Acceptance: 1 Inf(0)
            properties: trans-labels explicit-labels trans-acc deterministic
            --BODY--
            State: 0
            [0 & !1] 1
            State: 1
            [0 & !1] 1 {0}
            --END--
            """
        )
        markov_chain = buchi_distance.automaton_to_markov_chain(automaton)

        bsccs = buchi_distance.find_bsccs(markov_chain)
        accepting = buchi_distance.find_accepting_bsccs(markov_chain, bsccs)
        distance = buchi_distance.reachability_probability_exact(markov_chain, accepting, bsccs)

        self.assertAlmostEqual(markov_chain.transitions[0][0].probability, 0.5)
        self.assertEqual(bsccs, [{1}])
        self.assertEqual(accepting, [{1}])
        self.assertAlmostEqual(distance, 0.5)


if __name__ == "__main__":
    unittest.main()
