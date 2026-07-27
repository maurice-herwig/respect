# Spectra CLI with Unrealizable Core

This folder contains a runnable Spectra CLI JAR that can compute an unrealizable core for a Spectra specification.

## File

```text
spectra-cli-with-un-core.jar
```

Copy this JAR into the project where your `.spectra` files live.

## Usage

From the folder containing the JAR, run:

```bash
java -jar spectra-cli-with-un-core.jar -i path/to/spec.spectra --unrealizable-core
```

The British spelling is also supported:

```bash
java -jar spectra-cli-with-un-core.jar -i path/to/spec.spectra --unrealisable-core
```

## Expected Output

For an unrealizable specification, the CLI prints the core size and the source lines that belong to the core:

```text
Result: Found unrealizable core with 2 guarantees, at lines < 5 8 >
At line 5 is a behavior of kind <Simple GR(1)> and type <Safety>
At line 8 is a behavior of kind <Simple GR(1)> and type <Justice>
```

For a realizable specification, no core is computed:

```text
Error: Cannot compute unrealizable core for a realizable specification
```

The CLI may print additional CUDD/GR1 diagnostic lines before the final result. The relevant result line starts with `Result:` or `Error:`.

## Native Library Note

The JAR contains the CUDD native library required for unrealizable-core computation. On Windows, the CLI extracts `cudd.dll` into the current working directory when it starts. This file may remain after the command exits because Windows can keep native DLLs locked until process shutdown. It is safe to leave it there.

## Tested Commands

The JAR was tested with Spectra models from this repository:

```bash
java -jar spectra-cli-with-un-core.jar -i tau.smlab.syntech.Spectra.cli.tests/models/SimpleUnrealizableCore.spectra --unrealizable-core
java -jar spectra-cli-with-un-core.jar -i tau.smlab.syntech.Spectra.cli.tests/models/SimpleUnrealizableCore.spectra --unrealisable-core
java -jar spectra-cli-with-un-core.jar -i tau.smlab.syntech.Spectra.cli.tests/models/Realizable.spectra --unrealizable-core
java -jar spectra-cli-with-un-core.jar -i tau.smlab.syntech.Spectra.cli.tests/models/Unrealizable.spectra --unrealizable-core
```

The minimal unrealizable test model produced a core with exactly two guarantees at lines 5 and 8.
