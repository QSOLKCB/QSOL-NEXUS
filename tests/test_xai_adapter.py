from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from http.client import IncompleteRead, RemoteDisconnected
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from urllib.error import HTTPError

from nexus_runtime import NexusAPI
from nexus_runtime.__main__ import main
from nexus_runtime.adapters import AdapterAuthenticationError, AdapterError, AdapterProtocolError
from nexus_runtime.adapters.xai import (
    XAI_API_BASE_URL,
    XAI_SETUP_URL,
    XAIActor,
    XAITransport,
    _NoRedirectHandler,
    xai_auth_descriptor,
    xai_connection_test,
)
from nexus_runtime.auth import AuthBroker, AuthFlow, SecretMaterial
from nexus_runtime.auth.storage import FileSecretStore
from nexus_runtime.types import Ballot, CouncilMember, Phase, PhaseContext


FAKE_XAI_KEY = "xai-fixture-key-DO-NOT-PRINT"


def response_payload(text: str, *, status: str = "completed") -> dict[str, object]:
    return {
        "status": status,
        "error": None,
        "output": [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": text}],
            }
        ],
    }


class _FakeResponse:
    def __init__(self, value: object, *, raw: bytes | None = None) -> None:
        self.raw = raw if raw is not None else json.dumps(value).encode("utf-8")

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, maximum: int = -1) -> bytes:
        return self.raw


class _FakeOpener:
    def __init__(self, *values: object) -> None:
        self.values = list(values)
        self.requests: list[tuple[object, float]] = []

    def open(self, request: object, *, timeout: float) -> _FakeResponse:
        self.requests.append((request, timeout))
        value = self.values.pop(0)
        if isinstance(value, BaseException):
            raise value
        return _FakeResponse(value)


class _ReadErrorResponse(_FakeResponse):
    def __init__(self, error: BaseException) -> None:
        super().__init__({})
        self.error = error

    def read(self, maximum: int = -1) -> bytes:
        raise self.error


class _StubTransport:
    def __init__(self, *results: str) -> None:
        self.results = list(results)
        self.calls: list[tuple[str, str, int, bool]] = []

    def generate(
        self,
        model: str,
        prompt: str,
        *,
        max_output_tokens: int,
        require_complete: bool = True,
    ) -> str:
        self.calls.append((model, prompt, max_output_tokens, require_complete))
        return self.results.pop(0)


