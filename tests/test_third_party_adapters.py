from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from nexus_runtime import NexusAPI
from nexus_runtime.adapters import AdapterProtocolError
from nexus_runtime.adapters.third_party import (
    THIRD_PARTY_PROVIDER_IDS,
    ThirdPartyActor,
    ThirdPartyTransport,
    provider_spec,
)
from nexus_runtime.auth import AuthBroker, AuthFlow, SecretMaterial
from nexus_runtime.auth.storage import FileSecretStore
from nexus_runtime.types import Ballot, CouncilMember, Phase, PhaseContext


FAKE_KEY = "fixture-provider-key-DO-NOT-PRINT"


class _FakeResponse:
    def __init__(self, value: object) -> None:
        self.raw = json.dumps(value).encode("utf-8")

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
        return _FakeResponse(self.values.pop(0))


def _responses(text: str, *, status: str = "completed") -> dict[str, object]:
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


def _anthropic(text: str, *, stop_reason: str = "end_turn") -> dict[str, object]:
    return {
        "type": "message",
        "stop_reason": stop_reason,
        "content": [{"type": "text", "text": text}],
    }


def _gemini(text: str, *, finish_reason: str = "STOP") -> dict[str, object]:
    return {
        "candidates": [
            {
                "finishReason": finish_reason,
                "content": {"parts": [{"text": text}]},
            }
        ]
    }


def _chat(text: str, *, finish_reason: str = "stop") -> dict[str, object]:
    return {
        "choices": [
            {
                "finish_reason": finish_reason,
                "message": {"role": "assistant", "content": text},
            }
        ]
    }


