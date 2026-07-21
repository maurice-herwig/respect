"""Print the HOA files for a successful Buchi-distance comparison."""

from __future__ import annotations

import argparse
import itertools
import json
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DISTANCE_ROOT = REPO_ROOT / "evaluation" / "buchi" / "distance_results"
DEFAULT_RUNS_MANIFEST = REPO_ROOT / "experiments" / "runs" / "runs.jsonl"
DISTANCE_EVALUATOR = REPO_ROOT / "evaluation" / "buchi" / "evaluate_reconstruction_distances.py"
DEFAULT_GRAPH_OUTPUT_DIR = Path("/tmp") / "respect_hoa_graphs"
sys.path.insert(0, str(REPO_ROOT))

from evaluation.buchi import buchi_distance  # noqa: E402
from evaluation.buchi import bounded_semantic_distance  # noqa: E402


def resolve_repo_path(value: str | None) -> Path | None:
    if not value:
        return None
    normalized = value.replace("\\", "/")
    if len(normalized) >= 3 and normalized[1] == ":" and normalized[2] == "/":
        drive = normalized[0].lower()
        rest = normalized[2:]
        wsl_path = Path(f"/mnt/{drive}{rest}")
        if wsl_path.exists() or str(REPO_ROOT).startswith(f"/mnt/{drive}/"):
            return wsl_path
    path = Path(normalized)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def default_jsonl_path(skill: str, model: str) -> Path:
    return DEFAULT_DISTANCE_ROOT / skill / model / "distances.jsonl"


def load_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"Invalid JSON in {path} at line {line_number}: {exc}") from exc
    return records


def pair_size(record: dict[str, Any], normalized: bool) -> int:
    total = 0
    for side in ("baseline", "generated"):
        path = hoa_path(record, side, normalized)
        total += path.stat().st_size if path.exists() else 0
    return total


def select_success_record(records: list[dict[str, Any]], run_id: str | None, normalized: bool) -> dict[str, Any]:
    success_records: list[dict[str, Any]] = []
    for record in records:
        record_run_id = (record.get("run") or {}).get("run_id")
        if record.get("status") != "success":
            continue
        if run_id and record_run_id != run_id:
            continue
        success_records.append(record)

    if run_id and not success_records:
        raise SystemExit(f"No successful Buchi-distance record found for run_id={run_id}")
    if not success_records:
        raise SystemExit("No successful Buchi-distance record found.")
    return min(success_records, key=lambda record: pair_size(record, normalized))


def prepare_distance_for_run(
    *,
    run_id: str,
    skill: str,
    model: str,
    runs_manifest: Path,
    output_jsonl: Path,
) -> None:
    if not runs_manifest.is_file():
        raise SystemExit(f"Runs manifest does not exist: {runs_manifest}")

    matching_runs = [record for record in load_records(runs_manifest) if record.get("run_id") == run_id]
    if not matching_runs:
        raise SystemExit(f"Run ID does not exist in {runs_manifest}: {run_id}")
    if len(matching_runs) > 1:
        raise SystemExit(f"Run ID occurs more than once in {runs_manifest}: {run_id}")

    run = matching_runs[0]
    if run.get("skill") != skill:
        raise SystemExit(
            f"Run {run_id} uses skill={run.get('skill')!r}, but --skill={skill!r} was requested."
        )

    temporary_manifest: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".jsonl", delete=False) as handle:
            handle.write(json.dumps(run, sort_keys=True) + "\n")
            temporary_manifest = Path(handle.name)

        command = [
            sys.executable,
            str(DISTANCE_EVALUATOR),
            "--skill",
            skill,
            "--model",
            model,
            "--runs-manifest",
            str(temporary_manifest),
            "--output-jsonl",
            str(output_jsonl),
        ]
        print(f"No successful distance record found for run_id={run_id}; preparing it now.", file=sys.stderr)
        completed = subprocess.run(command, check=False)
        if completed.returncode != 0:
            raise SystemExit(
                f"Distance preparation failed for run_id={run_id} with exit code {completed.returncode}."
            )
    finally:
        if temporary_manifest is not None:
            temporary_manifest.unlink(missing_ok=True)


