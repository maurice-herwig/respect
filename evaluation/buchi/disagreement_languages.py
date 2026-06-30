#!/usr/bin/env python3
r"""Build directed language-difference automata for two Spectra specifications.

The cross-broker experiment needs two omega-regular language sets:

* L(left)  \ L(right)
* L(right) \ L(left)

This module reuses the existing Spectra-to-HOA export, HOA normalization,
alphabet checks, and determinization helpers from `evaluate_reconstruction_distances.py`.
It deliberately stops at language-set automata plus non-emptiness metadata;
human-readable witness extraction can be layered on top of these automata later.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evaluation.buchi import buchi_distance
from evaluation.buchi.evaluate_reconstruction_distances import (
    DEFAULT_JAR,
    alphabet_diagnostics,
    automata_are_structurally_compatible,
    automaton_summary,
    export_hoa,
    maybe_determinize_automata,
    normalize_hoa_file,
    repo_relative_or_absolute,
    resolve_existing_path,
    resolve_repo_path,
)


DEFAULT_OUTPUT_DIR = REPO_ROOT / "evaluation" / "buchi" / "disagreement_languages"


@dataclass(frozen=True)
class DifferenceAutomata:
    """Directed language-difference automata for a pair of inputs."""

    left_minus_right: object
    right_minus_left: object


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the standalone comparison helper."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--left", required=True, help="Left Spectra file.")
    parser.add_argument("--right", required=True, help="Right Spectra file.")
    parser.add_argument("--out", default=None, help="Optional JSON output file.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--jar", default=str(DEFAULT_JAR))
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--max-states", type=int, default=100_000)
    parser.add_argument("--jtlv", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--normalize-hoa", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--add-rejecting-sink", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--determinize", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--include-raw-output", action="store_true")
    parser.add_argument("--raw-output-tail-chars", type=int, default=4000)
    parser.add_argument("--write-difference-hoa", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args()


def require_language_ops_spot():
    """Import Spot and check the operations needed for directed differences."""
    spot = buchi_distance.require_spot()
    required = ("product",)
    missing = [name for name in required if not hasattr(spot, name)]
    if missing:
        raise SystemExit(f"Spot installation lacks required language operation(s): {', '.join(missing)}")
    return spot


def complement_automaton(automaton):
    """Return an automaton for the complement language.

    Spot versions expose complement either as a module-level function or as an
    automaton method. Keep both forms to avoid binding this project to one API
    spelling.
    """
    spot = require_language_ops_spot()
    if hasattr(spot, "complement"):
        return spot.complement(automaton)
    if hasattr(spot, "dualize"):
        return spot.dualize(automaton)
    if hasattr(automaton, "complement"):
        return automaton.complement()
    raise SystemExit("Spot installation lacks a complement operation.")


def intersection_automaton(left_automaton, right_automaton):
    """Return an automaton for the intersection of two languages."""
    spot = require_language_ops_spot()
    product = spot.product(left_automaton, right_automaton)
    return spot.postprocess(product, "generic", "deterministic")


def language_difference_automaton(left_automaton, right_automaton):
    """Return an automaton for L(left) \\ L(right)."""
    right_complement = complement_automaton(right_automaton)
    return intersection_automaton(left_automaton, right_complement)


def accepting_run_exists(automaton) -> bool | None:
    """Best-effort non-emptiness check for a Spot automaton.

    Returns `None` when the installed Spot binding does not expose a known
    emptiness method. The difference automaton is still useful in that case.
    """
    if hasattr(automaton, "is_empty"):
        return not bool(automaton.is_empty())
    if hasattr(automaton, "accepting_run"):
        return automaton.accepting_run() is not None
    return None


def compute_difference_automata(left_automaton, right_automaton, *, determinize: bool = True) -> tuple[DifferenceAutomata | None, dict[str, Any]]:
    """Compute L(left)\\L(right) and L(right)\\L(left) automata.

    The function assumes both automata already encode the intended Spectra
    language semantics, e.g. after HOA normalization. It performs the same AP
    and deterministic-structure checks used by the distance pipeline.
    """
    result: dict[str, Any] = {
        "status": "started",
        "left_automaton": automaton_summary(left_automaton),
        "right_automaton": automaton_summary(right_automaton),
        "left_determinization": None,
        "right_determinization": None,
        "left_after_determinization": None,
        "right_after_determinization": None,
        "alphabet_diagnostics": None,
        "left_minus_right": None,
        "right_minus_left": None,
        "error": None,
    }

    if result["left_automaton"]["ap"] != result["right_automaton"]["ap"]:
        result["status"] = "alphabet_mismatch"
        result["error"] = "Cannot compute language differences: alphabet_mismatch"
        result["alphabet_diagnostics"] = alphabet_diagnostics(
            {
                "baseline_automaton": result["left_automaton"],
                "generated_automaton": result["right_automaton"],
            }
        )
        return None, result

    left_automaton, right_automaton, left_det, right_det = maybe_determinize_automata(
        left_automaton,
        right_automaton,
        enabled=determinize,
    )
    result["left_determinization"] = left_det
    result["right_determinization"] = right_det
    result["left_after_determinization"] = automaton_summary(left_automaton)
    result["right_after_determinization"] = automaton_summary(right_automaton)

    compatible, incompatibility = automata_are_structurally_compatible(
        {
            "baseline_automaton": result["left_after_determinization"],
            "generated_automaton": result["right_after_determinization"],
        }
    )
    if not compatible:
        result["status"] = incompatibility
        result["error"] = f"Cannot compute language differences: {incompatibility}"
        return None, result

    left_minus_right = language_difference_automaton(left_automaton, right_automaton)
    right_minus_left = language_difference_automaton(right_automaton, left_automaton)
    result["left_minus_right"] = {
        "automaton": automaton_summary(left_minus_right),
        "nonempty": accepting_run_exists(left_minus_right),
    }
    result["right_minus_left"] = {
        "automaton": automaton_summary(right_minus_left),
        "nonempty": accepting_run_exists(right_minus_left),
    }
    result["status"] = "success"
    return DifferenceAutomata(left_minus_right, right_minus_left), result


def compute_disagreement_language_sets(left_automaton, right_automaton, *, determinize: bool = True) -> tuple[DifferenceAutomata | None, dict[str, Any]]:
    """Compute the two language sets needed by the cross-broker feedback loop.

    This is a descriptive alias for `compute_difference_automata`:

    - `left_minus_right` represents L(left) \\ L(right)
    - `right_minus_left` represents L(right) \\ L(left)
    """
    return compute_difference_automata(left_automaton, right_automaton, determinize=determinize)


def write_difference_hoa_files(differences: DifferenceAutomata, output_dir: Path, result: dict[str, Any]) -> None:
    """Persist the directed difference automata as HOA files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    left_minus_right_path = output_dir / "left_minus_right.hoa"
    right_minus_left_path = output_dir / "right_minus_left.hoa"
    left_minus_right_path.write_text(differences.left_minus_right.to_str("hoa"), encoding="utf-8")
    right_minus_left_path.write_text(differences.right_minus_left.to_str("hoa"), encoding="utf-8")
    result["left_minus_right"]["hoa_file"] = repo_relative_or_absolute(left_minus_right_path)
    result["right_minus_left"]["hoa_file"] = repo_relative_or_absolute(right_minus_left_path)


