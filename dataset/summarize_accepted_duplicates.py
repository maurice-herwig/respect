#!/usr/bin/env python3
"""Summarize duplicate Spectra contents in the accepted dataset manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


DEFAULT_ACCEPTED_MANIFEST = "dataset/accepted/accepted_manifest.jsonl"
REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize duplicates in accepted Spectra records.")
    parser.add_argument(
        "--accepted-manifest",
        default=DEFAULT_ACCEPTED_MANIFEST,
        help="Path to accepted_manifest.jsonl.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=10,
        help="Number of largest duplicate groups to print.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON instead of a text summary.",
    )
    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"Accepted manifest not found: {path}")

    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in {path} at line {line_number}: {exc}") from exc
    return records


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_repo_path(path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute() or path.exists():
        return path
    return REPO_ROOT / path


def content_hash_for_record(record: dict[str, Any]) -> tuple[str, bool]:
    content_sha256 = record.get("content_sha256")
    if isinstance(content_sha256, str) and content_sha256:
        return content_sha256, False

    accepted_file = record.get("accepted_file")
    if not isinstance(accepted_file, str) or not accepted_file:
        raise ValueError(f"Record without content_sha256 also has no accepted_file: {record.get('dataset_id')}")

    return sha256_file(resolve_repo_path(accepted_file)), True


def percent(count: int, total: int) -> float:
    if total == 0:
        return 0.0
    return 100.0 * count / total


def summarize(records: list[dict[str, Any]], top: int) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    hashes_computed_from_files = 0

    for record in records:
        content_hash, computed_from_file = content_hash_for_record(record)
        if computed_from_file:
            hashes_computed_from_files += 1
        groups[content_hash].append(record)

    total_records = len(records)
    unique_contents = len(groups)
    duplicate_groups = [items for items in groups.values() if len(items) > 1]
    duplicate_records = sum(len(items) for items in duplicate_groups)
    redundant_records = total_records - unique_contents
    group_size_counts = Counter(len(items) for items in groups.values())

    largest_groups = sorted(duplicate_groups, key=len, reverse=True)[:top]
    top_duplicate_groups = []
    for items in largest_groups:
        representative = items[0]
        top_duplicate_groups.append(
            {
                "content_sha256": representative.get("content_sha256") or content_hash_for_record(representative)[0],
                "count": len(items),
                "representative_dataset_id": representative.get("dataset_id"),
                "representative_file": representative.get("accepted_file"),
                "repositories": sorted(
                    {
                        item["repository_full_name"]
                        for item in items
                        if isinstance(item.get("repository_full_name"), str)
                    }
                ),
            }
        )

    return {
        "total_records": total_records,
        "unique_contents": unique_contents,
        "duplicate_groups": len(duplicate_groups),
        "duplicate_records": duplicate_records,
        "redundant_records": redundant_records,
        "unique_records_percent": percent(unique_contents, total_records),
        "duplicate_records_percent": percent(duplicate_records, total_records),
        "redundant_records_percent": percent(redundant_records, total_records),
        "hashes_computed_from_files": hashes_computed_from_files,
        "group_size_distribution": [
            {"group_size": size, "groups": count}
            for size, count in sorted(group_size_counts.items())
        ],
        "top_duplicate_groups": top_duplicate_groups,
    }


def print_text_summary(summary: dict[str, Any], manifest_path: Path) -> None:
    print("Accepted Spectra Duplicate Summary")
    print(f"Manifest: {manifest_path}")
    print()
    print(f"Total accepted records: {summary['total_records']}")
    print(f"Unique Spectra contents: {summary['unique_contents']} ({summary['unique_records_percent']:.2f}%)")
    print(f"Duplicate groups: {summary['duplicate_groups']}")
    print(f"Records in duplicate groups: {summary['duplicate_records']} ({summary['duplicate_records_percent']:.2f}%)")
    print(f"Redundant duplicate records: {summary['redundant_records']} ({summary['redundant_records_percent']:.2f}%)")
    if summary["hashes_computed_from_files"]:
        print(f"Hashes computed from files: {summary['hashes_computed_from_files']}")

    print()
    print("Group size distribution:")
    for item in summary["group_size_distribution"]:
        print(f"  size {item['group_size']}: {item['groups']} group(s)")

    if not summary["top_duplicate_groups"]:
        return

    print()
    print("Largest duplicate groups:")
    for index, item in enumerate(summary["top_duplicate_groups"], start=1):
        repositories = ", ".join(item["repositories"]) if item["repositories"] else "unknown"
        print(f"  {index}. count={item['count']} sha256={item['content_sha256']}")
        print(f"     representative: {item['representative_dataset_id']}")
        print(f"     file: {item['representative_file']}")
        print(f"     repositories: {repositories}")


def main() -> int:
    args = parse_args()
    manifest_path = resolve_repo_path(args.accepted_manifest)
    records = load_jsonl(manifest_path)
    summary = summarize(records, args.top)

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print_text_summary(summary, manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
