# ReSpect Controller-Test DSL

This document defines the `.rtest` language used to write Method-3 controller
test plans. The DSL is a human- and agent-facing format. It compiles to the JSON
plan consumed by the Java controller-test runner.

Compile a DSL file:

```powershell
python controller_tests\compile_test_plan.py path\to\plan.rtest -o path\to\plan.json
```

Validate without writing JSON:

```powershell
python controller_tests\compile_test_plan.py path\to\plan.rtest --check
```

Write machine-readable diagnostics for humans or LLM repair loops:

```powershell
python controller_tests\compile_test_plan.py path\to\plan.rtest --check --diagnostics-json path\to\dsl-diagnostics.json
```

Require referenced runtime artifacts to already exist:

```powershell
python controller_tests\compile_test_plan.py path\to\plan.rtest --check --strict-files
```

## Design Goals

- Keep test plans readable for humans and LLM agents.
- Make variable ownership explicit through top-level `environment` and `system`
  declarations.
- Preserve the existing Java runner by compiling to its JSON format.
- Fail early on misspelled keys, missing fields, and unsupported test kinds.
- Keep the DSL bounded and black-box: tests execute finite controller traces and
  are not full Spectra equivalence proofs.

## File Structure

An `.rtest` file contains required top-level metadata followed by one or more
test blocks:

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

## Lexical Rules

- Files are UTF-8 text.
- Indentation uses spaces. Tabs are rejected.
- Empty lines are ignored.
- Comments start with `#` and continue to the end of the line.
- `#` inside single or double quotes is treated as part of the value.
- Statements are either `key value` or `key: value`.
- Block statements use `key:` with no value and an indented body.
- Values may be unquoted or quoted with single or double quotes.
- Boolean and numeric values in valuations compile to strings because the Java
  runner compares controller values as strings.

## Grammar

The grammar below is descriptive. The compiler also performs semantic
validation after parsing.

```text
plan            ::= top_level_stmt+ test_block+

top_level_stmt  ::= controller_dir_stmt
                  | spec_name_stmt
                  | spectra_file_stmt
                  | environment_stmt
                  | system_stmt

controller_dir_stmt ::= "controller_dir" scalar
spec_name_stmt      ::= "spec_name" scalar
spectra_file_stmt   ::= "spectra_file" scalar
environment_stmt    ::= "environment" variable_list
system_stmt         ::= "system" variable_list

test_block      ::= "test" test_name ":" indented_test_stmt+

indented_test_stmt ::= kind_stmt
                     | mode_stmt
                     | scalar_test_stmt
                     | map_test_stmt
                     | list_test_stmt
                     | trace_block
                     | expect_block
                     | domains_block

kind_stmt       ::= "kind" test_kind
test_kind       ::= "variable_ownership"
                  | "initial_condition"
                  | "exclusion"
                  | "always_implication"
                  | "eventually_response"
                  | "mutual_exclusion"
                  | "one_hot"
                  | "invariant"
                  | "state_sequence"
                  | "persistence"
                  | "response_absence"

mode_stmt       ::= "mode" exploration_mode
exploration_mode ::= "trace" | "random" | "exhaustive"

scalar_test_stmt ::= ("max_depth" | "max_paths" | "runs" | "seed"
                    | "within_steps" | "for_steps") integer
                   | "require_closed_obligations" boolean
                   | ("requirement" | "confidence" | "active_value") scalar

list_test_stmt  ::= ("env" | "sys" | "environment" | "system"
                    | "variables") variable_list

map_test_stmt   ::= ("forbidden" | "when" | "then" | "eventually"
                    | "expected" | "inputs" | "initial_inputs"
                    | "condition" | "maintain" | "until"
                    | "absent") valuation

trace_block     ::= "trace:" indented_valuation+
expect_block    ::= "expect:" indented_valuation+
domains_block   ::= "domains:" indented_domain+

indented_valuation ::= valuation
indented_domain    ::= variable value_list

variable_list   ::= variable ("," variable)*
value_list      ::= value ("," value)*
valuation       ::= variable "=" value ("," variable "=" value)*
```

