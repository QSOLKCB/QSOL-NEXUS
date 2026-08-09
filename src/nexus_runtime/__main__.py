from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

from .api import NexusAPI
from .auth import AuthBroker, AuthError, ensure_disjoint_auth_world_roots
from .auth.storage import default_auth_root
from .auth_cli import configure_auth_parser, emit_auth_error, run_auth_command
from .model_cli import configure_models_parser, run_models_command
from .trap_cli import configure_trap_parser, run_trap_command
from .trap_demo import default_trap_root


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
    parser.add_argument("--trap-root", default=None, help="optional isolated TrapStore directory outside world/auth state")
    parser.add_argument("--demo", action="store_true", help="run one deterministic mock Council demo and exit")
    subparsers = parser.add_subparsers(dest="command")
    configure_auth_parser(subparsers)
    configure_models_parser(subparsers)
    configure_trap_parser(subparsers)
    args = parser.parse_args(argv)

    if args.command == "auth":
        try:
            broker = AuthBroker(args.auth_root)
            if args.world is not None:
                ensure_disjoint_auth_world_roots(broker.root, args.world)
            if args.trap_root is not None:
                NexusAPI._ensure_disjoint_storage_roots(broker.root, args.trap_root, "auth", "trap")
                if args.world is not None:
                    NexusAPI._ensure_disjoint_storage_roots(args.world, args.trap_root, "world", "trap")
        except (AuthError, EOFError, OSError) as exc:
            return emit_auth_error(exc)
        return run_auth_command(args, broker)

    if args.command == "models":
        try:
            broker = AuthBroker(args.auth_root)
            if args.world is not None:
                ensure_disjoint_auth_world_roots(broker.root, args.world)
            if args.trap_root is not None:
                NexusAPI._ensure_disjoint_storage_roots(broker.root, args.trap_root, "auth", "trap")
                if args.world is not None:
                    NexusAPI._ensure_disjoint_storage_roots(args.world, args.trap_root, "world", "trap")
        except (AuthError, EOFError, OSError) as exc:
            return emit_auth_error(exc)
        return run_models_command(args, broker)

    if args.command == "trap":
        try:
            selected_auth_root = (
                Path(args.auth_root).expanduser()
                if args.auth_root is not None
                else default_auth_root().expanduser()
            )
            if not selected_auth_root.is_absolute():
                raise AuthError("authentication storage root must be an absolute path")
            selected_trap_root = Path(args.trap_root).absolute() if args.trap_root else default_trap_root()
            NexusAPI._ensure_disjoint_storage_roots(
                selected_auth_root,
                selected_trap_root,
                "auth",
                "trap",
            )
            if args.world is not None:
                ensure_disjoint_auth_world_roots(selected_auth_root, args.world)
                NexusAPI._ensure_disjoint_storage_roots(args.world, selected_trap_root, "world", "trap")
        except (AuthError, EOFError, OSError, ValueError) as exc:
            return emit_auth_error(exc)
        return run_trap_command(
            args,
            trap_root=selected_trap_root,
        )

    api = NexusAPI(args.world, auth_root=args.auth_root, trap_root=args.trap_root)
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
