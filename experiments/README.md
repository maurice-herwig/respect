# Experiments

This directory contains scripts for the agent-based reconstruction experiments.

## Skill-Based Reconstruction

`reconstruct_with_skill.py` reads natural-language descriptions from
`dataset/nl_descriptions/descriptions.jsonl` and starts a fresh agent process
for each description. The selected skill is injected into the agent prompt.

Dry run:

```powershell
python experiments\reconstruct_with_skill.py --skill respect-method-2 --dry-run --limit 3
```

Run with the default agent command:

```powershell
python experiments\reconstruct_with_skill.py --skill respect-method-2
```

The default command is:

```text
codex exec --ephemeral -
```

`--ephemeral` prevents Codex from persisting session files for the invocation,
and `-` reads the prompt from stdin. The script starts a separate process for
each description.

If your Codex CLI uses a different invocation, pass it explicitly:

```powershell
python experiments\reconstruct_with_skill.py `
  --skill respect-method-2 `
  --agent-command "codex exec --ephemeral -"
```

Generated experiment artifacts are written to `experiments/runs/`, which is
ignored by Git.

Each run stores the prompt and captured agent output:

- `input_description.txt`
- `agent_prompt.txt`
- `agent_stdout.txt`
- `agent_stderr.txt`
- `parsed_result.json`, if the agent prints a final JSON object
- a row in `runs.jsonl`
