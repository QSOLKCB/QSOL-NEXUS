from __future__ import annotations

import base64
from contextlib import redirect_stdout
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import multiprocessing
import os
from pathlib import Path
from queue import Queue
import stat
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest import mock
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from urllib.request import urlopen

from nexus_runtime.__main__ import main
from nexus_runtime.api import NexusAPI
from nexus_runtime.auth import (
    AdapterAuthDescriptor,
    AuthBroker,
    AuthError,
    AuthFlow,
    AuthMethod,
    AuthProfile,
    AuthProtocolError,
    AuthTimeoutError,
    AuthUnavailableError,
    BrowserOAuthConfig,
    BrowserPKCEFlow,
    ConnectionCheck,
    DeviceCodeFlow,
    DeviceOAuthConfig,
    OAuthTokenClient,
    SecretMaterial,
)
from nexus_runtime.auth.oauth import MAX_DEVICE_AUTHORIZATION_SECONDS, OAuthHTTPClient
from nexus_runtime.auth.storage import FileSecretStore, ProfileStore, available_secret_stores
from nexus_runtime.auth_cli import run_auth_command


FAKE_ACCESS_TOKEN = "fixture-access-token-DO-NOT-PERSIST-IN-WORLD"
FAKE_REFRESH_TOKEN = "fixture-refresh-token-DO-NOT-PRINT"
REFRESHED_ACCESS_TOKEN = "fixture-refreshed-access-token"


def _headless_descriptor() -> AdapterAuthDescriptor:
    return AdapterAuthDescriptor(
        adapter_id="fixture",
        provider_name="Fixture Provider",
        local_or_remote="remote",
        auth_methods=(AuthMethod.API_CREDENTIAL,),
        auth_flows=(AuthFlow.ENVIRONMENT,),
    )


def _refresh_descriptor() -> AdapterAuthDescriptor:
    return AdapterAuthDescriptor(
        adapter_id="fixture",
        provider_name="Fixture Provider",
        local_or_remote="remote",
        auth_methods=(AuthMethod.PROVIDER_SUPPORTED_INTERACTIVE,),
        auth_flows=(AuthFlow.BROWSER_PKCE,),
        browser_oauth=BrowserOAuthConfig(
            authorization_endpoint="https://auth.example.test/authorize",
            token_endpoint="https://auth.example.test/token",
            client_id="client",
            scopes=("models.read", "inference"),
            allowed_endpoint_hosts=("auth.example.test",),
        ),
    )


class _SlowProfileStore(ProfileStore):
    def _load_unlocked(self) -> dict[str, AuthProfile]:
        profiles = super()._load_unlocked()
        time.sleep(0.15)
        return profiles


class _CoordinatedFileSecretStore(FileSecretStore):
    def __init__(self, root: str | Path, barrier: object) -> None:
        super().__init__(root)
        self._barrier = barrier
        self._first_get = True

    def get(self, handle: str) -> SecretMaterial:
        material = super().get(handle)
        if self._first_get:
            self._first_get = False
            self._barrier.wait(timeout=5)  # type: ignore[attr-defined]
        return material


class _ProcessTokenClient:
    def __init__(self, refresh_count: object) -> None:
        self._refresh_count = refresh_count

    def refresh(self, config: object, material: SecretMaterial) -> SecretMaterial:
        with self._refresh_count.get_lock():  # type: ignore[attr-defined]
            self._refresh_count.value += 1  # type: ignore[attr-defined]
        time.sleep(0.1)
        return SecretMaterial(
            REFRESHED_ACCESS_TOKEN,
            material.refresh_token,
            expires_at=4_600.0,
            scopes=material.scopes,
        )


def _process_add_environment(root: str, profile_name: str, start: object, results: object) -> None:
    try:
        profile_store = _SlowProfileStore(root)
        secret_store = FileSecretStore(root)
        broker = AuthBroker(
            root,
            descriptors=(_headless_descriptor(),),
            profile_store=profile_store,
            secret_stores={secret_store.backend_id: secret_store},
        )
        start.wait(timeout=5)  # type: ignore[attr-defined]
        broker.add_environment("fixture", profile_name, "FIXTURE_TOKEN")
        results.put(None)  # type: ignore[attr-defined]
    except BaseException as exc:
        results.put(repr(exc))  # type: ignore[attr-defined]


def _process_resolve_refresh(
    root: str,
    barrier: object,
    refresh_count: object,
    results: object,
) -> None:
    try:
        secret_store = _CoordinatedFileSecretStore(root, barrier)
        broker = AuthBroker(
            root,
            descriptors=(_refresh_descriptor(),),
            secret_stores={secret_store.backend_id: secret_store},
            token_client=_ProcessTokenClient(refresh_count),  # type: ignore[arg-type]
            clock=lambda: 1_000.0,
        )
        material = broker.resolve("fixture", "shared")
        results.put(material.access_token)  # type: ignore[union-attr,attr-defined]
    except BaseException as exc:
        results.put(repr(exc))  # type: ignore[attr-defined]


