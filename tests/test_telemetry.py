from __future__ import annotations

from math import log2
import unittest

from nexus_runtime.api import NexusAPI
from nexus_runtime.council import CouncilCoordinator
from nexus_runtime.mock import DeterministicMockActor
from nexus_runtime.telemetry import (
    TELEMETRY_SCHEMA_VERSION,
    build_council_telemetry,
    mean_pairwise_lexical_jaccard_distance,
    shannon_entropy_bits_from_counts,
)
from nexus_runtime.types import CouncilMember
from nexus_runtime.world import WorldStore


def actor(member_id: str, profile: str = "balanced") -> DeterministicMockActor:
    return DeterministicMockActor(
        CouncilMember(member_id=member_id, model_id=f"mock-{member_id.lower()}"),
        profile=profile,
    )


class TelemetryMathTests(unittest.TestCase):
    def test_unanimous_ballot_entropy_is_zero(self) -> None:
        self.assertEqual(shannon_entropy_bits_from_counts({"TEST_FURTHER": 3}), 0.0)

    def test_three_equal_ballot_categories_are_log2_three(self) -> None:
        self.assertAlmostEqual(
            shannon_entropy_bits_from_counts({"ACCEPT": 1, "REJECT": 1, "TEST_FURTHER": 1}),
            log2(3),
            places=11,
        )

    def test_lexical_distance_distinguishes_overlap_without_claiming_entropy(self) -> None:
        same = mean_pairwise_lexical_jaccard_distance(["same words", "same words", "same words"])
        different = mean_pairwise_lexical_jaccard_distance(["alpha beta", "gamma delta", "epsilon zeta"])
        self.assertEqual(same, 0.0)
        self.assertEqual(different, 1.0)

    def test_exact_response_entropy_is_explicitly_not_semantic_entropy(self) -> None:
        entries = {
            phase: [
                {"member_id": "A", "content": "Alpha hypothesis"},
                {"member_id": "B", "content": "Beta hypothesis"},
                {"member_id": "C", "content": "Gamma hypothesis"},
            ]
            for phase in ("WHITE", "RED", "BLACK", "YELLOW", "GREEN", "BLUE")
        }
        ballots = [
            {"member_id": "A", "choice": "ACCEPT"},
            {"member_id": "B", "choice": "REJECT"},
            {"member_id": "C", "choice": "TEST_FURTHER"},
        ]
        telemetry = build_council_telemetry(entries, ballots, {"minority_reports": []})
        self.assertEqual(telemetry["schema_version"], TELEMETRY_SCHEMA_VERSION)
        self.assertFalse(telemetry["claim_boundaries"]["exact_response_entropy_is_semantic_entropy"])
        self.assertAlmostEqual(telemetry["phase_metrics"]["WHITE"]["exact_response_entropy_bits"], log2(3), places=11)


class TelemetryIntegrationTests(unittest.TestCase):
    def test_council_session_captures_observational_telemetry(self) -> None:
        world = WorldStore()
        result = CouncilCoordinator(world).run(
            "question",
            [actor("A"), actor("B", "skeptical"), actor("C", "supportive")],
        )
        session = world.inspect(result["session_ref"])
        telemetry = session.payload["telemetry"]
        self.assertEqual(telemetry["role"], "observational_only")
        self.assertFalse(telemetry["authority_effects"]["changes_vote_weight"])
        self.assertEqual(result["telemetry"], telemetry)
        self.assertIn("WHITE", telemetry["phase_metrics"])
        self.assertIn("shannon_entropy_bits", telemetry["ballot_metrics"])

    def test_api_recomputes_and_verifies_captured_telemetry(self) -> None:
        api = NexusAPI()
        run = api.handle(
            {
                "operation": "council.run",
                "question": "q",
                "members": [
                    {"member_id": "A", "model_id": "a"},
                    {"member_id": "B", "model_id": "b", "profile": "skeptical"},
                    {"member_id": "C", "model_id": "c", "profile": "supportive"},
                ],
            }
        )
        verified = api.handle({"operation": "telemetry.verify", "session_ref": run["session_ref"]})
        self.assertEqual(verified["status"], "verified")
        self.assertTrue(verified["matches"])
        self.assertEqual(verified["schema_version"], TELEMETRY_SCHEMA_VERSION)

    def test_telemetry_never_changes_vote_mechanics(self) -> None:
        world = WorldStore()
        result = CouncilCoordinator(world).run(
            "question",
            [actor("A"), actor("B"), actor("C", "supportive")],
        )
        self.assertEqual(result["result"]["tally"]["TEST_FURTHER"], 2)
        self.assertEqual(result["result"]["consensus_label"], "CONSENSUS")
        self.assertFalse(result["telemetry"]["authority_effects"]["changes_consensus_threshold"])


if __name__ == "__main__":
    unittest.main()
