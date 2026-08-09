from __future__ import annotations

import json
from types import SimpleNamespace
import unittest
from urllib.parse import urlsplit

from nexus_runtime import NexusAPI
from nexus_runtime.adapters.base import AdapterError
from nexus_runtime.adapters.local_ai import (
    LocalAIActor,
    LocalAITransport,
    LocalMCPPlugin,
    validate_local_ai_endpoint,
)
from nexus_runtime.auth.types import SecretMaterial
from nexus_runtime.citizenship import DeterministicCivicProxy
from nexus_runtime.failsafe import FailsafeReplacementActor, RELIEF_MODEL_ID
from nexus_runtime.local_roles import LocalRoleActor, LocalRoleBackendConfig, LocalRoleRegistry
from nexus_runtime.types import Ballot, CouncilMember, Phase, PhaseContext


class _Response:
    def __init__(self, value: dict[str, object]) -> None:
        self._body = json.dumps(value).encode("utf-8")

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    def read(self, amount: int = -1) -> bytes:
        return self._body if amount < 0 else self._body[:amount]


class _RecordingOpener:
    def __init__(self, value: dict[str, object]) -> None:
        self.value = value
        self.requests: list[object] = []
        self.timeouts: list[float] = []

    def open(self, request: object, timeout: float) -> _Response:
        self.requests.append(request)
        self.timeouts.append(timeout)
        return _Response(self.value)


class _DeterministicActor:
    def __init__(self, member_id: str = "A", model_id: str = "deterministic-a") -> None:
        self.member = CouncilMember(member_id, model_id, adapter_id="fixture")

    @property
    def replayable(self) -> bool:
        return True

    def identity_metadata(self) -> dict[str, object]:
        return {"actor_kind": "fixture_deterministic"}

    def respond(self, context: PhaseContext) -> str:
        return "deterministic fallback"

    def direct_message(
        self,
        message: str,
        *,
        mode_id: str,
        mode_instruction: str,
        geometry_region_id: str,
        evidence_context: str = "",
    ) -> str:
        return "deterministic direct fallback"

    def ballot(self, context: PhaseContext) -> tuple[Ballot, str]:
        return Ballot.TEST_FURTHER, "deterministic ballot"


class LocalEndpointTests(unittest.TestCase):
    def test_only_loopback_origins_are_admitted(self) -> None:
        for value in (
            "http://127.0.0.1:1234",
            "http://localhost:3001",
            "http://[::1]:8000",
            "https://127.0.0.1:8443",
        ):
            with self.subTest(value=value):
                self.assertEqual(validate_local_ai_endpoint(value), value.rstrip("/"))

        for value in (
            "http://0.0.0.0:1234",
            "http://192.168.1.20:1234",
            "https://example.com",
            "http://local-ai.internal:1234",
            "http://127.0.0.1:1234/v1",
            "http://user:pass@127.0.0.1:1234",
            "http://127.0.0.1:1234/?token=x",
        ):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    validate_local_ai_endpoint(value)

    def test_lmstudio_request_uses_only_preconfigured_plugin_ids(self) -> None:
        opener = _RecordingOpener(
            {
                "output": [
                    {"type": "tool_call", "tool": "read_local_notes"},
                    {"type": "message", "content": "local answer"},
                ]
            }
        )
        transport = LocalAITransport(
            "lmstudio_local",
            endpoint="http://127.0.0.1:1234",
            credential=SecretMaterial("fixture-local-token"),
            _opener=opener,
        )
        text = transport.generate(
            "hello",
            model="local/model",
            mcp_plugins=(LocalMCPPlugin("mcp/notes", ("read_local_notes",)),),
        )
        self.assertEqual(text, "local answer")
        request = opener.requests[0]
        self.assertEqual(urlsplit(request.full_url).path, "/api/v1/chat")  # type: ignore[attr-defined]
        self.assertEqual(request.get_header("Authorization"), "Bearer fixture-local-token")  # type: ignore[attr-defined]
        payload = json.loads(request.data.decode("utf-8"))  # type: ignore[attr-defined]
        self.assertFalse(payload["store"])
        self.assertEqual(
            payload["integrations"],
            [{"type": "plugin", "id": "mcp/notes", "allowed_tools": ["read_local_notes"]}],
        )
        self.assertNotIn("server_url", json.dumps(payload))
        self.assertNotIn("headers", json.dumps(payload))

    def test_anythingllm_uses_loopback_workspace_chat(self) -> None:
        opener = _RecordingOpener({"textResponse": "workspace answer", "error": None})
        transport = LocalAITransport(
            "anythingllm_local",
            endpoint="http://127.0.0.1:3001",
            credential=SecretMaterial("fixture-anything-token"),
            _opener=opener,
        )
        text = transport.generate(
            "hello",
            workspace="nexus-local",
            session_key="session-a",
        )
        self.assertEqual(text, "workspace answer")
        request = opener.requests[0]
        self.assertEqual(
            urlsplit(request.full_url).path,  # type: ignore[attr-defined]
            "/api/v1/workspace/nexus-local/chat",
        )
        payload = json.loads(request.data.decode("utf-8"))  # type: ignore[attr-defined]
        self.assertEqual(payload["mode"], "chat")
        self.assertEqual(payload["sessionId"], "session-a")


