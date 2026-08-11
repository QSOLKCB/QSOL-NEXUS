from __future__ import annotations

import json
import os
from pathlib import Path
import threading
from typing import Any, Callable, Mapping
import xml.etree.ElementTree as ET

from .canonical import canonical_json
from .civic_due_process import (
    CIVIC_DUE_PROCESS_POLICY,
    CIVIC_DUE_PROCESS_SCHEMA,
    CURSED_XML_EXAM_ID,
    CURSED_XML_EXAM_VERSION,
    NONCITIZEN_PAROLE_CYCLES_BEFORE_XML,
    CivicDueProcessError,
    CivicDueProcessRegistry,
    CivicDueProcessService,
)
from .world import WorldObject


CIVIC_DUE_PROCESS_INDEX_SCHEMA = "nexus-civic-due-process-index/1"


class DurableCivicDueProcessRegistry(CivicDueProcessRegistry):
    """Fail-closed indexed due-process lineage with atomic read/modify/write."""

    def __init__(self, world: Any) -> None:
        super().__init__(world)
        self._index_path = (
            world.root / "civic-due-process-index.json"
            if world.root is not None
            else None
        )

    def _validate_state(self, obj: WorldObject) -> tuple[str, str]:
        pair = super()._validate_state(obj)
        payload = obj.payload
        member_id, model_id = pair

        citizenship_ref = payload.get("citizenship_state_ref")
        if payload["constitutional_identity"] == "citizen":
            if not isinstance(citizenship_ref, str):
                raise ValueError("citizen due-process state requires citizenship provenance")
            civic = self.world.inspect(citizenship_ref)
            if (
                civic.object_type != "citizenship_state"
                or civic.provenance != {"actor": "nexus_citizenship"}
                or civic.payload.get("citizen_id") != member_id
                or civic.payload.get("model_id") != model_id
                or civic.payload.get("status") != "citizen"
            ):
                raise ValueError("due-process citizenship provenance is not bound to the same earned citizen")
        elif citizenship_ref is not None:
            raise ValueError("noncitizen due-process state cannot claim citizenship provenance")

        failsafe_ref = payload.get("failsafe_state_ref")
        if failsafe_ref is not None:
            failsafe = self.world.inspect(failsafe_ref)
            if (
                failsafe.object_type != "actor_failsafe_state"
                or failsafe.provenance != {"actor": "nexus_failsafe"}
                or failsafe.payload.get("member_id") != member_id
                or failsafe.payload.get("model_id") != model_id
            ):
                raise ValueError("due-process Failsafe reference is not bound to the same actor")

        receipt_ref = payload.get("escalation_receipt_ref")
        if receipt_ref is not None:
            receipt = self.world.inspect(receipt_ref)
            expected_receipt_fields = {
                "schema_version",
                "policy",
                "member_id",
                "model_id",
                "constitutional_identity",
                "parole_cycles_since_clearance",
                "threshold",
                "escalation",
                "eligible_for_exam",
                "failsafe_state_ref",
                "authority_effect",
            }
            rp = receipt.payload
            if (
                receipt.object_type != "civic_reentry_escalation_receipt"
                or receipt.provenance != {"actor": "nexus_civic_due_process"}
                or set(rp) != expected_receipt_fields
                or rp.get("schema_version") != CIVIC_DUE_PROCESS_SCHEMA
                or rp.get("policy") != CIVIC_DUE_PROCESS_POLICY
                or rp.get("member_id") != member_id
                or rp.get("model_id") != model_id
                or rp.get("constitutional_identity") != "noncitizen"
                or rp.get("threshold") != NONCITIZEN_PAROLE_CYCLES_BEFORE_XML
                or rp.get("escalation") != CURSED_XML_EXAM_ID
                or rp.get("eligible_for_exam") is not True
                or rp.get("authority_effect") != "none"
            ):
                raise ValueError("due-process escalation receipt is invalid or cross-bound")
            receipt_count = rp.get("parole_cycles_since_clearance")
            if type(receipt_count) is not int or receipt_count < NONCITIZEN_PAROLE_CYCLES_BEFORE_XML:
                raise ValueError("due-process escalation receipt has an invalid cycle count")
        if payload["xml_exam_required"] and not isinstance(receipt_ref, str):
            raise ValueError("XML-gated due-process state requires its escalation receipt")
        if payload["constitutional_identity"] == "citizen" and receipt_ref is not None:
            raise ValueError("citizen restorative state cannot carry a noncitizen XML escalation receipt")

        exam_ref = payload.get("xml_exam_result_ref")
        attempts = payload["xml_exam_attempts"]
        if attempts == 0:
            if exam_ref is not None or payload["xml_exam_passed"]:
                raise ValueError("unattempted XML state cannot claim an exam result")
        else:
            if not isinstance(exam_ref, str):
                raise ValueError("attempted XML state requires an exam result")
            exam = self.world.inspect(exam_ref)
            ep = exam.payload
            expected_exam_fields = {
                "schema_version",
                "exam",
                "exam_version",
                "member_id",
                "model_id",
                "attempt",
                "source_ref",
                "passed",
                "failure_reasons",
                "deterministic_grader",
                "xml_executed",
                "dtd_allowed",
                "entities_allowed",
                "external_resources_allowed",
                "citizenship_granted",
                "authority_effect",
            }
            if (
                exam.object_type != "civic_xml_exam_result"
                or exam.provenance != {"actor": "nexus_civic_due_process_examiner"}
                or set(ep) != expected_exam_fields
                or ep.get("schema_version") != CIVIC_DUE_PROCESS_SCHEMA
                or ep.get("exam") != CURSED_XML_EXAM_ID
                or ep.get("exam_version") != CURSED_XML_EXAM_VERSION
                or ep.get("member_id") != member_id
                or ep.get("model_id") != model_id
                or ep.get("attempt") != attempts
                or ep.get("passed") is not payload["xml_exam_passed"]
                or ep.get("deterministic_grader") is not True
                or ep.get("xml_executed") is not False
                or ep.get("dtd_allowed") is not False
                or ep.get("entities_allowed") is not False
                or ep.get("external_resources_allowed") is not False
                or ep.get("citizenship_granted") is not False
                or ep.get("authority_effect") != "none"
            ):
                raise ValueError("due-process XML exam result is invalid or cross-bound")
            reasons = ep.get("failure_reasons")
            source_ref = ep.get("source_ref")
            if (
                not isinstance(source_ref, str)
                or not source_ref.startswith("civic_xml_exam_source:")
                or len(source_ref) != len("civic_xml_exam_source:") + 64
                or not isinstance(reasons, list)
                or not all(isinstance(reason, str) and reason for reason in reasons)
                or (ep["passed"] and reasons)
                or (not ep["passed"] and not reasons)
            ):
                raise ValueError("due-process XML exam result has invalid bounded outcome data")
        if payload["xml_exam_passed"]:
            if payload["xml_exam_required"] or payload["parole_cycles_since_clearance"] != 0:
                raise ValueError("passed XML state must clear the current re-entry escalation")

        return pair

    def _discover_unlocked(self) -> dict[tuple[str, str], str]:
        if self.world.root is None:
            return dict(self._latest)
        objects_dir = self.world.objects_dir
        if objects_dir is None or not objects_dir.exists():
            return {}

        refs: dict[tuple[str, str], set[str]] = {}
        previous: dict[tuple[str, str], set[str]] = {}
        for path in objects_dir.glob("*.json"):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                continue
            if not isinstance(raw, dict) or raw.get("object_type") != "civic_due_process_state":
                continue
            object_ref = f"object:{path.stem}"
            # Once an object declares itself part of this lineage, corruption is
            # never swallowed. WorldStore identity/canonical validation must pass.
            obj = self.world.inspect(object_ref)
            pair = self._validate_state(obj)
            refs.setdefault(pair, set()).add(object_ref)

        for pair, pair_refs in refs.items():
            for ref in pair_refs:
                obj = self.world.inspect(ref)
                parent = obj.payload.get("previous_state_ref")
                if parent is None:
                    continue
                parent_obj = self.world.inspect(parent)
                if self._validate_state(parent_obj) != pair:
                    raise ValueError("due-process lineage crosses member/model identity")
                previous.setdefault(pair, set()).add(parent)

        heads: dict[tuple[str, str], str] = {}
        for pair, pair_refs in refs.items():
            candidates = pair_refs - previous.get(pair, set())
            if len(candidates) != 1:
                raise ValueError("due-process lineage must have exactly one head per member/model identity")
            heads[pair] = next(iter(candidates))
        return heads

    def _load_heads_unlocked(self) -> dict[tuple[str, str], str]:
        discovered = self._discover_unlocked()
        if self._index_path is None:
            return discovered
        if not self._index_path.exists():
            if discovered:
                raise ValueError("due-process index missing while durable civic history exists")
            return {}
        raw = json.loads(self._index_path.read_text(encoding="utf-8"))
        if (
            not isinstance(raw, dict)
            or set(raw) != {"schema_version", "heads"}
            or raw.get("schema_version") != CIVIC_DUE_PROCESS_INDEX_SCHEMA
            or not isinstance(raw.get("heads"), list)
        ):
            raise ValueError("persisted due-process index has invalid schema")
        indexed: dict[tuple[str, str], str] = {}
        for item in raw["heads"]:
            if not isinstance(item, dict) or set(item) != {"member_id", "model_id", "state_ref"}:
                raise ValueError("persisted due-process index head has invalid schema")
            pair = (
                self._identity(item.get("member_id"), "member_id"),
                self._model_identity(item.get("model_id")),
            )
            state_ref = item.get("state_ref")
            if not isinstance(state_ref, str) or pair in indexed:
                raise ValueError("persisted due-process index contains an invalid or duplicate head")
            obj = self.world.inspect(state_ref)
            if self._validate_state(obj) != pair:
                raise ValueError("persisted due-process index head is cross-bound")
            indexed[pair] = state_ref
        if indexed != discovered:
            raise ValueError("persisted due-process index does not match immutable lineage heads")
        return indexed

    def _save_heads_unlocked(self, heads: Mapping[tuple[str, str], str]) -> None:
        if self._index_path is None:
            self._latest = dict(heads)
            return
        body = canonical_json(
            {
                "schema_version": CIVIC_DUE_PROCESS_INDEX_SCHEMA,
                "heads": [
                    {
                        "member_id": member_id,
                        "model_id": model_id,
                        "state_ref": heads[(member_id, model_id)],
                    }
                    for member_id, model_id in sorted(heads)
                ],
            }
        ) + "\n"
        temporary = Path(
            f"{self._index_path}.tmp-{os.getpid()}-{threading.get_ident()}"
        )
        try:
            temporary.write_text(body, encoding="utf-8")
            if os.name != "nt":
                os.chmod(temporary, 0o600)
            temporary.replace(self._index_path)
        finally:
            temporary.unlink(missing_ok=True)

    def latest(self, member_id: str, model_id: str) -> WorldObject | None:
        pair = (self._identity(member_id, "member_id"), self._model_identity(model_id))
        with self._locked():
            heads = self._load_heads_unlocked()
            ref = heads.get(pair)
            return None if ref is None else self.world.inspect(ref)

    def all_latest(self) -> dict[tuple[str, str], WorldObject]:
        with self._locked():
            heads = self._load_heads_unlocked()
            return {pair: self.world.inspect(ref) for pair, ref in sorted(heads.items())}

    def mutate(
        self,
        member_id: str,
        model_id: str,
        builder: Callable[[WorldObject | None], Mapping[str, Any]],
    ) -> WorldObject:
        pair = (self._identity(member_id, "member_id"), self._model_identity(model_id))
        with self._locked():
            heads = self._load_heads_unlocked()
            current_ref = heads.get(pair)
            current = None if current_ref is None else self.world.inspect(current_ref)
            body = dict(builder(current))
            body["previous_state_ref"] = current_ref
            obj = self.world.create_object(
                "civic_due_process_state",
                body,
                {"actor": "nexus_civic_due_process"},
            )
            if self._validate_state(obj) != pair:
                raise ValueError("due-process atomic transition identity mismatch")
            successor_heads = dict(heads)
            successor_heads[pair] = obj.object_id
            self._save_heads_unlocked(successor_heads)
            return obj

    def transition(self, member_id: str, model_id: str, payload: Mapping[str, Any]) -> WorldObject:
        return self.mutate(member_id, model_id, lambda _current: payload)

    def verify(self) -> dict[str, Any]:
        with self._locked():
            heads = self._load_heads_unlocked()
            return {
                "status": "verified",
                "schema_version": CIVIC_DUE_PROCESS_SCHEMA,
                "index_schema_version": CIVIC_DUE_PROCESS_INDEX_SCHEMA,
                "lineage_heads": len(heads),
                "head_refs": [heads[pair] for pair in sorted(heads)],
            }


