# Evaluation

This directory contains scripts for summarizing and evaluating reconstruction
experiment results.

Unless a section says otherwise, run commands from the repository root.

## Global Evaluation Summary

`summarize_all_results.py` combines the available outputs from the other
evaluation scripts for one model/skill pair. It does not rerun expensive HOA or
controller evaluations; it reads the existing JSONL files and reports one global
summary.

```powershell
python summarize_all_results.py --skill respect-method-3 --model llama-3
```

For machine-readable output:

```powershell
python evaluation\summarize_all_results.py --skill respect-method-2 --model llama-3 --json
```

The summary includes:

- reconstruction run outcomes from `experiments/runs/runs.jsonl`
- Buchi/specification-distance aggregates from `evaluation/distance_results/.../distances.jsonl`, when present
- controller-output-distance aggregates from `evaluation/controller_distance_results/.../controller_distances.jsonl`, when present

## Reconstruction Run Summary

After reconstruction experiments have produced `experiments/runs/runs.jsonl`,
summarize the CLI outcomes and repair-loop counts for a selected skill/model:

```powershell
python evaluation\summarize_reconstruction_runs.py --skill respect-method-2 --model llama-3
```

From this `evaluation` directory, for example when an IDE uses `evaluation` as
the working directory:

```powershell
python summarize_reconstruction_runs.py --skill respect-method-3 --model llama-3
```

The script reports:

```text
reported_cli_status counts and percentages
reported_repair_loops counts and percentages
percentage of runs with reported_cli_status=synthesized and reported_repair_loops=0
```

For machine-readable output:

```powershell
python evaluation\summarize_reconstruction_runs.py --skill respect-method-2 --model llama-3 --json
```

Use `--include-dry-run` to include dry-run records:

```powershell
python evaluation\summarize_reconstruction_runs.py --skill respect-method-2 --model llama-3 --include-dry-run
```

## Reconstruction Distances For A Model And Skill

`evaluate_reconstruction_distances.py` evaluates all synthesized runs for one
model/skill combination. For each matching run, it compares the reconstructed
Spectra file against the corresponding `dataset/accepted` baseline, writes one
JSONL result row, and prints an aggregate overview.

```powershell
  python evaluation/evaluate_reconstruction_distances.py --skill respect-method-2 --model llama-3 --force      
```

For each run, the script exports both Spectra files with
`assets/cli_with_hoa_export/spectra-cli.jar`, normalizes the state-labeled HOA
export into transition-labeled HOA, optionally determinizes the Spot automata,
and then calls `compute_buchi_distance`.

The distance is computed over valid Spectra letters. The CLI encodes a
finite-domain variable as one AP per value, such as `"signal=false"` and
`"signal=true"`. `compute_buchi_distance` treats those as one-hot alternatives
of the same variable instead of independent Boolean APs; otherwise valid
Spectra words would have probability 0 under the random-word model.

When normalization adds a sink for missing valuations, it also extends the HOA
acceptance condition with `Fin(k)` and marks the sink self-loop with `{k}`. This
keeps the completion sink rejecting even for raw exports with `Acceptance: 0 t`.

By default, nondeterministic normalized HOA automata are passed through Spot
postprocessing before distance computation:

```text
spot.postprocess(..., "generic", "deterministic", "complete")
```

Disable this strict fallback only for debugging:

```powershell
python evaluation\evaluate_reconstruction_distances.py `
  --skill respect-method-2 `
  --model llama-3 `
  --no-determinize
```

Outputs are written under:

```text
evaluation/distance_results/<skill>/<model>/
```

Use `--resume` to skip run ids already present in the JSONL result file:

```powershell
python evaluation\evaluate_reconstruction_distances.py `
  --skill respect-method-2 `
  --model llama-3 `
  --resume
```

By default the script also reuses existing JSONL distance records for the same
baseline/generated Spectra file hashes and evaluation settings. This avoids
recomputing distances when the same file pair appears again. Use
`--no-reuse-existing` to rebuild the JSONL from scratch, or `--force` to
recreate intermediate HOA artifacts and distances.

If the HOA AP alphabets differ only because generated variables use different
names, enable LLM-assisted one-to-one signature mapping:

```powershell
python evaluation\evaluate_reconstruction_distances.py `
  --skill respect-method-2 `
  --model llama-3 `
  --signature-mapping llm