class MCPConfigurationTests(unittest.TestCase):
    def test_mcp_configuration_rejects_ephemeral_urls_headers_and_commands(self) -> None:
        base = {
            "adapter_id": "lmstudio_local",
            "model": "local/model",
            "credential_env": "LM_STUDIO_TOKEN",
        }
        for forbidden in (
            {"id": "mcp/notes", "server_url": "https://example.com/mcp"},
            {"id": "mcp/notes", "headers": {"Authorization": "secret"}},
            {"id": "mcp/notes", "command": "python"},
        ):
            with self.subTest(forbidden=forbidden):
                with self.assertRaisesRegex(ValueError, "only id and allowed_tools"):
                    LocalRoleBackendConfig.from_request(
                        "failsafe_relief",
                        {**base, "mcp_plugins": [forbidden]},
                    )

    def test_lmstudio_mcp_requires_environment_backed_api_token(self) -> None:
        with self.assertRaisesRegex(ValueError, "require credential_env"):
            LocalRoleBackendConfig.from_request(
                "civic_proxy",
                {
                    "adapter_id": "lmstudio_local",
                    "model": "local/model",
                    "mcp_plugins": ["mcp/notes"],
                },
            )

        config = LocalRoleBackendConfig.from_request(
            "civic_proxy",
            {
                "adapter_id": "lmstudio_local",
                "model": "local/model",
                "credential_env": "LM_STUDIO_TOKEN",
                "mcp_plugins": [
                    {"id": "mcp/notes", "allowed_tools": ["read_notes"]}
                ],
            },
        )
        public = config.public_dict()
        self.assertEqual(public["credential_env"], "LM_STUDIO_TOKEN")
        self.assertFalse(public["ephemeral_mcp_urls_allowed"])
        self.assertFalse(public["downstream_mcp_locality_verified"])
        self.assertNotIn("fixture-local-token", json.dumps(public))

    def test_local_role_registry_never_accepts_raw_secret_fields(self) -> None:
        registry = LocalRoleRegistry({"LM_STUDIO_TOKEN": "fixture-local-token"})
        with self.assertRaisesRegex(ValueError, "unsupported fields"):
            registry.configure(
                "failsafe_relief",
                {
                    "adapter_id": "lmstudio_local",
                    "model": "local/model",
                    "token": "fixture-local-token",
                },
            )
        configured = registry.configure(
            "failsafe_relief",
            {
                "adapter_id": "lmstudio_local",
                "model": "local/model",
                "credential_env": "LM_STUDIO_TOKEN",
            },
        )
        self.assertNotIn("fixture-local-token", json.dumps(configured, sort_keys=True))


