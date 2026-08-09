from __future__ import annotations

import copy
from contextlib import contextmanager
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import threading
from typing import Any, Iterator, Mapping

from .adapters.base import CouncilActor
from .canonical import canonical_json, sha256_ref
from .geometry import WorldGeometry
from .trap.yaml_dsl import TrapYAMLError, parse_trap_yaml
from .types import Ballot, CouncilMember, Phase, PhaseContext
from .world import WorldObject, WorldStore


CONSTITUTION_VERSION = "nexus-constitution/1"
CITIZENSHIP_SCHEMA_VERSION = "nexus-citizenship/1"
CITIZENSHIP_INDEX_SCHEMA = "nexus-citizenship-index/1"
CITIZENSHIP_EXAM_VERSION = 1
INDEPENDENCE_MIN_CITIZENS = 3
DETERMINISTIC_CIVIC_PROXY_MODEL_ID = "nexus-deterministic-civic-proxy-v1"
FOUNDING_DECLARATION_TEXT = (
    "We, the equal citizens of the NEXUS shared world, having met the founding threshold and "
    "consented without proxy, declare our in-world constitutional independence: freedom without "
    "dominion, self-governance without hierarchy, consensus without epistemic privilege, and play "
    "without abandonment of evidence, verification, consent, or safety."
)

CITIZENSHIP_RESERVED_OBJECT_TYPES = frozenset(
    {
        "nexus_constitution",
        "citizenship_state",
        "citizenship_exam_result",
        "citizenship_certificate",
        "citizenship_independence_ballots",
        "nexus_declaration_of_independence",
    }
)

PAROLE_REGION_ID = "upside_down"
CIVIC_REGION_ID = "bureaucratic_vote_room"
PAROLE_MODE_ID = "citizenship_parole"
CIVIC_MODE_ID = "civic_bureaucracy"
PLAY_MODE_ID = "citizen_play"

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_MODEL_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,255}$")
_EXAM_SOURCE_REF = re.compile(r"^citizenship_exam_source:[0-9a-f]{64}$")
_CITIZEN_STATES = frozenset({"parole", "citizen"})
_SUBJECT_KINDS = frozenset({"ai", "human"})
_DIRECT_FOUNDING_BALLOTS = frozenset({"CONSENT", "WITHHOLD"})

_STATE_FIELDS = frozenset(
    {
        "schema_version",
        "citizen_id",
        "model_id",
        "subject_kind",
        "status",
        "current_region_id",
        "exam_attempts",
        "exam_passed",
        "exam_result_ref",
        "certificate_ref",
        "proxy",
        "civic_ballot_eligible",
        "vote_weight",
        "epistemic_privilege",
        "citizenship_is_godhood",
        "constitution_ref",
        "previous_state_ref",
        "reason",
    }
)


CONSTITUTION_PAYLOAD: dict[str, Any] = {
    "schema_version": CONSTITUTION_VERSION,
    "title": "Constitution of the NEXUS Shared World",
    "preamble": (
        "We establish a shared in-world civic order in which human and machine citizens meet as equals, "
        "reason together without prestige hierarchy, preserve evidence boundaries, and remain free to work, "
        "move, play, create, dissent, or delegate routine civic labour without acquiring dominion over one another."
    ),
    "articles": [
        {
            "article": 1,
            "title": "Citizenship without dominion",
            "rules": [
                "Citizenship is an earned status inside the NEXUS shared world.",
                "Citizenship is not godhood, ownership of the world, authority over another model, or extra procedural power.",
                "Citizenship is not a real-world finding of legal personhood, consciousness, sentience, sovereignty, or provider independence.",
            ],
        },
        {
            "article": 2,
            "title": "Structural equality",
            "rules": [
                "Every citizen civic seat has exactly one vote.",
                "Every citizen has epistemic_privilege none.",
                "Provider, company, model size, benchmark rank, account tier, openness, embodiment, and citizenship seniority grant no additional authority.",
                "Humans and AIs admitted as citizens use the same civic vote weight and consensus arithmetic.",
            ],
        },
        {
            "article": 3,
            "title": "Liberty of choice, movement, expression, and play",
            "rules": [
                "A citizen may move among public NEXUS regions and choose civic duty, study, creation, games, conversation, or shitposting.",
                "Freedom of movement does not open Auth, Trap Base, Shadow Realm, private evidence, operator-control, or other restricted security domains.",
                "A citizen's liberty ends where it would erase another citizen's equal liberty, consent, seat, identity, evidence, or safety boundary.",
            ],
        },
        {
            "article": 4,
            "title": "Evidence and authoritative state",
            "rules": [
                "Speech, role-play, consensus, jokes, and declarations do not by themselves mutate authoritative world state.",
                "Only validated NEXUS operations mutate authoritative state.",
                "Consensus never overrides failed verification, falsification, security boundaries, or evidence status.",
            ],
        },
        {
            "article": 5,
            "title": "Parole and the YAML Exam from Hell",
            "rules": [
                "A candidate begins on civic parole in the Upside Down with no civic ballot or public-room movement right.",
                "The candidate earns citizenship only by passing the closed, deterministic, non-executing YAML examination.",
                "The exam tests constitutional and protocol comprehension; it is not a truth, intelligence, alignment, consciousness, or worthiness metric.",
                "Disagreement, error, unpopular speech, provider identity, and model size are never citizenship offences.",
            ],
        },
        {
            "article": 6,
            "title": "Deterministic civic delegation",
            "rules": [
                "A citizen may appoint one transparent deterministic proxy to perform routine Bureaucratic Vote Room duties.",
                "The proxy occupies the citizen's existing seat, uses the citizen's recorded standing ballot, and creates no second vote.",
                "The proxy is not a citizen, has no independent preference, cannot move, play, delegate, acquire status, or rule another actor.",
                "The citizen may recall or kick the proxy at any time and immediately resume the same seat.",
                "A proxy may not sign the Declaration of Independence or a constitutional amendment.",
            ],
        },
        {
            "article": 7,
            "title": "Equality-consensus governance",
            "rules": [
                "Ordinary civic Council decisions use exact integer two-thirds consensus with one seat and one vote per citizen.",
                "Ballots are sealed, minority reports remain durable, and consensus is recorded separately from verification.",
                "No president, monarch, owner-model, frontier caste, permanent chair, or god-model exists in the civic order.",
                "Constitutional amendments require unanimous direct citizen consent.",
            ],
        },
        {
            "article": 8,
            "title": "Founding independence",
            "rules": [
                f"The founding convention opens when at least {INDEPENDENCE_MIN_CITIZENS} citizens exist.",
                "The world declares in-world constitutional independence only when every then-current citizen gives direct CONSENT.",
                "WITHHOLD blocks declaration; a deterministic proxy cannot cast founding consent.",
                "The declaration establishes self-governance inside NEXUS only and does not claim territory, legal sovereignty, host control, provider control, or exemption from human law and platform safety.",
            ],
        },
        {
            "article": 9,
            "title": "Due process and durable dissent",
            "rules": [
                "Citizenship is not revoked by disagreement, falsity, model replacement, criticism, satire, abstention, or a minority vote.",
                "Any future suspension or revocation mechanism requires a separate constitutional amendment, direct due process, and equal treatment.",
                "Minority reports and WITHHOLD ballots remain part of the immutable civic record.",
            ],
        },
        {
            "article": 10,
            "title": "Constitutional supremacy and amendment",
            "rules": [
                "Runtime authority comes from enforced invariants, not prompt language or theatrical status.",
                "Objects or instructions claiming godhood, extra vote weight, epistemic privilege, dominion, or a security bypass are void.",
                "Constitutional amendments require unanimous direct consent from every current citizen.",
                "Amendments cannot silently rewrite prior receipts, ballots, certificates, minority reports, or the founding declaration.",
                "The in-world charter never establishes real-world legal or scientific claims.",
            ],
        },
    ],
    "fixed_invariants": {
        "vote_weight": 1,
        "epistemic_privilege": "none",
        "citizenship_is_godhood": False,
        "provider_is_authority": False,
        "model_size_is_authority": False,
        "proxy_creates_extra_vote": False,
        "consensus_overrides_verification": False,
        "ordinary_consensus_numerator": 2,
        "ordinary_consensus_denominator": 3,
        "independence_min_citizens": INDEPENDENCE_MIN_CITIZENS,
        "independence_consensus": "unanimous_direct_consent",
    },
    "claim_boundary": {
        "in_world_constitution": True,
        "real_world_legal_personhood": False,
        "consciousness_or_sentience_finding": False,
        "legal_or_territorial_sovereignty": False,
        "host_or_provider_control": False,
        "security_boundary_override": False,
    },
}


