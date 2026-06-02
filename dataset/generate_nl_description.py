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
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from prompts import DEFAULT_NL_DESCRIPTION_SYSTEM_PROMPT, PROMPTS


DEFAULT_BASE_URL = "https://chat-ai.academiccloud.de/v1"
DEFAULT_OUTPUT_DIR = "dataset/nl_descriptions"
DEFAULT_ACCEPTED_MANIFEST = "dataset/accepted/accepted_manifest.jsonl"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate natural-language descriptions via Academic Cloud.")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--prompt", help="Prompt text to send as the user message for --single-run.")
    source.add_argument("--prompt-file", help="Path to a text file containing the user prompt for --single-run.")
    parser.add_argument("--prompt-name", choices=sorted(PROMPTS), default="spectra_to_english_v1", help="Name of a prompt from dataset/prompts.py.")
    parser.add_argument("--accepted-manifest", default=DEFAULT_ACCEPTED_MANIFEST, help="Path to accepted Spectra manifest JSONL.")
    parser.add_argument("--single-run", action="store_true", help="Run only one standalone prompt request instead of the dataset mode.")
    parser.add_argument("--resume", action="store_true", help="Skip dataset entries that already have a successful matching description.")
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
    return parser.parse_args()


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


def render_prompt(template: str, spectra_code: str | None = None) -> str:
    if "{spectra_code}" in template:
        if spectra_code is None:
            raise RuntimeError("Selected prompt requires Spectra code, but no Spectra file was provided.")
        return template.format(spectra_code=spectra_code)
    return template


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


def load_completed_generation_keys(output_dir: Path) -> set[str]:
    manifest_file = output_dir / "descriptions.jsonl"
    keys: set[str] = set()
    for record in load_jsonl(manifest_file):
        if record.get("api_status") == "success" and record.get("generation_config_key"):
            keys.add(record["generation_config_key"])
    return keys


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
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
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
) -> dict[str, Any]:
    response_id = metadata["description_id"]
    responses_dir = output_dir / "responses"
    raw_dir = output_dir / "raw_responses"
    responses_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    response_file = responses_dir / f"{response_id}.txt"
    raw_response_file = raw_dir / f"{response_id}.json"
    manifest_file = output_dir / "descriptions.jsonl"

    response_file.write_text(response_text, encoding="utf-8")
    raw_response_file.write_text(json.dumps(raw_response, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    manifest_record = {
        **metadata,
        "response_file": str(response_file),
        "raw_response_file": str(raw_response_file),
        "response_sha256": sha256_text(response_text),
    }
    with manifest_file.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(manifest_record, sort_keys=True) + "\n")
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
    return write_outputs(
        output_dir=Path(args.output_dir),
        response_text=response_text,
        raw_response=response,
        metadata=metadata,
    )


def run_single(args: argparse.Namespace, api_key: str) -> int:
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
    )
    print(json.dumps(manifest_record, indent=2, sort_keys=True))
    return 0


def run_dataset(args: argparse.Namespace, api_key: str) -> int:
    accepted_records = load_jsonl(Path(args.accepted_manifest))
    if not accepted_records:
        print(f"No accepted records found in {args.accepted_manifest}.", file=sys.stderr)
        return 2

    completed_keys = load_completed_generation_keys(Path(args.output_dir)) if args.resume else set()
    template = PROMPTS[args.prompt_name]
    processed = 0
    skipped = 0
    errors = 0

    for record in accepted_records:
        if args.limit is not None and processed >= args.limit:
            break

        spectra_file = Path(record["accepted_file"])
        spectra_code = spectra_file.read_text(encoding="utf-8")
        user_prompt = render_prompt(template, spectra_code=spectra_code)
        spectra_sha256 = sha256_text(spectra_code)
        config_key = generation_config_key(
            dataset_id=record.get("dataset_id"),
            prompt_name=args.prompt_name,
            prompt_sha256=sha256_text(user_prompt),
            system_prompt_sha256=sha256_text(args.system_prompt),
            model=args.model,
            temperature=args.temperature,
            top_p=args.top_p,
            max_tokens=args.max_tokens,
        )
        if config_key in completed_keys:
            skipped += 1
            print(f"[skip] {record.get('dataset_id')} already generated for current model/settings/prompt", file=sys.stderr)
            continue

        print(f"[generate] {record.get('dataset_id')} from {spectra_file}", file=sys.stderr)
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
            )
            completed_keys.add(config_key)
            processed += 1
        except Exception as exc:
            errors += 1
            print(f"[error] {record.get('dataset_id')}: {exc}", file=sys.stderr)

    summary = {
        "accepted_records": len(accepted_records),
        "generated": processed,
        "skipped": skipped,
        "errors": errors,
        "output_dir": args.output_dir,
        "model": args.model,
        "prompt_name": args.prompt_name,
        "temperature": args.temperature,
        "top_p": args.top_p,
        "max_tokens": args.max_tokens,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if errors == 0 else 1


def main() -> int:
    load_dotenv(Path(".env"))
    args = parse_args()

    api_key = os.environ.get("ACADEMIC_CLOUD_API_KEY")
    if not api_key:
        print("Missing ACADEMIC_CLOUD_API_KEY. Add it to .env or the environment.", file=sys.stderr)
        return 2
    if not args.model:
        print("Missing model. Set ACADEMIC_CLOUD_MODEL in .env or pass --model.", file=sys.stderr)
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
