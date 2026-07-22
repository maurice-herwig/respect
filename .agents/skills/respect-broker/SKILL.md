---
name: respect-broker
description: Method cross-broker agent for the ReSpect study. Generate Spectra specifications from natural-language requirements using the repository Spectra Xtext grammar at assets/grammar/Spectra.xtext as initial syntax guidance, validate with spectra-cli.jar, repair syntax errors, repair unrealizability with CLI counter-strategy diagnostics when consistent with the natural-language description, check and repair well-separation before synthesis, and after successful synthesis submit the generated specification to experiments/cross_broker.py for peer disagreement feedback. Do not run controller_tests, generated semantic tests, equivalence checks, mutation checks, or benchmark oracles.
---

# ReSpect Method Cross-Broker: Grammar-Guided CLI-Diagnosed Repair With Peer Disagreement Feedback

## Research Role

This skill implements a cross-agent ReSpect reconstruction condition:

- Input: natural-language requirements for a reactive system.
- Output: a generated Spectra specification plus CLI validation, diagnosis, synthesis, broker feedback, and repair results.
- Initial syntax reference: `assets/grammar/Spectra.xtext`.
- Feedback sources before broker submission: `spectra-cli.jar` parser/realizability/synthesis/well-separation output and CLI counter-strategy diagnostics for unrealizable specifications.
- Feedback source after successful synthesis: disagreement feedback returned by `experiments/cross_broker.py`.
- Allowed repair signal: parser output, realizability status, well-separation status, counter-strategy output, generated Spectra, the natural-language description, and broker disagreement feedback.
- Not allowed: `controller_tests`, generated controller tests, semantic equivalence checks against the benchmark, mutation checks, oracle-based tests, reading or comparing against the original/reference Spectra file, accepted dataset files, HOA distance results, or benchmark fixtures.

The goal is to measure whether peer disagreement feedback can improve reconstruction after syntax and unrealizability handling, while avoiding the controller-test feedback source.

## Best-Practice Drafting Order

Before writing the first complete Spectra draft, perform a concise requirements decomposition:

1. Identify the system boundary and declare which named concepts are environment-controlled inputs and which are system-controlled outputs.
2. Separate environment assumptions from system guarantees. Do not encode an assumption unless the natural-language description states or strongly implies the environment constraint.
3. Classify each requirement as an initial condition, safety/update rule, liveness/justice requirement, or response/pattern requirement.
4. Prefer the smallest kernel-level Spectra model that covers the stated requirements. Use advanced constructs such as patterns, monitors, counters, triggers, quantifiers, or arrays only when they express the natural-language requirement more directly or materially improve readability.
5. Build the first draft incrementally in reasoning: add one coherent requirement group at a time, checking for ownership mistakes, hidden assumptions, contradictory initial conditions, over-strong guarantees, and duplicate or unused variables before saving `specs/00_initial.spectra`.

This decomposition is a drafting discipline only. Do not read benchmark or source Spectra files, and do not run oracle-style checks.

## Workflow

