---
name: respect-interactive-spec
description: Interactive ReSpect specification skill for user-study condition B without controller tests. Generate and repair Spectra specifications from natural-language requirements plus a fixed or reviewed env/sys signature, validate with spectra-cli.jar, repair syntax/unrealizability/well-separation using counter-strategy and unrealizable-core diagnostics, and synthesize a controller. This is the no-test counterpart of respect-interactive-spec-tester: do not create tests, do not consume test feedback, do not read source Spectra files, and do not compare against benchmark oracles.
---

# ReSpect Spec Tester

## Interactive User-Study Delta

This skill is the no-test user-study counterpart to
`respect-interactive-spec-tester`. It follows the same Spectra drafting,
validation, repair, synthesis, and anti-oracle discipline, but omits all
controller-test and independent-test-feedback phases.

The interaction layer is:

- When the prompt names `Phase: setup`, write only the requested
  `signature.proposed.json` and `decomposition.proposed.md`, then stop. Do not
  draft Spectra and do not run validation.
- When the prompt names `Phase: draft`, read the participant-reviewed signature
  and decomposition files, write only the requested `spec.proposed.spectra`,
  then stop. Do not run validation.
- When the prompt names `Phase: validate_and_synthesize`, run the validation,
  repair, well-separation, and synthesis workflow below on the
  participant-reviewed Spectra file.
- Treat participant-reviewed files as authoritative. Use exactly the reviewed
  environment and system variable names and ownerships.

All other rules below mirror `respect-spec-tester`, except test feedback is not
available in this condition.

## Research Role

This skill implements the specification-only side of the interactive
user-study condition:

- Input: natural-language requirements and fixed environment/system signature.
- Output: generated Spectra, CLI diagnostics, synthesis output, repair counts, and artifact paths.
- Feedback sources: parser/realizability/well-separation/synthesis output from `spectra-cli.jar`, counter-strategy diagnostics, and unrealizable-core diagnostics.
- Not allowed: writing controller tests, consuming controller-test feedback, reading source/reference Spectra files, benchmark oracles, mutation checks, equivalence checks, or distance results.

The goal is to study interactive skill-guided specification writing without the TestDSL feedback source.

## Workflow

1. Read `assets/grammar/Spectra.xtext` and `.agents/skills/respect/references/spectra-workflow.md` before drafting or repairing.
2. Read the fixed signature supplied by the prompt. Use exactly those environment and system variable names and ownerships.
3. Decompose the natural-language requirements into assumptions, guarantees, initial conditions, safety/update rules, liveness/justice requirements, and response/pattern requirements.
4. If no previous generated Spectra is supplied, draft a complete Spectra specification and save it as `specs/00_initial.spectra`.
5. Initialize or preserve counters: `repair_loops`, `syntax_repair_loops`, `unrealizable_repair_loops`, and `well_separation_repair_loops`.
6. Validate with `.agents/skills/respect/scripts/run_spectra_cli.py --input <file> --timeout 120`.
7. Repair syntax errors for at most 3 syntax loops, then rerun validation.
8. If unrealizable, request `--counter-strategy`, save `diagnostics/unrealizable-<n>.json`, then request `--unrealizable-core` and save `diagnostics/unrealizable-core-<n>.json`. Analyze both diagnostics with the natural-language requirements. Use the core only to localize guarantees participating in an unrealizability conflict; do not treat it as a deletion list. Repair only when consistent with the natural-language requirements, then rerun validation.
9. If realizable, run `--well-separation`, save `diagnostics/well-separation-<n>.json`, repair non-well-separation only when consistent with the natural-language requirements, then rerun validation.
10. Synthesize only after the specification is both realizable and well-separated.
11. Stop after synthesis and report the final fields. Do not generate `.rtest` files, run controller tests, or consume test feedback.

After every Spectra edit, return to validation before any well-separation check or synthesis.

## Artifact Layout

Use the run directory supplied in the prompt:

```text
<agent-a-run-dir>/
  specs/
    00_initial.spectra
    01_after_syntax_repair.spectra
    02_after_unrealizable_repair.spectra
    03_after_well_separation_repair.spectra
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
spectra_file: <path>
controller_output_dir: <path or none>
artifact_dir: <path>
repair_log_file: <path>
```
