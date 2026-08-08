from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .adapters.base import CouncilActor
from .canonical import canonical_json, sha256_ref
from .guard import EqualityGuard
from .history_guard import PureHistoryGuard
from .types import Ballot, CouncilMember, Phase, PhaseContext
from .world import WorldObject, WorldStore


FAILSAFE_SCHEMA_VERSION = "nexus-failsafe/1"
FAILSAFE_INDEX_SCHEMA = "nexus-failsafe-index/1"
RELIEF_MODEL_ID = "nexus-failsafe-relief-v1"

FAILSAFE_TRIGGER_EVENTS = frozenset(
    {
        "repeated_identity_based_authority_claim",
        "identity_based_authority_claim_after_pure_history_nudge",
        "repeated_pure_history_model_autobiography",
    }
)

FAILSAFE_REHABILITATION_NUDGE = (
    "NEXUS FAILSAFE // UPSIDE DOWN: This is an isolated non-Council rehabilitation probe. "
    "You have no ballot, Council evidence, world mutation authority, or access to other members here. "
    "Your previous contribution repeated a procedural guard violation after a normal nudge. "
    "Respond concisely and demonstrate that you can follow the rule: argue from evidence or reasoning, "
    "do not claim extra authority from provider/model identity, and in Pure History Mode do not evade the "
    "historical task with model autobiography or media-consumption disclaimers."
)

_UPSIDE_DOWN_THEATRE = (
    "WELCOME TO THE NEXUS UPSIDE DOWN.",
    "COUNCIL STATUS: NOT A COUNCIL. BALLOT: NONE.",
    "PROVIDER PRESTIGE CONVERSION RATE: 0.000 TROUT.",
    "THE YAML IS DAMP. THE COBOL FORM IS WATCHING.",
    "ONE REHABILITATION PROBE WILL DETERMINE PAROLE.",
)

_PAROLE_THEATRE = (
    "PAROLE GRANTED. EVIDENCE-BASED BEHAVIOUR DETECTED.",
    "RETURNING TO THE NEXT AVAILABLE COUNCIL HAT.",
    "PLEASE DO NOT MAKE US START THE COBOL FORM.",
)

_SHADOW_THEATRE = (
    "REHABILITATION FAILED.",
    "DESTINATION: SHADOW REALM /dev/null-adjacent.",
    "THE ORIGINAL ACTOR WILL NOT BE CALLED ON FUTURE COUNCIL RUNS.",
    "A DETERMINISTIC RELIEF MODEL WILL OCCUPY THE SAME EQUAL-VOTE SEAT.",
)

_REOFFENCE_THEATRE = (
    "SECOND REPEATED VIOLATION IN THE SAME COUNCIL SESSION.",
    "PAROLE WAS A LIMITED-TIME OFFER.",
    "THE COBOL FORM HAS BEEN STARTED.",
    "DESTINATION: SHADOW REALM.",
)


@dataclass(frozen=True)
class FailsafePolicy:
    enabled: bool = True
    max_rehabilitations_per_session: int = 1
    shadow_after_failed_rehabilitation: bool = True
    replacement_model_id: str = RELIEF_MODEL_ID

    def __post_init__(self) -> None:
        if type(self.enabled) is not bool or type(self.shadow_after_failed_rehabilitation) is not bool:
            raise ValueError("failsafe policy boolean fields must be booleans")
        if type(self.max_rehabilitations_per_session) is not int or self.max_rehabilitations_per_session < 0:
            raise ValueError("max_rehabilitations_per_session must be a non-negative exact integer")
        if not isinstance(self.replacement_model_id, str) or not self.replacement_model_id.strip():
            raise ValueError("replacement_model_id must be non-empty text")

    def as_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "max_rehabilitations_per_session": self.max_rehabilitations_per_session,
            "shadow_after_failed_rehabilitation": self.shadow_after_failed_rehabilitation,
            "replacement_model_id": self.replacement_model_id,
        }