1. Read `references/spectra-workflow.md` before drafting a new specification.
2. Read `assets/grammar/Spectra.xtext` before drafting, and use it only as syntax guidance for valid Spectra constructs.
3. Follow the best-practice drafting order above, then translate the user's natural-language description into a complete Spectra specification.
4. Save the initial draft as `specs/00_initial.spectra` before validation.
5. Initialize `repair_loops = 0`, `syntax_repair_loops = 0`, `unrealizable_repair_loops = 0`, `well_separation_repair_loops = 0`, `broker_repair_loops = 0`, `broker_witnesses_received = 0`, `accepted_by_self_rejected_by_peer_repaired = 0`, `accepted_by_self_rejected_by_peer_ignored = 0`, `rejected_by_self_accepted_by_peer_repaired = 0`, and `rejected_by_self_accepted_by_peer_ignored = 0`.
6. Run `scripts/run_spectra_cli.py` on the saved file with an explicit timeout.
7. If the result is `syntax_error`, inspect the parser message, increment both `repair_loops` and `syntax_repair_loops`, repair only the syntax, and rerun validation.
8. After the syntax-repair phase ends and the run moves to the next phase, save the stable repaired specification as `specs/01_after_syntax_repair.spectra` and append one transition record to `repair_log.jsonl`.
9. Limit syntax-repair loops to at most 3 attempts and report the last parser error if repair still fails.
10. If the result is `timeout`, report the timeout and do not continue.
11. If the result is `unrealizable`, request CLI diagnostics with `--counter-strategy` and save the diagnostic JSON.
12. Analyze the counter-strategy and the natural-language description before changing the specification.
13. Repair unrealizability only if the proposed change is consistent with the natural-language description.
14. Prefer minimal repairs that preserve stated requirements: fix overly strong initialization, add environment assumptions only when implied by the description, or relax/reshape a guarantee only when the description supports the weaker form.
15. If every plausible repair would contradict the natural-language description, stop and report `blocked_by_nl_conflict = true`.
16. After each unrealizability repair, increment both `repair_loops` and `unrealizable_repair_loops`, save the current working file, rerun validation, and continue from the appropriate branch.
17. Limit unrealizability-repair loops to at most 3 attempts.
18. After the unrealizability-repair phase ends and the run moves to well-separation or stops, save the stable repaired specification as `specs/02_after_unrealizable_repair.spectra` and append one transition record to `repair_log.jsonl`.
19. If the specification is `realizable`, run the well-separation check before synthesis and save the wrapper JSON as `diagnostics/well-separation-<n>.json`.
20. If the well-separation result is `non_well_separated`, inspect the generated Spectra and the natural-language description before changing the specification.
21. Repair non-well-separation only by changing environment assumptions or related modeling choices that are inconsistent with, or not justified by, the natural-language description. Do not delete stated requirements, add artificial assumptions, or weaken guarantees unless the natural-language description supports that change.
22. After each well-separation repair, increment both `repair_loops` and `well_separation_repair_loops`, save the current working file, rerun validation, rerun well-separation when realizable, and continue from the appropriate branch.
23. Limit well-separation-repair loops to at most 3 attempts. If every plausible repair would contradict the natural-language description, stop and report `blocked_by_nl_conflict = true`.
24. After the well-separation-repair phase ends and the run moves to synthesis or stops, save the stable repaired specification as `specs/03_after_well_separation_repair.spectra` and append one transition record to `repair_log.jsonl`.
25. If the well-separation result is `well_separated`, run synthesis. If synthesis succeeds, set `cli_status = synthesized` and continue to broker submission.
26. Submit the current synthesized Spectra file to the broker by running `experiments/cross_broker.py submit-and-wait` with the run id, current round id, agent id, spec path, expected agents, and timeout provided by the task prompt.
27. Save the broker JSON response as `broker/feedback-<round>.json`. If the response contains a `feedback_file`, read that file and use it as the authoritative broker feedback for the round.
28. If broker feedback is unavailable, has a non-ready status, or reports `semantic_relation = equivalent`, record the status and stop the broker loop.
29. If broker feedback reports disagreement words, inspect both `accepted_by_you_rejected_by_peer` and `rejected_by_you_accepted_by_peer`. Treat them as peer disagreement evidence only, not as ground truth.
30. Decide for each word whether the natural-language description supports a specification change. Count every word as either leading to repair or ignored, separately for each direction.
31. If no word justifies a change, stop the broker loop and report that broker feedback was not applied.
32. If at least one word justifies a change, make the minimal Spectra repair consistent with the natural-language description, increment both `repair_loops` and `broker_repair_loops`, save the file, rerun CLI validation, rerun well-separation when realizable, rerun synthesis, increment the broker round id, and submit the repaired Spectra to the broker again.
33. After the broker-repair phase ends and the run moves to the next broker round or stops, save the stable repaired specification as `specs/04_after_broker_repair.spectra` and append one transition record to `repair_log.jsonl`.
34. Limit broker-repair loops to at most 3 attempts.
35. Save the final Spectra version as `final.spectra`. Always include the final method cross-broker result fields in the response.

## Temporary File Handling

- Create a temporary working directory under the repository root, for example `tmp/spectra-runs/<timestamp>-<slug>/`.
- Use this stable artifact layout:

```text
tmp/spectra-runs/<timestamp>-<slug>/
  specs/
    00_initial.spectra
    01_after_syntax_repair.spectra
    02_after_unrealizable_repair.spectra
    03_after_well_separation_repair.spectra
    04_after_broker_repair.spectra
  diagnostics/
    unrealizable-<n>.json
    well-separation-<n>.json
  broker/
    feedback-<round>.json
    feedback-detail-<round>.json
    repair-decisions-<round>.json
  final.spectra
  repair_log.jsonl
```

- Save only stable Spectra versions at phase boundaries: the initial draft, the specification that leaves each repair phase, and the final specification. Do not save every intermediate failed repair attempt inside a loop unless it is also the final state.
- Omit phase-specific spec files and repair-log entries for phases that did not run. For example, if no broker repair was attempted, do not create `specs/04_after_broker_repair.spectra`.
- Keep `final.spectra` as a copy of the last stable Spectra version and report `spectra_file` as that path.
- Append one JSON object per phase transition to `repair_log.jsonl`.
- Use this `repair_log.jsonl` schema consistently for cross-broker runs:

