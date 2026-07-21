#!/usr/bin/env python3
"""Compile ReSpect controller-test DSL files to JSON test plans.

The Java controller test runner intentionally stays JSON-based. This module is
the human/agent-facing layer in front of it: it accepts a compact `.rtest` DSL,
checks that the plan has the fields Method 3 needs, and emits the JSON shape
already understood by `respect.controller_tests.TestRunner`.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


# DSL keys are deliberately whitelisted so misspellings fail during compilation
# instead of silently producing a weak or empty test plan.
SCALAR_KEYS = {
    "controller_dir",
    "spec_name",
    "spectra_file",
    "kind",
    "mode",
    "max_depth",
    "max_paths",
    "runs",
    "seed",
    "within_steps",
    "require_closed_obligations",
    "name",
    "requirement",
    "confidence",
    "active_value",
}
LIST_KEYS = {"outputs", "env", "sys", "environment", "system", "variables"}
MAP_KEYS = {
    "forbidden",
    "when",
    "then",
    "eventually",
    "expected",
    "inputs",
    "initial_inputs",
    "condition",
    "maintain",
    "until",
    "absent",
}
BLOCK_KEYS = {"trace", "domains", "expect"}
INT_KEYS = {"max_depth", "max_paths", "runs", "seed", "within_steps", "for_steps"}
BOOL_KEYS = {"require_closed_obligations"}
VALID_TEST_KINDS = {
    "variable_ownership",
    "initial_condition",
    "exclusion",
    "always_implication",
    "eventually_response",
    "mutual_exclusion",
    "one_hot",
    "invariant",
    "state_sequence",
    "persistence",
    "response_absence",
}
VALID_EXPLORATION_MODES = {"trace", "random", "exhaustive"}
POSITIVE_INT_FIELDS = {"max_depth", "max_paths", "runs", "within_steps", "for_steps"}
INPUT_FIELDS = {"inputs", "initial_inputs"}
OBSERVATION_FIELDS = {
    "expected",
    "then",
    "eventually",
    "when",
    "forbidden",
    "condition",
    "maintain",
    "until",
    "absent",
}
ALL_KEYS = sorted(SCALAR_KEYS | LIST_KEYS | MAP_KEYS | BLOCK_KEYS)


class DslError(ValueError):
    """Raised when an `.rtest` file cannot be compiled into a valid plan.

    Besides the human-readable message, the exception carries structured fields
    used by `--diagnostics-json` for LLM repair prompts.
    """

    def __init__(self, message: str, *, code: str = "dsl_error", line: int | None = None, hint: str | None = None):
        super().__init__(message)
        self.code = code
        self.line = line if line is not None else self._line_from_message(message)
        self.hint = hint

    @staticmethod
    def _line_from_message(message: str) -> int | None:
        match = re.match(r"Line\s+(\d+):", message)
        return int(match.group(1)) if match else None


@dataclass(frozen=True)
class Line:
    """A non-empty logical DSL line after comment removal."""

    number: int
    indent: int
    text: str


def strip_comment(raw_line: str) -> str:
    """Remove comments while preserving `#` characters inside quoted strings."""

    in_quote: str | None = None
    escaped = False
    chars: list[str] = []
    for char in raw_line:
        if escaped:
            chars.append(char)
            escaped = False
            continue
        if char == "\\" and in_quote:
            chars.append(char)
            escaped = True
            continue
        if char in {"'", '"'}:
            if in_quote == char:
                in_quote = None
            elif in_quote is None:
                in_quote = char
            chars.append(char)
            continue
        if char == "#" and in_quote is None:
            break
        chars.append(char)
    return "".join(chars).rstrip()


def logical_lines(source: str) -> list[Line]:
    """Return non-empty DSL lines with source line numbers and indentation."""

    lines: list[Line] = []
    for number, raw in enumerate(source.splitlines(), start=1):
        if "\t" in raw:
            raise DslError(
                f"Line {number}: tabs are not supported; use spaces.",
                code="indentation_error",
                line=number,
                hint="Replace tab indentation with spaces.",
            )
        text = strip_comment(raw)
        if not text.strip():
            continue
        indent = len(text) - len(text.lstrip(" "))
        lines.append(Line(number=number, indent=indent, text=text.strip()))
    return lines


def parse_csv(value: str) -> list[str]:
    """Parse comma-separated DSL lists such as `carA, carB`."""

    return [unquote(part.strip()) for part in value.split(",") if part.strip()]


def parse_scalar(value: str) -> str | int | bool:
    """Parse a scalar token used in key/value statements and valuations."""

    value = unquote(value.strip())
    lower = value.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    return value


def unquote(value: str) -> str:
    """Remove matching single or double quotes from a scalar value."""

    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def stringify_plan_values(value: Any) -> Any:
    """Convert valuation values to the string format expected by Java TestUtil.

    The Java runner receives all controller values as strings, e.g. `"true"` or
    `"0"`. Keeping the compiled JSON in that form avoids differences between
    hand-written JSON plans and DSL-generated plans.
    """
    if isinstance(value, dict):
        return {key: stringify_plan_values(item) for key, item in value.items()}
    if isinstance(value, list):
        return [stringify_plan_values(item) for item in value]
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    return value


def parse_map(value: str, line_number: int) -> dict[str, str]:
    """Parse inline valuation maps such as `request=true, grant=false`."""

    result: dict[str, str] = {}
    if not value.strip():
        return result
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        if "=" not in item:
            raise DslError(
                f"Line {line_number}: expected key=value item, got {item!r}.",
                code="invalid_valuation",
                line=line_number,
                hint="Write valuations as comma-separated key=value pairs, for example `request=true, grant=false`.",
            )
        key, raw_value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise DslError(
                f"Line {line_number}: empty key in map item {item!r}.",
                code="invalid_valuation",
                line=line_number,
                hint="Add a variable name before `=`.",
            )
        result[key] = stringify_plan_values(parse_scalar(raw_value))
    return result


def parse_statement(line: Line) -> tuple[str, str]:
    """Parse either `key value` or `key: value` statement syntax."""

    if ":" in line.text:
        key, value = line.text.split(":", 1)
        return key.strip(), value.strip()
    parts = line.text.split(None, 1)
    if len(parts) != 2:
        raise DslError(
            f"Line {line.number}: expected '<key> <value>' or '<key>: <value>'.",
            code="invalid_statement",
            line=line.number,
            hint="Use `key value` for scalar/list fields or `key:` for indented blocks.",
        )
    return parts[0].strip(), parts[1].strip()


def parse_trace_block(lines: list[Line], start: int, parent_indent: int) -> tuple[list[dict[str, str]], int]:
    """Parse an indented `trace:` block into concrete input steps."""

    trace: list[dict[str, str]] = []
    index = start
    while index < len(lines) and lines[index].indent > parent_indent:
        text = lines[index].text
        if text.startswith("- "):
            text = text[2:].strip()
        trace.append(parse_map(text, lines[index].number))
        index += 1
    if not trace:
        line_number = lines[start - 1].number
        raise DslError(
            f"Line {line_number}: trace block must contain at least one step.",
            code="empty_block",
            line=line_number,
            hint="Add at least one indented input valuation under `trace:`.",
        )
    return trace, index


def parse_domains_block(lines: list[Line], start: int, parent_indent: int) -> tuple[dict[str, list[str]], int]:
    """Parse a `domains:` block used by random and exhaustive exploration."""

    domains: dict[str, list[str]] = {}
    index = start
    while index < len(lines) and lines[index].indent > parent_indent:
        key, value = parse_statement(lines[index])
        if not key:
            raise DslError(
                f"Line {lines[index].number}: empty domain variable.",
                code="invalid_domain",
                line=lines[index].number,
                hint="Write each domain as `<variable> value1, value2`.",
            )
        values = parse_csv(value)
        if not values:
            raise DslError(
                f"Line {lines[index].number}: empty domain for {key}.",
                code="invalid_domain",
                line=lines[index].number,
                hint=f"Add at least one value to the domain for `{key}`.",
            )
        domains[key] = values
        index += 1
    if not domains:
        line_number = lines[start - 1].number
        raise DslError(
            f"Line {line_number}: domains block must contain at least one variable.",
            code="empty_block",
            line=line_number,
            hint="Add at least one indented domain such as `request false, true`.",
        )
    return domains, index


def assign(target: dict[str, Any], key: str, value: str, line_number: int) -> None:
    """Assign a parsed DSL statement to a plan or test dictionary."""

    if key in INT_KEYS:
        try:
            target[key] = int(unquote(value))
        except ValueError as exc:
            raise DslError(
                f"Line {line_number}: {key} must be an integer.",
                code="invalid_integer",
                line=line_number,
                hint=f"Use an integer value for `{key}`, for example `{key} 4`.",
            ) from exc
    elif key in BOOL_KEYS:
        lowered = unquote(value).lower()
        if lowered not in {"true", "false"}:
            raise DslError(
                f"Line {line_number}: {key} must be true or false.",
                code="invalid_boolean",
                line=line_number,
                hint=f"Use `{key} true` or `{key} false`.",
            )
        target[key] = lowered == "true"
    elif key in LIST_KEYS:
        target[key] = parse_csv(value)
    elif key in MAP_KEYS:
        target[key] = parse_map(value, line_number)
    elif key in SCALAR_KEYS:
        target[key] = unquote(value)
    else:
        suggestion = difflib.get_close_matches(key, ALL_KEYS, n=1)
        hint = f"Did you mean `{suggestion[0]}`?" if suggestion else "Use only keys documented in controller_tests/DSL.md."
        raise DslError(
            f"Line {line_number}: unsupported key {key!r}.",
            code="unknown_key",
            line=line_number,
            hint=hint,
        )


def compile_rtest(source: str, *, strict_files: bool = False) -> dict[str, Any]:
    """Compile `.rtest` source text into the Java runner's JSON plan object."""

    lines = logical_lines(source)
    plan: dict[str, Any] = {"tests": []}
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.indent != 0:
            raise DslError(
                f"Line {line.number}: top-level statements must not be indented.",
                code="indentation_error",
                line=line.number,
                hint="Move top-level metadata and `test <name>:` blocks to column 1.",
            )
        if line.text.startswith("test "):
            # Test blocks are indentation-scoped. The DSL stays simple enough
            # that a full parser generator would add more maintenance burden
            # than value here.
            match = re.fullmatch(r"test\s+([A-Za-z_][A-Za-z0-9_-]*)\s*:", line.text)
            if not match:
                raise DslError(
                    f"Line {line.number}: expected 'test <name>:'.",
                    code="invalid_test_header",
                    line=line.number,
                    hint="Write test blocks as `test descriptive_name:`.",
                )
            test: dict[str, Any] = {"name": match.group(1), "__line": line.number}
            index += 1
            while index < len(lines) and lines[index].indent > line.indent:
                child = lines[index]
                key, value = parse_statement(child)
                if key == "trace" and value == "":
                    test["trace"], index = parse_trace_block(lines, index + 1, child.indent)
                    continue
                if key == "expect" and value == "":
                    test["expect"], index = parse_trace_block(lines, index + 1, child.indent)
                    continue
                if key == "domains" and value == "":
                    test["env"], index = parse_domains_block(lines, index + 1, child.indent)
                    continue
                if key in BLOCK_KEYS and value != "":
                    raise DslError(
                        f"Line {child.number}: {key} must be written as a block ending with ':'.",
                        code="invalid_block_syntax",
                        line=child.number,
                        hint=f"Write `{key}:` and place indented entries on following lines.",
                    )
                assign(test, key, value, child.number)
                index += 1
            plan["tests"].append(test)
            continue
        key, value = parse_statement(line)
        assign(plan, key, value, line.number)
        index += 1
    normalize_plan(plan)
    validate_plan(plan)
    for test in plan["tests"]:
        validate_test(test, test.get("__line", 1))
        test.pop("__line", None)
    validate_plan_semantics(plan, strict_files=strict_files)
    return plan


