from __future__ import annotations

from pathlib import Path
import tomllib
import unittest

from nexus_runtime import NexusAPI as PackageNexusAPI, PROTOCOL_VERSION, RUNTIME_VERSION
from nexus_runtime.api import NexusAPI as CanonicalNexusAPI
from nexus_runtime.adapters.local_ai import LOCAL_AI_ADAPTER_IDS, LocalAITransport
from nexus_runtime.adapters.ollama import OllamaTransport
from nexus_runtime.adapters.third_party import THIRD_PARTY_PROVIDER_IDS
from nexus_runtime.adapters.xai import XAITransport
from nexus_runtime.auth.types import SecretMaterial
from nexus_runtime.local_roles import LocalRoleBackendConfig
from nexus_runtime.provider_api import ProviderNexusAPI


ROOT = Path(__file__).resolve().parents[1]


class ReleaseWiringTests(unittest.TestCase):
    def test_all_public_api_imports_resolve_to_provider_aware_runtime(self) -> None:
        self.assertIs(PackageNexusAPI, ProviderNexusAPI)
        self.assertIs(CanonicalNexusAPI, ProviderNexusAPI)

    def test_health_and_operations_expose_complete_architecture(self) -> None:
        api = PackageNexusAPI()
        health = api.handle({"operation": "system.health"})
        self.assertEqual(health["status"], "ok")
        self.assertEqual(health["protocol"], PROTOCOL_VERSION)
        self.assertEqual(health["runtime_version"], RUNTIME_VERSION)
        self.assertEqual(
            set(health["actor_backends_available"]),
            {
                "mock",
                "ollama",
                *LOCAL_AI_ADAPTER_IDS,
                "xai",
                *THIRD_PARTY_PROVIDER_IDS,
            },
        )
        self.assertTrue(health["remote_provider_auth"])
        self.assertTrue(health["local_roles"]["local_only"])
        self.assertFalse(health["local_roles"]["persistent"])

        operations = set(api.handle({"operation": "system.operations"})["operations"])
        self.assertTrue(
            {
                "models.list",
                "actor.chat",
                "council.run",
                "local.roles.status",
                "local.roles.configure",
                "local.roles.clear",
            }.issubset(operations)
        )

    def test_release_version_triplet_is_aligned(self) -> None:
        pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        cargo = tomllib.loads((ROOT / "tui" / "Cargo.toml").read_text(encoding="utf-8"))
        cargo_lock = tomllib.loads((ROOT / "tui" / "Cargo.lock").read_text(encoding="utf-8"))
        api_reference = (ROOT / "docs" / "API.md").read_text(encoding="utf-8")

        self.assertEqual(PROTOCOL_VERSION, "nexus/0.14")
        self.assertEqual(RUNTIME_VERSION, "2.0.0-alpha10.3")
        self.assertEqual(pyproject["project"]["version"], "2.0.0a10.post3")
        self.assertEqual(cargo["package"]["version"], RUNTIME_VERSION)

        tui_lock_packages = [
            package
            for package in cargo_lock["package"]
            if package.get("name") == cargo["package"]["name"]
        ]
        self.assertEqual(len(tui_lock_packages), 1)
        self.assertEqual(tui_lock_packages[0]["version"], RUNTIME_VERSION)

        self.assertIn(
            f"Runtime identifier:\n\n```text\n{RUNTIME_VERSION}\n```",
            api_reference,
        )
        self.assertIn(f'"runtime_version": "{RUNTIME_VERSION}"', api_reference)
        self.assertNotIn("2.0.0-alpha10.2", api_reference)

    def test_pathological_timeouts_fail_closed_before_network(self) -> None:
        huge = 10**400
        with self.assertRaises(ValueError):
            OllamaTransport(timeout_seconds=huge)
        with self.assertRaises(ValueError):
            LocalAITransport("openai_local", timeout_seconds=huge)
        with self.assertRaises(ValueError):
            XAITransport(SecretMaterial("fixture-xai-token"), timeout_seconds=huge)
        with self.assertRaises(ValueError):
            LocalRoleBackendConfig.from_request(
                "failsafe_relief",
                {
                    "adapter_id": "openai_local",
                    "model": "fixture-model",
                    "timeout_seconds": huge,
                },
            )

    def test_public_jsonl_timeout_paths_remain_structured_errors(self) -> None:
        huge = 10**400
        api = PackageNexusAPI()

        ollama = api.handle(
            {
                "operation": "actor.chat",
                "member": {
                    "member_id": "OllamaHugeTimeout",
                    "model_id": "fixture-model",
                    "adapter_id": "ollama",
                    "model": "fixture-model",
                    "endpoint": "http://127.0.0.1:11434",
                    "timeout_seconds": huge,
                },
                "message": "do not connect",
            }
        )
        self.assertEqual(ollama["status"], "error")
        self.assertEqual(ollama["error"]["code"], "invalid_request")

        local = api.handle(
            {
                "operation": "actor.chat",
                "member": {
                    "member_id": "LocalHugeTimeout",
                    "model_id": "fixture-model",
                    "adapter_id": "openai_local",
                    "model": "fixture-model",
                    "timeout_seconds": huge,
                },
                "message": "do not connect",
            }
        )
        self.assertEqual(local["status"], "error")
        self.assertEqual(local["error"]["code"], "invalid_request")

        role = api.handle(
            {
                "operation": "local.roles.configure",
                "role_id": "failsafe_relief",
                "backend": {
                    "adapter_id": "openai_local",
                    "model": "fixture-model",
                    "timeout_seconds": huge,
                },
            }
        )
        self.assertEqual(role["status"], "error")
        self.assertEqual(role["error"]["code"], "invalid_request")


if __name__ == "__main__":
    unittest.main()
