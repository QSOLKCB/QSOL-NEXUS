#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, TextIO

from nexus_runtime import NexusAPI
from nexus_runtime.canonical import canonical_json
from nexus_runtime.three_minds import (
    DEFAULT_INTEGER_VALUES,
    ThreeMindsError,
    run_three_minds_demo,
)


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


def _values(value: str) -> tuple[int, ...]:
    try:
        parts = [item.strip() for item in value.split(",")]
        if not parts or any(not item for item in parts):
            raise ValueError
        return tuple(int(item, 10) for item in parts)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("--values must be a comma-separated list of base-10 integers") from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run NEXUS 2.0-alpha11 Three Minds, One World: A proposes, B arrives later "
            "to reproduce/critique, the coordinator runs a bounded integer instrument, "
            "and C attempts falsification from the shared lineage."
        )
    )
    parser.add_argument("--world", default=".nexus-alpha11-world", help="persistent WorldStore directory")
    parser.add_argument("--auth-root", help="optional NEXUS auth-profile directory")
    parser.add_argument("--stenographer-root", help="optional Courtroom Stenographer directory")
    parser.add_argument("--mode", default="analytical", help="existing NEXUS world mode")
    parser.add_argument(
        "--values",
        type=_values,
        default=DEFAULT_INTEGER_VALUES,
        help="comma-separated bounded integer fixture",
    )
    parser.add_argument("--question", help="optional custom framing for the fixed primality benchmark")
    parser.add_argument(
        "--mind-a",
        type=_member,
        default=DEFAULT_MIND_A,
        help="JSON CouncilActor member object for Mind A",
    )
    parser.add_argument(
        "--mind-b",
        type=_member,
        default=DEFAULT_MIND_B,
        help="JSON CouncilActor member object for Mind B",
    )
    parser.add_argument(
        "--mind-c",
        type=_member,
        default=DEFAULT_MIND_C,
        help="JSON CouncilActor member object for Mind C",
    )
    parser.add_argument(
        "--json-out",
        help=(
            "optional new output file; reserved before any model call and never overwritten "
            "(exit 3 when it already exists)"
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    output_path: Path | None = None
    output_handle: TextIO | None = None
    output_reserved = False
    output_committed = False

    try:
        if args.json_out:
            output_path = Path(args.json_out)
            # Reserve the path before constructing the runtime or contacting any
            # model/provider. Exclusive creation preserves prior output and closes
            # the race between a preflight exists() check and the expensive run.
            output_handle = output_path.open("x", encoding="utf-8", newline="\n")
            output_reserved = True

        api = NexusAPI(
            Path(args.world),
            auth_root=Path(args.auth_root) if args.auth_root else None,
            stenographer_root=Path(args.stenographer_root) if args.stenographer_root else None,
        )
        result = run_three_minds_demo(
            api,
            members=(args.mind_a, args.mind_b, args.mind_c),
            values=args.values,
            question=args.question,
            mode=args.mode,
        )
        rendered = canonical_json(result) + "\n"
        if output_handle is not None:
            output_handle.write(rendered)
            output_handle.flush()
            output_handle.close()
            output_handle = None
            output_committed = True
        sys.stdout.write(rendered)
        return 0
    except FileExistsError:
        print(
            "THREE MINDS ERROR: JSON output file already exists; refusing to overwrite: "
            f"{args.json_out}",
            file=sys.stderr,
        )
        return 3
    except (OSError, ThreeMindsError, TypeError, ValueError) as exc:
        print(f"THREE MINDS ERROR: {exc}", file=sys.stderr)
        return 2
    finally:
        if output_handle is not None:
            output_handle.close()
        if output_reserved and not output_committed and output_path is not None:
            try:
                output_path.unlink(missing_ok=True)
            except OSError:
                # Preserve the original failure. A crash/permission change can
                # leave an empty reservation behind, but we never overwrite it.
                pass


if __name__ == "__main__":
    raise SystemExit(main())