```json
{
  "version": "04_after_broker_repair",
  "phase": "broker_repair",
  "input_spec": "specs/03_after_well_separation_repair.spectra",
  "output_spec": "specs/04_after_broker_repair.spectra",
  "trigger": "broker_disagreement",
  "result_before": "synthesized",
  "result_after": "synthesized",
  "repair_loops_total": 2,
  "syntax_repair_loops": 0,
  "unrealizable_repair_loops": 1,
  "well_separation_repair_loops": 0,
  "test_repair_loops": 0,
  "broker_repair_loops": 1,
  "diagnostic_files": ["broker/feedback-1.json", "broker/repair-decisions-1.json"],
  "notes": "Minimal NL-consistent broker-feedback repair summary."
}
```

- Save the JSON output of each counter-strategy wrapper call as `diagnostics/unrealizable-<n>.json`. The actual counter-strategy text is preserved inside that JSON object's `raw_output` field.
- Save the JSON output of each well-separation wrapper call as `diagnostics/well-separation-<n>.json`. The actual CLI text is preserved inside that JSON object's `raw_output` field.
- Save broker responses as `broker/feedback-<round>.json`.
- If the broker response references `feedback_file`, read that file and save a copy as `broker/feedback-detail-<round>.json` before making any repair decision.
- Save a concise repair-decision log as `broker/repair-decisions-<round>.json`, including per-word decisions and counters.
- Keep the final `.spectra` file and synthesis output long enough for inspection.
- Do not overwrite unrelated files.

## Validation Commands

Use the bundled wrapper instead of calling the jar directly:

```bash
python .agents/skills/respect-broker/scripts/run_spectra_cli.py --input <path-to-file> --timeout 120
```

For counter-strategy diagnostics after an `unrealizable` result:

```bash
python .agents/skills/respect-broker/scripts/run_spectra_cli.py --input <path-to-file> --counter-strategy --timeout 120
```

For well-separation after a `realizable` result and before synthesis:

```bash
python .agents/skills/respect-broker/scripts/run_spectra_cli.py --input <path-to-file> --well-separation --timeout 120
```

The wrapper returns `status = well_separated` or `status = non_well_separated`. The underlying CLI returns exit code 0 for both outcomes, so use the normalized `status`, not the process exit code, to branch.

Use JTLV text format only if the default counter-strategy output is not useful:

```bash
python .agents/skills/respect-broker/scripts/run_spectra_cli.py --input <path-to-file> --counter-strategy-jtlv-format --timeout 120
```

For synthesis after a `realizable` result:

```bash
python .agents/skills/respect-broker/scripts/run_spectra_cli.py --input <path-to-file> --synthesize --output-dir <path-to-output-dir> --timeout 120
```

## Broker Command

Use the repository broker after successful synthesis. The task prompt must provide `run_id`, `agent_id`, and `round_id`. Use `agent_a` or `agent_b` unless the orchestrator provides a different expected-agent set.

```bash
python experiments/cross_broker.py submit-and-wait --run-id <run-id> --round <round-id> --agent <agent-id> --spec <path-to-file> --timeout 600
```

If the orchestrator provides `expected_agents`, pass them through:

```bash
python experiments/cross_broker.py submit-and-wait --run-id <run-id> --round <round-id> --agent <agent-id> --spec <path-to-file> --expected-agents agent_a agent_b --timeout 600
```

Treat broker responses as structured experiment feedback:

- `ready`: broker feedback is available. Read the referenced `feedback_file` when present.
- `timeout`: peer feedback was unavailable; do not invent broker feedback.
- `comparison_failed`, `alphabet_mismatch`, or other non-ready statuses: report the broker status and do not continue to broker-based repair.

The skill-facing feedback file has this shape:

```json
{
  "status": "ready",
  "semantic_relation": "equivalent|different|unknown",
  "accepted_by_you_rejected_by_peer": [],
  "rejected_by_you_accepted_by_peer": [],
  "witness_count": 0,
  "comparison_file": "..."
}
```

`accepted_by_you_rejected_by_peer` contains ultimately-periodic words accepted by the current generated Spectra specification but rejected by the peer specification. `rejected_by_you_accepted_by_peer` contains ultimately-periodic words rejected by the current generated Spectra specification but accepted by the peer specification. Each word is represented as `prefix` and `loop`, where the loop repeats forever.

Broker words are disagreement evidence, not oracle counterexamples. The peer specification was produced by another agent and may be wrong. Do not treat peer-accepted behavior as required or peer-rejected behavior as forbidden unless the natural-language requirements support that conclusion.

## Method Cross-Broker Boundaries