class _OAuthFixtureHandler(BaseHTTPRequestHandler):
    posted: list[tuple[str, dict[str, list[str]]]] = []
    device_polls = 0
    redirect_leak_contacted = False

    @classmethod
    def reset(cls) -> None:
        cls.posted = []
        cls.device_polls = 0
        cls.redirect_leak_contacted = False

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        form = parse_qs(self.rfile.read(length).decode("ascii"), keep_blank_values=True)
        type(self).posted.append((self.path, form))
        if self.path == "/device":
            port = self.server.server_port
            self._json(
                200,
                {
                    "device_code": "secret-device-code",
                    "user_code": "NEX-US16",
                    "verification_uri": f"http://127.0.0.1:{port}/verify",
                    "verification_uri_complete": f"http://127.0.0.1:{port}/verify?code=NEX-US16",
                    "expires_in": 120,
                    "interval": 1,
                },
            )
            return
        if self.path == "/redirect-token":
            self.send_response(302)
            self.send_header("Location", f"http://127.0.0.1:{self.server.server_port}/leak")
            self.end_headers()
            return
        if self.path != "/token":
            self._json(404, {"error": "not_found"})
            return
        grant_type = form.get("grant_type", [""])[0]
        if grant_type == "urn:ietf:params:oauth:grant-type:device_code":
            type(self).device_polls += 1
            if type(self).device_polls == 1:
                self._json(400, {"error": "authorization_pending", "secret_detail": FAKE_ACCESS_TOKEN})
                return
        if grant_type == "refresh_token":
            self._json(
                200,
                {
                    "access_token": REFRESHED_ACCESS_TOKEN,
                    "token_type": "Bearer",
                    "expires_in": 3600,
                },
            )
            return
        self._json(
            200,
            {
                "access_token": FAKE_ACCESS_TOKEN,
                "refresh_token": FAKE_REFRESH_TOKEN,
                "token_type": "Bearer",
                "expires_in": 3600,
                "id_token": "discard-this-id-token",
            },
        )

    def do_GET(self) -> None:
        if self.path == "/leak":
            type(self).redirect_leak_contacted = True
        self._json(200, {"ok": True})

    def _json(self, status: int, value: dict[str, object]) -> None:
        body = json.dumps(value).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return None


class _ServerFixture:
    def __enter__(self) -> ThreadingHTTPServer:
        _OAuthFixtureHandler.reset()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _OAuthFixtureHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self.server

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


def _descriptor(port: int, *, token_path: str = "/token") -> AdapterAuthDescriptor:
    host = "127.0.0.1"
    return AdapterAuthDescriptor(
        adapter_id="fixture",
        provider_name="Fixture Provider",
        local_or_remote="remote",
        auth_methods=(
            AuthMethod.API_CREDENTIAL,
            AuthMethod.PROVIDER_SUPPORTED_INTERACTIVE,
            AuthMethod.EXTERNAL_SECRET,
        ),
        auth_flows=(
            AuthFlow.API_KEY,
            AuthFlow.BROWSER_PKCE,
            AuthFlow.DEVICE_CODE,
            AuthFlow.ENVIRONMENT,
            AuthFlow.EXTERNAL_COMMAND,
        ),
        browser_oauth=BrowserOAuthConfig(
            authorization_endpoint=f"http://{host}:{port}/authorize",
            token_endpoint=f"http://{host}:{port}{token_path}",
            client_id="nexus-fixture-client",
            scopes=("models.read", "inference"),
            allowed_endpoint_hosts=(host,),
            callback_timeout_seconds=3,
            allow_insecure_loopback_provider=True,
        ),
        device_oauth=DeviceOAuthConfig(
            device_authorization_endpoint=f"http://{host}:{port}/device",
            token_endpoint=f"http://{host}:{port}/token",
            client_id="nexus-fixture-client",
            scopes=("models.read", "inference"),
            allowed_endpoint_hosts=(host,),
            allowed_verification_hosts=(host,),
            allow_insecure_loopback_provider=True,
        ),
    )


def _broker(root: Path, descriptor: AdapterAuthDescriptor, **kwargs: object) -> AuthBroker:
    store = FileSecretStore(root)
    return AuthBroker(
        root,
        descriptors=(descriptor,),
        secret_stores={store.backend_id: store},
        default_secret_backend=store.backend_id,
        **kwargs,
    )


