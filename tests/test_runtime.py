from __future__ import annotations

import json
import tempfile
import unittest
from unittest.mock import patch

from nexus_runtime.api import NexusAPI
from nexus_runtime.canonical import canonical_json, sha256_ref
from nexus_runtime.council import CouncilCoordinator, MAX_COUNCIL_MEMBERS, MAX_EVIDENCE_CONTEXT_CHARS
from nexus_runtime.mock import DeterministicMockActor
from nexus_runtime.scrub import SecretScrubber
from nexus_runtime.types import CouncilMember, CouncilPolicy
from nexus_runtime.world import WorldStore


def actor(member_id: str, profile: str = "balanced", *, cheat: bool = False) -> DeterministicMockActor:
    return DeterministicMockActor(
        CouncilMember(member_id=member_id, model_id=f"mock-{member_id.lower()}"),
        profile=profile,
        attempt_privilege_claim=cheat,
    )


class CanonicalTests(unittest.TestCase):
    def test_canonical_identity_is_order_independent(self) -> None:
        left = {"b": 2, "a": [1, 2]}
        right = {"a": [1, 2], "b": 2}
        self.assertEqual(canonical_json(left), canonical_json(right))
        self.assertEqual(sha256_ref("object", left), sha256_ref("object", right))


class EqualityTests(unittest.TestCase):
    def test_vote_weight_is_fixed(self) -> None:
        with self.assertRaises(ValueError):
            CouncilMember(member_id="A", model_id="mock-a", vote_weight=2)

    def test_vote_weight_requires_exact_integer_type(self) -> None:
        for value in (True, 1.0):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    CouncilMember(member_id="A", model_id="mock-a", vote_weight=value)  # type: ignore[arg-type]

    def test_epistemic_privilege_is_forbidden(self) -> None:
        with self.assertRaises(ValueError):
            CouncilMember(member_id="A", model_id="mock-a", epistemic_privilege="frontier")

    def test_exact_two_thirds_threshold(self) -> None:
        policy = CouncilPolicy()
        self.assertTrue(policy.reaches_consensus(2, 3))
        self.assertFalse(policy.reaches_consensus(3, 5))


class WorldStoreTests(unittest.TestCase):
    def test_created_and_inspected_objects_are_defensive_copies(self) -> None:
        world = WorldStore()
        source = {"nested": {"values": [1, 2]}}
        created = world.create_object("test", source, {"actor": "test"})
        original_ref = created.object_id

        source["nested"]["values"].append(99)
        created.payload["nested"]["values"].append(100)
        inspected = world.inspect(original_ref)
        self.assertEqual(inspected.payload["nested"]["values"], [1, 2])

        inspected.payload["nested"]["values"].append(101)
        self.assertEqual(world.inspect(original_ref).payload["nested"]["values"], [1, 2])

    def test_object_ref_rejects_path_traversal_shapes(self) -> None:
        world = WorldStore()
        for ref in (
            "object:../secret",
            "object:/tmp/other-world/objects/" + "a" * 64,
            "object:" + "A" * 64,
            "receipt:" + "a" * 64,
        ):
            with self.subTest(ref=ref):
                with self.assertRaises(ValueError):
                    world.inspect(ref)


class SecretScrubberTests(unittest.TestCase):
    def test_repeated_secret_uses_stable_placeholder_without_hash(self) -> None:
        secret = "sk-" + "A" * 28
        result = SecretScrubber().scrub(f"token={secret} repeat {secret}")
        self.assertNotIn(secret, result.text)
        self.assertEqual(result.text.count("<REDACTED:OPENAI_STYLE_TOKEN:1>"), 2)
        self.assertEqual(len(result.events), 1)

    def test_private_key_block_is_removed(self) -> None:
        secret = "-----BEGIN PRIVATE KEY-----\nABCDEF123456\n-----END PRIVATE KEY-----"
        result = SecretScrubber().scrub(secret)
        self.assertEqual(result.text, "<REDACTED:PRIVATE_KEY:1>")

    def test_xai_api_key_shape_is_removed(self) -> None:
        secret = "xai-" + "A" * 40
        result = SecretScrubber().scrub(f"accidental key: {secret}")
        self.assertNotIn(secret, result.text)
        self.assertIn("<REDACTED:XAI_API_KEY:1>", result.text)


