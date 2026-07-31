# Evaluation

This directory contains the current branched-experiment evaluation workflow.
Run commands from the repository root.

## Per-Run Evaluation

`evaluate_branched_runs.py` reads complete records from
`experiments/branched_runs/runs.jsonl` and writes one evaluation JSON per run.
It skips dry-runs, missing-input runs, partial runs, and branches that did not
reach a complete terminal status. For branches, `success` and `tests_passed`
count as complete.

By default the script requires Spot, because Buechi/Markov-chain distance is
part of the per-artifact evaluation. It also defaults to the current
`ACADEMIC_CLOUD_MODEL` from `.env`; pass `--all-description-models` to disable
that filter.

The main omega-distance uses a substochastic BSCC Markov chain by default:
internal HOA APs are projected away, no rejecting sink is added, and missing
transition mass is not renormalized. This avoids the saturation effect where an
explicit reachable sink is almost surely reached on infinite random traces.

The evaluator also computes a bounded semantic prefix distance by default. It
samples finite prefixes up to `--bounded-depth` and records mismatch,
false-positive, false-negative, and Jaccard-style rates under
`bounded_semantic_distance`.

```powershell
python evaluation\evaluate_branched_runs.py --limit 1
```

To change the bounded prefix depth or sample count:

```powershell
python evaluation\evaluate_branched_runs.py --limit 1 --bounded-depth 12 --bounded-samples 5000
```

With a log file:

```powershell
python evaluation\evaluate_branched_runs.py --limit 1 --log-file evaluation\branched_runs\eval.log
```

Outputs are written under:

```text
evaluation/branched_runs/<run_id>/evaluation.json
```

Use `--force` to recompute existing evaluation JSON files. For validation-only
debugging without Spot, pass `--allow-missing-spot`; distance entries will then
be recorded as `distance_unavailable`.

For quick distance debugging, select a specific artifact stage before limiting:

```powershell
python evaluation\evaluate_branched_runs.py --limit 1 --artifact-stage final --artifact-limit 1 --force
```

## Aggregate Summary

`summarize_branched_runs.py` collects all per-run evaluation JSON files and
writes basic aggregate tables for the branched experiment.

```powershell
python evaluation\summarize_branched_runs.py
```

For only tables, without optional plots:

```powershell
python evaluation\summarize_branched_runs.py --no-plots
```

Outputs are written under:

```text
evaluation/branched_summary/
```

The basic outputs are:

- `summary.json`: machine-readable aggregate summary
- `artifacts.csv`: one row per evaluated Spectra artifact
- `branch_statuses.csv`: one row per branch/run status
- `by_branch.csv`: aggregate validation, repair-loop, and distance metrics by branch
- `by_lineage.csv`: the same metrics by branch and lineage
- `by_stage.csv`: the same metrics by branch, lineage, and intermediate stage
- `final_by_branch.csv`: final-artifact metrics by branch

If `matplotlib` is installed, the script also writes simple PNG plots under
`evaluation/branched_summary/plots/`.

## Kept Internals

`evaluation/buchi/` is still required by the branched evaluator and by the
cross-repair broker. It contains the Spot/HOA normalization and
Buechi/Markov-chain distance helpers.

`signature_mapping.py` and `signature_mappings.jsonl` are kept because the
distance pipeline can use them when generated and baseline Spectra files expose
compatible variables under different names.