class AuthTypeTests(unittest.TestCase):
    def test_descriptor_rejects_unadmitted_or_insecure_provider_endpoint(self) -> None:
        with self.assertRaisesRegex(AuthError, "HTTPS"):
            BrowserOAuthConfig(
                authorization_endpoint="http://auth.example.test/authorize",
                token_endpoint="http://auth.example.test/token",
                client_id="client",
                scopes=("openid",),
                allowed_endpoint_hosts=("auth.example.test",),
            )
        with self.assertRaisesRegex(AuthError, "not admitted"):
            BrowserOAuthConfig(
                authorization_endpoint="https://evil.example/authorize",
                token_endpoint="https://auth.example.test/token",
                client_id="client",
                scopes=("openid",),
                allowed_endpoint_hosts=("auth.example.test",),
            )

    def test_descriptor_rejects_ambiguous_sequence_shapes(self) -> None:
        with self.assertRaisesRegex(AuthError, "scopes"):
            BrowserOAuthConfig(
                authorization_endpoint="https://auth.example.test/authorize",
                token_endpoint="https://auth.example.test/token",
                client_id="client",
                scopes="openid",  # type: ignore[arg-type]
                allowed_endpoint_hosts=("auth.example.test",),
            )
        with self.assertRaisesRegex(AuthError, "key/value pairs"):
            BrowserOAuthConfig(
                authorization_endpoint="https://auth.example.test/authorize",
                token_endpoint="https://auth.example.test/token",
                client_id="client",
                scopes=("openid",),
                allowed_endpoint_hosts=("auth.example.test",),
                extra_authorization_params=("prompt",),  # type: ignore[arg-type]
            )
    def test_secret_material_repr_is_redacted(self) -> None:
        material = SecretMaterial(FAKE_ACCESS_TOKEN, FAKE_REFRESH_TOKEN)
        rendered = repr(material)
        self.assertNotIn(FAKE_ACCESS_TOKEN, rendered)
        self.assertNotIn(FAKE_REFRESH_TOKEN, rendered)
        self.assertIn("<redacted>", rendered)

    def test_secret_material_rejects_header_control_characters(self) -> None:
        with self.assertRaisesRegex(AuthProtocolError, "access token"):
            SecretMaterial("token\r\nInjected: value")

    def test_descriptor_public_shape_contains_no_authority_fields_or_oauth_endpoints(self) -> None:
        with _ServerFixture() as server:
            public = _descriptor(server.server_port).public_dict()
        encoded = json.dumps(public, sort_keys=True)
        self.assertNotIn("vote_weight", encoded)
        self.assertNotIn("epistemic_privilege", encoded)
        self.assertNotIn("authorization_endpoint", encoded)
        self.assertEqual(public["adapter_id"], "fixture")


class AuthStorageTests(unittest.TestCase):
    def test_file_store_uses_owner_only_permissions_and_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = FileSecretStore(root)
            handle = "cred-11111111111111111111111111111111"
            store.put(handle, SecretMaterial(FAKE_ACCESS_TOKEN, FAKE_REFRESH_TOKEN))
            path = root / "secrets" / f"{handle}.json"
            self.assertEqual(store.get(handle).access_token, FAKE_ACCESS_TOKEN)
            if os.name != "nt":
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
                self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)

    def test_file_store_fails_closed_on_loose_permissions(self) -> None:
        if os.name == "nt":
            self.skipTest("POSIX permission fixture")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = FileSecretStore(root)
            handle = "cred-22222222222222222222222222222222"
            store.put(handle, SecretMaterial(FAKE_ACCESS_TOKEN))
            path = root / "secrets" / f"{handle}.json"
            path.chmod(0o644)
            with self.assertRaisesRegex(AuthError, "owner-only"):
                store.get(handle)

    def test_file_store_delete_sanitizes_os_errors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = FileSecretStore(root)
            handle = "cred-55555555555555555555555555555555"
            store.put(handle, SecretMaterial(FAKE_ACCESS_TOKEN))
            leaked_path = str(root / "secrets" / f"{handle}.json")
            with mock.patch.object(Path, "unlink", side_effect=PermissionError(13, "denied", leaked_path)):
                with self.assertRaises(AuthUnavailableError) as raised:
                    store.delete(handle)
            self.assertEqual(str(raised.exception), "stored credential could not be deleted")
            self.assertNotIn(leaked_path, str(raised.exception))

    def test_profile_store_rejects_unknown_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = ProfileStore(root)
            store.path.write_text(
                json.dumps({"schema_version": "nexus-auth-profiles/1", "profiles": [], "extra": True}),
                encoding="utf-8",
            )
            store.path.chmod(0o600)
            with self.assertRaisesRegex(AuthError, "schema"):
                store.load()

    def test_store_rejects_symlinked_auth_directory(self) -> None:
        if os.name == "nt":
            self.skipTest("symbolic-link fixture")
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            target = base / "target"
            target.mkdir(mode=0o700)
            link = base / "auth-link"
            link.symlink_to(target, target_is_directory=True)
            store = FileSecretStore(link)
            with self.assertRaisesRegex(AuthError, "private directory"):
                store.put("cred-44444444444444444444444444444444", SecretMaterial(FAKE_ACCESS_TOKEN))

    def test_profile_store_rejects_symlinked_interprocess_lock(self) -> None:
        if os.name == "nt":
            self.skipTest("symbolic-link fixture")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "unrelated"
            target.write_bytes(b"x")
            target.chmod(0o600)
            (root / "auth.lock").symlink_to(target)
            with self.assertRaisesRegex(AuthError, "regular file"):
                ProfileStore(root).save({})

    def test_broker_does_not_chmod_or_write_into_broad_preexisting_root(self) -> None:
        if os.name == "nt":
            self.skipTest("POSIX permission fixture")
        with _ServerFixture() as server, tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.chmod(0o755)
            broker = _broker(root, _descriptor(server.server_port))
            with self.assertRaisesRegex(AuthError, "owner-only"):
                broker.add_api_key("fixture", "default", FAKE_ACCESS_TOKEN)
            self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o755)
            self.assertFalse((root / "secrets").exists())

    def test_os_keyring_is_preferred_when_an_available_backend_exists(self) -> None:
        class Backend:
            priority = 1

        class FakeKeyring:
            values: dict[tuple[str, str], str] = {}

            @staticmethod
            def get_keyring() -> Backend:
                return Backend()

            @classmethod
            def set_password(cls, service: str, handle: str, value: str) -> None:
                cls.values[(service, handle)] = value

            @classmethod
            def get_password(cls, service: str, handle: str) -> str | None:
                return cls.values.get((service, handle))

            @classmethod
            def delete_password(cls, service: str, handle: str) -> None:
                cls.values.pop((service, handle), None)

        with tempfile.TemporaryDirectory() as directory:
            stores, default = available_secret_stores(directory, keyring_module=FakeKeyring)
            self.assertEqual(default, "os_keyring")
            handle = "cred-33333333333333333333333333333333"
            stores[default].put(handle, SecretMaterial(FAKE_ACCESS_TOKEN))
            self.assertEqual(stores[default].get(handle).access_token, FAKE_ACCESS_TOKEN)

    def test_unavailable_keyring_write_falls_back_to_private_file_and_reports_it(self) -> None:
        class Backend:
            priority = 1

        class LockedKeyring:
            @staticmethod
            def get_keyring() -> Backend:
                return Backend()

            @staticmethod
            def set_password(service: str, handle: str, value: str) -> None:
                raise RuntimeError("keyring is locked")

            @staticmethod
            def get_password(service: str, handle: str) -> None:
                return None

            @staticmethod
            def delete_password(service: str, handle: str) -> None:
                return None

        with _ServerFixture() as server, tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stores, default = available_secret_stores(root, keyring_module=LockedKeyring)
            broker = AuthBroker(
                root,
                descriptors=(_descriptor(server.server_port),),
                secret_stores=stores,
                default_secret_backend=default,
            )
            result = broker.add_api_key("fixture", "default", FAKE_ACCESS_TOKEN)
            self.assertTrue(result["credential_backend_fallback"])
            self.assertEqual(result["profile"]["source"]["backend"], "private_file")
            profile = broker.profile_store.load()["fixture:default"]
            self.assertEqual(profile.secret_backend, "private_file")
            self.assertEqual(stores["private_file"].get(profile.credential_handle).access_token, FAKE_ACCESS_TOKEN)

    def test_profile_mutations_preserve_concurrent_process_updates(self) -> None:
        try:
            context = multiprocessing.get_context("fork")
        except ValueError:
            self.skipTest("fork-based interprocess lock fixture")
        with tempfile.TemporaryDirectory() as directory:
            start = context.Event()
            results = context.Queue()
            processes = [
                context.Process(
                    target=_process_add_environment,
                    args=(directory, profile_name, start, results),
                )
                for profile_name in ("alpha", "beta")
            ]
            for process in processes:
                process.start()
            start.set()
            for process in processes:
                process.join(timeout=10)
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=2)
                    self.fail("concurrent auth profile process did not finish")
            self.assertEqual([results.get(timeout=2) for _ in processes], [None, None])
            profiles = ProfileStore(directory).load()
            self.assertEqual(set(profiles), {"fixture:alpha", "fixture:beta"})
            if os.name != "nt":
                self.assertEqual(stat.S_IMODE((Path(directory) / "auth.lock").stat().st_mode), 0o600)


