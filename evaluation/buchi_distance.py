#!/usr/bin/env python3
"""Spot integration scaffold for Buchi-automata distance evaluation.

Planned workflow:
1. Read two deterministic omega automata, initially in HOA format.
2. Check that both automata use the same atomic propositions/alphabet.
3. Build the symmetric-difference automaton.
4. Interpret the deterministic difference automaton as a DTMC under a chosen
   random-word distribution.
5. Find accepting bottom strongly connected components.
6. Compute the probability of reaching an accepting BSCC.
7. Report that probability as the distance.

Implementation intentionally deferred.
"""

from __future__ import annotations


def require_spot():
    """Import Spot lazily so the script can print a clear setup error."""
    try:
        import spot
    except ImportError as exc:
        raise SystemExit(
            "Could not import the LRDE/EPITA Spot Python bindings. "
            "Run this script inside the WSL/conda environment created with "
            "`conda create -n respect-spot python=3.12 conda-forge::spot`."
        ) from exc
    return spot


def get_example_buchi_automata():
    """Return two deterministic example Buchi automata for integration tests.

    The examples share the same atomic propositions (`req` and `grant`) so they
    can be combined with Spot's product operations. Both formulas also contain a
    liveness part (`GF req`) to keep the generated automata non-trivial.
    """
    spot = require_spot()
    formulas = [
        # Every request must eventually be granted, and requests occur
        # infinitely often.
        "G(req -> F grant) & GF req",
        # Every request must be granted in the next step, and requests occur
        # infinitely often.
        "G(req -> X grant) & GF req",
    ]
    # `product_xor` requires deterministic operands, so the examples are
    # generated as deterministic Buchi automata from the beginning.
    return tuple(spot.translate(formula, "BA", "deterministic") for formula in formulas)


def compute_buchi_distance(left_automaton, right_automaton, debug: bool = False) -> float:
    """Compute the planned probabilistic distance between two Buchi automata.

    Current implementation status:
    - implemented: construction of the symmetric-difference automaton
    - not implemented yet: conversion to a Markov chain and probability solving

    When `debug` is true, intermediate automata and state counts are printed to
    make each construction step inspectable.
    """
    spot = require_spot()

    if debug:
        print("[debug] Starting Buchi-distance computation.")
        print(f"[debug] Left automaton states: {left_automaton.num_states()}")
        print(f"[debug] Right automaton states: {right_automaton.num_states()}")

    # The language-theoretic difference we want is:
    #   L(left) xor L(right)
    # Spot's product_xor constructs an automaton for exactly this symmetric
    # difference. Spot expects both input automata to be deterministic.
    symmetric_difference = spot.product_xor(left_automaton, right_automaton)

    if debug:
        print("[debug] Symmetric-difference automaton:")
        print(f"[debug] States: {symmetric_difference.num_states()}")
        print(symmetric_difference.to_str("hoa").rstrip())
        print("[debug] Distance implementation stops after symmetric-difference construction.")

    # Later steps will interpret `symmetric_difference` as a Markov chain under a
    # random-word distribution, find accepting BSCCs, and compute the reachability
    # probability. For now, stop here explicitly so partial results are not
    # mistaken for the final distance.
    raise NotImplementedError("Buchi distance computation is implemented up to symmetric difference.")


def main() -> int:
    spot = require_spot()
    print(f"Spot version: {spot.version()}")

    # Build and print two example automata so the local Spot installation can be
    # tested before the real distance pipeline is complete.
    example_automata = get_example_buchi_automata()
    print("Example automata 0:")
    print(example_automata[0].to_str("hoa"))
    print()
    print("Example automata 1:")
    print(example_automata[1].to_str("hoa"))

    # Run the currently implemented part of the distance pipeline. This will
    # print the symmetric-difference automaton and then raise NotImplementedError.
    compute_buchi_distance(example_automata[0], example_automata[1], debug=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
