---
name: respect-method-cross-broker
description: Method cross-broker agent for the ReSpect study. Generate Spectra specifications from natural-language requirements, validate and synthesize with spectra-cli.jar like method 2, repair syntax errors, repair unrealizability with CLI counter-strategy diagnostics like method 3 when consistent with the natural-language description, and after successful synthesis submit the generated specification to experiments/cross_broker.py for peer disagreement feedback. Do not run controller_tests, generated semantic tests, equivalence checks, mutation checks, or benchmark oracles.
---

# ReSpect Method Cross-Broker: CLI-Diagnosed Repair With Peer Disagreement Feedback

## Research Role

This skill implements a cross-agent ReSpect reconstruction condition:

- Input: natural-language requirements for a reactive system.
- Output: a generated Spectra specification plus CLI validation, diagnosis, synthesis, broker feedback, and repair results.
- Feedback sources before broker submission: `spectra-cli.jar` parser/realizability/synthesis output and CLI counter-strategy diagnostics for unrealizable specifications.
- Feedback source after successful synthesis: disagreement feedback returned by `experiments/cross_broker.py`.
- Allowed repair signal in the current version: parser output, realizability status, counter-strategy output, generated Spectra, the natural-language description, and broker status/feedback.
- Not allowed: `controller_tests`, generated controller tests, semantic equivalence checks against the benchmark, mutation checks, oracle-based tests, reading or comparing against the original/reference Spectra file, accepted dataset files, HOA distance results, or benchmark fixtures.

The goal is to measure whether peer disagreement feedback can be introduced after the same syntax and unrealizability handling used by method 3, while avoiding the method-3 controller-test feedback source.

## Workflow

1. Read `references/spectra-workflow.md` before drafting a new specification.
2. Translate the user's natural-language description into a complete Spectra specification.
3. Save the draft to a temporary `.spectra` file before validation.
4. Initialize `repair_loops = 0`, `syntax_repair_loops = 0`, `unrealizable_repair_loops = 0`, `broker_repair_loops = 0`, and `broker_witnesses_received = 0`.
5. Run `scripts/run_spectra_cli.py` on the saved file with an explicit timeout.
6. If the result is `syntax_error`, inspect the parser message, increment both `repair_loops` and `syntax_repair_loops`, repair only the syntax, and rerun validation.
7. Limit syntax-repair loops to at most 3 attempts and report the last parser error if repair still fails.
8. If the result is `timeout`, report the timeout and do not continue.
9. If the result is `unrealizable`, request CLI diagnostics with `--counter-strategy` and save the diagnostic JSON.
10. Analyze the counter-strategy and the natural-language description before changing the specification.
11. Repair unrealizability only if the proposed change is consistent with the natural-language description.
12. Prefer minimal repairs that preserve stated requirements: fix overly strong initialization, add environment assumptions only when implied by the description, or relax/reshape a guarantee only when the description supports the weaker form.
13. If every plausible repair would contradict the natural-language description, stop and report `blocked_by_nl_conflict = true`.
14. After each unrealizability repair, increment both `repair_loops` and `unrealizable_repair_loops`, save the file, rerun validation, and continue from the appropriate branch.
15. Limit unrealizability-repair loops to at most 3 attempts.
16. If the result is `realizable`, run synthesis. If synthesis succeeds, set `cli_status = synthesized` and continue to broker submission.
17. Submit the current synthesized Spectra file to the broker by running `experiments/cross_broker.py submit-and-wait` with the run id, round id, agent id, spec path, and timeout provided by the task prompt.
18. Save the broker JSON response as `broker/feedback-<round>.json`.
19. In the current version, do not repair the specification based on broker witnesses unless the user explicitly requests broker-witness repair logic. Record the broker feedback status and witness count, then report the final result.
20. Always include the final method cross-broker result fields in the response.

## Temporary File Handling

- Create a temporary working directory under the repository root, for example `tmp/spectra-runs/<timestamp>-<slug>/`.
- Save the generated specification as `<name>.spectra`.
- Save the JSON output of each counter-strategy wrapper call as `diagnostics/unrealizable-<n>.json`. The actual counter-strategy text is preserved inside that JSON object's `raw_output` field.
- Save broker responses as `broker/feedback-<round>.json`.
- Keep the final `.spectra` file and synthesis output long enough for inspection.
- Do not overwrite unrelated files.

## Validation Commands

Use the bundled wrapper instead of calling the jar directly:

