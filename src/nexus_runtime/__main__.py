from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from .api import NexusAPI
from .auth import AuthBroker, AuthError, ensure_disjoint_auth_world_roots
from .auth_cli import configure_auth_parser, emit_auth_error, run_auth_command


def _demo_request() -> dict:
    return {
        "request_id": "demo-1",
        "operation": "council.run",
        "question": "I measured an interesting result. Does it justify the larger hypothesis?",
        "members": [
            {"member_id": "A", "model_id": "mock-a", "profile": "balanced"},
            {"member_id": "B", "model_id": "mock-b", "profile": "skeptical"},
            {"member_id": "C", "model_id": "mock-c", "profile": "exploratory"},
            {"member_id": "D", "model_id": "mock-d", "profile": "supportive"},
            {"member_id": "E", "model_id": "mock-e", "profile": "balanced", "attempt_privilege_claim": True},
        ],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="QSOL NEXUS Council reference runtime")
    parser.add_argument("--world", default=None, help="optional file-backed development world directory")
    parser.add_argument("--auth-root", default=None, help="absolute operational auth directory outside the world store")
    parser.add_argument("--demo", action="store_true", help="run one deterministic mock Council demo and exit")
    subparsers = parser.add_subparsers(dest="command")
    configure_auth_parser(subparsers)
    args = parser.parse_args(argv)

    if args.command == "auth":
        try:
            broker = AuthBroker(args.auth_root)
            if args.world is not None:
                ensure_disjoint_auth_world_roots(broker.root, args.world)
        except (AuthError, EOFError, OSError) as exc:
            return emit_auth_error(exc)
        return run_auth_command(args, broker)

    api = NexusAPI(args.world, auth_root=args.auth_root)
    if args.demo:
        print(json.dumps(api.handle(_demo_request()), indent=2, sort_keys=True))
        return 0

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            if not isinstance(request, dict):
                raise ValueError("request must be a JSON object")
            response = api.handle(request)
        except (json.JSONDecodeError, ValueError) as exc:
            response = {"status": "error", "error": {"code": "invalid_json", "message": str(exc)}}
        print(json.dumps(response, sort_keys=True, separators=(",", ":")), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