def validate_test(test: dict[str, Any], line_number: int) -> None:
    """Validate test-kind specific required fields."""

    kind = test.get("kind")
    if kind not in VALID_TEST_KINDS:
        if kind is None:
            raise DslError(
                f"Line {line_number}: test {test['name']!r} is missing kind.",
                code="missing_test_kind",
                line=line_number,
                hint="Add a `kind <test_kind>` statement inside the test block.",
            )
        suggestion = difflib.get_close_matches(str(kind), sorted(VALID_TEST_KINDS), n=1)
        hint = f"Did you mean `kind {suggestion[0]}`?" if suggestion else "Use one of the supported test kinds from controller_tests/DSL.md."
        raise DslError(
            f"Line {line_number}: test {test['name']!r} has unsupported kind {kind!r}.",
            code="unsupported_test_kind",
            line=line_number,
            hint=hint,
        )
    if kind == "variable_ownership":
        if not test.get("env") and not test.get("sys"):
            raise DslError(
                f"Line {line_number}: variable_ownership requires env and/or sys.",
                code="missing_required_field",
                line=line_number,
                hint="Add top-level `environment`/`system` declarations or test-level `env`/`sys` lists.",
            )
    if kind == "initial_condition" and not test.get("expected"):
        raise DslError(
            f"Line {line_number}: initial_condition requires expected.",
            code="missing_required_field",
            line=line_number,
            hint="Add `expected <valuation>` to this initial_condition test.",
        )
    if kind == "exclusion" and not test.get("forbidden"):
        raise DslError(
            f"Line {line_number}: exclusion requires forbidden.",
            code="missing_required_field",
            line=line_number,
            hint="Add `forbidden <valuation>` to this exclusion test.",
        )
    if kind == "always_implication" and not test.get("then"):
        raise DslError(
            f"Line {line_number}: always_implication requires then.",
            code="missing_required_field",
            line=line_number,
            hint="Add `then <valuation>` to this always_implication test.",
        )
    if kind == "eventually_response" and not test.get("eventually"):
        raise DslError(
            f"Line {line_number}: eventually_response requires eventually.",
            code="missing_required_field",
            line=line_number,
            hint="Add `eventually <valuation>` to this eventually_response test.",
        )
    if kind in {"mutual_exclusion", "one_hot"} and not test.get("variables"):
        raise DslError(
            f"Line {line_number}: {kind} requires variables.",
            code="missing_required_field",
            line=line_number,
            hint=f"Add `variables <comma-separated variables>` to this {kind} test.",
        )
    if kind == "invariant" and not test.get("condition"):
        raise DslError(
            f"Line {line_number}: invariant requires condition.",
            code="missing_required_field",
            line=line_number,
            hint="Add `condition <valuation>` to this invariant test.",
        )
    if kind == "state_sequence" and not test.get("expect"):
        raise DslError(
            f"Line {line_number}: state_sequence requires expect.",
            code="missing_required_field",
            line=line_number,
            hint="Add an `expect:` block with one expected valuation per trace step.",
        )
    if kind == "persistence" and not test.get("maintain"):
        raise DslError(
            f"Line {line_number}: persistence requires maintain.",
            code="missing_required_field",
            line=line_number,
            hint="Add `maintain <valuation>` to this persistence test.",
        )
    if kind == "response_absence" and not test.get("absent"):
        raise DslError(
            f"Line {line_number}: response_absence requires absent.",
            code="missing_required_field",
            line=line_number,
            hint="Add `absent <valuation>` to this response_absence test.",
        )
    mode = test.get("mode", "trace")
    if mode not in VALID_EXPLORATION_MODES:
        raise DslError(
            f"Line {line_number}: unsupported exploration mode {mode!r}.",
            code="unsupported_exploration_mode",
            line=line_number,
            hint="Use `mode trace`, `mode random`, or `mode exhaustive`.",
        )
    if mode in {"random", "exhaustive"} and not isinstance(test.get("env"), dict):
        raise DslError(
            f"Line {line_number}: {mode} tests require a domains: block.",
            code="invalid_exploration",
            line=line_number,
            hint=f"Add a `domains:` block with finite environment domains for this {mode} test.",
        )
    if mode == "trace" and kind not in {"variable_ownership", "initial_condition"} and not test.get("trace"):
        raise DslError(
            f"Line {line_number}: {kind} with trace mode requires a trace: block.",
            code="missing_required_field",
            line=line_number,
            hint="Add a `trace:` block or switch to `mode random`/`mode exhaustive` with `domains:`.",
        )


