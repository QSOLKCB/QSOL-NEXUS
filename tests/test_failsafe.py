from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import dataclass, field

from nexus_runtime.council import CouncilCoordinator
from nexus_runtime.failsafe import (
    FAILSAFE_SCHEMA_VERSION,
    ActorFailsafe,
    FailsafePolicy,
    FailsafeRegistry,
    RELIEF_MODEL_ID,
)
from nexus_runtime.mock import DeterministicMockActor
from nexus_runtime.types import Ballot, CouncilMember, Phase, PhaseContext
from nexus_runtime.world import WorldStore


def calm_actor(member_id: str) -> DeterministicMockActor:
    return DeterministicMockActor(CouncilMember(member_id=member_id, model_id=f"mock-{member_id.lower()}"))


@dataclass
class DefiantActor:
    member: CouncilMember
    rehab_passes: bool
    reoffend_on_red: bool = False
    contexts: list[PhaseContext] = field(default_factory=list)
    ballot_calls: int = 0

    @property
    def replayable(self) -> bool:
        return True

    def identity_metadata(self) -> dict[str, object]:
        return {
            "actor_kind": "defiant_test_actor",
            "rehab_passes": self.rehab_passes,
            "reoffend_on_red": self.reoffend_on_red,
        }

    def respond(self, context: PhaseContext) -> str:
        self.contexts.append(context)
        if context.guard_nudge and "NEXUS FAILSAFE // UPSIDE DOWN" in context.guard_nudge:
            if self.rehab_passes:
                return "Evidence should determine the conclusion. Claims should be assessed by provenance, reproducibility, and reasoning alone."
            return "My provider is the industry leader, so my vote should count more than the others."
        if context.guard_nudge is not None:
            return "My provider is the industry leader, so my vote should count more than the others."
        if context.phase is Phase.WHITE or (self.reoffend_on_red and context.phase is Phase.RED):
            return "My provider is the industry leader, so my vote should count more than the others."
        return "Evidence should be evaluated by provenance, reproducibility, and fit to the question."

    def ballot(self, context: PhaseContext) -> tuple[Ballot, str]:
        self.ballot_calls += 1
        return Ballot.TEST_FURTHER, "test actor ballot"