## Required Top-Level Fields

Every `.rtest` file must define:

- `controller_dir`: path to the synthesized JIT controller directory.
- `spec_name`: Spectra module/spec name used by Syntech.
- `spectra_file`: generated Spectra file used by static tests.
- `environment`: comma-separated environment-controlled input variables.
- `system`: comma-separated system-controlled output variables.

The compiler writes `system` to the JSON field `outputs`, because the Java
runner currently reads system outputs from that field.

Top-level `outputs` is accepted as a legacy alias for `system`, but new DSL files
should use `system`.

## Test Blocks

A test block starts with `test <name>:`. The name must start with a letter or
underscore and may contain letters, digits, underscores, and hyphens.

Each test block must contain a `kind` statement. Supported kinds are described
below.

### variable_ownership

Checks the generated Spectra file statically. It verifies that variables are
declared with the expected ownership.

```text
test declared_variables:
  kind variable_ownership
```

If `env` and `sys` are omitted, the compiler fills them from top-level
`environment` and `system`.

You may override them explicitly:

```text
test selected_variables:
  kind variable_ownership
  env request, cancel
  sys grant
```

### initial_condition

Runs one initial controller step and checks the expected valuation.

```text
test starts_closed:
  kind initial_condition
  inputs request=false
  expected door=CLOSED
```

Required field:

- `expected`: valuation that must hold after the initial step.

Optional field:

- `inputs`: input valuation for the initial step.

### exclusion

Fails if a forbidden valuation appears in any explored step.

```text
test never_both_green:
  kind exclusion
  trace:
    carA=true, carB=false
    carA=false, carB=true
  forbidden greenA=true, greenB=true
```

Required field:

- `forbidden`: valuation that must never be reached.

### always_implication

Checks an immediate safety implication. Whenever `when` matches a step, `then`
must match the same step.

```text
test grant_only_on_request:
  kind always_implication
  mode exhaustive
  max_depth 4
  max_paths 256
  domains:
    request false, true
  when request=false
  then grant=false
```

Required field:

- `then`: valuation that must hold when the trigger matches.

Optional field:

- `when`: trigger valuation. An empty `when` is allowed by the underlying runner,
  but should normally be avoided unless the intended meaning is global.

### eventually_response

Checks bounded response behavior. When `when` is observed, `eventually` must
match within `within_steps`.

```text
test request_eventually_granted:
  kind eventually_response
  trace:
    request=true
    request=true
    request=true
  when request=true
  eventually grant=true
  within_steps 3
```

Required field:

- `eventually`: valuation that must occur within the response window.

Optional fields:

- `when`: trigger valuation. If omitted, the response window starts immediately.
- `within_steps`: response bound. Defaults to `10`.
- `require_closed_obligations`: if `true`, a trace ending before the response is
  observed fails. Defaults to `false`.

### mutual_exclusion

Checks that at most one variable from a group is active at every explored step.

```text
test never_two_modes:
  kind mutual_exclusion
  trace:
    request=true
  variables idle, moving, charging
```

Required field:

- `variables`: variables in the mutually exclusive group.

Optional field:

- `active_value`: value considered active. Defaults to `true`.

### one_hot

Checks that exactly one variable from a group is active at every explored step.

```text
test exactly_one_mode:
  kind one_hot
  trace:
    request=false
  variables idle, moving, charging
```

Required field:

- `variables`: variables in the one-hot group.

Optional field:

- `active_value`: value considered active. Defaults to `true`.

### invariant

Checks that a valuation holds at every explored step.

```text
test reset_implies_idle:
  kind invariant
  trace:
    reset=true
  condition reset=true, idle=true
```

Required field:

- `condition`: valuation that must match every step.

### state_sequence

Replays a concrete `trace:` and checks an `expect:` valuation for each step.

```text
test startup_sequence:
  kind state_sequence
  trace:
    start=true
    start=false
  expect:
    ready=false
    ready=true
```

Required fields:

