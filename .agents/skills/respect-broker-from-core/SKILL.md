---
name: respect-broker-from-core
description: Cross-broker incumbent skill for branched ReSpect experiments. Start from an existing core_final.spectra plus full core context, validate and synthesize it, submit to experiments/cross_broker.py for peer disagreement feedback against a fresh challenger, and repair only broker-feedback differences justified by the natural-language requirements. Do not redraft from scratch, run controller_tests, or read source Spectra/benchmark oracles.
---

# ReSpect Broker From Core

## Research Role

This skill implements the incumbent side of the branched cross-repair condition:

- Input: natural-language requirements, fixed environment/system signature, `core_final.spectra`, `core_context.full.json`, broker metadata, and optional controller metadata.
- Output: branch Spectra files, CLI diagnostics, synthesis output, broker feedback artifacts, repair counts, and final incumbent artifacts.
- Feedback sources: generated core Spectra, full core context, parser/realizability/well-separation/synthesis output, and broker disagreement feedback from a fresh challenger.
- Not allowed: redrafting from scratch, controller_tests, generated semantic tests, mutation checks, equivalence checks against benchmark oracles, source/reference Spectra files, accepted dataset files, HOA distance results, or benchmark fixtures.

The goal is to measure whether an independent fresh challenger can improve the same `core_final.spectra` incumbent used by the other branched feedback strategies.

## Workflow

1. Read `.agents/skills/respect-broker-from-core/references/spectra-workflow.md` and `assets/grammar/Spectra.xtext` before repairing.
2. Read the fixed signature, `core_final.spectra`, and `core_context.full.json` supplied by the prompt.
3. Copy `core_final.spectra` to `specs/00_from_core.spectra`. This is the branch parent. Do not create `specs/00_initial.spectra` and do not redraft from NL.
4. Initialize branch counters: `repair_loops = 0`, `syntax_repair_loops = 0`, `unrealizable_repair_loops = 0`, `well_separation_repair_loops = 0`, `broker_repair_loops = 0`, `broker_witnesses_received = 0`, `accepted_by_self_rejected_by_peer_repaired = 0`, `accepted_by_self_rejected_by_peer_ignored = 0`, `rejected_by_self_accepted_by_peer_repaired = 0`, and `rejected_by_self_accepted_by_peer_ignored = 0`.
5. Validate `specs/00_from_core.spectra` with `.agents/skills/respect-broker-from-core/scripts/run_spectra_cli.py --input <file> --timeout 120`.
6. If the copied core file has a syntax/realizability/well-separation problem, repair only the minimal issue consistent with the natural-language requirements and core context, preserving the core semantics when possible.
7. Run well-separation before synthesis whenever the specification is realizable.
8. Synthesize only when the specification is realizable and well-separated.
9. Submit the current synthesized Spectra file to the broker using the command supplied by the prompt, including `--runs-root`, `--run-id`, `--round`, `--agent`, `--expected-agents`, and `--timeout`.
10. Save the broker JSON response as `broker/feedback-<round>.json`. If it references `feedback_file`, read that file and save a copy as `broker/feedback-detail-<round>.json`.
11. Treat broker words as disagreement evidence only. Decide whether each direction is justified by the natural-language requirements, not by the peer specification alone.
12. If no word justifies a change, stop the broker loop and report `broker_repair_decision = ignored_feedback` or `equivalent` as appropriate.
13. If feedback justifies a repair, minimally edit Spectra, increment `repair_loops` and `broker_repair_loops`, validate, check well-separation, synthesize, increment the round id, and submit again.
14. Save the stable post-broker-repair specification as `specs/04_after_broker_repair.spectra` when this phase completes.
15. Stop after the prompt's `max_broker_repair_loops`, defaulting to 3 if omitted.
16. Save the final Spectra version as `final.spectra` and report all final fields.

After every Spectra edit, return to validation before well-separation, synthesis, or broker submission.

## Artifact Layout

Use the run directory supplied in the prompt:

```text
<run-dir>/
  specs/
    00_from_core.spectra
    04_after_broker_repair.spectra
  diagnostics/
    unrealizable-<n>.json
    unrealizable-core-<n>.json
    well-separation-<n>.json
  broker/
    feedback-<round>.json
    feedback-detail-<round>.json
    repair-decisions-<round>.json
  synthesis/
  final.spectra
  repair_log.jsonl
```

Omit phase-specific files for phases that did not run. Append one JSON object per phase transition to `repair_log.jsonl`.

## Broker Command

The prompt supplies exact run metadata. Use that metadata and include the shared broker runs root:

```powershell
python experiments\cross_broker.py submit-and-wait --runs-root <broker-runs-root> --run-id <run-id> --round <round-id> --agent <agent-id> --spec <path-to-current-spectra-file> --expected-agents <agent-a> <agent-b> --timeout <broker-timeout-seconds>
```

Use a new incremented round id after each justified broker repair.

## Final Response Format

Return a final JSON object or key-value block with:

```text
cli_status: <syntax_error|unrealizable|realizable|synthesized|timeout|unknown>
repair_loops: <number>
syntax_repair_loops: <number>
unrealizable_repair_loops: <number>
well_separation_repair_loops: <number>
broker_repair_loops: <number>
timeout_seconds: <number>
used_counter_strategy: <true|false>
used_unrealizable_core: <true|false>
unrealizable_core_file: <path or none>
unrealizable_core_size: <number or none>
unrealizable_core_lines: <JSON array of line numbers, or []>
well_separation_status: <well_separated|non_well_separated|not_checked|unknown>
blocked_by_nl_conflict: <true|false>
diagnostic_file: <path or none>
well_separation_file: <path or none>
broker_feedback_status: <ready|timeout|comparison_failed|alphabet_mismatch|none|other>
broker_feedback_file: <path or none>
broker_witnesses_received: <number>
broker_repair_decision: <equivalent|no_repair|ignored_feedback|repaired|none>
accepted_by_self_rejected_by_peer_repaired: <number>
accepted_by_self_rejected_by_peer_ignored: <number>
rejected_by_self_accepted_by_peer_repaired: <number>
rejected_by_self_accepted_by_peer_ignored: <number>
spectra_file: <path>
controller_output_dir: <path or none>
artifact_dir: <path>
repair_log_file: <path>
parent_spectra_file: <path>
```
