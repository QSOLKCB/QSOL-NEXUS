#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nexus_runtime.canonical import canonical_json
from nexus_runtime.schema_migration import (
    SchemaMigrationError,
    build_migration_plan,
    classify_version_change,
    schema_migration_policy_snapshot,
    verify_migration_plan,
)


MAX_VERIFY_STDIN_BYTES = 65_536


class _DuplicateKey(ValueError):
    pass


class _ArgumentError(ValueError):
    pass


class _JSONArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise _ArgumentError(message)


def _closed_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKey(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number is forbidden: {value}")


def _read_plan_stdin() -> dict[str, Any]:
    raw = sys.stdin.buffer.read(MAX_VERIFY_STDIN_BYTES + 1)
    if len(raw) > MAX_VERIFY_STDIN_BYTES:
        raise ValueError(f"verification input exceeds {MAX_VERIFY_STDIN_BYTES} bytes")
    try:
        decoded = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("verification input must be UTF-8") from exc
    parsed = json.loads(
        decoded,
        object_pairs_hook=_closed_object,
        parse_constant=_reject_constant,
    )
    if not isinstance(parsed, dict):
        raise ValueError("verification input must be one JSON object")
    return parsed


def _emit(value: Any) -> None:
    sys.stdout.write(canonical_json(value) + "\n")


def build_parser() -> argparse.ArgumentParser:
    parser = _JSONArgumentParser(description="NEXUS schema/version migration policy tool")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("policy", help="print the current migration policy")

    classify = subparsers.add_parser("classify", help="classify one version identity change")
    classify.add_argument("--kind", required=True, choices=("schema", "protocol", "runtime"))
    classify.add_argument("--source", required=True)
    classify.add_argument("--target", required=True)

    plan = subparsers.add_parser("plan", help="build an inert content-addressed migration plan")
    plan.add_argument("--kind", required=True, choices=("schema", "protocol", "runtime"))
    plan.add_argument("--source", required=True)
    plan.add_argument("--target", required=True)
    plan.add_argument("--source-ref")

    subparsers.add_parser("verify", help="verify one plan JSON object from stdin")
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        if args.command == "policy":
            result = schema_migration_policy_snapshot()
        elif args.command == "classify":
            result = classify_version_change(args.kind, args.source, args.target)
        elif args.command == "plan":
            result = build_migration_plan(
                args.kind,
                args.source,
                args.target,
                source_ref=args.source_ref,
            )
        else:
            result = verify_migration_plan(_read_plan_stdin())
        _emit(result)
        return 0
    except (_ArgumentError, SchemaMigrationError, ValueError, json.JSONDecodeError, _DuplicateKey) as exc:
        _emit(
            {
                "status": "error",
                "error": {
                    "code": getattr(
                        exc,
                        "code",
                        "schema_migration_invalid_arguments"
                        if isinstance(exc, _ArgumentError)
                        else "schema_migration_invalid",
                    ),
                    "message": str(exc),
                },
            }
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