def compute_spectra_language_differences(
    *,
    left_spectra: Path,
    right_spectra: Path,
    output_dir: Path,
    jar_path: Path,
    max_states: int = 100_000,
    timeout: float = 120.0,
    use_jtlv: bool = True,
    normalize_hoa: bool = True,
    add_rejecting_sink: bool = True,
    determinize: bool = True,
    force: bool = False,
    include_raw_output: bool = False,
    raw_output_tail_chars: int = 4000,
    write_difference_hoa: bool = True,
) -> dict[str, Any]:
    """Export two Spectra files and compute directed language differences."""
    left_hoa = output_dir / "left.hoa"
    right_hoa = output_dir / "right.hoa"
    left_normalized = output_dir / "left.normalized.hoa"
    right_normalized = output_dir / "right.normalized.hoa"

    result: dict[str, Any] = {
        "status": "started",
        "left_spectra": repo_relative_or_absolute(left_spectra),
        "right_spectra": repo_relative_or_absolute(right_spectra),
        "left_export": None,
        "right_export": None,
        "left_normalization": None,
        "right_normalization": None,
        "difference": None,
        "error": None,
    }

    left_export, left_ok = export_hoa(
        input_path=left_spectra,
        output_path=left_hoa,
        jar_path=jar_path,
        max_states=max_states,
        timeout=timeout,
        use_jtlv=use_jtlv,
        force=force,
        include_raw_output=include_raw_output,
        raw_output_tail_chars=raw_output_tail_chars,
    )
    right_export, right_ok = export_hoa(
        input_path=right_spectra,
        output_path=right_hoa,
        jar_path=jar_path,
        max_states=max_states,
        timeout=timeout,
        use_jtlv=use_jtlv,
        force=force,
        include_raw_output=include_raw_output,
        raw_output_tail_chars=raw_output_tail_chars,
    )
    result["left_export"] = left_export
    result["right_export"] = right_export
    if not (left_ok and right_ok):
        result["status"] = "export_failed"
        return result

    if normalize_hoa:
        result["left_normalization"] = normalize_hoa_file(
            left_hoa,
            left_normalized,
            add_rejecting_sink=add_rejecting_sink,
            force=force,
        )
        result["right_normalization"] = normalize_hoa_file(
            right_hoa,
            right_normalized,
            add_rejecting_sink=add_rejecting_sink,
            force=force,
        )
    else:
        left_normalized = left_hoa
        right_normalized = right_hoa

    try:
        spot = buchi_distance.require_spot()
        left_automaton = spot.automaton(str(left_normalized))
        right_automaton = spot.automaton(str(right_normalized))
        differences, difference_result = compute_difference_automata(
            left_automaton,
            right_automaton,
            determinize=determinize,
        )
        if differences is not None and write_difference_hoa:
            write_difference_hoa_files(differences, output_dir, difference_result)
        result["difference"] = difference_result
        result["status"] = difference_result["status"]
        result["error"] = difference_result.get("error")
        return result
    except SystemExit as exc:
        result["status"] = "spot_unavailable"
        result["error"] = str(exc)
        return result
    except Exception as exc:
        result["status"] = "failed"
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result


def main() -> int:
    """Run the standalone Spectra language-difference helper."""
    args = parse_args()
    left = resolve_existing_path(args.left)
    right = resolve_existing_path(args.right)
    jar = resolve_existing_path(args.jar)
    output_dir = resolve_repo_path(args.output_dir)

    result = compute_spectra_language_differences(
        left_spectra=left,
        right_spectra=right,
        output_dir=output_dir,
        jar_path=jar,
        max_states=args.max_states,
        timeout=args.timeout,
        use_jtlv=args.jtlv,
        normalize_hoa=args.normalize_hoa,
        add_rejecting_sink=args.add_rejecting_sink,
        determinize=args.determinize,
        force=args.force,
        include_raw_output=args.include_raw_output,
        raw_output_tail_chars=args.raw_output_tail_chars,
        write_difference_hoa=args.write_difference_hoa,
    )

    output = json.dumps(result, indent=2, sort_keys=True)
    if args.out:
        out_path = resolve_repo_path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output + "\n", encoding="utf-8")
    print(output)
    return 0 if result.get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
