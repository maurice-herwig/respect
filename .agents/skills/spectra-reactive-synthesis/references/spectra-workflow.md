# Spectra Workflow Reference

## Use This Reference For

- Converting free-form reactive-system requirements into a first Spectra draft
- Interpreting `spectra-cli.jar` results
- Repairing parser errors without drifting away from the user's intent
- Explaining why a valid specification is unrealizable

## Drafting Guidance

- Start with one named `spec`.
- Declare environment variables with `env` and system variables with `sys`.
- Encode assumptions with `asm` and guarantees with `gar`.
- Prefer a minimal complete model over speculative features.
- If the user request leaves key semantics unstated, make the smallest explicit assumption and report it.

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

## Syntax-Repair Loop

1. Save the draft as a `.spectra` file.
2. Run the CLI.
3. If parsing fails, extract the parser message, for example `missing ';' at 'gar'`.
4. Repair the file with the smallest syntax-preserving edit.
5. Repeat until the file is syntactically valid or the attempt budget is exhausted.

## Realizability Guidance

The CLI reports realizability, but it does not explain the cause in a user-facing way. When a specification is unrealizable, inspect the assumptions and guarantees for patterns like:

- Guarantees that demand progress while safety rules forbid every path to that progress
- Missing environment assumptions that the system would need to fulfill liveness goals
- Multiple guarantees that cannot all hold together
- Initialization constraints that already block the required behavior
- Response guarantees over unconstrained environment inputs, especially in the initial state

Concrete pitfall: if the environment may set `pedRequest` initially, then `gar alw pedRequest -> walk;` conflicts with `gar ini !walk;` unless an assumption rules out that initial request.

State clearly when this explanation is an inference from the specification plus the CLI result.

## Example Fragments

Realizable example from this repo:

```spectra
spec TrafficA1

sys boolean greenA;
sys boolean greenB;

env boolean carA;
env boolean carB;

asm ini carA & !carB;
asm alwEv carA;
asm alwEv carB;

gar ini !greenA & !greenB;
gar alw !(greenA & greenB);
gar alw !carA -> !greenA;
gar alw !carB -> !greenB;
gar alwEv greenA;
gar alwEv greenB;
```

Unrealizable example from this repo:

```spectra
spec TrafficA2b

sys boolean greenA;
sys boolean greenB;

env boolean carA;
env boolean carB;

gar alw !(greenA & greenB);

gar alwEv carA & greenA;
gar alwEv carB & greenB;
```

## Useful Local Sources

- `assets/examples/A1_firstController/TrafficA1.spectra`
- `assets/examples/A2_unrealizability/TrafficA2b.spectra`
- `assets/examples/L1_firstSpec/`
- `assets/examples/L2_defsArrays/`
- `assets/examples/L3_patterns/`
