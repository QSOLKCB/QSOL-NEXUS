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
from nexus_runtime.replay import OPERATION_REPLAY_POLICY_ID


ROOT = Path(__file__).resolve().parents[1]


class ReleaseWiringTests(unittest.TestCase):
    def test_all_public_api_imports_resolve_to_current_persistent_world_runtime(self) -> None:
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
        self.assertEqual(
            health["operation_replay"]["policy"]["schema"],
            OPERATION_REPLAY_POLICY_ID,
        )
        self.assertEqual(
            health["operation_replay"]["policy"]["authority_effect"],
            "none",
        )

        operations = set(api.handle({"operation": "system.operations"})["operations"])
        self.assertTrue(
            {
                "models.list",
                "actor.chat",
                "council.run",
                "receipt.replay",
                "local.roles.status",
                "local.roles.configure",
                "local.roles.clear",
                "world.persistence.policy",
                "world.relation.create",
                "world.hypothesis.create",
                "world.experiment.create",
                "world.minority.search",
                "world.mode.history",
                "world.export",
                "world.import",
            }.issubset(operations)
        )

    @staticmethod
    def _mock_members(*, first_profile: str = "balanced") -> list[dict[str, str]]:
        return [
            {"member_id": "A", "model_id": "mock-a", "adapter_id": "mock", "profile": first_profile},
            {"member_id": "B", "model_id": "mock-b", "adapter_id": "mock", "profile": "skeptical"},
            {"member_id": "C", "model_id": "mock-c", "adapter_id": "mock", "profile": "supportive"},
        ]

    def test_generalized_replay_reconstructs_mock_council_without_source_mutation(self) -> None:
        api = PackageNexusAPI()
        evidence = api.handle(
            {
                "operation": "world.create",
                "object_type": "note",
                "payload": {"content": "bounded replay evidence"},
                "provenance": {"actor": "fixture"},
            }
        )
        evidence_ref = evidence["object"]["object_id"]
        run = api.handle(
            {
                "operation": "council.run",
                "question": "Can this deterministic stored Council be replayed?",
                "members": self._mock_members(),
                "evidence_refs": [evidence_ref],
                "evidence_state": "UNTESTED",
                "mode": "analytical",
            }
        )
        self.assertEqual(run["status"], "ok")
        self.assertTrue(run["execution_replayable"])
        before = set(api.world._objects)

        replay = api.handle(
            {
                "operation": "receipt.replay",
                "receipt_ref": run["receipt_ref"],
            }
        )
        self.assertEqual(replay["status"], "verified")
        self.assertEqual(replay["source_receipt_ref"], run["receipt_ref"])
        self.assertEqual(replay["source_result_ref"], run["session_ref"])
        self.assertEqual(replay["replayed_receipt_ref"], run["receipt_ref"])
        self.assertEqual(replay["replayed_result_ref"], run["session_ref"])
        self.assertTrue(replay["result_identity_match"])
        self.assertTrue(replay["receipt_identity_match"])
        self.assertTrue(replay["isolated_replay"])
        self.assertEqual(replay["source_world_write_effect"], "none")
        self.assertEqual(replay["authority_effect"], "none")
        self.assertEqual(replay["evidence_effect"], "none")
        self.assertEqual(set(api.world._objects), before)

    def test_generalized_replay_rejects_missing_presence_direct_input(self) -> None:
        api = PackageNexusAPI()
        run = api.handle(
            {
                "operation": "council.run",
                "question": "Presence must remain available for replay.",
                "members": self._mock_members(),
            }
        )
        self.assertEqual(run["status"], "ok")
        presence_ref = run["world_presence_ref"]
        api.world._objects.pop(presence_ref)

        verified = api.handle({"operation": "receipt.verify", "receipt_ref": run["receipt_ref"]})
        self.assertEqual(verified["status"], "failed")
        self.assertIn(presence_ref, verified["missing_refs"])

        replay = api.handle({"operation": "receipt.replay", "receipt_ref": run["receipt_ref"]})
        self.assertEqual(replay["status"], "error")
        self.assertEqual(replay["error"]["code"], "replay_context_not_reconstructible")
        self.assertIn("world presence", replay["error"]["message"].casefold())

    def test_generalized_replay_accepts_empty_mock_profile_admitted_by_council(self) -> None:
        api = PackageNexusAPI()
        run = api.handle(
            {
                "operation": "council.run",
                "question": "An empty mock profile is still an admitted exact string.",
                "members": self._mock_members(first_profile=""),
            }
        )
        self.assertEqual(run["status"], "ok")
        self.assertTrue(run["execution_replayable"])
        replay = api.handle({"operation": "receipt.replay", "receipt_ref": run["receipt_ref"]})
        self.assertEqual(replay["status"], "verified")
        self.assertEqual(replay["replayed_result_ref"], run["session_ref"])
        self.assertEqual(replay["replayed_receipt_ref"], run["receipt_ref"])

    def test_manual_2_1_1_dispatch_is_pinned_to_certified_pr61_merge(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "nexus-2.1.1-release-candidate.yml").read_text(
            encoding="utf-8"
        )
        certified = "a5fea299fbe682c9672dc577d2e683cebdb9f8f4"
        self.assertIn(f"NEXUS_211_CERTIFIED_MERGE: {certified}", workflow)
        self.assertIn(
            f"ref: ${{{{ github.event_name == 'workflow_dispatch' && '{certified}' || github.sha }}}}",
            workflow,
        )
        self.assertIn("Checkout exact candidate subject", workflow)
        self.assertIn("Confirm exact candidate subject", workflow)
        self.assertIn('test "$(git rev-parse HEAD)" = "$NEXUS_211_EXPECT"', workflow)
        self.assertIn('test "$NEXUS_211_EXPECT" = "$NEXUS_211_CERTIFIED_MERGE"', workflow)
        self.assertIn('--expect-commit "$NEXUS_211_EXPECT"', workflow)
        self.assertNotIn('--expect-commit "$GITHUB_SHA"', workflow)

    def test_generalized_replay_fails_closed_for_non_replayable_and_unknown_receipts(self) -> None:
        api = PackageNexusAPI()
        non_replayable = api.world.create_object(
            "receipt",
            {
                "operation": "council.run",
                "input_refs": [],
                "result_ref": "object:" + "0" * 64,
                "replayable": False,
                "protocol": PROTOCOL_VERSION,
            },
            {"actor": "nexus"},
        )
        denied = api.handle(
            {"operation": "receipt.replay", "receipt_ref": non_replayable.object_id}
        )
        self.assertEqual(denied["status"], "error")
        self.assertEqual(denied["error"]["code"], "replay_not_replayable")

        unsupported = api.world.create_object(
            "receipt",
            {
                "operation": "world.create",
                "input_refs": [],
                "result_ref": "object:" + "1" * 64,
                "replayable": True,
                "protocol": PROTOCOL_VERSION,
            },
            {"actor": "nexus"},
        )
        rejected = api.handle(
            {"operation": "receipt.replay", "receipt_ref": unsupported.object_id}
        )
        self.assertEqual(rejected["status"], "error")
        self.assertEqual(rejected["error"]["code"], "replay_unsupported_operation")

    def test_generalized_replay_does_not_reconstruct_discarded_secret_question_source(self) -> None:
        api = PackageNexusAPI()
        secret = "sk-" + "A" * 32
        run = api.handle(
            {
                "operation": "council.run",
                "question": f"Do not retain this raw secret {secret}",
                "members": [
                    {"member_id": "A", "model_id": "mock-a", "adapter_id": "mock"},
                    {"member_id": "B", "model_id": "mock-b", "adapter_id": "mock"},
                    {"member_id": "C", "model_id": "mock-c", "adapter_id": "mock"},
                ],
            }
        )
        self.assertEqual(run["status"], "ok")
        self.assertTrue(run["secret_scrub"]["changed"])
        replay = api.handle(
            {"operation": "receipt.replay", "receipt_ref": run["receipt_ref"]}
        )
        self.assertEqual(replay["status"], "error")
        self.assertEqual(
            replay["error"]["code"],
            "replay_context_not_reconstructible",
        )

    def test_release_version_triplet_and_protocol_are_aligned(self) -> None:
        pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        cargo = tomllib.loads((ROOT / "tui" / "Cargo.toml").read_text(encoding="utf-8"))
        cargo_lock = tomllib.loads((ROOT / "tui" / "Cargo.lock").read_text(encoding="utf-8"))
        api_reference = (ROOT / "docs" / "API.md").read_text(encoding="utf-8")

        self.assertEqual(PROTOCOL_VERSION, "nexus/0.15")
        self.assertEqual(RUNTIME_VERSION, "2.1.1")
        self.assertEqual(pyproject["project"]["version"], "2.1.1")
        self.assertEqual(cargo["package"]["version"], RUNTIME_VERSION)

        tui_lock_packages = [
            package
            for package in cargo_lock["package"]
            if package.get("name") == cargo["package"]["name"]
        ]
        self.assertEqual(len(tui_lock_packages), 1)
        self.assertEqual(tui_lock_packages[0]["version"], RUNTIME_VERSION)

        self.assertIn(
            f"Protocol identifier:\n\n```text\n{PROTOCOL_VERSION}\n```",
            api_reference,
        )
        self.assertIn(
            f"Runtime identifier:\n\n```text\n{RUNTIME_VERSION}\n```",
            api_reference,
        )
        self.assertIn(f'"protocol": "{PROTOCOL_VERSION}"', api_reference)
        self.assertIn(f'"runtime_version": "{RUNTIME_VERSION}"', api_reference)
        self.assertNotIn("2.0.0-alpha", api_reference)

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
