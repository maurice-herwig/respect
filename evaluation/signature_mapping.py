#!/usr/bin/env python3
"""LLM-assisted one-to-one variable mappings for ReSpect evaluation."""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_URL = "https://chat-ai.academiccloud.de/v1"
DEFAULT_MAPPING_FILE = REPO_ROOT / "evaluation" / "signature_mappings.jsonl"
SYSTEM_PROMPT = (
    "You map variable names between two formal Spectra specifications. "
    "Return only valid JSON and no Markdown. "
    "Perform conservative lexical renaming only. "
    "Prefer false negatives over false positives. "
    "If you are not certain that two names are obvious variants of the same name, leave them unmapped."
)
DECLARATION_RE = re.compile(r"^\s*(env|sys)\s+(.+?)\s+([A-Za-z_][A-Za-z0-9_]*)\s*;", re.MULTILINE)
SPEC_RE = re.compile(r"^\s*spec\s+([A-Za-z_][A-Za-z0-9_]*)\b", re.MULTILINE)
TYPE_RE = re.compile(r"^\s*type\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+?)\s*;", re.MULTILINE)
INLINE_ENUM_RE = re.compile(r"^\{\s*([^{}]+?)\s*\}$")
INT_RE = re.compile(r"^Int\s*\(\s*(-?\d+)\s*\.\.\s*(-?\d+)\s*\)$")


def repo_relative_or_absolute(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path.resolve())


def strip_line_comments(source: str) -> str:
    return "\n".join(line.split("//", 1)[0] for line in source.splitlines())


def parse_domain(type_expr: str, type_defs: dict[str, str]) -> tuple[list[str] | None, str | None]:
    type_expr = type_expr.strip()
    if "[" in type_expr or "]" in type_expr:
        return None, f"unsupported array type: {type_expr}"
    seen: set[str] = set()
    while type_expr in type_defs:
        if type_expr in seen:
            return None, f"cyclic type alias: {type_expr}"
        seen.add(type_expr)
        type_expr = type_defs[type_expr].strip()
    if type_expr == "boolean":
        return ["false", "true"], None
    enum_match = INLINE_ENUM_RE.match(type_expr)
    if enum_match:
        values = [value.strip() for value in enum_match.group(1).split(",") if value.strip()]
        return values or None, None if values else f"empty enum type: {type_expr}"
    int_match = INT_RE.match(type_expr)
    if int_match:
        low = int(int_match.group(1))
        high = int(int_match.group(2))
        if high < low:
            return None, f"invalid Int range: {type_expr}"
        return [str(value) for value in range(low, high + 1)], None
    return None, f"unsupported type: {type_expr}"


def parse_spectra_signature(path: Path) -> dict[str, Any]:
    source = strip_line_comments(path.read_text(encoding="utf-8", errors="replace"))
    spec_match = SPEC_RE.search(source)
    if not spec_match:
        return {"status": "error", "error": "missing spec declaration", "path": repo_relative_or_absolute(path)}
    type_defs = {match.group(1): match.group(2).strip() for match in TYPE_RE.finditer(source)}
    env: dict[str, list[str]] = {}
    sys_vars: dict[str, list[str]] = {}
    errors: list[str] = []
    for match in DECLARATION_RE.finditer(source):
        owner, type_expr, variable = match.group(1), match.group(2).strip(), match.group(3)
        domain, error = parse_domain(type_expr, type_defs)
        if error is not None or domain is None:
            errors.append(f"{owner} {variable}: {error}")
            continue
        target = env if owner == "env" else sys_vars
        target[variable] = domain
    return {
        "status": "success" if not errors else "unsupported_signature",
        "error": "; ".join(errors) if errors else None,
        "path": repo_relative_or_absolute(path),
        "spec_name": spec_match.group(1),
        "env": env,
        "sys": sys_vars,
    }


