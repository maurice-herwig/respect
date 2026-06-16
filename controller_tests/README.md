# ReSpect Controller Tests

Java test library for method-3 controller checks.

The library executes synthesized Spectra JIT controllers through Syntech's
`ControllerExecutor` and checks bounded, natural-language-derived properties.

Workflow overview: [`controller_test_workflow.svg`](controller_test_workflow.svg)

## Build

From the repository root:

```powershell
javac -cp assets\examples\E2_execution\executor.jar -d controller_tests\build\classes (Get-ChildItem controller_tests\src\main\java -Recurse -Filter *.java).FullName
```

## Run

First synthesize the example JIT controller if `assets/examples/E2_execution/out/jit`
does not exist:

```powershell
python .agents\skills\respect-method-3\scripts\run_spectra_cli.py --input assets\examples\E2_execution\TrafficE2.spectra --synthesize --output-dir assets\examples\E2_execution\out --timeout 120
```

```powershell
java "-Djava.library.path=." -cp "controller_tests\build\classes;assets\examples\E2_execution\executor.jar" respect.controller_tests.Method3TestRunner --plan controller_tests\examples\traffic_e2_plan.json
```

On Linux/macOS use `:` instead of `;` in the classpath.

If Java reports `ClassNotFoundException: respect.controller_tests.Method3TestRunner`,
run the build command first; `controller_tests/build/classes` is generated and is
not committed.

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
  Set `require_closed_obligations` to `true` if a trace ending with an open
  response obligation should fail. The default is `false`, which avoids failing
  merely because a bounded trace ends before an unexpired deadline.

Controller tests support three execution modes:

- `trace`: execute the explicit `trace` array from the test plan.
- `random`: generate `runs` random traces of length `max_depth` from `env` domains.
- `exhaustive`: enumerate input traces up to `max_depth`, capped by `max_paths`.

Example exploration test:

```json
{
  "kind": "exclusion",
  "name": "never_both_green",
  "mode": "exhaustive",
  "max_depth": 4,
  "max_paths": 256,
  "env": {
    "carA": ["false", "true"],
    "carB": ["false", "true"]
  },
  "forbidden": {"greenA": "true", "greenB": "true"}
}
```

All controller tests are bounded black-box tests. They replay generated input
traces against fresh controller instances. They are evidence for semantic
quality, not full equivalence proofs.