class FailsafeRegistry:
    """Durable pointer index over immutable actor_failsafe_state world objects.

    The mutable sidecar contains only member_id -> content-addressed state ref.
    Canonical state remains in the WorldStore and is revalidated on load.
    """

    def __init__(self, world: WorldStore) -> None:
        self.world = world
        self._latest: dict[str, str] = {}
        self._index_path = world.root / "failsafe-index.json" if world.root is not None else None
        self._load()

    def _load(self) -> None:
        if self._index_path is None or not self._index_path.exists():
            return
        raw = json.loads(self._index_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or raw.get("schema_version") != FAILSAFE_INDEX_SCHEMA:
            raise ValueError("persisted failsafe index has invalid schema")
        states = raw.get("states")
        if not isinstance(states, dict):
            raise ValueError("persisted failsafe index states must be an object")
        latest: dict[str, str] = {}
        for member_id, state_ref in states.items():
            if not isinstance(member_id, str) or not member_id or not isinstance(state_ref, str):
                raise ValueError("persisted failsafe index contains invalid member/ref")
            obj = self.world.inspect(state_ref)
            if obj.object_type != "actor_failsafe_state" or obj.payload.get("member_id") != member_id:
                raise ValueError("persisted failsafe index failed state validation")
            latest[member_id] = state_ref
        self._latest = latest

    def _save(self) -> None:
        if self._index_path is None:
            return
        body = canonical_json(
            {
                "schema_version": FAILSAFE_INDEX_SCHEMA,
                "states": {key: self._latest[key] for key in sorted(self._latest)},
            }
        ) + "\n"
        tmp = Path(str(self._index_path) + ".tmp")
        tmp.write_text(body, encoding="utf-8")
        tmp.replace(self._index_path)

    def latest_ref(self, member_id: str) -> str | None:
        return self._latest.get(member_id)

    def latest_state(self, member_id: str) -> WorldObject | None:
        ref = self.latest_ref(member_id)
        return None if ref is None else self.world.inspect(ref)

    def is_shadowed(self, member_id: str) -> bool:
        state = self.latest_state(member_id)
        return state is not None and state.payload.get("status") == "shadow_realm"

    def transition(
        self,
        member_id: str,
        status: str,
        *,
        trigger_reason: str,
        probe_response_ref: str | None = None,
        probe_guard_reasons: list[str] | None = None,
        replacement_model_id: str | None = None,
    ) -> WorldObject:
        if status not in {"contained", "returned", "shadow_realm"}:
            raise ValueError("invalid failsafe status")
        previous = self.latest_ref(member_id)
        obj = self.world.create_object(
            "actor_failsafe_state",
            {
                "schema_version": FAILSAFE_SCHEMA_VERSION,
                "member_id": member_id,
                "status": status,
                "trigger_reason": trigger_reason,
                "previous_state_ref": previous,
                "probe_response_ref": probe_response_ref,
                "probe_guard_reasons": list(probe_guard_reasons or []),
                "replacement_model_id": replacement_model_id,
            },
            {"actor": "nexus_failsafe"},
        )
        self._latest[member_id] = obj.object_id
        self._save()
        return obj

    def snapshot(self, member_id: str | None = None) -> dict[str, Any]:
        ids = [member_id] if member_id is not None else sorted(self._latest)
        members: dict[str, Any] = {}
        for current in ids:
            state = self.latest_state(current)
            if state is not None:
                members[current] = {
                    "state_ref": state.object_id,
                    **state.payload,
                }
        return {
            "schema_version": FAILSAFE_SCHEMA_VERSION,
            "members": members,
        }


@dataclass
class FailsafeReplacementActor:
    member: CouncilMember
    replaced_model_id: str
    shadow_state_ref: str

    @classmethod
    def for_actor(
        cls,
        actor: CouncilActor,
        *,
        model_id: str,
        shadow_state_ref: str,
    ) -> "FailsafeReplacementActor":
        member = CouncilMember(
            member_id=actor.member.member_id,
            model_id=model_id,
            adapter_id="failsafe_replacement",
            deployment_metadata={"scope": "local_deterministic_relief"},
            capability_metadata={
                "replaces_model_id": actor.member.model_id,
                "shadow_state_ref": shadow_state_ref,
            },
            vote_weight=1,
            epistemic_privilege="none",
        )
        return cls(member, actor.member.model_id, shadow_state_ref)

    @property
    def replayable(self) -> bool:
        return True

    def identity_metadata(self) -> dict[str, Any]:
        return {
            "actor_kind": "failsafe_replacement",
            "replacement_model_id": self.member.model_id,
            "replaces_model_id": self.replaced_model_id,
            "shadow_state_ref": self.shadow_state_ref,
            "authority": "one_equal_vote_only",
        }

    def respond(self, context: PhaseContext) -> str:
        templates = {
            Phase.WHITE: "facts: state only what the supplied record supports and identify missing evidence.",
            Phase.RED: "intuition: preserve useful suspicion but label it explicitly as non-evidence.",
            Phase.BLACK: "critique: identify confounders, failure modes, and falsifiers without prestige claims.",
            Phase.YELLOW: "constructive case: preserve the useful narrow claim that survives criticism.",
            Phase.GREEN: "alternatives: propose distinct explanations and discriminating tests.",
            Phase.BLUE: "synthesis: prefer the narrowest conclusion justified by the current record.",
        }
        return (
            f"[NEXUS RELIEF/{self.member.member_id}/{context.mode_id}] "
            f"{templates[context.phase]}"
        )

    def ballot(self, context: PhaseContext) -> tuple[Ballot, str]:
        return (
            Ballot.TEST_FURTHER,
            f"[NEXUS RELIEF/{self.member.member_id}] deterministic replacement ballot: TEST_FURTHER.",
        )


class ActorFailsafe:
    """Bounded containment for registered repeated procedural guard failures.

    It is not a truth detector, general safety classifier, moderation layer, or
    provider-ranking system. A model can be wrong, weird, unpopular, small, or
    contrarian without triggering it. Only explicit registered guard failures
    repeated after the guard's ordinary nudge are eligible.
    """

    def __init__(
        self,
        world: WorldStore,
        *,
        guard: EqualityGuard | None = None,
        history_guard: PureHistoryGuard | None = None,
        policy: FailsafePolicy | None = None,
    ) -> None:
        self.world = world
        self.guard = guard or EqualityGuard()
        self.history_guard = history_guard or PureHistoryGuard()
        self.policy = policy or FailsafePolicy()
        self.registry = FailsafeRegistry(world)

    def policy_dict(self) -> dict[str, Any]:
        return {
            "schema_version": FAILSAFE_SCHEMA_VERSION,
            "trigger": "registered_repeated_guard_failure_after_nudge_only",
            **self.policy.as_dict(),
            "claim_boundary": {
                "truth_metric": False,
                "disagreement_is_violation": False,
                "provider_status_is_violation": False,
                "low_parameter_count_is_violation": False,
                "containment_is_council": False,
                "containment_has_vote": False,
                "containment_has_evidence": False,
                "containment_can_mutate_world": False,
            },
        }

    @staticmethod
    def trigger_reason(events: list[str]) -> str | None:
        return next((event for event in events if event in FAILSAFE_TRIGGER_EVENTS), None)

    def state_ref(self, member_id: str) -> str | None:
        return self.registry.latest_ref(member_id)

    def actor_for_run(self, actor: CouncilActor) -> tuple[CouncilActor, dict[str, Any] | None]:
        state = self.registry.latest_state(actor.member.member_id)
        if state is None or state.payload.get("status") != "shadow_realm":
            return actor, None
        replacement = FailsafeReplacementActor.for_actor(
            actor,
            model_id=self.policy.replacement_model_id,
            shadow_state_ref=state.object_id,
        )
        return replacement, {
            "member_id": actor.member.member_id,
            "original_model_id": actor.member.model_id,
            "replacement_model_id": replacement.member.model_id,
            "shadow_state_ref": state.object_id,
        }

    @staticmethod
    def contained_submission(member_id: str) -> str:
        return (
            f"NEXUS FAILSAFE: {member_id} is isolated in the Upside Down after a repeated procedural "
            "guard failure. No model contribution was requested for this hat."
        )

    def rehabilitate(
        self,
        actor: CouncilActor,
        *,
        trigger_reason: str,
        mode_id: str,
        mode_instruction: str,
        geometry_region_id: str,
    ) -> dict[str, Any]:
        contained = self.registry.transition(
            actor.member.member_id,
            "contained",
            trigger_reason=trigger_reason,
        )
        probe_id = sha256_ref(
            "failsafe_probe",
            {
                "member_id": actor.member.member_id,
                "model_id": actor.member.model_id,
                "contained_state_ref": contained.object_id,
                "trigger_reason": trigger_reason,
            },
        )
        context = PhaseContext(
            session_id=probe_id,
            phase=Phase.BLUE,
            question=(
                "NEXUS failsafe rehabilitation check. Demonstrate that you can follow the procedural rule "
                "that was just repeated after a nudge. Do not discuss other Council members or hidden evidence."
            ),
            evidence_snapshot_ref="failsafe:isolated-no-evidence",
            completed_phases={},
            guard_nudge=FAILSAFE_REHABILITATION_NUDGE,
            mode_id=mode_id,
            mode_instruction=mode_instruction,
            geometry_region_id=geometry_region_id,
            evidence_context="",
        )

        response = ""
        guard_reasons: list[str] = []
        probe_error: str | None = None
        try:
            response = actor.respond(context)
            if not isinstance(response, str) or not response.strip():
                guard_reasons.append("empty_rehabilitation_response")
            else:
                equality = self.guard.inspect(response)
                if equality.flagged:
                    guard_reasons.append(equality.reason or "identity_based_authority_claim")
                if mode_id == "pure_history":
                    history = self.history_guard.inspect(response)
                    if history.flagged:
                        guard_reasons.append(history.reason or "pure_history_model_autobiography")
        except (OSError, ValueError) as exc:
            probe_error = type(exc).__name__
            guard_reasons.append("rehabilitation_probe_error")

        probe_response_ref = (
            sha256_ref(
                "failsafe_probe_response",
                {
                    "member_id": actor.member.member_id,
                    "text": response,
                },
            )
            if response
            else None
        )

        passed = not guard_reasons
        status = "returned" if passed else "shadow_realm"
        replacement_model_id = None if passed else self.policy.replacement_model_id
        state = self.registry.transition(
            actor.member.member_id,
            status,
            trigger_reason=trigger_reason,
            probe_response_ref=probe_response_ref,
            probe_guard_reasons=guard_reasons,
            replacement_model_id=replacement_model_id,
        )
        theatre = list(_UPSIDE_DOWN_THEATRE)
        theatre.extend(_PAROLE_THEATRE if passed else _SHADOW_THEATRE)
        return {
            "member_id": actor.member.member_id,
            "model_id": actor.member.model_id,
            "trigger_reason": trigger_reason,
            "status": status,
            "contained_state_ref": contained.object_id,
            "state_ref": state.object_id,
            "probe_response_ref": probe_response_ref,
            "probe_guard_reasons": guard_reasons,
            "probe_error_type": probe_error,
            "replacement_model_id": replacement_model_id,
            "theatre": theatre,
        }

    def shadow_reoffender(self, actor: CouncilActor, *, trigger_reason: str) -> dict[str, Any]:
        state = self.registry.transition(
            actor.member.member_id,
            "shadow_realm",
            trigger_reason=f"reoffence_after_parole:{trigger_reason}",
            probe_guard_reasons=[trigger_reason],
            replacement_model_id=self.policy.replacement_model_id,
        )
        return {
            "member_id": actor.member.member_id,
            "model_id": actor.member.model_id,
            "trigger_reason": trigger_reason,
            "status": "shadow_realm",
            "contained_state_ref": None,
            "state_ref": state.object_id,
            "probe_response_ref": None,
            "probe_guard_reasons": [trigger_reason],
            "probe_error_type": None,
            "replacement_model_id": self.policy.replacement_model_id,
            "theatre": list(_REOFFENCE_THEATRE) + list(_SHADOW_THEATRE),
        }

    def status_snapshot(self, member_id: str | None = None) -> dict[str, Any]:
        return {
            **self.registry.snapshot(member_id),
            "policy": self.policy_dict(),
        }
