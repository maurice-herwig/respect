# Evaluation

This directory contains scripts for summarizing and evaluating reconstruction
experiment results.

Unless a section says otherwise, run commands from the repository root.

## Reconstruction Run Summary

After reconstruction experiments have produced `experiments/runs/runs.jsonl`,
summarize the CLI outcomes and repair-loop counts for a selected skill/model:

```powershell
python evaluation\summarize_reconstruction_runs.py --skill respect-method-2 --model llama-3
```

From this `evaluation` directory, for example when an IDE uses `evaluation` as
the working directory:

```powershell
python summarize_reconstruction_runs.py --skill respect-method-2 --model llama-3
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
python evaluation\evaluate_reconstruction_distances.py `
  --skill respect-method-2 `
  --model llama-3 `
  --force
```

For each run, the script exports both Spectra files with
`assets/cli_with_hoa_export/spectra-cli.jar`, normalizes the state-labeled HOA
export into transition-labeled HOA, optionally determinizes the Spot automata,
and then calls `compute_buchi_distance`.

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

For a quick smoke test:

```powershell
python evaluation/evaluate_reconstruction_distances.py --skill respect-method-2 --model llama-3 --limit 1
```

The distance step requires the LRDE/EPITA Spot Python bindings. On Windows, run
it in the WSL/conda Spot environment described in the repository root README.
