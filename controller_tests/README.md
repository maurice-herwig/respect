# ReSpect Controller Tests

Java test library for method-3 controller checks.

The library executes synthesized Spectra JIT controllers through Syntech's
`ControllerExecutor` and checks bounded, natural-language-derived properties.

## Build

From the repository root:

```powershell
javac -cp assets\examples\E2_execution\executor.jar -d controller_tests\build\classes (Get-ChildItem controller_tests\src\main\java -Recurse -Filter *.java).FullName
```

## Run

```powershell
java -cp "controller_tests\build\classes;assets\examples\E2_execution\executor.jar" respect.controller_tests.Method3TestRunner --plan controller_tests\examples\traffic_e2_plan.json
```

On Linux/macOS use `:` instead of `;` in the classpath.

The controller directory in the plan must point at the synthesized JIT folder,
for example `<controller_output_dir>/jit`.

## Test Plan Format

```json
{
  "controller_dir": "path/to/controller/jit",
  "spec_name": "TrafficE2",
  "spectra_file": "path/to/generated.spectra",
  "tests": [
    {
      "kind": "variable_ownership",
      "name": "declared_variables",
      "env": ["carA", "carB"],
      "sys": ["greenA", "greenB"]
    },
    {
      "kind": "exclusion",
      "name": "never_both_green",
      "trace": [
        {"carA": "true", "carB": "false"},
        {"carA": "false", "carB": "true"}
      ],
      "forbidden": {"greenA": "true", "greenB": "true"}
    }
  ]
}
```

Supported `kind` values:

- `variable_ownership`: static check over the generated Spectra file.
- `initial_condition`: checks outputs after `initState`.
- `exclusion`: fails if a forbidden valuation appears at any step.
- `always_implication`: whenever `when` matches, `then` must match in the same step.
- `eventually_response`: whenever `when` matches, `eventually` must match within `within_steps`.

All controller tests are bounded trace tests. They are evidence for semantic
quality, not full equivalence proofs.