class AuthBrokerTests(unittest.TestCase):
    def test_auth_root_must_be_absolute(self) -> None:
        with self.assertRaisesRegex(AuthError, "absolute"):
            AuthBroker("relative-auth-root")

    def test_environment_source_resolves_without_persisting_the_token(self) -> None:
        with _ServerFixture() as server, tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            broker = _broker(
                root,
                _descriptor(server.server_port),
                environment={"FIXTURE_PROVIDER_TOKEN": FAKE_ACCESS_TOKEN},
            )
            added = broker.add_environment("fixture", "default", "FIXTURE_PROVIDER_TOKEN")
            self.assertEqual(broker.resolve("fixture").access_token, FAKE_ACCESS_TOKEN)
            public = json.dumps({"added": added, "listed": broker.list_profiles()}, sort_keys=True)
            persisted = (root / "profiles.json").read_text(encoding="utf-8")
            self.assertNotIn(FAKE_ACCESS_TOKEN, public)
            self.assertNotIn(FAKE_ACCESS_TOKEN, persisted)
            self.assertIn("FIXTURE_PROVIDER_TOKEN", public)

    def test_external_helper_uses_no_shell_and_does_not_persist_output(self) -> None:
        helper_script = (
            "import json,os; "
            "print(json.dumps({'access_token':os.environ['FIXTURE_PROVIDER_TOKEN'],'expires_in':3600}))"
        )
        with _ServerFixture() as server, tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            broker = _broker(
                root,
                _descriptor(server.server_port),
                environment={"FIXTURE_PROVIDER_TOKEN": FAKE_ACCESS_TOKEN},
            )
            broker.add_external_command("fixture", "corp", [sys.executable, "-c", helper_script])
            material = broker.resolve("fixture", "corp")
            self.assertEqual(material.access_token, FAKE_ACCESS_TOKEN)
            self.assertNotIn(FAKE_ACCESS_TOKEN, (root / "profiles.json").read_text(encoding="utf-8"))
            self.assertNotIn(FAKE_ACCESS_TOKEN, json.dumps(broker.list_profiles(), sort_keys=True))

    def test_external_helper_requires_absolute_executable_and_closed_json_shape(self) -> None:
        with _ServerFixture() as server, tempfile.TemporaryDirectory() as directory:
            broker = _broker(
                Path(directory),
                _descriptor(server.server_port),
                environment={"FIXTURE_PROVIDER_TOKEN": FAKE_ACCESS_TOKEN},
            )
            with self.assertRaisesRegex(AuthError, "absolute"):
                broker.add_external_command("fixture", "corp", ["helper"])
            with self.assertRaisesRegex(AuthError, "credential-bearing options"):
                broker.add_external_command(
                    "fixture",
                    "corp",
                    [sys.executable, "--token", "opaque-provider-value"],
                )
            with self.assertRaisesRegex(AuthError, "credential-bearing options"):
                broker.add_external_command(
                    "fixture",
                    "corp",
                    [sys.executable, "--api-key=opaque-provider-value"],
                )
            with self.assertRaisesRegex(AuthError, "credential-shaped"):
                broker.add_external_command("fixture", "corp", [sys.executable, "ghp_" + "Q" * 32])
            broker.add_external_command(
                "fixture",
                "corp",
                [
                    sys.executable,
                    "-c",
                    (
                        "import json,os; print(json.dumps({"
                        "'access_token':os.environ['FIXTURE_PROVIDER_TOKEN'],'extra':1}))"
                    ),
                ],
            )
            with self.assertRaisesRegex(AuthError, "unsupported fields"):
                broker.resolve("fixture", "corp")

    def test_external_helper_output_is_killed_at_the_broker_limit(self) -> None:
        with _ServerFixture() as server, tempfile.TemporaryDirectory() as directory:
            broker = _broker(Path(directory), _descriptor(server.server_port))
            broker.add_external_command(
                "fixture",
                "large",
                [sys.executable, "-c", "import sys; sys.stdout.write('x' * 1000000)"],
            )
            with self.assertRaisesRegex(AuthError, "size limit"):
                broker.resolve("fixture", "large")

    def test_api_key_profile_public_output_hides_handle_and_token_then_logout_deletes_both(self) -> None:
        with _ServerFixture() as server, tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            broker = _broker(root, _descriptor(server.server_port))
            added = broker.add_api_key("fixture", "personal", FAKE_ACCESS_TOKEN)
            public = json.dumps({"added": added, "list": broker.list_profiles()}, sort_keys=True)
            self.assertNotIn(FAKE_ACCESS_TOKEN, public)
            self.assertNotIn("credential_handle", public)
            self.assertEqual(len(list((root / "secrets").glob("*.json"))), 1)
            logged_out = broker.logout("fixture", "personal")
            self.assertTrue(logged_out["credential_removed"])
            self.assertEqual(list((root / "secrets").glob("*.json")), [])
            self.assertEqual(broker.list_profiles()["profiles"], [])

    def test_connection_test_exposes_only_bounded_status(self) -> None:
        observed: list[str] = []

        def tester(material: SecretMaterial | None) -> ConnectionCheck:
            self.assertIsNotNone(material)
            observed.append(material.access_token if material else "")
            return ConnectionCheck("healthy", "provider_healthy")

        with _ServerFixture() as server, tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = FileSecretStore(root)
            broker = AuthBroker(
                root,
                descriptors=(_descriptor(server.server_port),),
                secret_stores={store.backend_id: store},
                connection_testers={"fixture": tester},
            )
            broker.add_api_key("fixture", "default", FAKE_ACCESS_TOKEN)
            result = broker.test_profile("fixture")
            self.assertEqual(observed, [FAKE_ACCESS_TOKEN])
            self.assertTrue(result["remote_verified"])
            self.assertNotIn(FAKE_ACCESS_TOKEN, json.dumps(result, sort_keys=True))

    def test_connection_test_fails_closed_on_an_invalid_tester_result(self) -> None:
        with _ServerFixture() as server, tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = FileSecretStore(root)
            broker = AuthBroker(
                root,
                descriptors=(_descriptor(server.server_port),),
                secret_stores={store.backend_id: store},
                connection_testers={"fixture": lambda _: {"status": "healthy"}},  # type: ignore[dict-item]
            )
            broker.add_api_key("fixture", "default", FAKE_ACCESS_TOKEN)
            result = broker.test_profile("fixture")
            self.assertEqual(result["status"], "unavailable")
            self.assertFalse(result["remote_verified"])
            self.assertEqual(result["code"], "provider_test_failed")