class ThirdPartyTransportTests(unittest.TestCase):
    def material(self) -> SecretMaterial:
        return SecretMaterial(FAKE_KEY)

    def test_all_requested_providers_are_admitted_auth_descriptors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = FileSecretStore(root)
            broker = AuthBroker(root, secret_stores={store.backend_id: store})
            descriptors = {item["adapter_id"]: item for item in broker.adapters()["adapters"]}
        self.assertTrue({"openai", "anthropic", "gemini", "groq", "together"}.issubset(descriptors))
        for adapter_id in THIRD_PARTY_PROVIDER_IDS:
            with self.subTest(adapter_id=adapter_id):
                descriptor = descriptors[adapter_id]
                self.assertEqual(descriptor["local_or_remote"], "remote")
                self.assertIn(AuthFlow.API_KEY.value, descriptor["auth_flows"])
                self.assertIn(AuthFlow.ENVIRONMENT.value, descriptor["auth_flows"])
                self.assertIn(AuthFlow.EXTERNAL_COMMAND.value, descriptor["auth_flows"])

    def test_openai_uses_fixed_responses_endpoint_and_store_false(self) -> None:
        opener = _FakeOpener(_responses("OpenAI answer"))
        transport = ThirdPartyTransport("openai", self.material(), timeout_seconds=42, _opener=opener)
        self.assertEqual(
            transport.generate("gpt-5.5", "prompt", max_output_tokens=128),
            "OpenAI answer",
        )
        request, timeout = opener.requests[0]
        self.assertEqual(request.full_url, "https://api.openai.com/v1/responses")
        self.assertEqual(request.get_header("Authorization"), f"Bearer {FAKE_KEY}")
        self.assertEqual(timeout, 42)
        payload = json.loads(request.data.decode("utf-8"))
        self.assertFalse(payload["store"])
        self.assertNotIn(FAKE_KEY, request.data.decode("utf-8"))

    def test_anthropic_uses_messages_and_required_version_header(self) -> None:
        opener = _FakeOpener(_anthropic("Claude answer"))
        transport = ThirdPartyTransport("anthropic", self.material(), _opener=opener)
        self.assertEqual(
            transport.generate("claude-sonnet-4-5", "prompt", max_output_tokens=128),
            "Claude answer",
        )
        request, _ = opener.requests[0]
        self.assertEqual(request.full_url, "https://api.anthropic.com/v1/messages")
        self.assertEqual(request.get_header("X-api-key"), FAKE_KEY)
        self.assertEqual(request.get_header("Anthropic-version"), "2023-06-01")

    def test_gemini_uses_generate_content_and_key_header(self) -> None:
        opener = _FakeOpener(_gemini("Gemini answer"))
        transport = ThirdPartyTransport("gemini", self.material(), _opener=opener)
        self.assertEqual(
            transport.generate("gemini-3.5-flash", "prompt", max_output_tokens=128),
            "Gemini answer",
        )
        request, _ = opener.requests[0]
        self.assertEqual(
            request.full_url,
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent",
        )
        self.assertEqual(request.get_header("X-goog-api-key"), FAKE_KEY)
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["generationConfig"]["maxOutputTokens"], 128)

    def test_groq_responses_does_not_send_unsupported_store_field(self) -> None:
        opener = _FakeOpener(_responses("Groq open-weight answer"))
        transport = ThirdPartyTransport("groq", self.material(), _opener=opener)
        self.assertEqual(
            transport.generate("openai/gpt-oss-20b", "prompt", max_output_tokens=128),
            "Groq open-weight answer",
        )
        request, _ = opener.requests[0]
        self.assertEqual(request.full_url, "https://api.groq.com/openai/v1/responses")
        payload = json.loads(request.data.decode("utf-8"))
        self.assertNotIn("store", payload)

    def test_together_uses_chat_completions_not_responses(self) -> None:
        opener = _FakeOpener(_chat("Together open-weight answer"))
        transport = ThirdPartyTransport("together", self.material(), _opener=opener)
        self.assertEqual(
            transport.generate("openai/gpt-oss-20b", "prompt", max_output_tokens=128),
            "Together open-weight answer",
        )
        request, _ = opener.requests[0]
        self.assertEqual(request.full_url, "https://api.together.ai/v1/chat/completions")
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["messages"], [{"role": "user", "content": "prompt"}])
        self.assertNotIn("store", payload)

    def test_model_discovery_normalizes_openai_and_gemini_shapes(self) -> None:
        openai_models = ThirdPartyTransport(
            "openai",
            self.material(),
            _opener=_FakeOpener(
                {
                    "object": "list",
                    "data": [
                        {"id": "gpt-5.5", "owned_by": "openai", "created": 123},
                        {"id": "gpt-5-mini", "owned_by": "openai", "created": 122},
                    ],
                }
            ),
        ).list_language_models()
        self.assertEqual([item["id"] for item in openai_models], ["gpt-5-mini", "gpt-5.5"])

        gemini_models = ThirdPartyTransport(
            "gemini",
            self.material(),
            _opener=_FakeOpener(
                {
                    "models": [
                        {
                            "name": "models/gemini-3.5-flash",
                            "displayName": "Gemini 3.5 Flash",
                            "version": "001",
                            "supportedGenerationMethods": ["generateContent"],
                            "inputTokenLimit": 1000,
                            "outputTokenLimit": 100,
                        },
                        {
                            "name": "models/embedding-only",
                            "supportedGenerationMethods": ["embedContent"],
                        },
                    ]
                }
            ),
        ).list_language_models()
        self.assertEqual([item["id"] for item in gemini_models], ["gemini-3.5-flash"])

    def test_reflected_credentials_are_rejected_before_projection(self) -> None:
        for adapter_id, payload, model in (
            ("openai", _responses(f"leak {FAKE_KEY}"), "gpt-5.5"),
            ("anthropic", _anthropic(f"leak {FAKE_KEY}"), "claude-sonnet-4-5"),
            ("gemini", _gemini(f"leak {FAKE_KEY}"), "gemini-3.5-flash"),
            ("groq", _responses(f"leak {FAKE_KEY}"), "openai/gpt-oss-20b"),
            ("together", _chat(f"leak {FAKE_KEY}"), "openai/gpt-oss-20b"),
        ):
            with self.subTest(adapter_id=adapter_id):
                transport = ThirdPartyTransport(
                    adapter_id,
                    self.material(),
                    _opener=_FakeOpener(payload),
                )
                with self.assertRaises(AdapterProtocolError):
                    transport.generate(model, "prompt", max_output_tokens=64)

    def test_ballots_use_shared_closed_parser(self) -> None:
        context = PhaseContext(
            "session",
            Phase.WHITE,
            "question",
            "object:" + "a" * 64,
            {},
            mode_id="analytical",
            mode_instruction="Separate evidence from inference.",
            geometry_region_id="observatory",
        )
        transport = mock.Mock(spec=ThirdPartyTransport)
        transport.adapter_id = "openai"
        transport.spec = provider_spec("openai")
        transport.generate.return_value = '{"choice":"TEST_FURTHER","rationale":"Needs replication."}'
        actor = ThirdPartyActor(
            CouncilMember("OpenAI", "gpt-5.5", adapter_id="openai"),
            "gpt-5.5",
            transport,
        )
        choice, rationale = actor.ballot(context)
        self.assertEqual(choice, Ballot.TEST_FURTHER)
        self.assertEqual(rationale, "Needs replication.")
        self.assertFalse(actor.replayable)


