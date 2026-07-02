---
name: respect-method-2.1
description: Method 2.1 agent for the ReSpect study. Generate Spectra specifications from natural-language requirements using the repository Spectra Xtext grammar at assets/grammar/Spectra.xtext as initial syntax guidance, save them as temporary .spectra files, validate executability with spectra-cli.jar, repair only CLI-reported syntax errors, check realizability, and synthesize a controller when the specification is realizable. Do not run additional semantic tests, equivalence checks, counterexample-guided tests, or benchmark-specific test suites unless the user explicitly asks for a different method.
---

# ReSpect Method 2.1: Grammar-Guided CLI-Validated Spectra Synthesis

## Research Role

This skill implements the method 2.1 agent condition in the ReSpect study:

- Input: natural-language requirements for a reactive system.
- Output: a generated Spectra specification plus CLI validation results.
- Initial syntax reference: `assets/grammar/Spectra.xtext`.
- Feedback source: `spectra-cli.jar` only.
- Allowed repair signal: parser/CLI output from the generated Spectra file.
- Not allowed for this method: additional tests, semantic equivalence checks, generated test cases, mutation checks, benchmark-specific oracle checks, counter-strategy analysis, or well-separation analysis.

The goal is to measure the benefit of CLI-based executability feedback over a simple non-tool baseline while keeping it clearly separate from the third, test-enhanced agent.

## Workflow

1. Read `references/spectra-workflow.md` before drafting a new specification.
2. Read `assets/grammar/Spectra.xtext` before drafting, and use it only as syntax guidance for valid Spectra constructs.
3. Translate the user's free-form description into a complete Spectra specification.
4. Save the draft to a temporary `.spectra` file before validation.
5. Initialize `repair_loops` to `0`.
6. Run `scripts/run_spectra_cli.py` on the saved file with an explicit timeout.
7. If the result is `syntax_error`, inspect the parser message, increment `repair_loops`, repair the file with the LLM, and run the check again.
8. Limit syntax-repair loops to at most 3 attempts and report the last parser error if repair still fails.
9. If the result is `timeout`, report the timeout and do not continue to synthesis.
10. If the result is `unrealizable`, report that no controller can be synthesized for the current specification. Give only a concise LLM-inferred explanation grounded in the specification and CLI result.
11. If the result is `realizable`, run synthesis and return the controller output path.
12. Always include the final method-2.1 result fields in the response: `cli_status`, `repair_loops`, `timeout_seconds`, `spectra_file`, and `controller_output_dir` if synthesis succeeded.

## Temporary File Handling

- Create a temporary working directory under the repository root, for example `tmp/spectra-runs/<timestamp>-<slug>/`.
- Save the generated specification as `<name>.spectra`.
- Keep the final `.spectra` file and synthesis output long enough for the user to inspect the artifacts.
- Do not overwrite unrelated files.

## Validation Command

Use the wrapper script instead of calling the jar directly when possible:

```bash
python .agents/skills/respect-method-2.1/scripts/run_spectra_cli.py --input <path-to-file> --timeout 120
```

For synthesis:

```bash
python .agents/skills/respect-method-2.1/scripts/run_spectra_cli.py --input <path-to-file> --synthesize --output-dir <path-to-output-dir> --timeout 120
```

The wrapper uses a default timeout of 120 seconds. Override it when needed:

```bash
python .agents/skills/respect-method-2.1/scripts/run_spectra_cli.py --input <path-to-file> --timeout <seconds>
```

The wrapper prints JSON with a normalized `status` field and preserves the raw CLI output for diagnosis.

## Method 2 Boundaries

- Use only the Spectra CLI wrapper for validation feedback.
- Use `assets/grammar/Spectra.xtext` as a syntax reference, not as semantic feedback or a repair oracle.
- Do not run custom tests over traces, generated controllers, or benchmark oracles.
- Do not compare the generated Spectra file against an original/reference Spectra file.
- Do not use counter-strategy generation, well-separation checks, or additional CLI analysis modes unless the user explicitly switches away from method 2.
- Do not rewrite a syntactically valid but unrealizable specification to make it realizable unless the user explicitly asks for repair beyond method 2 evaluation.

## Repair Rules

- Treat the parser output as authoritative for syntax errors.
- Start with `repair_loops = 0` for each new generated specification.
- Increment `repair_loops` once per attempted LLM repair after a `syntax_error` result.
- Preserve the user's intended behavior when repairing syntax; prefer minimal edits over semantic rewrites.
- After each repair, re-save the `.spectra` file and rerun validation.
- Stop after 3 repair attempts.
- If the model must make a semantic assumption to finish the specification, state that assumption explicitly.
- Include `repair_loops` in the final answer even when it is `0`.

## Unrealizability Guidance

- Distinguish syntax problems from unrealizability; unrealizable specifications are syntactically valid.
- Base the explanation on conflicting guarantees, impossible liveness demands, missing environment assumptions, or safety constraints that block required progress.
- Make clear that the justification is an LLM analysis informed by the specification and CLI result, not a proof emitted by the jar.

## Synthesis Output

- Only synthesize after a realizable result.
- Store controller artifacts in a dedicated output directory inside the temporary run folder.
- Report the generated artifact paths back to the user.

## Final Response Format

For study runs, keep the final response compact and include:

```text
cli_status: <syntax_error|unrealizable|realizable|synthesized|timeout|unknown>
repair_loops: <number>
timeout_seconds: <number>
spectra_file: <path>
controller_output_dir: <path or none>
```

## Bundled Resources

- `scripts/run_spectra_cli.py`: Run `spectra-cli.jar`, normalize the outcome, and surface the raw output.
- `references/spectra-workflow.md`: Spectra examples, CLI result patterns, and drafting guidance.
- `assets/grammar/Spectra.xtext`: Repository-level Xtext grammar for Spectra syntax. Read this before drafting generated specifications.
