---
name: respect-self-test-from-core
description: ReSpect self-test branch for branched experiments. Start from an existing core_final.spectra plus full core context, synthesize or reuse the controller, write and run NL-guided controller_tests, and repair the Spectra only when self-generated test failures are justified by the natural-language requirements.
---

# ReSpect Self-Test From Core

## Research Role

This skill implements the self-test branch after a shared core reconstruction:

- Input: natural-language requirements, fixed environment/system signature, `core_final.spectra`, `core_context.full.json`, and controller metadata when available.
- Output: branch Spectra files, controller-test plans/results, CLI diagnostics, synthesis output, repair counts, and final branch artifacts.
- Feedback sources: generated Spectra, full core context, parser/realizability/well-separation/synthesis output, and self-generated NL-guided bounded controller tests.
- Not allowed: reading source/reference Spectra files, benchmark oracles, mutation checks, equivalence checks, distance results, independent test-writer outputs, or cross-broker feedback.

The goal is to measure the effect of self-generated controller tests from the same `core_final.spectra` incumbent used by other branches.

## Workflow

1. Read `assets/grammar/Spectra.xtext`, `.agents/skills/respect-self-test-from-core/references/spectra-workflow.md`, and `controller_tests/DSL.md`.
2. Read the fixed signature, `core_final.spectra`, and `core_context.full.json` supplied by the prompt.
3. Copy `core_final.spectra` to `specs/00_from_core.spectra`. This is the branch parent. Do not redraft from scratch.
4. Initialize branch counters: `repair_loops = 0`, `syntax_repair_loops = 0`, `unrealizable_repair_loops = 0`, `well_separation_repair_loops = 0`, and `test_repair_loops = 0`.
5. Validate `specs/00_from_core.spectra` with `.agents/skills/respect-self-test-from-core/scripts/run_spectra_cli.py --input <file> --timeout 120`.
6. If the copied core file is not valid, repair only the minimal issue needed to restore the core semantics, then rerun validation. Record this as a branch repair.
7. Run well-separation when realizable and synthesize a controller if no usable controller directory was supplied or if the Spectra file changed.
8. Create a controller-test plan from the natural-language description, fixed signature, generated Spectra, and synthesized controller metadata.
9. Save controller-test DSL files as `tests/test-plan-<n>.rtest`, compile them to JSON, and run the Java controller-test runner.
10. If all tests pass, save `final.spectra` as the current branch Spectra and report.
11. If tests fail, inspect each failing test name, requirement, reason, trace, and `details.failure_code`.
12. If a failing test is unsupported, too strong, underspecified, or has a plan problem, repair or remove the test and rerun tests without changing Spectra.
13. If a failing test is justified by the natural-language requirements, minimally repair Spectra, increment `repair_loops` and `test_repair_loops`, rerun validation, well-separation, synthesis, and tests.
14. Save the stable post-test-repair specification as `specs/04_after_self_test_repair.spectra` when this phase completes.
15. Stop after at most the feedback-round limit supplied by the prompt, defaulting to 3 if omitted.

Do not create `specs/00_initial.spectra` in this branch. The starting artifact is always `specs/00_from_core.spectra`.

## Artifact Layout

Use the run directory supplied in the prompt:

```text
<run-dir>/
  specs/
    00_from_core.spectra
    04_after_self_test_repair.spectra
  diagnostics/
    well-separation-<n>.json
  synthesis/
  tests/
    test-plan-<n>.rtest
    test-plan-<n>.json
    test-results-<n>.json
  final.spectra
  repair_log.jsonl
```

Omit phase-specific files for phases that did not run. Append one JSON object per branch phase transition to `repair_log.jsonl`.

## Final Response Format

Return a final JSON object or key-value block with:

```text
cli_status: <syntax_error|unrealizable|realizable|synthesized|timeout|unknown>
repair_loops: <number>
syntax_repair_loops: <number>
unrealizable_repair_loops: <number>
well_separation_repair_loops: <number>
test_repair_loops: <number>
timeout_seconds: <number>
used_counter_strategy: <true|false>
used_unrealizable_core: <true|false>
unrealizable_core_file: <path or none>
unrealizable_core_size: <number or none>
unrealizable_core_lines: <JSON array of line numbers, or []>
well_separation_status: <well_separated|non_well_separated|not_checked|unknown>
blocked_by_nl_conflict: <true|false>
test_plan_file: <path or none>
test_result_file: <path or none>
tests_total: <number>
tests_passed: <number>
tests_failed: <number>
spectra_file: <path>
controller_output_dir: <path or none>
artifact_dir: <path>
repair_log_file: <path>
parent_spectra_file: <path>
```