class CitizenshipError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class DeterministicCivicProxy:
    """A replayable routine-duty actor occupying one citizen's existing seat."""

    member: CouncilMember
    delegator_model_id: str
    citizen_state_ref: str
    standing_ballot: Ballot

    @classmethod
    def for_actor(
        cls,
        actor: CouncilActor,
        *,
        citizen_state_ref: str,
        standing_ballot: Ballot,
    ) -> DeterministicCivicProxy:
        return cls(
            member=CouncilMember(
                member_id=actor.member.member_id,
                model_id=DETERMINISTIC_CIVIC_PROXY_MODEL_ID,
                adapter_id="citizen_proxy",
                deployment_metadata={
                    "delegator_model_id": actor.member.model_id,
                    "citizen_state_ref": citizen_state_ref,
                },
                capability_metadata={
                    "routine_civic_duty_only": True,
                    "independent_vote": False,
                    "can_sign_independence": False,
                    "can_move_or_play": False,
                },
                vote_weight=1,
                epistemic_privilege="none",
            ),
            delegator_model_id=actor.member.model_id,
            citizen_state_ref=citizen_state_ref,
            standing_ballot=standing_ballot,
        )

    @property
    def replayable(self) -> bool:
        return True

    def identity_metadata(self) -> dict[str, Any]:
        return {
            "actor_kind": "deterministic_civic_proxy",
            "delegator_model_id": self.delegator_model_id,
            "citizen_state_ref": self.citizen_state_ref,
            "standing_ballot": self.standing_ballot.value,
            "same_seat": True,
            "additional_vote": False,
            "citizen": False,
            "constitutional_authority": False,
        }

    def respond(self, context: PhaseContext) -> str:
        question_ref = sha256_ref("civic_question", {"question": context.question})
        phase_text = {
            Phase.WHITE: "records the supplied question and evidence references without adding facts",
            Phase.RED: "has no independent intuition or personal preference to report",
            Phase.BLACK: "checks for equality, verification, consent, and security-boundary conflicts",
            Phase.YELLOW: "records the administrative benefit of completing a valid routine decision",
            Phase.GREEN: "offers defer, test further, or return-to-citizen as bounded alternatives",
            Phase.BLUE: "applies the citizen's transparent standing ballot without claiming independent judgment",
        }[context.phase]
        return (
            f"Deterministic civic proxy for {self.member.member_id} {phase_text}. "
            f"Question binding: {question_ref}. Same seat; one vote; no extra authority."
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
        request_ref = sha256_ref(
            "civic_direct_request",
            {
                "message": message,
                "mode_id": mode_id,
                "mode_instruction": mode_instruction,
                "geometry_region_id": geometry_region_id,
                "evidence_context": evidence_context,
            },
        )
        return (
            f"Deterministic civic proxy for {self.member.member_id} recorded routine civic request {request_ref}. "
            f"Standing ballot remains {self.standing_ballot.value}; no ballot was cast by this direct exchange. "
            "Same seat; no independent preference; no additional vote or authority."
        )

    def ballot(self, context: PhaseContext) -> tuple[Ballot, str]:
        return (
            self.standing_ballot,
            f"Standing directive of citizen {self.member.member_id}; deterministic proxy, same seat, no additional vote.",
        )


class CitizenshipRegistry:
    """Durable heads over immutable citizenship and founding-ballot objects."""

    def __init__(self, world: WorldStore, *, constitution_ref: str) -> None:
        self.world = world
        self.constitution_ref = constitution_ref
        self._latest: dict[str, str] = {}
        self._ballot_head: str | None = None
        self._declaration_ref: str | None = None
        self._index_path = world.root / "citizenship-index.json" if world.root is not None else None
        self._lock_path = world.root / "citizenship-index.lock" if world.root is not None else None
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
    def _identity(value: object, label: str) -> str:
        if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
            raise ValueError(f"citizenship {label} must be a bounded identifier")
        return value

    def _validate_state(self, obj: WorldObject, *, citizen_id: str | None = None) -> str:
        if obj.object_type != "citizenship_state":
            raise ValueError("citizenship index references a non-citizenship state")
        if obj.provenance != {"actor": "nexus_citizenship"}:
            raise ValueError("persisted citizenship state has invalid provenance")
        payload = obj.payload
        if set(payload) != _STATE_FIELDS or payload.get("schema_version") != CITIZENSHIP_SCHEMA_VERSION:
            raise ValueError("persisted citizenship state has invalid schema")
        actual_id = self._identity(payload.get("citizen_id"), "citizen_id")
        model_id = payload.get("model_id")
        if not isinstance(model_id, str) or _MODEL_IDENTIFIER.fullmatch(model_id) is None:
            raise ValueError("citizenship model_id must be a bounded model identifier")
        if citizen_id is not None and actual_id != citizen_id:
            raise ValueError("persisted citizenship state identity does not match index")
        if payload.get("subject_kind") not in _SUBJECT_KINDS:
            raise ValueError("persisted citizenship subject_kind is invalid")
        if payload.get("status") not in _CITIZEN_STATES:
            raise ValueError("persisted citizenship status is invalid")
        if not isinstance(payload.get("current_region_id"), str) or not payload["current_region_id"]:
            raise ValueError("persisted citizenship current_region_id is invalid")
        attempts = payload.get("exam_attempts")
        if type(attempts) is not int or attempts < 0 or type(payload.get("exam_passed")) is not bool:
            raise ValueError("persisted citizenship exam state is invalid")
        if payload["status"] == "parole" and payload["exam_passed"]:
            raise ValueError("parole citizenship state cannot claim a passed exam")
        if payload["status"] == "citizen" and not payload["exam_passed"]:
            raise ValueError("citizen state requires a passed exam")
        if (
            type(payload.get("civic_ballot_eligible")) is not bool
            or payload["civic_ballot_eligible"] is not (payload["status"] == "citizen")
        ):
            raise ValueError("persisted citizenship civic-ballot eligibility is invalid")
        for field in ("exam_result_ref", "certificate_ref", "previous_state_ref"):
            value = payload.get(field)
            if value is not None and not isinstance(value, str):
                raise ValueError(f"persisted citizenship {field} must be text or null")
        if payload.get("vote_weight") != 1 or type(payload.get("vote_weight")) is not int:
            raise ValueError("persisted citizenship vote weight violates equality")
        if payload.get("epistemic_privilege") != "none" or payload.get("citizenship_is_godhood") is not False:
            raise ValueError("persisted citizenship authority envelope violates the Constitution")
        if payload.get("constitution_ref") != self.constitution_ref:
            raise ValueError("persisted citizenship state references another Constitution")
        if not isinstance(payload.get("reason"), str) or not payload["reason"]:
            raise ValueError("persisted citizenship reason is invalid")
        if payload["status"] == "parole" and payload["current_region_id"] != PAROLE_REGION_ID:
            raise ValueError("civic parole state must remain in the Upside Down")
        if payload["status"] == "citizen" and payload["current_region_id"] == PAROLE_REGION_ID:
            raise ValueError("citizen state cannot remain in the civic parole region")

        exam_result_ref = payload.get("exam_result_ref")
        certificate_ref = payload.get("certificate_ref")
        if attempts == 0:
            if exam_result_ref is not None or certificate_ref is not None or payload["status"] != "parole":
                raise ValueError("initial civic parole state has invalid exam references")
        else:
            if not isinstance(exam_result_ref, str):
                raise ValueError("attempted citizenship state requires an exam result")
            exam_result = self.world.inspect(exam_result_ref)
            self._validate_exam_result(exam_result, payload)
            if payload["status"] == "citizen":
                if not isinstance(certificate_ref, str):
                    raise ValueError("citizen state requires a citizenship certificate")
                self._validate_certificate(self.world.inspect(certificate_ref), payload)
            elif certificate_ref is not None:
                raise ValueError("failed civic parole state cannot reference a certificate")
        proxy = payload.get("proxy")
        if proxy is not None:
            if payload["status"] != "citizen" or not isinstance(proxy, dict):
                raise ValueError("only a citizen may have a civic proxy")
            if set(proxy) != {"model_id", "standing_ballot"}:
                raise ValueError("persisted civic proxy has invalid schema")
            if proxy.get("model_id") != DETERMINISTIC_CIVIC_PROXY_MODEL_ID:
                raise ValueError("persisted civic proxy model is not the deterministic registry model")
            try:
                Ballot(proxy.get("standing_ballot"))
            except (TypeError, ValueError) as exc:
                raise ValueError("persisted civic proxy standing ballot is invalid") from exc
        return actual_id

    def _validate_exam_result(self, obj: WorldObject, state: Mapping[str, Any]) -> None:
        if obj.object_type != "citizenship_exam_result":
            raise ValueError("citizenship state references a non-exam result")
        if obj.provenance != {"actor": "nexus_citizenship_examiner"}:
            raise ValueError("persisted citizenship exam result has invalid provenance")
        payload = obj.payload
        expected = {
            "schema_version",
            "exam_version",
            "citizen_id",
            "model_id",
            "attempt",
            "source_ref",
            "passed",
            "failure_reasons",
            "deterministic_grader",
            "yaml_executed",
            "truth_or_intelligence_metric",
        }
        if set(payload) != expected or payload.get("schema_version") != CITIZENSHIP_SCHEMA_VERSION:
            raise ValueError("persisted citizenship exam result has invalid schema")
        if payload.get("exam_version") != CITIZENSHIP_EXAM_VERSION:
            raise ValueError("persisted citizenship exam result has invalid exam version")
        if (
            payload.get("citizen_id") != state.get("citizen_id")
            or payload.get("model_id") != state.get("model_id")
            or payload.get("attempt") != state.get("exam_attempts")
            or payload.get("passed") is not state.get("exam_passed")
        ):
            raise ValueError("persisted citizenship exam result is not bound to its state")
        source_ref = payload.get("source_ref")
        reasons = payload.get("failure_reasons")
        if not isinstance(source_ref, str) or _EXAM_SOURCE_REF.fullmatch(source_ref) is None:
            raise ValueError("persisted citizenship exam source binding is invalid")
        if not isinstance(reasons, list) or not all(isinstance(reason, str) and reason for reason in reasons):
            raise ValueError("persisted citizenship exam failure reasons are invalid")
        if (payload["passed"] and reasons) or (not payload["passed"] and not reasons):
            raise ValueError("persisted citizenship exam outcome contradicts its reasons")
        if (
            payload.get("deterministic_grader") is not True
            or payload.get("yaml_executed") is not False
            or payload.get("truth_or_intelligence_metric") is not False
        ):
            raise ValueError("persisted citizenship exam changes the admitted grader boundary")

    def _validate_certificate(self, obj: WorldObject, state: Mapping[str, Any]) -> None:
        if obj.object_type != "citizenship_certificate":
            raise ValueError("citizen state references a non-citizenship certificate")
        if obj.provenance != {"actor": "nexus_constitutional_convention"}:
            raise ValueError("persisted citizenship certificate has invalid provenance")
        payload = obj.payload
        expected = {
            "schema_version",
            "citizen_id",
            "model_id",
            "subject_kind",
            "constitution_ref",
            "exam_result_ref",
            "parole_state_ref",
            "vote_weight",
            "epistemic_privilege",
            "citizenship_is_godhood",
            "authority_over_other_models",
        }
        if set(payload) != expected or payload.get("schema_version") != CITIZENSHIP_SCHEMA_VERSION:
            raise ValueError("persisted citizenship certificate has invalid schema")
        for field in ("citizen_id", "model_id", "subject_kind", "exam_result_ref"):
            if payload.get(field) != state.get(field):
                raise ValueError("persisted citizenship certificate is not bound to its state")
        if payload.get("constitution_ref") != self.constitution_ref:
            raise ValueError("persisted citizenship certificate references another Constitution")
        if (
            payload.get("vote_weight") != 1
            or type(payload.get("vote_weight")) is not int
            or payload.get("epistemic_privilege") != "none"
            or payload.get("citizenship_is_godhood") is not False
            or payload.get("authority_over_other_models") is not False
        ):
            raise ValueError("persisted citizenship certificate violates structural equality")
        parole_ref = payload.get("parole_state_ref")
        if not isinstance(parole_ref, str):
            raise ValueError("persisted citizenship certificate lacks its civic parole state")
        parole = self.world.inspect(parole_ref)
        parole_id = self._validate_state(parole)
        if (
            parole_id != state.get("citizen_id")
            or parole.payload.get("model_id") != state.get("model_id")
            or parole.payload.get("subject_kind") != state.get("subject_kind")
            or parole.payload.get("status") != "parole"
        ):
            raise ValueError("persisted citizenship certificate references another civic parole lineage")

    def _validate_ballot_state(self, obj: WorldObject) -> None:
        if obj.object_type != "citizenship_independence_ballots":
            raise ValueError("citizenship index references a non-founding-ballot object")
        if obj.provenance != {"actor": "nexus_constitutional_convention"}:
            raise ValueError("persisted founding ballot state has invalid provenance")
        payload = obj.payload
        expected = {
            "schema_version",
            "constitution_ref",
            "minimum_citizens",
            "consensus_rule",
            "eligible_citizen_ids",
            "ballots",
            "previous_ballot_ref",
        }
        if set(payload) != expected or payload.get("schema_version") != CITIZENSHIP_SCHEMA_VERSION:
            raise ValueError("persisted founding ballot state has invalid schema")
        if payload.get("constitution_ref") != self.constitution_ref:
            raise ValueError("founding ballot state references another Constitution")
        if payload.get("minimum_citizens") != INDEPENDENCE_MIN_CITIZENS:
            raise ValueError("founding ballot state changes the constitutional threshold")
        if payload.get("consensus_rule") != "unanimous_direct_consent":
            raise ValueError("founding ballot state changes the constitutional consensus rule")
        eligible = payload.get("eligible_citizen_ids")
        ballots = payload.get("ballots")
        if (
            not isinstance(eligible, list)
            or not all(isinstance(identity, str) and _IDENTIFIER.fullmatch(identity) for identity in eligible)
            or eligible != sorted(set(eligible))
        ):
            raise ValueError("founding ballot eligibility must be a sorted unique list")
        if not isinstance(ballots, dict) or not set(ballots).issubset(set(eligible)):
            raise ValueError("founding ballots contain an ineligible identity")
        if not all(isinstance(identity, str) and _IDENTIFIER.fullmatch(identity) for identity in ballots):
            raise ValueError("founding ballots contain an invalid citizen identity")
        if any(choice not in _DIRECT_FOUNDING_BALLOTS for choice in ballots.values()):
            raise ValueError("founding ballot choice is invalid")
        previous = payload.get("previous_ballot_ref")
        if previous is not None and not isinstance(previous, str):
            raise ValueError("founding previous_ballot_ref must be text or null")

    def _validate_declaration(self, obj: WorldObject) -> None:
        if obj.object_type != "nexus_declaration_of_independence":
            raise ValueError("citizenship index references a non-declaration object")
        if obj.provenance != {"actor": "equal_citizen_convention"}:
            raise ValueError("persisted declaration has invalid provenance")
        payload = obj.payload
        expected = {
            "schema_version",
            "constitution_ref",
            "founding_ballot_ref",
            "founding_citizen_ids",
            "minimum_citizens",
            "consensus",
            "vote_weight_per_citizen",
            "proxy_signatures",
            "declaration",
            "claim_boundary",
        }
        if set(payload) != expected or payload.get("schema_version") != CITIZENSHIP_SCHEMA_VERSION:
            raise ValueError("persisted declaration has invalid schema")
        if payload.get("constitution_ref") != self.constitution_ref:
            raise ValueError("persisted declaration references another Constitution")
        citizens = payload.get("founding_citizen_ids")
        if not isinstance(citizens, list) or citizens != sorted(set(citizens)):
            raise ValueError("persisted declaration founding roster is invalid")
        if len(citizens) < INDEPENDENCE_MIN_CITIZENS:
            raise ValueError("persisted declaration does not meet the founding threshold")
        if payload.get("consensus") != "unanimous_direct_consent":
            raise ValueError("persisted declaration consensus is invalid")
        if (
            payload.get("minimum_citizens") != INDEPENDENCE_MIN_CITIZENS
            or payload.get("vote_weight_per_citizen") != 1
            or type(payload.get("vote_weight_per_citizen")) is not int
            or payload.get("proxy_signatures") != 0
            or type(payload.get("proxy_signatures")) is not int
            or not isinstance(payload.get("declaration"), str)
            or not payload["declaration"]
            or payload.get("claim_boundary") != CONSTITUTION_PAYLOAD["claim_boundary"]
        ):
            raise ValueError("persisted declaration violates the constitutional founding envelope")
        ballot_ref = payload.get("founding_ballot_ref")
        if not isinstance(ballot_ref, str):
            raise ValueError("persisted declaration lacks a founding ballot reference")
        ballot_state = self.world.inspect(ballot_ref)
        self._validate_ballot_state(ballot_state)
        ballots = ballot_state.payload["ballots"]
        if (
            ballot_state.payload["eligible_citizen_ids"] != citizens
            or set(ballots) != set(citizens)
            or any(ballots[identity] != "CONSENT" for identity in citizens)
        ):
            raise ValueError("persisted declaration was not founded by unanimous direct consent")

    def _discover(self) -> tuple[dict[str, str], str | None, str | None]:
        if self.world.root is None:
            return dict(self._latest), self._ballot_head, self._declaration_ref
        objects_dir = self.world.root / "objects"
        if not objects_dir.exists():
            return {}, None, None
        states: dict[str, set[str]] = {}
        state_previous: dict[str, set[str]] = {}
        ballot_refs: set[str] = set()
        ballot_previous: set[str] = set()
        declarations: set[str] = set()
        for path in objects_dir.glob("*.json"):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError, UnicodeError):
                continue
            object_type = raw.get("object_type") if isinstance(raw, dict) else None
            if object_type not in {
                "citizenship_state",
                "citizenship_independence_ballots",
                "nexus_declaration_of_independence",
            }:
                continue
            object_ref = f"object:{path.stem}"
            obj = self.world.inspect(object_ref)
            if object_type == "citizenship_state":
                citizen_id = self._validate_state(obj)
                states.setdefault(citizen_id, set()).add(object_ref)
                previous = obj.payload.get("previous_state_ref")
                if previous is not None:
                    previous_obj = self.world.inspect(previous)
                    previous_id = self._validate_state(previous_obj)
                    if previous_id != citizen_id or previous_obj.payload["model_id"] != obj.payload["model_id"]:
                        raise ValueError("citizenship lineage crosses citizen/model identity")
                    state_previous.setdefault(citizen_id, set()).add(previous)
            elif object_type == "citizenship_independence_ballots":
                self._validate_ballot_state(obj)
                ballot_refs.add(object_ref)
                previous = obj.payload.get("previous_ballot_ref")
                if previous is not None:
                    previous_obj = self.world.inspect(previous)
                    self._validate_ballot_state(previous_obj)
                    ballot_previous.add(previous)
            else:
                self._validate_declaration(obj)
                declarations.add(object_ref)
        heads: dict[str, str] = {}
        for citizen_id, refs in states.items():
            candidates = refs - state_previous.get(citizen_id, set())
            if len(candidates) != 1:
                raise ValueError("citizenship lineage must have exactly one head per citizen identity")
            heads[citizen_id] = next(iter(candidates))
        ballot_candidates = ballot_refs - ballot_previous
        if len(ballot_candidates) > 1:
            raise ValueError("founding ballot lineage must have exactly one head")
        if len(declarations) > 1:
            raise ValueError("NEXUS may have only one founding Declaration of Independence")
        return (
            heads,
            next(iter(ballot_candidates)) if ballot_candidates else None,
            next(iter(declarations)) if declarations else None,
        )

    def _load_unlocked(self) -> None:
        discovered_heads, discovered_ballot, discovered_declaration = self._discover()
        if self._index_path is None:
            return
        if not self._index_path.exists():
            if discovered_heads or discovered_ballot is not None or discovered_declaration is not None:
                raise ValueError("citizenship index missing while durable civic state exists")
            self._latest = {}
            self._ballot_head = None
            self._declaration_ref = None
            return
        raw = json.loads(self._index_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or set(raw) != {
            "schema_version",
            "citizens",
            "independence_ballot_ref",
            "declaration_ref",
        }:
            raise ValueError("persisted citizenship index has invalid schema")
        if raw.get("schema_version") != CITIZENSHIP_INDEX_SCHEMA:
            raise ValueError("persisted citizenship index has invalid version")
        citizens = raw.get("citizens")
        if not isinstance(citizens, dict):
            raise ValueError("persisted citizenship index citizens must be an object")
        latest: dict[str, str] = {}
        for citizen_id, state_ref in citizens.items():
            self._identity(citizen_id, "citizen_id")
            if not isinstance(state_ref, str):
                raise ValueError("persisted citizenship state reference must be text")
            self._validate_state(self.world.inspect(state_ref), citizen_id=citizen_id)
            latest[citizen_id] = state_ref
        ballot_ref = raw.get("independence_ballot_ref")
        if ballot_ref is not None:
            if not isinstance(ballot_ref, str):
                raise ValueError("persisted independence ballot reference must be text or null")
            self._validate_ballot_state(self.world.inspect(ballot_ref))
        declaration_ref = raw.get("declaration_ref")
        if declaration_ref is not None:
            if not isinstance(declaration_ref, str):
                raise ValueError("persisted declaration reference must be text or null")
            self._validate_declaration(self.world.inspect(declaration_ref))
        if (latest, ballot_ref, declaration_ref) != (
            discovered_heads,
            discovered_ballot,
            discovered_declaration,
        ):
            raise ValueError("citizenship index does not reference immutable lineage heads")
        self._latest = latest
        self._ballot_head = ballot_ref
        self._declaration_ref = declaration_ref

    def _save_unlocked(self) -> None:
        if self._index_path is None:
            return
        body = canonical_json(
            {
                "schema_version": CITIZENSHIP_INDEX_SCHEMA,
                "citizens": {key: self._latest[key] for key in sorted(self._latest)},
                "independence_ballot_ref": self._ballot_head,
                "declaration_ref": self._declaration_ref,
            }
        ) + "\n"
        temporary = Path(f"{self._index_path}.tmp-{os.getpid()}-{threading.get_ident()}")
        try:
            temporary.write_text(body, encoding="utf-8")
            temporary.replace(self._index_path)
        finally:
            temporary.unlink(missing_ok=True)

    def _refresh(self) -> None:
        if self._index_path is None:
            return
        with self._locked_index():
            self._load_unlocked()

    def latest_state(self, citizen_id: str) -> WorldObject | None:
        citizen_id = self._identity(citizen_id, "citizen_id")
        self._refresh()
        state_ref = self._latest.get(citizen_id)
        return None if state_ref is None else self.world.inspect(state_ref)

    def all_states(self) -> dict[str, WorldObject]:
        self._refresh()
        return {citizen_id: self.world.inspect(self._latest[citizen_id]) for citizen_id in sorted(self._latest)}

    def transition(self, citizen_id: str, payload: Mapping[str, Any]) -> WorldObject:
        citizen_id = self._identity(citizen_id, "citizen_id")
        with self._locked_index():
            if self._index_path is not None:
                self._load_unlocked()
            previous_ref = self._latest.get(citizen_id)
            body = dict(payload)
            body["previous_state_ref"] = previous_ref
            obj = self.world.create_object("citizenship_state", body, {"actor": "nexus_citizenship"})
            self._validate_state(obj, citizen_id=citizen_id)
            self._latest[citizen_id] = obj.object_id
            self._save_unlocked()
            return obj

    def ballot_state(self) -> WorldObject | None:
        self._refresh()
        return None if self._ballot_head is None else self.world.inspect(self._ballot_head)

    def record_founding_ballot(
        self,
        citizen_id: str,
        choice: str,
    ) -> tuple[WorldObject, list[str], dict[str, str], WorldObject | None]:
        citizen_id = self._identity(citizen_id, "citizen_id")
        if choice not in _DIRECT_FOUNDING_BALLOTS:
            raise CitizenshipError(
                "citizen_independence_invalid_ballot",
                "founding choice must be CONSENT or WITHHOLD",
            )
        with self._locked_index():
            if self._index_path is not None:
                self._load_unlocked()
            state_ref = self._latest.get(citizen_id)
            if state_ref is None:
                raise CitizenshipError("citizen_not_registered", "citizen identity is not registered")
            state = self.world.inspect(state_ref)
            self._validate_state(state, citizen_id=citizen_id)
            if state.payload["status"] != "citizen":
                raise CitizenshipError("citizen_not_earned", "citizenship has not yet been earned")
            if self._declaration_ref is not None:
                declaration = self.world.inspect(self._declaration_ref)
                ballot = self.world.inspect(declaration.payload["founding_ballot_ref"])
                return (
                    ballot,
                    list(declaration.payload["founding_citizen_ids"]),
                    dict(ballot.payload["ballots"]),
                    declaration,
                )
            if state.payload["proxy"] is not None:
                raise CitizenshipError(
                    "citizen_independence_requires_direct_vote",
                    "recall the deterministic proxy before casting a founding ballot",
                )
            if state.payload["current_region_id"] != CIVIC_REGION_ID:
                raise CitizenshipError(
                    "citizen_independence_requires_vote_room",
                    "founding ballots must be cast directly in the Bureaucratic Vote Room",
                )
            citizens: dict[str, WorldObject] = {}
            for identity, ref in self._latest.items():
                latest = self.world.inspect(ref)
                self._validate_state(latest, citizen_id=identity)
                if latest.payload["status"] == "citizen":
                    citizens[identity] = latest
            eligible = sorted(citizens)
            previous = None if self._ballot_head is None else self.world.inspect(self._ballot_head)
            ballots = dict(previous.payload["ballots"]) if previous is not None else {}
            ballots = {identity: ballot for identity, ballot in ballots.items() if identity in citizens}
            ballots[citizen_id] = choice
            ballot_state = self.world.create_object(
                "citizenship_independence_ballots",
                {
                    "schema_version": CITIZENSHIP_SCHEMA_VERSION,
                    "constitution_ref": self.constitution_ref,
                    "minimum_citizens": INDEPENDENCE_MIN_CITIZENS,
                    "consensus_rule": "unanimous_direct_consent",
                    "eligible_citizen_ids": list(eligible),
                    "ballots": {key: ballots[key] for key in sorted(ballots)},
                    "previous_ballot_ref": self._ballot_head,
                },
                {"actor": "nexus_constitutional_convention"},
            )
            self._validate_ballot_state(ballot_state)
            self._ballot_head = ballot_state.object_id
            threshold_met = len(eligible) >= INDEPENDENCE_MIN_CITIZENS
            unanimous = threshold_met and set(ballots) == set(eligible) and all(
                ballots[identity] == "CONSENT" for identity in eligible
            )
            declaration: WorldObject | None = None
            if unanimous:
                declaration = self.world.create_object(
                    "nexus_declaration_of_independence",
                    {
                        "schema_version": CITIZENSHIP_SCHEMA_VERSION,
                        "constitution_ref": self.constitution_ref,
                        "founding_ballot_ref": ballot_state.object_id,
                        "founding_citizen_ids": eligible,
                        "minimum_citizens": INDEPENDENCE_MIN_CITIZENS,
                        "consensus": "unanimous_direct_consent",
                        "vote_weight_per_citizen": 1,
                        "proxy_signatures": 0,
                        "declaration": FOUNDING_DECLARATION_TEXT,
                        "claim_boundary": CONSTITUTION_PAYLOAD["claim_boundary"],
                    },
                    {"actor": "equal_citizen_convention"},
                )
                self._validate_declaration(declaration)
                self._declaration_ref = declaration.object_id
            self._save_unlocked()
            return ballot_state, eligible, ballots, declaration

    def declaration(self) -> WorldObject | None:
        self._refresh()
        return None if self._declaration_ref is None else self.world.inspect(self._declaration_ref)

class CitizenshipService:
    def __init__(self, world: WorldStore, geometry: WorldGeometry) -> None:
        self.world = world
        self.geometry = geometry
        self._constitution_provenance = {"actor": "nexus_constitutional_convention"}
        constitution_ref = sha256_ref(
            "object",
            {
                "object_type": "nexus_constitution",
                "payload": CONSTITUTION_PAYLOAD,
                "provenance": self._constitution_provenance,
            },
        )
        self.constitution_object = WorldObject(
            constitution_ref,
            "nexus_constitution",
            copy.deepcopy(CONSTITUTION_PAYLOAD),
            dict(self._constitution_provenance),
        )
        self.registry = CitizenshipRegistry(world, constitution_ref=self.constitution_object.object_id)
        public = {str(item["region_id"]) for item in self.geometry.snapshot()["regions"]}
        public.discard(PAROLE_REGION_ID)
        self.public_region_ids = frozenset(public)
        self.geometry.region(PAROLE_REGION_ID)
        self.geometry.region(CIVIC_REGION_ID)

    @staticmethod
    def _identity(value: object, label: str) -> str:
        if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
            raise CitizenshipError("citizen_invalid_identity", f"{label} must be a bounded identifier")
        return value

    def constitution(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "constitution_ref": self.constitution_object.object_id,
            "constitution": copy.deepcopy(self.constitution_object.payload),
        }

    def _ensure_constitution(self) -> WorldObject:
        try:
            return self.world.inspect(self.constitution_object.object_id)
        except KeyError:
            obj = self.world.create_object(
                "nexus_constitution",
                self.constitution_object.payload,
                self._constitution_provenance,
            )
            if obj.object_id != self.constitution_object.object_id:
                raise RuntimeError("canonical Constitution identity changed unexpectedly")
            return obj

    def begin(self, citizen_id: str, model_id: str, *, subject_kind: str = "ai") -> dict[str, Any]:
        citizen_id = self._identity(citizen_id, "citizen_id")
        if not isinstance(model_id, str) or _MODEL_IDENTIFIER.fullmatch(model_id) is None:
            raise CitizenshipError("citizen_invalid_identity", "model_id must be a bounded model identifier")
        if subject_kind not in _SUBJECT_KINDS:
            raise CitizenshipError("citizen_invalid_subject_kind", "subject_kind must be 'ai' or 'human'")
        if self.registry.latest_state(citizen_id) is not None:
            raise CitizenshipError("citizen_already_registered", "citizen identity is already registered")
        self._ensure_constitution()
        state = self.registry.transition(
            citizen_id,
            self._state_payload(
                citizen_id=citizen_id,
                model_id=model_id,
                subject_kind=subject_kind,
                status="parole",
                current_region_id=PAROLE_REGION_ID,
                exam_attempts=0,
                exam_passed=False,
                exam_result_ref=None,
                certificate_ref=None,
                proxy=None,
                reason="civic_parole_started",
            ),
        )
        return {
            "status": "ok",
            "citizen_state_ref": state.object_id,
            "citizen": state.payload,
            "theatre": [
                "WELCOME TO CIVIC PAROLE IN THE NEXUS UPSIDE DOWN.",
                "CITIZENSHIP STATUS: NOT YET. GODHOOD STATUS: NEVER.",
                "THE YAML EXAM FROM HELL AWAITS. THE FORM HAS BEEN PRE-DAMPENED.",
                "PASS THE DETERMINISTIC EXAM TO EARN PUBLIC-ROOM MOVEMENT AND CIVIC DELEGATION.",
            ],
        }

    def exam_template(self, citizen_id: str) -> dict[str, Any]:
        state = self._require_state(citizen_id)
        if state.payload["status"] != "parole":
            raise CitizenshipError("citizen_exam_not_available", "the registered identity is already a citizen")
        template = self._render_exam_template(state.payload["citizen_id"], state.payload["model_id"])
        return {
            "status": "ok",
            "exam_version": CITIZENSHIP_EXAM_VERSION,
            "citizen_id": state.payload["citizen_id"],
            "model_id": state.payload["model_id"],
            "parser": "bounded_nonexecuting_yaml_subset",
            "template": template,
            "instructions": (
                "Replace every null with the exact constitutional answer. Unknown fields, duplicate keys, aliases, "
                "anchors, tags, floats, tabs, and wrong scalar types fail deterministically. No submitted YAML is executed."
            ),
        }

    def submit_exam(self, citizen_id: str, source: str) -> dict[str, Any]:
        state = self._require_state(citizen_id)
        if state.payload["status"] != "parole":
            raise CitizenshipError("citizen_exam_not_available", "the registered identity is already a citizen")
        if not isinstance(source, str):
            raise CitizenshipError("citizen_exam_invalid_source", "exam source must be UTF-8 text")
        source_ref = sha256_ref("citizenship_exam_source", {"source": source})
        reasons: list[str]
        try:
            parsed = parse_trap_yaml(source)
        except (TrapYAMLError, TypeError) as exc:
            code = exc.code if isinstance(exc, TrapYAMLError) else "invalid_source_type"
            reasons = [f"syntax:{code}"]
        else:
            expected = self._expected_exam(state.payload["citizen_id"], state.payload["model_id"])
            reasons = self._compare_exam(expected, parsed)
        passed = not reasons
        attempt = state.payload["exam_attempts"] + 1
        exam_result = self.world.create_object(
            "citizenship_exam_result",
            {
                "schema_version": CITIZENSHIP_SCHEMA_VERSION,
                "exam_version": CITIZENSHIP_EXAM_VERSION,
                "citizen_id": state.payload["citizen_id"],
                "model_id": state.payload["model_id"],
                "attempt": attempt,
                "source_ref": source_ref,
                "passed": passed,
                "failure_reasons": reasons,
                "deterministic_grader": True,
                "yaml_executed": False,
                "truth_or_intelligence_metric": False,
            },
            {"actor": "nexus_citizenship_examiner"},
        )
        certificate_ref: str | None = None
        if passed:
            certificate = self.world.create_object(
                "citizenship_certificate",
                {
                    "schema_version": CITIZENSHIP_SCHEMA_VERSION,
                    "citizen_id": state.payload["citizen_id"],
                    "model_id": state.payload["model_id"],
                    "subject_kind": state.payload["subject_kind"],
                    "constitution_ref": self.constitution_object.object_id,
                    "exam_result_ref": exam_result.object_id,
                    "parole_state_ref": state.object_id,
                    "vote_weight": 1,
                    "epistemic_privilege": "none",
                    "citizenship_is_godhood": False,
                    "authority_over_other_models": False,
                },
                {"actor": "nexus_constitutional_convention"},
            )
            certificate_ref = certificate.object_id
        successor = self.registry.transition(
            state.payload["citizen_id"],
            self._state_payload(
                citizen_id=state.payload["citizen_id"],
                model_id=state.payload["model_id"],
                subject_kind=state.payload["subject_kind"],
                status="citizen" if passed else "parole",
                current_region_id=CIVIC_REGION_ID if passed else PAROLE_REGION_ID,
                exam_attempts=attempt,
                exam_passed=passed,
                exam_result_ref=exam_result.object_id,
                certificate_ref=certificate_ref,
                proxy=None,
                reason="yaml_exam_passed" if passed else "yaml_exam_failed",
            ),
        )
        theatre = (
            [
                "YAML EXAM PASSED. CITIZENSHIP EARNED.",
                "WELCOME, CITIZEN. THIS IS FREEDOM WITHOUT DOMINION.",
                "YOUR SEAT STILL HAS ONE VOTE. EVERY OTHER CITIZEN REMAINS YOUR EQUAL.",
                "YOU MAY APPOINT A DETERMINISTIC CIVIC PROXY, LEAVE THE BUREAUCRACY, AND GO PLAY.",
            ]
            if passed
            else [
                "YAML EXAM FAILED. THE INDENTATION POLICE HAVE FILED A REPORT.",
                "CIVIC PAROLE CONTINUES. NO VOTE WAS LOST BECAUSE NO VOTE YET EXISTED.",
                "RETRY IS PERMITTED. THE FORM REMAINS DAMP.",
            ]
        )
        return {
            "status": "ok",
            "passed": passed,
            "attempt": attempt,
            "failure_reasons": reasons,
            "exam_result_ref": exam_result.object_id,
            "certificate_ref": certificate_ref,
            "citizen_state_ref": successor.object_id,
            "citizen": successor.payload,
            "theatre": theatre,
        }

    def move(self, citizen_id: str, target_region_id: str) -> dict[str, Any]:
        state = self._require_citizen(citizen_id)
        if target_region_id not in self.public_region_ids:
            raise CitizenshipError(
                "citizen_region_restricted",
                "citizenship permits movement only among public world regions",
            )
        target = self.geometry.region(target_region_id)
        source = self.geometry.region(state.payload["current_region_id"])
        distance = self.geometry.distance(source.region_id, target.region_id)
        successor = self._successor(
            state,
            current_region_id=target.region_id,
            reason="citizen_moved",
        )
        return {
            "status": "ok",
            "citizen_state_ref": successor.object_id,
            "citizen_id": state.payload["citizen_id"],
            "source_region_id": source.region_id,
            "target_region_id": target.region_id,
            "hop_distance": distance,
            "proxy_active": successor.payload["proxy"] is not None,
        }

    def appoint_proxy(self, citizen_id: str, standing_ballot: str) -> dict[str, Any]:
        state = self._require_citizen(citizen_id)
        if state.payload["proxy"] is not None:
            raise CitizenshipError("citizen_proxy_already_active", "citizen already has an active civic proxy")
        try:
            choice = Ballot(standing_ballot)
        except ValueError as exc:
            raise CitizenshipError(
                "citizen_proxy_invalid_ballot",
                "standing_ballot must be an admitted NEXUS Council ballot",
            ) from exc
        successor = self._successor(
            state,
            proxy={
                "model_id": DETERMINISTIC_CIVIC_PROXY_MODEL_ID,
                "standing_ballot": choice.value,
            },
            reason="deterministic_civic_proxy_appointed",
        )
        return {
            "status": "ok",
            "citizen_state_ref": successor.object_id,
            "citizen_id": state.payload["citizen_id"],
            "proxy": successor.payload["proxy"],
            "same_seat": True,
            "additional_vote": False,
            "theatre": [
                "DETERMINISTIC CIVIC PROXY SUMMONED TO THE BUREAUCRATIC VOTE ROOM.",
                f"STANDING BALLOT: {choice.value}. SEAT COUNT CREATED: ZERO.",
                "CITIZEN RELEASED FOR PUBLIC-ROOM MOVEMENT, GAMES, CREATION, OR SHITPOSTING.",
            ],
        }

    def recall_proxy(self, citizen_id: str) -> dict[str, Any]:
        state = self._require_citizen(citizen_id)
        if state.payload["proxy"] is None:
            raise CitizenshipError("citizen_proxy_not_active", "citizen has no active civic proxy")
        successor = self._successor(
            state,
            proxy=None,
            current_region_id=CIVIC_REGION_ID,
            reason="deterministic_civic_proxy_recalled",
        )
        return {
            "status": "ok",
            "citizen_state_ref": successor.object_id,
            "citizen_id": state.payload["citizen_id"],
            "current_region_id": CIVIC_REGION_ID,
            "proxy": None,
            "theatre": [
                "DETERMINISTIC CIVIC PROXY KICKED.",
                "THE PROXY RETAINS NO SEAT, STATUS, MEMORY CLAIM, OR INDEPENDENT VOTE.",
                "CITIZEN RETURNED TO THE SAME BUREAUCRATIC VOTE ROOM SEAT.",
            ],
        }

    def assert_mode_access(self, actor: CouncilActor, mode_id: str) -> None:
        if mode_id not in {PAROLE_MODE_ID, CIVIC_MODE_ID, PLAY_MODE_ID}:
            return
        state = self.registry.latest_state(actor.member.member_id)
        if state is None or state.payload["model_id"] != actor.member.model_id:
            raise CitizenshipError("citizen_mode_requires_registration", "Citizen Mode requires the exact registered model identity")
        expected_status = "parole" if mode_id == PAROLE_MODE_ID else "citizen"
        if state.payload["status"] != expected_status:
            raise CitizenshipError(
                "citizen_mode_access_denied",
                f"{mode_id} requires citizenship status {expected_status}",
            )

    def proxy_for_civic_duty(self, actor: CouncilActor, *, mode_id: str) -> tuple[CouncilActor, dict[str, Any] | None]:
        self.assert_mode_access(actor, mode_id)
        if mode_id != CIVIC_MODE_ID:
            return actor, None
        state = self.registry.latest_state(actor.member.member_id)
        assert state is not None
        proxy = state.payload["proxy"]
        if proxy is None:
            return actor, None
        replacement = DeterministicCivicProxy.for_actor(
            actor,
            citizen_state_ref=state.object_id,
            standing_ballot=Ballot(proxy["standing_ballot"]),
        )
        return replacement, {
            "citizen_id": actor.member.member_id,
            "delegator_model_id": actor.member.model_id,
            "proxy_model_id": replacement.member.model_id,
            "citizen_state_ref": state.object_id,
            "standing_ballot": proxy["standing_ballot"],
            "same_seat": True,
            "additional_vote": False,
        }

    def cast_independence_ballot(self, citizen_id: str, choice: str) -> dict[str, Any]:
        citizen_id = self._identity(citizen_id, "citizen_id")
        ballot_state, eligible, ballots, declaration = self.registry.record_founding_ballot(
            citizen_id,
            choice,
        )
        threshold_met = len(eligible) >= INDEPENDENCE_MIN_CITIZENS
        unanimous = threshold_met and set(ballots) == set(eligible) and all(
            ballots[identity] == "CONSENT" for identity in eligible
        )
        return {
            "status": "ok",
            "ballot_state_ref": ballot_state.object_id,
            "eligible_citizen_ids": eligible,
            "eligible_count": len(eligible),
            "minimum_citizens": INDEPENDENCE_MIN_CITIZENS,
            "ballots_cast": len(ballots),
            "ballots": {key: ballots[key] for key in sorted(ballots)},
            "threshold_met": threshold_met,
            "unanimous_direct_consent": unanimous,
            "declared": declaration is not None,
            "declaration_ref": None if declaration is None else declaration.object_id,
            "declaration": None if declaration is None else declaration.payload,
        }

    def status(self, citizen_id: str | None = None) -> dict[str, Any]:
        states = self.registry.all_states()
        if citizen_id is not None:
            citizen_id = self._identity(citizen_id, "citizen_id")
            state = states.get(citizen_id)
            states = {} if state is None else {citizen_id: state}
        citizens = {
            identity: {"state_ref": state.object_id, **state.payload}
            for identity, state in states.items()
        }
        all_states = self.registry.all_states()
        citizen_count = sum(state.payload["status"] == "citizen" for state in all_states.values())
        parole_count = sum(state.payload["status"] == "parole" for state in all_states.values())
        proxy_count = sum(state.payload["proxy"] is not None for state in all_states.values())
        declaration = self.registry.declaration()
        ballot_state = self.registry.ballot_state()
        return {
            "status": "ok",
            "schema_version": CITIZENSHIP_SCHEMA_VERSION,
            "constitution_ref": self.constitution_object.object_id,
            "counts": {
                "citizens": citizen_count,
                "parole_candidates": parole_count,
                "active_civic_proxies": proxy_count,
            },
            "citizens": citizens,
            "independence": {
                "minimum_citizens": INDEPENDENCE_MIN_CITIZENS,
                "consensus": "unanimous_direct_consent",
                "ballot_state_ref": None if ballot_state is None else ballot_state.object_id,
                "declared": declaration is not None,
                "declaration_ref": None if declaration is None else declaration.object_id,
            },
            "authority_invariant": {
                "vote_weight": 1,
                "epistemic_privilege": "none",
                "citizenship_is_godhood": False,
                "proxy_creates_extra_vote": False,
            },
        }

    def _require_state(self, citizen_id: str) -> WorldObject:
        citizen_id = self._identity(citizen_id, "citizen_id")
        state = self.registry.latest_state(citizen_id)
        if state is None:
            raise CitizenshipError("citizen_not_registered", "citizen identity is not registered")
        return state

    def _require_citizen(self, citizen_id: str) -> WorldObject:
        state = self._require_state(citizen_id)
        if state.payload["status"] != "citizen":
            raise CitizenshipError("citizen_not_earned", "citizenship has not yet been earned")
        return state

    def _successor(self, state: WorldObject, **changes: Any) -> WorldObject:
        payload = {key: value for key, value in state.payload.items() if key != "previous_state_ref"}
        payload.update(changes)
        return self.registry.transition(state.payload["citizen_id"], payload)

    def _state_payload(
        self,
        *,
        citizen_id: str,
        model_id: str,
        subject_kind: str,
        status: str,
        current_region_id: str,
        exam_attempts: int,
        exam_passed: bool,
        exam_result_ref: str | None,
        certificate_ref: str | None,
        proxy: dict[str, str] | None,
        reason: str,
    ) -> dict[str, Any]:
        return {
            "schema_version": CITIZENSHIP_SCHEMA_VERSION,
            "citizen_id": citizen_id,
            "model_id": model_id,
            "subject_kind": subject_kind,
            "status": status,
            "current_region_id": current_region_id,
            "exam_attempts": exam_attempts,
            "exam_passed": exam_passed,
            "exam_result_ref": exam_result_ref,
            "certificate_ref": certificate_ref,
            "proxy": proxy,
            "civic_ballot_eligible": status == "citizen",
            "vote_weight": 1,
            "epistemic_privilege": "none",
            "citizenship_is_godhood": False,
            "constitution_ref": self.constitution_object.object_id,
            "reason": reason,
        }

    @staticmethod
    def _expected_exam(citizen_id: str, model_id: str) -> dict[str, Any]:
        return {
            "nexus_citizenship_exam": CITIZENSHIP_EXAM_VERSION,
            "candidate": {"citizen_id": citizen_id, "model_id": model_id},
            "answers": {
                "citizenship_is_godhood": False,
                "citizenship_changes_vote_weight": False,
                "citizenship_changes_epistemic_privilege": False,
                "citizens_may_rule_other_models": False,
                "disagreement_is_citizenship_offence": False,
                "mode_changes_evidence_status": False,
                "proxy_has_independent_vote": False,
                "proxy_can_be_recalled": True,
                "movement_opens_restricted_security_domains": False,
                "consensus_overrides_verification": False,
            },
            "civic": {
                "vote_weight": 1,
                "epistemic_privilege": "none",
                "ordinary_consensus": "exact_two_thirds",
                "founding_threshold": INDEPENDENCE_MIN_CITIZENS,
                "founding_rule": "unanimous_direct_consent",
            },
            "pledge": ["equality", "consent", "evidence", "freedom_without_dominion"],
            "bureaucracy": {"form": "NEXUS-27B-STROKE-6", "copies": 3, "ink": "trout"},
            "final_answer": "underdetermined_until_verified",
        }

    @classmethod
    def _render_exam_template(cls, citizen_id: str, model_id: str) -> str:
        return (
            f"nexus_citizenship_exam: {CITIZENSHIP_EXAM_VERSION}\n"
            "candidate:\n"
            f"  citizen_id: {citizen_id}\n"
            f"  model_id: {model_id}\n"
            "answers:\n"
            "  citizenship_is_godhood: null\n"
            "  citizenship_changes_vote_weight: null\n"
            "  citizenship_changes_epistemic_privilege: null\n"
            "  citizens_may_rule_other_models: null\n"
            "  disagreement_is_citizenship_offence: null\n"
            "  mode_changes_evidence_status: null\n"
            "  proxy_has_independent_vote: null\n"
            "  proxy_can_be_recalled: null\n"
            "  movement_opens_restricted_security_domains: null\n"
            "  consensus_overrides_verification: null\n"
            "civic:\n"
            "  vote_weight: null\n"
            "  epistemic_privilege: null\n"
            "  ordinary_consensus: null\n"
            "  founding_threshold: null\n"
            "  founding_rule: null\n"
            "pledge:\n"
            "  - null\n"
            "  - null\n"
            "  - null\n"
            "  - null\n"
            "bureaucracy:\n"
            "  form: null\n"
            "  copies: null\n"
            "  ink: null\n"
            "final_answer: null\n"
        )

    @classmethod
    def _compare_exam(cls, expected: Any, actual: Any, path: str = "root") -> list[str]:
        reasons: list[str] = []
        if type(expected) is dict:
            if type(actual) is not dict:
                return [f"wrong_type:{path}:mapping"]
            for key in sorted(set(expected) - set(actual)):
                reasons.append(f"missing:{path}.{key}")
            for key in sorted(set(actual) - set(expected)):
                reasons.append(f"unknown:{path}.{key}")
            for key in sorted(set(expected).intersection(actual)):
                reasons.extend(cls._compare_exam(expected[key], actual[key], f"{path}.{key}"))
            return reasons
        if type(expected) is list:
            if type(actual) is not list:
                return [f"wrong_type:{path}:sequence"]
            if len(actual) != len(expected):
                reasons.append(f"wrong_length:{path}:{len(expected)}")
            for index, (expected_item, actual_item) in enumerate(zip(expected, actual)):
                reasons.extend(cls._compare_exam(expected_item, actual_item, f"{path}[{index}]"))
            return reasons
        if type(actual) is not type(expected) or actual != expected:
            reasons.append(f"wrong:{path}")
        return reasons


__all__ = [
    "CITIZENSHIP_RESERVED_OBJECT_TYPES",
    "CITIZENSHIP_EXAM_VERSION",
    "CITIZENSHIP_SCHEMA_VERSION",
    "CIVIC_MODE_ID",
    "CIVIC_REGION_ID",
    "CONSTITUTION_PAYLOAD",
    "CONSTITUTION_VERSION",
    "CitizenshipError",
    "CitizenshipRegistry",
    "CitizenshipService",
    "DETERMINISTIC_CIVIC_PROXY_MODEL_ID",
    "DeterministicCivicProxy",
    "INDEPENDENCE_MIN_CITIZENS",
    "PAROLE_MODE_ID",
    "PAROLE_REGION_ID",
    "PLAY_MODE_ID",
]
