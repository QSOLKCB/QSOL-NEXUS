from __future__ import annotations

import os
from pathlib import Path
import stat
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.request import ProxyHandler

from nexus_runtime.auth.broker import _external_helper_environment
from nexus_runtime.auth.oauth import OAuthHTTPClient
from nexus_runtime.world import WorldStore


class _JSONResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, limit: int = -1) -> bytes:
        return b"{}"


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


if __name__ == "__main__":
    unittest.main()
