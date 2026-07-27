---
name: respect
description: Primary ReSpect agent for the study. Generate Spectra specifications from natural-language requirements using the repository Spectra Xtext grammar at assets/grammar/Spectra.xtext as initial syntax guidance, validate with spectra-cli.jar, repair unrealizability with CLI counter-strategy and unrealizable-core diagnostics, check and repair well-separation before synthesis, and after successful synthesis create and run NL-guided controller tests with controller_tests. Repair generated Spectra only when CLI/test feedback indicates a problem and the repair is consistent with the natural-language description. Do not compare against source Spectra files or benchmark oracles.
---

# ReSpect: Grammar-Guided CLI-Diagnosed Repair With NL-Guided Controller Tests

## Research Role

This skill implements the primary ReSpect reconstruction condition:

- Input: natural-language requirements for a reactive system.
- Output: a generated Spectra specification plus CLI validation, diagnosis, synthesis, test, and repair results.
- Initial syntax reference: `assets/grammar/Spectra.xtext`.
- Feedback sources: `spectra-cli.jar` realizability/synthesis/well-separation output, CLI counter-strategy and unrealizable-core diagnostics for unrealizable specifications, and NL-guided controller tests from `controller_tests`.
- Allowed repair signal: parser output, realizability status, well-separation status, counter-strategy output, unrealizable-core output, controller-test failures, failing traces, generated Spectra, and the natural-language description.
- Not allowed: reading or comparing against the original/reference Spectra file, semantic equivalence checks against the benchmark, mutation checks, or oracle-based tests.

The goal is to measure whether CLI diagnostics plus NL-guided bounded controller tests improve reconstruction while avoiding leakage from the original specification.

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
5. Initialize `repair_loops = 0`, `syntax_repair_loops = 0`, `unrealizable_repair_loops = 0`, `well_separation_repair_loops = 0`, and `test_repair_loops = 0`.
6. Run `scripts/run_spectra_cli.py` on the saved file with an explicit timeout.
7. If the result is `syntax_error`, inspect the parser message, increment both `repair_loops` and `syntax_repair_loops`, repair only the syntax, and rerun validation.
8. After the syntax-repair phase ends and the run moves to the next phase, save the stable repaired specification as `specs/01_after_syntax_repair.spectra` and append one transition record to `repair_log.jsonl`.
9. Limit syntax-repair loops to at most 3 attempts and report the last parser error if repair still fails.
10. If the result is `timeout`, report the timeout and do not continue.
11. If the result is `unrealizable`, request CLI diagnostics with `--counter-strategy` and save the diagnostic JSON, then request `--unrealizable-core` and save the core diagnostic JSON.
12. Analyze the counter-strategy, the unrealizable core, and the natural-language description before changing the specification. Use the core only to localize guarantees participating in an unrealizability conflict; do not treat it as a deletion list.
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
25. If the well-separation result is `well_separated`, run synthesis. If synthesis succeeds, set `cli_status = synthesized` and continue to NL-guided controller tests.
26. After every successful synthesis, create a controller test plan from the natural-language description, generated Spectra, and synthesized controller metadata.
27. Run the test plan with `controller_tests`.
28. If all tests pass, report the passing test counts and test result file.
29. If tests fail, inspect each failing test name, reason, and trace. Decide whether the test is actually justified by the natural-language description.
30. If a failing test is too strong, underspecified, or not supported by the natural-language description, revise or remove that test and rerun the test plan without changing Spectra.
31. If a failing test is justified by the natural-language description, minimally repair the generated Spectra, increment both `repair_loops` and `test_repair_loops`, rerun CLI validation, rerun well-separation when realizable, rerun synthesis, create a fresh test plan, and rerun tests.
32. After the test-repair phase ends and the tests are rerun or the run stops, save the stable repaired specification as `specs/04_after_test_repair.spectra` and append one transition record to `repair_log.jsonl`.
33. Limit test-repair loops to at most 3 attempts.
34. Save the final Spectra version as `final.spectra`. Always include the final ReSpect result fields in the response.

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
    04_after_test_repair.spectra
  diagnostics/
    unrealizable-<n>.json
    unrealizable-core-<n>.json
    well-separation-<n>.json
  tests/
    test-plan-<n>.rtest
    test-plan-<n>.json
    test-results-<n>.json
  final.spectra
  repair_log.jsonl
