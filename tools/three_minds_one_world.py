#!/usr/bin/env python3
"""Alpha11 Three Minds, One World reference and optional mixed-provider demo."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nexus_runtime import NexusAPI  # noqa: E402
from nexus_runtime.canonical import canonical_json  # noqa: E402
from nexus_runtime.scrub import SecretScrubber  # noqa: E402
from nexus_runtime.three_minds_world import (  # noqa: E402
    ThreeMindsError,
    mixed_provider_council_request,
    run_three_minds_reference,
    verify_three_minds_reference,
)


class ToolError(RuntimeError):
    pass


def _scan_no_secrets(value: Any, *, field: str = "output") -> None:
    scrubber = SecretScrubber()
    if isinstance(value, str):
        if scrubber.scrub(value).changed:
            raise ToolError(f"{field} contains credential-shaped material")
        return
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise ToolError(f"{field} contains a non-string key")
            lowered = key.casefold().replace("-", "_")
            if lowered in {
                "api_key",
                "access_token",
                "refresh_token",
                "client_secret",
                "authorization",
                "password",
                "passwd",
                "secret",
                "token",
            }:
                raise ToolError(f"{field} contains a credential-labelled field")
            _scan_no_secrets(child, field=f"{field}.{key}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _scan_no_secrets(child, field=f"{field}[{index}]")


def _write_manifest(path: Path, manifest: Mapping[str, Any]) -> None:
    if not path.is_absolute():
        raise ToolError("manifest output path must be absolute")
    if path.exists() or path.is_symlink():
        raise ToolError("manifest output path must be new and non-symlink")
    parent = path.parent
    if parent.is_symlink():
        raise ToolError("manifest output parent must not be a symlink")
    parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((canonical_json(dict(manifest)) + "\n").encode("utf-8"))


def _run_reference(args: argparse.Namespace) -> int:
    if args.world is None:
        raise ToolError("reference run requires --world PATH")
    manifest = run_three_minds_reference(args.world)
    verification = verify_three_minds_reference(args.world, manifest)
    if args.manifest_output is not None:
        _write_manifest(args.manifest_output, manifest)
    result = {
        "status": "ok",
        "mode": "deterministic_reference",
        "manifest": manifest,
        "verification": verification,
    }
    _scan_no_secrets(result)
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


def _require_ok(response: Mapping[str, Any], operation: str) -> Mapping[str, Any]:
    if response.get("status") == "error":
        error = response.get("error")
        message = error.get("message") if isinstance(error, Mapping) else None
        raise ToolError(f"{operation} failed: {message if isinstance(message, str) else 'unknown runtime error'}")
    return response


def _run_mixed_provider(args: argparse.Namespace) -> int:
    if not args.authorize_mixed_provider:
        raise ToolError("mixed-provider demo requires --authorize-mixed-provider")
    if args.mixed_world is None:
        raise ToolError("mixed-provider demo requires --mixed-world PATH")
    if not args.xai_profile or not args.xai_model or not args.ollama_model:
        raise ToolError("mixed-provider demo requires --xai-profile, --xai-model and --ollama-model")

    question = args.mixed_question or (
        "Alpha11 mixed-provider Council: assess whether the Three Minds, One World integration "
        "demonstrates persistence and bounded replay without turning provider consensus into evidence."
    )
    request = mixed_provider_council_request(
        xai_profile=args.xai_profile,
        xai_model=args.xai_model,
        ollama_model=args.ollama_model,
        question=question,
    )
    _scan_no_secrets(request, field="mixed request")

    world_root = Path(args.mixed_world).absolute()
    trap_root = world_root.with_name(f"{world_root.name}.alpha11-trap")
    steno_root = world_root.with_name(f"{world_root.name}.alpha11-stenographer")
    api = NexusAPI(
        world_root,
        auth_root=args.auth_root,
        trap_root=trap_root,
        stenographer_root=steno_root,
    )

    auth_test = _require_ok(
        api.handle(
            {
                "operation": "auth.test",
                "adapter_id": "xai",
                "profile_name": args.xai_profile,
            }
        ),
        "auth.test",
    )
    if auth_test.get("status") not in {"ok", "ready"}:
        raise ToolError("xAI auth profile did not pass its admitted connection test")

    models_response = _require_ok(
        api.handle(
            {
                "operation": "models.list",
                "adapter_id": "xai",
                "profile_name": args.xai_profile,
                "timeout_seconds": 120,
            }
        ),
        "models.list",
    )
    models = models_response.get("models")
    if not isinstance(models, list):
        raise ToolError("models.list did not return a model array")
    discovered_ids = {
        item.get("id")
        for item in models
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    if args.xai_model not in discovered_ids:
        raise ToolError("selected xAI model was not returned by live discovery")

    result = _require_ok(api.handle(request), "council.run")
    result_body = result.get("result") if isinstance(result.get("result"), Mapping) else {}
    minority_reports = result_body.get("minority_reports")
    summary = {
        "status": "ok",
        "mode": "operator_authorized_mixed_provider",
        "session_ref": result.get("session_ref"),
        "receipt_ref": result.get("receipt_ref"),
        "execution_replayable": result.get("execution_replayable"),
        "consensus_label": result_body.get("consensus_label"),
        "tally": result_body.get("tally"),
        "minority_report_count": len(minority_reports) if isinstance(minority_reports, list) else None,
        "members": [
            {"member_id": "RemoteXAI", "adapter_id": "xai"},
            {"member_id": "LocalOpen", "adapter_id": "ollama"},
            {"member_id": "ReferenceMind", "adapter_id": "mock"},
        ],
        "authority_effect": "none",
        "provider_consensus_is_evidence": False,
    }
    _scan_no_secrets(summary)
    print(json.dumps(summary, sort_keys=True, indent=2))
    return 0


def self_test() -> None:
    with tempfile.TemporaryDirectory(prefix="nexus-alpha11-selftest-") as temporary:
        root = Path(temporary)
        left_root = root / "left-world"
        right_root = root / "right-world"
        left = run_three_minds_reference(left_root)
        left_verify = verify_three_minds_reference(left_root, left)
        right = run_three_minds_reference(right_root)
        right_verify = verify_three_minds_reference(right_root, right)
        if left != right:
            raise ToolError("alpha11 reference is not deterministic across clean world roots")
        if left_verify["manifest_ref"] != right_verify["manifest_ref"]:
            raise ToolError("alpha11 replay verification identities diverged")
        if left_verify.get("presence_lineage_length") != 4:
            raise ToolError("alpha11 world-presence lineage did not contain placement plus three handoffs")
        if left_verify.get("minority_report_count") != 1:
            raise ToolError("alpha11 deterministic Council did not preserve one minority report")
        if left_verify.get("mind_c_counterexample") != [25]:
            raise ToolError("alpha11 counterexample fixture did not survive verification")

    request = mixed_provider_council_request(
        xai_profile="fixture-profile",
        xai_model="grok-fixture",
        ollama_model="qwen-fixture:7b",
        question="fixture mixed-provider request",
    )
    _scan_no_secrets(request, field="mixed request fixture")
    members = request.get("members")
    if not isinstance(members, list) or len(members) != 3:
        raise ToolError("mixed-provider request must contain exactly three equal Council peers")
    for member in members:
        if not isinstance(member, Mapping):
            raise ToolError("mixed-provider member must be an object")
        if "vote_weight" in member or "epistemic_privilege" in member:
            raise ToolError("mixed-provider request must not assign authority metadata")
    print("alpha11 three-minds self-test: ok")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true", help="run deterministic hermetic conformance checks")
    parser.add_argument("--world", type=Path, help="file-backed world root for the deterministic reference run")
    parser.add_argument("--manifest-output", type=Path, help="optional new absolute path for canonical manifest JSON")

    parser.add_argument("--mixed-provider", action="store_true", help="run the optional xAI + Ollama + mock Council")
    parser.add_argument(
        "--authorize-mixed-provider",
        action="store_true",
        help="explicitly authorize xAI network and loopback Ollama execution",
    )
    parser.add_argument("--mixed-world", type=Path, help="persistent world root for the optional mixed-provider Council")
    parser.add_argument("--auth-root", type=Path, default=None, help="existing NEXUS auth root")
    parser.add_argument("--xai-profile", default=None, help="non-secret xAI auth profile name")
    parser.add_argument("--xai-model", default=None, help="xAI model id returned by live discovery")
    parser.add_argument("--ollama-model", default=None, help="loopback Ollama model id")
    parser.add_argument("--mixed-question", default=None, help="optional bounded mixed-provider Council question")
    args = parser.parse_args(argv)

    try:
        if args.self_test:
            self_test()
            return 0
        if args.mixed_provider:
            return _run_mixed_provider(args)
        return _run_reference(args)
    except (ThreeMindsError, ToolError, OSError, ValueError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
