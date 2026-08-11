from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

from .epoch_api import EpochNexusAPI as NexusAPI
from .auth import AuthBroker, AuthError, ensure_disjoint_auth_world_roots
from .auth.storage import default_auth_root
from .auth_cli import configure_auth_parser, emit_auth_error, run_auth_command
from .control_plane import iter_bounded_jsonl_lines
from .model_cli import configure_models_parser, run_models_command
from .stenographer import StenographerError, default_stenographer_root
from .stenographer_cli import configure_stenographer_parser, run_stenographer_command
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


def _ensure_stenographer_disjoint(
    auth_root: str | Path,
    stenographer_root: str | Path | None,
    *,
    world_root: str | Path | None = None,
    trap_root: str | Path | None = None,
) -> None:
    if stenographer_root is None:
        return
    NexusAPI._ensure_disjoint_storage_roots(
        auth_root,
        stenographer_root,
        "auth",
        "stenographer",
    )
    if world_root is not None:
        NexusAPI._ensure_disjoint_storage_roots(
            world_root,
            stenographer_root,
            "world",
            "stenographer",
        )
    if trap_root is not None:
        NexusAPI._ensure_disjoint_storage_roots(
            trap_root,
            stenographer_root,
            "trap",
            "stenographer",
        )


def _drain_stenographer_on_exit(api: object) -> None:
    """Best-effort drain of accepted observer writes at a graceful process boundary."""

    try:
        stenographer = getattr(api, "stenographer", None)
        shutdown = getattr(stenographer, "shutdown", None)
        if callable(shutdown):
            shutdown()
    except Exception:
        # The Stenographer is fail-passive by contract. Process shutdown must
        # never gain authority over an already-produced runtime result, including
        # failures while lazily resolving the stenographer attribute itself.
        pass


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="QSOL NEXUS Council reference runtime")
    parser.add_argument("--world", default=None, help="optional file-backed development world directory")
    parser.add_argument("--auth-root", default=None, help="absolute operational auth directory outside the world store")
    parser.add_argument("--trap-root", default=None, help="optional isolated TrapStore directory outside world/auth state")
    parser.add_argument(
        "--stenographer-root",
        default=None,
        help="optional private canonical AI-action record directory outside world/auth/trap state",
    )
    parser.add_argument("--demo", action="store_true", help="run one deterministic mock Council demo and exit")
    subparsers = parser.add_subparsers(dest="command")
    configure_auth_parser(subparsers)
    configure_models_parser(subparsers)
    configure_trap_parser(subparsers)
    configure_stenographer_parser(subparsers)
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
            _ensure_stenographer_disjoint(
                broker.root,
                args.stenographer_root,
                world_root=args.world,
                trap_root=args.trap_root,
            )
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
            _ensure_stenographer_disjoint(
                broker.root,
                args.stenographer_root,
                world_root=args.world,
                trap_root=args.trap_root,
            )
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
            _ensure_stenographer_disjoint(
                selected_auth_root,
                args.stenographer_root,
                world_root=args.world,
                trap_root=selected_trap_root,
            )
        except (AuthError, EOFError, OSError, ValueError) as exc:
            return emit_auth_error(exc)
        return run_trap_command(
            args,
            trap_root=selected_trap_root,
        )

    if args.command == "stenographer":
        try:
            selected_auth_root = (
                Path(args.auth_root).expanduser()
                if args.auth_root is not None
                else default_auth_root().expanduser()
            )
            if not selected_auth_root.is_absolute():
                raise AuthError("authentication storage root must be an absolute path")
            selected_stenographer_root = (
                Path(args.stenographer_root).absolute()
                if args.stenographer_root is not None
                else default_stenographer_root()
            )
            selected_trap_root = (
                Path(args.trap_root).absolute()
                if args.trap_root is not None
                else default_trap_root()
            )
            NexusAPI._ensure_disjoint_storage_roots(
                selected_auth_root,
                selected_trap_root,
                "auth",
                "trap",
            )
            _ensure_stenographer_disjoint(
                selected_auth_root,
                selected_stenographer_root,
                world_root=args.world,
                trap_root=selected_trap_root,
            )
            if args.world is not None:
                ensure_disjoint_auth_world_roots(selected_auth_root, args.world)
                NexusAPI._ensure_disjoint_storage_roots(
                    args.world,
                    selected_trap_root,
                    "world",
                    "trap",
                )
        except (AuthError, EOFError, OSError, ValueError) as exc:
            return emit_auth_error(exc)
        return run_stenographer_command(args, root=selected_stenographer_root)

    selected_stenographer_root = (
        Path(args.stenographer_root).absolute()
        if args.stenographer_root is not None
        else (
            Path(args.world).absolute().with_name(".nexus-stenographer")
            if args.world is not None
            else default_stenographer_root()
        )
    )
    try:
        api = NexusAPI(
            args.world,
            auth_root=args.auth_root,
            trap_root=args.trap_root,
            stenographer_root=selected_stenographer_root,
        )
    except AuthError as exc:
        return emit_auth_error(exc)
    except StenographerError as exc:
        print(
            json.dumps(
                {"status": "error", "error": {"code": exc.code, "message": str(exc)}},
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 2

    try:
        if args.demo:
            print(json.dumps(api.handle(_demo_request()), indent=2, sort_keys=True))
            return 0

        for bounded in iter_bounded_jsonl_lines(sys.stdin):
            if bounded.error is not None:
                code = "request_too_large" if "byte limit" in bounded.error else "invalid_json"
                response = {"status": "error", "error": {"code": code, "message": bounded.error}}
                print(json.dumps(response, sort_keys=True, separators=(",", ":")), flush=True)
                continue
            assert bounded.text is not None
            line = bounded.text.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
                if not isinstance(request, dict):
                    raise ValueError("request must be a JSON object")
                response = api.handle(request)
            except (json.JSONDecodeError, ValueError, RecursionError) as exc:
                response = {"status": "error", "error": {"code": "invalid_json", "message": str(exc)}}
            print(json.dumps(response, sort_keys=True, separators=(",", ":")), flush=True)
        return 0
    finally:
        _drain_stenographer_on_exit(api)


if __name__ == "__main__":
    raise SystemExit(main())