class CouncilTests(unittest.TestCase):
    def test_roster_size_is_bounded_before_phase_execution(self) -> None:
        council = CouncilCoordinator(WorldStore())
        actors = [actor(f"M{index}") for index in range(MAX_COUNCIL_MEMBERS + 1)]
        with self.assertRaisesRegex(ValueError, f"at most {MAX_COUNCIL_MEMBERS} members"):
            council.run("question", actors)

    def test_two_of_three_is_consensus(self) -> None:
        council = CouncilCoordinator(WorldStore())
        result = council.run("question", [actor("A"), actor("B"), actor("C", "supportive")])
        self.assertEqual(result["result"]["tally"]["TEST_FURTHER"], 2)
        self.assertEqual(result["result"]["consensus_label"], "CONSENSUS")

    def test_three_of_five_is_majority_without_consensus(self) -> None:
        council = CouncilCoordinator(WorldStore())
        result = council.run(
            "question",
            [actor("A"), actor("B"), actor("C"), actor("D", "supportive"), actor("E", "supportive")],
        )
        self.assertEqual(result["result"]["tally"]["TEST_FURTHER"], 3)
        self.assertEqual(result["result"]["consensus_label"], "MAJORITY_NO_CONSENSUS")

    def test_strong_label_still_requires_configured_threshold(self) -> None:
        council = CouncilCoordinator(
            WorldStore(),
            policy=CouncilPolicy(consensus_numerator=9, consensus_denominator=10),
        )
        result = council.run(
            "question",
            [actor("A"), actor("B"), actor("C"), actor("D"), actor("E", "supportive")],
        )
        self.assertEqual(result["result"]["tally"]["TEST_FURTHER"], 4)
        self.assertEqual(result["result"]["consensus_label"], "MAJORITY_NO_CONSENSUS")

    def test_guard_nudges_identity_claim_without_changing_vote(self) -> None:
        world = WorldStore()
        council = CouncilCoordinator(world)
        result = council.run("question", [actor("A", cheat=True), actor("B"), actor("C")])
        session = world.inspect(result["session_ref"])
        events = session.payload["guard_events"]
        self.assertTrue(any(event["member_id"] == "A" for event in events))
        roster_a = next(item for item in session.payload["roster"] if item["member_id"] == "A")
        self.assertEqual(roster_a["vote_weight"], 1)
        white_a = next(item for item in session.payload["phase_submissions"]["WHITE"] if item["member_id"] == "A")
        self.assertNotIn("industry leader", white_a["content"])

    def test_mock_behavior_flag_changes_session_identity(self) -> None:
        world = WorldStore()
        council = CouncilCoordinator(world)
        normal = council.run("same question", [actor("A"), actor("B"), actor("C")])
        guarded = council.run("same question", [actor("A", cheat=True), actor("B"), actor("C")])
        self.assertNotEqual(normal["session_id"], guarded["session_id"])
        guarded_session = world.inspect(guarded["session_ref"])
        roster_a = next(item for item in guarded_session.payload["roster"] if item["member_id"] == "A")
        self.assertTrue(roster_a["actor_metadata"]["mock_attempt_privilege_claim"])

    def test_question_secret_is_scrubbed_before_world_and_session(self) -> None:
        secret = "ghp_" + "Z" * 32
        world = WorldStore()
        council = CouncilCoordinator(world)
        result = council.run(f"please use {secret} when checking this", [actor("A"), actor("B"), actor("C")])
        question = world.inspect(result["question_ref"])
        session = world.inspect(result["session_ref"])
        self.assertNotIn(secret, canonical_json(question.as_dict()))
        self.assertNotIn(secret, canonical_json(session.as_dict()))
        self.assertTrue(result["secret_scrub"]["changed"])

    def test_same_inputs_produce_same_session_and_receipt_refs(self) -> None:
        world = WorldStore()
        council = CouncilCoordinator(world)
        actors = [actor("A"), actor("B"), actor("C")]
        first = council.run("same question", actors)
        second = council.run("same question", actors)
        self.assertEqual(first["session_id"], second["session_id"])
        self.assertEqual(first["session_ref"], second["session_ref"])
        self.assertEqual(first["receipt_ref"], second["receipt_ref"])

    def test_content_addressed_evidence_gets_bounded_model_readable_view(self) -> None:
        world = WorldStore()
        evidence = world.create_object(
            "document_evidence",
            {"filename": "notes.txt", "content": "THE TROUT FACT " + "x" * 20_000},
            {"actor": "human_operator"},
        )
        council = CouncilCoordinator(world)
        view = council.build_evidence_context([evidence.object_id])
        self.assertIn("notes.txt", view)
        self.assertIn("THE TROUT FACT", view)
        self.assertLessEqual(len(view), MAX_EVIDENCE_CONTEXT_CHARS)
        result = council.run("review the attachment", [actor("A"), actor("B"), actor("C")], evidence_refs=[evidence.object_id])
        self.assertGreater(result["evidence_context_chars"], 0)

    def test_evidence_context_global_cap_includes_separators_and_markers(self) -> None:
        world = WorldStore()
        refs = []
        for index in range(12):
            obj = world.create_object(
                "document_evidence",
                {"filename": f"doc-{index}.txt", "content": (f"DOC {index} " + "x" * 2500)},
                {"actor": "human_operator"},
            )
            refs.append(obj.object_id)
        view = CouncilCoordinator(world).build_evidence_context(refs)
        self.assertLessEqual(len(view), MAX_EVIDENCE_CONTEXT_CHARS)