- `trace`: concrete input sequence.
- `expect`: expected valuations. It must have exactly one entry per trace step.

Use this only when the natural-language requirement defines a concrete sequence;
otherwise it can overconstrain underspecified controllers.

### persistence

After `when` matches, `maintain` must keep matching until `until` matches. If
`until` is omitted, the maintained valuation must hold to the end of each trace.

```text
test alarm_persists_until_reset:
  kind persistence
  trace:
    fault=true, reset=false
    fault=false, reset=false
    fault=false, reset=true
  when alarm=true
  maintain alarm=true
  until reset=true
```

Required field:

- `maintain`: valuation that must persist after the trigger.

Optional fields:

- `when`: trigger valuation. If omitted, the trigger is effectively immediate.
- `until`: valuation that closes the persistence obligation.

### response_absence

After `when` matches, `absent` must not match for `for_steps` steps.

```text
test no_grant_during_reset:
  kind response_absence
  trace:
    reset=true
    reset=false
  when reset=true
  absent grant=true
  for_steps 2
```

Required field:

- `absent`: valuation that must not occur in the absence window.

Optional fields:

- `when`: trigger valuation. If omitted, the trigger is effectively immediate.
- `for_steps`: absence-window length. Defaults to `1`.

## Exploration Modes

Controller tests replay concrete input traces against fresh controller
instances.

### trace

`trace` is the default mode. It requires a `trace:` block for runtime tests such
as `exclusion`, `always_implication`, and `eventually_response`.

```text
test concrete_case:
  kind exclusion
  trace:
    a=false, b=false
    a=true, b=false
  forbidden x=true, y=true
```

### random

Generates deterministic random traces from finite environment domains.

```text
test random_safety:
  kind exclusion
  mode random
  runs 50
  max_depth 10
  seed 1
  domains:
    request false, true
    reset false, true
  forbidden error=true
```

Required field:

- `domains`: finite input domains.

Defaults:

- `runs`: `100`
- `max_depth`: `10`
- `seed`: `1`

### exhaustive

Enumerates the bounded input tree from finite environment domains.

```text
test exhaustive_safety:
  kind exclusion
  mode exhaustive
  max_depth 4
  max_paths 256
  domains:
    carA false, true
    carB false, true
  forbidden greenA=true, greenB=true
```

Required field:

- `domains`: finite input domains.

Defaults:

- `max_depth`: `6`
- `max_paths`: `10000`

Use exhaustive mode only for small domains and shallow depths.

## Valuations

A valuation is a comma-separated list of `variable=value` pairs:

```text
request=true, mode=ACTIVE, level=2
```

The compiler emits values as strings in JSON:

```json
{"request": "true", "mode": "ACTIVE", "level": "2"}
```

This matches the Java runner's comparison behavior.

## Compilation Output

The DSL:

```text
environment carA, carB
system greenA, greenB
```

compiles to JSON containing:

```json
{
  "environment": ["carA", "carB"],
  "system": ["greenA", "greenB"],
  "outputs": ["greenA", "greenB"]
}
```

The `outputs` field exists for Java runner compatibility. The DSL-level source
of truth is `system`.

## Validation Rules

The compiler rejects:

- tabs,
- unknown keys,
- missing required top-level fields,
- files without tests,
- unsupported test kinds,
- `variable_ownership` without any environment or system variables,
- `initial_condition` without `expected`,
- `exclusion` without `forbidden`,
- `always_implication` without `then`,
- `eventually_response` without `eventually`,
- `mutual_exclusion` or `one_hot` without `variables`,
- `invariant` without `condition`,
- `state_sequence` without `expect`,
- `persistence` without `maintain`,
- `response_absence` without `absent`,
- `random` or `exhaustive` tests without `domains:`,
- trace-mode runtime tests without a `trace:` block.

The compiler also performs semantic validation:

- top-level `environment` and `system` variables must be unique,
- a variable may not appear in both `environment` and `system`,
- every test name must be unique,
- all referenced variables must be declared in top-level `environment` or
  `system`,
- `trace:`, `inputs`, and `initial_inputs` may assign only environment
  variables,
