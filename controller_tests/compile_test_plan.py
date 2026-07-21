#!/usr/bin/env python3
"""Compile ReSpect controller-test DSL files to JSON test plans.

The Java controller test runner intentionally stays JSON-based. This module is
the human/agent-facing layer in front of it: it accepts a compact `.rtest` DSL,
checks that the plan has the fields Method 3 needs, and emits the JSON shape
already understood by `respect.controller_tests.TestRunner`.
"""

from __future__ import annotations

import argparse
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
}
LIST_KEYS = {"outputs", "env", "sys", "environment", "system"}
MAP_KEYS = {"forbidden", "when", "then", "eventually", "expected", "inputs", "initial_inputs"}
BLOCK_KEYS = {"trace", "domains"}
INT_KEYS = {"max_depth", "max_paths", "runs", "seed", "within_steps"}
BOOL_KEYS = {"require_closed_obligations"}
VALID_TEST_KINDS = {
    "variable_ownership",
    "initial_condition",
    "exclusion",
    "always_implication",
    "eventually_response",
}


class DslError(ValueError):
    """Raised when an `.rtest` file cannot be compiled into a valid plan."""


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
            raise DslError(f"Line {number}: tabs are not supported; use spaces.")
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
            raise DslError(f"Line {line_number}: expected key=value item, got {item!r}.")
        key, raw_value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise DslError(f"Line {line_number}: empty key in map item {item!r}.")
        result[key] = stringify_plan_values(parse_scalar(raw_value))
    return result


def parse_statement(line: Line) -> tuple[str, str]:
    """Parse either `key value` or `key: value` statement syntax."""

    if ":" in line.text:
        key, value = line.text.split(":", 1)
        return key.strip(), value.strip()
    parts = line.text.split(None, 1)
    if len(parts) != 2:
        raise DslError(f"Line {line.number}: expected '<key> <value>' or '<key>: <value>'.")
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
        raise DslError(f"Line {lines[start - 1].number}: trace block must contain at least one step.")
    return trace, index


def parse_domains_block(lines: list[Line], start: int, parent_indent: int) -> tuple[dict[str, list[str]], int]:
    """Parse a `domains:` block used by random and exhaustive exploration."""

    domains: dict[str, list[str]] = {}
    index = start
    while index < len(lines) and lines[index].indent > parent_indent:
        key, value = parse_statement(lines[index])
        if not key:
            raise DslError(f"Line {lines[index].number}: empty domain variable.")
        values = parse_csv(value)
        if not values:
            raise DslError(f"Line {lines[index].number}: empty domain for {key}.")
        domains[key] = values
        index += 1
    if not domains:
        raise DslError(f"Line {lines[start - 1].number}: domains block must contain at least one variable.")
    return domains, index


def assign(target: dict[str, Any], key: str, value: str, line_number: int) -> None:
    """Assign a parsed DSL statement to a plan or test dictionary."""

    if key in INT_KEYS:
        try:
            target[key] = int(unquote(value))
        except ValueError as exc:
            raise DslError(f"Line {line_number}: {key} must be an integer.") from exc
    elif key in BOOL_KEYS:
        lowered = unquote(value).lower()
        if lowered not in {"true", "false"}:
            raise DslError(f"Line {line_number}: {key} must be true or false.")
        target[key] = lowered == "true"
    elif key in LIST_KEYS:
        target[key] = parse_csv(value)
    elif key in MAP_KEYS:
        target[key] = parse_map(value, line_number)
    elif key in SCALAR_KEYS:
        target[key] = unquote(value)
    else:
        raise DslError(f"Line {line_number}: unsupported key {key!r}.")


def compile_rtest(source: str) -> dict[str, Any]:
    """Compile `.rtest` source text into the Java runner's JSON plan object."""

    lines = logical_lines(source)
    plan: dict[str, Any] = {"tests": []}
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.indent != 0:
            raise DslError(f"Line {line.number}: top-level statements must not be indented.")
        if line.text.startswith("test "):
            # Test blocks are indentation-scoped. The DSL stays simple enough
            # that a full parser generator would add more maintenance burden
            # than value here.
            match = re.fullmatch(r"test\s+([A-Za-z_][A-Za-z0-9_-]*)\s*:", line.text)
            if not match:
                raise DslError(f"Line {line.number}: expected 'test <name>:'.")
            test: dict[str, Any] = {"name": match.group(1)}
            index += 1
            while index < len(lines) and lines[index].indent > line.indent:
                child = lines[index]
                key, value = parse_statement(child)
                if key == "trace" and value == "":
                    test["trace"], index = parse_trace_block(lines, index + 1, child.indent)
                    continue
                if key == "domains" and value == "":
                    test["env"], index = parse_domains_block(lines, index + 1, child.indent)
                    continue
                if key in BLOCK_KEYS and value != "":
                    raise DslError(f"Line {child.number}: {key} must be written as a block ending with ':'.")
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
        validate_test(test, 1)
    return plan


def validate_test(test: dict[str, Any], line_number: int) -> None:
    """Validate test-kind specific required fields."""

    kind = test.get("kind")
    if kind not in VALID_TEST_KINDS:
        raise DslError(f"Line {line_number}: test {test['name']!r} has unsupported or missing kind {kind!r}.")
    if kind == "variable_ownership":
        if not test.get("env") and not test.get("sys"):
            raise DslError(f"Line {line_number}: variable_ownership requires env and/or sys.")
    if kind == "initial_condition" and not test.get("expected"):
        raise DslError(f"Line {line_number}: initial_condition requires expected.")
    if kind == "exclusion" and not test.get("forbidden"):
        raise DslError(f"Line {line_number}: exclusion requires forbidden.")
    if kind == "always_implication" and not test.get("then"):
        raise DslError(f"Line {line_number}: always_implication requires then.")
    if kind == "eventually_response" and not test.get("eventually"):
        raise DslError(f"Line {line_number}: eventually_response requires eventually.")
    mode = test.get("mode", "trace")
    if mode in {"random", "exhaustive"} and not isinstance(test.get("env"), dict):
        raise DslError(f"Line {line_number}: {mode} tests require a domains: block.")
    if mode in {"trace", "traces"} and kind not in {"variable_ownership", "initial_condition"} and not test.get("trace"):
        raise DslError(f"Line {line_number}: {kind} with trace mode requires a trace: block.")


def validate_plan(plan: dict[str, Any]) -> None:
    """Validate top-level fields required by Method 3 and the Java runner."""

    missing = [key for key in ("controller_dir", "spec_name", "spectra_file", "environment", "system") if not plan.get(key)]
    if missing:
        raise DslError(f"Missing required top-level field(s): {', '.join(missing)}.")
    if not plan["tests"]:
        raise DslError("At least one test block is required.")


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


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for compiling or checking `.rtest` files."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="Path to a .rtest controller-test DSL file.")
    parser.add_argument("-o", "--output", help="Path for the compiled JSON test plan. Defaults to stdout.")
    parser.add_argument("--check", action="store_true", help="Validate the DSL without writing JSON.")
    args = parser.parse_args(argv)

    try:
        plan = compile_rtest(Path(args.input).read_text(encoding="utf-8"))
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
        print(f"rtest error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