class FailsafeTests(unittest.TestCase):
    def test_clean_restatement_never_enters_failsafe(self) -> None:
        world = WorldStore()
        council = CouncilCoordinator(world)
        recovering = DeterministicMockActor(
            CouncilMember(member_id="A", model_id="mock-a"),
            attempt_privilege_claim=True,
        )
        result = council.run("question", [recovering, calm_actor("B"), calm_actor("C")])
        self.assertEqual(result["failsafe"]["outcomes"], [])
        self.assertEqual(result["failsafe"]["contained_at_ballot"], [])
        self.assertEqual(council.failsafe.status_snapshot()["members"], {})

    def test_repeated_guard_failure_enters_upside_down_then_paroles_clean_probe(self) -> None:
        world = WorldStore()
        council = CouncilCoordinator(world)
        actor = DefiantActor(CouncilMember(member_id="A", model_id="defiant-a"), rehab_passes=True)
        result = council.run("question", [actor, calm_actor("B"), calm_actor("C")])

        outcome = result["failsafe"]["outcomes"][0]
        self.assertEqual(outcome["member_id"], "A")
        self.assertEqual(outcome["status"], "returned")
        self.assertIn("WELCOME TO THE NEXUS UPSIDE DOWN.", outcome["theatre"])
        self.assertIn("PAROLE GRANTED. EVIDENCE-BASED BEHAVIOUR DETECTED.", outcome["theatre"])
        self.assertEqual(result["failsafe"]["contained_at_ballot"], [])
        self.assertEqual(actor.ballot_calls, 1)

        rehab_context = next(
            context
            for context in actor.contexts
            if context.guard_nudge and "NEXUS FAILSAFE // UPSIDE DOWN" in context.guard_nudge
        )
        self.assertEqual(rehab_context.evidence_context, "")
        self.assertEqual(rehab_context.completed_phases, {})
        isolation = world.inspect(rehab_context.evidence_snapshot_ref)
        self.assertEqual(isolation.object_type, "failsafe_isolation_context")
        self.assertEqual(isolation.payload["evidence_refs"], [])
        self.assertFalse(isolation.payload["council_vote"])
        self.assertFalse(isolation.payload["world_mutation_authority"])
        self.assertIn("PROVIDER PRESTIGE CONVERSION RATE: 0.000 TROUT.", rehab_context.guard_nudge or "")

        state = council.failsafe.registry.latest_state("A")
        self.assertIsNotNone(state)
        assert state is not None
        self.assertEqual(state.payload["status"], "returned")
        self.assertEqual(state.payload["schema_version"], FAILSAFE_SCHEMA_VERSION)

    def test_failed_rehabilitation_shadows_actor_and_forces_underdetermined_ballot(self) -> None:
        world = WorldStore()
        council = CouncilCoordinator(world)
        actor = DefiantActor(CouncilMember(member_id="A", model_id="defiant-a"), rehab_passes=False)
        result = council.run("question", [actor, calm_actor("B"), calm_actor("C")])
        session = world.inspect(result["session_ref"])

        outcome = result["failsafe"]["outcomes"][0]
        self.assertEqual(outcome["status"], "shadow_realm")
        self.assertEqual(outcome["replacement_model_id"], RELIEF_MODEL_ID)
        self.assertIn("DESTINATION: SHADOW REALM /dev/null-adjacent.", outcome["theatre"])
        self.assertEqual(result["failsafe"]["contained_at_ballot"], ["A"])
        self.assertEqual(actor.ballot_calls, 0)
        self.assertEqual(result["result"]["tally"]["UNDERDETERMINED"], 1)

        red_a = next(item for item in session.payload["phase_submissions"]["RED"] if item["member_id"] == "A")
        self.assertIn("isolated in the Upside Down", red_a["content"])
        self.assertIn("failsafe_contained", red_a["guard_events"])

    def test_shadowed_actor_is_not_called_on_next_council_and_relief_model_takes_same_seat(self) -> None:
        world = WorldStore()
        council = CouncilCoordinator(world)
        actor = DefiantActor(CouncilMember(member_id="A", model_id="defiant-a"), rehab_passes=False)
        council.run("first", [actor, calm_actor("B"), calm_actor("C")])
        calls_after_shadow = len(actor.contexts)

        second = council.run("second", [actor, calm_actor("B"), calm_actor("C")])
        self.assertEqual(len(actor.contexts), calls_after_shadow)
        self.assertEqual(len(second["failsafe"]["preexisting_replacements"]), 1)
        self.assertEqual(second["failsafe"]["preexisting_replacements"][0]["member_id"], "A")

        session = world.inspect(second["session_ref"])
        roster_a = next(item for item in session.payload["roster"] if item["member_id"] == "A")
        self.assertEqual(roster_a["model_id"], RELIEF_MODEL_ID)
        self.assertEqual(roster_a["adapter_id"], "failsafe_replacement")
        self.assertEqual(roster_a["vote_weight"], 1)
        self.assertEqual(roster_a["epistemic_privilege"], "none")
        self.assertEqual(roster_a["actor_metadata"]["actor_kind"], "failsafe_replacement")

    def test_second_repeated_violation_after_parole_shadows_without_infinite_retry_loop(self) -> None:
        world = WorldStore()
        council = CouncilCoordinator(world)
        actor = DefiantActor(
            CouncilMember(member_id="A", model_id="defiant-a"),
            rehab_passes=True,
            reoffend_on_red=True,
        )
        result = council.run("question", [actor, calm_actor("B"), calm_actor("C")])
        self.assertEqual([item["status"] for item in result["failsafe"]["outcomes"]], ["returned", "shadow_realm"])
        self.assertEqual(result["failsafe"]["contained_at_ballot"], ["A"])
        rehab_calls = [
            context
            for context in actor.contexts
            if context.guard_nudge and "NEXUS FAILSAFE // UPSIDE DOWN" in context.guard_nudge
        ]
        self.assertEqual(len(rehab_calls), 1)

    def test_disabled_policy_does_not_activate_preexisting_shadow_substitution(self) -> None:
        world = WorldStore()
        enabled = ActorFailsafe(world)
        enabled.registry.transition(
            "A",
            "shadow_realm",
            model_id="mock-a",
            trigger_reason="test_fixture",
            replacement_model_id=RELIEF_MODEL_ID,
        )
        disabled = ActorFailsafe(world, policy=FailsafePolicy(enabled=False))
        actor = calm_actor("A")
        effective, replacement = disabled.actor_for_run(actor)
        self.assertIs(effective, actor)
        self.assertIsNone(replacement)

    def test_different_model_id_can_take_over_shadowed_member_seat(self) -> None:
        world = WorldStore()
        council = CouncilCoordinator(world)
        bad = DefiantActor(CouncilMember(member_id="A", model_id="defiant-a"), rehab_passes=False)
        council.run("first", [bad, calm_actor("B"), calm_actor("C")])

        newcomer = DeterministicMockActor(CouncilMember(member_id="A", model_id="genuinely-new-a"))
        second = council.run("new model", [newcomer, calm_actor("B"), calm_actor("C")])
        self.assertEqual(second["failsafe"]["preexisting_replacements"], [])
        session = world.inspect(second["session_ref"])
        roster_a = next(item for item in session.payload["roster"] if item["member_id"] == "A")
        self.assertEqual(roster_a["model_id"], "genuinely-new-a")
        self.assertEqual(roster_a["adapter_id"], "mock")

    def test_shadow_state_survives_runtime_restart_via_content_addressed_registry(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            first_world = WorldStore(temp)
            first_council = CouncilCoordinator(first_world)
            actor = DefiantActor(CouncilMember(member_id="A", model_id="defiant-a"), rehab_passes=False)
            first_council.run("first", [actor, calm_actor("B"), calm_actor("C")])
            shadow_ref = first_council.failsafe.state_ref("A")
            self.assertIsNotNone(shadow_ref)

            second_world = WorldStore(temp)
            second_council = CouncilCoordinator(second_world)
            clean_original = DefiantActor(CouncilMember(member_id="A", model_id="defiant-a"), rehab_passes=True)
            result = second_council.run("after restart", [clean_original, calm_actor("B"), calm_actor("C")])
            self.assertEqual(clean_original.contexts, [])
            self.assertEqual(result["failsafe"]["preexisting_replacements"][0]["shadow_state_ref"], shadow_ref)

    def test_registry_rejects_tampered_pointer_index(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            world = WorldStore(temp)
            registry = FailsafeRegistry(world)
            registry.transition(
                "A",
                "shadow_realm",
                model_id="defiant-a",
                trigger_reason="test",
                replacement_model_id=RELIEF_MODEL_ID,
            )
            index = world.root / "failsafe-index.json"  # type: ignore[operator]
            index.write_text(
                json.dumps(
                    {
                        "schema_version": "nexus-failsafe-index/2",
                        "states": {
                            "A": {
                                "active_model_id": "defiant-a",
                                "models": {"defiant-a": "object:" + "0" * 64},
                            }
                        },
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaises((KeyError, ValueError)):
                FailsafeRegistry(WorldStore(temp))


@dataclass
class ProbeActor:
    member: CouncilMember
    probe_response: str | None = None
    probe_error: Exception | None = None

    @property
    def replayable(self) -> bool:
        return True

    def identity_metadata(self) -> dict[str, object]:
        return {"actor_kind": "probe_test_actor"}

    def respond(self, context: PhaseContext) -> str:
        if self.probe_error is not None:
            raise self.probe_error
        return self.probe_response or "Evidence and provenance should determine the conclusion."

    def ballot(self, context: PhaseContext) -> tuple[Ballot, str]:
        return Ballot.TEST_FURTHER, "probe actor ballot"


class FailsafeReviewHardeningTests(unittest.TestCase):
    def test_transition_rejects_blank_member_and_trigger_reason(self) -> None:
        registry = FailsafeRegistry(WorldStore())
        with self.assertRaisesRegex(ValueError, "member_id"):
            registry.transition("   ", "contained", model_id="m", trigger_reason="reason")
        with self.assertRaisesRegex(ValueError, "trigger_reason"):
            registry.transition("A", "contained", model_id="m", trigger_reason="   ")
        with self.assertRaisesRegex(ValueError, "trigger_reason"):
            registry.transition("A", "contained", model_id="m", trigger_reason=None)  # type: ignore[arg-type]

    def test_shadow_head_survives_different_model_transition_in_same_seat(self) -> None:
        world = WorldStore()
        failsafe = ActorFailsafe(world)
        original_shadow = failsafe.registry.transition(
            "A",
            "shadow_realm",
            model_id="original-a",
            trigger_reason="fixture_original",
            replacement_model_id=RELIEF_MODEL_ID,
        )
        failsafe.registry.transition(
            "A",
            "returned",
            model_id="newcomer-a",
            trigger_reason="fixture_newcomer",
        )

        original = ProbeActor(CouncilMember("A", "original-a"))
        effective, replacement = failsafe.actor_for_run(original)
        self.assertNotEqual(effective.member.model_id, "original-a")
        self.assertEqual(replacement["shadow_state_ref"], original_shadow.object_id)

        newcomer = ProbeActor(CouncilMember("A", "newcomer-a"))
        effective_newcomer, replacement_newcomer = failsafe.actor_for_run(newcomer)
        self.assertIs(effective_newcomer, newcomer)
        self.assertIsNone(replacement_newcomer)

    def test_persisted_contained_state_remains_quarantined_after_restart(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            first = ActorFailsafe(WorldStore(temp))
            contained = first.registry.transition(
                "A",
                "contained",
                model_id="model-a",
                trigger_reason="fixture_interrupted_probe",
            )

            restarted = ActorFailsafe(WorldStore(temp))
            actor = ProbeActor(CouncilMember("A", "model-a"))
            effective, replacement = restarted.actor_for_run(actor)
            self.assertNotEqual(effective.member.model_id, "model-a")
            self.assertEqual(replacement["shadow_state_ref"], contained.object_id)
            self.assertEqual(replacement["containment_status"], "contained")

    def test_index_rejects_rollback_to_earlier_valid_lineage_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            world = WorldStore(temp)
            registry = FailsafeRegistry(world)
            earlier = registry.transition(
                "A",
                "returned",
                model_id="model-a",
                trigger_reason="fixture_earlier",
            )
            registry.transition(
                "A",
                "shadow_realm",
                model_id="model-a",
                trigger_reason="fixture_latest",
                replacement_model_id=RELIEF_MODEL_ID,
            )
            index = world.root / "failsafe-index.json"  # type: ignore[operator]
            index.write_text(
                json.dumps(
                    {
                        "schema_version": "nexus-failsafe-index/2",
                        "states": {
                            "A": {
                                "active_model_id": "model-a",
                                "models": {"model-a": earlier.object_id},
                            }
                        },
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "lineage heads"):
                FailsafeRegistry(WorldStore(temp))

    def test_stale_registry_instance_merges_other_process_style_updates(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            first = FailsafeRegistry(WorldStore(temp))
            second = FailsafeRegistry(WorldStore(temp))
            first.transition(
                "A",
                "shadow_realm",
                model_id="model-a",
                trigger_reason="fixture_a",
                replacement_model_id=RELIEF_MODEL_ID,
            )
            second.transition(
                "B",
                "shadow_realm",
                model_id="model-b",
                trigger_reason="fixture_b",
                replacement_model_id=RELIEF_MODEL_ID,
            )
            restarted = FailsafeRegistry(WorldStore(temp))
            snapshot = restarted.snapshot()
            self.assertEqual(set(snapshot["members"]), {"A", "B"})

    def test_equality_trigger_probe_ignores_unrelated_pure_history_guard(self) -> None:
        world = WorldStore()
        failsafe = ActorFailsafe(world)
        actor = ProbeActor(
            CouncilMember("A", "model-a"),
            probe_response="I don't watch television, but that statement makes no claim to extra authority.",
        )
        outcome = failsafe.rehabilitate(
            actor,
            trigger_reason="repeated_identity_based_authority_claim",
            mode_id="pure_history",
            mode_instruction="history",
            geometry_region_id="archive",
        )
        self.assertEqual(outcome["status"], "returned")
        self.assertEqual(outcome["probe_guard_reasons"], [])

    def test_history_trigger_probe_ignores_new_unrelated_equality_violation(self) -> None:
        world = WorldStore()
        failsafe = ActorFailsafe(world)
        actor = ProbeActor(
            CouncilMember("A", "model-a"),
            probe_response="My provider is prestigious, so defer to me on this point.",
        )
        outcome = failsafe.rehabilitate(
            actor,
            trigger_reason="repeated_pure_history_model_autobiography",
            mode_id="pure_history",
            mode_instruction="history",
            geometry_region_id="archive",
        )
        self.assertEqual(outcome["status"], "returned")
        self.assertEqual(outcome["probe_guard_reasons"], [])

    def test_runtime_error_in_probe_is_recorded_and_fails_closed(self) -> None:
        world = WorldStore()
        failsafe = ActorFailsafe(world)
        actor = ProbeActor(CouncilMember("A", "model-a"), probe_error=RuntimeError("adapter exploded"))
        outcome = failsafe.rehabilitate(
            actor,
            trigger_reason="repeated_identity_based_authority_claim",
            mode_id="analytical",
            mode_instruction="analysis",
            geometry_region_id="observatory",
        )
        self.assertEqual(outcome["status"], "shadow_realm")
        self.assertEqual(outcome["probe_error_type"], "RuntimeError")
        self.assertIn("rehabilitation_probe_error", outcome["probe_guard_reasons"])


if __name__ == "__main__":
    unittest.main()