class RoleBoundaryTests(unittest.TestCase):
    @staticmethod
    def context() -> PhaseContext:
        return PhaseContext(
            session_id="session-local-role",
            phase=Phase.BLUE,
            question="What should this seat do?",
            evidence_snapshot_ref="evidence:fixture",
            completed_phases={},
        )

    def test_local_role_falls_back_but_never_changes_wrapped_ballot(self) -> None:
        class FailingTransport:
            adapter_id = "lmstudio_local"

            @staticmethod
            def generate(*args: object, **kwargs: object) -> str:
                raise AdapterError("offline")

        wrapped = _DeterministicActor()
        config = LocalRoleBackendConfig.from_request(
            "failsafe_relief",
            {"adapter_id": "lmstudio_local", "model": "local/model"},
        )
        actor = LocalRoleActor(
            "failsafe_relief",
            wrapped,
            config,
            FailingTransport(),  # type: ignore[arg-type]
        )
        self.assertEqual(actor.respond(self.context()), "deterministic fallback")
        self.assertEqual(actor.direct_message(
            "hello",
            mode_id="analytical",
            mode_instruction="reason carefully",
            geometry_region_id="observatory",
        ), "deterministic direct fallback")
        self.assertEqual(actor.ballot(self.context()), wrapped.ballot(self.context()))
        self.assertEqual(actor.fallback_count, 2)

    def test_failsafe_relief_keeps_test_further_under_local_backend(self) -> None:
        original = _DeterministicActor("A", "bad-model")
        relief = FailsafeReplacementActor.for_actor(
            original,
            model_id=RELIEF_MODEL_ID,
            shadow_state_ref="object:" + "1" * 64,
            containment_status="shadow_realm",
        )
        registry = LocalRoleRegistry()
        registry.configure(
            "failsafe_relief",
            {"adapter_id": "lmstudio_local", "model": "local/model"},
        )
        wrapped = registry.wrap("failsafe_relief", relief)
        self.assertEqual(wrapped.member.member_id, "A")
        self.assertEqual(wrapped.member.model_id, RELIEF_MODEL_ID)
        self.assertEqual(wrapped.ballot(self.context())[0], Ballot.TEST_FURTHER)

    def test_civic_proxy_keeps_recorded_standing_ballot_under_local_backend(self) -> None:
        original = _DeterministicActor("CitizenA", "citizen-model")
        proxy = DeterministicCivicProxy.for_actor(
            original,
            citizen_state_ref="object:" + "2" * 64,
            standing_ballot=Ballot.ACCEPT_WITH_CHANGES,
        )
        registry = LocalRoleRegistry()
        registry.configure(
            "civic_proxy",
            {"adapter_id": "openai_local", "model": "local/model"},
        )
        wrapped = registry.wrap("civic_proxy", proxy)
        self.assertEqual(wrapped.member.member_id, "CitizenA")
        self.assertEqual(wrapped.member.model_id, proxy.member.model_id)
        self.assertEqual(wrapped.ballot(self.context())[0], Ballot.ACCEPT_WITH_CHANGES)

    def test_ordinary_local_actor_disables_mcp_during_sealed_ballot(self) -> None:
        calls: list[tuple[LocalMCPPlugin, ...]] = []

        class BallotTransport:
            adapter_id = "lmstudio_local"

            @staticmethod
            def generate(prompt: str, **kwargs: object) -> str:
                calls.append(kwargs.get("mcp_plugins", ()))  # type: ignore[arg-type]
                return json.dumps({"choice": "TEST_FURTHER", "rationale": "local ballot"})

        member = CouncilMember("A", "local/model", adapter_id="lmstudio_local")
        actor = LocalAIActor(
            member=member,
            transport=BallotTransport(),  # type: ignore[arg-type]
            model="local/model",
            mcp_plugins=(LocalMCPPlugin("mcp/notes"),),
        )
        choice, rationale = actor.ballot(self.context())
        self.assertEqual(choice, Ballot.TEST_FURTHER)
        self.assertEqual(rationale, "local ballot")
        self.assertEqual(calls, [()])


class LocalRoleAPITests(unittest.TestCase):
    def test_control_surface_is_ephemeral_local_only_and_secret_free(self) -> None:
        api = NexusAPI()
        operations = api.handle({"operation": "system.operations"})
        for name in ("local.roles.status", "local.roles.configure", "local.roles.clear"):
            self.assertIn(name, operations["operations"])

        configured = api.handle(
            {
                "operation": "local.roles.configure",
                "role_id": "failsafe_relief",
                "backend": {
                    "adapter_id": "lmstudio_local",
                    "model": "local/model",
                },
            }
        )
        self.assertEqual(configured["status"], "ok")
        self.assertFalse(configured["persisted"])
        self.assertFalse(configured["authoritative_world_state"])

        status = api.handle({"operation": "local.roles.status"})
        self.assertTrue(status["local_only"])
        self.assertFalse(status["persistent"])
        self.assertEqual(status["invariants"]["extra_votes_created"], 0)
        self.assertFalse(status["invariants"]["remote_mcp_urls_from_requests"])

        health = api.handle({"operation": "system.health"})
        self.assertIn("lmstudio_local", health["actor_backends_available"])
        self.assertIn("anythingllm_local", health["actor_backends_available"])
        self.assertIn("openai_local", health["actor_backends_available"])
        self.assertTrue(health["local_roles"]["local_only"])

        cleared = api.handle(
            {"operation": "local.roles.clear", "role_id": "failsafe_relief"}
        )
        self.assertTrue(cleared["removed"])

    def test_control_surface_rejects_non_loopback_and_ephemeral_mcp(self) -> None:
        api = NexusAPI()
        remote = api.handle(
            {
                "operation": "local.roles.configure",
                "role_id": "civic_proxy",
                "backend": {
                    "adapter_id": "lmstudio_local",
                    "endpoint": "http://192.168.1.10:1234",
                    "model": "local/model",
                },
            }
        )
        self.assertEqual(remote["status"], "error")
        self.assertIn("loopback", remote["error"]["message"])

        ephemeral = api.handle(
            {
                "operation": "local.roles.configure",
                "role_id": "civic_proxy",
                "backend": {
                    "adapter_id": "lmstudio_local",
                    "model": "local/model",
                    "credential_env": "LM_STUDIO_TOKEN",
                    "mcp_plugins": [
                        {"id": "mcp/notes", "server_url": "https://example.com/mcp"}
                    ],
                },
            }
        )
        self.assertEqual(ephemeral["status"], "error")
        self.assertIn("only id and allowed_tools", ephemeral["error"]["message"])


if __name__ == "__main__":
    unittest.main()
