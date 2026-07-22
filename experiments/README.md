# Experiments

This directory contains scripts for the agent-based reconstruction experiments.

Unless a section says otherwise, run commands from the repository root.

## Skill-Based Reconstruction

`reconstruct_with_skill.py` reads natural-language descriptions from
`dataset/nl_descriptions/descriptions.jsonl` and starts a fresh agent process
for each description. The selected skill is injected into the agent prompt.

From the repository root, run:

```powershell
python experiments\reconstruct_with_skill.py --skill respect --dry-run --limit 3
```

From this `experiments` directory, run:

```powershell
python reconstruct_with_skill.py --skill respect --dry-run --limit 3
```

Run a limited real experiment from the repository root:

```powershell
python reconstruct_with_skill.py --skill respect --limit 195
```

Run all pending descriptions with the default agent command:

```powershell
python experiments\reconstruct_with_skill.py --skill respect
```

The default command is:

```text
codex --ask-for-approval never exec --ephemeral --sandbox danger-full-access -
```

`--ask-for-approval never` avoids interactive approval prompts in batch runs,
`--ephemeral` prevents Codex from persisting session files for the invocation,
`--sandbox danger-full-access` avoids the nested Windows sandbox failure that can
otherwise prevent the skill from running local validation commands, and `-`
reads the prompt from stdin. The script starts a separate process for each
description.

If your Codex CLI uses a different invocation, pass it explicitly:

```powershell
python experiments\reconstruct_with_skill.py `
  --skill respect `
  --agent-command "codex --ask-for-approval never exec --ephemeral --sandbox danger-full-access -"
```

Generated experiment artifacts are written to `experiments/runs/`, which is
ignored by Git. Each run uses a path that mirrors the natural-language
description path. For example:

```text
dataset/nl_descriptions/responses/A/B/C.txt
```

becomes:

```text
experiments/runs/A/B/C/respect/
```

Each run directory stores:

- `input_description.txt`
- `agent_prompt.txt`
- `agent_stdout.txt`
- `agent_stderr.txt`
- `parsed_result.json`, if the agent prints a final JSON object
- `respect.spectra`, if the agent reports a Spectra file
- `skill_artifacts/specs/*.spectra`, stable intermediate Spectra files copied
  from the skill artifact directory, when reported
- `skill_artifacts/final.spectra`, the final Spectra version copied from the
  skill artifact directory, when reported
- `skill_artifacts/repair_log.jsonl`, the repair phase log, when reported
- a row in `runs.jsonl`

The `runs.jsonl` row records these persistent artifacts in
`intermediate_spectra_files`, keyed by stage names such as `00_initial`,
`01_after_syntax_repair`, `02_after_unrealizable_repair`,
`03_after_well_separation_repair`, `04_after_test_repair`, and `final`.
It also records reported well-separation fields such as
`reported_well_separation_repair_loops`, `reported_well_separation_status`,
and `reported_well_separation_file` when the selected skill reports them.

## Cross-Broker Reconstruction

`reconstruct_with_cross_repair.py` reads natural-language descriptions from
`dataset/nl_descriptions/descriptions.jsonl` like `reconstruct_with_skill.py`,
but starts a paired cross-broker run for each description. Each run invokes
`cross_repair_with_broker.py`, which starts two agents in parallel so they can
synchronize through `cross_broker.py`.

Dry-run the first three descriptions from the repository root:

```powershell
python experiments\reconstruct_with_cross_repair.py --limit 3 --dry-run
```

Run a limited real cross-broker experiment:

```powershell
python experiments\reconstruct_with_cross_repair.py --limit 10
```

Use an explicit skill or agent command:

```powershell
python experiments\reconstruct_with_cross_repair.py `
  --skill respect-broker `
  --agent-command "codex --ask-for-approval never exec --ephemeral --sandbox danger-full-access -" `
  --limit 10
```

Generated cross-broker artifacts are written to `experiments/cross_runs/`, which
is ignored by Git. The batch manifest is:

```text
experiments/cross_runs/runs.jsonl
```

For debugging a single natural-language description without the dataset batch
wrapper, call the single-run orchestrator directly:

```powershell
python experiments\cross_repair_with_broker.py `
  --description-file path\to\description.txt `
  --skill respect-broker `
  --dry-run
```

Remove `--dry-run` to start the two agent processes for that one description.

## Independent-Test Reconstruction

`independent_test_repair.py` runs one specification agent and one independent
test-writer agent. The specification agent uses `respect-spec-tester` to
generate, validate, repair, check well-separation, and synthesize Spectra. The
test-writer agent uses `respect-test-writer` to write `.rtest` plans from only
the natural-language description, fixed env/sys signature, and controller
metadata. The test-writer must not inspect generated Spectra contents.

Run a single dry run:

```powershell
python experiments\independent_test_repair.py `
  --description-file path\to\description.txt `
  --signature-file path\to\signature.json `
  --dry-run
```

Run a real single-description experiment:

```powershell
python experiments\independent_test_repair.py `
  --description-file path\to\description.txt `
  --signature-file path\to\signature.json `
  --max-feedback-rounds 3
```

The runner repeats feedback rounds until tests pass, the spec agent no longer
synthesizes, or `--max-feedback-rounds` is reached. Each round is:

```text
spec agent -> synthesize controller -> test writer -> compile/run tests
  -> if justified failures remain, feed test results back to spec agent
```

Batch runs use `reconstruct_with_independent_tests.py`. It expects one signature
JSON per description under `--signature-root`, named either
`<description_id>.json` or `<dataset_id>.json`.

```powershell
python experiments\reconstruct_with_independent_tests.py `
  --signature-root dataset\signatures `
  --limit 3 `
  --dry-run
```

Signature JSON format:

```json
{
  "spec_name": "TrafficE2",
  "environment": [
    {"name": "carA", "type": "boolean", "domain": ["false", "true"]}
  ],
  "system": [
    {"name": "greenA", "type": "boolean", "domain": ["false", "true"]}
  ]
}
```
