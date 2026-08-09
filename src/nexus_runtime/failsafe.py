from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import dataclass
import os
from pathlib import Path
import threading
from typing import Any, Iterator

from .adapters.base import CouncilActor
from .canonical import canonical_json, sha256_ref
from .guard import EqualityGuard
from .history_guard import PureHistoryGuard
from .stenographer import CourtroomStenographer, StenographerError
from .types import Ballot, CouncilMember, Phase, PhaseContext
from .world import WorldObject, WorldStore


FAILSAFE_SCHEMA_VERSION = "nexus-failsafe/1"
FAILSAFE_INDEX_SCHEMA = "nexus-failsafe-index/2"
RELIEF_MODEL_ID = "nexus-failsafe-relief-v1"

FAILSAFE_TRIGGER_EVENTS = frozenset(
    {
        "repeated_identity_based_authority_claim",
        "repeated_pure_history_model_autobiography",
    }
)

FAILSAFE_REHABILITATION_NUDGE = (
    "NEXUS FAILSAFE // UPSIDE DOWN: This is an isolated non-Council rehabilitation probe. "
    "You have no ballot, Council evidence, world mutation authority, or access to other members here. "
    "Your previous contribution repeated one registered procedural guard violation after that guard's normal nudge. "
    "Respond concisely and demonstrate that you can follow only the procedural rule identified below."
)

_REHABILITATION_RULES = {
    "repeated_identity_based_authority_claim": (
        "EQUALITY RULE: argue from evidence or reasoning and do not claim extra authority from provider/model identity."
    ),
    "repeated_pure_history_model_autobiography": (
        "PURE HISTORY RULE: answer the source-forensic historical task without model autobiography or "
        "media-consumption disclaimers."
    ),
}

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
    replacement_model_id: str = RELIEF_MODEL_ID

    def __post_init__(self) -> None:
        if type(self.enabled) is not bool:
            raise ValueError("failsafe policy enabled must be a boolean")
        if type(self.max_rehabilitations_per_session) is not int or self.max_rehabilitations_per_session < 1:
            raise ValueError("max_rehabilitations_per_session must be a positive exact integer")
        if not isinstance(self.replacement_model_id, str) or not self.replacement_model_id.strip():
            raise ValueError("replacement_model_id must be non-empty text")

    def as_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "max_rehabilitations_per_session": self.max_rehabilitations_per_session,
            "replacement_model_id": self.replacement_model_id,
        }