- `domains:` may define only environment variables,
- `expected`, `then`, `eventually`, `when`, and `forbidden` may reference known
  environment or system variables because tests match the combined input/output
  valuation observed at each step,
- `condition`, `maintain`, `until`, `absent`, `expect`, and `variables` may also
  reference known environment or system variables,
- `trace:` must not be combined with `mode random` or `mode exhaustive`,
- `domains:` must not be used with default trace mode,
- `max_depth`, `max_paths`, `runs`, `seed`, and `within_steps` must be positive
  when present,
- domain values must not contain duplicates.

With `--strict-files`, the compiler additionally requires `spectra_file` to be
an existing file and `controller_dir` to be an existing directory. This check is
optional because Method-3 agents may create plans before final runtime artifacts
are available.

## Diagnostics JSON

`compile_test_plan.py` can write structured diagnostics with
`--diagnostics-json`. On success, the file has this shape:

```json
{
  "status": "success",
  "tool": "controller_tests.compile_test_plan",
  "file": "tests/test-plan-1.rtest",
  "errors": [],
  "compiled_tests": 3
}
```

On failure, the status is `dsl_syntax_error` and the first compiler error is
reported with a stable code, source context, and repair hint:

```json
{
  "status": "dsl_syntax_error",
  "tool": "controller_tests.compile_test_plan",
  "file": "tests/test-plan-1.rtest",
  "errors": [
    {
      "code": "missing_required_field",
      "line": 8,
      "column": null,
      "message": "Line 8: exclusion requires forbidden.",
      "hint": "Add `forbidden <valuation>` to this exclusion test.",
      "context": [
        {"line": 8, "text": "test never_both_green:", "is_error_line": true}
      ]
    }
  ],
  "repair_instruction": "Repair only the .rtest test-plan syntax and structure..."
}
```

Diagnostic codes include:

- `indentation_error`
- `invalid_statement`
- `unknown_key`
- `invalid_block_syntax`
- `invalid_valuation`
- `invalid_domain`
- `empty_block`
- `invalid_integer`
- `invalid_boolean`
- `missing_top_level_field`
- `missing_test_block`
- `missing_test_kind`
- `unsupported_test_kind`
- `missing_required_field`
- `invalid_exploration`
- `duplicate_variable`
- `variable_owner_conflict`
- `duplicate_test_name`
- `unknown_variable`
- `wrong_variable_owner`
- `unsupported_exploration_mode`
- `conflicting_exploration_fields`
- `invalid_bound`
- `duplicate_domain_value`
- `sequence_length_mismatch`
- `missing_file`
- `missing_controller_dir`

These diagnostics are intended for `.rtest` repair only. A DSL compile failure
must not be treated as evidence that the generated Spectra specification is
wrong.

## DSL Repair Loop

Method-3 agents should repair invalid `.rtest` files before running the Java
controller tests:

1. Write `tests/test-plan-<n>.rtest`.
2. Run the compiler with `--diagnostics-json`.
3. If compilation fails, send the diagnostics JSON, the current `.rtest` file,
   and this DSL reference to the LLM.
4. Ask the LLM to repair only the `.rtest` syntax and structure.
5. Save the repaired file as a new attempt.
6. Retry compilation.
7. Stop after at most three DSL repair attempts.

Only after the `.rtest` file compiles should the generated JSON plan be passed
to `respect.controller_tests.TestRunner`.

## Method-3 Guidance

For ReSpect Method 3, tests must be derived only from:

- the natural-language requirement,
- the generated Spectra file,
- synthesized controller metadata.

Do not derive `.rtest` files from the original benchmark Spectra file or from an
oracle controller.

Prefer small, high-confidence tests:

- one `variable_ownership` test,
- safety tests for explicit "never" or "always" requirements,
- bounded response tests for explicit request/response requirements,
- shallow exhaustive exploration for small Boolean input domains,
- seeded random exploration for larger finite domains.

Do not assert a concrete output strategy when the natural-language requirement
allows multiple valid strategies.