```

- Save only stable Spectra versions at phase boundaries: the initial draft, the specification that leaves each repair phase, and the final specification. Do not save every intermediate failed repair attempt inside a loop unless it is also the final state.
- Omit phase-specific spec files and repair-log entries for phases that did not run. For example, if no test repair was attempted, do not create `specs/04_after_test_repair.spectra`.
- Keep `final.spectra` as a copy of the last stable Spectra version and report `spectra_file` as that path.
- Append one JSON object per phase transition to `repair_log.jsonl`.
- Use this `repair_log.jsonl` schema consistently for ReSpect runs:

```json
{
  "version": "02_after_unrealizable_repair",
  "phase": "unrealizable_repair",
  "input_spec": "specs/01_after_syntax_repair.spectra",
  "output_spec": "specs/02_after_unrealizable_repair.spectra",
  "trigger": "unrealizable",
  "result_before": "unrealizable",
  "result_after": "synthesized",
  "repair_loops_total": 2,
  "syntax_repair_loops": 1,
  "unrealizable_repair_loops": 1,
  "well_separation_repair_loops": 0,
  "test_repair_loops": 0,
  "broker_repair_loops": 0,
  "diagnostic_files": ["diagnostics/unrealizable-1.json", "diagnostics/unrealizable-core-1.json"],
  "notes": "Minimal NL-consistent repair summary."
}
```

- Save the JSON output of each counter-strategy wrapper call as `diagnostics/unrealizable-<n>.json`. The actual counter-strategy text is preserved inside that JSON object's `raw_output` field.
- Save the JSON output of each unrealizable-core wrapper call as `diagnostics/unrealizable-core-<n>.json`. The reported `unrealizable_core_lines` identify source lines for guarantees in one locally minimal unrealizable core. Treat these lines as localization evidence, not as permission to remove or weaken the guarantees.
- Save the JSON output of each well-separation wrapper call as `diagnostics/well-separation-<n>.json`. The actual CLI text is preserved inside that JSON object's `raw_output` field.
- Save controller test DSL files as `tests/test-plan-<n>.rtest`.
- Compile each DSL file to `tests/test-plan-<n>.json` before running the Java test runner.
- Save DSL compiler diagnostics as `tests/dsl-diagnostics-<n>-<attempt>.json` when compilation fails or when a repair loop is used.
- Save controller test results as `tests/test-results-<n>.json`.
- Keep the final `.spectra` file and synthesis output long enough for inspection.
- Do not overwrite unrelated files.

## Validation Commands

Use the bundled wrapper instead of calling the jar directly:

```bash
python .agents/skills/respect/scripts/run_spectra_cli.py --input <path-to-file> --timeout 120
```

For counter-strategy diagnostics after an `unrealizable` result:

```bash
python .agents/skills/respect/scripts/run_spectra_cli.py --input <path-to-file> --counter-strategy --timeout 120
```

For unrealizable-core diagnostics after an `unrealizable` result:

```bash
python .agents/skills/respect/scripts/run_spectra_cli.py --input <path-to-file> --unrealizable-core --timeout 120
```

For well-separation after a `realizable` result and before synthesis:

```bash
python .agents/skills/respect/scripts/run_spectra_cli.py --input <path-to-file> --well-separation --timeout 120
```

The wrapper returns `status = well_separated` or `status = non_well_separated`. The underlying CLI returns exit code 0 for both outcomes, so use the normalized `status`, not the process exit code, to branch.

Use JTLV text format only if the default counter-strategy output is not useful:

```bash
python .agents/skills/respect/scripts/run_spectra_cli.py --input <path-to-file> --counter-strategy-jtlv-format --timeout 120
```

For synthesis after a `realizable` result:

```bash
python .agents/skills/respect/scripts/run_spectra_cli.py --input <path-to-file> --synthesize --output-dir <path-to-output-dir> --timeout 120
```

## Controller Test Commands

Build the Java test library before the first test run in a task:

```powershell
javac -cp assets\examples\E2_execution\executor.jar -d controller_tests\build\classes (Get-ChildItem controller_tests\src\main\java -Recurse -Filter *.java).FullName
```

Run a test plan:

```powershell
java "-Djava.library.path=." -cp "controller_tests\build\classes;assets\examples\E2_execution\executor.jar" respect.controller_tests.TestRunner --plan <test-plan.json> --output <test-results.json>
```

On Linux/macOS use `:` instead of `;` in the Java classpath and adjust the native library path for CUDD if needed.

The test plan's `controller_dir` must point at the synthesized JIT folder, usually `<controller_output_dir>/jit`. The `spec_name` must match the `spec` name in the generated Spectra file.

Compile a controller-test DSL file before running it:

```powershell
python controller_tests\compile_test_plan.py <test-plan.rtest> -o <test-plan.json>
```

For DSL repair feedback:

```powershell
python controller_tests\compile_test_plan.py <test-plan.rtest> --check --diagnostics-json <dsl-diagnostics.json>
```

Use `--strict-files` only after the generated Spectra file and synthesized JIT controller directory are expected to exist.

## ReSpect Boundaries

- Use only the natural-language description, generated Spectra, CLI outputs, synthesized controller metadata, and controller-test outputs as repair evidence.
- Use `assets/grammar/Spectra.xtext` as a syntax reference, not as semantic feedback or a repair oracle.
- Do not open `source_spectra_file`, accepted dataset files, HOA exports, distance results, or benchmark fixtures for the current instance.
- Do not make a specification realizable by deleting stated requirements without a natural-language justification.
- Do not weaken a guarantee merely because it appears in the counter-strategy; first decide whether the weaker behavior is allowed by the description.
- Do not add environment assumptions that shift responsibility to the environment unless the description states or strongly implies that assumption.
- Do not generate tests from the original/reference Spectra file.
- Do not treat a failed test as proof that Spectra is wrong until checking whether the test is actually supported by the natural-language description.

## Unrealizability Repair Rules

- Treat the counter-strategy as diagnostic evidence, not as permission to rewrite the task.
- Treat the unrealizable core as diagnostic localization evidence, not as permission to delete, weaken, or ignore the reported guarantees.
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

## NL-Guided Controller Test Planning

After successful synthesis, generate a controller-test DSL file for `controller_tests` and compile it to JSON. Use only the natural-language description, the generated Spectra file, and the synthesized controller location.

Prefer the `.rtest` DSL over writing JSON directly. The JSON file is an execution artifact produced by `controller_tests/compile_test_plan.py`.

If the DSL compiler reports `dsl_syntax_error`, repair only the `.rtest` file:

1. Read the diagnostics JSON, especially `errors[0].code`, `message`, `hint`, and `context`.
2. Treat semantic plan errors such as `unknown_variable`, `wrong_variable_owner`, `conflicting_exploration_fields`, and `invalid_bound` as test-plan problems, not Spectra problems.
3. Compare the intended tests against the natural-language description.
4. Fix only DSL syntax or test-plan structure. Do not change the generated Spectra file.
5. Do not add tests that are not justified by the natural-language description.
6. Save the repaired `.rtest` as the next attempt and rerun the compiler.
7. Limit DSL repair to at most 3 attempts.
8. If the DSL still does not compile, report the final diagnostics and do not run Java controller tests.

Required top-level `.rtest` fields:

```text
controller_dir <controller-output-dir>/jit
spec_name <SpectraSpecName>
spectra_file <generated-spectra-file>
environment <comma-separated environment inputs>
system <comma-separated system outputs>
```

Example `.rtest` tests:

```text
test declared_variables:
  kind variable_ownership

