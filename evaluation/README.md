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
- Buchi/specification-distance aggregates from `evaluation/buchi/distance_results/.../distances.jsonl`, when present
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

## Buchi / HOA Evaluation

Buchi-distance, HOA export/normalization, non-zero distance fixtures, and
directed disagreement-language helpers now live in `evaluation/buchi/`.

See [`buchi/README.md`](buchi/README.md) for commands such as:

```powershell
python evaluation\buchi\evaluate_reconstruction_distances.py --skill respect-method-2 --model llama-3 --limit 10
python evaluation\buchi\disagreement_languages.py --left path\to\a.spectra --right path\to\b.spectra
```

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
