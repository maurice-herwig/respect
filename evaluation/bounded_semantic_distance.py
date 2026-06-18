"""Bounded semantic prefix distance for deterministic Buchi automata."""

from __future__ import annotations

from dataclasses import dataclass
import itertools
import random
from typing import Any

from evaluation import buchi_distance


@dataclass(frozen=True)
class PrefixClassification:
    both_viable: int
    baseline_only: int
    generated_only: int
    neither_viable: int

    @property
    def total(self) -> int:
        return self.both_viable + self.baseline_only + self.generated_only + self.neither_viable


def build_valid_letter_alphabet(automaton) -> buchi_distance.LetterAlphabet:
    bdd_dict = automaton.get_dict()
    atomic_propositions = tuple(str(ap) for ap in automaton.ap())
    bdd_variables = tuple(bdd_dict.varnum(ap) for ap in automaton.ap())
    return buchi_distance.build_letter_alphabet(atomic_propositions, bdd_variables)


def matching_successor(automaton, state: int, letter) -> int | None:
    buddy = buchi_distance.require_buddy()
    successor: int | None = None
    for edge in automaton.out(state):
        if edge.cond & letter == buddy.bddfalse:
            continue
        if successor is not None and successor != edge.dst:
            raise ValueError(f"Automaton is nondeterministic for a valid letter at state {state}.")
        successor = edge.dst
    return successor


def automaton_positive_graph(automaton, alphabet: buchi_distance.LetterAlphabet) -> dict[int, list[tuple[int, frozenset[int]]]]:
    """Build the graph induced by existing transitions over valid Spectra letters."""
    buddy = buchi_distance.require_buddy()
    graph: dict[int, list[tuple[int, frozenset[int]]]] = {}
    for state in range(automaton.num_states()):
        edges: list[tuple[int, frozenset[int]]] = []
        for edge in automaton.out(state):
            if any(edge.cond & letter != buddy.bddfalse for letter in alphabet.cubes):
                edges.append((edge.dst, frozenset(int(acc_set) for acc_set in edge.acc.sets())))
        graph[state] = edges
    return graph


def graph_sccs(graph: dict[int, list[tuple[int, frozenset[int]]]], num_states: int) -> list[set[int]]:
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

        for successor, _acc in graph.get(state, []):
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

    for state in range(num_states):
        if state not in indices:
            visit(state)

    return components


def accepting_sccs(automaton, alphabet: buchi_distance.LetterAlphabet) -> list[set[int]]:
    """Return SCCs that can witness the automaton's omega acceptance condition."""
    graph = automaton_positive_graph(automaton, alphabet)
    components = graph_sccs(graph, automaton.num_states())
    accepting: list[set[int]] = []
    for component in components:
        seen: set[int] = set()
        for state in component:
            for successor, acceptance_sets in graph[state]:
                if successor in component:
                    seen.update(acceptance_sets)
        if buchi_distance.evaluate_acceptance_condition(automaton.get_acceptance(), frozenset(seen)):
            accepting.append(component)
    return accepting


def states_that_can_reach_accepting_scc(automaton, alphabet: buchi_distance.LetterAlphabet) -> set[int]:
    """Compute states from which a finite prefix can still be extended acceptingly."""
    graph = automaton_positive_graph(automaton, alphabet)
    accepting_states = buchi_distance.union_components(accepting_sccs(automaton, alphabet))
    reverse: dict[int, set[int]] = {state: set() for state in range(automaton.num_states())}
    for state, edges in graph.items():
        for successor, _acc in edges:
            reverse[successor].add(state)

    reachable = set(accepting_states)
    stack = list(accepting_states)
    while stack:
        state = stack.pop()
        for predecessor in reverse[state]:
            if predecessor in reachable:
                continue
            reachable.add(predecessor)
            stack.append(predecessor)
    return reachable


def prefix_viable(automaton, prefix: tuple[object, ...], viable_states: set[int]) -> bool:
    """Return whether a finite valid-letter prefix has an accepting continuation."""
    state = automaton.get_init_state_number()
    for letter in prefix:
        successor = matching_successor(automaton, state, letter)
        if successor is None:
            return False
        state = successor
    return state in viable_states


