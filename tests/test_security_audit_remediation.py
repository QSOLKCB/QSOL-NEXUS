from __future__ import annotations

import json
import os
from pathlib import Path
import stat
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.request import ProxyHandler

from nexus_runtime.adapters.ollama import OllamaTransport
from nexus_runtime.api import PROTOCOL_VERSION as API_PROTOCOL_VERSION
from nexus_runtime.auth.broker import _external_helper_environment
from nexus_runtime.auth.oauth import OAuthHTTPClient
from nexus_runtime.canonical import canonical_json
from nexus_runtime.council import CouncilCoordinator
from nexus_runtime.types import Ballot, CouncilMember
from nexus_runtime.version import PROTOCOL_VERSION
from nexus_runtime.world import WorldStore


class _JSONResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, limit: int = -1) -> bytes:
        return b"{}"


class _SecretEmittingActor:
    def __init__(self, member_id: str, canary: str) -> None:
        self.member = CouncilMember(member_id, f"model-{member_id}", "mock")
        self.canary = canary

    @property
    def replayable(self) -> bool:
        return True

    def identity_metadata(self) -> dict[str, object]:
        return {"actor_kind": "audit-secret-fixture"}

    def respond(self, context) -> str:
        return f"phase fixture {self.canary}"

    def ballot(self, context) -> tuple[Ballot, str]:
        return Ballot.TEST_FURTHER, f"ballot fixture {self.canary}"


