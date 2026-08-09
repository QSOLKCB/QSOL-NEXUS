from __future__ import annotations

import argparse
from getpass import getpass
import json
import sys
from typing import Any
import webbrowser

from .auth import AuthBroker, AuthError, DeviceAuthorizationPrompt


def configure_auth_parser(subparsers: Any) -> None:
    auth = subparsers.add_parser("auth", help="manage provider authentication outside world state")
    actions = auth.add_subparsers(dest="auth_action", required=True)

    actions.add_parser("adapters", help="list adapters and their admitted auth methods")
    actions.add_parser("list", help="list non-secret auth profile metadata")

    add = actions.add_parser("add", help="add an auth profile")
    add.add_argument("adapter_id")
    add.add_argument("--profile", default="default")
    add.add_argument(
        "--method",
        required=True,
        choices=("browser", "browser-key", "device", "api-key", "env", "external-command"),
    )
    add.add_argument("--env", dest="env_var", help="environment variable containing an API credential")
    add.add_argument(
        "--helper-env",
        dest="helper_env_vars",
        action="append",
        default=[],
        metavar="NAME",
        help="environment variable explicitly forwarded to an external credential helper; repeatable",
    )
    add.add_argument("--no-open", action="store_true", help="print a browser URL without opening it")
    add.add_argument("--replace", action="store_true", help="replace an existing profile")
    add.add_argument(
        "--command",
        dest="command_argv",
        nargs=argparse.REMAINDER,
        help="absolute helper executable followed by argv; this option must be last",
    )

    test = actions.add_parser("test", help="resolve a profile and run its admitted connection test")
    test.add_argument("adapter_id")
    test.add_argument("--profile", default="default")

    logout = actions.add_parser("logout", help="delete an auth profile and its stored credential")
    logout.add_argument("adapter_id")
    logout.add_argument("--profile", default="default")


def run_auth_command(args: argparse.Namespace, broker: AuthBroker) -> int:
    try:
        if args.auth_action == "adapters":
            result = broker.adapters()
        elif args.auth_action == "list":
            result = broker.list_profiles()
        elif args.auth_action == "test":
            result = broker.test_profile(args.adapter_id, args.profile)
        elif args.auth_action == "logout":
            result = broker.logout(args.adapter_id, args.profile)
        elif args.auth_action == "add":
            result = _add_profile(args, broker)
        else:
            raise AuthError("unknown auth command")
    except (AuthError, EOFError, OSError) as exc:
        return emit_auth_error(exc)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") in {"ok", "ready"} else 1


def emit_auth_error(exc: BaseException) -> int:
    if isinstance(exc, AuthError):
        message = str(exc)
        if not message or len(message) > 256 or any(ord(character) < 0x20 for character in message):
            message = "authentication operation failed"
    elif isinstance(exc, EOFError):
        message = "authentication input was unavailable"
    else:
        message = "authentication operation failed"
    print(
        json.dumps(
            {"status": "error", "error": {"code": "auth_error", "message": message}},
            sort_keys=True,
        )
    )
    return 2


def _add_profile(args: argparse.Namespace, broker: AuthBroker) -> dict[str, Any]:
    if args.method == "browser":
        if args.env_var or args.helper_env_vars or args.command_argv:
            raise AuthError("browser mode does not accept env or external-command options")
        return broker.add_browser(
            args.adapter_id,
            args.profile,
            open_browser=not args.no_open,
            on_authorization_url=lambda url: print(f"Authorize NEXUS in your browser:\n{url}", file=sys.stderr),
            replace=args.replace,
        )
    if args.method == "device":
        if args.env_var or args.helper_env_vars or args.command_argv:
            raise AuthError("device mode does not accept env or external-command options")
        return broker.add_device(
            args.adapter_id,
            args.profile,
            on_prompt=_print_device_prompt,
            replace=args.replace,
        )
    if args.method == "api-key":
        if args.env_var or args.helper_env_vars or args.command_argv:
            raise AuthError("api-key mode reads from a hidden prompt; use env or external-command for headless setup")
        return _prompt_and_store_api_key(args, broker)
    if args.method == "browser-key":
        if args.env_var or args.helper_env_vars or args.command_argv:
            raise AuthError("browser-key mode does not accept env or external-command options")
        setup_url = broker.setup_url(args.adapter_id)
        print(f"Create a provider API key in your browser:\n{setup_url}", file=sys.stderr)
        if not args.no_open:
            try:
                webbrowser.open(setup_url)
            except (OSError, webbrowser.Error):
                # The fixed URL is already printed, so a missing desktop
                # browser does not prevent secure hidden-prompt enrollment.
                pass
        return _prompt_and_store_api_key(args, broker)
    if args.method == "env":
        if not args.env_var:
            raise AuthError("env mode requires --env NAME")
        if args.command_argv:
            raise AuthError("env mode does not accept --command")
        if args.helper_env_vars:
            raise AuthError("env mode does not accept --helper-env")
        return broker.add_environment(
            args.adapter_id,
            args.profile,
            args.env_var,
            replace=args.replace,
        )
    if args.method == "external-command":
        if not args.command_argv:
            raise AuthError("external-command mode requires --command /absolute/helper [args...]")
        if args.env_var:
            raise AuthError("external-command mode does not accept --env")
        return broker.add_external_command(
            args.adapter_id,
            args.profile,
            args.command_argv,
            environment_variables=args.helper_env_vars,
            replace=args.replace,
        )
    raise AuthError("unsupported auth method")


def _prompt_and_store_api_key(args: argparse.Namespace, broker: AuthBroker) -> dict[str, Any]:
    api_key = getpass("Provider API credential (input hidden): ")
    if not api_key:
        raise AuthError("API credential must not be empty")
    return broker.add_api_key(args.adapter_id, args.profile, api_key, replace=args.replace)


def _print_device_prompt(prompt: DeviceAuthorizationPrompt) -> None:
    target = prompt.verification_uri_complete or prompt.verification_uri
    print(f"Open this URL on a browser-capable device:\n{target}", file=sys.stderr)
    if prompt.user_code:
        print(f"Device code: {prompt.user_code}", file=sys.stderr)
