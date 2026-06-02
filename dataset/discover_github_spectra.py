#!/usr/bin/env python3
"""
Discover public Spectra files through the GitHub Search API.

This script performs only the discovery step. It does not download file
contents. Results are written as JSONL plus a small manifest so later dataset
pipeline steps can download, validate, and synthesize from a reproducible list.
"""

from __future__ import annotations

import argparse
import json
import os
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
    score: float | None

    @property
    def dedupe_key(self) -> str:
        return f"{self.repository_full_name}:{self.path}:{self.sha}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Discover .spectra files with the GitHub Search API.")
    parser.add_argument(
        "--output-dir",
        default="dataset/discovery",
        help="Directory for github_spectra_files.jsonl and github_spectra_manifest.json",
    )
    parser.add_argument(
        "--base-query",
        action="append",
        default=None,
        help="GitHub code-search query without size partition. Can be passed multiple times.",
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
        help="Reuse an existing JSONL output file and skip already-seen records.",
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
        score=item.get("score"),
    )


def load_seen_records(path: Path) -> set[str]:
    if not path.is_file():
        return set()

    seen: set[str] = set()
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            data = json.loads(line)
            seen.add(f"{data['repository_full_name']}:{data['path']}:{data['sha']}")
    return seen


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    load_dotenv(Path(".env"))
    output_dir = Path(args.output_dir)
    records_path = output_dir / "github_spectra_files.jsonl"
    manifest_path = output_dir / "github_spectra_manifest.json"

    base_queries = args.base_query or ["extension:spectra"]
    size_ranges = fixed_size_ranges(args.min_size, args.max_size, args.size_step)
    planned_queries = [build_query(base_query, size_range) for base_query in base_queries for size_range in size_ranges]
    if args.dry_run:
        for query in planned_queries:
            print(query)
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    headers = github_headers()
    seen = load_seen_records(records_path) if args.resume else set()
    discovered_at = datetime.now(timezone.utc).isoformat()
    progress(
        f"[start] discovery started with {len(base_queries)} base query/queries, "
        f"size={args.min_size}..{args.max_size}, max_step={args.size_step}, "
        f"target_results_per_query={args.target_results_per_query}, resume={args.resume}",
        args.quiet,
    )
    if seen:
        progress(f"[resume] loaded {len(seen)} existing record(s)", args.quiet)

    partitioned_queries: list[tuple[str, int]] = []
    for base_query in base_queries:
        progress(f"[base-query] partitioning {base_query}", args.quiet)
        partitioned_queries.extend(
            discover_adaptive_queries(
                base_query=base_query,
                minimum=args.min_size,
                maximum=args.max_size,
                initial_step=args.size_step,
                min_step=args.min_size_step,
                target_results_per_query=args.target_results_per_query,
                headers=headers,
                timeout=args.timeout,
                rate_limit_mode=args.rate_limit_mode,
                rate_limit_buffer_seconds=args.rate_limit_buffer_seconds,
                sleep_seconds=args.sleep_seconds,
                max_results_per_query=args.max_results_per_query,
                max_depth=args.max_depth,
                quiet=args.quiet,
            )
        )
        progress(
            f"[base-query] finished partitioning {base_query}; "
            f"total executable query partitions so far: {len(partitioned_queries)}",
            args.quiet,
        )

    written = 0
    duplicate_count = 0
    mode = "a" if args.resume else "w"
    progress(f"[fetch] fetching result pages for {len(partitioned_queries)} query partition(s)", args.quiet)
    with records_path.open(mode, encoding="utf-8") as output:
        for query_index, (query, total_count) in enumerate(partitioned_queries, start=1):
            pages = min((total_count + args.per_page - 1) // args.per_page, SEARCH_RESULT_LIMIT // args.per_page)
            progress(
                f"[fetch] query {query_index}/{len(partitioned_queries)}: total_count={total_count}, "
                f"pages={pages}, query={query}",
                args.quiet,
            )
            for page in range(1, pages + 1):
                progress(f"[fetch] query {query_index}/{len(partitioned_queries)} page {page}/{pages}", args.quiet)
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
                    record = record_from_item(item, query, discovered_at)
                    if record.dedupe_key in seen:
                        duplicate_count += 1
                        continue
                    seen.add(record.dedupe_key)
                    output.write(json.dumps(asdict(record), sort_keys=True) + "\n")
                    written += 1
                progress(
                    f"[fetch] totals so far: written={written}, duplicates={duplicate_count}, unique={len(seen)}",
                    args.quiet,
                )

    manifest = {
        "created_at": discovered_at,
        "github_api": SEARCH_CODE_ENDPOINT,
        "base_queries": base_queries,
        "size_ranges": [asdict(current_size_range) for current_size_range in size_ranges],
        "size_step": args.size_step,
        "min_size_step": args.min_size_step,
        "target_results_per_query": args.target_results_per_query,
        "partitioned_queries": [
            {"query": query, "total_count": total_count} for query, total_count in partitioned_queries
        ],
        "records_path": str(records_path),
        "records_written_this_run": written,
        "duplicates_skipped_this_run": duplicate_count,
        "unique_records_total": len(seen),
        "per_page": args.per_page,
        "max_results_per_query": args.max_results_per_query,
        "sleep_seconds": args.sleep_seconds,
        "timeout_seconds": args.timeout,
        "rate_limit_mode": args.rate_limit_mode,
        "rate_limit_buffer_seconds": args.rate_limit_buffer_seconds,
        "used_github_token": bool(os.environ.get("GITHUB_TOKEN")),
    }
    write_manifest(manifest_path, manifest)
    progress(
        f"[done] discovery finished: written={written}, duplicates={duplicate_count}, unique={len(seen)}",
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
