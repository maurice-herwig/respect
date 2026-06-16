---
name: respect-method-3
description: Method 3 agent for the ReSpect study. Generate Spectra specifications from natural-language requirements, validate and synthesize with spectra-cli.jar like method 2, and when a syntactically valid specification is unrealizable, request CLI counter-strategy diagnostics and attempt bounded repairs only when the proposed correction does not contradict the natural-language description. Do not compare against source Spectra files or benchmark oracles.
---

# ReSpect Method 3: CLI-Diagnosed Unrealizability Repair

## Research Role

This skill implements the third ReSpect reconstruction condition in its first version:

- Input: natural-language requirements for a reactive system.
- Output: a generated Spectra specification plus CLI validation, diagnosis, repair, and synthesis results.
- Feedback sources: `spectra-cli.jar` realizability/synthesis output and CLI counter-strategy diagnostics for unrealizable specifications.
- Allowed repair signal: parser output, realizability status, counter-strategy output, and the natural-language description.
- Not allowed: reading or comparing against the original/reference Spectra file, semantic equivalence checks against the benchmark, generated benchmark-specific tests, mutation checks, or oracle-based tests.

The goal is to measure whether CLI unrealizability diagnostics improve reconstruction over method 2 while avoiding leakage from the original specification.

## Workflow

1. Read `references/spectra-workflow.md` before drafting a new specification.
2. Translate the user's natural-language description into a complete Spectra specification.
3. Save the draft to a temporary `.spectra` file before validation.
4. Initialize `repair_loops = 0`, `syntax_repair_loops = 0`, and `unrealizable_repair_loops = 0`.
5. Run `scripts/run_spectra_cli.py` on the saved file with an explicit timeout.
6. If the result is `syntax_error`, inspect the parser message, increment both `repair_loops` and `syntax_repair_loops`, repair only the syntax, and rerun validation.
7. Limit syntax-repair loops to at most 3 attempts and report the last parser error if repair still fails.
8. If the result is `timeout`, report the timeout and do not continue.
9. If the result is `realizable`, run synthesis and return the controller output path.
10. If the result is `unrealizable`, request CLI diagnostics with `--counter-strategy` and save the diagnostic JSON.
11. Analyze the counter-strategy and the natural-language description before changing the specification.
12. Repair unrealizability only if the proposed change is consistent with the natural-language description.
13. Prefer minimal repairs that preserve stated requirements: fix overly strong initialization, add environment assumptions only when implied by the description, or relax/reshape a guarantee only when the description supports the weaker form.
14. If every plausible repair would contradict the natural-language description, stop and report `blocked_by_nl_conflict = true`.
15. After each unrealizability repair, increment both `repair_loops` and `unrealizable_repair_loops`, save the file, rerun validation, and continue from the appropriate branch.
16. Limit unrealizability-repair loops to at most 3 attempts.
17. If a repaired specification becomes realizable, run synthesis and report `cli_status = synthesized`.
18. Always include the final method-3 result fields in the response.

## Temporary File Handling

- Create a temporary working directory under the repository root, for example `tmp/spectra-runs/<timestamp>-<slug>/`.
- Save the generated specification as `<name>.spectra`.
- Save each unrealizability diagnostic response as `diagnostics/unrealizable-<n>.json`.
- Keep the final `.spectra` file and synthesis output long enough for inspection.
- Do not overwrite unrelated files.

## Validation Commands

Use the bundled wrapper instead of calling the jar directly:

```bash
python .agents/skills/respect-method-3/scripts/run_spectra_cli.py --input <path-to-file> --timeout 120
```

For counter-strategy diagnostics after an `unrealizable` result:

```bash
python .agents/skills/respect-method-3/scripts/run_spectra_cli.py --input <path-to-file> --counter-strategy --timeout 120
```

Use JTLV text format only if the default counter-strategy output is not useful:

```bash
python .agents/skills/respect-method-3/scripts/run_spectra_cli.py --input <path-to-file> --counter-strategy-jtlv-format --timeout 120
```

For synthesis after a `realizable` result:

```bash
python .agents/skills/respect-method-3/scripts/run_spectra_cli.py --input <path-to-file> --synthesize --output-dir <path-to-output-dir> --timeout 120
```

The current `spectra-cli.jar` exposes counter-strategy options, but not an unrealizable-core command-line option. If an unrealizable core is unavailable from the wrapper, set `used_unrealizable_core = false` and continue with counter-strategy diagnostics only.

## Method 3 Boundaries

- Use only the natural-language description and CLI outputs as repair evidence.
- Do not open `source_spectra_file`, accepted dataset files, HOA exports, distance results, or benchmark fixtures for the current instance.
- Do not make a specification realizable by deleting stated requirements without a natural-language justification.
- Do not weaken a guarantee merely because it appears in the counter-strategy; first decide whether the weaker behavior is allowed by the description.
- Do not add environment assumptions that shift responsibility to the environment unless the description states or strongly implies that assumption.
- Do not run additional tests in this initial method-3 version.

## Unrealizability Repair Rules

- Treat the counter-strategy as diagnostic evidence, not as permission to rewrite the task.
- State the suspected conflict before editing.
- Check each proposed repair against the natural-language description:
  - `consistent`: apply the minimal edit and retry.
  - `unclear`: prefer a smaller edit or stop if the assumption would be material.
  - `contradicts`: do not apply the edit.
- Preserve all explicitly described inputs, outputs, initial conditions, safety requirements, liveness requirements, and update rules unless the description itself leaves room for the change.
- Keep a concise repair log for each unrealizability loop.

## Final Response Format

For study runs, keep the final response compact and include:

```text
cli_status: <syntax_error|unrealizable|realizable|synthesized|timeout|unknown>
repair_loops: <number>
syntax_repair_loops: <number>
unrealizable_repair_loops: <number>
timeout_seconds: <number>
used_counter_strategy: <true|false>
used_unrealizable_core: <true|false>
blocked_by_nl_conflict: <true|false>
diagnostic_file: <path or none>
spectra_file: <path>
controller_output_dir: <path or none>
```

## Bundled Resources

- `scripts/run_spectra_cli.py`: Run `spectra-cli.jar`, normalize the outcome, optionally request counter-strategy diagnostics, and preserve raw output.
- `references/spectra-workflow.md`: Spectra examples, CLI result patterns, and drafting/repair guidance.
