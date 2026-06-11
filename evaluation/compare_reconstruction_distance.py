#!/usr/bin/env python3
"""Export one reconstructed/baseline Spectra pair to HOA and compute distance."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evaluation import buchi_distance
from evaluation.export_spectra_to_hoa import (
    DEFAULT_JAR,
    build_command,
    output_fields,
    repo_relative_or_absolute,
    resolve_existing_path,
    resolve_input_path,
    sha256_file,
    utc_now,
)
from evaluation.normalize_hoa_state_labels import transform_hoa_state_labels_to_transitions
from evaluation.summarize_reconstruction_runs import extract_model_label


DEFAULT_RUNS_MANIFEST = REPO_ROOT / "experiments" / "runs" / "runs.jsonl"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "evaluation" / "hoa_exports" / "comparisons"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare one reconstructed Spectra file against its accepted-dataset baseline. "
            "By default, the first synthesized run in experiments/runs/runs.jsonl is used."
        )
    )
    parser.add_argument("--runs-manifest", default=str(DEFAULT_RUNS_MANIFEST))
    parser.add_argument("--run-id", default=None, help="Run id from experiments/runs/runs.jsonl.")
    parser.add_argument("--skill", default="respect-method-2", help="Filter runs by skill when --run-id is omitted.")
    parser.add_argument("--model", default=None, help="Optional model label/path-segment filter when --run-id is omitted.")
    parser.add_argument("--generated-spectra", default=None, help="Explicit reconstructed .spectra path.")
    parser.add_argument("--baseline-spectra", default=None, help="Explicit accepted-dataset baseline .spectra path.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for generated HOA files.")
    parser.add_argument("--jar", default=str(DEFAULT_JAR), help="Path to the modified spectra-cli.jar.")
    parser.add_argument("--max-states", type=int, default=100_000)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument(
        "--jtlv",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use the Java BDD backend for HOA export. Enabled by default.",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing HOA files.")
    parser.add_argument("--debug-distance", action="store_true", help="Enable debug output in buchi_distance.")
    parser.add_argument(
        "--normalize-hoa",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Move Spectra CLI state labels to transition labels before loading with Spot.",
    )
    parser.add_argument(
        "--add-rejecting-sink",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="During HOA normalization, add a rejecting sink for missing valuations.",
    )
    parser.add_argument(
        "--determinize",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use Spot postprocessing to determinize nondeterministic automata before distance computation.",
    )
    parser.add_argument("--include-run-record", action="store_true", help="Include the full run JSON record in output.")
    parser.add_argument("--include-raw-output", action="store_true", help="Include full Spectra CLI output in JSON.")
    parser.add_argument("--raw-output-tail-chars", type=int, default=2000)
    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in {path} at line {line_number}: {exc}") from exc
    return records


def model_matches(record: dict[str, Any], model: str | None) -> bool:
    if model is None:
        return True
    return extract_model_label(record) == model


def select_run(records: list[dict[str, Any]], run_id: str | None, skill: str, model: str | None) -> dict[str, Any]:
    if run_id:
        for record in records:
            if record.get("run_id") == run_id:
                return record
        raise ValueError(f"Run id not found: {run_id}")

    for record in records:
        if record.get("skill") != skill:
            continue
        if record.get("status") != "success":
            continue
        if record.get("reported_cli_status") != "synthesized":
            continue
        if not record.get("reconstructed_spectra_file") or not record.get("source_spectra_file"):
            continue
        if not model_matches(record, model):
            continue
        return record

    model_message = f" and model={model}" if model else ""
    raise ValueError(f"No synthesized run found for skill={skill}{model_message}.")


def safe_path_part(value: str, max_length: int = 120) -> str:
    safe = "".join(char if char.isalnum() or char in "._=-" else "_" for char in value).strip("_")
    return (safe or "value")[:max_length]


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
        result = {
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
        }
        return result, True

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists() and force:
        output_path.unlink()

    command = build_command(jar_path, input_path, output_path, max_states, use_jtlv)
    started_at = utc_now()
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raw_output = "\n".join(part for part in (exc.stdout or "", exc.stderr or "") if part).strip()
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
            "started_at": started_at,
            "finished_at": utc_now(),
        }
        result.update(output_fields(raw_output, include_raw_output, raw_output_tail_chars))
        return result, False

    raw_output = completed.stdout or ""
    if completed.stderr:
        raw_output = f"{raw_output}\n{completed.stderr}".strip()

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
        "started_at": started_at,
        "finished_at": utc_now(),
    }
    result.update(output_fields(raw_output, include_raw_output, raw_output_tail_chars))
    return result, ok


def load_hoa(path: Path):
    spot = buchi_distance.require_spot()
    return spot.automaton(str(path))


def normalize_hoa_file(input_path: Path, output_path: Path, add_rejecting_sink: bool, force: bool) -> dict[str, Any]:
    if output_path.exists() and not force:
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


def automata_are_distance_compatible(result: dict[str, Any]) -> tuple[bool, str | None]:
    baseline = result.get("baseline_automaton") or {}
    generated = result.get("generated_automaton") or {}

    if baseline.get("ap") != generated.get("ap"):
        return False, "alphabet_mismatch"
    if baseline.get("deterministic") is not True or generated.get("deterministic") is not True:
        return False, "nondeterministic_automaton"
    if baseline.get("complete") != "yes" or generated.get("complete") != "yes":
        return False, "incomplete_automaton"
    return True, None


def alphabet_diagnostics(result: dict[str, Any]) -> dict[str, Any]:
    baseline = result.get("baseline_automaton") or {}
    generated = result.get("generated_automaton") or {}
    baseline_ap = list(baseline.get("ap") or [])
    generated_ap = list(generated.get("ap") or [])
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
    if baseline.get("complete") != "yes" or generated.get("complete") != "yes":
        return False, "incomplete_automaton"
    return True, None


def determinize_automaton_for_distance(automaton):
    """Return a deterministic and complete Spot automaton for distance computation."""
    spot = buchi_distance.require_spot()

    candidates = [
        ("generic", ("generic", "deterministic", "complete")),
        ("parity", ("parity", "deterministic", "complete")),
        ("rabin", ("rabin", "deterministic", "complete")),
        ("deterministic_complete", ("deterministic", "complete")),
    ]
    errors: list[str] = []

    for name, options in candidates:
        try:
            processed = spot.postprocess(automaton, *options)
        except Exception as exc:
            errors.append(f"{name}: {type(exc).__name__}: {exc}")
            continue
        if processed.is_deterministic() and str(processed.prop_complete()) == "yes":
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


def maybe_determinize_automata(
    baseline_automaton,
    generated_automaton,
    *,
    enabled: bool,
) -> tuple[Any, Any, dict[str, Any], dict[str, Any]]:
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

    if not baseline_automaton.is_deterministic() or str(baseline_automaton.prop_complete()) != "yes":
        baseline_automaton, baseline_info = determinize_automaton_for_distance(baseline_automaton)
    if not generated_automaton.is_deterministic() or str(generated_automaton.prop_complete()) != "yes":
        generated_automaton, generated_info = determinize_automaton_for_distance(generated_automaton)

    return baseline_automaton, generated_automaton, baseline_info, generated_info


def print_result(result: dict[str, Any]) -> None:
    print(json.dumps(result, indent=2, sort_keys=True))


def main() -> int:
    args = parse_args()

    if args.generated_spectra or args.baseline_spectra:
        if not args.generated_spectra or not args.baseline_spectra:
            print_result({"status": "error", "message": "Use both --generated-spectra and --baseline-spectra."})
            return 2
        run_record: dict[str, Any] | None = None
        generated_spectra = resolve_input_path(args.generated_spectra)
        baseline_spectra = resolve_input_path(args.baseline_spectra)
        comparison_id = f"manual__{sha256_file(generated_spectra)[:12]}__{sha256_file(baseline_spectra)[:12]}"
    else:
        runs_manifest = resolve_existing_path(args.runs_manifest)
        records = load_jsonl(runs_manifest)
        run_record = select_run(records, args.run_id, args.skill, args.model)
        generated_spectra = resolve_input_path(str(run_record["reconstructed_spectra_file"]))
        baseline_spectra = resolve_input_path(str(run_record["source_spectra_file"]))
        comparison_id = safe_path_part(str(run_record.get("run_id") or run_record.get("run_key") or "run"))

    if not generated_spectra.is_file():
        print_result({"status": "error", "message": f"Generated Spectra file not found: {generated_spectra}"})
        return 2
    if not baseline_spectra.is_file():
        print_result({"status": "error", "message": f"Baseline Spectra file not found: {baseline_spectra}"})
        return 2

    jar_path = resolve_existing_path(args.jar)
    if not jar_path.is_file():
        print_result({"status": "error", "message": f"Modified spectra-cli.jar not found: {jar_path}"})
        return 2

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = REPO_ROOT / output_dir
    pair_output_dir = output_dir / comparison_id
    generated_hoa = pair_output_dir / "generated.hoa"
    baseline_hoa = pair_output_dir / "baseline.hoa"
    generated_distance_hoa = pair_output_dir / "generated.normalized.hoa"
    baseline_distance_hoa = pair_output_dir / "baseline.normalized.hoa"

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

    result: dict[str, Any] = {
        "status": "export_failed" if not (baseline_ok and generated_ok) else "exported",
        "comparison_id": comparison_id,
        "run": summarize_run(run_record, args.include_run_record),
        "baseline_export": baseline_export,
        "generated_export": generated_export,
        "baseline_normalization": None,
        "generated_normalization": None,
        "baseline_determinization": None,
        "generated_determinization": None,
        "alphabet_diagnostics": None,
        "distance": None,
        "distance_error": None,
    }

    if not (baseline_ok and generated_ok):
        print_result(result)
        return 1

    try:
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

        baseline_automaton = load_hoa(baseline_distance_hoa)
        generated_automaton = load_hoa(generated_distance_hoa)
        result["baseline_automaton"] = {
            "states": baseline_automaton.num_states(),
            "ap": [str(ap) for ap in baseline_automaton.ap()],
            "deterministic": bool(baseline_automaton.is_deterministic()),
            "complete": str(baseline_automaton.prop_complete()),
        }
        result["generated_automaton"] = {
            "states": generated_automaton.num_states(),
            "ap": [str(ap) for ap in generated_automaton.ap()],
            "deterministic": bool(generated_automaton.is_deterministic()),
            "complete": str(generated_automaton.prop_complete()),
        }

        if result["baseline_automaton"]["ap"] != result["generated_automaton"]["ap"]:
            result["status"] = "alphabet_mismatch"
            result["distance_error"] = "Cannot compute distance: alphabet_mismatch"
            result["alphabet_diagnostics"] = alphabet_diagnostics(result)
            print_result(result)
            return 1

        baseline_automaton, generated_automaton, baseline_det, generated_det = maybe_determinize_automata(
            baseline_automaton,
            generated_automaton,
            enabled=args.determinize,
        )
        result["baseline_determinization"] = baseline_det
        result["generated_determinization"] = generated_det
        result["baseline_automaton_after_determinization"] = {
            "states": baseline_automaton.num_states(),
            "ap": [str(ap) for ap in baseline_automaton.ap()],
            "deterministic": bool(baseline_automaton.is_deterministic()),
            "complete": str(baseline_automaton.prop_complete()),
        }
        result["generated_automaton_after_determinization"] = {
            "states": generated_automaton.num_states(),
            "ap": [str(ap) for ap in generated_automaton.ap()],
            "deterministic": bool(generated_automaton.is_deterministic()),
            "complete": str(generated_automaton.prop_complete()),
        }

        compatible_result = {
            "baseline_automaton": result["baseline_automaton_after_determinization"],
            "generated_automaton": result["generated_automaton_after_determinization"],
        }
        compatible, incompatibility = automata_are_structurally_compatible(compatible_result)
        if not compatible:
            result["status"] = incompatibility
            result["distance_error"] = f"Cannot compute distance: {incompatibility}"
            print_result(result)
            return 1

        result["distance"] = buchi_distance.compute_buchi_distance(
            baseline_automaton,
            generated_automaton,
            debug=args.debug_distance,
        )
        result["status"] = "success"
        print_result(result)
        return 0
    except SystemExit as exc:
        result["status"] = "distance_unavailable"
        result["distance_error"] = str(exc)
        print_result(result)
        return 1
    except Exception as exc:
        result["status"] = "distance_failed"
        result["distance_error"] = f"{type(exc).__name__}: {exc}"
        print_result(result)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
