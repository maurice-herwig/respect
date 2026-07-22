#!/usr/bin/env python3
"""
Generate natural-language descriptions with the Academic Cloud/GWD API.

The main mode reads accepted Spectra files from the dataset manifest and sends
one independent chat-completion request per file. A standalone prompt mode is
kept for API tests.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from prompts import DEFAULT_NL_DESCRIPTION_SYSTEM_PROMPT, PROMPTS


DEFAULT_BASE_URL = "https://chat-ai.academiccloud.de/v1"
DEFAULT_OUTPUT_DIR = "dataset/nl_descriptions"
DEFAULT_ACCEPTED_MANIFEST = "dataset/accepted/accepted_manifest.jsonl"
SIGNATURE_FILENAME_TAG = "sig"
LOGGER = logging.getLogger("generate_nl_description")
SPEC_RE = re.compile(r"^\s*(?:spec|module)\s+([A-Za-z_][A-Za-z0-9_]*)\b", re.MULTILINE)
TYPE_RE = re.compile(r"^\s*type\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+?)\s*;", re.MULTILINE)
DECLARATION_RE = re.compile(r"^\s*(env|sys)\s+(.+?)\s+([A-Za-z_][A-Za-z0-9_]*)\s*;", re.MULTILINE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate natural-language descriptions via Academic Cloud.")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--prompt", help="Prompt text to send as the user message for --single-run.")
    source.add_argument("--prompt-file", help="Path to a text file containing the user prompt for --single-run.")
    parser.add_argument("--prompt-name", choices=sorted(PROMPTS), default="spectra_to_english_v1", help="Name of a prompt from prompts.py.")
    parser.add_argument("--accepted-manifest", default=DEFAULT_ACCEPTED_MANIFEST, help="Path to accepted Spectra manifest JSONL.")
    parser.add_argument(
        "--include-signature",
        action="store_true",
        help="Ask the model to include the exact environment and system variable signature in the description.",
    )
    parser.add_argument(
        "--dedupe-by-content",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Process only one accepted record per Spectra content_sha256 value. Enabled by default.",
    )
    parser.add_argument("--single-run", action="store_true", help="Run only one standalone prompt request instead of the dataset mode.")
    parser.add_argument("--resume", action="store_true", help="Deprecated compatibility flag. Matching successful descriptions are skipped by default.")
    parser.add_argument("--force", action="store_true", help="Regenerate descriptions even if a matching successful description already exists.")
    parser.add_argument(
        "--refresh-before",
        default=None,
        help="ISO timestamp. Existing descriptions before this timestamp are treated as stale and regenerated.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of dataset entries to process.")
    parser.add_argument("--system-prompt", default=DEFAULT_NL_DESCRIPTION_SYSTEM_PROMPT, help="System message for the model.")
    parser.add_argument("--model", default=os.environ.get("ACADEMIC_CLOUD_MODEL"), help="Model name.")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("ACADEMIC_CLOUD_BASE_URL", DEFAULT_BASE_URL),
        help="OpenAI-compatible API base URL.",
    )
    parser.add_argument("--temperature", type=float, default=None, help="Override model default temperature.")
    parser.add_argument("--top-p", type=float, default=None, help="Override model default top_p.")
    parser.add_argument("--max-tokens", type=int, default=None, help="Override model default max_tokens.")
    parser.add_argument("--timeout", type=float, default=120.0, help="HTTP timeout in seconds.")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--keep-raw-responses", action="store_true", help="Store full raw API responses as JSON files.")
    parser.add_argument("--log-file", default=None, help="Optional log file path.")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        help="Logging verbosity.",
    )
    return parser.parse_args()


def configure_logging(log_level: str, log_file: str | None) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_path, encoding="utf-8"))

    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
    )


def load_dotenv(path: Path) -> None:
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


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def chat_completions_url(base_url: str) -> str:
    return base_url.rstrip("/") + "/chat/completions"


def read_prompt(args: argparse.Namespace) -> tuple[str, str | None]:
    if args.prompt_name is not None:
        return PROMPTS[args.prompt_name], None
    if args.prompt is not None:
        return args.prompt, None
    prompt_path = Path(args.prompt_file)
    return prompt_path.read_text(encoding="utf-8"), str(prompt_path)


def strip_line_comments(source: str) -> str:
    return "\n".join(line.split("//", 1)[0] for line in source.splitlines())


def extract_spectra_signature(spectra_code: str) -> dict[str, Any]:
    source = strip_line_comments(spectra_code)
    spec_match = SPEC_RE.search(source)
    type_defs = [
        {"name": match.group(1), "domain": " ".join(match.group(2).strip().split())}
        for match in TYPE_RE.finditer(source)
    ]
    env: list[dict[str, str]] = []
    sys_vars: list[dict[str, str]] = []

    for match in DECLARATION_RE.finditer(source):
        owner, type_expr, variable = match.group(1), " ".join(match.group(2).strip().split()), match.group(3)
        target = env if owner == "env" else sys_vars
        target.append({"name": variable, "type": type_expr})

    return {
        "spec_name": spec_match.group(1) if spec_match else None,
        "type_definitions": type_defs,
        "environment": env,
        "system": sys_vars,
    }


def format_signature_lines(variables: list[dict[str, str]]) -> list[str]:
    if not variables:
        return ["- none"]
    return [f"- {variable['name']}: {variable['type']}" for variable in variables]


def build_signature_prompt_section(signature: dict[str, Any]) -> str:
    lines = [
        "Additional fixed-interface requirement:",
        "Include the following exact interface in the English requirements description.",
        "Preserve every variable name and domain exactly. State which variables are environment-controlled inputs and which are system-controlled outputs. Do not rename variables and do not introduce additional variables.",
    ]
    if signature.get("spec_name"):
        lines.extend(["", f"Specification name: {signature['spec_name']}"])
    type_defs = signature.get("type_definitions") or []
    if type_defs:
        lines.append("")
        lines.append("Named domains:")
        lines.extend(f"- {type_def['name']}: {type_def['domain']}" for type_def in type_defs)
    lines.append("")
    lines.append("Environment variables:")
    lines.extend(format_signature_lines(signature.get("environment") or []))
    lines.append("")
    lines.append("System variables:")
    lines.extend(format_signature_lines(signature.get("system") or []))
    return "\n".join(lines)


def render_prompt(template: str, spectra_code: str | None = None, signature_section: str | None = None) -> str:
    if "{spectra_code}" in template:
        if spectra_code is None:
            raise RuntimeError("Selected prompt requires Spectra code, but no Spectra file was provided.")
        rendered = template.format(spectra_code=spectra_code)
    else:
        rendered = template
    if signature_section:
        rendered = rendered.rstrip() + "\n\n" + signature_section + "\n"
    return rendered


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not path.is_file():
        return records
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            records.append(json.loads(line))
    return records


def dedupe_accepted_records_by_content(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()

    for record in records:
        content_sha256 = record.get("content_sha256")
        if not content_sha256:
            accepted_file = Path(record["accepted_file"])
            content_sha256 = sha256_text(accepted_file.read_text(encoding="utf-8"))

        if content_sha256 in seen:
            continue

        seen.add(content_sha256)
        deduped.append(record)

    return deduped, len(records) - len(deduped)


def generation_config_key(
    *,
    dataset_id: str | None,
    prompt_name: str | None,
    prompt_sha256: str,
    system_prompt_sha256: str,
    model: str,
    temperature: float | None,
    top_p: float | None,
    max_tokens: int | None,
) -> str:
    return sha256_text(
        json.dumps(
            {
                "dataset_id": dataset_id,
                "prompt_name": prompt_name,
                "prompt_sha256": prompt_sha256,
                "system_prompt_sha256": system_prompt_sha256,
                "model": model,
                "temperature": temperature,
                "top_p": top_p,
                "max_tokens": max_tokens,
            },
            sort_keys=True,
        )
    )


def content_generation_key(
    *,
    spectra_sha256: str,
    prompt_name: str | None,
    prompt_sha256: str,
    system_prompt_sha256: str,
    model: str,
    temperature: float | None,
    top_p: float | None,
    max_tokens: int | None,
) -> str:
    return sha256_text(
        json.dumps(
            {
                "source_spectra_sha256": spectra_sha256,
                "prompt_name": prompt_name,
                "prompt_sha256": prompt_sha256,
                "system_prompt_sha256": system_prompt_sha256,
                "model": model,
                "temperature": temperature,
                "top_p": top_p,
                "max_tokens": max_tokens,
            },
            sort_keys=True,
        )
    )


def record_is_fresh(record: dict[str, Any], refresh_before: datetime | None) -> bool:
    if refresh_before is None:
        return True
    timestamp = record.get("response_received_at") or record.get("request_started_at")
    if not timestamp:
        return False
    try:
        parsed = parse_iso_datetime(timestamp)
    except ValueError:
        return False
    return parsed is not None and parsed >= refresh_before


def load_completed_generation_keys(output_dir: Path, refresh_before: datetime | None = None) -> set[str]:
    manifest_file = output_dir / "descriptions.jsonl"
    keys: set[str] = set()
    for record in load_jsonl(manifest_file):
        if (
            record.get("api_status") == "success"
            and record.get("generation_config_key")
            and record_is_fresh(record, refresh_before)
        ):
            keys.add(record["generation_config_key"])
    return keys


def load_completed_content_generation_keys(output_dir: Path, refresh_before: datetime | None = None) -> set[str]:
    manifest_file = output_dir / "descriptions.jsonl"
    keys: set[str] = set()
    for record in load_jsonl(manifest_file):
        if record.get("api_status") != "success" or not record_is_fresh(record, refresh_before):
            continue

        spectra_sha256 = record.get("source_spectra_sha256")
        prompt_sha256 = record.get("user_prompt_sha256")
        system_prompt_sha256 = record.get("system_prompt_sha256")
        model = record.get("model")
        if not all(isinstance(value, str) and value for value in (spectra_sha256, prompt_sha256, system_prompt_sha256, model)):
            continue

        keys.add(
            content_generation_key(
                spectra_sha256=spectra_sha256,
                prompt_name=record.get("prompt_name"),
                prompt_sha256=prompt_sha256,
                system_prompt_sha256=system_prompt_sha256,
                model=model,
                temperature=record.get("temperature"),
                top_p=record.get("top_p"),
                max_tokens=record.get("max_tokens"),
            )
        )
    return keys


def safe_path_part(value: str, max_length: int = 120) -> str:
    safe = re.sub(r"[^A-Za-z0-9._=-]+", "_", value).strip("_")
    return (safe or "value")[:max_length]


def generation_variant_name(
    *,
    model: str,
    prompt_name: str | None,
    temperature: float | None,
    top_p: float | None,
    max_tokens: int | None,
    generation_config_key: str,
    filename_tag: str | None = None,
) -> str:
    parts = [
        f"model={safe_path_part(model, 80)}",
        f"prompt={safe_path_part(prompt_name or 'adhoc', 60)}",
    ]
    if filename_tag:
        parts.append(f"tag={safe_path_part(filename_tag, 60)}")
    parts.extend(
        [
            f"temperature={temperature if temperature is not None else 'default'}",
            f"top_p={top_p if top_p is not None else 'default'}",
            f"max_tokens={max_tokens if max_tokens is not None else 'default'}",
            f"id={generation_config_key[:12]}",
        ]
    )
    return "__".join(parts)


def response_path_for_spectra_file(
    output_dir: Path,
    spectra_file: str | None,
    variant_name: str | None = None,
) -> Path | None:
    if spectra_file is None:
        return None

    source = Path(spectra_file)
    parts = source.parts
    try:
        files_index = parts.index("files")
    except ValueError:
        return None

    relative_parts = parts[files_index + 1 :]
    if not relative_parts:
        return None

    source_relative_path = Path(*relative_parts)
    spectra_name_dir = source_relative_path.with_suffix("")
    file_name = f"{variant_name or source_relative_path.stem}.txt"
    relative_path = spectra_name_dir / file_name
    return output_dir / "responses" / relative_path


def call_academic_cloud(
    *,
    api_key: str,
    base_url: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float | None,
    top_p: float | None,
    max_tokens: int | None,
    timeout: float,
) -> dict[str, Any]:
    LOGGER.debug("Preparing Academic Cloud request: model=%s base_url=%s", model, base_url)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    if temperature is not None:
        payload["temperature"] = temperature
    if top_p is not None:
        payload["top_p"] = top_p
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        chat_completions_url(base_url),
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        LOGGER.info("Sending Academic Cloud request to %s", chat_completions_url(base_url))
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
            LOGGER.info("Received Academic Cloud response")
            return result
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        LOGGER.error("Academic Cloud API request failed with HTTP %s: %s", exc.code, details)
        raise RuntimeError(f"Academic Cloud API request failed with HTTP {exc.code}: {details}") from exc


def extract_response_text(response: dict[str, Any]) -> str:
    choices = response.get("choices") or []
    if not choices:
        raise RuntimeError("Academic Cloud API response did not contain choices.")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if not isinstance(content, str):
        raise RuntimeError("Academic Cloud API response did not contain message.content.")
    return content


def write_outputs(
    *,
    output_dir: Path,
    response_text: str,
    raw_response: dict[str, Any],
    metadata: dict[str, Any],
    response_file: Path | None = None,
    keep_raw_response: bool = False,
) -> dict[str, Any]:
    response_id = metadata["description_id"]
    responses_dir = output_dir / "responses"
    raw_dir = output_dir / "raw_responses"
    responses_dir.mkdir(parents=True, exist_ok=True)

    if response_file is None:
        response_file = responses_dir / f"{response_id}.txt"
    else:
        response_file.parent.mkdir(parents=True, exist_ok=True)
    raw_response_file = raw_dir / f"{response_id}.json" if keep_raw_response else None
    manifest_file = output_dir / "descriptions.jsonl"

    response_file.write_text(response_text, encoding="utf-8")
    if raw_response_file is not None:
        raw_dir.mkdir(parents=True, exist_ok=True)
        raw_response_file.write_text(json.dumps(raw_response, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    LOGGER.info("Wrote response text to %s", response_file)
    if raw_response_file is not None:
        LOGGER.debug("Wrote raw response to %s", raw_response_file)

    manifest_record = {
        **metadata,
        "response_file": str(response_file),
        "raw_response_file": str(raw_response_file) if raw_response_file else None,
        "raw_response_stored": raw_response_file is not None,
        "response_sha256": sha256_text(response_text),
    }
    with manifest_file.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(manifest_record, sort_keys=True) + "\n")
    LOGGER.info("Appended description metadata to %s", manifest_file)
    return manifest_record


def generate_one(
    *,
    args: argparse.Namespace,
    api_key: str,
    user_prompt: str,
    prompt_name: str | None,
    prompt_file: str | None,
    dataset_record: dict[str, Any] | None,
    spectra_file: str | None,
    spectra_sha256: str | None,
    source_signature: dict[str, Any] | None = None,
) -> dict[str, Any]:
    request_started_at = utc_now()
    started = time.perf_counter()
    response = call_academic_cloud(
        api_key=api_key,
        base_url=args.base_url,
        model=args.model,
        system_prompt=args.system_prompt,
        user_prompt=user_prompt,
        temperature=args.temperature,
        top_p=args.top_p,
        max_tokens=args.max_tokens,
        timeout=args.timeout,
    )
    response_received_at = utc_now()
    duration_ms = int((time.perf_counter() - started) * 1000)
    response_text = extract_response_text(response)

    prompt_sha256 = sha256_text(user_prompt)
    system_prompt_sha = sha256_text(args.system_prompt)
    dataset_id = dataset_record.get("dataset_id") if dataset_record else None
    config_key = generation_config_key(
        dataset_id=dataset_id,
        prompt_name=prompt_name,
        prompt_sha256=prompt_sha256,
        system_prompt_sha256=system_prompt_sha,
        model=args.model,
        temperature=args.temperature,
        top_p=args.top_p,
        max_tokens=args.max_tokens,
    )
    description_id = config_key[:24]
    metadata = {
        "description_id": description_id,
        "generation_config_key": config_key,
        "provider": "academic_cloud_gwd",
        "base_url": args.base_url,
        "model": args.model,
        "temperature": args.temperature,
        "top_p": args.top_p,
        "max_tokens": args.max_tokens,
        "used_model_default_temperature": args.temperature is None,
        "used_model_default_top_p": args.top_p is None,
        "used_model_default_max_tokens": args.max_tokens is None,
        "system_prompt_sha256": system_prompt_sha,
        "user_prompt_sha256": prompt_sha256,
        "prompt_name": prompt_name,
        "prompt_file": prompt_file,
        "include_signature": args.include_signature,
        "signature_filename_tag": SIGNATURE_FILENAME_TAG if args.include_signature else None,
        "source_signature": source_signature,
        "dataset_id": dataset_id,
        "source_spectra_file": spectra_file,
        "source_spectra_sha256": spectra_sha256,
        "source_repository_full_name": dataset_record.get("repository_full_name") if dataset_record else None,
        "source_path": dataset_record.get("path") if dataset_record else None,
        "thread_isolation": "independent_chat_completion_request",
        "request_started_at": request_started_at,
        "response_received_at": response_received_at,
        "duration_ms": duration_ms,
        "api_status": "success",
        "finish_reason": (response.get("choices") or [{}])[0].get("finish_reason"),
        "usage": response.get("usage"),
    }
    variant_name = generation_variant_name(
        model=args.model,
        prompt_name=prompt_name,
        temperature=args.temperature,
        top_p=args.top_p,
        max_tokens=args.max_tokens,
        generation_config_key=config_key,
        filename_tag=SIGNATURE_FILENAME_TAG if args.include_signature else None,
    )
    return write_outputs(
        output_dir=Path(args.output_dir),
        response_text=response_text,
        raw_response=response,
        metadata=metadata,
        response_file=response_path_for_spectra_file(Path(args.output_dir), spectra_file, variant_name),
        keep_raw_response=args.keep_raw_responses,
    )


def run_single(args: argparse.Namespace, api_key: str) -> int:
    if args.include_signature:
        LOGGER.error("--include-signature is only supported in dataset mode, where a source Spectra file is available.")
        return 2
    if args.prompt_name and args.prompt is None and args.prompt_file is None:
        user_prompt = render_prompt(PROMPTS[args.prompt_name])
        prompt_file = None
    else:
        user_prompt, prompt_file = read_prompt(args)
    manifest_record = generate_one(
        args=args,
        api_key=api_key,
        user_prompt=user_prompt,
        prompt_name=args.prompt_name,
        prompt_file=prompt_file,
        dataset_record=None,
        spectra_file=None,
        spectra_sha256=None,
        source_signature=None,
    )
    print(json.dumps(manifest_record, indent=2, sort_keys=True))
    return 0


def run_dataset(args: argparse.Namespace, api_key: str) -> int:
    accepted_records = load_jsonl(Path(args.accepted_manifest))
    if not accepted_records:
        LOGGER.error("No accepted records found in %s.", args.accepted_manifest)
        return 2
    original_accepted_count = len(accepted_records)
    deduplicated_records = 0
    if args.dedupe_by_content:
        accepted_records, deduplicated_records = dedupe_accepted_records_by_content(accepted_records)
        LOGGER.info(
            "[dedupe] kept %d of %d accepted records by content_sha256; removed %d duplicates",
            len(accepted_records),
            original_accepted_count,
            deduplicated_records,
        )

    refresh_before = parse_iso_datetime(args.refresh_before)
    completed_keys = set() if args.force else load_completed_generation_keys(Path(args.output_dir), refresh_before)
    completed_content_keys = (
        set() if args.force else load_completed_content_generation_keys(Path(args.output_dir), refresh_before)
    )
    template = PROMPTS[args.prompt_name]
    processed = 0
    skipped = 0
    errors = 0
    LOGGER.info(
        f"[start] accepted_records={len(accepted_records)}, original_accepted_records={original_accepted_count}, "
        f"deduplicated_records={deduplicated_records}, existing_matching_descriptions={len(completed_keys)}, "
        f"existing_matching_content_descriptions={len(completed_content_keys)}, "
        f"force={args.force}, refresh_before={refresh_before.isoformat() if refresh_before else None}"
    )

    for record in accepted_records:
        if args.limit is not None and processed >= args.limit:
            break

        spectra_file = Path(record["accepted_file"])
        spectra_code = spectra_file.read_text(encoding="utf-8")
        source_signature = extract_spectra_signature(spectra_code) if args.include_signature else None
        signature_section = build_signature_prompt_section(source_signature) if source_signature else None
        user_prompt = render_prompt(template, spectra_code=spectra_code, signature_section=signature_section)
        spectra_sha256 = sha256_text(spectra_code)
        prompt_sha256 = sha256_text(user_prompt)
        system_prompt_sha256 = sha256_text(args.system_prompt)
        config_key = generation_config_key(
            dataset_id=record.get("dataset_id"),
            prompt_name=args.prompt_name,
            prompt_sha256=prompt_sha256,
            system_prompt_sha256=system_prompt_sha256,
            model=args.model,
            temperature=args.temperature,
            top_p=args.top_p,
            max_tokens=args.max_tokens,
        )
        content_key = content_generation_key(
            spectra_sha256=spectra_sha256,
            prompt_name=args.prompt_name,
            prompt_sha256=prompt_sha256,
            system_prompt_sha256=system_prompt_sha256,
            model=args.model,
            temperature=args.temperature,
            top_p=args.top_p,
            max_tokens=args.max_tokens,
        )
        if config_key in completed_keys or content_key in completed_content_keys:
            skipped += 1
            LOGGER.info(
                "[skip] %s already generated for current model/settings/prompt/content",
                record.get("dataset_id"),
            )
            continue

        LOGGER.info("[generate] %s from %s", record.get("dataset_id"), spectra_file)
        try:
            generate_one(
                args=args,
                api_key=api_key,
                user_prompt=user_prompt,
                prompt_name=args.prompt_name,
                prompt_file=None,
                dataset_record=record,
                spectra_file=str(spectra_file),
                spectra_sha256=spectra_sha256,
                source_signature=source_signature,
            )
            completed_keys.add(config_key)
            completed_content_keys.add(content_key)
            processed += 1
        except Exception as exc:
            errors += 1
            LOGGER.exception("[error] %s: %s", record.get("dataset_id"), exc)

    summary = {
        "accepted_records": len(accepted_records),
        "original_accepted_records": original_accepted_count,
        "dedupe_by_content": args.dedupe_by_content,
        "deduplicated_records": deduplicated_records,
        "existing_matching_descriptions": len(completed_keys),
        "existing_matching_content_descriptions": len(completed_content_keys),
        "generated": processed,
        "skipped": skipped,
        "errors": errors,
        "output_dir": args.output_dir,
        "model": args.model,
        "prompt_name": args.prompt_name,
        "temperature": args.temperature,
        "top_p": args.top_p,
        "max_tokens": args.max_tokens,
        "include_signature": args.include_signature,
        "signature_filename_tag": SIGNATURE_FILENAME_TAG if args.include_signature else None,
        "force": args.force,
        "refresh_before": refresh_before.isoformat() if refresh_before else None,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if errors == 0 else 1


def main() -> int:
    load_dotenv(Path(".env"))
    args = parse_args()
    configure_logging(args.log_level, args.log_file)

    api_key = os.environ.get("ACADEMIC_CLOUD_API_KEY")
    if not api_key:
        LOGGER.error("Missing ACADEMIC_CLOUD_API_KEY. Add it to .env or the environment.")
        return 2
    if not args.model:
        LOGGER.error("Missing model. Set ACADEMIC_CLOUD_MODEL in .env or pass --model.")
        return 2

    if args.single_run or args.prompt is not None or args.prompt_file is not None:
        return run_single(args, api_key)
    return run_dataset(args, api_key)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        raise SystemExit(130)
