#!/usr/bin/env python3
"""Smoke test that the distance computation can produce a non-zero distance."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evaluation.buchi import buchi_distance
from evaluation.buchi.evaluate_reconstruction_distances import (
    DEFAULT_JAR,
    automata_are_structurally_compatible,
    automaton_summary,
    export_hoa,
    maybe_determinize_automata,
    normalize_hoa_file,
    resolve_existing_path,
)


FIXTURE_DIR = REPO_ROOT / "evaluation" / "buchi" / "fixtures" / "distance_nonzero"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "evaluation" / "buchi" / "distance_results" / "fixtures" / "distance_nonzero"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("spot-formula", "spectra-cli"),
        default="spot-formula",
        help=(
            "spot-formula translates two Spot formulas directly and does not use the "
            "modified Spectra CLI. spectra-cli keeps the end-to-end Spectra-to-HOA path."
        ),
    )
    parser.add_argument("--left-formula", default="F signal")
    parser.add_argument("--right-formula", default="G signal")
    parser.add_argument("--left", default=str(FIXTURE_DIR / "unconstrained.spectra"))
    parser.add_argument("--right", default=str(FIXTURE_DIR / "always_true.spectra"))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--jar", default=str(DEFAULT_JAR))
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--max-states", type=int, default=100_000)
    parser.add_argument("--jtlv", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--debug-distance", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def evaluate_pair(left_aut, right_aut, result: dict, debug_distance: bool) -> int:
    result["left_automaton"] = automaton_summary(left_aut)
    result["right_automaton"] = automaton_summary(right_aut)

    if result["left_automaton"]["ap"] != result["right_automaton"]["ap"]:
        result["status"] = "alphabet_mismatch"
        result["error"] = "Fixture alphabets differ unexpectedly."
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1

    left_aut, right_aut, left_det, right_det = maybe_determinize_automata(left_aut, right_aut, enabled=True)
    result["left_determinization"] = left_det
    result["right_determinization"] = right_det
    result["left_after_determinization"] = automaton_summary(left_aut)
    result["right_after_determinization"] = automaton_summary(right_aut)

    compatible_result = {
        "baseline_automaton": result["left_after_determinization"],
        "generated_automaton": result["right_after_determinization"],
    }
    compatible, incompatibility = automata_are_structurally_compatible(compatible_result)
    if not compatible:
        result["status"] = incompatibility
        result["error"] = f"Cannot compute distance: {incompatibility}"
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1

    result["distance"] = buchi_distance.compute_buchi_distance(left_aut, right_aut, debug=debug_distance)
    result["status"] = "success" if result["distance"] > 0.0 else "unexpected_zero_distance"
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["distance"] > 0.0 else 1


def run_spot_formula_mode(args: argparse.Namespace) -> int:
    result = {
        "status": "started",
        "mode": "spot-formula",
        "left_formula": args.left_formula,
        "right_formula": args.right_formula,
        "left_export": None,
        "right_export": None,
        "left_normalization": None,
        "right_normalization": None,
        "left_automaton": None,
        "right_automaton": None,
        "left_determinization": None,
        "right_determinization": None,
        "left_after_determinization": None,
        "right_after_determinization": None,
        "distance": None,
        "error": None,
    }

    try:
        spot = buchi_distance.require_spot()
        left_aut = spot.translate(args.left_formula, "generic", "deterministic", "complete")
        right_aut = spot.translate(args.right_formula, "generic", "deterministic", "complete")
        return evaluate_pair(left_aut, right_aut, result, args.debug_distance)
    except Exception as exc:
        result["status"] = "failed"
        result["error"] = f"{type(exc).__name__}: {exc}"
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1


def run_spectra_cli_mode(args: argparse.Namespace) -> int:
    left = resolve_existing_path(args.left)
    right = resolve_existing_path(args.right)
    jar = resolve_existing_path(args.jar)
    output_dir = resolve_existing_path(args.output_dir) if Path(args.output_dir).exists() else Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = REPO_ROOT / output_dir

    left_hoa = output_dir / "left.hoa"
    right_hoa = output_dir / "right.hoa"
    left_normalized = output_dir / "left.normalized.hoa"
    right_normalized = output_dir / "right.normalized.hoa"

    left_export, left_ok = export_hoa(
        input_path=left,
        output_path=left_hoa,
        jar_path=jar,
        max_states=args.max_states,
        timeout=args.timeout,
        use_jtlv=args.jtlv,
        force=args.force,
        include_raw_output=False,
        raw_output_tail_chars=1000,
    )
    right_export, right_ok = export_hoa(
        input_path=right,
        output_path=right_hoa,
        jar_path=jar,
        max_states=args.max_states,
        timeout=args.timeout,
        use_jtlv=args.jtlv,
        force=args.force,
        include_raw_output=False,
        raw_output_tail_chars=1000,
    )

    result = {
        "status": "started",
        "mode": "spectra-cli",
        "left_formula": None,
        "right_formula": None,
        "left_export": left_export,
        "right_export": right_export,
        "left_normalization": None,
        "right_normalization": None,
        "left_automaton": None,
        "right_automaton": None,
        "left_determinization": None,
        "right_determinization": None,
        "left_after_determinization": None,
        "right_after_determinization": None,
        "distance": None,
        "error": None,
    }

    if not (left_ok and right_ok):
        result["status"] = "export_failed"
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1

    try:
        result["left_normalization"] = normalize_hoa_file(left_hoa, left_normalized, add_rejecting_sink=True, force=args.force)
        result["right_normalization"] = normalize_hoa_file(right_hoa, right_normalized, add_rejecting_sink=True, force=args.force)

        spot = buchi_distance.require_spot()
        left_aut = spot.automaton(str(left_normalized))
        right_aut = spot.automaton(str(right_normalized))
        return evaluate_pair(left_aut, right_aut, result, args.debug_distance)
    except Exception as exc:
        result["status"] = "failed"
        result["error"] = f"{type(exc).__name__}: {exc}"
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1


def main() -> int:
    args = parse_args()
    if args.mode == "spot-formula":
        return run_spot_formula_mode(args)
    return run_spectra_cli_mode(args)


if __name__ == "__main__":
    raise SystemExit(main())
