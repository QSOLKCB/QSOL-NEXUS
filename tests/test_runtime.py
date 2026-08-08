from __future__ import annotations

import json
import tempfile
import unittest

from nexus_runtime.api import NexusAPI
from nexus_runtime.canonical import canonical_json, sha256_ref
from nexus_runtime.council import CouncilCoordinator
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

    def test_epistemic_privilege_is_forbidden(self) -> None:
        with self.assertRaises(ValueError):
            CouncilMember(member_id="A", model_id="mock-a", epistemic_privilege="frontier")

    def test_exact_two_thirds_threshold(self) -> None:
        policy = CouncilPolicy()
        self.assertTrue(policy.reaches_consensus(2, 3))
        self.assertFalse(policy.reaches_consensus(3, 5))


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


class CouncilTests(unittest.TestCase):
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


class APITests(unittest.TestCase):
    def test_health_and_mock_only_network_posture(self) -> None:
        api = NexusAPI()
        result = api.handle({"operation": "system.health"})
        self.assertEqual(result["network"], "none")
        self.assertEqual(result["adapters"], ["mock"])

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