def exhaustive_prefixes(letters: tuple[object, ...], depth: int, max_prefixes: int | None) -> list[tuple[object, ...]]:
    prefixes: list[tuple[object, ...]] = []
    for prefix in itertools.product(letters, repeat=depth):
        prefixes.append(prefix)
        if max_prefixes is not None and len(prefixes) >= max_prefixes:
            break
    return prefixes


def random_prefixes(letters: tuple[object, ...], depth: int, samples: int, seed: int | None) -> list[tuple[object, ...]]:
    rng = random.Random(seed)
    return [tuple(rng.choice(letters) for _step in range(depth)) for _sample in range(samples)]


def summarize_classification(classification: PrefixClassification, *, mode: str, depth: int, samples: int | None, seed: int | None, alphabet_size: int) -> dict[str, Any]:
    total = classification.total
    mismatch = classification.baseline_only + classification.generated_only
    union = classification.both_viable + mismatch
    return {
        "mode": mode,
        "depth": depth,
        "samples": samples,
        "seed": seed,
        "alphabet_size": alphabet_size,
        "total_prefixes": total,
        "both_viable": classification.both_viable,
        "baseline_only": classification.baseline_only,
        "generated_only": classification.generated_only,
        "neither_viable": classification.neither_viable,
        "mismatch_rate": 0.0 if total == 0 else mismatch / total,
        "false_negative_rate": 0.0 if total == 0 else classification.baseline_only / total,
        "false_positive_rate": 0.0 if total == 0 else classification.generated_only / total,
        "jaccard_distance": None if union == 0 else mismatch / union,
    }


def compute_bounded_semantic_distance(
    baseline_automaton,
    generated_automaton,
    *,
    depth: int,
    mode: str = "random",
    samples: int = 1000,
    seed: int | None = 1,
    max_prefixes: int | None = None,
) -> dict[str, Any]:
    """Compare finite prefixes by accepting-continuation viability.

    The result is a bounded semantic distance: for each sampled/exhaustive
    prefix of length `depth`, we check whether each automaton can extend that
    prefix to an accepting infinite run. A mismatch means exactly one side is
    viable after reading the same valid Spectra-letter prefix.
    """
    if depth < 0:
        raise ValueError("depth must be non-negative.")
    if mode not in {"random", "exhaustive"}:
        raise ValueError("mode must be 'random' or 'exhaustive'.")
    if not baseline_automaton.is_deterministic() or not generated_automaton.is_deterministic():
        raise ValueError("Bounded semantic distance requires deterministic automata.")

    baseline_ap = [str(ap) for ap in baseline_automaton.ap()]
    generated_ap = [str(ap) for ap in generated_automaton.ap()]
    if baseline_ap != generated_ap:
        raise ValueError("Bounded semantic distance requires identical AP alphabets.")

    alphabet = build_valid_letter_alphabet(baseline_automaton)
    letters = alphabet.cubes
    if not letters:
        raise ValueError("Bounded semantic distance requires at least one valid letter.")

    if mode == "exhaustive":
        prefixes = exhaustive_prefixes(letters, depth, max_prefixes)
        effective_samples = len(prefixes)
    else:
        prefixes = random_prefixes(letters, depth, samples, seed)
        effective_samples = samples

    baseline_viable_states = states_that_can_reach_accepting_scc(baseline_automaton, alphabet)
    generated_viable_states = states_that_can_reach_accepting_scc(generated_automaton, alphabet)

    counts = PrefixClassification(0, 0, 0, 0)
    both = baseline_only = generated_only = neither = 0
    for prefix in prefixes:
        baseline_viable = prefix_viable(baseline_automaton, prefix, baseline_viable_states)
        generated_viable = prefix_viable(generated_automaton, prefix, generated_viable_states)
        if baseline_viable and generated_viable:
            both += 1
        elif baseline_viable:
            baseline_only += 1
        elif generated_viable:
            generated_only += 1
        else:
            neither += 1

    counts = PrefixClassification(
        both_viable=both,
        baseline_only=baseline_only,
        generated_only=generated_only,
        neither_viable=neither,
    )
    return summarize_classification(
        counts,
        mode=mode,
        depth=depth,
        samples=effective_samples,
        seed=seed if mode == "random" else None,
        alphabet_size=len(letters),
    )