def hoa_path(record: dict[str, Any], side: str, normalized: bool) -> Path:
    if normalized:
        normalization = record.get(f"{side}_normalization") or {}
        path = resolve_repo_path(normalization.get("output"))
        if path:
            return path

    export = record.get(f"{side}_export") or {}
    path = resolve_repo_path(export.get("hoa_file"))
    if path:
        return path

    raise SystemExit(f"Record does not contain a {side} HOA path.")


def print_file(label: str, path: Path) -> None:
    if not path.exists():
        raise SystemExit(f"{label} file does not exist: {path}")

    content = path.read_text(encoding="utf-8", errors="replace")
    print(f"===== {label} HOA: {path} =====")
    print(content, end="")
    if not content.endswith("\n"):
        print()
    print(f"===== END {label} HOA =====")


def decoded_letter_alphabet(automaton) -> tuple[list[str], list[tuple[str, ...]], tuple[object, ...]]:
    atomic_propositions = tuple(str(ap) for ap in automaton.ap())
    grouped_values: dict[str, list[str]] = {}
    independent: list[str] = []

    for atomic_proposition in atomic_propositions:
        parsed = buchi_distance.parse_spectra_value_ap(atomic_proposition)
        if parsed is None:
            independent.append(atomic_proposition)
            continue
        variable, value = parsed
        grouped_values.setdefault(variable, []).append(value)

    variable_names: list[str] = []
    domains: list[list[str]] = []
    for variable, values in grouped_values.items():
        if len(values) >= 2:
            variable_names.append(variable)
            domains.append(values)
        else:
            independent.append(f"{variable}={values[0]}")

    for atomic_proposition in independent:
        variable_names.append(atomic_proposition)
        domains.append(["false", "true"])

    bdd_dict = automaton.get_dict()
    bdd_variables = tuple(bdd_dict.varnum(ap) for ap in automaton.ap())
    alphabet = buchi_distance.build_letter_alphabet(atomic_propositions, bdd_variables)
    valuations = list(itertools.product(*domains))
    if len(valuations) != len(alphabet.cubes):
        raise SystemExit("Could not align decoded valuations with the valid-letter alphabet.")
    return variable_names, valuations, alphabet.cubes


def print_decoded_automaton(label: str, automaton, source: Path | None = None) -> None:
    buddy = buchi_distance.require_buddy()
    variable_names, valuations, cubes = decoded_letter_alphabet(automaton)

    print(f"===== {label} DECODED AUTOMATON =====")
    if source is not None:
        print(f"source: {source}")
    print(f"states: {automaton.num_states()}")
    print(f"start: {automaton.get_init_state_number()}")
    print(f"acceptance: {automaton.get_acceptance()}")
    print(f"deterministic: {automaton.is_deterministic()}")
    print(f"complete: {automaton.prop_complete()}")
    print(f"valuation_order: ({', '.join(variable_names)})")
    print()

    for state in range(automaton.num_states()):
        print(f"State: {state}")
        printed_transition = False
        for edge in automaton.out(state):
            matching = [
                valuation
                for valuation, cube in zip(valuations, cubes)
                if edge.cond & cube != buddy.bddfalse
            ]
            if not matching:
                continue
            printed_transition = True
            acceptance_sets = sorted(int(value) for value in edge.acc.sets())
            acceptance = f" acceptance={{{', '.join(map(str, acceptance_sets))}}}" if acceptance_sets else ""
            formatted = " | ".join(f"({', '.join(values)})" for values in matching)
            print(f"  {formatted} -> {edge.dst}{acceptance}")
        if not printed_transition:
            print("  <no valid Spectra valuation>")
    print("invalid_one_hot_encodings: omitted")
    print(f"===== END {label} DECODED AUTOMATON =====")


def print_decoded_hoa_file(label: str, path: Path) -> None:
    if not path.exists():
        raise SystemExit(f"{label} HOA file does not exist: {path}")
    spot = buchi_distance.require_spot()
    print_decoded_automaton(label, spot.automaton(str(path)), source=path)


def latex_escape(value: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(character, character) for character in value)


