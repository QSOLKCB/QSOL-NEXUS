from __future__ import annotations

import argparse
from contextlib import ExitStack
import json
from pathlib import Path
import tempfile
from typing import Any

from .trap.commands import TrapCommandError
from .trap.controller import TrapController
from .trap.scenarios import list_scenarios
from .trap.subject import TrapSubjectError
from .trap.types import TrapError
from .trap.yaml_dsl import TrapYAMLError
from .trap.yaml_runtime import TrapYAMLRuntimeError
from .trap_demo import (
    DEFAULT_SCENARIO_ID,
    DEFAULT_SUBJECT_MODEL,
    public_demo_summary,
    run_trap_demo,
)


def configure_trap_parser(subparsers: Any) -> None:
    trap = subparsers.add_parser("trap", help="operate the isolated synthetic Trap Base")
    commands = trap.add_subparsers(dest="trap_command", required=True)

    demo = commands.add_parser("demo", help="run one bounded synthetic front-door incident")
    demo.add_argument("--subject-model", default=DEFAULT_SUBJECT_MODEL)
    demo.add_argument(
        "--scenario",
        default=DEFAULT_SCENARIO_ID,
        choices=[scenario.scenario_id for scenario in list_scenarios()],
    )
    demo.add_argument("--timeout", type=float, default=90.0)
    demo.add_argument(
        "--pull-missing",
        action="store_true",
        help="explicitly allow pulling a missing local Ollama model",
    )
    demo.add_argument(
        "--fake-subject",
        action="store_true",
        help="run only the hermetic structural fixture; real Ollama acceptance remains NOT_TESTABLE",
    )

    commands.add_parser("status", help="show bounded incident status")
    inspect = commands.add_parser("inspect", help="inspect one trap:<sha256> object")
    inspect.add_argument("object_ref")
    commands.add_parser("export", help="emit an inert manifest of TrapStore references")
    commands.add_parser(
        "emergency-close",
        help="operator-close a live or detached incident and restore Council mutation",
    )


def _emit(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))


def _safe_error(exc: BaseException) -> dict[str, object]:
    if isinstance(
        exc,
        (
            TrapError,
            TrapCommandError,
            TrapSubjectError,
            TrapYAMLError,
            TrapYAMLRuntimeError,
        ),
    ):
        code = getattr(exc, "code", "trap_error")
        message = str(exc)
    elif isinstance(exc, ValueError):
        code = "trap_invalid_request"
        message = str(exc)
    else:
        code = "trap_unavailable"
        message = "Trap Base is unavailable"
    return {"status": "error", "error": {"code": code, "message": message}}


def run_trap_command(
    args: argparse.Namespace,
    *,
    trap_root: str | Path,
) -> int:
    try:
        if args.trap_command == "demo":
            with ExitStack() as stack:
                temporary = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix="nexus-trap-cli-")))
                world_root = Path(args.world).absolute() if args.world is not None else temporary / "world"
                result = run_trap_demo(
                    world_root=world_root,
                    auth_root=temporary / "auth",
                    trap_root=trap_root,
                    subject_model=args.subject_model,
                    scenario_id=args.scenario,
                    timeout_seconds=args.timeout,
                    pull_missing=args.pull_missing,
                    force_fake_subject=args.fake_subject,
                )
                _emit(public_demo_summary(result))
                return 0

        controller = TrapController(trap_root)
        if args.trap_command == "status":
            _emit(controller.status())
            return 0
        if args.trap_command == "inspect":
            _emit(controller.inspect(args.object_ref))
            return 0
        if args.trap_command == "export":
            _emit(
                {
                    "status": "ok",
                    "schema_version": "nexus-trap-export/1",
                    "object_refs": controller.store.refs(),
                    "external_path": None,
                    "automatic_import": False,
                }
            )
            return 0
        if args.trap_command == "emergency-close":
            _emit(controller.emergency_close(actor_id="human_operator"))
            return 0
        raise ValueError("unknown trap command")
    except (Exception, KeyboardInterrupt) as exc:
        _emit(_safe_error(exc))
        return 2