def validate_plan(plan: dict[str, Any]) -> None:
    """Validate top-level fields required by Method 3 and the Java runner."""

    missing = [key for key in ("controller_dir", "spec_name", "spectra_file", "environment", "system") if not plan.get(key)]
    if missing:
        raise DslError(
            f"Missing required top-level field(s): {', '.join(missing)}.",
            code="missing_top_level_field",
            hint="Add all required top-level fields: controller_dir, spec_name, spectra_file, environment, system.",
        )
    if not plan["tests"]:
        raise DslError(
            "At least one test block is required.",
            code="missing_test_block",
            hint="Add at least one `test <name>:` block.",
        )


def normalize_plan(plan: dict[str, Any]) -> None:
    """Normalize DSL aliases to the JSON fields consumed by the Java runner."""

    if "outputs" in plan and "system" not in plan:
        plan["system"] = plan["outputs"]
    if "system" in plan:
        # The DSL uses `system`; the Java harness still consumes `outputs`.
        plan["outputs"] = plan["system"]

    for test in plan.get("tests", []):
        # Inside test blocks, keep the existing JSON field names so the Java
        # runner remains unchanged.
        if "environment" in test:
            test["env"] = test.pop("environment")
        if "system" in test:
            test["sys"] = test.pop("system")
        if test.get("kind") == "variable_ownership":
            # Ownership checks normally mirror the top-level signature, so the
            # DSL does not force authors to repeat the same variable lists.
            test.setdefault("env", plan.get("environment", []))
            test.setdefault("sys", plan.get("system", []))


