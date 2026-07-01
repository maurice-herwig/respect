# Buchi / HOA Evaluation

This directory contains the Buchi-automata and HOA-based evaluation utilities.
Unless a section says otherwise, run commands from the repository root.

## Reconstruction Distances For A Model And Skill

`evaluate_reconstruction_distances.py` evaluates all synthesized runs for one
model/skill combination. For each matching run, it compares the reconstructed
Spectra file against the corresponding `dataset/accepted` baseline, writes one
JSONL result row, and prints an aggregate overview.

```powershell
python evaluation\buchi\evaluate_reconstruction_distances.py --skill respect-method-2 --model llama-3 --force
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
python evaluation\buchi\evaluate_reconstruction_distances.py `
  --skill respect-method-2 `
  --model llama-3 `
  --no-determinize
```

Outputs are written under:

```text
evaluation/buchi/distance_results/<skill>/<model>/
```

By default the evaluator resumes previous runs: run ids already present in the
JSONL result file are skipped, missing run ids are computed, and the final
summary includes both existing and newly computed records. This lets a full
dataset run be restarted after interruption with the same command.

To make the resume behavior explicit:

```powershell
python evaluation\buchi\evaluate_reconstruction_distances.py `
  --skill respect-method-2 `
  --model llama-3 `
  --resume
```

By default the script also reuses existing JSONL distance records for the same
baseline/generated Spectra file hashes and evaluation settings. This avoids
recomputing distances when the same file pair appears again. Use
`--no-reuse-existing` to rebuild the JSONL, or `--force` to recreate
intermediate HOA artifacts and distances.

To recompute already recorded run ids, use `--force` or `--no-resume`.

By default, the distance evaluator uses LLM-assisted one-to-one signature
mapping when the pre-mapping HOA AP alphabets differ:

```powershell
python evaluation\buchi\evaluate_reconstruction_distances.py `
  --skill respect-method-2 `
  --model llama-3
```

Mappings are requested from the Academic Cloud API, validated locally, and
cached in `evaluation/signature_mappings.jsonl`. The generated HOA AP names are
then renamed to the baseline variable names before Spot imports the automata.
Each result row records whether a pre-mapping alphabet mismatch occurred,
whether LLM mapping was attempted, whether the returned mapping was usable, and
whether it was applied.

To require identical HOA AP names without any LLM-assisted renaming:

```powershell
python evaluation\buchi\evaluate_reconstruction_distances.py `
  --skill respect-method-2 `
  --model llama-3 `
  --signature-mapping strict
```

For a quick smoke test:

```powershell
python evaluation\buchi\evaluate_reconstruction_distances.py --skill respect-method-2 --model llama-3 --limit 1
```

To test the distance computation without the modified Spectra CLI, translate two
Spot formulas over the same alphabet directly:

```powershell
python evaluation\buchi\test_nonzero_distance_fixture.py
```

The default formulas are `F signal` and `G signal`, so the expected distance is
non-zero. To run the older end-to-end Spectra export fixture explicitly:

```powershell
python evaluation\buchi\test_nonzero_distance_fixture.py --mode spectra-cli --force
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
python evaluation\buchi\disagreement_languages.py `
  --left path\to\agent_a.spectra `
  --right path\to\agent_b.spectra `
  --output-dir evaluation\buchi\disagreement_languages\example `
  --out evaluation\buchi\disagreement_languages\example\comparison.json
```

The helper writes `left_minus_right.hoa` and `right_minus_left.hoa` when the
comparison succeeds. Human-readable witness rendering is intentionally separate
and can be layered on top of these difference automata.

## Utility Scripts

`print_success_hoa_pair.py` prints and optionally renders HOA artifacts for a
successful distance comparison:

```powershell
python evaluation\buchi\print_success_hoa_pair.py --run-id <run-id>
```

The local tests in this folder cover the Buchi-distance semantics and the
non-zero distance smoke fixture:

```powershell
python -m unittest evaluation.buchi.test_buchi_distance_semantics
python -m unittest evaluation.buchi.test_disagreement_languages
python evaluation\buchi\test_nonzero_distance_fixture.py
```

In WSL/Linux, run the Spot-dependent disagreement-language test from the
repository root with the active Spot environment:

```bash
python -m unittest evaluation.buchi.test_disagreement_languages
```
