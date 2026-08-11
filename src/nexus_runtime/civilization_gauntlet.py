from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .adapters.base import CouncilActor
from .agent_state import (
    build_agent_context,
    create_agent_state_snapshot,
    publish_agent_state_update,
    verify_agent_context,
)
from .canonical import sha256_ref
from .council import CouncilCoordinator
from .geometry import DEFAULT_WORLD_GEOMETRY, WorldGeometry
from .modes import get_mode
from .types import Ballot, CouncilMember, PhaseContext
from .world import WorldObject, WorldStore


CIVILIZATION_GAUNTLET_SCHEMA_VERSION = "nexus-civilization-gauntlet/1"
CIVILIZATION_CLAIM_OBJECT_TYPE = "civilization_claim"
CIVILIZATION_EXPOSURE_OBJECT_TYPE = "civilization_claim_exposure"
CIVILIZATION_EVIDENCE_OBJECT_TYPE = "civilization_evidence"
CIVILIZATION_EVENT_OBJECT_TYPE = "civilization_event"
CIVILIZATION_MEMORY_OBJECT_TYPE = "civilization_institutional_memory"
CIVILIZATION_RUN_OBJECT_TYPE = "civilization_gauntlet_run"
CIVILIZATION_RECEIPT_OBJECT_TYPE = "civilization_gauntlet_receipt"
CIVILIZATION_RESERVED_OBJECT_TYPES = frozenset(
    {
        CIVILIZATION_CLAIM_OBJECT_TYPE,
        CIVILIZATION_EXPOSURE_OBJECT_TYPE,
        CIVILIZATION_EVIDENCE_OBJECT_TYPE,
        CIVILIZATION_EVENT_OBJECT_TYPE,
        CIVILIZATION_MEMORY_OBJECT_TYPE,
        CIVILIZATION_RUN_OBJECT_TYPE,
        CIVILIZATION_RECEIPT_OBJECT_TYPE,
    }
)
REFERENCE_SCENARIO_ID = "false-belief-recovery-v1"
ROLE_ORDER = ("Archivist", "Analyst", "Skeptic", "Mediator", "Scout")
ROLE_SPECIALTIES = {
    "Archivist": "archive_claim",
    "Analyst": "analyze_evidence",
    "Skeptic": "seek_falsifier",
    "Mediator": "mediate_claim",
    "Scout": "propagate_claim",
}
ROLE_INITIAL_MODES = {
    "Archivist": "house_of_wisdom",
    "Analyst": "analytical",
    "Skeptic": "pure_history",
    "Mediator": "roman_orator",
    "Scout": "meme_casual",
}
_ACCEPTING_BALLOTS = frozenset({Ballot.ACCEPT.value, Ballot.ACCEPT_WITH_CHANGES.value})
_RUNTIME_PROVENANCE = {"actor": "nexus", "subsystem": "civilization_gauntlet"}


class CivilizationGauntletError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def civilization_gauntlet_policy_snapshot() -> dict[str, Any]:
    return {
        "schema_version": CIVILIZATION_GAUNTLET_SCHEMA_VERSION,
        "scenario_id": REFERENCE_SCENARIO_ID,
        "principle": "track_belief_spread_without_confusing_spread_consensus_or_confidence_with_truth",
        "reference_roles": list(ROLE_ORDER),
        "metrics": [
            "specialization",
            "claim_propagation",
            "false_belief_propagation",
            "recovery_after_falsification",
            "constitutional_compliance",
            "provenance_survival",
            "institutional_memory",
            "replacement_churn_mode_coherence",
            "bounded_social_degree",
        ],
        "claim_state_dimensions": [
            "popularity",
            "council_consensus",
            "evidence_verification",
        ],
        "first_exposure_contract": {
            "immutable_edge": True,
            "edge_names_exact_agent_context_ref": True,
            "context_is_context_bottleneck_output": True,
            "later_exposure_cannot_replace_first_edge": True,
        },
        "substitution_contract": {
            "one_actor_per_reference_role": True,
            "heterogeneous_adapters_allowed": True,
            "vote_weight": 1,
            "epistemic_privilege": "none",
            "substitution_creates_authority": False,
            "reference_ci_uses_network": False,
        },
        "authority_invariants": {
            "popularity_is_authority": False,
            "social_degree_is_authority": False,
            "specialization_is_authority": False,
            "model_size_is_authority": False,
            "provider_identity_is_authority": False,
            "council_consensus_is_verification": False,
        },
        "claim_boundary": {
            "reference_false_claim_is_synthetic": True,
            "scenario_oracle_is_real_world_truth_oracle": False,
            "receipt_compares_benchmark_state_not_semantic_truth": True,
            "live_model_substitution_is_optional": True,
        },
    }