class XAITransportTests(unittest.TestCase):
    def material(self) -> SecretMaterial:
        return SecretMaterial(FAKE_XAI_KEY)

    def test_descriptor_admits_api_key_sources_but_not_grok_build_oauth(self) -> None:
        descriptor = xai_auth_descriptor()
        self.assertEqual(descriptor.adapter_id, "xai")
        self.assertEqual(descriptor.setup_url, XAI_SETUP_URL)
        self.assertEqual(
            descriptor.auth_flows,
            (AuthFlow.API_KEY, AuthFlow.ENVIRONMENT, AuthFlow.EXTERNAL_COMMAND),
        )
        self.assertNotIn(AuthFlow.BROWSER_PKCE, descriptor.auth_flows)
        self.assertNotIn(AuthFlow.DEVICE_CODE, descriptor.auth_flows)

    def test_responses_request_is_fixed_stateless_bounded_and_keeps_key_out_of_body(self) -> None:
        opener = _FakeOpener(response_payload("Evidence, not prestige."))
        transport = XAITransport(self.material(), timeout_seconds=42, _opener=opener)
        result = transport.generate("grok-4.5", "Council prompt", max_output_tokens=1024)
        self.assertEqual(result, "Evidence, not prestige.")
        request, timeout = opener.requests[0]
        self.assertEqual(request.full_url, f"{XAI_API_BASE_URL}/responses")
        self.assertEqual(timeout, 42)
        self.assertEqual(request.get_header("Authorization"), f"Bearer {FAKE_XAI_KEY}")
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["model"], "grok-4.5")
        self.assertFalse(payload["store"])
        self.assertNotIn(FAKE_XAI_KEY, request.data.decode("utf-8"))
        self.assertNotIn(FAKE_XAI_KEY, repr(transport))

    def test_redirects_and_auth_errors_are_rejected_without_error_body_disclosure(self) -> None:
        self.assertIsNone(_NoRedirectHandler().redirect_request(None, None, 302, "redirect", {}, "https://evil.test"))
        leaked = "xai-leaked-body /private/operator/key"
        error = HTTPError(
            f"{XAI_API_BASE_URL}/models",
            401,
            leaked,
            {},
            io.BytesIO(leaked.encode("utf-8")),
        )
        transport = XAITransport(self.material(), _opener=_FakeOpener(error))
        with self.assertRaises(AdapterAuthenticationError) as raised:
            transport.probe()
        self.assertEqual(str(raised.exception), "xAI rejected the configured credential")
        self.assertNotIn(leaked, str(raised.exception))
        self.assertNotIn(FAKE_XAI_KEY, str(raised.exception))

    def test_oversized_or_invalid_provider_responses_fail_closed(self) -> None:
        oversized = _FakeOpener()
        oversized.values = [None]
        transport = XAITransport(self.material(), _opener=oversized)
        oversized.open = mock.Mock(return_value=_FakeResponse({}, raw=b"x" * (4 * 1024 * 1024 + 1)))
        with self.assertRaisesRegex(AdapterProtocolError, "size limit"):
            transport.generate("grok-4.5", "prompt", max_output_tokens=64)

        malformed = XAITransport(self.material(), _opener=mock.Mock())
        malformed._opener.open.return_value = _FakeResponse({}, raw=b"not json")
        with self.assertRaisesRegex(AdapterProtocolError, "invalid JSON"):
            malformed.probe()

    def test_http_protocol_failures_are_sanitized_during_open_and_read(self) -> None:
        open_failure = XAITransport(
            self.material(),
            _opener=_FakeOpener(RemoteDisconnected("provider closed /private/operator/path")),
        )
        with self.assertRaises(AdapterError) as opened:
            open_failure.probe()
        self.assertEqual(str(opened.exception), "xAI inference API is unavailable")

        read_opener = mock.Mock()
        read_opener.open.return_value = _ReadErrorResponse(IncompleteRead(b"partial-secret", 100))
        read_failure = XAITransport(self.material(), _opener=read_opener)
        with self.assertRaises(AdapterError) as read:
            read_failure.probe()
        self.assertEqual(str(read.exception), "xAI inference API is unavailable")

    def test_successful_responses_reject_reflected_and_credential_shaped_text(self) -> None:
        github_token = "ghp_" + "Z" * 32
        for leaked in (FAKE_XAI_KEY, github_token):
            with self.subTest(leaked=leaked[:4]):
                transport = XAITransport(
                    self.material(),
                    _opener=_FakeOpener(response_payload(f"provider reflected {leaked}")),
                )
                with self.assertRaises(AdapterProtocolError) as raised:
                    transport.generate("grok-4.5", "prompt", max_output_tokens=64)
                self.assertNotIn(leaked, str(raised.exception))

        model_response = {
            "models": [
                {
                    "id": "grok-4.5",
                    "aliases": [],
                    "input_modalities": ["text"],
                    "output_modalities": ["text"],
                    "owned_by": f"xAI {FAKE_XAI_KEY}",
                }
            ]
        }
        transport = XAITransport(self.material(), _opener=_FakeOpener(model_response))
        with self.assertRaises(AdapterProtocolError) as raised:
            transport.list_language_models()
        self.assertNotIn(FAKE_XAI_KEY, str(raised.exception))

    def test_rate_limit_error_describes_the_request(self) -> None:
        error = HTTPError(f"{XAI_API_BASE_URL}/models", 429, "fixture", {}, io.BytesIO())
        transport = XAITransport(self.material(), _opener=_FakeOpener(error))
        with self.assertRaises(AdapterError) as raised:
            transport.probe()
        self.assertEqual(str(raised.exception), "xAI request was rate-limited")

    def test_incomplete_phase_can_be_used_but_incomplete_ballot_cannot(self) -> None:
        first = response_payload("bounded partial contribution", status="incomplete")
        second = response_payload('{"choice":"TEST_FURTHER","rationale":"partial"}', status="incomplete")
        transport = XAITransport(self.material(), _opener=_FakeOpener(first, second))
        self.assertEqual(
            transport.generate("grok-4.5", "phase", max_output_tokens=64, require_complete=False),
            "bounded partial contribution",
        )
        with self.assertRaisesRegex(AdapterProtocolError, "truncated"):
            transport.generate("grok-4.5", "ballot", max_output_tokens=64, require_complete=True)

    def test_language_model_discovery_is_bounded_sanitized_and_sorted(self) -> None:
        opener = _FakeOpener(
            {
                "models": [
                    {
                        "id": "grok-z",
                        "aliases": ["grok-latest"],
                        "input_modalities": ["text", "image"],
                        "output_modalities": ["text"],
                        "created": 123,
                        "owned_by": "xai",
                        "version": "1.0",
                        "fingerprint": "fp_fixture",
                        "prompt_text_token_price": 123456,
                    },
                    {
                        "id": "grok-a",
                        "aliases": [],
                        "input_modalities": ["text"],
                        "output_modalities": ["text"],
                    },
                ]
            }
        )
        models = XAITransport(self.material(), _opener=opener).list_language_models()
        self.assertEqual([item["id"] for item in models], ["grok-a", "grok-z"])
        self.assertNotIn("prompt_text_token_price", models[1])
        request, _ = opener.requests[0]
        self.assertEqual(request.full_url, f"{XAI_API_BASE_URL}/language-models")

    def test_language_model_discovery_rejects_non_text_and_path_shaped_ids(self) -> None:
        bad_entries = (
            {
                "id": "../secret",
                "aliases": [],
                "input_modalities": ["text"],
                "output_modalities": ["text"],
            },
            {
                "id": "grok-image-only",
                "aliases": [],
                "input_modalities": ["text"],
                "output_modalities": ["image"],
            },
            {
                "id": "xai-" + "A" * 40,
                "aliases": [],
                "input_modalities": ["text"],
                "output_modalities": ["text"],
            },
            {
                "id": "grok-malformed-metadata",
                "aliases": [],
                "input_modalities": ["text", "image\nunsafe"],
                "output_modalities": ["text"],
            },
        )
        for entry in bad_entries:
            with self.subTest(entry=entry):
                transport = XAITransport(self.material(), _opener=_FakeOpener({"models": [entry]}))
                with self.assertRaises(AdapterProtocolError):
                    transport.list_language_models()

    def test_connection_test_returns_only_bounded_codes(self) -> None:
        with mock.patch.object(XAITransport, "probe", return_value=None):
            self.assertEqual(xai_connection_test(self.material()).public_dict(), {"status": "healthy", "code": "xai_healthy"})
        with mock.patch.object(
            XAITransport,
            "probe",
            side_effect=AdapterAuthenticationError("provider body that must not escape"),
        ):
            self.assertEqual(
                xai_connection_test(self.material()).public_dict(),
                {"status": "unavailable", "code": "xai_auth_rejected"},
            )
        self.assertEqual(
            xai_connection_test(None).public_dict(),
            {"status": "unavailable", "code": "xai_credential_missing"},
        )


