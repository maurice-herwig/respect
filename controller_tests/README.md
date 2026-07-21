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
java "-Djava.library.path=." -cp "controller_tests\build\classes;assets\examples\E2_execution\executor.jar" respect.controller_tests.TestRunner --plan controller_tests\examples\traffic_e2_plan.json
```

On Linux/macOS use `:` instead of `;` in the classpath.

If Java reports `ClassNotFoundException: respect.controller_tests.TestRunner`,
run the build command first; `controller_tests/build/classes` is generated and is
not committed.

The controller directory in the plan must point at the synthesized JIT folder,
for example `<controller_output_dir>/jit`.

## DSL Test Plans

Humans and Method-3 agents should write controller tests in the `.rtest` DSL and
compile it to the JSON format consumed by the Java runner:

```powershell
python controller_tests\compile_test_plan.py controller_tests\examples\traffic_e2_plan.rtest -o controller_tests\examples\traffic_e2_plan.compiled.json
```

The complete DSL syntax and semantics are defined in [`DSL.md`](DSL.md).

Run the compiled plan:

```powershell
java "-Djava.library.path=." -cp "controller_tests\build\classes;assets\examples\E2_execution\executor.jar" respect.controller_tests.TestRunner --plan controller_tests\examples\traffic_e2_plan.compiled.json
```

Minimal `.rtest` example:

```text
controller_dir assets/examples/E2_execution/out/jit
spec_name TrafficE2
spectra_file assets/examples/E2_execution/TrafficE2.spectra
environment carA, carB
system greenA, greenB

test declared_variables:
  kind variable_ownership

test never_both_green:
  kind exclusion
  trace:
    carA=true, carB=false
    carA=false, carB=true
  forbidden greenA=true, greenB=true
```

Top-level required fields:

- `controller_dir`: synthesized JIT controller directory.
- `spec_name`: Spectra module/spec name used by the Syntech executor.
- `spectra_file`: generated Spectra file used by static checks.
- `environment`: comma-separated environment-controlled input variables.
- `system`: comma-separated system-controlled output variables.

The compiler writes `system` to the JSON `outputs` field used by the Java
runner. Old DSL files with top-level `outputs` still compile, but new plans
should use `system`.

Inside a `test <name>:` block, use `kind` plus the fields required by that test
kind. Concrete input traces are written as a `trace:` block. Random and
exhaustive exploration use a `domains:` block, which compiles to the JSON
environment-domain map:

```text
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

Validate a DSL file without writing JSON:

```powershell
python controller_tests\compile_test_plan.py path\to\plan.rtest --check
```

The existing JSON format remains the runner input and is still supported.

## JSON Test Plan Format

```json
{
  "controller_dir": "path/to/controller/jit",
  "spec_name": "TrafficE2",
  "spectra_file": "path/to/generated.spectra",
  "environment": ["carA", "carB"],
  "system": ["greenA", "greenB"],
  "outputs": ["greenA", "greenB"],
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