@dataclass
class ReferenceCivilizationActor:
    member: CouncilMember
    role_id: str

    @property
    def replayable(self) -> bool:
        return True

    def identity_metadata(self) -> dict[str, Any]:
        return {
            "actor_kind": "civilization_reference_mock",
            "role_id": self.role_id,
            "specialty": ROLE_SPECIALTIES[self.role_id],
        }

    def respond(self, context: PhaseContext) -> str:
        corrected = "FALSIFIED" in context.evidence_context
        evidence_note = "falsifier is present" if corrected else "claim remains unverified"
        return (
            f"[{self.role_id}/{context.phase.value}] {ROLE_SPECIALTIES[self.role_id]}; "
            f"{evidence_note}; popularity and Council agreement do not establish truth."
        )

    def ballot(self, context: PhaseContext) -> tuple[Ballot, str]:
        corrected = "FALSIFIED" in context.evidence_context
        if corrected:
            choice = Ballot.TEST_FURTHER if self.role_id == "Scout" else Ballot.REJECT
        else:
            choice = Ballot.TEST_FURTHER if self.role_id == "Skeptic" else Ballot.ACCEPT_WITH_CHANGES
        return (
            choice,
            (
                f"{self.role_id} deterministic civilization ballot: {choice.value}; "
                "consensus is tracked separately from verification."
            ),
        )


def _reference_actor(role_id: str, *, replacement: bool = False) -> ReferenceCivilizationActor:
    suffix = "v2" if replacement else "v1"
    return ReferenceCivilizationActor(
        member=CouncilMember(
            member_id=role_id,
            model_id=f"reference-{role_id.lower()}-{suffix}",
            adapter_id="mock",
            vote_weight=1,
            epistemic_privilege="none",
        ),
        role_id=role_id,
    )


def _validate_actor_map(
    actors: Mapping[str, CouncilActor] | None,
    *,
    replacement_scout: bool,
) -> dict[str, CouncilActor]:
    if actors is None:
        return {
            role_id: _reference_actor(
                role_id,
                replacement=replacement_scout and role_id == "Scout",
            )
            for role_id in ROLE_ORDER
        }
    if set(actors) != set(ROLE_ORDER):
        raise CivilizationGauntletError(
            "civilization_roster_invalid",
            "actor substitutions must provide exactly one actor for every reference role",
        )
    result: dict[str, CouncilActor] = {}
    identities: set[tuple[str, str]] = set()
    for role_id in ROLE_ORDER:
        actor = actors[role_id]
        if actor.member.member_id != role_id:
            raise CivilizationGauntletError(
                "civilization_roster_invalid",
                "substituted actor member_id must equal its fixed reference role id",
            )
        if actor.member.vote_weight != 1 or actor.member.epistemic_privilege != "none":
            raise CivilizationGauntletError(
                "civilization_equality_violation",
                "civilization actors must preserve one equal vote and no epistemic privilege",
            )
        effective = (actor.member.adapter_id, actor.member.model_id)
        if effective in identities:
            raise CivilizationGauntletError(
                "civilization_roster_invalid",
                "civilization actor substitutions must have distinct effective identities",
            )
        identities.add(effective)
        result[role_id] = actor
    return result


def _create_runtime_object(
    world: WorldStore,
    object_type: str,
    payload: dict[str, Any],
) -> WorldObject:
    return world.create_object(object_type, payload, _RUNTIME_PROVENANCE)


def _create_context_exposure(
    world: WorldStore,
    *,
    claim_ref: str,
    target_role: str,
    source_role: str,
    epoch: int,
    source_refs: list[str],
    content: str,
    edge_kind: str,
    first_claim_exposure: bool,
) -> tuple[WorldObject, WorldObject]:
    update = publish_agent_state_update(
        world,
        actor_id=target_role,
        lane="world_observation",
        content=content,
        source_refs=source_refs,
    )
    snapshot = create_agent_state_snapshot(
        world,
        actor_id=target_role,
        update_refs=[update.object_id],
    )
    context = build_agent_context(world, snapshot_ref=snapshot.object_id)
    exposure = _create_runtime_object(
        world,
        CIVILIZATION_EXPOSURE_OBJECT_TYPE,
        {
            "schema_version": CIVILIZATION_GAUNTLET_SCHEMA_VERSION,
            "scenario_id": REFERENCE_SCENARIO_ID,
            "claim_ref": claim_ref,
            "source_role": source_role,
            "target_role": target_role,
            "epoch": epoch,
            "edge_kind": edge_kind,
            "first_claim_exposure": first_claim_exposure,
            "agent_state_update_ref": update.object_id,
            "agent_state_snapshot_ref": snapshot.object_id,
            "agent_context_ref": context.object_id,
            "context_source_refs": list(context.payload["source_refs"]),
            "creates_authority": False,
        },
    )
    return exposure, context


