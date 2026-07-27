---
name: respect-interactive-spec-tester
description: Interactive variant of respect-spec-tester for ReSpect user studies with independent TestDSL feedback. Use the same Spectra generation, validation, repair, synthesis, independent-test-feedback, and anti-oracle workflow as respect-spec-tester, but write setup/draft/repair outputs as participant-reviewable proposal files when the wizard asks for an interactive phase.
---

# ReSpect Spec Tester

## Interactive User-Study Delta

This skill is a copy of `respect-spec-tester` with only this interaction layer
added:

- When the prompt names `Phase: setup`, write only the requested
  `signature.proposed.json` and `decomposition.proposed.md`, then stop. Do not
  draft Spectra and do not run validation.
- When the prompt names `Phase: draft`, read the participant-reviewed signature
  and decomposition files, write only the requested `spec.proposed.spectra`,
  then stop. Do not run validation.
- When the prompt names `Phase: validate_and_synthesize`, run the original
  `respect-spec-tester` workflow below on the participant-reviewed Spectra
  file.
- When the prompt names `Phase: test_feedback_repair`, run the original
  independent-test feedback workflow below on the supplied generated Spectra
  and test result file. If a Spectra repair is justified, also write the
  requested `spec.repair_proposed_<round>.spectra` for participant review.
- Treat participant-reviewed files as authoritative. Use exactly the reviewed
  environment and system variable names and ownerships.

All other rules below are inherited unchanged from `respect-spec-tester`.

## Research Role

This skill implements the specification side of the independent-test condition:

- Input: natural-language requirements, fixed environment/system signature, and optionally feedback from independently generated controller tests.
- Output: generated Spectra, CLI diagnostics, synthesis output, repair counts, and artifact paths.
- Feedback sources: parser/realizability/well-separation/synthesis output from `spectra-cli.jar`, counter-strategy diagnostics, unrealizable-core diagnostics, and independent test failures supplied by the orchestrator.
- Not allowed: writing controller tests, reading the independent test-writer prompt or reasoning, reading source/reference Spectra files, benchmark oracles, mutation checks, equivalence checks, or distance results.

The goal is to keep specification repair separate from test generation while preserving the ReSpect validation discipline.

## Workflow

1. Read `assets/grammar/Spectra.xtext` and `.agents/skills/respect/references/spectra-workflow.md` before drafting or repairing.
2. Read the fixed signature supplied by the prompt. Use exactly those environment and system variable names and ownerships.
3. Decompose the natural-language requirements into assumptions, guarantees, initial conditions, safety/update rules, liveness/justice requirements, and response/pattern requirements.
4. If no previous generated Spectra is supplied, draft a complete Spectra specification and save it as `specs/00_initial.spectra`.
5. If previous generated Spectra plus independent test feedback is supplied, read only those generated artifacts and repair minimally when the failing test is justified by the natural-language description.
6. Initialize or preserve counters: `repair_loops`, `syntax_repair_loops`, `unrealizable_repair_loops`, `well_separation_repair_loops`, and `independent_test_repair_loops`.
7. Validate with `.agents/skills/respect/scripts/run_spectra_cli.py --input <file> --timeout 120`.
8. Repair syntax errors for at most 3 syntax loops, then rerun validation.
9. If unrealizable, request `--counter-strategy`, save `diagnostics/unrealizable-<n>.json`, then request `--unrealizable-core` and save `diagnostics/unrealizable-core-<n>.json`. Analyze both diagnostics with the natural-language requirements. Use the core only to localize guarantees participating in an unrealizability conflict; do not treat it as a deletion list. Repair only when consistent with the natural-language requirements, then rerun validation.
10. If realizable, run `--well-separation`, save `diagnostics/well-separation-<n>.json`, repair non-well-separation only when consistent with the natural-language requirements, then rerun validation.
11. Synthesize only after the specification is both realizable and well-separated.
12. Stop after synthesis and report the final fields. Do not generate `.rtest` files or run controller tests yourself.

After every Spectra edit, return to validation before any well-separation check or synthesis.

## Independent Test Feedback

When the prompt provides a test result file:

- Read `tests_total`, `tests_passed`, `tests_failed`, each failing test's `name`, `kind`, `requirement`, `reason`, `trace`, and `details`.
- Decide whether each failure is justified by the natural-language description.
- If the test is too strong, underspecified, or unsupported, report `test_feedback_decision = rejected_invalid_test` and do not modify Spectra for that failure.
- When rejecting invalid tests, list every rejected test name exactly as it appears in the aggregated result file under `invalid_test_names`, and give a short `invalid_test_reason`.
- If the failure is justified, make the smallest Spectra repair, increment `repair_loops` and `independent_test_repair_loops`, then rerun validation, well-separation, and synthesis.
- Do not inspect the test-writer agent's stdout except for the test artifacts explicitly provided by the orchestrator.

## Artifact Layout

Use the run directory supplied in the prompt:

```text
<agent-a-run-dir>/
  specs/
    00_initial.spectra
    01_after_syntax_repair.spectra
    02_after_unrealizable_repair.spectra
    03_after_well_separation_repair.spectra
    04_after_independent_test_repair.spectra
  diagnostics/
    unrealizable-<n>.json
    unrealizable-core-<n>.json
    well-separation-<n>.json
  synthesis/
  final.spectra
  repair_log.jsonl
```

## Final Response Format

Return a final JSON object or key-value block with:

```text
cli_status: <syntax_error|unrealizable|realizable|synthesized|timeout|unknown>
repair_loops: <number>
syntax_repair_loops: <number>
unrealizable_repair_loops: <number>
well_separation_repair_loops: <number>
independent_test_repair_loops: <number>
timeout_seconds: <number>
used_counter_strategy: <true|false>
used_unrealizable_core: <true|false>
unrealizable_core_file: <path or none>
unrealizable_core_size: <number or none>
unrealizable_core_lines: <JSON array of line numbers, or []>
well_separation_status: <well_separated|non_well_separated|not_checked|unknown>
blocked_by_nl_conflict: <true|false>
test_feedback_decision: <none|rejected_invalid_test|repaired|blocked_by_nl_conflict>
invalid_test_names: <JSON array of rejected test names, or []>
invalid_test_reason: <short reason or none>
diagnostic_file: <path or none>
well_separation_file: <path or none>
spectra_file: <path>
controller_output_dir: <path or none>
artifact_dir: <path>
repair_log_file: <path>
```
