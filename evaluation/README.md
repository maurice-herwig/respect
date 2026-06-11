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

## Spectra to HOA Export

`export_spectra_to_hoa.py` exports one `.spectra` file to HOA with the modified
Spectra CLI stored in `assets/cli_with_hoa_export/spectra-cli.jar`.

```powershell
python export_spectra_to_hoa.py --input dataset\accepted\files\jringert\gendev.bot\gendev.bot.runner\botV0.spectra
```

By default, output is written to `evaluation/hoa_exports/` and `--jtlv` is used
to avoid native CUDD setup. To choose the output path explicitly:

```powershell
python evaluation\export_spectra_to_hoa.py `
  --input path\to\model.spectra `
  --output path\to\model.hoa `
  --max-states 100000 `
  --force
```

## Reconstruction Distance For One Run

`compare_reconstruction_distance.py` takes one synthesized reconstruction run,
exports both the accepted-dataset baseline and the reconstructed Spectra file to
HOA, loads both HOA files with Spot, and calls `compute_buchi_distance`.

```powershell
python evaluation\compare_reconstruction_distance.py --run-id <run_id> --force
```

If `--run-id` is omitted, the first synthesized run for `respect-method-2` is
used:

```powershell
python evaluation\compare_reconstruction_distance.py --force
```

You can also compare two explicit files:

```powershell
python evaluation\compare_reconstruction_distance.py `
  --baseline-spectra dataset\accepted\files\...\model.spectra `
  --generated-spectra experiments\runs\...\respect-method-2.spectra `
  --force
```

The distance step requires the LRDE/EPITA Spot Python bindings. On Windows, run
it in the WSL/conda Spot environment described in the repository root README.

By default, the comparison script normalizes the Spectra CLI HOA export before
loading it with Spot. The modified CLI emits state-labeled HOA, while the
distance code expects transition-labeled deterministic automata. Normalization
moves each target state's valuation label onto the incoming transition and adds
a rejecting sink for missing valuations:

```powershell
python evaluation\normalize_hoa_state_labels.py `
  --input evaluation\hoa_exports\comparisons\<run_id>\baseline.hoa `
  --output evaluation\hoa_exports\comparisons\<run_id>\baseline.normalized.hoa `
  --force
```

To inspect the raw exported HOA without this transformation:

```powershell
python evaluation\compare_reconstruction_distance.py --run-id <run_id> --no-normalize-hoa
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
