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

from dataclasses import dataclass
from math import isclose


@dataclass(frozen=True)
class MarkovTransition:
    """One probabilistic transition of the induced Markov chain."""

    target: int
    probability: float
    acceptance_sets: frozenset[int]


@dataclass(frozen=True)
class MarkovChain:
    """Sparse Markov-chain view of a deterministic Spot automaton."""

    num_states: int
    initial_state: int
    atomic_propositions: tuple[str, ...]
    transitions: dict[int, list[MarkovTransition]]
    acceptance_formula: str
    num_acceptance_sets: int


def markov_successors(markov_chain: MarkovChain, state: int) -> set[int]:
    """Return successors reachable with positive probability."""
    return {
        transition.target
        for transition in markov_chain.transitions.get(state, [])
        if transition.probability > 0.0
    }


def find_strongly_connected_components(markov_chain: MarkovChain) -> list[set[int]]:
    """Find SCCs of the Markov-chain graph with Tarjan's algorithm."""
    index = 0
    stack: list[int] = []
    on_stack: set[int] = set()
    indices: dict[int, int] = {}
    lowlinks: dict[int, int] = {}
    components: list[set[int]] = []

    def visit(state: int) -> None:
        nonlocal index
        indices[state] = index
        lowlinks[state] = index
        index += 1
        stack.append(state)
        on_stack.add(state)

        for successor in markov_successors(markov_chain, state):
            if successor not in indices:
                visit(successor)
                lowlinks[state] = min(lowlinks[state], lowlinks[successor])
            elif successor in on_stack:
                lowlinks[state] = min(lowlinks[state], indices[successor])

        if lowlinks[state] == indices[state]:
            component: set[int] = set()
            while True:
                member = stack.pop()
                on_stack.remove(member)
                component.add(member)
                if member == state:
                    break
            components.append(component)

    for state in range(markov_chain.num_states):
        if state not in indices:
            visit(state)

    return components


def find_bsccs(markov_chain: MarkovChain, debug: bool = False) -> list[set[int]]:
    """Return all bottom SCCs of the Markov chain."""
    bsccs: list[set[int]] = []

    for component in find_strongly_connected_components(markov_chain):
        is_bottom = True
        for state in component:
            outside_successors = markov_successors(markov_chain, state) - component
            if outside_successors:
                is_bottom = False
                break

        if is_bottom:
            bsccs.append(component)

    if debug:
        print(f"[debug] BSCC count: {len(bsccs)}")
        for index, component in enumerate(bsccs):
            print(f"[debug] BSCC {index}: {sorted(component)}")

    return bsccs


def acceptance_sets_in_bscc(markov_chain: MarkovChain, bscc: set[int]) -> frozenset[int]:
    """Return acceptance sets seen on positive-probability internal BSCC edges.

    For transition-based acceptance, an acceptance set is seen infinitely often
    inside a reached BSCC iff it occurs on at least one internal transition with
    positive probability.
    """
    seen: set[int] = set()

    for source in bscc:
        for transition in markov_chain.transitions.get(source, []):
            if transition.probability <= 0.0 or transition.target not in bscc:
                continue
            seen.update(transition.acceptance_sets)

    return frozenset(seen)


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


def require_buddy():
    """Import Buddy, Spot's BDD backend, with a clear setup error."""
    try:
        import buddy
    except ImportError as exc:
        raise SystemExit(
            "Could not import Buddy, Spot's BDD backend. "
            "Run this script inside the WSL/conda Spot environment."
        ) from exc
    return buddy


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


def count_satisfying_letters(condition, bdd_variables: tuple[int, ...]) -> int:
    """Count complete AP valuations satisfying a Spot/Buddy BDD condition.

    This intentionally uses explicit enumeration. That is simple and reliable
    for the first implementation, and good enough while the example alphabets are
    small. Later, this can be replaced by a direct BDD model-counting routine if
    large Spectra alphabets become a bottleneck.
    """
    buddy = require_buddy()
    satisfying_letters = 0

    for valuation in range(1 << len(bdd_variables)):
        cube = buddy.bddtrue
        for index, variable in enumerate(bdd_variables):
            literal = buddy.bdd_ithvar(variable) if valuation & (1 << index) else buddy.bdd_nithvar(variable)
            cube &= literal
        if condition & cube != buddy.bddfalse:
            satisfying_letters += 1

    return satisfying_letters