def duplicates(values: list[str]) -> list[str]:
    """Return duplicate entries while preserving first duplicate encounter order."""

    seen: set[str] = set()
    repeated: list[str] = []
    repeated_seen: set[str] = set()
    for value in values:
        if value in seen and value not in repeated_seen:
            repeated.append(value)
            repeated_seen.add(value)
        seen.add(value)
    return repeated


def validate_plan_semantics(plan: dict[str, Any], *, strict_files: bool = False) -> None:
    """Validate variable ownership, exploration consistency, and numeric bounds."""

    environment = list(plan.get("environment") or [])
    system = list(plan.get("system") or [])
    env_set = set(environment)
    sys_set = set(system)
    known = env_set | sys_set

    validate_top_level_signature(environment, system)
    validate_unique_test_names(plan.get("tests", []))
    for test in plan.get("tests", []):
        validate_test_semantics(test, env_set=env_set, sys_set=sys_set, known=known)
    if strict_files:
        validate_files(plan)


def validate_top_level_signature(environment: list[str], system: list[str]) -> None:
    """Ensure environment and system declarations are unique and disjoint."""

    for label, values in (("environment", environment), ("system", system)):
        repeated = duplicates(values)
        if repeated:
            raise DslError(
                f"Duplicate variable(s) in top-level {label}: {', '.join(repeated)}.",
                code="duplicate_variable",
                hint=f"Remove duplicate variable names from the top-level `{label}` declaration.",
            )
    overlap = sorted(set(environment) & set(system))
    if overlap:
        raise DslError(
            f"Variable(s) declared as both environment and system: {', '.join(overlap)}.",
            code="variable_owner_conflict",
            hint="Each variable must be controlled by either the environment or the system, not both.",
        )


