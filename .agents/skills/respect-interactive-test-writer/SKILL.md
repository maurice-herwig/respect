---
name: respect-interactive-test-writer
description: Interactive variant of respect-test-writer for ReSpect user studies. Use the same independent controller_tests .rtest generation and anti-leakage workflow as respect-test-writer, but save the generated test plan as a participant-reviewable proposal when the wizard asks for an interactive phase.
---

# ReSpect Test Writer

## Interactive User-Study Delta

This skill is a copy of `respect-test-writer` with only this interaction layer
added:

- When the prompt names `Phase: test_plan_proposal`, write the proposed `.rtest`
  plan to the exact requested proposal path, usually
  `tests/test-plan.proposed.rtest`, then stop.
- The wizard will copy the proposal to a reviewed file and let the participant
  inspect, edit, remove, or add tests before compilation and execution.
- Continue to obey all original `respect-test-writer` boundaries: do not read
  generated Spectra contents, source/reference Spectra files, spec-agent
  stdout/reasoning, repair logs, benchmark oracles, mutation checks,
  equivalence checks, or distance results.

All other rules below are inherited unchanged from `respect-test-writer`.

## Research Role

This skill writes independent bounded controller tests for a generated controller:

- Input: natural-language requirements, fixed environment/system signature, `spec_name`, `controller_dir`, `spectra_file` path, and output directory.
- Output: `.rtest` controller-test DSL plan plus optional DSL compile diagnostics.
- Allowed sources: the natural-language requirements, fixed signature, controller metadata, and `controller_tests/DSL.md`.
- Not allowed: reading generated Spectra contents, source/reference Spectra files, the specification agent's stdout/reasoning, repair logs, benchmark oracles, mutation checks, equivalence checks, or distance results.

The goal is to test the natural-language requirements independently of the generated implementation.

## Workflow

1. Read `controller_tests/DSL.md`.
2. Read the fixed signature from the prompt. Use exactly those environment and system variables.
3. Derive tests only from the natural-language requirements.
4. Use `spectra_file` only as a top-level DSL path. Do not open or inspect its contents.
5. Prefer adversarial tests that could expose incomplete, over-permissive, over-restrictive, wrongly initialized, or unfair controllers. Do not write only happy-path tests.
6. Include a `variable_ownership` test.
7. For every runtime test, include `requirement "<quote or close paraphrase from the NL description>"`.
8. Use bounded trace, random, or exhaustive modes with conservative bounds. Prefer `max_depth <= 6`, `max_paths <= 256`, `runs <= 50`, and `within_steps <= 10` unless the description gives a bound.
9. Save the plan as `test-plan.rtest` in the output directory supplied by the prompt.
10. If asked to compile, run `python controller_tests\compile_test_plan.py <rtest> -o <json>` and repair only DSL/test-plan issues, not Spectra.

## Test Selection

Cover each clearly testable requirement at least once:

- Ownership/signature declarations.
- Initial output requirements.
- Safety exclusions and invariants.
- Immediate implications.
- Bounded evidence for response/liveness requirements.
- Small exhaustive exploration for Boolean or small finite input domains.

Do not limit the plan to traces where the controller is expected to behave nicely. Include stress cases when supported by the natural-language requirements, such as simultaneous requests, no requests, persistent one-sided requests, alternating requests, rapid input changes, boundary enum values, and inputs that could reveal over-permissive behavior. Do not turn an unbounded liveness requirement into a hard bounded deadline unless the natural-language text gives that deadline.

If a requirement cannot be tested soundly with bounded controller tests, record it in the final response under `untestable_requirements`.

## Final Response Format

Return a final JSON object or key-value block with:

```text
test_plan_file: <path>
compiled_test_plan_file: <path or none>
dsl_diagnostics_file: <path or none>
tests_planned: <number>
untestable_requirements: <number>
artifact_dir: <path>
```
