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
    acceptance_condition: object
    num_acceptance_sets: int


@dataclass(frozen=True)
class LetterAlphabet:
    """Finite letter model used to assign probabilities to automaton edges."""

    cubes: tuple[object, ...]
    model: str


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


def evaluate_acceptance_condition(acceptance_condition, seen_acceptance_sets: frozenset[int]) -> bool:
    """Evaluate a Spot acceptance condition for a reached BSCC.

    Inside a BSCC, `Inf(i)` is true iff acceptance set `i` appears on at least
    one positive-probability internal transition. Spot's `accepting()` method
    evaluates the acceptance formula from exactly this set of infinitely-often
    seen acceptance marks.
    """
    return bool(acceptance_condition.accepting(sorted(seen_acceptance_sets)))


def find_accepting_bsccs(markov_chain: MarkovChain, bsccs: list[set[int]], debug: bool = False) -> list[set[int]]:
    """Return BSCCs satisfying the Markov chain's omega-acceptance formula."""
    accepting_bsccs: list[set[int]] = []

    for index, bscc in enumerate(bsccs):
        seen_acceptance_sets = acceptance_sets_in_bscc(markov_chain, bscc)
        is_accepting = evaluate_acceptance_condition(markov_chain.acceptance_condition, seen_acceptance_sets)

        if debug:
            print(
                f"[debug] BSCC {index}: states={sorted(bscc)}, "
                f"acceptance_sets={sorted(seen_acceptance_sets)}, "
                f"accepting={is_accepting}"
            )

        if is_accepting:
            accepting_bsccs.append(bscc)

    if debug:
        print(f"[debug] Accepting BSCC count: {len(accepting_bsccs)}")

    return accepting_bsccs


def union_components(components: list[set[int]]) -> set[int]:
    """Return the union of a list of state sets."""
    states: set[int] = set()
    for component in components:
        states.update(component)
    return states


def require_numpy():
    """Import NumPy lazily because only the final probability solve needs it."""
    try:
        import numpy
    except ImportError as exc:
        raise SystemExit(
            "Could not import NumPy. Install it in the WSL/conda environment with "
            "`conda install numpy` or `pip install numpy`."
        ) from exc
    return numpy


def reachability_probability_exact(
    markov_chain: MarkovChain,
    accepting_bsccs: list[set[int]],
    all_bsccs: list[set[int]],
    debug: bool = False,
) -> float:
    """Compute the probability of reaching an accepting BSCC.

    Accepting BSCC states have value 1, rejecting BSCC states have value 0, and
    all remaining transient states are solved exactly via `(I - P_UU) x = b`.
    """
    np = require_numpy()

    accepting_states = union_components(accepting_bsccs)
    rejecting_bsccs = [bscc for bscc in all_bsccs if bscc not in accepting_bsccs]
    rejecting_states = union_components(rejecting_bsccs)
    all_states = set(range(markov_chain.num_states))
    unknown_states = sorted(all_states - accepting_states - rejecting_states)

    if debug:
        print(f"[debug] Accepting states: {sorted(accepting_states)}")
        print(f"[debug] Rejecting states: {sorted(rejecting_states)}")
        print(f"[debug] Unknown transient states: {unknown_states}")

    if markov_chain.initial_state in accepting_states:
        return 1.0
    if markov_chain.initial_state in rejecting_states:
        return 0.0
    if not unknown_states:
        raise ValueError("Initial state is neither classified nor transient; cannot solve reachability.")

    state_to_row = {state: index for index, state in enumerate(unknown_states)}
    size = len(unknown_states)
    matrix = np.eye(size)
    rhs = np.zeros(size)

    for state in unknown_states:
        row = state_to_row[state]
        for transition in markov_chain.transitions.get(state, []):
            target = transition.target
            probability = transition.probability

            if target in accepting_states:
                rhs[row] += probability
            elif target in rejecting_states:
                continue
            else:
                column = state_to_row[target]
                matrix[row, column] -= probability

    if debug:
        print("[debug] Reachability linear-system matrix:")
        print(matrix)
        print("[debug] Reachability linear-system rhs:")
        print(rhs)

    solution = np.linalg.solve(matrix, rhs)
    probability = float(solution[state_to_row[markov_chain.initial_state]])

    if debug:
        print("[debug] Reachability solution:")
        print(solution)
        print(f"[debug] Initial-state reachability probability: {probability}")

    return probability


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
    required_attributes = ("automaton", "product_xor")
    missing = [attribute for attribute in required_attributes if not hasattr(spot, attribute)]
    if missing:
        location = getattr(spot, "__file__", "unknown location")
        raise SystemExit(
            "Imported a Python module named `spot`, but it is not the LRDE/EPITA "
            "Spot omega-automata binding required by this project. "
            f"Missing attributes: {', '.join(missing)}. Imported module location: {location}. "
            "Install/use conda-forge::spot in the active WSL/conda environment, and make sure "
            "no PyPI package named `spot` shadows it."
        )
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


def get_second_example_buchi_automata():
    """Return a second deterministic example pair with distance strictly between 0 and 1."""
    spot = require_spot()
    formulas = [
        "GF grant",
        "req & GF grant",
    ]
    return tuple(spot.translate(formula, "BA", "deterministic") for formula in formulas)


def parse_spectra_value_ap(atomic_proposition: str) -> tuple[str, str] | None:
    """Parse Spectra CLI AP names like `"signal=true"` into variable/value."""
    name = atomic_proposition
    if len(name) >= 2 and name[0] == '"' and name[-1] == '"':
        name = name[1:-1]
    if "=" not in name:
        return None
    variable, value = name.split("=", 1)
    if not variable or not value:
        return None
    return variable, value


