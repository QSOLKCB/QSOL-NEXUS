#!/usr/bin/env python3
"""Operator-authorized live xAI acceptance harness for NEXUS alpha9.

This tool is intentionally not part of ordinary CI. A real network call is made
only when the operator supplies --authorize-live-xai. The resulting archive
contains references and bounded public result metadata, never credential bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nexus_runtime import NexusAPI  # noqa: E402
from nexus_runtime.canonical import canonical_json, sha256_ref  # noqa: E402
from nexus_runtime.scrub import SecretScrubber  # noqa: E402


ACCEPTANCE_SCHEMA = "nexus-alpha9-live-xai-acceptance/1"
ACCEPTANCE_POLICY = "nexus-alpha9-remote-operator/1"
MAX_REPORT_BYTES = 1_048_576
MAX_QUESTION_CHARS = 4_096
MAX_TIMEOUT_SECONDS = 900
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_MODEL_RE = re.compile(r"^[A-Za-z0-9._:/+-]{1,256}$")


class AcceptanceError(RuntimeError):
    pass


def _safe_identifier(value: str, *, field: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER_RE.fullmatch(value) is None:
        raise AcceptanceError(f"{field} must be a bounded non-secret identifier")
    return value


def _safe_model(value: str) -> str:
    if not isinstance(value, str) or _MODEL_RE.fullmatch(value) is None:
        raise AcceptanceError("model must be a bounded provider model identifier")
    return value


def _scan_no_secrets(value: Any, scrubber: SecretScrubber, *, field: str = "report") -> None:
    if isinstance(value, str):
        if scrubber.scrub(value).changed:
            raise AcceptanceError(f"{field} contains credential-shaped material")
        return
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise AcceptanceError(f"{field} contains a non-string object key")
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
                raise AcceptanceError(f"{field} contains a credential-labelled field")
            _scan_no_secrets(child, scrubber, field=f"{field}.{key}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _scan_no_secrets(child, scrubber, field=f"{field}[{index}]")


def _response_ok(response: Mapping[str, Any], *, operation: str) -> Mapping[str, Any]:
    if response.get("status") == "error":
        error = response.get("error")
        message = error.get("message") if isinstance(error, Mapping) else None
        raise AcceptanceError(
            f"{operation} failed: {message if isinstance(message, str) else 'unknown runtime error'}"
        )
    return response


def _model_ids(response: Mapping[str, Any]) -> list[str]:
    models = response.get("models")
    if not isinstance(models, list):
        raise AcceptanceError("models.list response did not contain a model array")
    result: list[str] = []
    for entry in models:
        if not isinstance(entry, Mapping):
            continue
        model_id = entry.get("id")
        if isinstance(model_id, str):
            result.append(model_id)
    return result


def _report_body(
    *,
    profile_name: str,
    model: str,
    question: str,
    model_count: int,
    run: Mapping[str, Any],
    session: Mapping[str, Any],
    receipt: Mapping[str, Any],
) -> dict[str, Any]:
    result = run.get("result") if isinstance(run.get("result"), Mapping) else {}
    telemetry = run.get("telemetry") if isinstance(run.get("telemetry"), Mapping) else {}
    return {
        "schema": ACCEPTANCE_SCHEMA,
        "policy": ACCEPTANCE_POLICY,
        "live_network": True,
        "operator_authorized": True,
        "adapter_id": "xai",
        "auth_profile_name": profile_name,
        "selected_model": model,
        "discovered_model_count": model_count,
        "question_sha256": hashlib.sha256(question.encode("utf-8")).hexdigest(),
        "roster": [
            {"member_id": "LocalAlpha", "adapter_id": "mock", "vote_weight": 1},
            {"member_id": "LocalBeta", "adapter_id": "mock", "vote_weight": 1},
            {"member_id": "RemoteXAI", "adapter_id": "xai", "vote_weight": 1},
        ],
        "session_ref": run.get("session_ref"),
        "receipt_ref": run.get("receipt_ref"),
        "session_id": run.get("session_id"),
        "execution_replayable": run.get("execution_replayable"),
        "result": {
            "disposition": result.get("disposition"),
            "consensus_label": result.get("consensus_label"),
            "evidence_state": result.get("evidence_state"),
            "tally": result.get("tally"),
            "minority_report_count": (
                len(result.get("minority_reports", []))
                if isinstance(result.get("minority_reports"), list)
                else None
            ),
        },
        "telemetry": {
            "schema_version": telemetry.get("schema_version"),
            "authority_effect": "none",
        },
        "verified_objects": {
            "session_object_id": session.get("object_id"),
            "session_object_type": session.get("object_type"),
            "receipt_object_id": receipt.get("object_id"),
            "receipt_object_type": receipt.get("object_type"),
        },
        "credential_material_recorded": False,
        "provider_output_is_truth": False,
        "provider_identity_confers_authority": False,
        "authority_effect": "none",
    }


def _finalize_report(body: dict[str, Any]) -> dict[str, Any]:
    acceptance_ref = sha256_ref("alpha9-live-acceptance", body)
    report = {**body, "acceptance_ref": acceptance_ref}
    encoded = (canonical_json(report) + "\n").encode("utf-8")
    if len(encoded) > MAX_REPORT_BYTES:
        raise AcceptanceError("acceptance report exceeds the canonical byte limit")
    _scan_no_secrets(report, SecretScrubber())
    return report


def _write_private_json(path: Path, report: Mapping[str, Any]) -> None:
    if not path.is_absolute():
        raise AcceptanceError("output path must be absolute")
    if path.is_symlink() or path.exists():
        raise AcceptanceError("output path must not already exist or be a symbolic link")
    parent = path.parent
    if parent.is_symlink():
        raise AcceptanceError("output parent must not be a symbolic link")
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    encoded = (canonical_json(dict(report)) + "\n").encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            if os.name != "nt":
                os.fchmod(handle.fileno(), stat.S_IRUSR | stat.S_IWUSR)
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def run_live(args: argparse.Namespace) -> dict[str, Any]:
    if not args.authorize_live_xai:
        raise AcceptanceError("live xAI execution requires --authorize-live-xai")
    profile = _safe_identifier(args.profile, field="profile")
    model = _safe_model(args.model)
    question = args.question
    if not isinstance(question, str) or not question.strip() or len(question) > MAX_QUESTION_CHARS:
        raise AcceptanceError(f"question must be non-empty and at most {MAX_QUESTION_CHARS} characters")
    timeout = args.timeout_seconds
    if type(timeout) is not int or not 1 <= timeout <= MAX_TIMEOUT_SECONDS:
        raise AcceptanceError(f"timeout_seconds must be in [1, {MAX_TIMEOUT_SECONDS}]")

    with tempfile.TemporaryDirectory(prefix="nexus-alpha9-live-") as temporary:
        root = Path(temporary)
        api = NexusAPI(
            root / "world",
            auth_root=args.auth_root,
            trap_root=root / "trap",
            stenographer_root=root / "stenographer",
        )

        auth_test = _response_ok(
            api.handle(
                {
                    "operation": "auth.test",
                    "adapter_id": "xai",
                    "profile_name": profile,
                }
            ),
            operation="auth.test",
        )
        if auth_test.get("status") not in {"ok", "ready"}:
            raise AcceptanceError("xAI auth profile did not pass its admitted connection test")

        models_response = _response_ok(
            api.handle(
                {
                    "operation": "models.list",
                    "adapter_id": "xai",
                    "profile_name": profile,
                    "timeout_seconds": timeout,
                }
            ),
            operation="models.list",
        )
        models = _model_ids(models_response)
        if model not in models:
            raise AcceptanceError("selected xAI model was not returned by live model discovery")

        run = _response_ok(
            api.handle(
                {
                    "operation": "council.run",
                    "question": question,
                    "mode_id": "analytical",
                    "evidence_state": "UNTESTED",
                    "members": [
                        {
                            "member_id": "LocalAlpha",
                            "model_id": "mock-alpha9-local-a",
                            "adapter_id": "mock",
                            "profile": "skeptical",
                        },
                        {
                            "member_id": "LocalBeta",
                            "model_id": "mock-alpha9-local-b",
                            "adapter_id": "mock",
                            "profile": "balanced",
                        },
                        {
                            "member_id": "RemoteXAI",
                            "model_id": model,
                            "adapter_id": "xai",
                            "auth_profile": profile,
                            "timeout_seconds": timeout,
                        },
                    ],
                }
            ),
            operation="council.run",
        )

        session_ref = run.get("session_ref")
        receipt_ref = run.get("receipt_ref")
        if not isinstance(session_ref, str) or not isinstance(receipt_ref, str):
            raise AcceptanceError("live Council run did not return session and receipt references")
        session = _response_ok(
            api.handle({"operation": "world.inspect", "object_ref": session_ref}),
            operation="world.inspect(session)",
        ).get("object")
        receipt = _response_ok(
            api.handle({"operation": "world.inspect", "object_ref": receipt_ref}),
            operation="world.inspect(receipt)",
        ).get("object")
        if not isinstance(session, Mapping) or not isinstance(receipt, Mapping):
            raise AcceptanceError("live Council objects could not be re-read from WorldStore")

        report = _finalize_report(
            _report_body(
                profile_name=profile,
                model=model,
                question=question,
                model_count=len(models),
                run=run,
                session=session,
                receipt=receipt,
            )
        )
        _write_private_json(args.output, report)
        return report


def self_test() -> None:
    body = {
        "schema": ACCEPTANCE_SCHEMA,
        "policy": ACCEPTANCE_POLICY,
        "live_network": False,
        "operator_authorized": False,
        "adapter_id": "xai",
        "auth_profile_name": "fixture",
        "selected_model": "grok-fixture",
        "credential_material_recorded": False,
        "authority_effect": "none",
    }
    first = _finalize_report(dict(body))
    second = _finalize_report(dict(body))
    if first != second:
        raise AcceptanceError("self-test report identity is not deterministic")
    try:
        _scan_no_secrets({"value": "xai-" + "A" * 32}, SecretScrubber())
    except AcceptanceError:
        pass
    else:
        raise AcceptanceError("self-test failed to reject credential-shaped material")
    print("alpha9 live acceptance self-test: ok")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true", help="run hermetic structural checks only")
    parser.add_argument("--authorize-live-xai", action="store_true", help="explicitly permit real xAI network calls")
    parser.add_argument("--auth-root", type=Path, default=None, help="optional existing NEXUS auth root")
    parser.add_argument("--profile", default="default", help="non-secret xAI auth profile name")
    parser.add_argument("--model", default="grok-4.5", help="model id that must be returned by live discovery")
    parser.add_argument(
        "--question",
        default=(
            "Alpha9 live acceptance: participate as one equal-vote remote Council peer. "
            "Evaluate whether this live transport test establishes connectivity only, not truth or authority."
        ),
    )
    parser.add_argument("--timeout-seconds", type=int, default=600)
    parser.add_argument("--output", type=Path, help="absolute new path for the private acceptance JSON")
    args = parser.parse_args(argv)

    try:
        if args.self_test:
            self_test()
            return 0
        if args.output is None:
            raise AcceptanceError("live acceptance requires --output /absolute/new/report.json")
        report = run_live(args)
    except (AcceptanceError, OSError, ValueError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2

    print(
        json.dumps(
            {
                "status": "ok",
                "acceptance_ref": report["acceptance_ref"],
                "session_ref": report["session_ref"],
                "receipt_ref": report["receipt_ref"],
                "output": str(args.output),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