- Use the syntax-repair and unrealizability-repair discipline defined in this skill.
- Use `assets/grammar/Spectra.xtext` as a syntax reference, not as semantic feedback or a repair oracle.
- Do not run `controller_tests`.
- Do not create or run NL-guided controller tests.
- Do not run generated semantic tests, trace tests, benchmark-specific oracle checks, mutation checks, or equivalence checks.
- Do not open `source_spectra_file`, accepted dataset files, HOA exports, distance results, or benchmark fixtures for the current instance.
- Do not make a specification realizable by deleting stated requirements without a natural-language justification.
- Do not weaken a guarantee merely because it appears in the counter-strategy; first decide whether the weaker behavior is allowed by the description.
- Do not add environment assumptions that shift responsibility to the environment unless the description states or strongly implies that assumption.
- Do not compare the generated Spectra file against an original/reference Spectra file.
- Do not treat broker feedback as proof that the generated Spectra is wrong.
- Do not repair solely to match the peer specification. Repair only to better satisfy the natural-language description.

## Unrealizability Repair Rules

- Treat the counter-strategy as diagnostic evidence, not as permission to rewrite the task.
- State the suspected conflict before editing.
- Check each proposed repair against the natural-language description:
  - `consistent`: apply the minimal edit and retry.
  - `unclear`: prefer a smaller edit or stop if the assumption would be material.
  - `contradicts`: do not apply the edit.
- Preserve all explicitly described inputs, outputs, initial conditions, safety requirements, liveness requirements, and update rules unless the description itself leaves room for the change.
- Keep a concise repair log for each unrealizability loop.

## Well-Separation Repair Rules

- Treat `non_well_separated` as diagnostic evidence that the system may be able to force the environment to violate its own assumptions.
- Inspect environment assumptions first, especially assumptions that mention system variables or constrain the environment based on system-controlled behavior.
- Repair only when the natural-language description supports the change.
- Prefer removing or reshaping unjustified environment assumptions over adding new assumptions.
- Do not delete stated guarantees or weaken required behavior solely to make the well-separation check pass.
- If the natural-language description genuinely requires a non-well-separated environment contract, stop and report `blocked_by_nl_conflict = true`.

## Broker Feedback Handling

When broker feedback is ready:

1. Read the broker JSON response from stdout and save it as `broker/feedback-<round>.json`.
2. If the JSON contains `feedback_file`, read that file and save a copy as `broker/feedback-detail-<round>.json`.
3. Set `broker_feedback_status` to the feedback `status`.
4. Set `broker_witnesses_received` to the total `witness_count`.
5. If `semantic_relation = equivalent`, set `broker_repair_decision = equivalent` and stop.
6. If no feedback file exists, the status is not `ready`, or the semantic relation is `unknown`, set `broker_repair_decision = no_repair` and stop.
7. For each word in `accepted_by_you_rejected_by_peer`, decide whether the natural-language description says the behavior should be rejected. If yes, count it in `accepted_by_self_rejected_by_peer_repaired`; otherwise count it in `accepted_by_self_rejected_by_peer_ignored`.
8. For each word in `rejected_by_you_accepted_by_peer`, decide whether the natural-language description says the behavior should be accepted. If yes, count it in `rejected_by_self_accepted_by_peer_repaired`; otherwise count it in `rejected_by_self_accepted_by_peer_ignored`.
9. Save the per-word decisions and the counters as `broker/repair-decisions-<round>.json`.
10. If no word supports a change, set `broker_repair_decision = ignored_feedback` and stop.
11. If one or more words support a change, apply one minimal coherent repair that addresses the justified feedback without contradicting the natural-language description. Set `broker_repair_decision = repaired`, increment `repair_loops` and `broker_repair_loops`, rerun validation and synthesis, then submit the repaired Spectra in the next broker round.
12. Stop after 3 broker-repair loops even if further disagreement remains.

For `accepted_by_you_rejected_by_peer`, a justified repair usually means strengthening or correcting the generated Spectra so that the disputed behavior is no longer accepted. For `rejected_by_you_accepted_by_peer`, a justified repair usually means relaxing or correcting the generated Spectra so that the disputed behavior becomes accepted. In both directions, the natural-language description is the deciding authority, not the peer.

## Final Response Format

For study runs, keep the final response compact and include:

```text
cli_status: <syntax_error|unrealizable|realizable|synthesized|timeout|unknown>
repair_loops: <number>
syntax_repair_loops: <number>
unrealizable_repair_loops: <number>
well_separation_repair_loops: <number>
broker_repair_loops: <number>
timeout_seconds: <number>
used_counter_strategy: <true|false>
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
```

## Bundled Resources

- `scripts/run_spectra_cli.py`: Run `spectra-cli.jar`, normalize the outcome, optionally request counter-strategy diagnostics, and preserve raw output.
- `references/spectra-workflow.md`: Spectra examples, CLI result patterns, and drafting/repair guidance.
- `assets/examples/LanguageFeatures/`: Compact `.spectra` syntax examples for less common Spectra language constructs.
- `assets/grammar/Spectra.xtext`: Repository-level Xtext grammar for Spectra syntax. Read this before drafting generated specifications.
- `experiments/cross_broker.py`: Repository-level broker used after successful synthesis to synchronize peer disagreement feedback.
