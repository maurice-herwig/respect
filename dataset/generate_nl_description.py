#!/usr/bin/env python3
"""
Standalone Academic Cloud/GWD chat-completion call for generating natural-language text.

This first version is intentionally not connected to the Spectra dataset yet. It
takes a prompt from the command line or a prompt file, calls an OpenAI-compatible
Academic Cloud endpoint, and stores the generated text plus request metadata.
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

from prompts import DEFAULT_NL_DESCRIPTION_SYSTEM_PROMPT


DEFAULT_BASE_URL = "https://chat-ai.academiccloud.de/v1"
DEFAULT_OUTPUT_DIR = "dataset/nl_descriptions"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate one natural-language description via Academic Cloud.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--prompt", help="Prompt text to send as the user message.")
    source.add_argument("--prompt-file", help="Path to a text file containing the user prompt.")
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
    if args.prompt is not None:
        return args.prompt, None
    prompt_path = Path(args.prompt_file)
    return prompt_path.read_text(encoding="utf-8"), str(prompt_path)


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

    user_prompt, prompt_file = read_prompt(args)
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

    description_id = sha256_text(
        json.dumps(
            {
                "model": args.model,
                "system_prompt": args.system_prompt,
                "user_prompt_sha256": sha256_text(user_prompt),
                "request_started_at": request_started_at,
            },
            sort_keys=True,
        )
    )[:24]
    metadata = {
        "description_id": description_id,
        "provider": "academic_cloud_gwd",
        "base_url": args.base_url,
        "model": args.model,
        "temperature": args.temperature,
        "top_p": args.top_p,
        "max_tokens": args.max_tokens,
        "used_model_default_temperature": args.temperature is None,
        "used_model_default_top_p": args.top_p is None,
        "used_model_default_max_tokens": args.max_tokens is None,
        "system_prompt_sha256": sha256_text(args.system_prompt),
        "user_prompt_sha256": sha256_text(user_prompt),
        "prompt_file": prompt_file,
        "request_started_at": request_started_at,
        "response_received_at": response_received_at,
        "duration_ms": duration_ms,
        "api_status": "success",
        "finish_reason": (response.get("choices") or [{}])[0].get("finish_reason"),
        "usage": response.get("usage"),
    }
    manifest_record = write_outputs(
        output_dir=Path(args.output_dir),
        response_text=response_text,
        raw_response=response,
        metadata=metadata,
    )
    print(json.dumps(manifest_record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        raise SystemExit(130)
