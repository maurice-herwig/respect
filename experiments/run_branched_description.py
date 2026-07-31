#!/usr/bin/env python3
"""Run all branched reconstruction variants for one NL description.

This is a single-description convenience wrapper around
`experiments/branched_reconstruction.py`. It runs the shared core once and then
starts the selected branches, including asymmetric cross repair by default.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments import branched_reconstruction as branched  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--description-file", required=True)
    parser.add_argument("--signature-file", required=True)
    parser.add_argument("--description-id", default=None)
    parser.add_argument("--dataset-id", default=None)
    parser.add_argument("--output-dir", default=branched.DEFAULT_OUTPUT_DIR)
    parser.add_argument("--agent-command", default=branched.DEFAULT_AGENT_COMMAND)
    parser.add_argument("--agent-model", default=None)
    parser.add_argument("--core-skill", default=branched.DEFAULT_CORE_SKILL)
    parser.add_argument("--self-test-skill", default=branched.DEFAULT_SELF_TEST_SKILL)
    parser.add_argument("--spec-repair-skill", default=branched.DEFAULT_SPEC_REPAIR_SKILL)
    parser.add_argument("--test-writer-skill", default=branched.DEFAULT_TEST_WRITER_SKILL)
    parser.add_argument("--cross-incumbent-skill", default=branched.DEFAULT_CROSS_INCUMBENT_SKILL)
    parser.add_argument("--cross-challenger-skill", default=branched.DEFAULT_CROSS_CHALLENGER_SKILL)
    parser.add_argument("--cross-runner", default=branched.DEFAULT_CROSS_RUNNER)
    parser.add_argument("--branches", nargs="+", choices=branched.DEFAULT_BRANCHES, default=list(branched.DEFAULT_BRANCHES))
    parser.add_argument("--timeout", type=float, default=1800.0)
    parser.add_argument("--broker-timeout", type=float, default=600.0)
    parser.add_argument("--max-feedback-rounds", type=int, default=3)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def description_id_for(description_file: Path, explicit_id: str | None) -> str:
    if explicit_id:
        return explicit_id
    content = description_file.read_text(encoding="utf-8")
    return branched.sha256_text(content)[:24]


def main() -> int:
    args = parse_args()
    description_file = branched.resolve_repo_path(args.description_file)
    signature_file = branched.resolve_repo_path(args.signature_file)
    output_dir = branched.resolve_repo_path(args.output_dir)
    runs_manifest = output_dir / "runs.jsonl"

    description_id = description_id_for(description_file, args.description_id)
    record = {
        "description_id": description_id,
        "dataset_id": args.dataset_id or description_id,
        "response_file": str(description_file),
        "response_sha256": branched.sha256_text(description_file.read_text(encoding="utf-8")) if description_file.is_file() else None,
        "signature_file": str(signature_file),
        "source_spectra_file": None,
        "source_repository_full_name": None,
        "source_path": None,
    }

    # `process_record` expects a signature_root attribute for batch records, but
    # the explicit signature_file in this synthetic record takes precedence.
    args.signature_root = str(signature_file.parent)
    args.limit = 1

    completed = set() if args.force else branched.completed_run_keys(runs_manifest)
    status = branched.process_record(record, args, output_dir, runs_manifest, completed)
    summary = {
        "status": status,
        "description_id": description_id,
        "description_file": str(description_file),
        "signature_file": str(signature_file),
        "output_dir": str(output_dir),
        "runs_manifest": str(runs_manifest),
        "branches": args.branches,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if status not in {"missing_input"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
