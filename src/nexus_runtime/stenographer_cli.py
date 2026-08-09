from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .stenographer import CourtroomStenographer, StenographerError


def configure_stenographer_parser(subparsers: Any) -> None:
    stenographer = subparsers.add_parser(
        "stenographer",
        help="inspect the read-only canonical AI action record",
    )
    commands = stenographer.add_subparsers(dest="stenographer_command", required=True)
    commands.add_parser("status", help="show the Knowledge-Watchman boundary and ledger head")

    listing = commands.add_parser("list", help="list bounded AI action records")
    listing.add_argument("--limit", type=int, default=100)
    listing.add_argument("--action-type", default=None)
    listing.add_argument("--member-id", default=None)

    inspect = commands.add_parser("inspect", help="inspect one steno:<sha256> record")
    inspect.add_argument("record_ref")
    commands.add_parser("verify", help="verify the immutable record lineage")
    commands.add_parser("summary", help="show deterministic study counts")
    commands.add_parser("export", help="emit a read-only manifest of record references")


def _emit(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))


def run_stenographer_command(args: argparse.Namespace, *, root: str | Path) -> int:
    try:
        stenographer = CourtroomStenographer(root)
        if args.stenographer_command == "status":
            value = stenographer.status()
        elif args.stenographer_command == "list":
            value = stenographer.list_records(
                limit=args.limit,
                action_type=args.action_type,
                member_id=args.member_id,
            )
        elif args.stenographer_command == "inspect":
            value = stenographer.inspect(args.record_ref)
        elif args.stenographer_command == "verify":
            value = stenographer.verify()
        elif args.stenographer_command == "summary":
            value = stenographer.summary()
        elif args.stenographer_command == "export":
            value = stenographer.export_manifest()
        else:
            raise StenographerError(
                "stenographer_invalid_query",
                "unknown stenographer command",
            )
        _emit(value)
        return 0
    except (Exception, KeyboardInterrupt) as exc:
        if isinstance(exc, StenographerError):
            code = exc.code
            message = str(exc)
        else:
            code = "stenographer_unavailable"
            message = "Courtroom Stenographer is unavailable"
        _emit({"status": "error", "error": {"code": code, "message": message}})
        return 2