class SecurityAuditRemediationTests(unittest.TestCase):
    @unittest.skipIf(os.name == "nt", "POSIX permission and symlink semantics")
    def test_world_store_is_private_and_rejects_object_symlink_replacement(self) -> None:
        with TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "world"
            world = WorldStore(root)
            payload = {"message": "immutable"}
            created = world.create_object("note", payload, {"actor": "operator"})

            digest = created.object_id.removeprefix("object:")
            object_path = root / "objects" / f"{digest}.json"
            self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE((root / "objects").stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(object_path.stat().st_mode), 0o600)

            external = base / "outside.txt"
            external.write_text("do-not-touch", encoding="utf-8")
            object_path.unlink()
            object_path.symlink_to(external)

            with self.assertRaises((ValueError, OSError)):
                world.create_object("note", payload, {"actor": "operator"})
            self.assertEqual(external.read_text(encoding="utf-8"), "do-not-touch")

    @unittest.skipIf(os.name == "nt", "POSIX permission migration semantics")
    def test_world_store_migrates_legacy_umask_permissions(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "world"
            objects = root / "objects"
            objects.mkdir(parents=True, mode=0o755)
            created = WorldStore().create_object(
                "legacy_note",
                {"message": "still readable"},
                {"actor": "legacy-runtime"},
            )
            path = objects / f"{created.object_id.removeprefix('object:')}.json"
            path.write_text(canonical_json(created.as_dict()) + "\n", encoding="utf-8")
            root.chmod(0o755)
            objects.chmod(0o755)
            path.chmod(0o644)

            migrated = WorldStore(root)

            self.assertEqual(migrated.inspect(created.object_id).as_dict(), created.as_dict())
            self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(objects.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    @unittest.skipIf(os.name == "nt", "POSIX persisted-file semantics")
    def test_existing_world_object_requires_closed_canonical_bytes(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "world"
            world = WorldStore(root)
            created = world.create_object("note", {"message": "immutable"}, {"actor": "operator"})
            path = root / "objects" / f"{created.object_id.removeprefix('object:')}.json"

            injected = created.as_dict()
            injected["unhashed_extra"] = "not covered by object identity"
            path.write_text(canonical_json(injected) + "\n", encoding="utf-8")
            path.chmod(0o600)
            with self.assertRaisesRegex(ValueError, "schema"):
                WorldStore(root).create_object(
                    "note",
                    {"message": "immutable"},
                    {"actor": "operator"},
                )

            path.write_text(json.dumps(created.as_dict(), indent=2) + "\n", encoding="utf-8")
            path.chmod(0o600)
            with self.assertRaisesRegex(ValueError, "canonical"):
                WorldStore(root).inspect(created.object_id)

    def test_oauth_post_form_always_installs_empty_proxy_handler(self) -> None:
        captured_handlers: list[object] = []

        class Opener:
            def open(self, request, timeout):
                return _JSONResponse()

        def fake_build_opener(*handlers):
            captured_handlers.extend(handlers)
            return Opener()

        config = SimpleNamespace(
            allowed_endpoint_hosts=("oauth.example",),
            allow_insecure_loopback_provider=False,
            token_endpoint="https://oauth.example/token",
            client_id="fixture-client",
        )
        with patch("nexus_runtime.auth.oauth.build_opener", side_effect=fake_build_opener):
            result = OAuthHTTPClient().post_form("https://oauth.example/token", {"code": "fixture"}, config)

        self.assertEqual(result, {})
        proxies = [handler.proxies for handler in captured_handlers if isinstance(handler, ProxyHandler)]
        self.assertEqual(proxies, [{}])

    def test_external_helper_environment_drops_ambient_secrets(self) -> None:
        environment = {
            "PATH": "/usr/bin:/bin",
            "LANG": "C.UTF-8",
            "HOME": "/home/operator",
            "XAI_API_KEY": "xai-this-must-not-reach-helper",
            "GITHUB_TOKEN": "ghp_this_must_not_reach_helper",
            "AWS_SECRET_ACCESS_KEY": "also-secret",
            "CUSTOM_NON_SECRET": "still-not-implicitly-authorized",
        }
        clean = _external_helper_environment(
            environment,
            adapter_id="fixture",
            profile_name="default",
        )

        self.assertEqual(clean["PATH"], environment["PATH"])
        self.assertEqual(clean["LANG"], environment["LANG"])
        self.assertEqual(clean["HOME"], environment["HOME"])
        self.assertEqual(clean["NEXUS_AUTH_ADAPTER"], "fixture")
        self.assertEqual(clean["NEXUS_AUTH_PROFILE"], "default")
        self.assertNotIn("XAI_API_KEY", clean)
        self.assertNotIn("GITHUB_TOKEN", clean)
        self.assertNotIn("AWS_SECRET_ACCESS_KEY", clean)
        self.assertNotIn("CUSTOM_NON_SECRET", clean)

        forwarded = _external_helper_environment(
            environment,
            adapter_id="fixture",
            profile_name="default",
            forwarded_names=("XAI_API_KEY",),
        )
        self.assertEqual(forwarded["XAI_API_KEY"], environment["XAI_API_KEY"])
        self.assertNotIn("GITHUB_TOKEN", forwarded)

    def test_external_helper_environment_matches_windows_names_case_insensitively(self) -> None:
        environment = {
            "Path": r"C:\\Windows\\System32",
            "provider_token": "fixture-secret",
        }
        with patch("nexus_runtime.auth.broker.os.name", "nt"):
            clean = _external_helper_environment(
                environment,
                adapter_id="fixture",
                profile_name="default",
                forwarded_names=("PROVIDER_TOKEN",),
            )
        self.assertEqual(clean["Path"], environment["Path"])
        self.assertEqual(clean["provider_token"], environment["provider_token"])

    def test_remote_ollama_retains_no_proxy_no_redirect_opener(self) -> None:
        captured_handlers: list[object] = []

        class Opener:
            def open(self, request, timeout):
                return _JSONResponse()

        def fake_build_opener(*handlers):
            captured_handlers.extend(handlers)
            return Opener()

        with patch("nexus_runtime.adapters.ollama.build_opener", side_effect=fake_build_opener):
            OllamaTransport("https://ollama.example", allow_remote=True)

        proxies = [handler.proxies for handler in captured_handlers if isinstance(handler, ProxyHandler)]
        self.assertEqual(proxies, [{}])
        self.assertTrue(any(type(handler).__name__ == "_NoRedirectHandler" for handler in captured_handlers))

    def test_council_scrubs_model_output_before_world_persistence_and_stamps_protocol(self) -> None:
        canary = "xai-" + "A" * 48
        world = WorldStore()
        actors = tuple(_SecretEmittingActor(member_id, canary) for member_id in ("alpha", "beta", "gamma"))
        result = CouncilCoordinator(world).run("audit question", actors)

        session = world.inspect(result["session_ref"])
        receipt = world.inspect(result["receipt_ref"])
        self.assertEqual(API_PROTOCOL_VERSION, PROTOCOL_VERSION)
        self.assertNotIn(canary, canonical_json(session.as_dict()))
        self.assertEqual(receipt.payload["protocol"], PROTOCOL_VERSION)


if __name__ == "__main__":
    unittest.main()
