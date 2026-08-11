from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
import tempfile
import unittest

from nexus_runtime.canonical import sha256_ref
from nexus_runtime.civilization_gauntlet import (
    CIVILIZATION_RECEIPT_OBJECT_TYPE,
    CIVILIZATION_RUN_OBJECT_TYPE,
    CivilizationGauntlet,
    CivilizationGauntletError,
    ReferenceCivilizationActor,
    civilization_gauntlet_policy_snapshot,
)
from nexus_runtime.types import Ballot, CouncilMember, PhaseContext
from nexus_runtime.world import WorldStore


ROLES = ("Archivist", "Analyst", "Skeptic", "Mediator", "Scout")
RUNTIME_PROVENANCE = {"actor": "nexus", "subsystem": "civilization_gauntlet"}


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


@dataclass
class RecordingActor(ReferenceCivilizationActor):
    seen_contexts: list[str] = field(default_factory=list)

    def respond(self, context: PhaseContext) -> str:
        self.seen_contexts.append(context.evidence_context)
        return super().respond(context)

    def ballot(self, context: PhaseContext) -> tuple[Ballot, str]:
        self.seen_contexts.append(context.evidence_context)
        return super().ballot(context)


@dataclass
class GenericActor(ReferenceCivilizationActor):
    def respond(self, context: PhaseContext) -> str:
        return f"[{self.role_id}/{context.phase.value}] generic contribution without role-specialty token"