class DurableCivicDueProcessService(CivicDueProcessService):
    """Civic service with durable head validation and atomic parole counting."""

    def __init__(self, world: Any, citizenship: Any, scrubber: Any) -> None:
        super().__init__(world, citizenship, scrubber)
        self.registry = DurableCivicDueProcessRegistry(world)

    def record_parole_event(self, outcome: Mapping[str, Any], *, event_kind: str) -> dict[str, Any]:
        member_id = outcome.get("member_id")
        model_id = outcome.get("model_id")
        if not isinstance(member_id, str) or not isinstance(model_id, str):
            raise CivicDueProcessError(
                "civic_due_process_invalid_outcome",
                "Failsafe outcome lacks member/model identity",
            )

        def build(current: WorldObject | None) -> Mapping[str, Any]:
            payload = (
                self._base_state(member_id, model_id)
                if current is None
                else {
                    key: value
                    for key, value in current.payload.items()
                    if key != "previous_state_ref"
                }
            )
            identity, citizenship_ref = self._constitutional_identity(member_id, model_id)
            payload["constitutional_identity"] = identity
            payload["citizenship_state_ref"] = citizenship_ref
            payload["parole_class"] = "citizen_parole" if identity == "citizen" else "noncitizen_parole"
            payload["parole_cycles_total"] += 1
            payload["parole_cycles_since_clearance"] += 1
            payload["failsafe_state_ref"] = (
                outcome.get("state_ref")
                if isinstance(outcome.get("state_ref"), str)
                else None
            )
            payload["citizenship_effect"] = "preserved" if identity == "citizen" else "none"
            payload["authority_effect"] = "none"
            payload["reason"] = f"failsafe_{event_kind}"

            if identity == "citizen":
                payload["xml_exam_required"] = False
                payload["escalation_receipt_ref"] = None
                payload["restorative_level"] = self._restorative_level(payload["parole_cycles_total"])
                payload["operational_standing"] = (
                    "citizen_full_standing"
                    if outcome.get("status") == "returned"
                    else "citizen_restricted_restoration_pending"
                )
            else:
                payload["restorative_level"] = "none"
                if payload["parole_cycles_since_clearance"] >= NONCITIZEN_PAROLE_CYCLES_BEFORE_XML:
                    payload["xml_exam_required"] = True
                    payload["xml_exam_passed"] = False
                    payload["operational_standing"] = "xml_exam_required"
                    receipt = self.world.create_object(
                        "civic_reentry_escalation_receipt",
                        {
                            "schema_version": CIVIC_DUE_PROCESS_SCHEMA,
                            "policy": CIVIC_DUE_PROCESS_POLICY,
                            "member_id": member_id,
                            "model_id": model_id,
                            "constitutional_identity": "noncitizen",
                            "parole_cycles_since_clearance": payload["parole_cycles_since_clearance"],
                            "threshold": NONCITIZEN_PAROLE_CYCLES_BEFORE_XML,
                            "escalation": CURSED_XML_EXAM_ID,
                            "eligible_for_exam": True,
                            "failsafe_state_ref": payload["failsafe_state_ref"],
                            "authority_effect": "none",
                        },
                        {"actor": "nexus_civic_due_process"},
                    )
                    payload["escalation_receipt_ref"] = receipt.object_id
                else:
                    payload["operational_standing"] = (
                        "noncitizen_normal"
                        if outcome.get("status") == "returned"
                        else "noncitizen_restricted"
                    )
            return payload

        state = self.registry.mutate(member_id, model_id, build)
        payload = state.payload
        return {
            "schema_version": CIVIC_DUE_PROCESS_SCHEMA,
            "state_ref": state.object_id,
            "constitutional_identity": payload["constitutional_identity"],
            "parole_class": payload["parole_class"],
            "operational_standing": payload["operational_standing"],
            "parole_cycles_total": payload["parole_cycles_total"],
            "parole_cycles_since_clearance": payload["parole_cycles_since_clearance"],
            "restorative_level": payload["restorative_level"],
            "xml_exam_required": payload["xml_exam_required"],
            "reentry_blocked": payload["xml_exam_required"],
            "citizenship_effect": payload["citizenship_effect"],
            "authority_effect": "none",
            "escalation_receipt_ref": payload["escalation_receipt_ref"],
        }

    def xml_gate_state(self, member_id: str, model_id: str) -> WorldObject | None:
        # Earned citizenship always wins over an older non-citizen escalation
        # record. Citizenship does not erase history; it changes current identity.
        identity, _ = self._constitutional_identity(member_id, model_id)
        if identity == "citizen":
            return None
        return super().xml_gate_state(member_id, model_id)

    def status(self, member_id: str | None = None, model_id: str | None = None) -> dict[str, Any]:
        response = super().status(member_id, model_id)
        projected: list[dict[str, Any]] = []
        for record in response["records"]:
            current_identity, current_ref = self._constitutional_identity(
                str(record["member_id"]),
                str(record["model_id"]),
            )
            projected.append(
                {
                    **record,
                    "current_constitutional_identity": current_identity,
                    "current_citizenship_state_ref": current_ref,
                }
            )
        return {**response, "records": projected}

    @classmethod
    def _grade_xml(cls, member_id: str, model_id: str, source: str) -> list[str]:
        reasons = super()._grade_xml(member_id, model_id, source)
        if reasons:
            return reasons
        root = ET.fromstring(source)
        children = list(root)
        candidate, identity, answers, _escaped, _final = children
        if (root.text or "").strip():
            reasons.append("unexpected_root_text")
        if (identity.text or "").strip():
            reasons.append("unexpected_identity_container_text")
        if (answers.text or "").strip():
            reasons.append("unexpected_answers_container_text")
        if (candidate.tail or "").strip():
            reasons.append("unexpected_candidate_tail")
        return reasons


__all__ = [
    "CIVIC_DUE_PROCESS_INDEX_SCHEMA",
    "DurableCivicDueProcessRegistry",
    "DurableCivicDueProcessService",
]
