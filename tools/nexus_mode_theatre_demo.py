#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from nexus_runtime import NexusAPI
from nexus_runtime.canonical import canonical_json
from nexus_runtime.mode_theatre import (
    DEFAULT_HOUSE_CASE,
    DEFAULT_ORATOR_MOTION,
    ModeTheatreError,
    run_mode_theatre_demo,
)
from nexus_runtime.mode_theatre_archive import ModeTheatreArchive, ModeTheatreArchiveError


DEFAULT_MIND_A = {
    "member_id": "Alpha",
    "model_id": "mock-alpha",
    "adapter_id": "mock",
    "profile": "exploratory",
}
DEFAULT_MIND_B = {
    "member_id": "Beta",
    "model_id": "mock-beta",
    "adapter_id": "mock",
    "profile": "skeptical",
}
DEFAULT_MIND_C = {
    "member_id": "Gamma",
    "model_id": "mock-gamma",
    "adapter_id": "mock",
    "profile": "balanced",
}


def _member(value: str) -> dict[str, Any]:
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(f"mind specification is not JSON: {exc.msg}") from exc
    if not isinstance(decoded, dict):
        raise argparse.ArgumentTypeError("mind specification must decode to a JSON object")
    return decoded


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the NEXUS multi-mind Mode Theatre: three minds do a fictional House Fun "
            "round, then reverse order for Roman Orator, with mandatory durable logs."
        )
    )
    parser.add_argument("--world", default=".nexus-mode-theatre-world", help="persistent WorldStore directory")
    parser.add_argument("--auth-root", help="optional NEXUS auth-profile directory")
    parser.add_argument(
        "--archive-root",
        default=".nexus-mode-theatre-archives",
        help="parent directory for mandatory unique run archives",
    )
    parser.add_argument(
        "--house-case",
        default=DEFAULT_HOUSE_CASE,
        help="fictional House Fun case; real-person medical cases are not the demo contract",
    )
    parser.add_argument(
        "--orator-motion",
        default=DEFAULT_ORATOR_MOTION,
        help="motion for the Roman Orator round",
    )
    parser.add_argument("--mind-a", type=_member, default=DEFAULT_MIND_A, help="JSON member object for Mind A")
    parser.add_argument("--mind-b", type=_member, default=DEFAULT_MIND_B, help="JSON member object for Mind B")
    parser.add_argument("--mind-c", type=_member, default=DEFAULT_MIND_C, help="JSON member object for Mind C")
    return parser


def _record_archive_error(archive: ModeTheatreArchive | None, message: str) -> None:
    if archive is None:
        return
    try:
        archive.record_error(message)
    except ModeTheatreArchiveError:
        pass


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    archive: ModeTheatreArchive | None = None
    try:
        # Mandatory archive reservation happens before NexusAPI construction and
        # before any provider/model call. If logging cannot be guaranteed, the
        # expensive/funny part does not start.
        archive = ModeTheatreArchive.reserve(Path(args.archive_root))
        api = NexusAPI(
            Path(args.world),
            auth_root=Path(args.auth_root) if args.auth_root else None,
            stenographer_root=archive.stenographer_root,
        )
        result = run_mode_theatre_demo(
            api,
            archive,
            members=(args.mind_a, args.mind_b, args.mind_c),
            house_case=args.house_case,
            orator_motion=args.orator_motion,
        )
        # actor.chat submits Stenographer observations asynchronously. The
        # Mode Theatre's own scrubbed archive is already durable here, but the
        # CLI also promises a complete laugh-later Stenographer directory, so
        # drain the observer before process exit instead of racing its daemon.
        if not api.stenographer.wait_for_idle():
            raise ModeTheatreError("stenographer observations did not flush before timeout")
        sys.stdout.write(canonical_json(result) + "\n")
        print(f"MODE THEATRE ARCHIVE: {archive.run_dir}", file=sys.stderr)
        return 0
    except KeyboardInterrupt:
        # Preserve normal Ctrl-C semantics, but leave an explicit marker in the
        # already-reserved archive so an interrupted live provider run cannot be
        # mistaken for unexplained filesystem corruption.
        _record_archive_error(archive, "MODE THEATRE INTERRUPTED: operator keyboard interrupt")
        raise
    except (ModeTheatreArchiveError, ModeTheatreError, OSError, TypeError, ValueError) as exc:
        _record_archive_error(archive, f"MODE THEATRE ERROR: {exc}")
        print(f"MODE THEATRE ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
