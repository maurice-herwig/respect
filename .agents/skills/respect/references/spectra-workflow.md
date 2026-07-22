# Spectra Workflow Reference

## Use This Reference For

- Converting free-form reactive-system requirements into a first Spectra draft
- Interpreting `spectra-cli.jar` results
- Repairing parser errors without drifting away from the user's intent
- Using counter-strategy diagnostics to repair unrealizable drafts

## Drafting Guidance

- Start with one named `spec`.
- Declare environment variables with `env` and system variables with `sys`.
- Encode assumptions with `asm` and guarantees with `gar`.
- Prefer a minimal complete model over speculative features.
- Prefer the simplest Spectra construct that directly expresses the requirement.
- Use advanced constructs such as `counter`, `monitor`, `pattern`, `regexp`, quantifiers, aggregates, and triggers only when the natural-language description clearly calls for them or they materially simplify the specification.
- If the description leaves key semantics unstated, make the smallest explicit assumption and report it.

## Validation And Synthesis Branches

Use this check command:

```bash
java -jar spectra-cli.jar -i <path-to-file>
```

Observed CLI result patterns in this repo:

- Realizable: `Result: Specification is realizable`
- Unrealizable: `Result: Specification is unrealizable`
- Syntax failure: `Error: Could not prepare game input from Spectra file`

Use this synthesis command only after a realizable result:

```bash
java -jar spectra-cli.jar -i <path-to-file> -s -o <output-dir>
```

Observed synthesis success pattern:

- `Result: Successfully synthesized a just-in-time controller in output folder`

## Counter-Strategy Diagnostics

The current CLI exposes:

```bash
java -jar spectra-cli.jar -i <path-to-file> --counter-strategy
java -jar spectra-cli.jar -i <path-to-file> --counter-strategy-jtlv-format
```

Use these only after the normal check reports `Result: Specification is unrealizable`.

Read the counter-strategy as an environment-winning behavior that demonstrates why the system cannot force its guarantees. It is diagnostic evidence, not a target behavior to copy.

## Syntax-Repair Loop

1. Save the draft as a `.spectra` file.
2. Run the CLI.
3. If parsing fails, extract the parser message, for example `missing ';' at 'gar'`.
4. Repair the file with the smallest syntax-preserving edit.
5. Repeat until the file is syntactically valid or the attempt budget is exhausted.

## Unrealizability-Repair Loop

1. Run the CLI and confirm the specification is syntactically valid but unrealizable.
2. Request a counter-strategy diagnostic.
3. Identify a likely conflict between assumptions, guarantees, initial conditions, safety, liveness, or update rules.
4. Compare any candidate repair against the natural-language description.
5. Apply the candidate only when it is consistent with the description.
6. Re-run the normal CLI check.
7. Stop after 3 unrealizability-repair attempts or when all plausible repairs would contradict the description.

Common repair patterns:

- Add a missing environment assumption only when the description says the environment is constrained.
- Repair an initial condition that conflicts with an immediate response requirement.
- Replace an accidental always-immediate response with a next-step response if the description allows delayed reaction.
- Remove an over-specific liveness condition only when the description does not require that recurrence.

Common invalid repairs:

- Deleting a stated guarantee solely to make synthesis succeed.
- Adding an assumption that forbids inputs the description explicitly permits.
- Weakening "must always" into "may sometimes" without textual support.
- Ignoring a named input/output or changing control ownership.

## Useful Local Sources

Use these files only as syntax and idiom references. Do not copy their behavior unless the natural-language requirements call for the same behavior, and do not use them as semantic or benchmark oracles.

- `assets/examples/A1_firstController/TrafficA1.spectra`
- `assets/examples/A2_unrealizability/TrafficA2b.spectra`
- `assets/examples/L1_firstSpec_solution/`
- `assets/examples/L2_defsArrays_solution/`
- `assets/examples/L3_patterns_solution/`
- `assets/examples/L4_triggers_solution/`
- `assets/examples/UserGuideSpecs/Blink5.spectra`
- `assets/examples/UserGuideSpecs/Rover.spectra`
- `assets/examples/LanguageFeatures/`