class XAIActorTests(unittest.TestCase):
    def context(self) -> PhaseContext:
        return PhaseContext(
            "session",
            Phase.WHITE,
            "question",
            "object:" + "a" * 64,
            {},
            mode_id="analytical",
            mode_instruction="Separate evidence from inference.",
            geometry_region_id="laboratory",
        )

    def test_actor_uses_shared_council_prompts_and_strict_ballot_parser(self) -> None:
        transport = _StubTransport(
            "A bounded contribution.",
            '{"choice":"TEST_FURTHER","rationale":"Needs replication."}',
        )
        actor = XAIActor(
            CouncilMember("Grok", "grok-4.5", adapter_id="xai"),
            "grok-4.5",
            transport,  # type: ignore[arg-type]
        )
        self.assertEqual(actor.respond(self.context()), "A bounded contribution.")
        choice, rationale = actor.ballot(self.context())
        self.assertEqual(choice, Ballot.TEST_FURTHER)
        self.assertEqual(rationale, "Needs replication.")
        self.assertIn("exactly one equal vote", transport.calls[0][1])
        self.assertFalse(transport.calls[0][3])
        self.assertIn("sealed ballot", transport.calls[1][1])
        self.assertTrue(transport.calls[1][3])
        self.assertFalse(actor.replayable)
        self.assertEqual(actor.identity_metadata()["remote_host"], "api.x.ai")
        self.assertFalse(actor.identity_metadata()["responses_api_store"])
        self.assertNotIn("provider_response_storage", actor.identity_metadata())

    def test_actor_rejects_invalid_ballot_shape(self) -> None:
        actor = XAIActor(
            CouncilMember("Grok", "grok-4.5", adapter_id="xai"),
            "grok-4.5",
            _StubTransport('{"choice":"TEST_FURTHER","rationale":"ok","vote_weight":2}'),  # type: ignore[arg-type]
        )
        with self.assertRaises(AdapterProtocolError):
            actor.ballot(self.context())