def validate_unique_test_names(tests: list[dict[str, Any]]) -> None:
    """Reject duplicate test names because they make repair feedback ambiguous."""

    seen: set[str] = set()
    for test in tests:
        name = str(test.get("name"))
        if name in seen:
            raise DslError(
                f"Duplicate test name {name!r}.",
                code="duplicate_test_name",
                hint="Rename one of the tests so every `test <name>:` block has a unique name.",
            )
        seen.add(name)


def validate_test_semantics(test: dict[str, Any], *, env_set: set[str], sys_set: set[str], known: set[str]) -> None:
    """Validate semantic consistency inside one compiled test block."""

    test_name = str(test.get("name"))
    mode = test.get("mode", "trace")
    has_trace = "trace" in test
    has_domains = isinstance(test.get("env"), dict)

    if mode in {"random", "exhaustive"} and has_trace:
        raise DslError(
            f"Test {test_name!r} uses mode {mode!r} but also defines a trace block.",
            code="conflicting_exploration_fields",
            hint="Use either `trace:` with default trace mode or `domains:` with random/exhaustive mode, not both.",
        )
    if mode == "trace" and has_domains:
        raise DslError(
            f"Test {test_name!r} uses trace mode but defines a domains block.",
            code="conflicting_exploration_fields",
            hint="Remove `domains:` or switch to `mode random` or `mode exhaustive`.",
        )

    for field in POSITIVE_INT_FIELDS:
        if field in test and int(test[field]) <= 0:
            raise DslError(
                f"Test {test_name!r} has non-positive {field}: {test[field]}.",
                code="invalid_bound",
                hint=f"Use a positive integer for `{field}`.",
            )

    if has_domains:
        validate_domain_map(test_name, test["env"], env_set=env_set, known=known)

    for step in test.get("trace") or []:
        validate_variables(
            test_name=test_name,
            field="trace",
            variables=set(step),
            allowed=env_set,
            known=known,
            owner_hint="Trace steps may assign only environment variables.",
        )

    if "variables" in test:
        validate_variables(
            test_name=test_name,
            field="variables",
            variables=set(test["variables"]),
            allowed=known,
            known=known,
            owner_hint="`variables` may reference known environment or system variables.",
        )

    for field in INPUT_FIELDS:
        if field in test:
            validate_variables(
                test_name=test_name,
                field=field,
                variables=set(test[field]),
                allowed=env_set,
                known=known,
                owner_hint=f"`{field}` may assign only environment variables.",
            )

    for field in OBSERVATION_FIELDS:
        if field in test:
            variables = set(test[field])
            validate_variables(
                test_name=test_name,
                field=field,
                variables=variables,
                allowed=known,
                known=known,
                owner_hint=f"`{field}` may reference known environment or system variables.",
            )

    if "expect" in test:
        for step in test["expect"]:
            validate_variables(
                test_name=test_name,
                field="expect",
                variables=set(step),
                allowed=known,
                known=known,
                owner_hint="`expect:` may reference known environment or system variables.",
            )
        if test.get("kind") == "state_sequence" and len(test.get("trace") or []) != len(test["expect"]):
            raise DslError(
                f"Test {test_name!r} has {len(test.get('trace') or [])} trace step(s) but {len(test['expect'])} expect step(s).",
                code="sequence_length_mismatch",
                hint="For `state_sequence`, provide exactly one `expect:` valuation for each `trace:` step.",
            )


