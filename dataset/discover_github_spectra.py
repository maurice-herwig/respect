#!/usr/bin/env python3
"""
Discover public Spectra files through the GitHub Search API.

For each size partition, the script searches GitHub, downloads each discovered
file, checks whether a controller can be synthesized with the local Spectra CLI,
and stores only accepted .spectra files under the dataset directory.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


GITHUB_API = "https://api.github.com"
SEARCH_CODE_ENDPOINT = f"{GITHUB_API}/search/code"
SEARCH_RESULT_LIMIT = 1000
DEFAULT_PER_PAGE = 100
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_SIZE_STEP = 1_000
DEFAULT_MIN_SIZE_STEP = 1
DEFAULT_MAX_RESULTS_PER_QUERY = 500
DEFAULT_TARGET_RESULTS_PER_QUERY = 100
DEFAULT_RATE_LIMIT_BUFFER_SECONDS = 5
DEFAULT_EXCLUDED_REPOS = ("maurice-herwig/respect",)


@dataclass(frozen=True)
class SizeRange:
    minimum: int
    maximum: int

    def query_fragment(self) -> str:
        return f"size:{self.minimum}..{self.maximum}"

    def can_split(self) -> bool:
        return self.minimum < self.maximum

    def split(self) -> tuple["SizeRange", "SizeRange"]:
        midpoint = (self.minimum + self.maximum) // 2
        return (
            SizeRange(self.minimum, midpoint),
            SizeRange(midpoint + 1, self.maximum),
        )


@dataclass
class DiscoveryRecord:
    discovery_query: str
    discovered_at: str
    name: str
    path: str
    sha: str
    html_url: str
    api_url: str
    git_url: str | None
    download_url: str | None
    repository_full_name: str
    repository_owner: str
    repository_name: str
    repository_html_url: str
    repository_api_url: str
    repository_default_branch: str | None
    repository_fork: bool | None
    github_ranking_score: float | None

    @property
    def dedupe_key(self) -> str:
        return f"{self.repository_full_name}:{self.path}:{self.sha}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Discover .spectra files with the GitHub Search API.")
    parser.add_argument(
        "--output-dir",
        default="dataset/accepted",
        help="Directory for accepted .spectra files and the accepted manifest.",
    )
    parser.add_argument(
        "--work-dir",
        default="dataset/work",
        help="Temporary directory for downloaded candidates and synthesis output.",
    )
    parser.add_argument(
        "--candidate-dir",
        default="dataset/candidates",
        help="Persistent directory for downloaded candidate .spectra files.",
    )
    parser.add_argument(
        "--manifest",
        default=None,
        help="Accepted manifest JSONL path. Defaults to <output-dir>/accepted_manifest.jsonl.",
    )
    parser.add_argument(
        "--processed-manifest",
        default=None,
        help="Processed-candidate JSONL path. Defaults to <output-dir>/processed_candidates.jsonl.",
    )
    parser.add_argument(
        "--cli-wrapper",
        default=".agents/skills/respect-method-2/scripts/run_spectra_cli.py",
        help="Path to the Spectra CLI wrapper.",
    )
    parser.add_argument(
        "--cli-timeout",
        type=float,
        default=120.0,
        help="Timeout in seconds for each Spectra synthesis attempt.",
    )
    parser.add_argument(
        "--keep-controller-output",
        action="store_true",
        help="Keep synthesized controller artifacts for accepted files.",
    )
    parser.add_argument(
        "--keep-candidate-files",
        action="store_true",
        help="Keep downloaded candidate files after they have been processed.",
    )
    parser.add_argument(
        "--base-query",
        action="append",
        default=None,
        help="GitHub code-search query without size partition. Can be passed multiple times.",
    )
    parser.add_argument(
        "--exclude-repo",
        action="append",
        default=list(DEFAULT_EXCLUDED_REPOS),
        help="GitHub repository to exclude, e.g. owner/repo. Can be passed multiple times.",
    )
    parser.add_argument(
        "--include-current-repo",
        action="store_true",
        help="Do not automatically exclude the current origin GitHub repository.",
    )
    parser.add_argument(
        "--min-size",
        type=int,
        default=1,
        help="Smallest file size in bytes to search for.",
    )
    parser.add_argument(
        "--max-size",
        type=int,
        default=500_000,
        help="Largest file size in bytes to search for.",
    )
    parser.add_argument(
        "--size-step",
        type=int,
        default=DEFAULT_SIZE_STEP,
        help="Maximum adaptive size partition width in bytes.",
    )
    parser.add_argument(
        "--min-size-step",
        type=int,
        default=DEFAULT_MIN_SIZE_STEP,
        help="Smallest adaptive size partition width in bytes.",
    )
    parser.add_argument(
        "--target-results-per-query",
        type=int,
        default=DEFAULT_TARGET_RESULTS_PER_QUERY,
        help="Target total_count for each adaptive size window.",
    )
    parser.add_argument(
        "--per-page",
        type=int,
        default=DEFAULT_PER_PAGE,
        help="Search results per page. GitHub allows at most 100.",
    )
    parser.add_argument(
        "--max-results-per-query",
        type=int,
        default=DEFAULT_MAX_RESULTS_PER_QUERY,
        help="Split size ranges until total_count is at or below this value.",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=1.0,
        help="Delay between GitHub API requests.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="HTTP timeout in seconds.",
    )
    parser.add_argument(
        "--rate-limit-mode",
        choices=("wait", "fail"),
        default="wait",
        help="Wait for GitHub rate-limit reset or fail immediately.",
    )
    parser.add_argument(
        "--rate-limit-buffer-seconds",
        type=float,
        default=DEFAULT_RATE_LIMIT_BUFFER_SECONDS,
        help="Extra seconds to wait after GitHub's rate-limit reset time.",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=24,
        help="Maximum recursive partition depth for dense size ranges.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse existing manifests and skip already-processed records.",
    )
    parser.add_argument(
        "--refresh-before",
        default=None,
        help=(
            "ISO timestamp. With --resume, processed records before this timestamp are ignored "
            "and will be downloaded and checked again."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned top-level queries without calling the GitHub API.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Disable progress messages.",
    )
    return parser.parse_args()


def github_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "respect-spectra-dataset-discovery",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def progress(message: str, quiet: bool = False) -> None:
    if not quiet:
        print(message, file=sys.stderr, flush=True)


def parse_github_repo_from_url(url: str) -> str | None:
    stripped = url.strip()
    patterns = [
        r"https://github\.com/([^/]+/[^/]+?)(?:\.git)?/?$",
        r"git@github\.com:([^/]+/[^/]+?)(?:\.git)?$",
    ]
    for pattern in patterns:
        match = re.match(pattern, stripped)
        if match:
            return match.group(1)
    return None


def detect_current_github_repo() -> str | None:
    completed = subprocess.run(
        ["git", "config", "--get", "remote.origin.url"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return None
    return parse_github_repo_from_url(completed.stdout)


def build_excluded_repos(args: argparse.Namespace) -> set[str]:
    excluded = {repo.lower() for repo in (args.exclude_repo or [])}
    if not args.include_current_repo:
        current_repo = detect_current_github_repo()
        if current_repo:
            excluded.add(current_repo.lower())
    return excluded


def apply_repo_exclusions(base_query: str, excluded_repos: set[str]) -> str:
    query = base_query
    for repo in sorted(excluded_repos):
        exclusion = f"-repo:{repo}"
        if exclusion not in query.lower():
            query = f"{query} {exclusion}"
    return query


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


def parse_rate_limit_reset(exc: urllib.error.HTTPError) -> float | None:
    remaining = exc.headers.get("X-RateLimit-Remaining")
    reset = exc.headers.get("X-RateLimit-Reset")
    if remaining != "0" or not reset:
        return None

    try:
        return float(reset)
    except ValueError:
        return None


def request_json(
    url: str,
    headers: dict[str, str],
    timeout: float,
    rate_limit_mode: str,
    rate_limit_buffer_seconds: float,
) -> dict[str, Any]:
    request = urllib.request.Request(url, headers=headers)
    while True:
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read().decode("utf-8")
                return json.loads(body)
        except urllib.error.HTTPError as exc:
            reset_at = parse_rate_limit_reset(exc)
            if exc.code == 403 and reset_at is not None and rate_limit_mode == "wait":
                wait_seconds = max(1.0, reset_at - time.time() + rate_limit_buffer_seconds)
                reset_time = datetime.fromtimestamp(reset_at, timezone.utc).isoformat()
                print(
                    f"GitHub rate limit reached. Waiting {wait_seconds:.0f}s until reset at {reset_time}.",
                    file=sys.stderr,
                )
                time.sleep(wait_seconds)
                continue

            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"GitHub API request failed with HTTP {exc.code}: {details}") from exc


def search_url(query: str, page: int, per_page: int) -> str:
    parameters = urllib.parse.urlencode(
        {
            "q": query,
            "page": page,
            "per_page": min(per_page, 100),
        }
    )
    return f"{SEARCH_CODE_ENDPOINT}?{parameters}"


def search_page(
    query: str,
    page: int,
    per_page: int,
    headers: dict[str, str],
    timeout: float,
    rate_limit_mode: str,
    rate_limit_buffer_seconds: float,
) -> dict[str, Any]:
    return request_json(
        search_url(query, page, per_page),
        headers,
        timeout,
        rate_limit_mode,
        rate_limit_buffer_seconds,
    )


def build_query(base_query: str, size_range: SizeRange) -> str:
    return f"{base_query} {size_range.query_fragment()}"


def fixed_size_ranges(minimum: int, maximum: int, step: int) -> list[SizeRange]:
    if minimum < 0:
        raise ValueError("--min-size must be >= 0")
    if maximum < minimum:
        raise ValueError("--max-size must be >= --min-size")
    if step < 1:
        raise ValueError("--size-step must be >= 1")

    ranges: list[SizeRange] = []
    start = minimum
    while start <= maximum:
        end = min(start + step - 1, maximum)
        ranges.append(SizeRange(start, end))
        start = end + 1
    return ranges


def adjust_next_size_step(
    current_step: int,
    total_count: int,
    target_results_per_query: int,
    min_step: int,
    max_step: int,
) -> int:
    if total_count > target_results_per_query:
        scaled_step = max(1, int(current_step * target_results_per_query / total_count))
        return max(min_step, min(current_step, scaled_step))

    low_density_threshold = max(1, target_results_per_query // 4)
    if total_count < low_density_threshold and current_step < max_step:
        return min(max_step, current_step * 2)

    return current_step


def discover_adaptive_queries(
    base_query: str,
    minimum: int,
    maximum: int,
    initial_step: int,
    min_step: int,
    target_results_per_query: int,
    headers: dict[str, str],
    timeout: float,
    rate_limit_mode: str,
    rate_limit_buffer_seconds: float,
    sleep_seconds: float,
    max_results_per_query: int,
    max_depth: int,
    quiet: bool,
) -> list[tuple[str, int]]:
    if minimum < 0:
        raise ValueError("--min-size must be >= 0")
    if maximum < minimum:
        raise ValueError("--max-size must be >= --min-size")
    if initial_step < 1:
        raise ValueError("--size-step must be >= 1")
    if min_step < 1:
        raise ValueError("--min-size-step must be >= 1")
    if min_step > initial_step:
        raise ValueError("--min-size-step must be <= --size-step")
    if target_results_per_query < 1:
        raise ValueError("--target-results-per-query must be >= 1")

    partitioned_queries: list[tuple[str, int]] = []
    start = minimum
    step = initial_step

    while start <= maximum:
        end = min(start + step - 1, maximum)
        current_range = SizeRange(start, end)
        query = build_query(base_query, current_range)
        progress(f"[partition] probing {query}", quiet)
        first_page = search_page(query, 1, 1, headers, timeout, rate_limit_mode, rate_limit_buffer_seconds)
        total_count = int(first_page.get("total_count", 0))
        progress(f"[partition] total_count={total_count} for {query}", quiet)
        time.sleep(sleep_seconds)

        if total_count > max_results_per_query and current_range.can_split():
            progress(
                f"[partition] splitting {current_range.query_fragment()} because total_count={total_count} "
                f"> max_results_per_query={max_results_per_query}",
                quiet,
            )
            partitioned_queries.extend(
                discover_queries(
                    base_query=base_query,
                    size_range=current_range,
                    headers=headers,
                    timeout=timeout,
                    rate_limit_mode=rate_limit_mode,
                    rate_limit_buffer_seconds=rate_limit_buffer_seconds,
                    sleep_seconds=sleep_seconds,
                    max_results_per_query=max_results_per_query,
                    max_depth=max_depth,
                    quiet=quiet,
                )
            )
        else:
            partitioned_queries.append((query, total_count))

        next_step = adjust_next_size_step(
            current_step=step,
            total_count=total_count,
            target_results_per_query=target_results_per_query,
            min_step=min_step,
            max_step=initial_step,
        )
        if next_step != step:
            progress(f"[partition] next size step adjusted from {step} to {next_step}", quiet)
        step = next_step
        start = end + 1

    return partitioned_queries


def discover_queries(
    base_query: str,
    size_range: SizeRange,
    headers: dict[str, str],
    timeout: float,
    rate_limit_mode: str,
    rate_limit_buffer_seconds: float,
    sleep_seconds: float,
    max_results_per_query: int,
    max_depth: int,
    quiet: bool,
    depth: int = 0,
) -> list[tuple[str, int]]:
    query = build_query(base_query, size_range)
    progress(f"[split depth={depth}] probing {query}", quiet)
    first_page = search_page(query, 1, 1, headers, timeout, rate_limit_mode, rate_limit_buffer_seconds)
    total_count = int(first_page.get("total_count", 0))
    progress(f"[split depth={depth}] total_count={total_count} for {query}", quiet)
    time.sleep(sleep_seconds)

    if total_count > max_results_per_query and size_range.can_split() and depth < max_depth:
        left, right = size_range.split()
        progress(
            f"[split depth={depth}] splitting {size_range.query_fragment()} into "
            f"{left.query_fragment()} and {right.query_fragment()}",
            quiet,
        )
        return [
            *discover_queries(
                base_query,
                left,
                headers,
                timeout,
                rate_limit_mode,
                rate_limit_buffer_seconds,
                sleep_seconds,
                max_results_per_query,
                max_depth,
                quiet,
                depth + 1,
            ),
            *discover_queries(
                base_query,
                right,
                headers,
                timeout,
                rate_limit_mode,
                rate_limit_buffer_seconds,
                sleep_seconds,
                max_results_per_query,
                max_depth,
                quiet,
                depth + 1,
            ),
        ]

    if total_count > max_results_per_query:
        progress(
            f"[split depth={depth}] keeping {query} with total_count={total_count}; "
            "range cannot be split further or max depth was reached",
            quiet,
        )
    return [(query, total_count)]


def record_from_item(item: dict[str, Any], query: str, discovered_at: str) -> DiscoveryRecord:
    repository = item["repository"]
    owner = repository["owner"]
    return DiscoveryRecord(
        discovery_query=query,
        discovered_at=discovered_at,
        name=item["name"],
        path=item["path"],
        sha=item["sha"],
        html_url=item["html_url"],
        api_url=item["url"],
        git_url=item.get("git_url"),
        download_url=item.get("download_url"),
        repository_full_name=repository["full_name"],
        repository_owner=owner["login"],
        repository_name=repository["name"],
        repository_html_url=repository["html_url"],
        repository_api_url=repository["url"],
        repository_default_branch=repository.get("default_branch"),
        repository_fork=repository.get("fork"),
        github_ranking_score=item.get("score"),
    )


def record_is_fresh(data: dict[str, Any], timestamp_field: str, refresh_before: datetime | None) -> bool:
    if refresh_before is None:
        return True

    timestamp = data.get(timestamp_field)
    if not timestamp:
        return False

    try:
        parsed = parse_iso_datetime(timestamp)
    except ValueError:
        return False

    return parsed is not None and parsed >= refresh_before


def load_accepted_records(path: Path, refresh_before: datetime | None = None) -> set[str]:
    if not path.is_file():
        return set()

    seen: set[str] = set()
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            data = json.loads(line)
            if not record_is_fresh(data, "accepted_at", refresh_before):
                continue
            seen.add(data["dedupe_key"])
    return seen


def load_processed_records(path: Path, refresh_before: datetime | None = None) -> set[str]:
    if not path.is_file():
        return set()

    seen: set[str] = set()
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            data = json.loads(line)
            if not record_is_fresh(data, "processed_at", refresh_before):
                continue
            seen.add(data["dedupe_key"])
    return seen


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def safe_slug(value: str, max_length: int = 80) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_")
    return slug[:max_length] or "spectra"


def dataset_id(record: DiscoveryRecord) -> str:
    digest = hashlib.sha256(record.dedupe_key.encode("utf-8")).hexdigest()[:16]
    owner_repo = safe_slug(record.repository_full_name.replace("/", "_"), 60)
    stem = safe_slug(Path(record.path).stem, 40)
    return f"{owner_repo}__{stem}__{digest}"


def accepted_file_path(accepted_dir: Path, record: DiscoveryRecord, current_id: str) -> Path:
    repo_parts = [safe_slug(part, 120) for part in record.repository_full_name.split("/")]
    path_parts = [safe_slug(part, 120) for part in Path(record.path).parts]
    relative_path = Path(*repo_parts, *path_parts)
    if relative_path.suffix.lower() != ".spectra":
        relative_path = relative_path.with_suffix(relative_path.suffix + ".spectra")

    candidate = accepted_dir / "files" / relative_path
    if candidate.exists():
        return candidate.with_name(f"{candidate.stem}__{current_id[-16:]}{candidate.suffix}")
    return candidate


def candidate_cache_file_path(candidate_dir: Path, record: DiscoveryRecord, current_id: str) -> Path:
    repo_parts = [safe_slug(part, 120) for part in record.repository_full_name.split("/")]
    path_parts = [safe_slug(part, 120) for part in Path(record.path).parts]
    relative_path = Path(*repo_parts, *path_parts)
    suffix = relative_path.suffix if relative_path.suffix else ".spectra"
    return candidate_dir / "files" / relative_path.with_name(f"{relative_path.stem}__{current_id[-16:]}{suffix}")


def decode_github_content(content_record: dict[str, Any]) -> bytes:
    encoding = content_record.get("encoding")
    content = content_record.get("content")
    if encoding == "base64" and isinstance(content, str):
        return base64.b64decode(content)
    raise RuntimeError(f"Unsupported GitHub content response encoding: {encoding!r}")


def download_file_content(
    record: DiscoveryRecord,
    headers: dict[str, str],
    timeout: float,
    rate_limit_mode: str,
    rate_limit_buffer_seconds: float,
) -> bytes:
    content_record = request_json(
        record.api_url,
        headers,
        timeout,
        rate_limit_mode,
        rate_limit_buffer_seconds,
    )
    return decode_github_content(content_record)


def fetch_repo_license(
    record: DiscoveryRecord,
    headers: dict[str, str],
    timeout: float,
    rate_limit_mode: str,
    rate_limit_buffer_seconds: float,
    license_cache: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if record.repository_full_name in license_cache:
        return license_cache[record.repository_full_name]

    license_url = f"{record.repository_api_url}/license"
    try:
        data = request_json(
            license_url,
            headers,
            timeout,
            rate_limit_mode,
            rate_limit_buffer_seconds,
        )
    except RuntimeError as exc:
        text = str(exc)
        if "HTTP 404" in text:
            info = {
                "license_found": False,
                "license_key": None,
                "license_name": None,
                "license_spdx_id": None,
                "license_url": license_url,
                "license_html_url": None,
            }
            license_cache[record.repository_full_name] = info
            return info
        raise

    license_data = data.get("license") or {}
    info = {
        "license_found": True,
        "license_key": license_data.get("key"),
        "license_name": license_data.get("name"),
        "license_spdx_id": license_data.get("spdx_id"),
        "license_url": license_data.get("url"),
        "license_html_url": data.get("html_url"),
    }
    license_cache[record.repository_full_name] = info
    return info


def run_synthesis_check(
    cli_wrapper: Path,
    spectra_file: Path,
    output_dir: Path,
    cli_timeout: float,
) -> dict[str, Any]:
    command = [
        sys.executable,
        str(cli_wrapper),
        "--input",
        str(spectra_file),
        "--synthesize",
        "--output-dir",
        str(output_dir),
        "--timeout",
        str(cli_timeout),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    stdout = completed.stdout.strip()
    if not stdout:
        return {
            "status": "error",
            "exit_code": completed.returncode,
            "raw_output": completed.stderr.strip(),
        }

    try:
        result = json.loads(stdout)
    except json.JSONDecodeError:
        return {
            "status": "error",
            "exit_code": completed.returncode,
            "raw_output": stdout,
            "stderr": completed.stderr.strip(),
        }
    return result


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def remove_candidate_file(candidate_file: Path, keep_candidate_files: bool, quiet: bool) -> None:
    if keep_candidate_files or not candidate_file.exists():
        return

    candidate_file.unlink()
    progress(f"[candidate] removed cached candidate {candidate_file}", quiet)


def process_candidate(
    item: dict[str, Any],
    query: str,
    discovered_at: str,
    headers: dict[str, str],
    args: argparse.Namespace,
    accepted_dir: Path,
    candidate_dir: Path,
    work_dir: Path,
    manifest_path: Path,
    processed_manifest_path: Path,
    accepted_keys: set[str],
    processed_keys: set[str],
    license_cache: dict[str, dict[str, Any]],
) -> str:
    record = record_from_item(item, query, discovered_at)
    if record.repository_full_name.lower() in args.excluded_repos:
        progress(f"[candidate] skipping excluded repo {record.repository_full_name}: {record.html_url}", args.quiet)
        return "excluded_repo"
    if record.dedupe_key in processed_keys:
        progress(f"[candidate] skipping already processed {record.html_url}", args.quiet)
        return "already_processed"

    current_id = dataset_id(record)
    run_dir = work_dir / current_id
    candidate_file = candidate_cache_file_path(candidate_dir, record, current_id)
    synthesis_dir = run_dir / "controller"
    run_dir.mkdir(parents=True, exist_ok=True)
    candidate_file.parent.mkdir(parents=True, exist_ok=True)
    progress(
        f"[candidate] checking {record.html_url} "
        f"(repo={record.repository_full_name}, path={record.path}, sha={record.sha[:12]})",
        args.quiet,
    )

    try:
        if candidate_file.is_file():
            content = candidate_file.read_bytes()
            progress(
                f"[download] using cached candidate {candidate_file} "
                f"({len(content)} bytes, sha256={hashlib.sha256(content).hexdigest()[:12]})",
                args.quiet,
            )
        else:
            progress(f"[download] downloading {record.api_url}", args.quiet)
            content = download_file_content(
                record,
                headers,
                args.timeout,
                args.rate_limit_mode,
                args.rate_limit_buffer_seconds,
            )
            candidate_file.write_bytes(content)
            progress(
                f"[download] saved candidate {candidate_file} "
                f"({len(content)} bytes, sha256={hashlib.sha256(content).hexdigest()[:12]})",
                args.quiet,
            )

        progress(f"[synthesis] running Spectra synthesis for {candidate_file}", args.quiet)
        result = run_synthesis_check(Path(args.cli_wrapper), candidate_file, synthesis_dir, args.cli_timeout)
        status = result.get("status")
        progress(f"[synthesis] status={status} for {record.html_url}", args.quiet)

        content_sha256 = hashlib.sha256(content).hexdigest()
        processed_record = {
            **asdict(record),
            "dataset_id": current_id,
            "dedupe_key": record.dedupe_key,
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "candidate_file": str(candidate_file),
            "content_sha256": content_sha256,
            "content_size_bytes": len(content),
            "cli_status": status,
            "cli_timeout_seconds": args.cli_timeout,
            "accepted": status == "synthesized",
        }

        if status != "synthesized":
            raw_output = str(result.get("raw_output", "")).splitlines()
            if raw_output:
                progress(f"[synthesis] first output line: {raw_output[0]}", args.quiet)
            append_jsonl(processed_manifest_path, processed_record)
            processed_keys.add(record.dedupe_key)
            remove_candidate_file(candidate_file, args.keep_candidate_files, args.quiet)
            return str(status or "rejected")

        progress(f"[license] fetching license for {record.repository_full_name}", args.quiet)
        license_info = fetch_repo_license(
            record,
            headers,
            args.timeout,
            args.rate_limit_mode,
            args.rate_limit_buffer_seconds,
            license_cache,
        )
        progress(
            f"[license] license_found={license_info['license_found']} "
            f"spdx={license_info['license_spdx_id']} for {record.repository_full_name}",
            args.quiet,
        )

        accepted_file = accepted_file_path(accepted_dir, record, current_id)
        accepted_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(candidate_file, accepted_file)
        progress(f"[accepted] stored {accepted_file}", args.quiet)

        controller_output_dir = None
        if args.keep_controller_output:
            controller_target = accepted_dir / "controllers" / current_id
            if controller_target.exists():
                shutil.rmtree(controller_target)
            shutil.copytree(synthesis_dir, controller_target)
            controller_output_dir = str(controller_target)
            progress(f"[accepted] stored controller output {controller_target}", args.quiet)

        accepted_record = {
            **asdict(record),
            "dataset_id": current_id,
            "dedupe_key": record.dedupe_key,
            "accepted_at": datetime.now(timezone.utc).isoformat(),
            "accepted_file": str(accepted_file),
            "candidate_file": str(candidate_file),
            "content_sha256": content_sha256,
            "content_size_bytes": len(content),
            "cli_status": status,
            "cli_timeout_seconds": args.cli_timeout,
            "controller_output_dir": controller_output_dir,
            **license_info,
        }
        append_jsonl(manifest_path, accepted_record)
        append_jsonl(processed_manifest_path, {**processed_record, "accepted_file": str(accepted_file), **license_info})
        accepted_keys.add(record.dedupe_key)
        processed_keys.add(record.dedupe_key)
        remove_candidate_file(candidate_file, args.keep_candidate_files, args.quiet)
        progress(f"[accepted] appended manifest record for {current_id}", args.quiet)
        return "accepted"
    finally:
        if run_dir.exists() and not args.keep_controller_output:
            shutil.rmtree(run_dir)


def process_query_results(
    query: str,
    total_count: int,
    discovered_at: str,
    headers: dict[str, str],
    args: argparse.Namespace,
    accepted_dir: Path,
    candidate_dir: Path,
    work_dir: Path,
    manifest_path: Path,
    processed_manifest_path: Path,
    accepted_keys: set[str],
    processed_keys: set[str],
    license_cache: dict[str, dict[str, Any]],
) -> dict[str, int]:
    pages = min((total_count + args.per_page - 1) // args.per_page, SEARCH_RESULT_LIMIT // args.per_page)
    stats = {
        "items": 0,
        "accepted": 0,
        "skipped": 0,
        "excluded": 0,
        "rejected": 0,
        "errors": 0,
    }
    progress(f"[fetch] total_count={total_count}, pages={pages}, query={query}", args.quiet)

    for page in range(1, pages + 1):
        progress(f"[fetch] page {page}/{pages} for {query}", args.quiet)
        data = search_page(
            query,
            page,
            args.per_page,
            headers,
            args.timeout,
            args.rate_limit_mode,
            args.rate_limit_buffer_seconds,
        )
        time.sleep(args.sleep_seconds)

        for item in data.get("items", []):
            stats["items"] += 1
            try:
                outcome = process_candidate(
                    item,
                    query,
                    discovered_at,
                    headers,
                    args,
                    accepted_dir,
                    candidate_dir,
                    work_dir,
                    manifest_path,
                    processed_manifest_path,
                    accepted_keys,
                    processed_keys,
                    license_cache,
                )
            except Exception as exc:  # Keep the crawl moving; rejected candidates are discarded.
                stats["errors"] += 1
                progress(f"[candidate] error while processing {item.get('html_url')}: {exc}", args.quiet)
                continue

            if outcome == "accepted":
                stats["accepted"] += 1
            elif outcome == "excluded_repo":
                stats["excluded"] += 1
            elif outcome == "already_processed":
                stats["skipped"] += 1
            else:
                stats["rejected"] += 1

            progress(
                "[candidate] totals for current query: "
                f"items={stats['items']}, accepted={stats['accepted']}, "
                f"rejected={stats['rejected']}, skipped={stats['skipped']}, "
                f"excluded={stats['excluded']}, errors={stats['errors']}",
                args.quiet,
            )

    progress(
        f"[fetch] finished query: items={stats['items']}, accepted={stats['accepted']}, "
        f"rejected={stats['rejected']}, skipped={stats['skipped']}, "
        f"excluded={stats['excluded']}, errors={stats['errors']}",
        args.quiet,
    )
    return stats


def main() -> int:
    args = parse_args()
    load_dotenv(Path(".env"))
    excluded_repos = build_excluded_repos(args)
    args.excluded_repos = excluded_repos
    accepted_dir = Path(args.output_dir)
    candidate_dir = Path(args.candidate_dir)
    work_dir = Path(args.work_dir)
    manifest_path = Path(args.manifest) if args.manifest else accepted_dir / "accepted_manifest.jsonl"
    processed_manifest_path = (
        Path(args.processed_manifest) if args.processed_manifest else accepted_dir / "processed_candidates.jsonl"
    )
    run_manifest_path = accepted_dir / "last_run_manifest.json"
    refresh_before = parse_iso_datetime(args.refresh_before)

    base_queries = [apply_repo_exclusions(query, excluded_repos) for query in (args.base_query or ["extension:spectra"])]
    size_ranges = fixed_size_ranges(args.min_size, args.max_size, args.size_step)
    planned_queries = [build_query(base_query, size_range) for base_query in base_queries for size_range in size_ranges]
    if args.dry_run:
        for query in planned_queries:
            print(query)
        return 0

    accepted_dir.mkdir(parents=True, exist_ok=True)
    candidate_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    headers = github_headers()
    accepted_keys = load_accepted_records(manifest_path, refresh_before) if args.resume else set()
    processed_keys = load_processed_records(processed_manifest_path, refresh_before) if args.resume else set()
    processed_keys.update(accepted_keys)
    discovered_at = datetime.now(timezone.utc).isoformat()
    progress(
        f"[start] discovery started with {len(base_queries)} base query/queries, "
        f"size={args.min_size}..{args.max_size}, max_step={args.size_step}, "
        f"target_results_per_query={args.target_results_per_query}, resume={args.resume}, "
        f"refresh_before={refresh_before.isoformat() if refresh_before else None}",
        args.quiet,
    )
    if excluded_repos:
        progress(f"[start] excluded repositories: {', '.join(sorted(excluded_repos))}", args.quiet)
    if accepted_keys:
        progress(f"[resume] loaded {len(accepted_keys)} accepted record(s)", args.quiet)
    if processed_keys:
        progress(f"[resume] loaded {len(processed_keys)} processed candidate record(s)", args.quiet)

    total_stats = {
        "queries_processed": 0,
        "items": 0,
        "accepted": 0,
        "skipped": 0,
        "excluded": 0,
        "rejected": 0,
        "errors": 0,
    }
    processed_queries: list[dict[str, Any]] = []
    license_cache: dict[str, dict[str, Any]] = {}

    for base_query in base_queries:
        progress(f"[base-query] processing {base_query}", args.quiet)
        start = args.min_size
        step = args.size_step

        while start <= args.max_size:
            end = min(start + step - 1, args.max_size)
            current_range = SizeRange(start, end)
            query = build_query(base_query, current_range)
            progress(f"[partition] probing {query}", args.quiet)
            first_page = search_page(
                query,
                1,
                1,
                headers,
                args.timeout,
                args.rate_limit_mode,
                args.rate_limit_buffer_seconds,
            )
            total_count = int(first_page.get("total_count", 0))
            progress(
                f"[partition] total_count={total_count} for {query}; downloading and testing this window before moving on",
                args.quiet,
            )
            time.sleep(args.sleep_seconds)

            leaf_queries = [(query, total_count)]
            if total_count > args.max_results_per_query and current_range.can_split():
                leaf_queries = discover_queries(
                    base_query=base_query,
                    size_range=current_range,
                    headers=headers,
                    timeout=args.timeout,
                    rate_limit_mode=args.rate_limit_mode,
                    rate_limit_buffer_seconds=args.rate_limit_buffer_seconds,
                    sleep_seconds=args.sleep_seconds,
                    max_results_per_query=args.max_results_per_query,
                    max_depth=args.max_depth,
                    quiet=args.quiet,
                )

            for leaf_query, leaf_total_count in leaf_queries:
                query_stats = process_query_results(
                    leaf_query,
                    leaf_total_count,
                    discovered_at,
                    headers,
                    args,
                    accepted_dir,
                    candidate_dir,
                    work_dir,
                    manifest_path,
                    processed_manifest_path,
                    accepted_keys,
                    processed_keys,
                    license_cache,
                )
                total_stats["queries_processed"] += 1
                for key in ("items", "accepted", "skipped", "excluded", "rejected", "errors"):
                    total_stats[key] += query_stats[key]
                processed_queries.append(
                    {
                        "query": leaf_query,
                        "total_count": leaf_total_count,
                        "stats": query_stats,
                    }
                )
                progress(
                    "[progress] run totals: "
                    f"queries={total_stats['queries_processed']}, items={total_stats['items']}, "
                    f"accepted={total_stats['accepted']}, rejected={total_stats['rejected']}, "
                    f"skipped={total_stats['skipped']}, excluded={total_stats['excluded']}, "
                    f"errors={total_stats['errors']}",
                    args.quiet,
                )

            next_step = adjust_next_size_step(
                current_step=step,
                total_count=total_count,
                target_results_per_query=args.target_results_per_query,
                min_step=args.min_size_step,
                max_step=args.size_step,
            )
            if next_step != step:
                progress(f"[partition] next size step adjusted from {step} to {next_step}", args.quiet)
            step = next_step
            start = end + 1

    manifest = {
        "created_at": discovered_at,
        "github_api": SEARCH_CODE_ENDPOINT,
        "base_queries": base_queries,
        "excluded_repositories": sorted(excluded_repos),
        "size_ranges": [asdict(current_size_range) for current_size_range in size_ranges],
        "size_step": args.size_step,
        "min_size_step": args.min_size_step,
        "target_results_per_query": args.target_results_per_query,
        "processed_queries": processed_queries,
        "accepted_manifest_path": str(manifest_path),
        "processed_manifest_path": str(processed_manifest_path),
        "accepted_dir": str(accepted_dir),
        "candidate_dir": str(candidate_dir),
        "work_dir": str(work_dir),
        "stats": total_stats,
        "accepted_records_total": len(accepted_keys),
        "processed_records_total": len(processed_keys),
        "license_cache_repositories": len(license_cache),
        "per_page": args.per_page,
        "max_results_per_query": args.max_results_per_query,
        "sleep_seconds": args.sleep_seconds,
        "timeout_seconds": args.timeout,
        "cli_timeout_seconds": args.cli_timeout,
        "rate_limit_mode": args.rate_limit_mode,
        "rate_limit_buffer_seconds": args.rate_limit_buffer_seconds,
        "refresh_before": refresh_before.isoformat() if refresh_before else None,
        "used_github_token": bool(os.environ.get("GITHUB_TOKEN")),
    }
    write_manifest(run_manifest_path, manifest)
    progress(
        f"[done] discovery finished: accepted={total_stats['accepted']}, rejected={total_stats['rejected']}, "
        f"skipped={total_stats['skipped']}, excluded={total_stats['excluded']}, errors={total_stats['errors']}",
        args.quiet,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        raise SystemExit(130)
