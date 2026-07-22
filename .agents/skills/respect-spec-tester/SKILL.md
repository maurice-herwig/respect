---
name: respect-spec-tester
description: ReSpect specification agent for the independent-test condition. Generate and repair Spectra specifications from natural-language requirements plus a fixed env/sys signature, validate with spectra-cli.jar, repair syntax/unrealizability/well-separation, synthesize a controller, and consume independent controller-test feedback from a separate test-writer agent. Do not create controller tests yourself, do not read source Spectra files, and do not compare against benchmark oracles.
---

# ReSpect Spec Tester

## Research Role

This skill implements the specification side of the independent-test condition:

- Input: natural-language requirements, fixed environment/system signature, and optionally feedback from independently generated controller tests.
- Output: generated Spectra, CLI diagnostics, synthesis output, repair counts, and artifact paths.
- Feedback sources: parser/realizability/well-separation/synthesis output from `spectra-cli.jar`, counter-strategy diagnostics, and independent test failures supplied by the orchestrator.
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
9. If unrealizable, request `--counter-strategy`, save `diagnostics/unrealizable-<n>.json`, repair only when consistent with the natural-language requirements, then rerun validation.
10. If realizable, run `--well-separation`, save `diagnostics/well-separation-<n>.json`, repair non-well-separation only when consistent with the natural-language requirements, then rerun validation.
11. Synthesize only after the specification is both realizable and well-separated.
12. Stop after synthesis and report the final fields. Do not generate `.rtest` files or run controller tests yourself.

After every Spectra edit, return to validation before any well-separation check or synthesis.

## Independent Test Feedback

When the prompt provides a test result file:

- Read `tests_total`, `tests_passed`, `tests_failed`, each failing test's `name`, `kind`, `requirement`, `reason`, `trace`, and `details`.
- Decide whether each failure is justified by the natural-language description.
- If the test is too strong, underspecified, or unsupported, report `test_feedback_decision = rejected_invalid_test` and do not modify Spectra for that failure.
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
well_separation_status: <well_separated|non_well_separated|not_checked|unknown>
blocked_by_nl_conflict: <true|false>
test_feedback_decision: <none|rejected_invalid_test|repaired|blocked_by_nl_conflict>
diagnostic_file: <path or none>
well_separation_file: <path or none>
spectra_file: <path>
controller_output_dir: <path or none>
artifact_dir: <path>
repair_log_file: <path>
```