def validate_domain_map(test_name: str, domains: dict[str, list[str]], *, env_set: set[str], known: set[str]) -> None:
    """Validate exploration domains and reject duplicate domain values."""

    validate_variables(
        test_name=test_name,
        field="domains",
        variables=set(domains),
        allowed=env_set,
        known=known,
        owner_hint="`domains:` may define only environment input variables.",
    )
    for variable, values in domains.items():
        repeated = duplicates(values)
        if repeated:
            raise DslError(
                f"Test {test_name!r} domain for {variable!r} contains duplicate value(s): {', '.join(repeated)}.",
                code="duplicate_domain_value",
                hint=f"Remove duplicate values from the domain for `{variable}`.",
            )


def validate_variables(
    *,
    test_name: str,
    field: str,
    variables: set[str],
    allowed: set[str],
    known: set[str],
    owner_hint: str,
) -> None:
    """Validate that referenced variables are known and owned by the right side."""

    unknown = sorted(variables - known)
    if unknown:
        suggestion = variable_suggestion(unknown[0], known)
        hint = f"Did you mean `{suggestion}`?" if suggestion else "Declare the variable in top-level `environment` or `system`, or fix the typo."
        raise DslError(
            f"Test {test_name!r} field `{field}` references unknown variable(s): {', '.join(unknown)}.",
            code="unknown_variable",
            hint=hint,
        )
    wrong_owner = sorted(variables - allowed)
    if wrong_owner:
        raise DslError(
            f"Test {test_name!r} field `{field}` uses variable(s) with the wrong owner: {', '.join(wrong_owner)}.",
            code="wrong_variable_owner",
            hint=owner_hint,
        )