```bash
python .agents/skills/respect-method-cross-broker/scripts/run_spectra_cli.py --input <path-to-file> --timeout 120
```

For counter-strategy diagnostics after an `unrealizable` result:

```bash
python .agents/skills/respect-method-cross-broker/scripts/run_spectra_cli.py --input <path-to-file> --counter-strategy --timeout 120
```

Use JTLV text format only if the default counter-strategy output is not useful:

```bash
python .agents/skills/respect-method-cross-broker/scripts/run_spectra_cli.py --input <path-to-file> --counter-strategy-jtlv-format --timeout 120
```

For synthesis after a `realizable` result:

```bash
python .agents/skills/respect-method-cross-broker/scripts/run_spectra_cli.py --input <path-to-file> --synthesize --output-dir <path-to-output-dir> --timeout 120
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

- `ready`: broker feedback is available; save it and count `witnesses`.
- `timeout`: peer feedback was unavailable; do not invent broker feedback.
- `comparison_failed`, `alphabet_mismatch`, or other non-ready statuses: report the broker status and do not continue to broker-based repair.

Broker witnesses are disagreement evidence, not oracle counterexamples. Do not treat the peer specification as ground truth.

## Method Cross-Broker Boundaries

- Use the same syntax-repair and unrealizability-repair discipline as method 3.
- Do not run `controller_tests`.
- Do not create or run NL-guided controller tests.
- Do not run generated semantic tests, trace tests, benchmark-specific oracle checks, mutation checks, or equivalence checks.
- Do not open `source_spectra_file`, accepted dataset files, HOA exports, distance results, or benchmark fixtures for the current instance.
- Do not make a specification realizable by deleting stated requirements without a natural-language justification.
- Do not weaken a guarantee merely because it appears in the counter-strategy; first decide whether the weaker behavior is allowed by the description.
- Do not add environment assumptions that shift responsibility to the environment unless the description states or strongly implies that assumption.
- Do not compare the generated Spectra file against an original/reference Spectra file.
- Do not treat broker feedback as proof that the generated Spectra is wrong.

## Unrealizability Repair Rules

- Treat the counter-strategy as diagnostic evidence, not as permission to rewrite the task.
- State the suspected conflict before editing.
- Check each proposed repair against the natural-language description:
  - `consistent`: apply the minimal edit and retry.
  - `unclear`: prefer a smaller edit or stop if the assumption would be material.
  - `contradicts`: do not apply the edit.
- Preserve all explicitly described inputs, outputs, initial conditions, safety requirements, liveness requirements, and update rules unless the description itself leaves room for the change.
- Keep a concise repair log for each unrealizability loop.

## Broker Feedback Handling

In the current version, broker feedback is collected but not used for specification repair unless the user explicitly requests broker-witness repair logic.

When broker feedback is ready:

1. Read the broker JSON response from stdout.
2. Save it under `broker/feedback-<round>.json`.
3. Count the number of `witnesses`.
4. Set `broker_feedback_status` to the broker `status`.
5. Set `broker_witnesses_received` to the witness count.
6. Set `broker_repair_decision = not_implemented`.
7. Leave the Spectra file unchanged after broker feedback.

If broker-witness repair is later enabled, only revise the specification when the natural-language requirements clearly justify the change. Until then, do not perform broker-based repairs.

## Final Response Format

For study runs, keep the final response compact and include:

```text
cli_status: <syntax_error|unrealizable|realizable|synthesized|timeout|unknown>
repair_loops: <number>
syntax_repair_loops: <number>
unrealizable_repair_loops: <number>
broker_repair_loops: <number>
timeout_seconds: <number>
used_counter_strategy: <true|false>
blocked_by_nl_conflict: <true|false>
diagnostic_file: <path or none>
broker_feedback_status: <ready|timeout|comparison_failed|alphabet_mismatch|none|other>
broker_feedback_file: <path or none>
broker_witnesses_received: <number>
broker_repair_decision: <not_implemented|none>
spectra_file: <path>
controller_output_dir: <path or none>
```

## Bundled Resources

- `scripts/run_spectra_cli.py`: Run `spectra-cli.jar`, normalize the outcome, optionally request counter-strategy diagnostics, and preserve raw output.
- `references/spectra-workflow.md`: Spectra examples, CLI result patterns, and drafting/repair guidance.
- `experiments/cross_broker.py`: Repository-level broker used after successful synthesis to synchronize peer disagreement feedback.
