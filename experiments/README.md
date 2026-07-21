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
- a row in `runs.jsonl`

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
