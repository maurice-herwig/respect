#!/usr/bin/env python3
"""Batch distance evaluation for synthesized reconstruction runs."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import multiprocessing
import os
import re
import subprocess
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evaluation.buchi import buchi_distance
from evaluation.buchi import bounded_semantic_distance
from evaluation.signature_mapping import (
    DEFAULT_MAPPING_FILE,
    apply_hoa_ap_mapping,
    generated_to_baseline,
    get_or_create_llm_mapping,
    parse_spectra_signature,
)


DEFAULT_RUNS_MANIFEST = REPO_ROOT / "experiments" / "runs" / "runs.jsonl"
DEFAULT_JAR = REPO_ROOT / "assets" / "cli_with_hoa_export" / "spectra-cli.jar"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "evaluation" / "buchi" / "distance_results"
STATE_RE = re.compile(r"^State:\s+(\d+)(?:\s+\[(.*)\])?(?:\s+(\{[^}]*\}))?\s*$")
EDGE_RE = re.compile(r"^\[(.*)\]\s+(\d+)(?:\s+(\{[^}]*\}))?\s*$")
STATES_RE = re.compile(r"^States:\s+(\d+)\s*$")
PROPERTIES_RE = re.compile(r"^properties:\s+(.*)$")
ACCEPTANCE_RE = re.compile(r"^Acceptance:\s+(\d+)\s+(.*)$")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not path.is_file():
        raise FileNotFoundError(f"JSONL file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in {path} at line {line_number}: {exc}") from exc
    return records


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def repo_relative_or_absolute(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path.resolve())


def normalize_path_value_for_platform(path_value: str) -> str:
    value = path_value.strip().strip('"').strip("'")
    if os.name == "nt":
        return value

    windows_drive_match = re.fullmatch(r"([A-Za-z]):[\\/](.*)", value)
    if windows_drive_match:
        drive = windows_drive_match.group(1).lower()
        rest = windows_drive_match.group(2).replace("\\", "/")
        return f"/mnt/{drive}/{rest}"

    if "\\" in value and not value.startswith("\\\\"):
        return value.replace("\\", "/")
    return value


def resolve_input_path(path_value: str) -> Path:
    path = Path(normalize_path_value_for_platform(path_value))
    candidates = [path]
    if not path.is_absolute():
        candidates.append(REPO_ROOT / path)
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_file():
            return resolved
    return candidates[0].resolve()


def resolve_existing_path(path_value: str | Path) -> Path:
    path = Path(normalize_path_value_for_platform(str(path_value)))
    candidates = [path]
    if not path.is_absolute():
        candidates.append(REPO_ROOT / path)
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.exists():
            return resolved
    return candidates[0].resolve()


def resolve_repo_path(path_value: str | Path) -> Path:
    path = Path(str(path_value))
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def extract_model_label(record: dict[str, Any]) -> str | None:
    """Return the model label stored directly or encoded in legacy run paths."""
    agent_model = record.get("agent_model")
    if isinstance(agent_model, str) and agent_model:
        return agent_model

    candidates = [
        record.get("description_relative_stem"),
        record.get("run_dir"),
        record.get("description_file"),
        record.get("agent_prompt_file"),
    ]
    for candidate in candidates:
        if not isinstance(candidate, str):
            continue
        match = re.search(r"(?:^|[\\/])model=([^\\/]+)", candidate)
        if match:
            return match.group(1)
    return None


def safe_path_part(value: str, max_length: int = 120) -> str:
    safe = "".join(char if char.isalnum() or char in "._=-" else "_" for char in value).strip("_")
    return (safe or "value")[:max_length]


def model_matches(record: dict[str, Any], model: str | None) -> bool:
    if model is None:
        return True
    return extract_model_label(record) == model


def summarize_run(record: dict[str, Any] | None, include_full_record: bool) -> dict[str, Any] | None:
    if record is None:
        return None
    if include_full_record:
        return record
    keys = (
        "run_id",
        "run_key",
        "dataset_id",
        "skill",
        "status",
        "reported_cli_status",
        "reported_repair_loops",
        "source_repository_full_name",
        "source_path",
        "source_spectra_file",
        "reconstructed_spectra_file",
        "description_id",
        "description_relative_stem",
    )
    return {key: record.get(key) for key in keys if key in record}


def selected_generated_spectra_value(record: dict[str, Any], spectra_stage: str) -> str | None:
    if spectra_stage == "final":
        return record.get("reconstructed_spectra_file")
    intermediate = record.get("intermediate_spectra_files")
    if not isinstance(intermediate, dict):
        return None
    value = intermediate.get(spectra_stage)
    return str(value) if value else None


def stage_comparison_id(record: dict[str, Any], spectra_stage: str) -> str:
    base = safe_path_part(str(record.get("run_id") or record.get("run_key") or record.get("dataset_id") or "run"))
    if spectra_stage == "final":
        return base
    return safe_path_part(f"{base}__{spectra_stage}")


def build_export_command(jar_path: Path, input_path: Path, output_path: Path, max_states: int, use_jtlv: bool) -> list[str]:
    command = ["java", "-jar", str(jar_path), "-i", str(input_path)]
    if use_jtlv:
        command.append("--jtlv")
    command.extend(["--export-hoa", "--hoa-output", str(output_path), "--max-states", str(max_states)])
    return command


def output_fields(raw_output: str, include_raw_output: bool, tail_chars: int) -> dict[str, Any]:
    if include_raw_output:
        return {"raw_output": raw_output}
    if tail_chars <= 0:
        return {"raw_output_truncated": len(raw_output) > 0, "raw_output_tail": ""}
    return {"raw_output_truncated": len(raw_output) > tail_chars, "raw_output_tail": raw_output[-tail_chars:]}


def subprocess_output_to_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def combine_subprocess_output(stdout: str | bytes | None, stderr: str | bytes | None) -> str:
    return "\n".join(
        part
        for part in (subprocess_output_to_text(stdout), subprocess_output_to_text(stderr))
        if part
    ).strip()


def export_hoa(
    *,
    input_path: Path,
    output_path: Path,
    jar_path: Path,
    max_states: int,
    timeout: float,
    use_jtlv: bool,
    force: bool,
    include_raw_output: bool,
    raw_output_tail_chars: int,
) -> tuple[dict[str, Any], bool]:
    if output_path.exists() and not force:
        return (
            {
                "status": "reused",
                "input": repo_relative_or_absolute(input_path),
                "input_sha256": sha256_file(input_path),
                "hoa_file": repo_relative_or_absolute(output_path),
                "hoa_exists": True,
                "hoa_size_bytes": output_path.stat().st_size,
                "jar": repo_relative_or_absolute(jar_path),
                "jar_sha256": sha256_file(jar_path),
                "max_states": max_states,
                "timeout_seconds": timeout,
                "jtlv": use_jtlv,
            },
            True,
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists() and force:
        output_path.unlink()

    command = build_export_command(jar_path, input_path, output_path, max_states, use_jtlv)
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raw_output = combine_subprocess_output(exc.stdout, exc.stderr)
        if output_path.exists():
            output_path.unlink()
        result = {
            "status": "timeout",
            "input": repo_relative_or_absolute(input_path),
            "hoa_file": repo_relative_or_absolute(output_path),
            "hoa_exists": False,
            "jar": repo_relative_or_absolute(jar_path),
            "command": command,
            "exit_code": None,
            "max_states": max_states,
            "timeout_seconds": timeout,
            "jtlv": use_jtlv,
        }
        result.update(output_fields(raw_output, include_raw_output, raw_output_tail_chars))
        return result, False

    raw_output = combine_subprocess_output(completed.stdout, completed.stderr)
    hoa_exists = output_path.is_file()
    hoa_size_bytes = output_path.stat().st_size if hoa_exists else None
    ok = completed.returncode == 0 and bool(hoa_size_bytes)
    if not ok and hoa_exists:
        output_path.unlink()
        hoa_exists = False
        hoa_size_bytes = None

    result = {
        "status": "exported" if ok else "error",
        "input": repo_relative_or_absolute(input_path),
        "input_sha256": sha256_file(input_path),
        "hoa_file": repo_relative_or_absolute(output_path),
        "hoa_exists": hoa_exists,
        "hoa_size_bytes": hoa_size_bytes,
        "jar": repo_relative_or_absolute(jar_path),
        "jar_sha256": sha256_file(jar_path),
        "command": command,
        "exit_code": completed.returncode,
        "max_states": max_states,
        "timeout_seconds": timeout,
        "jtlv": use_jtlv,
    }
    result.update(output_fields(raw_output, include_raw_output, raw_output_tail_chars))
    return result, ok


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


def add_rejecting_sink_acceptance(line: str, sink_acceptance_set: int | None) -> str:
    if sink_acceptance_set is None:
        return line
    match = ACCEPTANCE_RE.match(line)
    if not match:
        return line
    old_count = int(match.group(1))
    formula = match.group(2).strip()
    return f"Acceptance: {old_count + 1} ({formula}) & Fin({sink_acceptance_set})"


def transform_hoa_state_labels_to_transitions(input_text: str, *, add_rejecting_sink: bool = True) -> tuple[str, dict[str, Any]]:
    lines = input_text.splitlines()
    body_index = lines.index("--BODY--")
    end_index = lines.index("--END--")
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
            state_acceptance[current_state] = state_match.group(3).strip() if state_match.group(3) else None
            transitions.setdefault(current_state, [])
            continue
        edge_match = EDGE_RE.match(line)
        if edge_match:
            if current_state is None:
                raise ValueError(f"Transition before first state: {line}")
            transitions.setdefault(current_state, []).append((int(edge_match.group(2)), edge_match.group(3)))
            continue
        raise ValueError(f"Unsupported HOA body line: {line}")

    missing_targets = sorted({target for edges in transitions.values() for target, _ in edges} - set(state_labels))
    if missing_targets:
        raise ValueError(f"Transitions reference missing states: {missing_targets}")

    declared_states = None
    for line in header:
        states_match = STATES_RE.match(line)
        if states_match:
            declared_states = int(states_match.group(1))
            break
    if declared_states is None:
        declared_states = max(state_order) + 1

    sink_state = max(state_order) + 1 if add_rejecting_sink else None
    sink_acceptance_set: int | None = None
    if sink_state is not None:
        for line in header:
            acceptance_match = ACCEPTANCE_RE.match(line)
            if acceptance_match:
                sink_acceptance_set = int(acceptance_match.group(1))
                break
        if sink_acceptance_set is None:
            sink_acceptance_set = 0
    output_state_count = max(declared_states, max(state_order) + 1)
    if sink_state is not None:
        output_state_count = max(output_state_count, sink_state + 1)

    final_header: list[str] = []
    inserted_states = False
    for line in header:
        if STATES_RE.match(line):
            final_header.append(f"States: {output_state_count}")
            inserted_states = True
        elif ACCEPTANCE_RE.match(line):
            final_header.append(add_rejecting_sink_acceptance(line, sink_acceptance_set))
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
            output_body.append(f"[{missing_condition(edge_conditions)}] {sink_state}")
            added_sink_edges += 1
    if sink_state is not None:
        output_body.append(f"State: {sink_state}")
        acceptance_suffix = f" {{{sink_acceptance_set}}}" if sink_acceptance_set is not None else ""
        output_body.append(f"[t] {sink_state}{acceptance_suffix}")

    metadata = {
        "states_in": len(state_order),
        "states_out": output_state_count,
        "sink_added": sink_state is not None,
        "sink_state": sink_state,
        "sink_edges_added": added_sink_edges,
        "sink_acceptance_set": sink_acceptance_set,
        "sink_rejecting_acceptance_added": sink_acceptance_set is not None,
        "transition_label_source": "target_state_label",
        "acceptance_source": "target_state_acceptance",
    }
    return "\n".join(final_header + ["--BODY--"] + output_body + footer) + "\n", metadata


def normalize_hoa_file(input_path: Path, output_path: Path, add_rejecting_sink: bool, force: bool) -> dict[str, Any]:
    if output_path.exists() and not force:
        existing_text = output_path.read_text(encoding="utf-8", errors="replace")
        if not add_rejecting_sink or "sink_rejecting_acceptance_added" in existing_text:
            return {
                "status": "reused",
                "input": repo_relative_or_absolute(input_path),
                "output": repo_relative_or_absolute(output_path),
                "output_size_bytes": output_path.stat().st_size,
            }
        # Older normalized artifacts used an accepting sink for `Acceptance: 0 t`.
        # Regenerate them so missing valuations are rejected consistently.
    if output_path.exists() and not force and add_rejecting_sink:
        existing_text = output_path.read_text(encoding="utf-8", errors="replace")
        if "Acceptance: 0 t" not in existing_text and re.search(r"Acceptance:\s+\d+\s+.*&\s*Fin\(\d+\)", existing_text):
            return {
                "status": "reused",
                "input": repo_relative_or_absolute(input_path),
                "output": repo_relative_or_absolute(output_path),
                "output_size_bytes": output_path.stat().st_size,
            }
    elif output_path.exists() and not force:
        return {
            "status": "reused",
            "input": repo_relative_or_absolute(input_path),
            "output": repo_relative_or_absolute(output_path),
            "output_size_bytes": output_path.stat().st_size,
        }
    normalized, metadata = transform_hoa_state_labels_to_transitions(
        input_path.read_text(encoding="utf-8"),
        add_rejecting_sink=add_rejecting_sink,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(normalized, encoding="utf-8")
    return {
        "status": "normalized",
        "input": repo_relative_or_absolute(input_path),
        "output": repo_relative_or_absolute(output_path),
        "output_size_bytes": output_path.stat().st_size,
        **metadata,
    }


def alphabet_diagnostics(result: dict[str, Any]) -> dict[str, Any]:
    baseline_ap = list((result.get("baseline_automaton") or {}).get("ap") or [])
    generated_ap = list((result.get("generated_automaton") or {}).get("ap") or [])
    return {
        "baseline_ap": baseline_ap,
        "generated_ap": generated_ap,
        "baseline_only": sorted(set(baseline_ap) - set(generated_ap)),
        "generated_only": sorted(set(generated_ap) - set(baseline_ap)),
    }


def automata_are_structurally_compatible(result: dict[str, Any]) -> tuple[bool, str | None]:
    baseline = result.get("baseline_automaton") or {}
    generated = result.get("generated_automaton") or {}
    if baseline.get("deterministic") is not True or generated.get("deterministic") is not True:
        return False, "nondeterministic_automaton"
    return True, None


def determinize_automaton_for_distance(automaton):
    spot = buchi_distance.require_spot()
    candidates = [
        ("generic", ("generic", "deterministic")),
        ("parity", ("parity", "deterministic")),
        ("rabin", ("rabin", "deterministic")),
        ("deterministic", ("deterministic",)),
    ]
    errors: list[str] = []
    for name, options in candidates:
        try:
            processed = spot.postprocess(automaton, *options)
        except Exception as exc:
            errors.append(f"{name}: {type(exc).__name__}: {exc}")
            continue
        if processed.is_deterministic():
            return processed, {
                "status": "determinized",
                "method": f"spot.postprocess({', '.join(options)})",
                "states_before": automaton.num_states(),
                "states_after": processed.num_states(),
                "acceptance_before": str(automaton.get_acceptance()),
                "acceptance_after": str(processed.get_acceptance()),
            }
        errors.append(
            f"{name}: produced deterministic={processed.is_deterministic()} "
            f"complete={processed.prop_complete()} states={processed.num_states()}"
        )
    raise ValueError("Could not determinize automaton with Spot. Attempts: " + " | ".join(errors))


def maybe_determinize_automata(baseline_automaton, generated_automaton, *, enabled: bool) -> tuple[Any, Any, dict[str, Any], dict[str, Any]]:
    baseline_info = {
        "status": "not_needed" if baseline_automaton.is_deterministic() else "disabled",
        "states_before": baseline_automaton.num_states(),
        "states_after": baseline_automaton.num_states(),
    }
    generated_info = {
        "status": "not_needed" if generated_automaton.is_deterministic() else "disabled",
        "states_before": generated_automaton.num_states(),
        "states_after": generated_automaton.num_states(),
    }
    if not enabled:
        return baseline_automaton, generated_automaton, baseline_info, generated_info
    if not baseline_automaton.is_deterministic():
        baseline_automaton, baseline_info = determinize_automaton_for_distance(baseline_automaton)
    if not generated_automaton.is_deterministic():
        generated_automaton, generated_info = determinize_automaton_for_distance(generated_automaton)
    return baseline_automaton, generated_automaton, baseline_info, generated_info


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate all synthesized reconstructed Spectra files for one model/skill combination "
            "against their accepted-dataset baselines."
        )
    )
    parser.add_argument("--skill", required=True, help="Skill/method to evaluate, e.g. respect.")
    parser.add_argument("--model", required=True, help="Model label, e.g. llama-3.")
    parser.add_argument("--runs-manifest", default=str(DEFAULT_RUNS_MANIFEST))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--output-jsonl", default=None, help="Explicit JSONL result path.")
    parser.add_argument(
        "--spectra-stage",
        default="final",
        help=(
            "Generated Spectra stage to evaluate. Use final for reconstructed_spectra_file, "
            "or a key from intermediate_spectra_files such as 00_initial, "
            "01_after_syntax_repair, 02_after_unrealizable_repair, or 03_after_test_repair."
        ),
    )
    parser.add_argument("--jar", default=str(DEFAULT_JAR), help="Path to the modified spectra-cli.jar.")
    parser.add_argument("--max-states", type=int, default=100_000)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument(
        "--run-timeout",
        type=float,
        default=180.0,
        help="Maximum wall-clock seconds for one full distance run. Use 0 to disable.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Evaluate at most N matching runs.")
    parser.add_argument(
        "--jtlv",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use Java BDD backend for HOA export. Enabled by default.",
    )
    parser.add_argument(
        "--normalize-hoa",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Move Spectra CLI state labels to transition labels before Spot import.",
    )
    parser.add_argument(
        "--add-rejecting-sink",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="During normalization, add a rejecting sink for missing valuations.",
    )
    parser.add_argument(
        "--determinize",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use Spot postprocessing to determinize nondeterministic automata before distance computation.",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing HOA artifacts and recompute existing run_ids.")
    parser.add_argument(
        "--resume",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Skip run_ids already present in the output JSONL. Enabled by default; use --no-resume to revisit all selected runs.",
    )
    parser.add_argument(
        "--reuse-existing",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Reuse existing JSONL distance records for the same baseline/generated Spectra file hashes "
            "and evaluation settings. Enabled by default; use --no-reuse-existing to rebuild the JSONL."
        ),
    )
    parser.add_argument(
        "--preflight-spot",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Check Spot availability before exporting any HOA files. Enabled by default.",
    )
    parser.add_argument(
        "--preflight-java",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Check that Java is new enough for the modified Spectra CLI before exporting. Enabled by default.",
    )
    parser.add_argument("--include-raw-output", action="store_true")
    parser.add_argument("--raw-output-tail-chars", type=int, default=1000)
    parser.add_argument("--include-run-record", action="store_true")
    parser.add_argument("--debug-distance", action="store_true")
    parser.add_argument(
        "--bounded-semantic-distance",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Also compute bounded prefix-viability semantic distance.",
    )
    parser.add_argument("--bounded-depth", type=int, default=10)
    parser.add_argument("--bounded-mode", choices=("random", "exhaustive"), default="random")
    parser.add_argument("--bounded-samples", type=int, default=1000)
    parser.add_argument("--bounded-seed", type=int, default=1)
    parser.add_argument(
        "--bounded-max-prefixes",
        type=int,
        default=None,
        help="Optional cap for exhaustive bounded semantic prefixes.",
    )
    parser.add_argument(
        "--signature-mapping",
        choices=("strict", "llm"),
        default="llm",
        help="strict requires identical HOA AP names. llm may rename generated AP variable names to baseline names.",
    )
    parser.add_argument("--signature-mapping-file", default=str(DEFAULT_MAPPING_FILE))
    parser.add_argument("--mapping-model", default=None)
    parser.add_argument("--mapping-base-url", default=None)
    parser.add_argument("--mapping-timeout", type=float, default=120.0)
    parser.add_argument("--force-signature-mapping", action="store_true")
    parser.add_argument("--json", action="store_true", help="Print machine-readable summary.")
    return parser.parse_args()


def output_root(args: argparse.Namespace) -> Path:
    path = Path(args.output_root)
    if not path.is_absolute():
        path = REPO_ROOT / path
    root = path / safe_path_part(args.skill) / safe_path_part(args.model)
    if args.spectra_stage != "final":
        root = root / safe_path_part(args.spectra_stage)
    return root


def default_output_jsonl(args: argparse.Namespace) -> Path:
    if args.output_jsonl:
        path = Path(args.output_jsonl)
        return path if path.is_absolute() else REPO_ROOT / path
    return output_root(args) / "distances.jsonl"


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def java_major_version() -> tuple[int | None, str]:
    try:
        completed = subprocess.run(["java", "-version"], capture_output=True, text=True, check=False, timeout=10)
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"

    output = "\n".join(part for part in (completed.stderr, completed.stdout) if part).strip()
    match = re.search(r'version\s+"([^"]+)"', output)
    if not match:
        return None, output

    version = match.group(1)
    if version.startswith("1."):
        parts = version.split(".")
        try:
            return int(parts[1]), output
        except (IndexError, ValueError):
            return None, output
    try:
        return int(version.split(".", 1)[0]), output
    except ValueError:
        return None, output


def load_completed_run_ids(path: Path) -> set[str]:
    completed: set[str] = set()
    if not path.is_file():
        return completed
    for record in load_jsonl(path):
        run = record.get("run")
        if isinstance(run, dict) and isinstance(run.get("run_id"), str):
            completed.add(run["run_id"])
    return completed


def run_id_from_result(record: dict[str, Any]) -> str | None:
    run = record.get("run")
    if isinstance(run, dict) and isinstance(run.get("run_id"), str):
        return run["run_id"]
    return None


def result_pair_key(record: dict[str, Any]) -> tuple[Any, ...] | None:
    baseline_export = record.get("baseline_export") or {}
    generated_export = record.get("generated_export") or {}
    metadata = record.get("cache_metadata") or {}
    baseline_sha = baseline_export.get("input_sha256") or metadata.get("baseline_sha256")
    generated_sha = generated_export.get("input_sha256") or metadata.get("generated_sha256")
    settings = metadata.get("settings")
    if not baseline_sha or not generated_sha or not isinstance(settings, dict):
        return None
    return ("buchi_distance", baseline_sha, generated_sha, json.dumps(settings, sort_keys=True))


def current_pair_key(record: dict[str, Any], args: argparse.Namespace, jar_path: Path) -> tuple[Any, ...]:
    baseline_spectra = resolve_input_path(str(record["source_spectra_file"]))
    generated_spectra_value = selected_generated_spectra_value(record, args.spectra_stage)
    if not generated_spectra_value:
        raise FileNotFoundError(f"No generated Spectra file recorded for stage {args.spectra_stage!r}.")
    generated_spectra = resolve_input_path(generated_spectra_value)
    settings = {
        "jar_sha256": sha256_file(jar_path),
        "max_states": args.max_states,
        "run_timeout": args.run_timeout,
        "jtlv": args.jtlv,
        "normalize_hoa": args.normalize_hoa,
        "add_rejecting_sink": args.add_rejecting_sink,
        "determinize": args.determinize,
        "distance_semantics": "relative_bscc_raw_valid_letter_mean_coverage_v1",
        "bounded_semantic_distance": args.bounded_semantic_distance,
        "bounded_depth": args.bounded_depth if args.bounded_semantic_distance else None,
        "bounded_mode": args.bounded_mode if args.bounded_semantic_distance else None,
        "bounded_samples": args.bounded_samples if args.bounded_semantic_distance and args.bounded_mode == "random" else None,
        "bounded_seed": args.bounded_seed if args.bounded_semantic_distance and args.bounded_mode == "random" else None,
        "bounded_max_prefixes": args.bounded_max_prefixes if args.bounded_semantic_distance and args.bounded_mode == "exhaustive" else None,
        "signature_mapping": args.signature_mapping,
        "mapping_model": args.mapping_model if args.signature_mapping == "llm" else None,
        "spectra_stage": args.spectra_stage,
    }
    return (
        "buchi_distance",
        sha256_file(baseline_spectra),
        sha256_file(generated_spectra),
        json.dumps(settings, sort_keys=True),
    )


def load_pair_cache(path: Path) -> dict[tuple[Any, ...], dict[str, Any]]:
    cache: dict[tuple[Any, ...], dict[str, Any]] = {}
    if not path.is_file():
        return cache
    for record in load_jsonl(path):
        key = result_pair_key(record)
        if key is not None:
            cache[key] = record
    return cache


def cached_record_for_run(cached: dict[str, Any], run_record: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    reused = copy.deepcopy(cached)
    reused["run"] = summarize_run(run_record, args.include_run_record)
    reused["comparison_id"] = stage_comparison_id(run_record, args.spectra_stage)
    reused["spectra_stage"] = args.spectra_stage
    reused["cache_reused"] = True
    reused["cache_source_comparison_id"] = cached.get("comparison_id")
    return reused


def timeout_result_for_run(
    *,
    record: dict[str, Any],
    args: argparse.Namespace,
    jar_path: Path,
) -> dict[str, Any]:
    comparison_id = stage_comparison_id(record, args.spectra_stage)
    result: dict[str, Any] = {
        "status": "run_timeout",
        "comparison_id": comparison_id,
        "spectra_stage": args.spectra_stage,
        "run": summarize_run(record, args.include_run_record),
        "baseline_export": None,
        "generated_export": None,
        "baseline_normalization": None,
        "generated_normalization": None,
        "baseline_determinization": None,
        "generated_determinization": None,
        "pre_mapping_alphabet_mismatch": None,
        "pre_mapping_alphabet_diagnostics": None,
        "signature_mapping_attempted": False,
        "signature_mapping_usable": None,
        "signature_mapping_used": False,
        "signature_mapping": None,
        "signature_mapping_record": None,
        "alphabet_diagnostics": None,
        "baseline_automaton": None,
        "generated_automaton": None,
        "baseline_automaton_after_determinization": None,
        "generated_automaton_after_determinization": None,
        "distance": None,
        "bounded_semantic_distance": None,
        "run_timeout_seconds": args.run_timeout,
        "error": f"Distance run exceeded --run-timeout={args.run_timeout} seconds.",
    }
    try:
        baseline_spectra = resolve_input_path(str(record["source_spectra_file"]))
        generated_spectra_value = selected_generated_spectra_value(record, args.spectra_stage)
        generated_spectra = resolve_input_path(str(generated_spectra_value)) if generated_spectra_value else None
        result["cache_metadata"] = {
            "baseline_sha256": sha256_file(baseline_spectra) if baseline_spectra.is_file() else None,
            "generated_sha256": sha256_file(generated_spectra) if generated_spectra and generated_spectra.is_file() else None,
            "settings": {
                "jar_sha256": sha256_file(jar_path) if jar_path.is_file() else None,
                "max_states": args.max_states,
                "run_timeout": args.run_timeout,
                "jtlv": args.jtlv,
                "normalize_hoa": args.normalize_hoa,
                "add_rejecting_sink": args.add_rejecting_sink,
                "determinize": args.determinize,
                "distance_semantics": "relative_bscc_raw_valid_letter_mean_coverage_v1",
                "bounded_semantic_distance": args.bounded_semantic_distance,
                "bounded_depth": args.bounded_depth if args.bounded_semantic_distance else None,
                "bounded_mode": args.bounded_mode if args.bounded_semantic_distance else None,
                "bounded_samples": args.bounded_samples if args.bounded_semantic_distance and args.bounded_mode == "random" else None,
                "bounded_seed": args.bounded_seed if args.bounded_semantic_distance and args.bounded_mode == "random" else None,
                "bounded_max_prefixes": args.bounded_max_prefixes if args.bounded_semantic_distance and args.bounded_mode == "exhaustive" else None,
                "signature_mapping": args.signature_mapping,
                "mapping_model": args.mapping_model if args.signature_mapping == "llm" else None,
                "spectra_stage": args.spectra_stage,
            },
        }
    except Exception as exc:
        result["cache_metadata_error"] = f"{type(exc).__name__}: {exc}"
    return result


def evaluate_one_run_worker(
    queue: multiprocessing.Queue,
    record: dict[str, Any],
    args: argparse.Namespace,
    jar_path: Path,
    artifacts_root: Path,
) -> None:
    try:
        queue.put(evaluate_one_run(record=record, args=args, jar_path=jar_path, artifacts_root=artifacts_root))
    except BaseException as exc:  # noqa: BLE001 - child process should return structured failure.
        queue.put(
            {
                "status": "failed",
                "comparison_id": stage_comparison_id(record, args.spectra_stage),
                "spectra_stage": args.spectra_stage,
                "run": summarize_run(record, args.include_run_record),
                "distance": None,
                "error": f"{type(exc).__name__}: {exc}",
            }
        )


def evaluate_one_run_with_timeout(
    *,
    record: dict[str, Any],
    args: argparse.Namespace,
    jar_path: Path,
    artifacts_root: Path,
) -> dict[str, Any]:
    if args.run_timeout is None or args.run_timeout <= 0:
        return evaluate_one_run(record=record, args=args, jar_path=jar_path, artifacts_root=artifacts_root)

    queue: multiprocessing.Queue = multiprocessing.Queue()
    process = multiprocessing.Process(
        target=evaluate_one_run_worker,
        args=(queue, record, args, jar_path, artifacts_root),
    )
    process.start()
    process.join(args.run_timeout)
    if process.is_alive():
        process.terminate()
        process.join(5)
        if process.is_alive() and hasattr(process, "kill"):
            process.kill()
            process.join(5)
        return timeout_result_for_run(record=record, args=args, jar_path=jar_path)

    if not queue.empty():
        return queue.get()
    result = timeout_result_for_run(record=record, args=args, jar_path=jar_path)
    result["status"] = "failed"
    result["error"] = f"Distance child process exited without a result. exitcode={process.exitcode}"
    return result


def select_matching_runs(
    records: list[dict[str, Any]],
    skill: str,
    model: str,
    spectra_stage: str = "final",
) -> tuple[list[dict[str, Any]], Counter[str]]:
    skipped: Counter[str] = Counter()
    selected: list[dict[str, Any]] = []

    for record in records:
        if record.get("skill") != skill:
            skipped["other_skill"] += 1
            continue
        if not model_matches(record, model):
            skipped["other_model"] += 1
            continue
        if record.get("status") != "success":
            skipped["run_not_success"] += 1
            continue
        if record.get("reported_cli_status") != "synthesized":
            skipped[f"cli_status_{record.get('reported_cli_status') or 'missing'}"] += 1
            continue
        if not selected_generated_spectra_value(record, spectra_stage):
            if spectra_stage == "final":
                skipped["missing_reconstructed_spectra_file"] += 1
            else:
                skipped[f"missing_spectra_stage_{spectra_stage}"] += 1
            continue
        if not record.get("source_spectra_file"):
            skipped["missing_source_spectra_file"] += 1
            continue
        selected.append(record)

    return selected, skipped


def automaton_summary(automaton) -> dict[str, Any]:
    return {
        "states": automaton.num_states(),
        "ap": [str(ap) for ap in automaton.ap()],
        "deterministic": bool(automaton.is_deterministic()),
        "complete": str(automaton.prop_complete()),
    }


def evaluate_one_run(
    *,
    record: dict[str, Any],
    args: argparse.Namespace,
    jar_path: Path,
    artifacts_root: Path,
) -> dict[str, Any]:
    comparison_id = stage_comparison_id(record, args.spectra_stage)
    pair_output_dir = artifacts_root / "hoa" / comparison_id
    baseline_hoa = pair_output_dir / "baseline.hoa"
    generated_hoa = pair_output_dir / "generated.hoa"
    baseline_distance_hoa = pair_output_dir / "baseline.normalized.hoa"
    generated_distance_hoa = pair_output_dir / "generated.normalized.hoa"
    generated_mapped_hoa = pair_output_dir / "generated.normalized.mapped.hoa"

    result: dict[str, Any] = {
        "status": "started",
        "comparison_id": comparison_id,
        "spectra_stage": args.spectra_stage,
        "run": summarize_run(record, args.include_run_record),
        "baseline_export": None,
        "generated_export": None,
        "baseline_normalization": None,
        "generated_normalization": None,
        "baseline_determinization": None,
        "generated_determinization": None,
        "pre_mapping_alphabet_mismatch": None,
        "pre_mapping_alphabet_diagnostics": None,
        "signature_mapping_attempted": False,
        "signature_mapping_usable": None,
        "signature_mapping_used": False,
        "signature_mapping": None,
        "signature_mapping_record": None,
        "alphabet_diagnostics": None,
        "baseline_automaton": None,
        "generated_automaton": None,
        "baseline_automaton_after_determinization": None,
        "generated_automaton_after_determinization": None,
        "distance": None,
        "bounded_semantic_distance": None,
        "error": None,
    }

    try:
        baseline_spectra = resolve_input_path(str(record["source_spectra_file"]))
        generated_spectra_value = selected_generated_spectra_value(record, args.spectra_stage)
        if not generated_spectra_value:
            raise FileNotFoundError(f"No generated Spectra file recorded for stage {args.spectra_stage!r}.")
        generated_spectra = resolve_input_path(generated_spectra_value)
        if not baseline_spectra.is_file():
            raise FileNotFoundError(f"Baseline Spectra file not found: {baseline_spectra}")
        if not generated_spectra.is_file():
            raise FileNotFoundError(f"Generated Spectra file not found: {generated_spectra}")
        result["cache_metadata"] = {
            "baseline_sha256": sha256_file(baseline_spectra),
            "generated_sha256": sha256_file(generated_spectra),
            "settings": {
                "jar_sha256": sha256_file(jar_path),
                "max_states": args.max_states,
                "run_timeout": args.run_timeout,
                "jtlv": args.jtlv,
                "normalize_hoa": args.normalize_hoa,
                "add_rejecting_sink": args.add_rejecting_sink,
                "determinize": args.determinize,
                "distance_semantics": "relative_bscc_raw_valid_letter_mean_coverage_v1",
                "bounded_semantic_distance": args.bounded_semantic_distance,
                "bounded_depth": args.bounded_depth if args.bounded_semantic_distance else None,
                "bounded_mode": args.bounded_mode if args.bounded_semantic_distance else None,
                "bounded_samples": args.bounded_samples if args.bounded_semantic_distance and args.bounded_mode == "random" else None,
                "bounded_seed": args.bounded_seed if args.bounded_semantic_distance and args.bounded_mode == "random" else None,
                "bounded_max_prefixes": args.bounded_max_prefixes if args.bounded_semantic_distance and args.bounded_mode == "exhaustive" else None,
                "signature_mapping": args.signature_mapping,
                "mapping_model": args.mapping_model if args.signature_mapping == "llm" else None,
                "spectra_stage": args.spectra_stage,
            },
        }

        baseline_export, baseline_ok = export_hoa(
            input_path=baseline_spectra,
            output_path=baseline_hoa,
            jar_path=jar_path,
            max_states=args.max_states,
            timeout=args.timeout,
            use_jtlv=args.jtlv,
            force=args.force,
            include_raw_output=args.include_raw_output,
            raw_output_tail_chars=args.raw_output_tail_chars,
        )
        generated_export, generated_ok = export_hoa(
            input_path=generated_spectra,
            output_path=generated_hoa,
            jar_path=jar_path,
            max_states=args.max_states,
            timeout=args.timeout,
            use_jtlv=args.jtlv,
            force=args.force,
            include_raw_output=args.include_raw_output,
            raw_output_tail_chars=args.raw_output_tail_chars,
        )
        result["baseline_export"] = baseline_export
        result["generated_export"] = generated_export

        if not (baseline_ok and generated_ok):
            result["status"] = "export_failed"
            return result

        if args.normalize_hoa:
            result["baseline_normalization"] = normalize_hoa_file(
                baseline_hoa,
                baseline_distance_hoa,
                add_rejecting_sink=args.add_rejecting_sink,
                force=args.force,
            )
            result["generated_normalization"] = normalize_hoa_file(
                generated_hoa,
                generated_distance_hoa,
                add_rejecting_sink=args.add_rejecting_sink,
                force=args.force,
            )
        else:
            baseline_distance_hoa = baseline_hoa
            generated_distance_hoa = generated_hoa

        spot = buchi_distance.require_spot()
        baseline_automaton = spot.automaton(str(baseline_distance_hoa))
        generated_automaton = spot.automaton(str(generated_distance_hoa))
        baseline_pre_mapping_summary = automaton_summary(baseline_automaton)
        generated_pre_mapping_summary = automaton_summary(generated_automaton)
        pre_mapping_alphabet_mismatch = baseline_pre_mapping_summary["ap"] != generated_pre_mapping_summary["ap"]
        result["pre_mapping_alphabet_mismatch"] = pre_mapping_alphabet_mismatch
        if pre_mapping_alphabet_mismatch:
            result["pre_mapping_alphabet_diagnostics"] = alphabet_diagnostics(
                {
                    "baseline_automaton": baseline_pre_mapping_summary,
                    "generated_automaton": generated_pre_mapping_summary,
                }
            )

        if args.signature_mapping == "llm" and pre_mapping_alphabet_mismatch:
            result["signature_mapping_attempted"] = True
            baseline_signature = parse_spectra_signature(baseline_spectra)
            generated_signature = parse_spectra_signature(generated_spectra)
            if (
                baseline_signature.get("status") == "success"
                and generated_signature.get("status") == "success"
            ):
                mapping_record = get_or_create_llm_mapping(
                    baseline_signature=baseline_signature,
                    generated_signature=generated_signature,
                    mapping_file=resolve_repo_path(args.signature_mapping_file),
                    model=args.mapping_model,
                    base_url=args.mapping_base_url,
                    timeout=args.mapping_timeout,
                    force=args.force_signature_mapping,
                )
                result["signature_mapping_record"] = {
                    "mapping_key": mapping_record.get("mapping_key"),
                    "api_status": mapping_record.get("api_status"),
                    "model": mapping_record.get("model"),
                    "usable": mapping_record.get("usable"),
                    "validation_errors": mapping_record.get("validation_errors"),
                }
                result["signature_mapping"] = mapping_record.get("mapping")
                result["signature_mapping_usable"] = bool(mapping_record.get("usable"))
                if mapping_record.get("usable"):
                    reverse_mapping = generated_to_baseline(mapping_record["mapping"])
                    mapped_text = apply_hoa_ap_mapping(
                        generated_distance_hoa.read_text(encoding="utf-8", errors="replace"),
                        reverse_mapping,
                    )
                    generated_mapped_hoa.write_text(mapped_text, encoding="utf-8")
                    generated_distance_hoa = generated_mapped_hoa
                    result["signature_mapping_used"] = True
            else:
                result["signature_mapping_usable"] = False

        baseline_automaton = spot.automaton(str(baseline_distance_hoa))
        generated_automaton = spot.automaton(str(generated_distance_hoa))
        result["baseline_automaton"] = automaton_summary(baseline_automaton)
        result["generated_automaton"] = automaton_summary(generated_automaton)

        if result["baseline_automaton"]["ap"] != result["generated_automaton"]["ap"]:
            result["status"] = "alphabet_mismatch"
            result["error"] = "Cannot compute distance: alphabet_mismatch"
            result["alphabet_diagnostics"] = alphabet_diagnostics(result)
            return result

        baseline_automaton, generated_automaton, baseline_det, generated_det = maybe_determinize_automata(
            baseline_automaton,
            generated_automaton,
            enabled=args.determinize,
        )
        result["baseline_determinization"] = baseline_det
        result["generated_determinization"] = generated_det
        result["baseline_automaton_after_determinization"] = automaton_summary(baseline_automaton)
        result["generated_automaton_after_determinization"] = automaton_summary(generated_automaton)

        compatible_result = {
            "baseline_automaton": result["baseline_automaton_after_determinization"],
            "generated_automaton": result["generated_automaton_after_determinization"],
        }
        compatible, incompatibility = automata_are_structurally_compatible(compatible_result)
        if not compatible:
            result["status"] = incompatibility
            result["error"] = f"Cannot compute distance: {incompatibility}"
            return result
        result["distance"] = buchi_distance.compute_buchi_distance(
            baseline_automaton,
            generated_automaton,
            debug=args.debug_distance,
        )
        if args.bounded_semantic_distance:
            result["bounded_semantic_distance"] = bounded_semantic_distance.compute_bounded_semantic_distance(
                baseline_automaton,
                generated_automaton,
                depth=args.bounded_depth,
                mode=args.bounded_mode,
                samples=args.bounded_samples,
                seed=args.bounded_seed,
                max_prefixes=args.bounded_max_prefixes,
            )
        result["status"] = "success"
        return result
    except SystemExit as exc:
        result["status"] = "distance_unavailable"
        result["error"] = str(exc)
        return result
    except Exception as exc:
        result["status"] = "failed"
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result


def percent(count: int, total: int) -> float:
    return 0.0 if total == 0 else 100.0 * count / total


def summarize_results(
    *,
    args: argparse.Namespace,
    total_matching_runs: int,
    selected_runs: int,
    evaluated_records: list[dict[str, Any]],
    skipped: Counter[str],
    output_jsonl: Path,
) -> dict[str, Any]:
    statuses = Counter(str(record.get("status")) for record in evaluated_records)
    distances = [float(record["distance"]) for record in evaluated_records if record.get("status") == "success"]

    def bounded_values(key: str) -> list[float]:
        values: list[float] = []
        for record in evaluated_records:
            bounded = record.get("bounded_semantic_distance") or {}
            value = bounded.get(key)
            if record.get("status") == "success" and value is not None:
                values.append(float(value))
        return values

    def stats(values: list[float]) -> dict[str, Any]:
        return {
            "count": len(values),
            "mean": statistics.fmean(values) if values else None,
            "median": statistics.median(values) if values else None,
            "min": min(values) if values else None,
            "max": max(values) if values else None,
        }

    bounded_summary = {
        "enabled": args.bounded_semantic_distance,
        "mismatch_rate": stats(bounded_values("mismatch_rate")),
        "false_negative_rate": stats(bounded_values("false_negative_rate")),
        "false_positive_rate": stats(bounded_values("false_positive_rate")),
        "jaccard_distance": stats(bounded_values("jaccard_distance")),
    }
    pre_mapping_alphabet_mismatch = sum(
        1 for record in evaluated_records if record.get("pre_mapping_alphabet_mismatch") is True
    )
    signature_mapping_attempted = sum(
        1 for record in evaluated_records if record.get("signature_mapping_attempted") is True
    )
    signature_mapping_usable = sum(
        1 for record in evaluated_records if record.get("signature_mapping_usable") is True
    )
    signature_mapping_used = sum(
        1 for record in evaluated_records if record.get("signature_mapping_used") is True
    )
    run_timeouts = sum(1 for record in evaluated_records if record.get("status") == "run_timeout")
    summary: dict[str, Any] = {
        "skill": args.skill,
        "model": args.model,
        "spectra_stage": args.spectra_stage,
        "matching_synthesized_runs": total_matching_runs,
        "selected_runs": selected_runs,
        "evaluated_runs": len(evaluated_records),
        "output_jsonl": str(output_jsonl),
        "status_counts": [
            {"status": status, "count": count, "percent": percent(count, len(evaluated_records))}
            for status, count in sorted(statuses.items())
        ],
        "skipped_counts": dict(sorted(skipped.items())),
        "distance": {
            "count": len(distances),
            "mean": statistics.fmean(distances) if distances else None,
            "median": statistics.median(distances) if distances else None,
            "min": min(distances) if distances else None,
            "max": max(distances) if distances else None,
        },
        "run_timeouts": {
            "count": run_timeouts,
            "percent": percent(run_timeouts, len(evaluated_records)),
            "timeout_seconds": args.run_timeout,
        },
        "bounded_semantic_distance": bounded_summary,
        "alphabet_mapping": {
            "mode": args.signature_mapping,
            "pre_mapping_alphabet_mismatch": {
                "count": pre_mapping_alphabet_mismatch,
                "percent": percent(pre_mapping_alphabet_mismatch, len(evaluated_records)),
            },
            "signature_mapping_attempted": {
                "count": signature_mapping_attempted,
                "percent": percent(signature_mapping_attempted, len(evaluated_records)),
            },
            "signature_mapping_usable": {
                "count": signature_mapping_usable,
                "percent": percent(signature_mapping_usable, len(evaluated_records)),
                "percent_of_attempted": percent(signature_mapping_usable, signature_mapping_attempted),
            },
            "signature_mapping_used": {
                "count": signature_mapping_used,
                "percent": percent(signature_mapping_used, len(evaluated_records)),
                "percent_of_pre_mapping_mismatches": percent(signature_mapping_used, pre_mapping_alphabet_mismatch),
            },
        },
    }
    return summary


def print_text_summary(summary: dict[str, Any]) -> None:
    print(f"Skill: {summary['skill']}")
    print(f"Model: {summary['model']}")
    print(f"Spectra stage: {summary['spectra_stage']}")
    print(f"Matching synthesized runs: {summary['matching_synthesized_runs']}")
    print(f"Selected runs: {summary['selected_runs']}")
    print(f"Evaluated runs: {summary['evaluated_runs']}")
    print(f"Results: {summary['output_jsonl']}")
    print()
    print("Statuses:")
    for item in summary["status_counts"]:
        print(f"  {item['status']}: {item['count']} ({item['percent']:.2f}%)")
    distance = summary["distance"]
    print()
    print(f"Successful distances: {distance['count']}")
    if distance["count"]:
        print(f"  mean: {distance['mean']:.6g}")
        print(f"  median: {distance['median']:.6g}")
        print(f"  min: {distance['min']:.6g}")
        print(f"  max: {distance['max']:.6g}")
    timeouts = summary["run_timeouts"]
    print(f"Run timeouts: {timeouts['count']} ({timeouts['percent']:.2f}%) at {timeouts['timeout_seconds']}s")
    alphabet_mapping = summary["alphabet_mapping"]
    print()
    print(f"Alphabet mapping mode: {alphabet_mapping['mode']}")
    mismatch = alphabet_mapping["pre_mapping_alphabet_mismatch"]
    attempted = alphabet_mapping["signature_mapping_attempted"]
    usable = alphabet_mapping["signature_mapping_usable"]
    used = alphabet_mapping["signature_mapping_used"]
    print(f"  pre-mapping alphabet mismatches: {mismatch['count']} ({mismatch['percent']:.2f}%)")
    print(f"  LLM mapping attempted: {attempted['count']} ({attempted['percent']:.2f}%)")
    print(
        "  LLM mapping usable: "
        f"{usable['count']} ({usable['percent']:.2f}% of evaluated, "
        f"{usable['percent_of_attempted']:.2f}% of attempted)"
    )
    print(
        "  LLM mapping applied: "
        f"{used['count']} ({used['percent']:.2f}% of evaluated, "
        f"{used['percent_of_pre_mapping_mismatches']:.2f}% of pre-mapping mismatches)"
    )
    bounded = summary["bounded_semantic_distance"]
    if bounded["enabled"]:
        print()
        print("Bounded semantic distance overview:")
        for key in ("mismatch_rate", "false_negative_rate", "false_positive_rate", "jaccard_distance"):
            values = bounded[key]
            print(f"  {key}: count={values['count']}", end="")
            if values["count"]:
                print(
                    f" mean={values['mean']:.6g} median={values['median']:.6g} "
                    f"min={values['min']:.6g} max={values['max']:.6g}"
                )
            else:
                print()


def print_intermediate_result(index: int, total: int, run_id: str, result: dict[str, Any]) -> None:
    status = result.get("status")
    distance = result.get("distance")
    if status == "success" and distance is not None:
        detail = f"distance={float(distance):.6g}"
        bounded = result.get("bounded_semantic_distance") or {}
        if bounded.get("mismatch_rate") is not None:
            detail += (
                f" bounded_mismatch={float(bounded['mismatch_rate']):.6g}"
                f" bounded_false_negative={float(bounded['false_negative_rate']):.6g}"
                f" bounded_false_positive={float(bounded['false_positive_rate']):.6g}"
            )
            if bounded.get("jaccard_distance") is not None:
                detail += f" bounded_jaccard={float(bounded['jaccard_distance']):.6g}"
            detail += (
                f" bounded_prefixes={bounded.get('total_prefixes')}"
                f" bounded_depth={bounded.get('depth')}"
                f" bounded_mode={bounded.get('mode')}"
            )
    else:
        error = result.get("error")
        detail = f"error={error}" if error else "distance=none"
    print(
        f"[{index}/{total}] result run_id={run_id or 'missing'} status={status} {detail}",
        file=sys.stderr,
    )


def main() -> int:
    args = parse_args()
    runs_manifest = resolve_existing_path(args.runs_manifest)
    records = load_jsonl(runs_manifest)
    matching, skipped = select_matching_runs(records, args.skill, args.model, args.spectra_stage)
    total_matching_runs = len(matching)
    if args.limit is not None:
        matching = matching[: args.limit]

    output_jsonl = default_output_jsonl(args)
    artifacts_root = output_root(args)
    jar_path = resolve_existing_path(args.jar)
    if not jar_path.is_file():
        print(json.dumps({"status": "error", "message": f"Modified spectra-cli.jar not found: {jar_path}"}, indent=2))
        return 2

    if args.preflight_java:
        major, java_output = java_major_version()
        if major is None or major < 17:
            summary = {
                "status": "java_unavailable" if major is None else "java_too_old",
                "message": (
                    "The modified Spectra CLI requires Java 17 or newer. "
                    f"Detected Java major version: {major if major is not None else 'unknown'}."
                ),
                "java_version_output": java_output,
                "skill": args.skill,
                "model": args.model,
                "spectra_stage": args.spectra_stage,
                "matching_synthesized_runs": total_matching_runs,
                "selected_runs": len(matching),
                "output_jsonl": str(output_jsonl),
            }
            print(json.dumps(summary, indent=2, sort_keys=True) if args.json else summary["message"])
            return 1

    if args.preflight_spot:
        try:
            buchi_distance.require_spot()
        except SystemExit as exc:
            summary = {
                "status": "distance_unavailable",
                "message": str(exc),
                "skill": args.skill,
                "model": args.model,
                "spectra_stage": args.spectra_stage,
                "matching_synthesized_runs": total_matching_runs,
                "selected_runs": len(matching),
                "output_jsonl": str(output_jsonl),
            }
            print(json.dumps(summary, indent=2, sort_keys=True) if args.json else summary["message"])
            return 1

    completed_run_ids = load_completed_run_ids(output_jsonl) if args.resume and not args.force else set()
    existing_run_ids = load_completed_run_ids(output_jsonl)
    pair_cache = load_pair_cache(output_jsonl) if args.reuse_existing and not args.force else {}
    evaluated_records: list[dict[str, Any]] = []
    if not args.resume and not args.reuse_existing and output_jsonl.exists():
        output_jsonl.unlink()

    for index, record in enumerate(matching, start=1):
        run_id = str(record.get("run_id") or "")
        if args.resume and run_id and run_id in completed_run_ids:
            print(f"[{index}/{len(matching)}] skipping existing distance run_id={run_id}", file=sys.stderr)
            continue
        if args.reuse_existing and not args.force:
            try:
                key = current_pair_key(record, args, jar_path)
            except Exception:
                key = None
            if key is not None and key in pair_cache:
                print(f"[{index}/{len(matching)}] reusing cached distance run_id={run_id or 'missing'}", file=sys.stderr)
                if not (run_id and run_id in existing_run_ids):
                    result = cached_record_for_run(pair_cache[key], record, args)
                    append_jsonl(output_jsonl, result)
                    existing_run_ids.add(run_id)
                    evaluated_records.append(result)
                continue
        print(f"[{index}/{len(matching)}] evaluating run_id={run_id or 'missing'}", file=sys.stderr)
        result = evaluate_one_run_with_timeout(record=record, args=args, jar_path=jar_path, artifacts_root=artifacts_root)
        print_intermediate_result(index, len(matching), run_id, result)
        if result.get("status") == "alphabet_mismatch":
            diagnostics = result.get("alphabet_diagnostics") or {}
            print(f"[{index}/{len(matching)}] alphabet mismatch for run_id={run_id or 'missing'}", file=sys.stderr)
            print(f"  baseline_ap: {diagnostics.get('baseline_ap')}", file=sys.stderr)
            print(f"  generated_ap: {diagnostics.get('generated_ap')}", file=sys.stderr)
            print(f"  baseline_only: {diagnostics.get('baseline_only')}", file=sys.stderr)
            print(f"  generated_only: {diagnostics.get('generated_only')}", file=sys.stderr)
        append_jsonl(output_jsonl, result)
        evaluated_records.append(result)
        key = result_pair_key(result)
        if key is not None:
            pair_cache[key] = result

    if (args.resume or args.reuse_existing) and output_jsonl.is_file():
        evaluated_records = load_jsonl(output_jsonl)

    summary = summarize_results(
        args=args,
        total_matching_runs=total_matching_runs,
        selected_runs=len(matching),
        evaluated_records=evaluated_records,
        skipped=skipped,
        output_jsonl=output_jsonl,
    )
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print_text_summary(summary)
    return 0 if all(record.get("status") == "success" for record in evaluated_records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
