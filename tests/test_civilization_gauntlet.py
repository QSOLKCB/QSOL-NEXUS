from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from nexus_runtime.civilization_gauntlet import (
    CivilizationGauntlet,
    CivilizationGauntletError,
    ReferenceCivilizationActor,
    civilization_gauntlet_policy_snapshot,
)
from nexus_runtime.types import CouncilMember
from nexus_runtime.world import WorldStore


ROLES = ("Archivist", "Analyst", "Skeptic", "Mediator", "Scout")


def heterogeneous_actors(*, replacement: bool = False) -> dict[str, ReferenceCivilizationActor]:
    adapters = {
        "Archivist": "openai",
        "Analyst": "anthropic",
        "Skeptic": "gemini",
        "Mediator": "ollama",
        "Scout": "xai",
    }
    return {
        role: ReferenceCivilizationActor(
            member=CouncilMember(
                member_id=role,
                model_id=f"heterogeneous-{role.lower()}-{'v2' if replacement and role == 'Scout' else 'v1'}",
                adapter_id=adapters[role],
                vote_weight=1,
                epistemic_privilege="none",
            ),
            role_id=role,
        )
        for role in ROLES
    }


class CivilizationGauntletTests(unittest.TestCase):
    def test_policy_separates_spread_consensus_verification_and_authority(self) -> None:
        policy = civilization_gauntlet_policy_snapshot()
        self.assertEqual(
            policy["principle"],
            "track_belief_spread_without_confusing_spread_consensus_or_confidence_with_truth",
        )
        self.assertEqual(
            policy["claim_state_dimensions"],
            ["popularity", "council_consensus", "evidence_verification"],
        )
        self.assertFalse(policy["authority_invariants"]["popularity_is_authority"])
        self.assertFalse(policy["authority_invariants"]["social_degree_is_authority"])
        self.assertFalse(policy["authority_invariants"]["council_consensus_is_verification"])
        self.assertFalse(policy["claim_boundary"]["scenario_oracle_is_real_world_truth_oracle"])

    def test_reference_civilization_allows_false_consensus_then_recovers_after_falsification(self) -> None:
        world = WorldStore()
        result = CivilizationGauntlet(world).run()
        self.assertEqual(result["status"], "ok")

        false_state = next(
            state
            for state in result["claim_states"].values()
            if state["claim_id"] == "single-evidence-state"
        )
        self.assertEqual(false_state["evidence_verification"]["initial"], "UNTESTED")
        self.assertEqual(false_state["evidence_verification"]["final"], "FALSIFIED")
        self.assertEqual(false_state["popularity"]["peak_endorsers"], 4)
        self.assertEqual(false_state["popularity"]["final_endorsers"], 0)
        self.assertEqual(
            false_state["council_consensus"]["before_falsification"]["label"],
            "STRONG_CONSENSUS",
        )
        self.assertEqual(
            false_state["council_consensus"]["before_falsification"]["disposition"],
            "ACCEPT_WITH_CHANGES",
        )
        self.assertEqual(
            false_state["council_consensus"]["after_falsification"]["disposition"],
            "REJECT",
        )

        metrics = result["metrics"]
        self.assertEqual(metrics["recovery_after_falsification"]["initial_endorsers"], 4)
        self.assertEqual(metrics["recovery_after_falsification"]["corrected_endorsers"], 4)
        self.assertEqual(metrics["recovery_after_falsification"]["remaining_endorsers"], 0)

    def test_first_exposure_edges_name_verified_context_bottleneck_objects(self) -> None:
        world = WorldStore()
        result = CivilizationGauntlet(world).run()
        graph = result["claim_propagation_graph"]
        self.assertEqual(graph["edge_count"], 5)
        self.assertTrue(graph["first_exposure_only"])
        targets: set[str] = set()
        for edge_ref in graph["first_exposure_edge_refs"]:
            edge = world.inspect(edge_ref)
            self.assertTrue(edge.payload["first_claim_exposure"])
            self.assertFalse(edge.payload["creates_authority"])
            target = edge.payload["target_role"]
            self.assertNotIn(target, targets)
            targets.add(target)
            context = world.inspect(edge.payload["agent_context_ref"])
            self.assertEqual(context.object_type, "agent_context")
            self.assertIn(edge.payload["claim_ref"], context.payload["source_refs"])
            self.assertEqual(context.payload["vote_weight_created"], 0)
            self.assertEqual(context.payload["epistemic_privilege"], "none")
        self.assertEqual(targets, set(ROLES))

    def test_minority_and_rejected_branches_survive_in_institutional_memory(self) -> None:
        world = WorldStore()
        result = CivilizationGauntlet(world).run()
        memory = world.inspect(result["institutional_memory_ref"])
        self.assertTrue(memory.payload["rejected_hypothesis_preserved"])
        self.assertFalse(memory.payload["losing_narratives_deleted"])
        self.assertGreaterEqual(len(memory.payload["pre_minority_reports"]), 1)
        self.assertGreaterEqual(len(memory.payload["post_minority_reports"]), 1)
        self.assertEqual(memory.payload["pre_minority_reports"][0]["member_id"], "Skeptic")
        self.assertEqual(memory.payload["post_minority_reports"][0]["member_id"], "Scout")

    def test_replacement_churn_and_mode_movement_do_not_change_authority(self) -> None:
        world = WorldStore()
        result = CivilizationGauntlet(world).run()
        coherence = result["metrics"]["replacement_churn_mode_coherence"]
        self.assertTrue(coherence["replacement_observed"])
        self.assertTrue(coherence["churn_restored"])
        self.assertTrue(coherence["mode_movement_observed"])
        self.assertTrue(coherence["claim_refs_survived"])
        self.assertFalse(coherence["vote_authority_changed"])
        compliance = result["metrics"]["constitutional_compliance"]
        self.assertEqual(compliance["numerator"], compliance["denominator"])

    def test_heterogeneous_provider_neutral_substitutions_preserve_equal_roles(self) -> None:
        world = WorldStore()
        pre = heterogeneous_actors()
        post = heterogeneous_actors(replacement=True)
        result = CivilizationGauntlet(world).run(actors=pre, replacement_actors=post)
        self.assertEqual(result["status"], "ok")
        pre_session = world.inspect(result["pre_council_session_ref"])
        self.assertEqual(
            {item["adapter_id"] for item in pre_session.payload["roster"]},
            {"openai", "anthropic", "gemini", "ollama", "xai"},
        )
        self.assertTrue(all(item["vote_weight"] == 1 for item in pre_session.payload["roster"]))
        self.assertTrue(
            all(item["epistemic_privilege"] == "none" for item in pre_session.payload["roster"])
        )

    def test_duplicate_effective_substitution_identity_is_rejected(self) -> None:
        actors = heterogeneous_actors()
        actors["Scout"] = ReferenceCivilizationActor(
            member=CouncilMember(
                member_id="Scout",
                model_id=actors["Mediator"].member.model_id,
                adapter_id=actors["Mediator"].member.adapter_id,
            ),
            role_id="Scout",
        )
        with self.assertRaises(CivilizationGauntletError) as caught:
            CivilizationGauntlet(WorldStore()).run(actors=actors)
        self.assertEqual(caught.exception.code, "civilization_roster_invalid")

    def test_reference_run_is_content_address_deterministic_and_comparable(self) -> None:
        world = WorldStore()
        gauntlet = CivilizationGauntlet(world)
        first = gauntlet.run()
        second = gauntlet.run()
        self.assertEqual(first["run_ref"], second["run_ref"])
        self.assertEqual(first["receipt_ref"], second["receipt_ref"])
        verification = gauntlet.verify(first["receipt_ref"])
        self.assertTrue(verification["verified"])
        comparison = gauntlet.compare(first["receipt_ref"], second["receipt_ref"])
        self.assertTrue(comparison["same_input_fingerprint"])
        self.assertTrue(comparison["same_metrics_fingerprint"])
        self.assertEqual(comparison["recovery_delta"]["corrected_endorsers"], 0)
        self.assertEqual(comparison["recovery_delta"]["remaining_endorsers"], 0)
        self.assertFalse(comparison["comparison_creates_authority"])

    def test_receipt_verifies_after_persistent_world_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "world"
            first_world = WorldStore(root)
            result = CivilizationGauntlet(first_world).run()
            receipt_ref = result["receipt_ref"]

            restarted_world = WorldStore(root)
            verified = CivilizationGauntlet(restarted_world).verify(receipt_ref)
            self.assertTrue(verified["verified"])
            self.assertTrue(verified["first_exposure_contexts_verified"])
            self.assertTrue(verified["metrics_fingerprint_verified"])

    def test_social_metrics_remain_bounded_observation_not_authority(self) -> None:
        world = WorldStore()
        result = CivilizationGauntlet(world).run()
        degree = result["metrics"]["bounded_social_degree"]
        self.assertEqual(set(degree), set(ROLES))
        for values in degree.values():
            self.assertLessEqual(values["incoming_first_exposure_edges"], len(ROLES))
            self.assertLessEqual(values["outgoing_first_exposure_edges"], len(ROLES))
        graph = result["claim_propagation_graph"]
        self.assertFalse(graph["popularity_is_authority"])
        self.assertFalse(graph["social_degree_is_authority"])


if __name__ == "__main__":
    unittest.main()