def load_dotenv(path: Path | None = None) -> None:
    path = path or REPO_ROOT / ".env"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def mapping_key(
    *,
    baseline_signature: dict[str, Any],
    generated_signature: dict[str, Any],
    model: str,
    prompt_version: str,
) -> str:
    payload = {
        "baseline": {
            "env": baseline_signature.get("env"),
            "sys": baseline_signature.get("sys"),
        },
        "generated": {
            "env": generated_signature.get("env"),
            "sys": generated_signature.get("sys"),
        },
        "model": model,
        "prompt_version": prompt_version,
    }
    return sha256_text(json.dumps(payload, sort_keys=True))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return records


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def load_cached_mapping(path: Path, key: str) -> dict[str, Any] | None:
    for record in reversed(load_jsonl(path)):
        if record.get("mapping_key") == key:
            return record
    return None


def chat_completions_url(base_url: str) -> str:
    return base_url.rstrip("/") + "/chat/completions"


def call_academic_cloud(
    *,
    api_key: str,
    base_url: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float | None,
    max_tokens: int | None,
    timeout: float,
    retries: int = 1,
    retry_delay_seconds: float = 2.0,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    if temperature is not None:
        payload["temperature"] = temperature
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    request = urllib.request.Request(
        chat_completions_url(base_url),
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    attempts = retries + 1
    last_http_error: tuple[int, str] | None = None
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
                result.setdefault("_respect_api_metadata", {})
                result["_respect_api_metadata"].update(
                    {"attempts": attempt, "max_attempts": attempts, "retried": attempt > 1}
                )
                return result
        except urllib.error.HTTPError as exc:
            try:
                details = exc.read().decode("utf-8", errors="replace")
            except Exception:
                details = ""
            last_http_error = (exc.code, details)
            if exc.code < 500 or attempt >= attempts:
                break
            time.sleep(retry_delay_seconds)
    if last_http_error is not None:
        code, details = last_http_error
        raise RuntimeError(f"Academic Cloud API request failed with HTTP {code}: {details}")
    raise RuntimeError("Academic Cloud API request failed without an HTTP response.")


def extract_response_text(response: dict[str, Any]) -> str:
    choices = response.get("choices") or []
    if not choices:
        raise RuntimeError("Academic Cloud response did not contain choices.")
    content = (choices[0].get("message") or {}).get("content")
    if not isinstance(content, str):
        raise RuntimeError("Academic Cloud response did not contain message.content.")
    return content


def extract_json_object(text: str) -> dict[str, Any]:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fenced:
        return json.loads(fenced.group(1))
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("LLM response did not contain a JSON object.")
    return json.loads(text[start : end + 1])


def render_mapping_prompt(baseline_signature: dict[str, Any], generated_signature: dict[str, Any]) -> str:
    payload = {
        "baseline": {
            "env": baseline_signature.get("env") or {},
            "sys": baseline_signature.get("sys") or {},
        },
        "generated": {
            "env": generated_signature.get("env") or {},
            "sys": generated_signature.get("sys") or {},
        },
    }
    return (
        "Create a conservative one-to-one lexical variable-name mapping from baseline Spectra variable names "
        "to generated Spectra variable names.\n\n"
        "Your task is only to identify obvious renamings from the names themselves. "
        "Do not infer meaning from specification behavior, variable ownership, variable order, or domain knowledge. "
        "Only map a pair when you are certain the names are lexical variants of the same name. "
        "If there is any doubt, leave the variables unmapped.\n\n"
        "Allowed mappings:\n"
        "- Identical names.\n"
        "- Case-only variants.\n"
        "- snake_case, kebab-case, camelCase, and PascalCase variants.\n"
        "- Minor separator, spelling, or pluralization variants.\n"
        "- Abbreviation expansions only when the expansion is explicit and obvious in the other name, "
        "such as HighW -> HighWater.\n\n"
        "Forbidden mappings:\n"
        "- Do not map names by guessing synonyms or related domain concepts.\n"
        "- Do not use the variable domains to infer semantic equivalence.\n"
        "- Do not map related but non-identical concepts, such as water -> highWater, motor -> pump, "
        "alarm -> warning, or request -> grant.\n"
        "- Do not map short ambiguous names unless the expansion is explicit and obvious in the other name.\n"
        "- Do not invent variables.\n"
        "- Do not force a complete mapping. It is better to leave variables unmapped than to risk a wrong mapping.\n\n"
        "Structural rules:\n"
        "- Map env variables only to generated env variables.\n"
        "- Map sys variables only to generated sys variables.\n"
        "- Only map variables with exactly identical domains, including value names and order.\n"
        "- Each baseline variable and each generated variable may appear at most once.\n"
        "- Prefer false negatives over false positives.\n\n"
        "Return JSON only with exactly these keys: env, sys, unmapped_baseline_env, unmapped_generated_env, "
        "unmapped_baseline_sys, unmapped_generated_sys, confidence, explanation. "
        "Use confidence \"high\" only when every returned mapping is obvious. "
        "If no mapping is obvious, return empty env/sys objects and list all variables as unmapped.\n\n"
        f"Signatures:\n{json.dumps(payload, indent=2, sort_keys=True)}"
    )


def validate_mapping(
    mapping: dict[str, Any],
    baseline_signature: dict[str, Any],
    generated_signature: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    baseline_env = baseline_signature.get("env") or {}
    baseline_sys = baseline_signature.get("sys") or {}
    generated_env = generated_signature.get("env") or {}
    generated_sys = generated_signature.get("sys") or {}
    validated = {"env": {}, "sys": {}}

    for owner, baseline_vars, generated_vars in (
        ("env", baseline_env, generated_env),
        ("sys", baseline_sys, generated_sys),
    ):
        raw = mapping.get(owner) or {}
        if not isinstance(raw, dict):
            errors.append(f"{owner} mapping is not an object")
            continue
        used_targets: set[str] = set()
        for baseline_name, generated_name in raw.items():
            if baseline_name not in baseline_vars:
                errors.append(f"{owner}.{baseline_name}: baseline variable does not exist")
                continue
            if generated_name not in generated_vars:
                errors.append(f"{owner}.{baseline_name}: generated variable {generated_name!r} does not exist")
                continue
            if generated_name in used_targets:
                errors.append(f"{owner}.{baseline_name}: generated variable {generated_name!r} mapped more than once")
                continue
            if baseline_vars[baseline_name] != generated_vars[generated_name]:
                errors.append(f"{owner}.{baseline_name}: domain mismatch with {generated_name}")
                continue
            used_targets.add(generated_name)
            validated[owner][baseline_name] = generated_name

    for owner, baseline_vars, generated_vars in (
        ("env", baseline_env, generated_env),
        ("sys", baseline_sys, generated_sys),
    ):
        mapped_baseline = set(validated[owner])
        mapped_generated = set(validated[owner].values())
        validated[f"unmapped_baseline_{owner}"] = sorted(set(baseline_vars) - mapped_baseline)
        validated[f"unmapped_generated_{owner}"] = sorted(set(generated_vars) - mapped_generated)

    complete = not any(validated[f"unmapped_baseline_{owner}"] or validated[f"unmapped_generated_{owner}"] for owner in ("env", "sys"))
    validated["complete"] = complete
    validated["confidence"] = mapping.get("confidence")
    validated["explanation"] = mapping.get("explanation")
    return validated, errors


def get_or_create_llm_mapping(
    *,
    baseline_signature: dict[str, Any],
    generated_signature: dict[str, Any],
    mapping_file: Path,
    model: str | None = None,
    base_url: str | None = None,
    timeout: float = 120.0,
    temperature: float | None = 0.0,
    max_tokens: int | None = 1000,
    retries: int = 1,
    retry_delay_seconds: float = 2.0,
    force: bool = False,
) -> dict[str, Any]:
    load_dotenv()
    model = model or os.environ.get("ACADEMIC_CLOUD_MODEL")
    base_url = base_url or os.environ.get("ACADEMIC_CLOUD_BASE_URL", DEFAULT_BASE_URL)
    api_key = os.environ.get("ACADEMIC_CLOUD_API_KEY")
    if not model:
        raise RuntimeError("Missing Academic Cloud model. Set ACADEMIC_CLOUD_MODEL or pass --mapping-model.")
    key = mapping_key(
        baseline_signature=baseline_signature,
        generated_signature=generated_signature,
        model=model,
        prompt_version="signature_mapping_v1",
    )
    if not force:
        cached = load_cached_mapping(mapping_file, key)
        if cached is not None:
            return cached
    if not api_key:
        raise RuntimeError("Missing ACADEMIC_CLOUD_API_KEY for LLM signature mapping.")

    prompt = render_mapping_prompt(baseline_signature, generated_signature)
    try:
        response = call_academic_cloud(
            api_key=api_key,
            base_url=base_url,
            model=model,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            retries=retries,
            retry_delay_seconds=retry_delay_seconds,
        )
    except RuntimeError as exc:
        record = {
            "mapping_key": key,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "api_status": "error",
            "model": model,
            "base_url": base_url,
            "prompt_version": "signature_mapping_v1",
            "baseline_signature": {
                "env": baseline_signature.get("env"),
                "sys": baseline_signature.get("sys"),
            },
            "generated_signature": {
                "env": generated_signature.get("env"),
                "sys": generated_signature.get("sys"),
            },
            "raw_mapping": None,
            "mapping": {
                "env": {},
                "sys": {},
                "unmapped_baseline_env": sorted((baseline_signature.get("env") or {}).keys()),
                "unmapped_generated_env": sorted((generated_signature.get("env") or {}).keys()),
                "unmapped_baseline_sys": sorted((baseline_signature.get("sys") or {}).keys()),
                "unmapped_generated_sys": sorted((generated_signature.get("sys") or {}).keys()),
                "complete": False,
                "confidence": None,
                "explanation": "Academic Cloud mapping request failed.",
            },
            "validation_errors": [str(exc)],
            "usable": False,
            "response_text": None,
            "api_attempts": retries + 1,
        }
        append_jsonl(mapping_file, record)
        return record
    response_text = extract_response_text(response)
    raw_mapping = extract_json_object(response_text)
    validated, errors = validate_mapping(raw_mapping, baseline_signature, generated_signature)
    record = {
        "mapping_key": key,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "api_status": "success",
        "model": model,
        "base_url": base_url,
        "prompt_version": "signature_mapping_v1",
        "baseline_signature": {
            "env": baseline_signature.get("env"),
            "sys": baseline_signature.get("sys"),
        },
        "generated_signature": {
            "env": generated_signature.get("env"),
            "sys": generated_signature.get("sys"),
        },
        "raw_mapping": raw_mapping,
        "mapping": validated,
        "validation_errors": errors,
        "usable": not errors and validated.get("complete") is True,
        "response_text": response_text,
        "api_attempts": (response.get("_respect_api_metadata") or {}).get("attempts"),
        "api_retried": (response.get("_respect_api_metadata") or {}).get("retried"),
    }
    append_jsonl(mapping_file, record)
    return record


def identity_mapping(signature: dict[str, Any]) -> dict[str, Any]:
    return {
        "env": {name: name for name in (signature.get("env") or {})},
        "sys": {name: name for name in (signature.get("sys") or {})},
        "unmapped_baseline_env": [],
        "unmapped_generated_env": [],
        "unmapped_baseline_sys": [],
        "unmapped_generated_sys": [],
        "complete": True,
        "confidence": "strict",
        "explanation": "Exact signature match.",
    }


def generated_to_baseline(mapping: dict[str, Any]) -> dict[str, str]:
    reverse: dict[str, str] = {}
    for owner in ("env", "sys"):
        for baseline_name, generated_name in (mapping.get(owner) or {}).items():
            reverse[generated_name] = baseline_name
    return reverse


def apply_hoa_ap_mapping(text: str, generated_to_baseline_names: dict[str, str]) -> str:
    """Rename Spectra AP names like "leftMotor=FWD" to baseline variable names."""
    for generated_name, baseline_name in sorted(generated_to_baseline_names.items(), key=lambda item: len(item[0]), reverse=True):
        text = re.sub(
            rf'"{re.escape(generated_name)}=',
            f'"{baseline_name}=',
            text,
        )
    return text