class ProviderAPITests(unittest.TestCase):
    def broker(self, root: Path) -> AuthBroker:
        store = FileSecretStore(root)
        environment = {
            "OPENAI_API_KEY": FAKE_KEY,
            "ANTHROPIC_API_KEY": FAKE_KEY,
            "GEMINI_API_KEY": FAKE_KEY,
            "GROQ_API_KEY": FAKE_KEY,
            "TOGETHER_API_KEY": FAKE_KEY,
        }
        broker = AuthBroker(
            root,
            secret_stores={store.backend_id: store},
            environment=environment,
        )
        for adapter_id, env_name in (
            ("openai", "OPENAI_API_KEY"),
            ("anthropic", "ANTHROPIC_API_KEY"),
            ("gemini", "GEMINI_API_KEY"),
            ("groq", "GROQ_API_KEY"),
            ("together", "TOGETHER_API_KEY"),
        ):
            broker.add_environment(adapter_id, "default", env_name)
        return broker

    def test_system_health_advertises_all_remote_backends(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            api = NexusAPI(base / "world", auth_broker=self.broker(base / "auth"))
            health = api.handle({"operation": "system.health"})
        self.assertEqual(health["status"], "ok")
        for adapter_id in THIRD_PARTY_PROVIDER_IDS:
            self.assertIn(adapter_id, health["actor_backends_available"])
            self.assertIn(f"{adapter_id}_https", health["adapters"])

    def test_models_list_and_actor_chat_route_through_profile_reference(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            api = NexusAPI(base / "world", auth_broker=self.broker(base / "auth"))
            with mock.patch.object(
                ThirdPartyTransport,
                "list_language_models",
                return_value=[{"id": "gpt-5.5"}],
            ):
                models = api.handle({"operation": "models.list", "adapter_id": "openai"})
            self.assertEqual(models["status"], "ok")
            self.assertEqual(models["models"], [{"id": "gpt-5.5"}])

            with mock.patch.object(ThirdPartyTransport, "generate", return_value="Remote answer"):
                chat = api.handle(
                    {
                        "operation": "actor.chat",
                        "member": {
                            "member_id": "OpenAI",
                            "model_id": "gpt-5.5",
                            "adapter_id": "openai",
                            "auth_profile": "default",
                        },
                        "message": "hello",
                    }
                )
            self.assertEqual(chat["status"], "ok")
            self.assertEqual(chat["response"], "Remote answer")

    def test_arbitrary_endpoint_override_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            api = NexusAPI(base / "world", auth_broker=self.broker(base / "auth"))
            result = api.handle(
                {
                    "operation": "actor.chat",
                    "member": {
                        "member_id": "OpenAI",
                        "model_id": "gpt-5.5",
                        "adapter_id": "openai",
                        "auth_profile": "default",
                        "endpoint": "https://evil.example/v1",
                    },
                    "message": "hello",
                }
            )
        self.assertEqual(result["status"], "error")
        self.assertIn("unsupported fields", result["error"]["message"])

    def test_mixed_remote_provider_cap_is_enforced_before_credentials(self) -> None:
        api = NexusAPI()
        members = [
            {"member_id": f"M{index}", "model_id": "fixture", "adapter_id": adapter_id}
            for index, adapter_id in enumerate(
                ["openai", "anthropic", "gemini", "groq", "together"]
            )
        ]
        result = api.handle(
            {
                "operation": "council.run",
                "question": "test",
                "members": members,
            }
        )
        self.assertEqual(result["status"], "error")
        self.assertIn("at most 4 remote provider seats", result["error"]["message"])


if __name__ == "__main__":
    unittest.main()
