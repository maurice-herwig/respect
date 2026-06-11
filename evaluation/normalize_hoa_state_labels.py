#!/usr/bin/env python3
"""Normalize Spectra CLI state-labeled HOA exports for Spot distance checks."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


STATE_RE = re.compile(r"^State:\s+(\d+)(?:\s+\[(.*)\])?(?:\s+(\{[^}]*\}))?\s*$")
EDGE_RE = re.compile(r"^\[(.*)\]\s+(\d+)(?:\s+(\{[^}]*\}))?\s*$")
STATES_RE = re.compile(r"^States:\s+(\d+)\s*$")
PROPERTIES_RE = re.compile(r"^properties:\s+(.*)$")


def parse_state_acceptance(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


def normalize_condition(condition: str | None) -> str:
    if condition is None or not condition.strip():
        return "t"
    return condition.strip()


def missing_condition(conditions: list[str]) -> str:
    if not conditions:
        return "t"
    if len(conditions) == 1:
        return f"!({conditions[0]})"
    return "!(" + " | ".join(f"({condition})" for condition in conditions) + ")"


def normalize_properties(line: str) -> str:
    match = PROPERTIES_RE.match(line)
    if not match:
        return line

    properties = match.group(1).split()
    rewritten: list[str] = []
    for prop in properties:
        if prop == "state-labels":
            prop = "trans-labels"
        elif prop == "state-acc":
            prop = "trans-acc"
        if prop not in rewritten:
            rewritten.append(prop)

    if "trans-labels" not in rewritten:
        rewritten.append("trans-labels")
    if "explicit-labels" not in rewritten:
        rewritten.append("explicit-labels")

    return "properties: " + " ".join(rewritten)


def transform_hoa_state_labels_to_transitions(
    input_text: str,
    *,
    add_rejecting_sink: bool = True,
) -> tuple[str, dict[str, Any]]:
    lines = input_text.splitlines()
    try:
        body_index = lines.index("--BODY--")
        end_index = lines.index("--END--")
    except ValueError as exc:
        raise ValueError("HOA file must contain --BODY-- and --END-- markers.") from exc

    header = lines[:body_index]
    body = lines[body_index + 1 : end_index]
    footer = lines[end_index:]

    state_labels: dict[int, str] = {}
    state_acceptance: dict[int, str | None] = {}
    transitions: dict[int, list[tuple[int, str | None]]] = {}
    state_order: list[int] = []
    current_state: int | None = None

    for line in body:
        if not line.strip():
            continue

        state_match = STATE_RE.match(line)
        if state_match:
            current_state = int(state_match.group(1))
            state_order.append(current_state)
            state_labels[current_state] = normalize_condition(state_match.group(2))
            state_acceptance[current_state] = parse_state_acceptance(state_match.group(3))
            transitions.setdefault(current_state, [])
            continue

        edge_match = EDGE_RE.match(line)
        if edge_match:
            if current_state is None:
                raise ValueError(f"Transition before first state: {line}")
            target = int(edge_match.group(2))
            transitions.setdefault(current_state, []).append((target, parse_state_acceptance(edge_match.group(3))))
            continue

        raise ValueError(f"Unsupported HOA body line: {line}")

    if not state_order:
        raise ValueError("HOA body contains no states.")

    missing_targets = sorted({target for edges in transitions.values() for target, _ in edges} - set(state_labels))
    if missing_targets:
        raise ValueError(f"Transitions reference missing states: {missing_targets}")

    declared_states: int | None = None
    rewritten_header: list[str] = []
    for line in header:
        states_match = STATES_RE.match(line)
        if states_match:
            declared_states = int(states_match.group(1))
            continue
        if PROPERTIES_RE.match(line):
            rewritten_header.append(normalize_properties(line))
        else:
            rewritten_header.append(line)

    if declared_states is None:
        declared_states = max(state_order) + 1

    sink_state = max(state_order) + 1 if add_rejecting_sink else None
    output_state_count = max(declared_states, max(state_order) + 1)
    if sink_state is not None:
        output_state_count = max(output_state_count, sink_state + 1)

    final_header: list[str] = []
    inserted_states = False
    for line in header:
        if STATES_RE.match(line):
            final_header.append(f"States: {output_state_count}")
            inserted_states = True
        elif PROPERTIES_RE.match(line):
            final_header.append(normalize_properties(line))
        else:
            final_header.append(line)
    if not inserted_states:
        final_header.append(f"States: {output_state_count}")

    output_body: list[str] = []
    added_sink_edges = 0
    for state in state_order:
        output_body.append(f"State: {state}")
        edge_conditions: list[str] = []
        for target, edge_acceptance in transitions.get(state, []):
            condition = state_labels[target]
            acceptance = edge_acceptance or state_acceptance.get(target)
            suffix = f" {acceptance}" if acceptance else ""
            output_body.append(f"[{condition}] {target}{suffix}")
            edge_conditions.append(condition)

        if sink_state is not None:
            condition = missing_condition(edge_conditions)
            output_body.append(f"[{condition}] {sink_state}")
            added_sink_edges += 1

    if sink_state is not None:
        output_body.append(f"State: {sink_state}")
        output_body.append(f"[t] {sink_state}")

    output_lines = final_header + ["--BODY--"] + output_body + footer
    metadata = {
        "states_in": len(state_order),
        "states_out": output_state_count,
        "sink_added": sink_state is not None,
        "sink_state": sink_state,
        "sink_edges_added": added_sink_edges,
        "transition_label_source": "target_state_label",
        "acceptance_source": "target_state_acceptance",
    }
    return "\n".join(output_lines) + "\n", metadata


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Move HOA state labels to transition labels.")
    parser.add_argument("--input", required=True, help="Input HOA file exported by the modified Spectra CLI.")
    parser.add_argument("--output", required=True, help="Output normalized HOA file.")
    parser.add_argument(
        "--add-rejecting-sink",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Add a rejecting sink for valuations not covered by outgoing target-state labels.",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite an existing output file.")
    return parser.parse_args()


def print_result(result: dict[str, Any]) -> None:
    print(json.dumps(result, indent=2, sort_keys=True))


def main() -> int:
    args = parse_args()
    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()

    if not input_path.is_file():
        print_result({"status": "error", "message": f"Input HOA file not found: {input_path}"})
        return 2
    if output_path.exists() and not args.force:
        print_result({"status": "error", "message": f"Output already exists: {output_path}"})
        return 2

    try:
        normalized, metadata = transform_hoa_state_labels_to_transitions(
            input_path.read_text(encoding="utf-8"),
            add_rejecting_sink=args.add_rejecting_sink,
        )
    except Exception as exc:
        print_result({"status": "error", "message": f"{type(exc).__name__}: {exc}"})
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(normalized, encoding="utf-8")
    print_result(
        {
            "status": "normalized",
            "input": str(input_path),
            "output": str(output_path),
            **metadata,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