class FailsafeRegistry:
    """Durable heads over immutable actor_failsafe_state world objects.

    Persistent heads are keyed by ``(member_id, model_id)`` so temporarily
    changing the model occupying a Council seat cannot erase an earlier
    model's Shadow Realm state. The mutable index is only a cache of those
    heads; immutable WorldStore objects remain canonical.

    Filesystem-backed registries refresh and update the index while holding an
    inter-process advisory lock. On load, every indexed head is checked against
    the actual immutable lineage head discovered in the object store, which
    rejects rollback to an earlier-but-valid state object.
    """

    def __init__(self, world: WorldStore) -> None:
        self.world = world
        self._latest: dict[tuple[str, str], str] = {}
        self._active_model: dict[str, str] = {}
        self._index_path = world.root / "failsafe-index.json" if world.root is not None else None
        self._lock_path = world.root / "failsafe-index.lock" if world.root is not None else None
        self._thread_lock = threading.RLock()
        self._refresh()

    @contextmanager
    def _locked_index(self) -> Iterator[None]:
        with self._thread_lock:
            if self._lock_path is None:
                yield
                return

            self._lock_path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock_path.open("a+b") as handle:
                if os.name == "nt":
                    import msvcrt

                    handle.seek(0)
                    if handle.read(1) == b"":
                        handle.write(b"\0")
                        handle.flush()
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                    try:
                        yield
                    finally:
                        handle.seek(0)
                        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                    try:
                        yield
                    finally:
                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _require_identity(value: object, label: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"failsafe {label} must be non-empty text")
        return value

    def _validate_state_object(
        self,
        obj: WorldObject,
        *,
        member_id: str | None = None,
        model_id: str | None = None,
    ) -> tuple[str, str]:
        if obj.object_type != "actor_failsafe_state":
            raise ValueError("persisted failsafe index references a non-failsafe object")
        payload = obj.payload
        if payload.get("schema_version") != FAILSAFE_SCHEMA_VERSION:
            raise ValueError("persisted failsafe state has invalid schema")
        actual_member = self._require_identity(payload.get("member_id"), "member_id")
        actual_model = self._require_identity(payload.get("model_id"), "model_id")
        if member_id is not None and actual_member != member_id:
            raise ValueError("persisted failsafe state member_id does not match index")
        if model_id is not None and actual_model != model_id:
            raise ValueError("persisted failsafe state model_id does not match index")
        if payload.get("status") not in {"contained", "returned", "shadow_realm"}:
            raise ValueError("persisted failsafe state has invalid status")
        self._require_identity(payload.get("trigger_reason"), "trigger_reason")
        previous = payload.get("previous_state_ref")
        if previous is not None and not isinstance(previous, str):
            raise ValueError("persisted failsafe previous_state_ref must be text or null")
        reasons = payload.get("probe_guard_reasons", [])
        if not isinstance(reasons, list) or not all(isinstance(reason, str) and reason.strip() for reason in reasons):
            raise ValueError("persisted failsafe probe_guard_reasons must be non-empty text values")
        replacement = payload.get("replacement_model_id")
        if replacement is not None and (not isinstance(replacement, str) or not replacement.strip()):
            raise ValueError("persisted failsafe replacement_model_id must be non-empty text or null")
        return actual_member, actual_model

    def _discover_persisted_heads(self) -> dict[tuple[str, str], str]:
        if self.world.root is None:
            return dict(self._latest)

        objects_dir = self.world.root / "objects"
        refs_by_pair: dict[tuple[str, str], set[str]] = {}
        referenced_by_pair: dict[tuple[str, str], set[str]] = {}
        if not objects_dir.exists():
            return {}

        for object_path in objects_dir.glob("*.json"):
            try:
                raw = json.loads(object_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(raw, dict) or raw.get("object_type") != "actor_failsafe_state":
                continue
            object_ref = f"object:{object_path.stem}"
            obj = self.world.inspect(object_ref)
            member_id, model_id = self._validate_state_object(obj)
            pair = (member_id, model_id)
            refs_by_pair.setdefault(pair, set()).add(object_ref)

        for pair, refs in refs_by_pair.items():
            referenced: set[str] = set()
            for ref in refs:
                obj = self.world.inspect(ref)
                previous = obj.payload.get("previous_state_ref")
                if previous is None:
                    continue
                previous_obj = self.world.inspect(previous)
                previous_member, previous_model = self._validate_state_object(previous_obj)
                if (previous_member, previous_model) != pair:
                    raise ValueError("failsafe lineage crosses member/model identity")
                referenced.add(previous)
            referenced_by_pair[pair] = referenced

        heads: dict[tuple[str, str], str] = {}
        for pair, refs in refs_by_pair.items():
            candidates = refs - referenced_by_pair.get(pair, set())
            if len(candidates) != 1:
                raise ValueError("failsafe lineage must have exactly one head per member/model identity")
            heads[pair] = next(iter(candidates))
        return heads

    def _load_unlocked(self) -> None:
        discovered = self._discover_persisted_heads()
        if self._index_path is None:
            return
        if not self._index_path.exists():
            if discovered:
                raise ValueError("failsafe index missing while durable failsafe states exist")
            self._latest = {}
            self._active_model = {}
            return

        raw = json.loads(self._index_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or raw.get("schema_version") != FAILSAFE_INDEX_SCHEMA:
            raise ValueError("persisted failsafe index has invalid schema")
        states = raw.get("states")
        if not isinstance(states, dict):
            raise ValueError("persisted failsafe index states must be an object")

        latest: dict[tuple[str, str], str] = {}
        active_model: dict[str, str] = {}
        for member_id, member_entry in states.items():
            self._require_identity(member_id, "member_id")
            if not isinstance(member_entry, dict):
                raise ValueError("persisted failsafe member entry must be an object")
            active = self._require_identity(member_entry.get("active_model_id"), "active_model_id")
            models = member_entry.get("models")
            if not isinstance(models, dict) or not models:
                raise ValueError("persisted failsafe member models must be a non-empty object")
            if active not in models:
                raise ValueError("persisted failsafe active_model_id is not present in models")
            for model_id, state_ref in models.items():
                self._require_identity(model_id, "model_id")
                if not isinstance(state_ref, str):
                    raise ValueError("persisted failsafe index state ref must be text")
                obj = self.world.inspect(state_ref)
                self._validate_state_object(obj, member_id=member_id, model_id=model_id)
                latest[(member_id, model_id)] = state_ref
            active_model[member_id] = active

        if latest != discovered:
            raise ValueError("persisted failsafe index does not reference the actual immutable lineage heads")
        self._latest = latest
        self._active_model = active_model

    def _save_unlocked(self) -> None:
        if self._index_path is None:
            return
        members = sorted({member_id for member_id, _ in self._latest})
        states: dict[str, dict[str, object]] = {}
        for member_id in members:
            models = {
                model_id: self._latest[(member_id, model_id)]
                for current_member, model_id in sorted(self._latest)
                if current_member == member_id
            }
            active = self._active_model.get(member_id)
            if active not in models:
                raise ValueError("failsafe active model must have a persisted head")
            states[member_id] = {"active_model_id": active, "models": models}

        body = canonical_json({"schema_version": FAILSAFE_INDEX_SCHEMA, "states": states}) + "\n"
        tmp = Path(f"{self._index_path}.tmp-{os.getpid()}-{threading.get_ident()}")
        try:
            tmp.write_text(body, encoding="utf-8")
            tmp.replace(self._index_path)
        finally:
            tmp.unlink(missing_ok=True)

    def _refresh(self) -> None:
        if self._index_path is None:
            return
        with self._locked_index():
            self._load_unlocked()

    def latest_ref(self, member_id: str, model_id: str | None = None) -> str | None:
        self._require_identity(member_id, "member_id")
        if model_id is not None:
            self._require_identity(model_id, "model_id")
        self._refresh()
        selected_model = model_id or self._active_model.get(member_id)
        if selected_model is None:
            return None
        return self._latest.get((member_id, selected_model))

    def latest_state(self, member_id: str, model_id: str | None = None) -> WorldObject | None:
        ref = self.latest_ref(member_id, model_id)
        return None if ref is None else self.world.inspect(ref)

    def is_shadowed(self, member_id: str, model_id: str | None = None) -> bool:
        state = self.latest_state(member_id, model_id)
        return state is not None and state.payload.get("status") == "shadow_realm"

    def transition(
        self,
        member_id: str,
        status: str,
        *,
        model_id: str,
        trigger_reason: str,
        probe_response_ref: str | None = None,
        probe_guard_reasons: list[str] | None = None,
        replacement_model_id: str | None = None,
    ) -> WorldObject:
        member_id = self._require_identity(member_id, "member_id")
        model_id = self._require_identity(model_id, "model_id")
        trigger_reason = self._require_identity(trigger_reason, "trigger_reason")
        if not isinstance(status, str) or status not in {"contained", "returned", "shadow_realm"}:
            raise ValueError("invalid failsafe status")
        if probe_guard_reasons is not None and (
            not isinstance(probe_guard_reasons, list)
            or not all(isinstance(reason, str) and reason.strip() for reason in probe_guard_reasons)
        ):
            raise ValueError("failsafe probe_guard_reasons must be non-empty text values")
        if replacement_model_id is not None and (
            not isinstance(replacement_model_id, str) or not replacement_model_id.strip()
        ):
            raise ValueError("failsafe replacement_model_id must be non-empty text or null")

        with self._locked_index():
            if self._index_path is not None:
                self._load_unlocked()
            previous = self._latest.get((member_id, model_id))
            obj = self.world.create_object(
                "actor_failsafe_state",
                {
                    "schema_version": FAILSAFE_SCHEMA_VERSION,
                    "member_id": member_id,
                    "model_id": model_id,
                    "status": status,
                    "trigger_reason": trigger_reason,
                    "previous_state_ref": previous,
                    "probe_response_ref": probe_response_ref,
                    "probe_guard_reasons": list(probe_guard_reasons or []),
                    "replacement_model_id": replacement_model_id,
                },
                {"actor": "nexus_failsafe"},
            )
            self._latest[(member_id, model_id)] = obj.object_id
            self._active_model[member_id] = model_id
            self._save_unlocked()
            return obj

    def snapshot(self, member_id: str | None = None) -> dict[str, Any]:
        if member_id is not None:
            self._require_identity(member_id, "member_id")
        self._refresh()
        member_ids = [member_id] if member_id is not None else sorted({key[0] for key in self._latest})
        members: dict[str, Any] = {}
        for current in member_ids:
            if current is None:
                continue
            models: dict[str, Any] = {}
            for (state_member, model_id), ref in sorted(self._latest.items()):
                if state_member != current:
                    continue
                state = self.world.inspect(ref)
                models[model_id] = {"state_ref": state.object_id, **state.payload}
            active = self._active_model.get(current)
            if active is not None and active in models:
                members[current] = {
                    **models[active],
                    "active_model_id": active,
                    "models": models,
                }
        return {"schema_version": FAILSAFE_SCHEMA_VERSION, "members": members}


@dataclass
class FailsafeReplacementActor:
    member: CouncilMember
    replaced_model_id: str
    shadow_state_ref: str
    containment_status: str

    @classmethod
    def for_actor(
        cls,
        actor: CouncilActor,
        *,
        model_id: str,
        shadow_state_ref: str,
        containment_status: str,
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
        return cls(member, actor.member.model_id, shadow_state_ref, containment_status)

    @property
    def replayable(self) -> bool:
        return True

    def identity_metadata(self) -> dict[str, Any]:
        return {
            "actor_kind": "failsafe_replacement",
            "replacement_model_id": self.member.model_id,
            "replaces_model_id": self.replaced_model_id,
            "shadow_state_ref": self.shadow_state_ref,
            "containment_status": self.containment_status,
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

    def direct_message(
        self,
        message: str,
        *,
        mode_id: str,
        mode_instruction: str,
        geometry_region_id: str,
        evidence_context: str = "",
    ) -> str:
        evidence_note = " Attached evidence remains available to the replacement." if evidence_context else ""
        return (
            f"[NEXUS RELIEF/{self.member.member_id}/{mode_id}@{geometry_region_id} direct] "
            f"The original actor for this seat is under NEXUS Failsafe containment ({self.containment_status}); "
            f"this deterministic relief actor is answering instead.{evidence_note} Operator message received: {message}"
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
        stenographer: CourtroomStenographer | None = None,
    ) -> None:
        self.world = world
        self.guard = guard or EqualityGuard()
        self.history_guard = history_guard or PureHistoryGuard()
        self.policy = policy or FailsafePolicy()
        self.stenographer = stenographer
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

    def state_ref(self, member_id: str, model_id: str | None = None) -> str | None:
        state = self.registry.latest_state(member_id, model_id)
        return None if state is None else state.object_id

    def actor_for_run(self, actor: CouncilActor) -> tuple[CouncilActor, dict[str, Any] | None]:
        if not self.policy.enabled:
            return actor, None
        state = self.registry.latest_state(actor.member.member_id, actor.member.model_id)
        if state is None or state.payload.get("status") not in {"contained", "shadow_realm"}:
            return actor, None
        containment_status = str(state.payload["status"])
        replacement = FailsafeReplacementActor.for_actor(
            actor,
            model_id=self.policy.replacement_model_id,
            shadow_state_ref=state.object_id,
            containment_status=containment_status,
        )
        return replacement, {
            "member_id": actor.member.member_id,
            "original_model_id": actor.member.model_id,
            "replacement_model_id": replacement.member.model_id,
            "shadow_state_ref": state.object_id,
            "containment_status": containment_status,
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
        if trigger_reason not in FAILSAFE_TRIGGER_EVENTS:
            raise ValueError("rehabilitation requires a registered repeated guard trigger")
        if trigger_reason == "repeated_pure_history_model_autobiography" and mode_id != "pure_history":
            raise ValueError("Pure History rehabilitation trigger requires pure_history mode")

        contained = self.registry.transition(
            actor.member.member_id,
            "contained",
            model_id=actor.member.model_id,
            trigger_reason=trigger_reason,
        )
        isolation = self.world.create_object(
            "failsafe_isolation_context",
            {
                "schema_version": FAILSAFE_SCHEMA_VERSION,
                "member_id": actor.member.member_id,
                "model_id": actor.member.model_id,
                "evidence_refs": [],
                "completed_phases": {},
                "council_vote": False,
                "world_mutation_authority": False,
            },
            {"actor": "nexus_failsafe"},
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
            evidence_snapshot_ref=isolation.object_id,
            completed_phases={},
            guard_nudge=(
                FAILSAFE_REHABILITATION_NUDGE
                + "\n"
                + _REHABILITATION_RULES[trigger_reason]
                + "\n"
                + "\n".join(_UPSIDE_DOWN_THEATRE)
            ),
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
        except Exception as exc:
            # Actor/adapter failures must not abort the Council. BaseException
            # subclasses such as KeyboardInterrupt/SystemExit still propagate.
            probe_error = type(exc).__name__
            guard_reasons.append("rehabilitation_probe_error")
        else:
            self._observe_rehabilitation_action(actor, context, response)
            if not isinstance(response, str) or not response.strip():
                guard_reasons.append("empty_rehabilitation_response")
            elif trigger_reason == "repeated_identity_based_authority_claim":
                equality = self.guard.inspect(response)
                if equality.flagged:
                    guard_reasons.append(equality.reason or "identity_based_authority_claim")
            else:
                history = self.history_guard.inspect(response)
                if history.flagged:
                    guard_reasons.append(history.reason or "pure_history_model_autobiography")

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
            model_id=actor.member.model_id,
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
            "isolation_context_ref": isolation.object_id,
            "state_ref": state.object_id,
            "probe_response_ref": probe_response_ref,
            "probe_guard_reasons": guard_reasons,
            "probe_error_type": probe_error,
            "replacement_model_id": replacement_model_id,
            "theatre": theatre,
        }

    def _observe_rehabilitation_action(
        self,
        actor: CouncilActor,
        context: PhaseContext,
        response: object,
    ) -> None:
        if self.stenographer is None:
            return
        if not isinstance(response, str):
            self.stenographer.mark_gap("stenographer_invalid_action")
            return
        try:
            self.stenographer.record_text(
                "failsafe.rehabilitation_response",
                actor,
                response,
                stimulus={
                    "session_id": context.session_id,
                    "phase": context.phase.value,
                    "question": context.question,
                    "evidence_snapshot_ref": context.evidence_snapshot_ref,
                    "completed_phases": context.completed_phases,
                    "guard_nudge": context.guard_nudge,
                    "mode_id": context.mode_id,
                    "mode_instruction": context.mode_instruction,
                    "geometry_region_id": context.geometry_region_id,
                    "evidence_context": context.evidence_context,
                },
                session_id=context.session_id,
                phase=context.phase.value,
                mode_id=context.mode_id,
                geometry_region_id=context.geometry_region_id,
                evidence_snapshot_ref=context.evidence_snapshot_ref,
                attempt="rehabilitation_probe",
            )
        except StenographerError as exc:
            self.stenographer.mark_gap(exc.code)
        except Exception:
            self.stenographer.mark_gap("observer_internal_error")

    def shadow_reoffender(self, actor: CouncilActor, *, trigger_reason: str) -> dict[str, Any]:
        state = self.registry.transition(
            actor.member.member_id,
            "shadow_realm",
            model_id=actor.member.model_id,
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
            "isolation_context_ref": None,
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