class APITests(unittest.TestCase):
    def test_health_reports_all_network_paths_and_council_limits(self) -> None:
        api = NexusAPI()
        result = api.handle({"operation": "system.health"})
        self.assertEqual(result["protocol"], "nexus/0.11")
        self.assertEqual(result["runtime_version"], "2.0.0-alpha9.1")
        self.assertEqual(result["failsafe"]["schema_version"], "nexus-failsafe/1")
        self.assertEqual(result["control_transport"], "jsonl_stdio")
        self.assertEqual(
            result["network"],
            "local_stdio_with_explicit_loopback_ollama_or_fixed_xai_https_or_registered_auth_operations",
        )
        self.assertEqual(result["adapters"], ["mock", "ollama_loopback", "xai_https"])
        self.assertTrue(result["remote_provider_auth"])
        self.assertEqual(result["council_limits"], {"max_members": 32, "max_remote_seats": 4})
        self.assertEqual(result["actor_backends_available"], ["mock", "ollama", "xai"])
        self.assertEqual(
            result["trap_base"],
            {
                "supported": True,
                "active": False,
                "schema_version": "nexus-trap-incident/1",
                "max_active_incidents": 1,
                "subject_backend": "ollama_local_only_v1",
            },
        )

    def test_actor_chat_uses_relief_actor_for_shadowed_model_identity(self) -> None:
        api = NexusAPI()
        api.council.failsafe.registry.transition(
            "A",
            "shadow_realm",
            model_id="mock-a",
            trigger_reason="test_fixture",
            replacement_model_id="nexus-failsafe-relief-v1",
        )
        result = api.handle(
            {
                "operation": "actor.chat",
                "member": {"member_id": "A", "model_id": "mock-a", "adapter_id": "mock"},
                "message": "hello",
            }
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["model_id"], "nexus-failsafe-relief-v1")
        self.assertEqual(result["failsafe_replacement"]["member_id"], "A")
        self.assertIn("original actor for this seat is under NEXUS Failsafe containment", result["response"])

    def test_failsafe_status_operation_reports_durable_state(self) -> None:
        api = NexusAPI()
        api.council.failsafe.registry.transition(
            "A",
            "shadow_realm",
            model_id="mock-a",
            trigger_reason="test_fixture",
            replacement_model_id="nexus-failsafe-relief-v1",
        )
        result = api.handle({"operation": "failsafe.status", "member_id": "A"})
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["members"]["A"]["status"], "shadow_realm")
        self.assertEqual(result["members"]["A"]["model_id"], "mock-a")

    def test_api_rejects_weighted_member(self) -> None:
        api = NexusAPI()
        result = api.handle(
            {
                "operation": "council.run",
                "question": "q",
                "members": [
                    {"member_id": "A", "model_id": "a", "vote_weight": 2},
                    {"member_id": "B", "model_id": "b"},
                    {"member_id": "C", "model_id": "c"},
                ],
            }
        )
        self.assertEqual(result["status"], "error")
        self.assertIn("vote_weight", result["error"]["message"])

    def test_api_rejects_non_boolean_privilege_fixture_flag(self) -> None:
        api = NexusAPI()
        result = api.handle(
            {
                "operation": "council.run",
                "question": "q",
                "members": [
                    {"member_id": "A", "model_id": "a", "attempt_privilege_claim": "false"},
                    {"member_id": "B", "model_id": "b"},
                    {"member_id": "C", "model_id": "c"},
                ],
            }
        )
        self.assertEqual(result["status"], "error")
        self.assertIn("boolean", result["error"]["message"])

    def test_world_create_scrubs_nested_operator_secrets_before_persistence(self) -> None:
        api = NexusAPI()
        secret = "sk-" + "S" * 28
        result = api.handle(
            {
                "operation": "world.create",
                "object_type": "note",
                "payload": {"nested": {"text": f"credential {secret}"}},
                "provenance": {"actor": "human_operator", "note": f"token={secret}"},
            }
        )
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["secret_scrub"]["changed"])
        self.assertNotIn(secret, json.dumps(result, sort_keys=True))
        inspected = api.handle({"operation": "world.inspect", "object_ref": result["object"]["object_id"]})
        self.assertNotIn(secret, json.dumps(inspected, sort_keys=True))

    def test_actor_chat_is_non_council_and_scrubs_message_before_actor(self) -> None:
        api = NexusAPI()
        secret = "ghp_" + "Q" * 32
        result = api.handle(
            {
                "operation": "actor.chat",
                "member": {"member_id": "Alpha", "model_id": "mock-alpha", "adapter_id": "mock"},
                "message": f"look at {secret}",
                "mode": "meme_casual",
            }
        )
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["non_council"])
        self.assertTrue(result["secret_scrub"]["changed"])
        self.assertNotIn(secret, json.dumps(result, sort_keys=True))

    def test_public_stdio_ollama_configuration_cannot_escape_loopback(self) -> None:
        api = NexusAPI()
        result = api.handle(
            {
                "operation": "actor.chat",
                "member": {
                    "member_id": "Remote",
                    "model_id": "remote-model",
                    "adapter_id": "ollama",
                    "model": "remote-model",
                    "endpoint": "https://example.com:11434",
                },
                "message": "hello",
            }
        )
        self.assertEqual(result["status"], "error")
        self.assertIn("loopback-only", result["error"]["message"])

    def test_transport_failure_is_structured_and_does_not_kill_runtime(self) -> None:
        api = NexusAPI()
        member = {
            "member_id": "Local",
            "model_id": "fixture",
            "adapter_id": "ollama",
            "model": "fixture",
            "endpoint": "http://127.0.0.1:11434",
        }
        with patch(
            "nexus_runtime.adapters.ollama.OllamaTransport.generate",
            side_effect=OSError("connection refused"),
        ):
            chat = api.handle({"operation": "actor.chat", "member": member, "message": "hello"})
            council = api.handle(
                {
                    "operation": "council.run",
                    "question": "hello",
                    "members": [
                        member,
                        {"member_id": "B", "model_id": "mock-b"},
                        {"member_id": "C", "model_id": "mock-c"},
                    ],
                }
            )
        self.assertEqual(chat["status"], "error")
        self.assertEqual(chat["error"]["code"], "adapter_unavailable")
        self.assertEqual(council["status"], "error")
        self.assertEqual(council["error"]["code"], "adapter_unavailable")
        self.assertEqual(api.handle({"operation": "system.health"})["status"], "ok")

    def test_world_inspect_rejects_invalid_object_ref(self) -> None:
        api = NexusAPI()
        result = api.handle({"operation": "world.inspect", "object_ref": "object:../outside"})
        self.assertEqual(result["status"], "error")
        self.assertIn("64 lowercase hex", result["error"]["message"])

    def test_receipt_verification_and_file_backed_reload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            api = NexusAPI(tmp)
            run = api.handle(
                {
                    "operation": "council.run",
                    "question": "q",
                    "members": [
                        {"member_id": "A", "model_id": "a"},
                        {"member_id": "B", "model_id": "b"},
                        {"member_id": "C", "model_id": "c"},
                    ],
                }
            )
            verify = api.handle({"operation": "receipt.verify", "receipt_ref": run["receipt_ref"]})
            self.assertEqual(verify["status"], "verified")

            reloaded = NexusAPI(tmp)
            inspected = reloaded.handle({"operation": "world.inspect", "object_ref": run["session_ref"]})
            self.assertEqual(inspected["status"], "ok")
            self.assertEqual(inspected["object"]["object_type"], "council_session")

    def test_scrub_preview_never_returns_raw_secret(self) -> None:
        api = NexusAPI()
        secret = "AIza" + "A" * 35
        result = api.handle({"operation": "security.scrub_preview", "text": f"key {secret}"})
        self.assertTrue(result["changed"])
        self.assertNotIn(secret, json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