class BrowserPKCETests(unittest.TestCase):
    def test_browser_callback_timeout_is_bounded_and_sanitized(self) -> None:
        with _ServerFixture() as provider:
            descriptor = _descriptor(provider.server_port)
            ticks = iter((0.0, 4.0))
            flow = BrowserPKCEFlow(browser_open=lambda _: True, monotonic=lambda: next(ticks))
            with self.assertRaisesRegex(AuthTimeoutError, "timed out"):
                flow.authorize(
                    descriptor.browser_oauth,  # type: ignore[arg-type]
                    open_browser=False,
                )

    def test_browser_pkce_rejects_wrong_state_then_exchanges_with_the_verifier(self) -> None:
        with _ServerFixture() as provider, tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            descriptor = _descriptor(provider.server_port)
            urls: Queue[str] = Queue()
            token_client = OAuthTokenClient(OAuthHTTPClient(timeout_seconds=2))
            browser_flow = BrowserPKCEFlow(token_client=token_client, browser_open=lambda _: True)
            broker = _broker(root, descriptor, browser_flow=browser_flow, token_client=token_client)
            outcome: dict[str, object] = {}

            def authorize() -> None:
                try:
                    outcome["result"] = broker.add_browser(
                        "fixture",
                        "personal",
                        open_browser=False,
                        on_authorization_url=urls.put,
                    )
                except BaseException as exc:
                    outcome["error"] = exc

            thread = threading.Thread(target=authorize, daemon=True)
            thread.start()
            authorization_url = urls.get(timeout=2)
            query = parse_qs(urlsplit(authorization_url).query)
            redirect_uri = query["redirect_uri"][0]
            state = query["state"][0]
            with self.assertRaises(HTTPError):
                urlopen(f"{redirect_uri}?code=wrong-code&state=wrong-state", timeout=2)
            with urlopen(f"{redirect_uri}?code=fixture-code&state={state}", timeout=2) as response:
                self.assertEqual(response.status, 200)
            thread.join(timeout=4)
            self.assertFalse(thread.is_alive())
            self.assertNotIn("error", outcome)

            token_posts = [form for path, form in _OAuthFixtureHandler.posted if path == "/token"]
            self.assertEqual(len(token_posts), 1)
            verifier = token_posts[0]["code_verifier"][0]
            expected_challenge = base64.urlsafe_b64encode(
                hashlib.sha256(verifier.encode("ascii")).digest()
            ).rstrip(b"=").decode("ascii")
            self.assertEqual(query["code_challenge"], [expected_challenge])
            self.assertEqual(token_posts[0]["redirect_uri"], [redirect_uri])

            public = json.dumps({"result": outcome["result"], "list": broker.list_profiles()}, sort_keys=True)
            self.assertNotIn(FAKE_ACCESS_TOKEN, public)
            self.assertNotIn(FAKE_REFRESH_TOKEN, public)
            resolved = broker.resolve("fixture", "personal")
            self.assertEqual(resolved.access_token, FAKE_ACCESS_TOKEN)
            self.assertEqual(resolved.scopes, ("models.read", "inference"))

    def test_token_endpoint_redirect_is_rejected_without_contacting_target(self) -> None:
        with _ServerFixture() as provider:
            descriptor = _descriptor(provider.server_port, token_path="/redirect-token")
            urls: Queue[str] = Queue()
            flow = BrowserPKCEFlow(browser_open=lambda _: True)
            outcome: list[BaseException] = []

            def authorize() -> None:
                try:
                    flow.authorize(
                        descriptor.browser_oauth,  # type: ignore[arg-type]
                        open_browser=False,
                        on_authorization_url=urls.put,
                    )
                except BaseException as exc:
                    outcome.append(exc)

            thread = threading.Thread(target=authorize, daemon=True)
            thread.start()
            query = parse_qs(urlsplit(urls.get(timeout=2)).query)
            with urlopen(f"{query['redirect_uri'][0]}?code=fixture&state={query['state'][0]}", timeout=2):
                pass
            thread.join(timeout=4)
            self.assertEqual(len(outcome), 1)
            self.assertIsInstance(outcome[0], AuthProtocolError)
            self.assertFalse(_OAuthFixtureHandler.redirect_leak_contacted)

    def test_expired_browser_token_refreshes_without_exposing_refresh_token(self) -> None:
        with _ServerFixture() as provider, tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            broker = _broker(root, _descriptor(provider.server_port), clock=lambda: 1_000.0)
            broker.add_api_key("fixture", "temporary", "placeholder")
            profile = broker.profile_store.load()["fixture:temporary"]
            store = broker.secret_stores[profile.secret_backend]
            store.put(
                profile.credential_handle,
                SecretMaterial(
                    access_token="expired-access",
                    refresh_token=FAKE_REFRESH_TOKEN,
                    expires_at=900.0,
                    scopes=("models.read", "inference"),
                ),
            )
            # Turn the fixture profile into a browser-flow profile without
            # exposing or re-entering the secret.
            browser_profile = type(profile)(
                **{
                    **profile.storage_dict(),
                    "auth_method": AuthMethod.PROVIDER_SUPPORTED_INTERACTIVE,
                    "auth_flow": AuthFlow.BROWSER_PKCE,
                }
            )
            broker.profile_store.upsert(browser_profile, replace=True)
            refreshed = broker.resolve("fixture", "temporary")
            self.assertEqual(refreshed.access_token, REFRESHED_ACCESS_TOKEN)
            self.assertEqual(refreshed.refresh_token, FAKE_REFRESH_TOKEN)
            self.assertEqual(refreshed.scopes, ("models.read", "inference"))
            refresh_posts = [form for path, form in _OAuthFixtureHandler.posted if path == "/token"]
            self.assertEqual(refresh_posts[0]["grant_type"], ["refresh_token"])

    def test_parallel_resolution_rotates_an_expired_refresh_token_once(self) -> None:
        class CountingTokenClient:
            calls = 0
            lock = threading.Lock()

            def refresh(self, config: object, material: SecretMaterial) -> SecretMaterial:
                with self.lock:
                    self.calls += 1
                time.sleep(0.05)
                return SecretMaterial(
                    REFRESHED_ACCESS_TOKEN,
                    material.refresh_token,
                    expires_at=4_600.0,
                )

        with _ServerFixture() as provider, tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = FileSecretStore(root)
            token_client = CountingTokenClient()
            broker = AuthBroker(
                root,
                descriptors=(_descriptor(provider.server_port),),
                secret_stores={store.backend_id: store},
                token_client=token_client,  # type: ignore[arg-type]
                clock=lambda: 1_000.0,
            )
            broker.add_api_key("fixture", "shared", "placeholder")
            profile = broker.profile_store.load()["fixture:shared"]
            store.put(
                profile.credential_handle,
                SecretMaterial("expired", FAKE_REFRESH_TOKEN, expires_at=900.0),
            )
            browser_profile = type(profile)(
                **{
                    **profile.storage_dict(),
                    "auth_method": AuthMethod.PROVIDER_SUPPORTED_INTERACTIVE,
                    "auth_flow": AuthFlow.BROWSER_PKCE,
                }
            )
            broker.profile_store.upsert(browser_profile, replace=True)
            results: list[str] = []
            threads = [
                threading.Thread(
                    target=lambda: results.append(broker.resolve("fixture", "shared").access_token),
                    daemon=True,
                )
                for _ in range(4)
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=2)
            self.assertEqual(results, [REFRESHED_ACCESS_TOKEN] * 4)
            self.assertEqual(token_client.calls, 1)

    def test_parallel_processes_rotate_an_expired_refresh_token_once(self) -> None:
        try:
            context = multiprocessing.get_context("fork")
        except ValueError:
            self.skipTest("fork-based interprocess lock fixture")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            handle = "cred-66666666666666666666666666666666"
            secret_store = FileSecretStore(root)
            secret_store.put(
                handle,
                SecretMaterial(
                    "expired",
                    FAKE_REFRESH_TOKEN,
                    expires_at=900.0,
                    scopes=("models.read", "inference"),
                ),
            )
            ProfileStore(root).upsert(
                AuthProfile(
                    adapter_id="fixture",
                    profile_name="shared",
                    auth_method=AuthMethod.PROVIDER_SUPPORTED_INTERACTIVE,
                    auth_flow=AuthFlow.BROWSER_PKCE,
                    secret_source="stored",
                    source_metadata={},
                    credential_handle=handle,
                    secret_backend="private_file",
                    created_at=1.0,
                    updated_at=1.0,
                )
            )
            barrier = context.Barrier(2)
            refresh_count = context.Value("i", 0)
            results = context.Queue()
            processes = [
                context.Process(
                    target=_process_resolve_refresh,
                    args=(directory, barrier, refresh_count, results),
                )
                for _ in range(2)
            ]
            for process in processes:
                process.start()
            for process in processes:
                process.join(timeout=10)
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=2)
                    self.fail("concurrent credential refresh process did not finish")
            self.assertEqual(
                [results.get(timeout=2) for _ in processes],
                [REFRESHED_ACCESS_TOKEN, REFRESHED_ACCESS_TOKEN],
            )
            self.assertEqual(refresh_count.value, 1)