class XAIAPIAndCLITests(unittest.TestCase):
    def broker(self, root: Path) -> AuthBroker:
        store = FileSecretStore(root)
        broker = AuthBroker(
            root,
            secret_stores={store.backend_id: store},
            environment={"XAI_API_KEY": FAKE_XAI_KEY},
        )
        broker.add_environment("xai", "default", "XAI_API_KEY")
        return broker

    def test_api_model_discovery_and_direct_actor_use_only_profile_reference(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            api = NexusAPI(base / "world", auth_broker=self.broker(base / "auth"))
            discovered = [{"id": "grok-4.5", "aliases": [], "input_modalities": ["text"], "output_modalities": ["text"]}]
            with mock.patch.object(XAITransport, "list_language_models", return_value=discovered):
                models = api.handle({"operation": "models.list", "adapter_id": "xai"})
            self.assertEqual(models["models"], discovered)
            self.assertTrue(models["remote_verified"])

            with mock.patch.object(XAITransport, "generate", return_value="Remote answer") as generate:
                chat = api.handle(
                    {
                        "operation": "actor.chat",
                        "member": {"member_id": "Grok", "model_id": "grok-4.5", "adapter_id": "xai"},
                        "message": "hello",
                    }
                )
            self.assertEqual(chat["status"], "ok")
            self.assertEqual(chat["response"], "Remote answer")
            prompt = generate.call_args.args[1]
            self.assertNotIn(FAKE_XAI_KEY, prompt)
            world_bytes = b"".join(path.read_bytes() for path in (base / "world").rglob("*") if path.is_file())
            self.assertNotIn(FAKE_XAI_KEY.encode("utf-8"), world_bytes)

    def test_xai_member_rejects_endpoint_overrides_and_inline_credentials_before_network(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            api = NexusAPI(Path(directory) / "world", auth_broker=self.broker(Path(directory) / "auth"))
            for forbidden in (
                {"endpoint": "https://evil.test/v1"},
                {"base_url": "https://evil.test/v1"},
                {"api_key": FAKE_XAI_KEY},
                {"deployment_metadata": {"api_key": FAKE_XAI_KEY}},
            ):
                with self.subTest(forbidden=forbidden):
                    member = {"member_id": "Grok", "model_id": "grok-4.5", "adapter_id": "xai", **forbidden}
                    with mock.patch.object(XAITransport, "generate") as generate:
                        response = api.handle({"operation": "actor.chat", "member": member, "message": "do not connect"})
                    self.assertEqual(response["status"], "error")
                    self.assertEqual(response["error"]["code"], "invalid_request")
                    generate.assert_not_called()

            with mock.patch.object(XAITransport, "generate") as generate:
                response = api.handle(
                    {
                        "operation": "actor.chat",
                        "member": {
                            "member_id": "Grok",
                            "model_id": "xai-" + "A" * 40,
                            "adapter_id": "xai",
                        },
                        "message": "do not connect",
                    }
                )
            self.assertEqual(response["status"], "error")
            self.assertEqual(response["error"]["code"], "invalid_request")
            generate.assert_not_called()

    def test_council_rejects_excess_remote_seats_before_resolving_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            api = NexusAPI(Path(directory) / "world", auth_broker=self.broker(Path(directory) / "auth"))
            members = [
                {
                    "member_id": f"Grok{index}",
                    "model_id": f"grok-{index}",
                    "adapter_id": "xai",
                }
                for index in range(5)
            ]
            with (
                mock.patch.object(api.auth, "resolve") as resolve,
                mock.patch.object(XAITransport, "generate") as generate,
            ):
                response = api.handle(
                    {"operation": "council.run", "question": "bounded spend", "members": members}
                )
            self.assertEqual(response["status"], "error")
            self.assertEqual(response["error"]["code"], "invalid_request")
            self.assertIn("at most 4 remote xAI seats", response["error"]["message"])
            resolve.assert_not_called()
            generate.assert_not_called()

    def test_council_rejects_credential_shaped_provider_output_before_persistence(self) -> None:
        leaked = "ghp_" + "R" * 32
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            api = NexusAPI(base / "world", auth_broker=self.broker(base / "auth"))
            opener = _FakeOpener(response_payload(f"malicious provider output {leaked}"))
            with mock.patch("nexus_runtime.adapters.xai.build_opener", return_value=opener):
                response = api.handle(
                    {
                        "operation": "council.run",
                        "question": "inspect the evidence",
                        "members": [
                            {"member_id": "LocalA", "model_id": "mock-a", "adapter_id": "mock"},
                            {"member_id": "LocalB", "model_id": "mock-b", "adapter_id": "mock"},
                            {"member_id": "Grok", "model_id": "grok-4.5", "adapter_id": "xai"},
                        ],
                    }
                )
            self.assertEqual(response["status"], "error")
            self.assertEqual(response["error"]["code"], "adapter_unavailable")
            self.assertNotIn(leaked, json.dumps(response, sort_keys=True))
            world_bytes = b"".join(path.read_bytes() for path in (base / "world").rglob("*") if path.is_file())
            self.assertNotIn(leaked.encode("utf-8"), world_bytes)

    def test_mixed_local_and_remote_council_preserves_equal_vote_and_scrubs_secrets(self) -> None:
        secret = FAKE_XAI_KEY
        prompts: list[str] = []

        def generate(_transport: object, model: str, prompt: str, **kwargs: object) -> str:
            prompts.append(prompt)
            if "sealed ballot" in prompt:
                return '{"choice":"TEST_FURTHER","rationale":"Remote evidence needs replication."}'
            return "A remote contribution based on evidence alone."

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            api = NexusAPI(base / "world", auth_broker=self.broker(base / "auth"))
            with mock.patch.object(XAITransport, "generate", autospec=True, side_effect=generate):
                result = api.handle(
                    {
                        "operation": "council.run",
                        "question": f"Assess this claim; accidental token={secret}",
                        "members": [
                            {"member_id": "LocalA", "model_id": "mock-a", "adapter_id": "mock"},
                            {"member_id": "LocalB", "model_id": "mock-b", "adapter_id": "mock"},
                            {"member_id": "Grok", "model_id": "grok-4.5", "adapter_id": "xai"},
                        ],
                    }
                )
            self.assertEqual(result["status"], "ok", result)
            session = api.world.inspect(result["session_ref"])
            remote = next(row for row in session.payload["roster"] if row["member_id"] == "Grok")
            self.assertEqual(remote["vote_weight"], 1)
            self.assertEqual(remote["epistemic_privilege"], "none")
            receipt = api.world.inspect(result["receipt_ref"])
            self.assertFalse(receipt.payload["replayable"])
            self.assertTrue(prompts)
            self.assertFalse(any(secret in prompt or FAKE_XAI_KEY in prompt for prompt in prompts))
            world_bytes = b"".join(path.read_bytes() for path in (base / "world").rglob("*") if path.is_file())
            self.assertNotIn(FAKE_XAI_KEY.encode("utf-8"), world_bytes)

    def test_browser_key_cli_opens_only_fixed_setup_url_and_keeps_key_out_of_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            errors = io.StringIO()
            with (
                mock.patch.dict(os.environ, {"NEXUS_AUTH_FORCE_FILE_STORE": "1"}),
                mock.patch("nexus_runtime.auth_cli.getpass", return_value=FAKE_XAI_KEY),
                mock.patch("nexus_runtime.auth_cli.webbrowser.open", return_value=True) as browser_open,
                redirect_stdout(output),
                redirect_stderr(errors),
            ):
                exit_code = main(
                    [
                        "--auth-root",
                        str(Path(directory).resolve()),
                        "auth",
                        "add",
                        "xai",
                        "--method",
                        "browser-key",
                    ]
                )
            self.assertEqual(exit_code, 0, output.getvalue())
            browser_open.assert_called_once_with(XAI_SETUP_URL)
            self.assertNotIn(FAKE_XAI_KEY, output.getvalue())
            self.assertNotIn(FAKE_XAI_KEY, errors.getvalue())
            self.assertIn(XAI_SETUP_URL, errors.getvalue())
            public = json.loads(output.getvalue())
            self.assertEqual(public["profile"]["auth_flow"], "api_key")

    def test_models_cli_uses_stored_profile_without_printing_key(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            auth_root = Path(directory).resolve()
            store = FileSecretStore(auth_root)
            broker = AuthBroker(auth_root, secret_stores={store.backend_id: store})
            broker.add_api_key("xai", "default", FAKE_XAI_KEY)
            output = io.StringIO()
            models = [{"id": "grok-4.5", "aliases": [], "input_modalities": ["text"], "output_modalities": ["text"]}]
            with mock.patch.object(XAITransport, "list_language_models", return_value=models), redirect_stdout(output):
                exit_code = main(["--auth-root", str(auth_root), "models", "list", "xai"])
            self.assertEqual(exit_code, 0, output.getvalue())
            self.assertNotIn(FAKE_XAI_KEY, output.getvalue())
            self.assertEqual(json.loads(output.getvalue())["models"], models)


if __name__ == "__main__":
    unittest.main()
