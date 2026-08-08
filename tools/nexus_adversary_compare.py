#!/usr/bin/env python3
"""Compare two NEXUS adversarial-gauntlet JSON reports.

Exit 1 only when the candidate introduces a newly failing named check.
This is useful for build-agent iterations where a known failing reproducer is
intentionally kept red while a fix is being developed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_report(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"{path}: report must be a JSON object")
    schema = data.get("schema_version")
    if not isinstance(schema, str) or not schema.startswith("nexus-adversarial-gauntlet/"):
        raise SystemExit(f"{path}: unsupported report schema {schema!r}")
    results = data.get("results")
    if not isinstance(results, list):
        raise SystemExit(f"{path}: results must be an array")
    return data


def status_map(report: dict[str, Any]) -> dict[str, str]:
    output: dict[str, str] = {}
    for row in report["results"]:
        if not isinstance(row, dict):
            raise SystemExit("report result rows must be objects")
        name = row.get("name")
        status = row.get("status")
        if not isinstance(name, str) or not name:
            raise SystemExit("report result name must be non-empty text")
        if status not in {"pass", "fail"}:
            raise SystemExit(f"report result {name!r} has invalid status {status!r}")
        if name in output:
            raise SystemExit(f"duplicate result name in report: {name}")
        output[name] = status
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare NEXUS adversarial gauntlet reports")
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    args = parser.parse_args()

    baseline = status_map(load_report(args.baseline))
    candidate = status_map(load_report(args.candidate))

    baseline_failed = {name for name, status in baseline.items() if status == "fail"}
    candidate_failed = {name for name, status in candidate.items() if status == "fail"}
    new_failures = sorted(candidate_failed - baseline_failed)
    fixed = sorted(baseline_failed - candidate_failed)
    added_checks = sorted(set(candidate) - set(baseline))
    missing_checks = sorted(set(baseline) - set(candidate))

    print(f"baseline failures: {len(baseline_failed)}")
    print(f"candidate failures: {len(candidate_failed)}")
    if new_failures:
        print("NEW FAILURES:")
        for name in new_failures:
            print(f"  - {name}")
    if fixed:
        print("FIXED:")
        for name in fixed:
            print(f"  - {name}")
    if added_checks:
        print("ADDED CHECKS:")
        for name in added_checks:
            print(f"  - {name}: {candidate[name]}")
    if missing_checks:
        print("MISSING CHECKS:")
        for name in missing_checks:
            print(f"  - {name}")

    if new_failures:
        print("COMPARISON: REGRESSION")
        return 1
    print("COMPARISON: NO NEW NAMED FAILURES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