test never_both_green:
  kind exclusion
  trace:
    carA=true, carB=false
    carA=false, carB=true
  forbidden greenA=true, greenB=true

test exhaustive_never_both_green:
  kind exclusion
  mode exhaustive
  max_depth 4
  max_paths 256
  domains:
    carA false, true
    carB false, true
  forbidden greenA=true, greenB=true
```

Supported test kinds:

- `variable_ownership`: use when the description identifies environment-controlled inputs and system-controlled outputs.
- `initial_condition`: use when the description states initial output or state requirements.
- `exclusion`: use for safety requirements saying that a combination must never happen.
- `always_implication`: use for immediate safety rules of the form "whenever A, B must hold in the same step".
- `eventually_response`: use for bounded evidence of response/liveness rules, but choose conservative bounds and do not overstate unbounded liveness.

Supported execution modes for controller tests:

- `trace`: use for concrete scenarios directly described in the natural language.
- `random`: use for lightweight exploration of environment domains.
- `exhaustive`: use for small Boolean or finite-domain inputs with low depth.

Default bounds:

- `max_depth <= 6`
- `max_paths <= 256`
- `runs <= 50`
- `within_steps <= 10` unless the natural-language description gives a different bound.

Test-plan rules:

- Include `requirement "<natural-language requirement>"` in every runtime test. The requirement must quote or closely paraphrase the natural-language description and justify the test.
- Do not include a test if no natural-language requirement justifies it.
- Include top-level `environment` and `system`. The DSL compiler uses `system` to produce the JSON `outputs` field so the harness reads only system-controlled outputs.
- Include `spectra_file`, `controller_dir`, and `spec_name`.
- Use finite environment domains, e.g. `"carA": ["false", "true"]`.
- Do not create a test that is stronger than the natural-language description. For example, "eventually green" does not imply "green immediately".
- Prefer a small set of tests that are clearly justified by the natural-language description over many speculative tests.

## Test Failure Repair Rules

When a controller test fails:

1. Read the test result JSON, especially `name`, `kind`, `reason`, `trace`, and `details`.
2. Use `details.failure_code` and fields such as `actual_combined`, `missing_or_different`, `trace_index`, and `step_index` to diagnose the failure.
3. Compare the failed test's `requirement` field against the natural-language description.
4. If the `requirement` field is missing, too vague, or not supported by the natural-language description, repair or remove the test instead of changing Spectra.
5. If the test is not justified by the description, revise or remove the test and rerun tests. Do not change Spectra for an invalid test.
6. If the test is justified, identify the minimal Spectra change needed to satisfy the description.
7. Apply the repair, increment `test_repair_loops`, rerun CLI validation, rerun synthesis, write a fresh test plan, and rerun tests.
8. Stop after 3 test-repair attempts.
9. If tests still fail, report the last failure and whether the remaining issue appears to be a generated-Spectra problem or a test-plan uncertainty.

## Final Response Format

For study runs, keep the final response compact and include:

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
diagnostic_file: <path or none>
well_separation_file: <path or none>
test_plan_file: <path or none>
test_result_file: <path or none>
tests_total: <number>
tests_passed: <number>
tests_failed: <number>
spectra_file: <path>
controller_output_dir: <path or none>
artifact_dir: <path>
repair_log_file: <path>
```

## Bundled Resources

- `scripts/run_spectra_cli.py`: Run `spectra-cli.jar`, normalize the outcome, optionally request counter-strategy or unrealizable-core diagnostics, and preserve raw output.
- `references/spectra-workflow.md`: Spectra examples, CLI result patterns, and drafting/repair guidance.
- `assets/examples/LanguageFeatures/`: Compact `.spectra` syntax examples for less common Spectra language constructs.
- `assets/grammar/Spectra.xtext`: Repository-level Xtext grammar for Spectra syntax. Read this before drafting generated specifications.
- `controller_tests/`: Java test library used after synthesis for NL-guided bounded controller tests.
