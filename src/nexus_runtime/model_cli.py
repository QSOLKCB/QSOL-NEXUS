from __future__ import annotations

import argparse
import json
from typing import Any

from .adapters import AdapterError, XAITransport
from .auth import AuthBroker, AuthError


def configure_models_parser(subparsers: Any) -> None:
    models = subparsers.add_parser("models", help="inspect models exposed by an admitted provider adapter")
    actions = models.add_subparsers(dest="models_action", required=True)
    listing = actions.add_parser("list", help="list language models available to an auth profile")
    listing.add_argument("adapter_id")
    listing.add_argument("--profile", default="default")
    listing.add_argument("--timeout", type=float, default=60.0)


def run_models_command(args: argparse.Namespace, broker: AuthBroker) -> int:
    try:
        if args.models_action != "list":
            raise ValueError("unknown models command")
        if args.adapter_id != "xai":
            raise ValueError("model discovery currently supports only the xai adapter")
        material = broker.resolve(args.adapter_id, args.profile)
        if material is None:
            raise AuthError("xAI auth profile did not resolve a credential")
        models = XAITransport(material, timeout_seconds=args.timeout).list_language_models()
        result = {
            "status": "ok",
            "adapter_id": args.adapter_id,
            "profile_name": args.profile,
            "remote_verified": True,
            "model_count": len(models),
            "models": models,
        }
    except (AuthError, AdapterError, ValueError) as exc:
        message = str(exc)
        if not message or len(message) > 256 or any(ord(character) < 0x20 for character in message):
            message = "model discovery failed"
        print(json.dumps({"status": "error", "error": {"code": "models_error", "message": message}}, sort_keys=True))
        return 2
    except OSError:
        print(
            json.dumps(
                {"status": "error", "error": {"code": "models_error", "message": "model discovery failed"}},
                sort_keys=True,
            )
        )
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0