def variable_suggestion(name: str, known: set[str]) -> str | None:
    """Return a close known variable name for typo-oriented diagnostics."""

    matches = difflib.get_close_matches(name, sorted(known), n=1)
    return matches[0] if matches else None


def validate_files(plan: dict[str, Any]) -> None:
    """Optionally ensure referenced files/directories already exist."""

    spectra_file = Path(str(plan.get("spectra_file")))
    if not spectra_file.is_file():
        raise DslError(
            f"spectra_file does not exist: {spectra_file}",
            code="missing_file",
            hint="Create the generated Spectra file before compiling with `--strict-files`, or omit `--strict-files`.",
        )
    controller_dir = Path(str(plan.get("controller_dir")))
    if not controller_dir.is_dir():
        raise DslError(
            f"controller_dir does not exist: {controller_dir}",
            code="missing_controller_dir",
            hint="Synthesize the controller before compiling with `--strict-files`, or omit `--strict-files`.",
        )


def source_context(source: str, line_number: int | None, radius: int = 3) -> list[dict[str, Any]]:
    """Return a small source excerpt around a diagnostic line."""

    if line_number is None:
        return []
    raw_lines = source.splitlines()
    start = max(1, line_number - radius)
    end = min(len(raw_lines), line_number + radius)
    return [
        {
            "line": number,
            "text": raw_lines[number - 1],
            "is_error_line": number == line_number,
        }
        for number in range(start, end + 1)
    ]


def diagnostic_payload(
    *,
    source: str,
    path: str,
    error: DslError | None = None,
    compiled_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build machine-readable compiler diagnostics for humans or LLM repair."""

    if error is None:
        return {
            "status": "success",
            "tool": "controller_tests.compile_test_plan",
            "file": path,
            "errors": [],
            "compiled_tests": len(compiled_plan.get("tests", [])) if compiled_plan else 0,
        }

    return {
        "status": "dsl_syntax_error",
        "tool": "controller_tests.compile_test_plan",
        "file": path,
        "errors": [
            {
                "code": error.code,
                "line": error.line,
                "column": None,
                "message": str(error),
                "hint": error.hint,
                "context": source_context(source, error.line),
            }
        ],
        "repair_instruction": (
            "Repair only the .rtest test-plan syntax and structure. Preserve the intended tests, "
            "do not change the generated Spectra specification, and do not add tests that are not "
            "justified by the natural-language requirements."
        ),
    }


def write_diagnostics(path: str | None, payload: dict[str, Any]) -> None:
    """Write diagnostics JSON when requested by the caller."""

    if path is None:
        return
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for compiling or checking `.rtest` files."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="Path to a .rtest controller-test DSL file.")
    parser.add_argument("-o", "--output", help="Path for the compiled JSON test plan. Defaults to stdout.")
    parser.add_argument("--check", action="store_true", help="Validate the DSL without writing JSON.")
    parser.add_argument(
        "--diagnostics-json",
        help="Optional path for machine-readable compile diagnostics used by DSL repair loops.",
    )
    parser.add_argument(
        "--strict-files",
        action="store_true",
        help="Also require spectra_file and controller_dir paths to exist.",
    )
    args = parser.parse_args(argv)

    source = Path(args.input).read_text(encoding="utf-8")
    try:
        plan = compile_rtest(source, strict_files=args.strict_files)
        write_diagnostics(
            args.diagnostics_json,
            diagnostic_payload(source=source, path=args.input, compiled_plan=plan),
        )
        if args.check:
            return 0
        payload = json.dumps(plan, indent=2)
        if args.output:
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(payload + "\n", encoding="utf-8")
        else:
            print(payload)
        return 0
    except DslError as exc:
        write_diagnostics(
            args.diagnostics_json,
            diagnostic_payload(source=source, path=args.input, error=exc),
        )
        print(f"rtest error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