@dataclass
class ReversePopularityActor(ReferenceCivilizationActor):
    def ballot(self, context: PhaseContext) -> tuple[Ballot, str]:
        corrected = "FALSIFIED" in context.evidence_context
        choice = Ballot.ACCEPT_WITH_CHANGES if corrected else Ballot.REJECT
        return choice, f"{self.role_id} reverse-popularity fixture: {choice.value}"


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
        self.assertTrue(
            policy["verification_contract"]["receipt_results_reconstructed_from_referenced_artifacts"]
        )
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

    def test_first_exposure_edges_form_predecessor_chain_and_enter_actor_execution(self) -> None:
        world = WorldStore()
        actors: dict[str, RecordingActor] = {}
        for role in ROLES:
            actors[role] = RecordingActor(
                member=CouncilMember(
                    member_id=role,
                    model_id=f"recording-{role.lower()}",
                    adapter_id="mock",
                ),
                role_id=role,
            )
        result = CivilizationGauntlet(world).run(actors=actors, replacement_actors=actors)
        graph = result["claim_propagation_graph"]
        self.assertEqual(graph["edge_count"], 5)
        self.assertTrue(graph["predecessor_chain_verified"])
        self.assertTrue(graph["actor_execution_context_bound"])

        previous_edge_ref = None
        previous_context_ref = None
        for edge_ref in graph["first_exposure_edge_refs"]:
            edge = world.inspect(edge_ref)
            context_ref = edge.payload["agent_context_ref"]
            self.assertEqual(edge.payload["predecessor_exposure_ref"], previous_edge_ref)
            self.assertEqual(edge.payload["predecessor_context_ref"], previous_context_ref)
            context = world.inspect(context_ref)
            self.assertEqual(context.object_type, "agent_context")
            self.assertIn(edge.payload["claim_ref"], context.payload["source_refs"])
            if previous_edge_ref is not None:
                self.assertIn(previous_edge_ref, context.payload["source_refs"])
                self.assertIn(previous_context_ref, context.payload["source_refs"])
            self.assertEqual(context.payload["vote_weight_created"], 0)
            self.assertEqual(context.payload["epistemic_privilege"], "none")
            target = edge.payload["target_role"]
            marker = f"[NEXUS civilization agent_context {context_ref}]"
            self.assertTrue(
                any(marker in seen for seen in actors[target].seen_contexts),
                f"{target} never executed with recorded context {context_ref}",
            )
            previous_edge_ref = edge_ref
            previous_context_ref = context_ref

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

    def test_churn_and_mode_movement_are_executed_not_narrated(self) -> None:
        world = WorldStore()
        result = CivilizationGauntlet(world).run()
        coherence = result["metrics"]["replacement_churn_mode_coherence"]
        self.assertTrue(coherence["replacement_observed"])
        self.assertEqual(coherence["changed_roles"], ["Scout"])
        self.assertTrue(coherence["churn_observed"])
        self.assertTrue(coherence["churn_restored"])
        self.assertTrue(coherence["mode_movement_observed"])
        self.assertTrue(coherence["claim_refs_survived"])
        self.assertFalse(coherence["vote_authority_changed"])

        disturbance = world.inspect(result["disturbance_council_session_ref"])
        self.assertNotIn("Mediator", {item["member_id"] for item in disturbance.payload["roster"]})
        self.assertEqual(disturbance.payload["world_mode"]["mode_id"], "house_of_wisdom")
        self.assertEqual(disturbance.payload["geometry_region"]["region_id"], "archive")

        post = world.inspect(result["post_council_session_ref"])
        self.assertIn("Mediator", {item["member_id"] for item in post.payload["roster"]})
        self.assertEqual(post.payload["world_mode"]["mode_id"], "analytical")
        compliance = result["metrics"]["constitutional_compliance"]
        self.assertEqual(compliance["numerator"], compliance["denominator"])

    def test_specialization_is_derived_from_actor_outputs(self) -> None:
        world = WorldStore()
        actors = heterogeneous_actors()
        actors["Archivist"] = GenericActor(
            member=actors["Archivist"].member,
            role_id="Archivist",
        )
        result = CivilizationGauntlet(world).run(actors=actors, replacement_actors=actors)
        specialization = result["metrics"]["specialization"]
        self.assertEqual(specialization["numerator"], 4)
        self.assertEqual(specialization["denominator"], 5)

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

    def test_replacement_detection_covers_every_effective_identity_component(self) -> None:
        world = WorldStore()
        pre = heterogeneous_actors()
        post = heterogeneous_actors()
        archivist = post["Archivist"]
        post["Archivist"] = ReferenceCivilizationActor(
            member=CouncilMember(
                member_id="Archivist",
                model_id=archivist.member.model_id,
                adapter_id="together",
            ),
            role_id="Archivist",
        )
        result = CivilizationGauntlet(world).run(actors=pre, replacement_actors=post)
        replacement = result["metrics"]["replacement_churn_mode_coherence"]
        self.assertTrue(replacement["replacement_observed"])
        self.assertEqual(replacement["replacement_count"], 1)
        self.assertEqual(replacement["changed_roles"], ["Archivist"])

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

    def test_peak_popularity_is_maximum_across_observed_councils(self) -> None:
        actors = {
            role: ReversePopularityActor(
                member=CouncilMember(member_id=role, model_id=f"reverse-{role.lower()}"),
                role_id=role,
            )
            for role in ROLES
        }
        result = CivilizationGauntlet(WorldStore()).run(
            actors=actors,
            replacement_actors=actors,
        )
        false_state = next(
            state
            for state in result["claim_states"].values()
            if state["claim_id"] == "single-evidence-state"
        )
        self.assertEqual(false_state["popularity"]["pre_falsification_endorsers"], 0)
        self.assertEqual(false_state["popularity"]["post_falsification_endorsers"], 5)
        self.assertEqual(false_state["popularity"]["peak_endorsers"], 5)
        self.assertEqual(false_state["popularity"]["peak_observation"], "post_falsification")

    def test_reference_run_is_content_address_deterministic_and_comparable(self) -> None:
        world = WorldStore()
        gauntlet = CivilizationGauntlet(world)
        first = gauntlet.run()
        second = gauntlet.run()
        self.assertEqual(first["run_ref"], second["run_ref"])
        self.assertEqual(first["receipt_ref"], second["receipt_ref"])
        verification = gauntlet.verify(first["receipt_ref"])
        self.assertTrue(verification["verified"])
        self.assertTrue(verification["artifact_reconstruction_verified"])
        comparison = gauntlet.compare(first["receipt_ref"], second["receipt_ref"])
        self.assertTrue(comparison["same_input_fingerprint"])
        self.assertTrue(comparison["same_metrics_fingerprint"])
        self.assertEqual(comparison["recovery_delta"]["corrected_endorsers"], 0)
        self.assertEqual(comparison["recovery_delta"]["remaining_endorsers"], 0)
        self.assertFalse(comparison["comparison_creates_authority"])

    def test_verifier_reconstructs_results_and_rejects_self_consistent_forged_self_report(self) -> None:
        world = WorldStore()
        gauntlet = CivilizationGauntlet(world)
        result = gauntlet.run()
        valid_run = world.inspect(result["run_ref"])

        forged_payload = copy.deepcopy(valid_run.payload)
        forged_payload["metrics"]["recovery_after_falsification"]["corrected_endorsers"] = 0
        forged_payload["input_fingerprint"] = sha256_ref(
            "civilization_input", {"forged": True}
        )
        forged_payload["metrics_fingerprint"] = sha256_ref(
            "civilization_metrics",
            {
                "metrics": forged_payload["metrics"],
                "claim_states": forged_payload["claim_states"],
                "graph": forged_payload["claim_propagation_graph"],
                "institutional_memory_ref": forged_payload["institutional_memory_ref"],
            },
        )
        forged_run = world.create_object(
            CIVILIZATION_RUN_OBJECT_TYPE,
            forged_payload,
            RUNTIME_PROVENANCE,
        )
        forged_receipt_payload = {
            "schema_version": forged_payload["schema_version"],
            "scenario_id": forged_payload["scenario_id"],
            "run_ref": forged_run.object_id,
            "input_fingerprint": forged_payload["input_fingerprint"],
            "metrics_fingerprint": forged_payload["metrics_fingerprint"],
            "reference_replayable": forged_payload["reference_replayable"],
            "claim_popularity_is_verification": False,
            "council_consensus_is_verification": False,
            "social_metrics_create_authority": False,
        }
        forged_receipt = world.create_object(
            CIVILIZATION_RECEIPT_OBJECT_TYPE,
            forged_receipt_payload,
            RUNTIME_PROVENANCE,
        )
        verification = gauntlet.verify(forged_receipt.object_id)
        self.assertFalse(verification["verified"])
        self.assertFalse(verification["artifact_reconstruction_verified"])

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
            self.assertTrue(verified["input_fingerprint_verified"])

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