def decoded_transition_rows(automaton) -> list[tuple[int, int, tuple[int, ...], list[tuple[str, ...]]]]:
    buddy = buchi_distance.require_buddy()
    _variable_names, valuations, cubes = decoded_letter_alphabet(automaton)
    rows: list[tuple[int, int, tuple[int, ...], list[tuple[str, ...]]]] = []
    for state in range(automaton.num_states()):
        for edge in automaton.out(state):
            matching = [
                valuation
                for valuation, cube in zip(valuations, cubes)
                if edge.cond & cube != buddy.bddfalse
            ]
            if matching:
                acceptance_sets = tuple(sorted(int(value) for value in edge.acc.sets()))
                rows.append((state, edge.dst, acceptance_sets, matching))
    return rows


def tikz_transition_label(valuations: list[tuple[str, ...]]) -> str:
    lines = [r"\texttt{" + latex_escape(f"({', '.join(values)})") + "}" for values in valuations]
    return r"\shortstack{" + r" \\ ".join(lines) + "}"


def write_tikz_automaton(label: str, automaton, output_dir: Path, run_id: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_run_id = "".join(character if character.isalnum() or character in "-_" else "_" for character in run_id)
    tikz_path = output_dir / f"{safe_run_id}.{label}.tex"
    variable_names, _valuations, _cubes = decoded_letter_alphabet(automaton)
    rows = decoded_transition_rows(automaton)

    outgoing: dict[int, list[tuple[int, ...]]] = {state: [] for state in range(automaton.num_states())}
    for source, _destination, acceptance_sets, _matching in rows:
        outgoing[source].append(acceptance_sets)
    accepting_states = {
        state
        for state, markings in outgoing.items()
        if markings and all(0 in marking for marking in markings)
    }

    grouped: dict[tuple[int, int], list[tuple[str, ...]]] = {}
    for source, destination, _acceptance_sets, matching in rows:
        grouped.setdefault((source, destination), []).extend(matching)

    state_count = automaton.num_states()
    radius = max(2.5, state_count * 0.8)
    lines = [
        r"% Requires \usepackage{tikz}",
        r"% Requires \usetikzlibrary{automata,positioning}",
        "% Valuation order: (" + ", ".join(latex_escape(name) for name in variable_names) + ")",
        r"\begin{tikzpicture}[>=stealth,shorten >=1pt,auto,semithick]",
    ]
    initial_state = automaton.get_init_state_number()
    for state in range(state_count):
        angle = 90.0 - (360.0 * state / max(1, state_count))
        x = radius * math.cos(math.radians(angle))
        y = radius * math.sin(math.radians(angle))
        styles = ["state"]
        if state == initial_state:
            styles.append("initial")
        if state in accepting_states:
            styles.append("accepting")
        lines.append(f"  \\node[{', '.join(styles)}] (q{state}) at ({x:.2f},{y:.2f}) {{$q_{state}$}};")

    lines.append("")
    lines.append(r"  \path[->]")
    pairs = set(grouped)
    edge_lines: list[str] = []
    for (source, destination), matching in sorted(grouped.items()):
        if source == destination:
            style = "loop above"
        elif (destination, source) in pairs:
            style = "bend left=15"
        else:
            style = ""
        option = f"[{style}]" if style else ""
        edge_lines.append(
            f"    (q{source}) edge{option} node {{{tikz_transition_label(matching)}}} (q{destination})"
        )
    if edge_lines:
        lines.append("\n".join(edge_lines) + ";")
    else:
        lines[-1] += ";"
    lines.append(r"\end{tikzpicture}")
    lines.append("")
    tikz_path.write_text("\n".join(lines), encoding="utf-8")
    return tikz_path


def print_spectra_file(label: str, path: Path) -> None:
    if not path.exists():
        raise SystemExit(f"{label} Spectra file does not exist: {path}")

    content = path.read_text(encoding="utf-8", errors="replace")
    print(f"===== {label} SPECTRA: {path} =====")
    print(content, end="")
    if not content.endswith("\n"):
        print()
    print(f"===== END {label} SPECTRA =====")


def determinize_automaton(automaton):
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
            status = "not_needed" if automaton.is_deterministic() and str(automaton.prop_complete()) == "yes" else "determinized"
            return processed, {
                "status": status,
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
    raise SystemExit("Could not determinize automaton with Spot. Attempts: " + " | ".join(errors))


def print_deterministic_hoa(label: str, path: Path) -> None:
    if not path.exists():
        raise SystemExit(f"{label} HOA file does not exist: {path}")

    spot = buchi_distance.require_spot()
    automaton = spot.automaton(str(path))
    deterministic, info = determinize_automaton(automaton)
    print(f"===== {label} DETERMINISTIC HOA: {path} =====")
    print("input_variant: normalized")
    print(
        "determinization: "
        f"status={info.get('status')} "
        f"states_before={info.get('states_before')} "
        f"states_after={info.get('states_after')} "
        f"acceptance_before={info.get('acceptance_before')} "
        f"acceptance_after={info.get('acceptance_after')}"
    )
    print(f"method: {info.get('method')}")
    print()
    print_decoded_automaton(f"{label} DETERMINISTIC", deterministic, source=path)
    print(f"===== END {label} DETERMINISTIC HOA =====")
    return deterministic


def load_deterministic_automaton(path: Path):
    if not path.exists():
        raise SystemExit(f"HOA file does not exist: {path}")

    spot = buchi_distance.require_spot()
    automaton = spot.automaton(str(path))
    deterministic, info = determinize_automaton(automaton)
    return deterministic, info


def print_symmetric_difference_hoa(baseline_path: Path, generated_path: Path) -> None:
    spot = buchi_distance.require_spot()
    baseline, baseline_info = load_deterministic_automaton(baseline_path)
    generated, generated_info = load_deterministic_automaton(generated_path)

    if [str(ap) for ap in baseline.ap()] != [str(ap) for ap in generated.ap()]:
        raise SystemExit("Cannot build product automaton: baseline/generated AP alphabets differ.")

    product = spot.product_xor(baseline, generated)
    product = spot.postprocess(product, "generic", "deterministic")

    print("===== SYMMETRIC DIFFERENCE PRODUCT HOA =====")
    print(f"baseline_input: {baseline_path}")
    print(f"generated_input: {generated_path}")
    print("input_variant: normalized")
    print(
        "baseline_determinization: "
        f"status={baseline_info.get('status')} "
        f"states_before={baseline_info.get('states_before')} "
        f"states_after={baseline_info.get('states_after')}"
    )
    print(
        "generated_determinization: "
        f"status={generated_info.get('status')} "
        f"states_before={generated_info.get('states_before')} "
        f"states_after={generated_info.get('states_after')}"
    )
    print(
        "product: "
        f"states={product.num_states()} "
        f"deterministic={product.is_deterministic()} "
        f"complete={product.prop_complete()} "
        f"acceptance={product.get_acceptance()}"
    )
    print("method: spot.product_xor(...), then spot.postprocess(generic, deterministic)")
    print()
    print_decoded_automaton("SYMMETRIC DIFFERENCE PRODUCT", product)
    print("===== END SYMMETRIC DIFFERENCE PRODUCT HOA =====")
    return product


def print_product_distance(product, debug: bool = False) -> None:
    markov_chain = buchi_distance.automaton_to_markov_chain(product, debug=debug)
    bsccs = buchi_distance.find_bsccs(markov_chain, debug=debug)
    accepting_bsccs = buchi_distance.find_accepting_bsccs(markov_chain, bsccs, debug=debug)
    distance = buchi_distance.reachability_probability_exact(markov_chain, accepting_bsccs, bsccs, debug=debug)
    partial_rows = [
        (state, row_sum)
        for state, row_sum in enumerate(markov_chain.row_probability_sums)
        if row_sum < 1.0
    ]

    print("===== PRODUCT DISTANCE =====")
    print(f"distance: {distance}")
    print(f"states: {markov_chain.num_states}")
    print(f"acceptance: {markov_chain.acceptance_formula}")
    print(f"bscc_count: {len(bsccs)}")
    print(f"accepting_bscc_count: {len(accepting_bsccs)}")
    print(f"partial_row_count: {len(partial_rows)}")
    if partial_rows:
        min_row_sum = min(row_sum for _state, row_sum in partial_rows)
        max_row_sum = max(row_sum for _state, row_sum in partial_rows)
        print(f"partial_row_sum_min: {min_row_sum}")
        print(f"partial_row_sum_max: {max_row_sum}")
        print(f"partial_rows: {partial_rows}")
    print(f"bsccs: {[sorted(bscc) for bscc in bsccs]}")
    print(f"accepting_bsccs: {[sorted(bscc) for bscc in accepting_bsccs]}")
    print("===== END PRODUCT DISTANCE =====")


def print_bounded_semantic_distance(
    baseline,
    generated,
    *,
    depth: int,
    mode: str,
    samples: int,
    seed: int | None,
    max_prefixes: int | None,
) -> None:
    result = bounded_semantic_distance.compute_bounded_semantic_distance(
        baseline,
        generated,
        depth=depth,
        mode=mode,
        samples=samples,
        seed=seed,
        max_prefixes=max_prefixes,
    )

    print("===== BOUNDED SEMANTIC DISTANCE =====")
    print(f"mode: {result['mode']}")
    print(f"depth: {result['depth']}")
    print(f"samples: {result['samples']}")
    print(f"seed: {result['seed']}")
    print(f"alphabet_size: {result['alphabet_size']}")
    print(f"total_prefixes: {result['total_prefixes']}")
    print(f"both_viable: {result['both_viable']}")
    print(f"baseline_only: {result['baseline_only']}")
    print(f"generated_only: {result['generated_only']}")
    print(f"neither_viable: {result['neither_viable']}")
    print(f"mismatch_rate: {result['mismatch_rate']}")
    print(f"false_negative_rate: {result['false_negative_rate']}")
    print(f"false_positive_rate: {result['false_positive_rate']}")
    print(f"jaccard_distance: {result['jaccard_distance']}")
    print("===== END BOUNDED SEMANTIC DISTANCE =====")


def write_automaton_graph(label: str, automaton, output_dir: Path, run_id: str) -> dict[str, str | None]:
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_run_id = "".join(character if character.isalnum() or character in "-_" else "_" for character in run_id)
    dot_path = output_dir / f"{safe_run_id}.{label}.dot"
    svg_path = output_dir / f"{safe_run_id}.{label}.svg"
    tikz_path = write_tikz_automaton(label, automaton, output_dir, run_id)

    dot_path.write_text(automaton.to_str("dot"), encoding="utf-8")

    dot_executable = shutil.which("dot")
    if not dot_executable:
        return {
            "dot": str(dot_path),
            "svg": None,
            "tikz": str(tikz_path),
            "warning": "Graphviz 'dot' executable not found.",
        }

    completed = subprocess.run(
        [dot_executable, "-Tsvg", str(dot_path), "-o", str(svg_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        warning = (completed.stderr or completed.stdout or "Graphviz failed.").strip()
        return {"dot": str(dot_path), "svg": None, "tikz": str(tikz_path), "warning": warning}

    return {"dot": str(dot_path), "svg": str(svg_path), "tikz": str(tikz_path), "warning": None}


def print_graph_outputs(outputs: dict[str, dict[str, str | None]]) -> None:
    print("===== GRAPHVIZ OUTPUTS =====")
    for label, paths in outputs.items():
        print(f"{label}:")
        print(f"  dot: {paths.get('dot')}")
        if paths.get("svg"):
            print(f"  svg: {paths.get('svg')}")
        if paths.get("tikz"):
            print(f"  tikz: {paths.get('tikz')}")
        if paths.get("warning"):
            print(f"  warning: {paths.get('warning')}")
    print("===== END GRAPHVIZ OUTPUTS =====")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Print the baseline and generated Spectra and HOA files for one successful "
            "Buchi-distance comparison. Raw exported HOA files are printed by default."
        )
    )
    parser.add_argument("--skill", default="respect")
    parser.add_argument("--model", default="llama-3")
    parser.add_argument("--jsonl", default=None, help="Explicit distances.jsonl path.")
    parser.add_argument(
        "--run-id",
        default=None,
        help=(
            "Print this run. If its successful distance record is missing, automatically "
            "prepare the HOA and distance artifacts first."
        ),
    )
    parser.add_argument(
        "--runs-manifest",
        default=str(DEFAULT_RUNS_MANIFEST),
        help="Runs manifest used to prepare a missing --run-id.",
    )
    parser.add_argument(
        "--normalized",
        action="store_true",
        help="Print normalized HOA files used for distance instead of raw exported HOA files.",
    )
    parser.add_argument(
        "--graph-output-dir",
        default=str(DEFAULT_GRAPH_OUTPUT_DIR),
        help="Directory for Graphviz .dot/.svg files and decoded TikZ .tex files.",
    )
    parser.add_argument(
        "--debug-product-distance",
        action="store_true",
        help="Print detailed Markov-chain diagnostics while computing the product distance.",
    )
    parser.add_argument("--bounded-depth", type=int, default=10)
    parser.add_argument("--bounded-mode", choices=("random", "exhaustive"), default="random")
    parser.add_argument("--bounded-samples", type=int, default=1000)
    parser.add_argument("--bounded-seed", type=int, default=1)
    parser.add_argument("--bounded-max-prefixes", type=int, default=None)
    args = parser.parse_args()

    jsonl_path = resolve_repo_path(args.jsonl) if args.jsonl else default_jsonl_path(args.skill, args.model)
    if not jsonl_path:
        raise SystemExit(f"Distance JSONL does not exist: {jsonl_path}")

    normalized = args.normalized
    records = load_records(jsonl_path) if jsonl_path.exists() else []
    matching_success = any(
        record.get("status") == "success" and (record.get("run") or {}).get("run_id") == args.run_id
        for record in records
    )
    if args.run_id and not matching_success:
        runs_manifest = resolve_repo_path(args.runs_manifest)
        if not runs_manifest:
            raise SystemExit(f"Runs manifest does not exist: {args.runs_manifest}")
        prepare_distance_for_run(
            run_id=args.run_id,
            skill=args.skill,
            model=args.model,
            runs_manifest=runs_manifest,
            output_jsonl=jsonl_path,
        )
        records = load_records(jsonl_path) if jsonl_path.exists() else []
    elif not jsonl_path.exists():
        raise SystemExit(f"Distance JSONL does not exist: {jsonl_path}")

    record = select_success_record(records, args.run_id, normalized)
    run = record.get("run") or {}

    print(f"Source JSONL: {jsonl_path}")
    print(f"run_id: {run.get('run_id', 'missing')}")
    print(f"dataset_id: {run.get('dataset_id', 'missing')}")
    print(f"distance: {record.get('distance')}")
    print(f"hoa_variant: {'normalized' if normalized else 'raw'}")
    print()

    baseline_spectra = resolve_repo_path(run.get("source_spectra_file"))
    generated_spectra = resolve_repo_path(run.get("reconstructed_spectra_file"))
    if not baseline_spectra:
        raise SystemExit("Record does not contain a baseline Spectra path.")
    if not generated_spectra:
        raise SystemExit("Record does not contain a generated Spectra path.")

    print_spectra_file("BASELINE", baseline_spectra)
    print()
    print_spectra_file("GENERATED", generated_spectra)
    print()

    baseline_deterministic_input = hoa_path(record, "baseline", True)
    generated_deterministic_input = hoa_path(record, "generated", True)

    if not normalized:
        print_file("BASELINE RAW", hoa_path(record, "baseline", False))
        print()
        print_file("GENERATED RAW", hoa_path(record, "generated", False))
        print()

    print_decoded_hoa_file("BASELINE NORMALIZED", baseline_deterministic_input)
    print()
    print_decoded_hoa_file("GENERATED NORMALIZED", generated_deterministic_input)
    print()

    baseline_deterministic = print_deterministic_hoa("BASELINE", baseline_deterministic_input)
    print()
    generated_deterministic = print_deterministic_hoa("GENERATED", generated_deterministic_input)
    print()
    symmetric_difference = print_symmetric_difference_hoa(baseline_deterministic_input, generated_deterministic_input)
    print()
    print_product_distance(symmetric_difference, debug=args.debug_product_distance)
    print()
    print_bounded_semantic_distance(
        baseline_deterministic,
        generated_deterministic,
        depth=args.bounded_depth,
        mode=args.bounded_mode,
        samples=args.bounded_samples,
        seed=args.bounded_seed,
        max_prefixes=args.bounded_max_prefixes,
    )
    print()

    graph_output_dir = resolve_repo_path(args.graph_output_dir) or DEFAULT_GRAPH_OUTPUT_DIR
    run_id = run.get("run_id") or record.get("comparison_id") or "missing_run_id"
    graph_outputs = {
        "baseline": write_automaton_graph("baseline", baseline_deterministic, graph_output_dir, run_id),
        "generated": write_automaton_graph("generated", generated_deterministic, graph_output_dir, run_id),
        "symmetric_difference": write_automaton_graph(
            "symmetric_difference",
            symmetric_difference,
            graph_output_dir,
            run_id,
        ),
    }
    print_graph_outputs(graph_outputs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
