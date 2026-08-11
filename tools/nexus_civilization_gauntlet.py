#!/usr/bin/env python3
"""Run and verify the deterministic NEXUS Civilization Gauntlet."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nexus_runtime.civilization_gauntlet import CivilizationGauntlet  # noqa: E402
from nexus_runtime.world import WorldStore  # noqa: E402


def _emit(payload: dict) -> None:
    print(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the network-free reference Civilization Gauntlet, verify a receipt, "
            "or compare two verified receipts."
        )
    )
    parser.add_argument(
        "--world",
        type=Path,
        required=True,
        help="Persistent NEXUS WorldStore directory used for benchmark lineage.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("run", help="Run the deterministic false-belief-recovery reference civilization.")

    verify = sub.add_parser("verify", help="Verify one civilization receipt and its immutable lineage.")
    verify.add_argument("receipt_ref")

    compare = sub.add_parser("compare", help="Compare two verified civilization receipts.")
    compare.add_argument("left_receipt_ref")
    compare.add_argument("right_receipt_ref")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    world = WorldStore(args.world)
    gauntlet = CivilizationGauntlet(world)

    if args.command == "run":
        _emit(gauntlet.run())
        return 0
    if args.command == "verify":
        result = gauntlet.verify(args.receipt_ref)
        _emit(result)
        return 0 if result["verified"] else 1
    if args.command == "compare":
        _emit(gauntlet.compare(args.left_receipt_ref, args.right_receipt_ref))
        return 0
    raise AssertionError("unreachable command")


if __name__ == "__main__":
    raise SystemExit(main())