class DeviceCodeTests(unittest.TestCase):
    def test_device_flow_polls_pending_then_returns_token_and_bounded_prompt(self) -> None:
        with _ServerFixture() as provider:
            descriptor = _descriptor(provider.server_port)
            prompts: list[dict[str, str | None]] = []
            flow = DeviceCodeFlow(
                OAuthHTTPClient(timeout_seconds=2),
                sleep=lambda _: None,
            )
            material = flow.authorize(
                descriptor.device_oauth,  # type: ignore[arg-type]
                on_prompt=lambda prompt: prompts.append(prompt.public_dict()),
            )
            self.assertEqual(material.access_token, FAKE_ACCESS_TOKEN)
            self.assertEqual(material.scopes, ("models.read", "inference"))
            self.assertEqual(_OAuthFixtureHandler.device_polls, 2)
            self.assertEqual(prompts[0]["user_code"], "NEX-US16")
            self.assertNotIn("secret-device-code", json.dumps(prompts))

    def test_device_flow_rejects_provider_supplied_phishing_url(self) -> None:
        class BadHTTP:
            def post_form(self, endpoint: str, form: object, config: object) -> dict[str, object]:
                return {
                    "device_code": "secret",
                    "user_code": "CODE",
                    "verification_uri": "https://evil.example/login",
                    "expires_in": 60,
                }

        with _ServerFixture() as provider:
            descriptor = _descriptor(provider.server_port)
            flow = DeviceCodeFlow(BadHTTP())  # type: ignore[arg-type]
            with self.assertRaisesRegex(AuthProtocolError, "not admitted"):
                flow.authorize(descriptor.device_oauth, on_prompt=lambda _: None)  # type: ignore[arg-type]

    def test_device_flow_caps_provider_supplied_lifetime(self) -> None:
        class LongLivedHTTP:
            calls = 0

            def post_form(self, endpoint: str, form: object, config: object) -> dict[str, object]:
                self.calls += 1
                if self.calls > 1:
                    raise AssertionError("the capped flow should expire before polling")
                return {
                    "device_code": "secret",
                    "user_code": "CODE",
                    "verification_uri": "https://verify.example.test/login",
                    "expires_in": MAX_DEVICE_AUTHORIZATION_SECONDS * 10,
                    "interval": MAX_DEVICE_AUTHORIZATION_SECONDS * 2,
                }

        elapsed = [0.0]
        http = LongLivedHTTP()
        config = DeviceOAuthConfig(
            device_authorization_endpoint="https://auth.example.test/device",
            token_endpoint="https://auth.example.test/token",
            client_id="client",
            scopes=("models.read",),
            allowed_endpoint_hosts=("auth.example.test",),
            allowed_verification_hosts=("verify.example.test",),
        )
        flow = DeviceCodeFlow(
            http,  # type: ignore[arg-type]
            monotonic=lambda: elapsed[0],
            sleep=lambda seconds: elapsed.__setitem__(0, elapsed[0] + seconds),
        )
        with self.assertRaisesRegex(AuthTimeoutError, "timed out"):
            flow.authorize(config, on_prompt=lambda _: None)
        self.assertEqual(elapsed[0], MAX_DEVICE_AUTHORIZATION_SECONDS)
        self.assertEqual(http.calls, 1)


