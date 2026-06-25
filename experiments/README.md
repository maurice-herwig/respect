# Experiments

This directory contains scripts for the agent-based reconstruction experiments.

Unless a section says otherwise, run commands from the repository root.

## Skill-Based Reconstruction

`reconstruct_with_skill.py` reads natural-language descriptions from
`dataset/nl_descriptions/descriptions.jsonl` and starts a fresh agent process
for each description. The selected skill is injected into the agent prompt.

From the repository root, run:

```powershell
python experiments\reconstruct_with_skill.py --skill respect-method-2 --dry-run --limit 3
```

From this `experiments` directory, run:

```powershell
python reconstruct_with_skill.py --skill respect-method-2 --dry-run --limit 3
```

Run a limited real experiment from the repository root:

```powershell
python reconstruct_with_skill.py --skill respect-method-2 --limit 140
```
```powershell
python reconstruct_with_skill.py --skill respect-method-3 --limit 180
```

Run all pending descriptions with the default agent command:

```powershell
python experiments\reconstruct_with_skill.py --skill respect-method-2
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
  --skill respect-method-2 `
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
experiments/runs/A/B/C/respect-method-2/
```

Each run directory stores:

- `input_description.txt`
- `agent_prompt.txt`
- `agent_stdout.txt`
- `agent_stderr.txt`
- `parsed_result.json`, if the agent prints a final JSON object
- `respect-method-2.spectra`, if the agent reports a Spectra file
- a row in `runs.jsonl`
