---
name: respect-core
description: Shared ReSpect core reconstruction skill for branched experiments. Generate a Spectra specification from natural-language requirements plus a fixed env/sys signature, validate and repair syntax/unrealizability/well-separation with spectra-cli.jar diagnostics, synthesize a controller, write full and filtered core context artifacts, and stop before any controller-test or broker-feedback phase.
---

# ReSpect Core

## Research Role

This skill implements the shared NL-to-Spectra core for branched experiments:

- Input: natural-language requirements and a fixed environment/system signature.
- Output: generated Spectra, CLI diagnostics, synthesis output, stable intermediate Spectra files, repair log, and two context artifacts for later branches.
- Feedback sources: parser/realizability/well-separation/synthesis output from `spectra-cli.jar`, counter-strategy diagnostics, and unrealizable-core diagnostics.
- Not allowed: writing controller tests, running controller tests, calling the cross broker, reading source/reference Spectra files, reading benchmark oracles, mutation checks, equivalence checks, or distance results.

The goal is to produce one shared `core_final.spectra` starting point per natural-language description.

## Workflow

1. Read `assets/grammar/Spectra.xtext` and `.agents/skills/respect/references/spectra-workflow.md` before drafting or repairing.
2. Read the fixed signature supplied by the prompt. Use exactly those environment and system variable names and ownerships.
3. Decompose the natural-language requirements into assumptions, guarantees, initial conditions, safety/update rules, liveness/justice requirements, and response/pattern requirements.
4. Draft a complete Spectra specification and save it as `specs/00_initial.spectra`.
5. Initialize `repair_loops`, `syntax_repair_loops`, `unrealizable_repair_loops`, and `well_separation_repair_loops` to `0`.
6. Validate with `.agents/skills/respect/scripts/run_spectra_cli.py --input <file> --timeout 120`.
7. Repair syntax errors for at most 3 syntax loops, then rerun validation. Save the stable post-syntax version as `specs/01_after_syntax_repair.spectra` when this phase completes.
8. If unrealizable, request `--counter-strategy`, save `diagnostics/unrealizable-<n>.json`, then request `--unrealizable-core` and save `diagnostics/unrealizable-core-<n>.json`. Repair only when consistent with the natural-language requirements. Save the stable post-unrealizable version as `specs/02_after_unrealizable_repair.spectra` when this phase completes.
9. If realizable, run `--well-separation`, save `diagnostics/well-separation-<n>.json`, repair non-well-separation only when consistent with the natural-language requirements, and save the stable post-well-separation version as `specs/03_after_well_separation_repair.spectra` when this phase completes.
10. Synthesize only after the specification is both realizable and well-separated.
11. Save the final Spectra version as `final.spectra`.
12. Write `core_context.full.json` and `core_context.test_writer.json` in the artifact directory.
13. Stop after synthesis and context writing. Do not generate `.rtest` files, run controller tests, or call the cross broker.

After every Spectra edit, return to validation before any well-separation check or synthesis.

## Context Artifacts

`core_context.full.json` is for downstream specification-repair branches. Include:

- `natural_language_summary`
- `signature`
- `final_spectra_file`
- `controller_output_dir`
- `well_separation_status`
- repair counters
- `intermediate_spectra_files`
- `diagnostic_files`
- `repair_log_file`
- concise notes about modeling decisions and unresolved ambiguities

`core_context.test_writer.json` is for independent test writing. It must not include generated Spectra contents, repair logs, diagnostic details, or modeling rationales. Include only:

- `natural_language_summary`
- `signature`
- `spec_name`
- `spectra_file` path
- `controller_dir`

The independent test writer may use `spectra_file` only as a DSL path and must not open it.

## Artifact Layout

Use the run directory supplied in the prompt:

```text
<run-dir>/
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
  core_context.full.json
  core_context.test_writer.json
  repair_log.jsonl
```

Omit phase-specific files for phases that did not run. Append one JSON object per phase transition to `repair_log.jsonl`.

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
core_context_full_file: <path>
core_context_test_writer_file: <path>
```