def automaton_to_markov_chain(automaton, debug: bool = False) -> MarkovChain:
    """Translate a deterministic Spot automaton into a sparse Markov chain.

    The random-word model is currently uniform over all complete valuations of
    the automaton's atomic propositions. For `n` APs, every letter therefore has
    probability `1 / 2**n`.

    Raises:
        ValueError: if the automaton is not deterministic, explicitly marked
        incomplete, or if an outgoing row does not cover the complete alphabet.
    """
    if not automaton.is_deterministic():
        raise ValueError("Cannot translate a nondeterministic automaton into a Markov chain.")

    # Spot stores automaton properties as three-valued information:
    # true/false/unknown. The HOA printer may still be able to report
    # `complete` after analyzing the automaton, while prop_complete() remains
    # unknown on the object. Therefore we only fail early on explicit false and
    # keep the row-sum check below as the authoritative completeness test.
    complete_property = automaton.prop_complete()
    if complete_property.is_false():
        raise ValueError("Cannot translate an incomplete automaton into a Markov chain.")

    bdd_dict = automaton.get_dict()
    atomic_propositions = tuple(str(ap) for ap in automaton.ap())
    bdd_variables = tuple(bdd_dict.varnum(ap) for ap in automaton.ap())
    alphabet_size = 1 << len(bdd_variables)
    transitions: dict[int, list[MarkovTransition]] = {}

    if debug:
        print("[debug] Translating automaton to Markov chain.")
        print(f"[debug] States: {automaton.num_states()}")
        print(f"[debug] Initial state: {automaton.get_init_state_number()}")
        print(f"[debug] Atomic propositions: {atomic_propositions}")
        print(f"[debug] Alphabet size: {alphabet_size}")
        print(f"[debug] Spot complete property: {complete_property}")

    for source in range(automaton.num_states()):
        outgoing: list[MarkovTransition] = []
        row_probability = 0.0

        for edge in automaton.out(source):
            satisfying_letters = count_satisfying_letters(edge.cond, bdd_variables)
            if satisfying_letters == 0:
                continue

            probability = satisfying_letters / alphabet_size
            transition = MarkovTransition(
                target=edge.dst,
                probability=probability,
                acceptance_sets=frozenset(int(acc_set) for acc_set in edge.acc.sets()),
            )
            outgoing.append(transition)
            row_probability += probability

            if debug:
                print(
                    "[debug] MC edge "
                    f"{source} -> {transition.target}, "
                    f"probability={transition.probability:.6g}, "
                    f"acceptance_sets={sorted(transition.acceptance_sets)}"
                )

        if not isclose(row_probability, 1.0, rel_tol=1e-12, abs_tol=1e-12):
            raise ValueError(
                f"Automaton is not complete at state {source}: "
                f"outgoing probability sums to {row_probability} instead of 1.0."
            )

        transitions[source] = outgoing

    return MarkovChain(
        num_states=automaton.num_states(),
        initial_state=automaton.get_init_state_number(),
        atomic_propositions=atomic_propositions,
        transitions=transitions,
        acceptance_formula=str(automaton.get_acceptance()),
        num_acceptance_sets=automaton.num_sets(),
    )


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

    markov_chain = automaton_to_markov_chain(symmetric_difference, debug=debug)
    bsccs = find_bsccs(markov_chain, debug=debug)

    if debug:
        print("[debug] Markov-chain translation complete.")
        print(f"[debug] Markov-chain states: {markov_chain.num_states}")
        print(f"[debug] Markov-chain BSCCs: {bsccs}")
        for index, bscc in enumerate(bsccs):
            acceptance_sets = acceptance_sets_in_bscc(markov_chain, bscc)
            print(f"[debug] BSCC {index} acceptance sets: {sorted(acceptance_sets)}")
        print("[debug] Distance implementation stops after Markov-chain construction.")

    # Later steps will interpret `symmetric_difference` as a Markov chain under a
    # random-word distribution, find accepting BSCCs, and compute the reachability
    # probability. For now, stop here explicitly so partial results are not
    # mistaken for the final distance.
    raise NotImplementedError("Buchi distance computation is implemented up to Markov-chain construction.")


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


if __name__ == "__main__":
    raise SystemExit(main())