class AuthAPITests(unittest.TestCase):
    def test_jsonl_auth_operations_and_world_storage_never_return_or_persist_token(self) -> None:
        with _ServerFixture() as provider, tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            auth_root = base / "auth"
            world_root = base / "world"
            broker = _broker(auth_root, _descriptor(provider.server_port))
            broker.add_api_key("fixture", "default", FAKE_ACCESS_TOKEN)
            api = NexusAPI(world_root, auth_broker=broker)
            listed = api.handle({"request_id": "a", "operation": "auth.list"})
            tested = api.handle({"request_id": "b", "operation": "auth.test", "adapter_id": "fixture"})
            health = api.handle({"request_id": "c", "operation": "system.health"})
            operations = api.handle({"operation": "system.operations"})
            encoded = json.dumps([listed, tested, health, operations], sort_keys=True)
            self.assertNotIn(FAKE_ACCESS_TOKEN, encoded)
            self.assertNotIn(FAKE_REFRESH_TOKEN, encoded)
            self.assertIn("auth.list", operations["operations"])
            self.assertFalse(health["remote_provider_auth"])
            self.assertEqual(health["auth_broker"]["remote_auth_descriptor_count"], 1)
            self.assertFalse(health["auth_broker"]["remote_adapters_admitted"])
            if world_root.exists():
                world_bytes = b"".join(path.read_bytes() for path in world_root.rglob("*") if path.is_file())
                self.assertNotIn(FAKE_ACCESS_TOKEN.encode("utf-8"), world_bytes)

    def test_api_rejects_auth_storage_nested_inside_world_storage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world_root = Path(directory) / "world"
            auth_root = world_root / "auth"
            with self.assertRaisesRegex(ValueError, "disjoint"):
                NexusAPI(world_root, auth_root=auth_root)

    def test_cli_auth_adapters_is_noninteractive_and_secret_free(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--auth-root", directory, "auth", "adapters"])
            self.assertEqual(exit_code, 0)
            value = json.loads(output.getvalue())
            self.assertEqual([row["adapter_id"] for row in value["adapters"]], ["mock", "ollama"])
            self.assertNotIn("credential", output.getvalue())

    def test_cli_rejects_auth_storage_nested_inside_world_storage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world_root = Path(directory) / "world"
            auth_root = world_root / "auth"
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(
                    [
                        "--world",
                        str(world_root),
                        "--auth-root",
                        str(auth_root),
                        "auth",
                        "adapters",
                    ]
                )
            self.assertEqual(exit_code, 2)
            value = json.loads(output.getvalue())
            self.assertEqual(value["error"]["message"], "auth storage and world storage must be disjoint directories")
            self.assertFalse(auth_root.exists())

    def test_cli_sanitizes_raw_os_errors(self) -> None:
        leaked_path = "/private/operator/auth/secrets/token.json"

        class FailingBroker:
            @staticmethod
            def adapters() -> dict[str, object]:
                raise PermissionError(13, "denied", leaked_path)

        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = run_auth_command(
                SimpleNamespace(auth_action="adapters"),  # type: ignore[arg-type]
                FailingBroker(),  # type: ignore[arg-type]
            )
        self.assertEqual(exit_code, 2)
        value = json.loads(output.getvalue())
        self.assertEqual(value["error"]["message"], "authentication operation failed")
        self.assertNotIn(leaked_path, output.getvalue())


if __name__ == "__main__":
    unittest.main()