```

Mappings are requested from the Academic Cloud API, validated locally, and cached
in `evaluation/signature_mappings.jsonl`. The generated HOA AP names are then
renamed to the baseline variable names before Spot imports the automata.

For a quick smoke test:

```powershell
python evaluation\evaluate_reconstruction_distances.py --skill respect-method-2 --model llama-3 --limit 1
```

To test the distance computation without the modified Spectra CLI, translate two
Spot formulas over the same alphabet directly:

```powershell
python evaluation/test_nonzero_distance_fixture.py
```

The default formulas are `F signal` and `G signal`, so the expected distance is
non-zero. To run the older end-to-end Spectra export fixture explicitly:

```powershell
python evaluation/test_nonzero_distance_fixture.py --mode spectra-cli --force
```

The distance step requires the LRDE/EPITA Spot Python bindings. On Windows, run
it in the WSL/conda Spot environment described in the repository root README.

## Directed Disagreement Languages

`disagreement_languages.py` computes the two directed omega-language difference
sets needed by the cross-broker experiment:

```text
L(left) \ L(right)
L(right) \ L(left)
```

It reuses the existing Spectra-to-HOA export, HOA normalization, alphabet checks,
and determinization helpers from the Buchi-distance pipeline. For a direct pair
of Spectra files:

```powershell
python evaluation\disagreement_languages.py `
  --left path\to\agent_a.spectra `
  --right path\to\agent_b.spectra `
  --output-dir evaluation\disagreement_languages\example `
  --out evaluation\disagreement_languages\example\comparison.json
```

The helper writes `left_minus_right.hoa` and `right_minus_left.hoa` when the
comparison succeeds. Human-readable witness rendering is intentionally separate
and can be layered on top of these difference automata.

## Controller Output Distances For A Model And Skill

`evaluate_controller_distances.py` evaluates synthesized runs by comparing the
controllers synthesized from the accepted baseline Spectra file and the
reconstructed Spectra file. Both controllers are executed with the same bounded
input traces, and their system outputs are compared step by step.

Metric overview: [`controller_distance_metrics.svg`](evaluation.svg)

```powershell
python evaluate_controller_distances.py --skill respect-method-3 --model llama-3 --mode exhaustive --max-depth 6 --max-paths 10000
```

For larger input domains, use random sampling:

```powershell
  python evaluation/evaluate_controller_distances.py --skill respect-method-2 --model llama-3 --mode random --max-depth 10 --runs 1000 --seed 1           
```

The script automatically synthesizes both controllers into:

```text
evaluation/controller_distance_results/<skill>/<model>/comparisons/<run_id>/
```

It then runs `respect.controller_tests.ControllerTraceRunner` in isolated Java
processes and writes one JSONL result row to:

```text
evaluation/controller_distance_results/<skill>/<model>/controller_distances.jsonl
```

By default the script reuses existing JSONL controller-distance records for the
same baseline/generated Spectra file hashes and controller-distance settings
such as mode, depth, seed, and trace batch size. Use `--no-reuse-existing` to
rebuild the JSONL, or `--force` to resynthesize controllers and recompute.

For variable-name mismatches such as `leftM` versus `leftMotor`, use the same
LLM-assisted signature mapping:

```powershell
python evaluation\evaluate_controller_distances.py `
  --skill respect-method-2 `
  --model llama-3 `
  --signature-mapping llm
```

The evaluation keeps baseline input/output names as the reference. Input traces
are translated to generated input names before running the generated controller,
and generated outputs are compared back against the mapped baseline outputs.

Reported distance metrics:

- `trace_mismatch_rate`: fraction of bounded input traces where at least one
  output mismatch occurs.
- `step_mismatch_rate`: fraction of executed time steps with any output
  mismatch.
- `output_hamming_mismatch_rate`: fraction of individual output-variable
  comparisons that differ.

This is an operational controller-distance measure, not a specification-language
equivalence proof. Two controllers can differ while still satisfying the same
underspecified Spectra contract. The metric is most useful for measuring how
similar the synthesized strategies behave under the same bounded input
distribution.

Because the metric compares concrete synthesized controller artifacts, even two
controllers synthesized from the same underspecified Spectra file can produce
different outputs if synthesis chooses different valid strategies. Use identical
controller artifacts, not two fresh syntheses, when you need a zero-distance
smoke test for the runner itself.

For robustness on Windows/CUDD, the Python driver runs controller traces in
short isolated Java processes by default. `--trace-batch-size 1` is the default;
increase it only after checking that the local Syntech/CUDD setup stays stable.

Automatic signature extraction currently supports scalar `boolean`, inline enum,
enum type aliases, and `Int(a..b)` declarations. Runs with renamed variables,
different domains, arrays, or unsupported declaration forms are reported as
`signature_mismatch` or `unsupported_signature` instead of receiving a distance.