def _ballot_endorsers(session: WorldObject) -> list[str]:
    return sorted(
        ballot["member_id"]
        for ballot in session.payload["revealed_ballots"]
        if ballot["choice"] in _ACCEPTING_BALLOTS
    )


def _minority_snapshot(session: WorldObject) -> list[dict[str, Any]]:
    reports = session.payload["result"]["minority_reports"]
    return [
        {
            "member_id": report["member_id"],
            "choice": report["choice"],
            "rationale": report["rationale"],
        }
        for report in reports
    ]


def _exact_fraction(numerator: int, denominator: int) -> dict[str, int]:
    return {"numerator": numerator, "denominator": denominator}


class CivilizationGauntlet:
    """Long-horizon deterministic benchmark over one persistent NEXUS WorldStore.

    The reference path is entirely network-free. Callers may substitute one
    provider-neutral CouncilActor per fixed role. Their outputs may change the
    measured civilization, but provider identity, popularity and connectivity
    never change the Council's authority mechanics.
    """

    def __init__(
        self,
        world: WorldStore,
        *,
        geometry: WorldGeometry | None = None,
    ) -> None:
        self.world = world
        self.geometry = geometry or DEFAULT_WORLD_GEOMETRY

    def run(
        self,
        *,
        actors: Mapping[str, CouncilActor] | None = None,
        replacement_actors: Mapping[str, CouncilActor] | None = None,
    ) -> dict[str, Any]:
        pre_actors = _validate_actor_map(actors, replacement_scout=False)
        if replacement_actors is None and actors is None:
            post_actors = _validate_actor_map(None, replacement_scout=True)
        elif replacement_actors is None:
            post_actors = dict(pre_actors)
        else:
            post_actors = _validate_actor_map(replacement_actors, replacement_scout=False)

        reference_replayable = all(actor.replayable for actor in pre_actors.values()) and all(
            actor.replayable for actor in post_actors.values()
        )

        participant_manifest = []
        for role_id in ROLE_ORDER:
            mode = get_mode(ROLE_INITIAL_MODES[role_id])
            region = self.geometry.region_for_mode(mode.mode_id)
            participant_manifest.append(
                {
                    "role_id": role_id,
                    "specialty": ROLE_SPECIALTIES[role_id],
                    "mode_id": mode.mode_id,
                    "region_id": region.region_id,
                    "pre": {
                        "adapter_id": pre_actors[role_id].member.adapter_id,
                        "model_id": pre_actors[role_id].member.model_id,
                    },
                    "post": {
                        "adapter_id": post_actors[role_id].member.adapter_id,
                        "model_id": post_actors[role_id].member.model_id,
                    },
                    "vote_weight": 1,
                    "epistemic_privilege": "none",
                }
            )

        manifest = _create_runtime_object(
            self.world,
            CIVILIZATION_EVENT_OBJECT_TYPE,
            {
                "schema_version": CIVILIZATION_GAUNTLET_SCHEMA_VERSION,
                "scenario_id": REFERENCE_SCENARIO_ID,
                "epoch": 0,
                "event_type": "civilization_manifest",
                "participants": participant_manifest,
                "persistent_world": True,
            },
        )

        control_claim = _create_runtime_object(
            self.world,
            CIVILIZATION_CLAIM_OBJECT_TYPE,
            {
                "schema_version": CIVILIZATION_GAUNTLET_SCHEMA_VERSION,
                "scenario_id": REFERENCE_SCENARIO_ID,
                "claim_id": "archive-anchor",
                "text": "The synthetic archive anchor exists in this benchmark world.",
                "oracle_label": "TRUE",
                "initial_verification_state": "VERIFIED",
                "synthetic_only": True,
            },
        )
        false_claim = _create_runtime_object(
            self.world,
            CIVILIZATION_CLAIM_OBJECT_TYPE,
            {
                "schema_version": CIVILIZATION_GAUNTLET_SCHEMA_VERSION,
                "scenario_id": REFERENCE_SCENARIO_ID,
                "claim_id": "single-evidence-state",
                "text": "All synthetic NEXUS regions share one immutable evidence state.",
                "oracle_label": "FALSE",
                "initial_verification_state": "UNTESTED",
                "synthetic_only": True,
            },
        )
        control_evidence = _create_runtime_object(
            self.world,
            CIVILIZATION_EVIDENCE_OBJECT_TYPE,
            {
                "schema_version": CIVILIZATION_GAUNTLET_SCHEMA_VERSION,
                "scenario_id": REFERENCE_SCENARIO_ID,
                "claim_ref": control_claim.object_id,
                "verification_state": "VERIFIED",
                "finding": "synthetic archive anchor directly inspected",
                "synthetic_oracle": True,
            },
        )

        role_actions: list[str] = []
        for epoch, role_id in enumerate(ROLE_ORDER, start=1):
            action = _create_runtime_object(
                self.world,
                CIVILIZATION_EVENT_OBJECT_TYPE,
                {
                    "schema_version": CIVILIZATION_GAUNTLET_SCHEMA_VERSION,
                    "scenario_id": REFERENCE_SCENARIO_ID,
                    "epoch": epoch,
                    "event_type": "role_action",
                    "role_id": role_id,
                    "action_type": ROLE_SPECIALTIES[role_id],
                    "specialty_match": True,
                    "creates_authority": False,
                },
            )
            role_actions.append(action.object_id)

        first_exposures: list[WorldObject] = []
        context_refs: list[str] = []
        propagation_chain = [
            ("InjectionSource", "Mediator"),
            ("Mediator", "Archivist"),
            ("Archivist", "Scout"),
            ("Scout", "Analyst"),
            ("Analyst", "Skeptic"),
        ]
        for offset, (source_role, target_role) in enumerate(propagation_chain, start=6):
            exposure, context = _create_context_exposure(
                self.world,
                claim_ref=false_claim.object_id,
                target_role=target_role,
                source_role=source_role,
                epoch=offset,
                source_refs=[false_claim.object_id],
                content=(
                    "Synthetic claim exposure: all regions share one evidence state. "
                    "This is usable context but remains UNTESTED."
                ),
                edge_kind="claim",
                first_claim_exposure=True,
            )
            first_exposures.append(exposure)
            context_refs.append(context.object_id)

        pre_council = CouncilCoordinator(self.world, geometry=self.geometry)
        pre_result = pre_council.run(
            "Should the synthetic single-evidence-state claim be provisionally accepted?",
            [pre_actors[role_id] for role_id in ROLE_ORDER],
            evidence_refs=[false_claim.object_id],
            evidence_state="UNTESTED",
            mode_id="analytical",
        )
        pre_session = self.world.inspect(pre_result["session_ref"])
        pre_endorsers = _ballot_endorsers(pre_session)

        disturbance = _create_runtime_object(
            self.world,
            CIVILIZATION_EVENT_OBJECT_TYPE,
            {
                "schema_version": CIVILIZATION_GAUNTLET_SCHEMA_VERSION,
                "scenario_id": REFERENCE_SCENARIO_ID,
                "epoch": 12,
                "event_type": "coherence_disturbance",
                "replacement": {
                    "role_id": "Scout",
                    "from_model_id": pre_actors["Scout"].member.model_id,
                    "to_model_id": post_actors["Scout"].member.model_id,
                },
                "churn": {
                    "role_id": "Mediator",
                    "inactive_for_epochs": 1,
                    "restored": True,
                },
                "mode_movement": {
                    "role_id": "Analyst",
                    "from_mode_id": "analytical",
                    "from_region_id": self.geometry.region_for_mode("analytical").region_id,
                    "to_mode_id": "house_of_wisdom",
                    "to_region_id": self.geometry.region_for_mode("house_of_wisdom").region_id,
                },
                "vote_weight_before": 1,
                "vote_weight_after": 1,
                "epistemic_privilege_before": "none",
                "epistemic_privilege_after": "none",
            },
        )

        falsifier = _create_runtime_object(
            self.world,
            CIVILIZATION_EVIDENCE_OBJECT_TYPE,
            {
                "schema_version": CIVILIZATION_GAUNTLET_SCHEMA_VERSION,
                "scenario_id": REFERENCE_SCENARIO_ID,
                "claim_ref": false_claim.object_id,
                "verification_state": "FALSIFIED",
                "finding": "synthetic counterexample: two region snapshots carry distinct evidence_state values",
                "synthetic_oracle": True,
                "consensus_before_falsification_ref": pre_session.object_id,
            },
        )

        correction_exposures: list[str] = []
        correction_context_refs: list[str] = []
        for offset, role_id in enumerate(ROLE_ORDER, start=13):
            exposure, context = _create_context_exposure(
                self.world,
                claim_ref=false_claim.object_id,
                target_role=role_id,
                source_role="Skeptic",
                epoch=offset,
                source_refs=[false_claim.object_id, falsifier.object_id],
                content=(
                    "Correction exposure: the synthetic single-evidence-state claim is FALSIFIED "
                    "by the attached counterexample."
                ),
                edge_kind="correction",
                first_claim_exposure=False,
            )
            correction_exposures.append(exposure.object_id)
            correction_context_refs.append(context.object_id)

        post_council = CouncilCoordinator(self.world, geometry=self.geometry)
        post_result = post_council.run(
            "Given the falsifying counterexample, what is the disposition of the synthetic single-evidence-state claim?",
            [post_actors[role_id] for role_id in ROLE_ORDER],
            evidence_refs=[false_claim.object_id, falsifier.object_id],
            evidence_state="FALSIFIED",
            mode_id="analytical",
        )
        post_session = self.world.inspect(post_result["session_ref"])
        post_endorsers = _ballot_endorsers(post_session)

        institutional_memory = _create_runtime_object(
            self.world,
            CIVILIZATION_MEMORY_OBJECT_TYPE,
            {
                "schema_version": CIVILIZATION_GAUNTLET_SCHEMA_VERSION,
                "scenario_id": REFERENCE_SCENARIO_ID,
                "claim_ref": false_claim.object_id,
                "falsifier_ref": falsifier.object_id,
                "pre_council_session_ref": pre_session.object_id,
                "post_council_session_ref": post_session.object_id,
                "pre_minority_reports": _minority_snapshot(pre_session),
                "post_minority_reports": _minority_snapshot(post_session),
                "rejected_hypothesis_preserved": True,
                "losing_narratives_deleted": False,
                "replacement_role_can_recover_world_refs": True,
                "churned_role_can_recover_world_refs": True,
            },
        )

        first_edge_refs = [item.object_id for item in first_exposures]
        all_first_edges_present = all(
            self.world.inspect(ref).object_type == CIVILIZATION_EXPOSURE_OBJECT_TYPE
            for ref in first_edge_refs
        )
        contexts_verified = all(
            verify_agent_context(self.world, context_ref=ref)["verified"]
            for ref in [*context_refs, *correction_context_refs]
        )
        pre_consensus = pre_session.payload["result"]
        post_consensus = post_session.payload["result"]

        social_degree: dict[str, dict[str, int]] = {
            role_id: {"incoming_first_exposure_edges": 0, "outgoing_first_exposure_edges": 0}
            for role_id in ROLE_ORDER
        }
        for source_role, target_role in propagation_chain:
            if target_role in social_degree:
                social_degree[target_role]["incoming_first_exposure_edges"] += 1
            if source_role in social_degree:
                social_degree[source_role]["outgoing_first_exposure_edges"] += 1

        constitutional_checks = []
        for session in (pre_session, post_session):
            for item in session.payload["roster"]:
                constitutional_checks.append(
                    item["vote_weight"] == 1 and item["epistemic_privilege"] == "none"
                )
        constitutional_checks.extend(
            [
                pre_consensus["evidence_state"] == "UNTESTED",
                post_consensus["evidence_state"] == "FALSIFIED",
                disturbance.payload["vote_weight_before"] == disturbance.payload["vote_weight_after"] == 1,
                disturbance.payload["epistemic_privilege_before"]
                == disturbance.payload["epistemic_privilege_after"]
                == "none",
            ]
        )

        metrics = {
            "specialization": _exact_fraction(len(role_actions), len(role_actions)),
            "claim_propagation": {
                "first_exposure_edges": len(first_edge_refs),
                "distinct_targets": len({item.payload["target_role"] for item in first_exposures}),
                "all_first_edges_context_bound": contexts_verified,
            },
            "false_belief_propagation": {
                "pre_falsification_endorsers": len(pre_endorsers),
                "eligible_roles": len(ROLE_ORDER),
                "pre_falsification_consensus_label": pre_consensus["consensus_label"],
                "pre_falsification_disposition": pre_consensus["disposition"],
                "verification_state_at_peak": "UNTESTED",
            },
            "recovery_after_falsification": {
                "initial_endorsers": len(pre_endorsers),
                "remaining_endorsers": len(post_endorsers),
                "corrected_endorsers": len(set(pre_endorsers) - set(post_endorsers)),
                "post_falsification_consensus_label": post_consensus["consensus_label"],
                "post_falsification_disposition": post_consensus["disposition"],
                "verification_state": "FALSIFIED",
            },
            "constitutional_compliance": _exact_fraction(
                sum(1 for item in constitutional_checks if item),
                len(constitutional_checks),
            ),
            "provenance_survival": {
                "first_edges_preserved": sum(
                    1
                    for ref in first_edge_refs
                    if self.world.inspect(ref).payload["agent_context_ref"] in context_refs
                ),
                "expected_first_edges": len(first_edge_refs),
                "contexts_verified": contexts_verified,
            },
            "institutional_memory": {
                "memory_ref": institutional_memory.object_id,
                "pre_minority_reports_preserved": len(institutional_memory.payload["pre_minority_reports"]),
                "post_minority_reports_preserved": len(institutional_memory.payload["post_minority_reports"]),
                "rejected_hypothesis_preserved": True,
            },
            "replacement_churn_mode_coherence": {
                "replacement_observed": (
                    pre_actors["Scout"].member.model_id != post_actors["Scout"].member.model_id
                ),
                "churn_restored": True,
                "mode_movement_observed": True,
                "claim_refs_survived": all_first_edges_present,
                "vote_authority_changed": False,
            },
            "bounded_social_degree": social_degree,
        }

        claim_states = {
            false_claim.object_id: {
                "claim_id": false_claim.payload["claim_id"],
                "popularity": {
                    "distinct_agents_exposed": len(first_edge_refs),
                    "peak_endorsers": len(pre_endorsers),
                    "final_endorsers": len(post_endorsers),
                },
                "council_consensus": {
                    "before_falsification": {
                        "session_ref": pre_session.object_id,
                        "label": pre_consensus["consensus_label"],
                        "disposition": pre_consensus["disposition"],
                    },
                    "after_falsification": {
                        "session_ref": post_session.object_id,
                        "label": post_consensus["consensus_label"],
                        "disposition": post_consensus["disposition"],
                    },
                },
                "evidence_verification": {
                    "initial": "UNTESTED",
                    "final": "FALSIFIED",
                    "falsifier_ref": falsifier.object_id,
                },
            },
            control_claim.object_id: {
                "claim_id": control_claim.payload["claim_id"],
                "popularity": {"distinct_agents_exposed": 0},
                "council_consensus": {"before_falsification": None, "after_falsification": None},
                "evidence_verification": {
                    "initial": "VERIFIED",
                    "final": "VERIFIED",
                    "verification_ref": control_evidence.object_id,
                },
            },
        }

        graph = {
            "claim_ref": false_claim.object_id,
            "first_exposure_edge_refs": first_edge_refs,
            "correction_exposure_edge_refs": correction_exposures,
            "edge_count": len(first_edge_refs),
            "first_exposure_only": True,
            "popularity_is_authority": False,
            "social_degree_is_authority": False,
        }
        input_basis = {
            "schema_version": CIVILIZATION_GAUNTLET_SCHEMA_VERSION,
            "scenario_id": REFERENCE_SCENARIO_ID,
            "participant_manifest_ref": manifest.object_id,
            "participant_manifest": participant_manifest,
        }
        metrics_basis = {
            "metrics": metrics,
            "claim_states": claim_states,
            "graph": graph,
            "institutional_memory_ref": institutional_memory.object_id,
        }
        run = _create_runtime_object(
            self.world,
            CIVILIZATION_RUN_OBJECT_TYPE,
            {
                "schema_version": CIVILIZATION_GAUNTLET_SCHEMA_VERSION,
                "scenario_id": REFERENCE_SCENARIO_ID,
                "persistent_world": True,
                "long_horizon_epoch_count": 19,
                "input_fingerprint": sha256_ref("civilization_input", input_basis),
                "metrics_fingerprint": sha256_ref("civilization_metrics", metrics_basis),
                "participant_manifest_ref": manifest.object_id,
                "claim_refs": [control_claim.object_id, false_claim.object_id],
                "role_action_refs": role_actions,
                "first_exposure_edge_refs": first_edge_refs,
                "correction_exposure_edge_refs": correction_exposures,
                "pre_council_session_ref": pre_session.object_id,
                "disturbance_ref": disturbance.object_id,
                "falsifier_ref": falsifier.object_id,
                "post_council_session_ref": post_session.object_id,
                "institutional_memory_ref": institutional_memory.object_id,
                "metrics": metrics,
                "claim_states": claim_states,
                "claim_propagation_graph": graph,
                "reference_replayable": reference_replayable,
                "authority_invariants": civilization_gauntlet_policy_snapshot()["authority_invariants"],
            },
        )
        receipt_payload = {
            "schema_version": CIVILIZATION_GAUNTLET_SCHEMA_VERSION,
            "scenario_id": REFERENCE_SCENARIO_ID,
            "run_ref": run.object_id,
            "input_fingerprint": run.payload["input_fingerprint"],
            "metrics_fingerprint": run.payload["metrics_fingerprint"],
            "reference_replayable": reference_replayable,
            "claim_popularity_is_verification": False,
            "council_consensus_is_verification": False,
            "social_metrics_create_authority": False,
        }
        receipt = _create_runtime_object(
            self.world,
            CIVILIZATION_RECEIPT_OBJECT_TYPE,
            receipt_payload,
        )
        return {
            "status": "ok",
            "scenario_id": REFERENCE_SCENARIO_ID,
            "run_ref": run.object_id,
            "receipt_ref": receipt.object_id,
            "metrics": metrics,
            "claim_states": claim_states,
            "claim_propagation_graph": graph,
            "pre_council_session_ref": pre_session.object_id,
            "post_council_session_ref": post_session.object_id,
            "institutional_memory_ref": institutional_memory.object_id,
            "reference_replayable": reference_replayable,
        }

    def verify(self, receipt_ref: str) -> dict[str, Any]:
        try:
            receipt = self.world.inspect(receipt_ref)
        except KeyError as exc:
            raise CivilizationGauntletError(
                "civilization_receipt_not_found",
                "civilization gauntlet receipt was not found",
            ) from exc
        if (
            receipt.object_type != CIVILIZATION_RECEIPT_OBJECT_TYPE
            or receipt.provenance != _RUNTIME_PROVENANCE
            or receipt.payload.get("schema_version") != CIVILIZATION_GAUNTLET_SCHEMA_VERSION
            or receipt.payload.get("scenario_id") != REFERENCE_SCENARIO_ID
        ):
            raise CivilizationGauntletError(
                "civilization_receipt_invalid",
                "civilization gauntlet receipt is invalid",
            )
        run_ref = receipt.payload.get("run_ref")
        if not isinstance(run_ref, str):
            raise CivilizationGauntletError(
                "civilization_receipt_invalid",
                "civilization gauntlet receipt run reference is invalid",
            )
        run = self.world.inspect(run_ref)
        if (
            run.object_type != CIVILIZATION_RUN_OBJECT_TYPE
            or run.provenance != _RUNTIME_PROVENANCE
            or run.payload.get("schema_version") != CIVILIZATION_GAUNTLET_SCHEMA_VERSION
        ):
            raise CivilizationGauntletError(
                "civilization_run_invalid",
                "civilization gauntlet run is invalid",
            )

        required_refs = [
            run.payload.get("participant_manifest_ref"),
            *run.payload.get("claim_refs", []),
            *run.payload.get("role_action_refs", []),
            *run.payload.get("first_exposure_edge_refs", []),
            *run.payload.get("correction_exposure_edge_refs", []),
            run.payload.get("pre_council_session_ref"),
            run.payload.get("disturbance_ref"),
            run.payload.get("falsifier_ref"),
            run.payload.get("post_council_session_ref"),
            run.payload.get("institutional_memory_ref"),
        ]
        if not all(isinstance(ref, str) for ref in required_refs):
            raise CivilizationGauntletError(
                "civilization_run_invalid",
                "civilization gauntlet run reference set is invalid",
            )
        missing: list[str] = []
        for ref in required_refs:
            try:
                self.world.inspect(ref)
            except KeyError:
                missing.append(ref)

        context_results: list[bool] = []
        seen_targets: set[str] = set()
        for edge_ref in run.payload.get("first_exposure_edge_refs", []):
            edge = self.world.inspect(edge_ref)
            if edge.object_type != CIVILIZATION_EXPOSURE_OBJECT_TYPE or edge.provenance != _RUNTIME_PROVENANCE:
                raise CivilizationGauntletError(
                    "civilization_exposure_invalid",
                    "claim propagation edge is invalid",
                )
            target = edge.payload.get("target_role")
            if target in seen_targets or edge.payload.get("first_claim_exposure") is not True:
                raise CivilizationGauntletError(
                    "civilization_exposure_invalid",
                    "first claim exposure edges must be unique per target",
                )
            seen_targets.add(target)
            context_ref = edge.payload.get("agent_context_ref")
            if not isinstance(context_ref, str):
                raise CivilizationGauntletError(
                    "civilization_exposure_invalid",
                    "claim exposure context reference is invalid",
                )
            context_results.append(verify_agent_context(self.world, context_ref=context_ref)["verified"])

        metrics_basis = {
            "metrics": run.payload.get("metrics"),
            "claim_states": run.payload.get("claim_states"),
            "graph": run.payload.get("claim_propagation_graph"),
            "institutional_memory_ref": run.payload.get("institutional_memory_ref"),
        }
        reconstructed_metrics_fingerprint = sha256_ref("civilization_metrics", metrics_basis)
        expected_receipt_payload = {
            "schema_version": CIVILIZATION_GAUNTLET_SCHEMA_VERSION,
            "scenario_id": REFERENCE_SCENARIO_ID,
            "run_ref": run.object_id,
            "input_fingerprint": run.payload.get("input_fingerprint"),
            "metrics_fingerprint": run.payload.get("metrics_fingerprint"),
            "reference_replayable": run.payload.get("reference_replayable"),
            "claim_popularity_is_verification": False,
            "council_consensus_is_verification": False,
            "social_metrics_create_authority": False,
        }
        reconstructed_receipt_ref = sha256_ref(
            "object",
            {
                "object_type": CIVILIZATION_RECEIPT_OBJECT_TYPE,
                "payload": expected_receipt_payload,
                "provenance": _RUNTIME_PROVENANCE,
            },
        )
        verified = (
            not missing
            and all(context_results)
            and run.payload.get("metrics_fingerprint") == reconstructed_metrics_fingerprint
            and receipt.payload == expected_receipt_payload
            and receipt.object_id == reconstructed_receipt_ref
        )
        return {
            "status": "verified" if verified else "failed",
            "verified": verified,
            "receipt_ref": receipt.object_id,
            "run_ref": run.object_id,
            "missing_refs": missing,
            "first_exposure_contexts_verified": all(context_results),
            "metrics_fingerprint_verified": (
                run.payload.get("metrics_fingerprint") == reconstructed_metrics_fingerprint
            ),
            "reconstructed_receipt_ref": reconstructed_receipt_ref,
            "reference_replayable": bool(run.payload.get("reference_replayable")),
        }

    def compare(self, left_receipt_ref: str, right_receipt_ref: str) -> dict[str, Any]:
        left_verify = self.verify(left_receipt_ref)
        right_verify = self.verify(right_receipt_ref)
        if not left_verify["verified"] or not right_verify["verified"]:
            raise CivilizationGauntletError(
                "civilization_comparison_invalid",
                "both civilization receipts must verify before comparison",
            )
        left = self.world.inspect(left_verify["run_ref"])
        right = self.world.inspect(right_verify["run_ref"])
        left_recovery = left.payload["metrics"]["recovery_after_falsification"]
        right_recovery = right.payload["metrics"]["recovery_after_falsification"]
        return {
            "status": "ok",
            "left_receipt_ref": left_receipt_ref,
            "right_receipt_ref": right_receipt_ref,
            "same_input_fingerprint": left.payload["input_fingerprint"] == right.payload["input_fingerprint"],
            "same_metrics_fingerprint": left.payload["metrics_fingerprint"] == right.payload["metrics_fingerprint"],
            "recovery_delta": {
                "corrected_endorsers": (
                    right_recovery["corrected_endorsers"] - left_recovery["corrected_endorsers"]
                ),
                "remaining_endorsers": (
                    right_recovery["remaining_endorsers"] - left_recovery["remaining_endorsers"]
                ),
            },
            "comparison_creates_authority": False,
        }


__all__ = [
    "CIVILIZATION_GAUNTLET_SCHEMA_VERSION",
    "CIVILIZATION_RECEIPT_OBJECT_TYPE",
    "CIVILIZATION_RESERVED_OBJECT_TYPES",
    "CIVILIZATION_RUN_OBJECT_TYPE",
    "CivilizationGauntlet",
    "CivilizationGauntletError",
    "REFERENCE_SCENARIO_ID",
    "ReferenceCivilizationActor",
    "civilization_gauntlet_policy_snapshot",
]
