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