def build_letter_alphabet(atomic_propositions: tuple[str, ...], bdd_variables: tuple[int, ...]) -> LetterAlphabet:
    """Build the finite letter alphabet used for edge probabilities.

    The Spectra HOA exporter encodes finite-domain variables as one AP per
    value, for example `"signal=false"` and `"signal=true"`. Treating those APs
    as independent Boolean propositions makes valid Spectra valuations a
    measure-zero subset over infinite words. For such AP groups, we therefore
    count only one-hot assignments: exactly one value per variable is true.

    APs that do not match this encoding remain ordinary independent Booleans.
    """
    buddy = require_buddy()
    grouped_indices: dict[str, list[int]] = {}
    independent_indices: list[int] = []

    for index, atomic_proposition in enumerate(atomic_propositions):
        parsed = parse_spectra_value_ap(atomic_proposition)
        if parsed is None:
            independent_indices.append(index)
            continue
        variable, _value = parsed
        grouped_indices.setdefault(variable, []).append(index)

    # A single AP containing "=" is not enough evidence for a finite-domain
    # encoding, so keep it independent.
    one_hot_groups: list[list[int]] = []
    for indices in grouped_indices.values():
        if len(indices) >= 2:
            one_hot_groups.append(indices)
        else:
            independent_indices.extend(indices)

    cubes: list[object] = []

    def append_cubes(group_index: int, independent_index: int, cube) -> None:
        if group_index < len(one_hot_groups):
            group = one_hot_groups[group_index]
            for selected_index in group:
                group_cube = cube
                for member_index in group:
                    variable = bdd_variables[member_index]
                    literal = buddy.bdd_ithvar(variable) if member_index == selected_index else buddy.bdd_nithvar(variable)
                    group_cube &= literal
                append_cubes(group_index + 1, independent_index, group_cube)
            return

        if independent_index < len(independent_indices):
            ap_index = independent_indices[independent_index]
            variable = bdd_variables[ap_index]
            append_cubes(group_index, independent_index + 1, cube & buddy.bdd_nithvar(variable))
            append_cubes(group_index, independent_index + 1, cube & buddy.bdd_ithvar(variable))
            return

        cubes.append(cube)

    append_cubes(0, 0, buddy.bddtrue)
    model = "spectra_one_hot" if one_hot_groups else "raw_boolean_ap"
    return LetterAlphabet(cubes=tuple(cubes), model=model)


def count_satisfying_letters(condition, letter_alphabet: LetterAlphabet) -> int:
    """Count valid letters satisfying a Spot/Buddy BDD condition.

    This intentionally uses explicit enumeration. That is simple and reliable
    for the first implementation, and good enough while the example alphabets are
    small. Later, this can be replaced by a direct BDD model-counting routine if
    large Spectra alphabets become a bottleneck.
    """
    buddy = require_buddy()
    satisfying_letters = 0

    for cube in letter_alphabet.cubes:
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
    letter_alphabet = build_letter_alphabet(atomic_propositions, bdd_variables)
    alphabet_size = len(letter_alphabet.cubes)
    transitions: dict[int, list[MarkovTransition]] = {}

    if debug:
        print("[debug] Translating automaton to Markov chain.")
        print(f"[debug] States: {automaton.num_states()}")
        print(f"[debug] Initial state: {automaton.get_init_state_number()}")
        print(f"[debug] Atomic propositions: {atomic_propositions}")
        print(f"[debug] Letter model: {letter_alphabet.model}")
        print(f"[debug] Alphabet size: {alphabet_size}")
        print(f"[debug] Spot complete property: {complete_property}")

    for source in range(automaton.num_states()):
        outgoing: list[MarkovTransition] = []
        row_probability = 0.0

        for edge in automaton.out(source):
            satisfying_letters = count_satisfying_letters(edge.cond, letter_alphabet)
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
        acceptance_condition=automaton.get_acceptance(),
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
    symmetric_difference = spot.postprocess(symmetric_difference, "generic", "deterministic", "complete")

    if debug:
        print("[debug] Symmetric-difference automaton:")
        print(f"[debug] States: {symmetric_difference.num_states()}")
        print(symmetric_difference.to_str("hoa").rstrip())

    markov_chain = automaton_to_markov_chain(symmetric_difference, debug=debug)
    bsccs = find_bsccs(markov_chain, debug=debug)
    accepting_bsccs = find_accepting_bsccs(markov_chain, bsccs, debug=debug)
    distance = reachability_probability_exact(markov_chain, accepting_bsccs, bsccs, debug=debug)

    if debug:
        print("[debug] Markov-chain translation complete.")
        print(f"[debug] Markov-chain states: {markov_chain.num_states}")
        print(f"[debug] Markov-chain BSCCs: {bsccs}")
        print(f"[debug] Markov-chain accepting BSCCs: {accepting_bsccs}")
        print(f"[debug] Buchi distance: {distance}")

    return distance


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

    distance = compute_buchi_distance(example_automata[0], example_automata[1], debug=True)
    print(f"Buchi distance: {distance}")

    second_example_automata = get_second_example_buchi_automata()
    print()
    print("Second example automata 0:")
    print(second_example_automata[0].to_str("hoa"))
    print()
    print("Second example automata 1:")
    print(second_example_automata[1].to_str("hoa"))
    second_distance = compute_buchi_distance(second_example_automata[0], second_example_automata[1], debug=True)
    print(f"Second Buchi distance: {second_distance}")


if __name__ == "__main__":
    raise SystemExit(main())
