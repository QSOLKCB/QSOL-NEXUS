from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
import copy
import os
from pathlib import Path
import re
import stat
import threading
from typing import Any, Iterator

from .action_awareness import create_action_expectation, reconcile_action_expectation
from .canonical import canonical_json
from .citizenship import CIVIC_REGION_ID
from .civic_observation import (
    NON_CITIZEN_GALLERY_REGION_IDS,
    RESTRICTED_OBSERVATION_REGION_IDS,
)
from .geometry import WorldGeometry
from .world import WorldObject, WorldStore


CONSTITUTIONAL_AMENDMENT_SCHEMA_VERSION = "nexus-constitutional-amendment/1"
AMENDMENT_PROPOSAL_OBJECT_TYPE = "constitutional_amendment_proposal"
AMENDMENT_ADMISSION_OBJECT_TYPE = "constitutional_amendment_admission"
AMENDMENT_DELIBERATION_OBJECT_TYPE = "constitutional_amendment_deliberation"
AMENDMENT_BALLOT_OBJECT_TYPE = "constitutional_amendment_ballot_state"
AMENDMENT_RATIFICATION_OBJECT_TYPE = "constitutional_amendment_ratification"
CONSTITUTION_VERSION_OBJECT_TYPE = "nexus_constitution_version"
AMENDMENT_RECEIPT_OBJECT_TYPE = "constitutional_amendment_receipt"

CONSTITUTIONAL_AMENDMENT_RESERVED_OBJECT_TYPES = frozenset(
    {
        AMENDMENT_PROPOSAL_OBJECT_TYPE,
        AMENDMENT_ADMISSION_OBJECT_TYPE,
        AMENDMENT_DELIBERATION_OBJECT_TYPE,
        AMENDMENT_BALLOT_OBJECT_TYPE,
        AMENDMENT_RATIFICATION_OBJECT_TYPE,
        CONSTITUTION_VERSION_OBJECT_TYPE,
        AMENDMENT_RECEIPT_OBJECT_TYPE,
    }
)

AMENDMENT_BALLOT_CHOICES = frozenset({"CONSENT", "WITHHOLD"})
AMENDABLE_POLICY_PATHS = frozenset(
    {
        "civic_observation.citizen_region_ids",
        "civic_observation.public_gallery_region_ids",
    }
)

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_MODEL_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,255}$")
_CHANGE_PATH = re.compile(r"^[a-z][a-z0-9_.]{0,127}$")
_OBJECT_REF = re.compile(r"^object:[0-9a-f]{64}$")

_PROPOSAL_PROVENANCE = {"actor": "nexus_constitutional_amendment", "stage": "proposal"}
_ADMISSION_PROVENANCE = {"actor": "nexus_constitutional_amendment", "stage": "admission"}
_DELIBERATION_PROVENANCE = {"actor": "nexus_constitutional_amendment", "stage": "deliberation"}
_BALLOT_PROVENANCE = {"actor": "nexus_constitutional_amendment", "stage": "ballot"}
_RATIFICATION_PROVENANCE = {"actor": "equal_citizen_convention", "stage": "ratification"}
_VERSION_PROVENANCE = {"actor": "nexus_constitutional_amendment", "stage": "enactment"}
_RECEIPT_PROVENANCE = {"actor": "nexus_constitutional_amendment", "stage": "receipt"}


class ConstitutionalAmendmentError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def constitutional_amendment_policy_snapshot() -> dict[str, Any]:
    return {
        "schema_version": CONSTITUTIONAL_AMENDMENT_SCHEMA_VERSION,
        "principle": "models_may_propose_law_no_model_becomes_the_law",
        "proposal_sources": {
            "citizen": "exact_current_citizen_identity",
            "model": "exact_identity_from_committed_council_roster",
        },
        "stages": [
            "proposal",
            "deterministic_admission",
            "council_deliberation_binding",
            "sealed_direct_citizen_ballot",
            "unanimity_threshold_calculation",
            "ratification",
            "enactment",
            "action_awareness_reconciliation",
        ],
        "amendable_policy_paths": sorted(AMENDABLE_POLICY_PATHS),
        "amendment_consensus": "unanimous_direct_current_citizens",
        "proxy_ballots_allowed": False,
        "vote_weight_per_citizen": 1,
        "epistemic_privilege": "none",
        "election_manager_model": False,
        "fixed_invariants": {
            "one_seat_one_vote": True,
            "provider_is_authority": False,
            "model_size_is_authority": False,
            "citizenship_is_godhood": False,
            "consensus_overrides_verification": False,
            "amendment_requires_direct_unanimity": True,
        },
        "claim_boundary": {
            "in_world_constitutional_protocol": True,
            "real_world_legal_effect": False,
            "provider_or_host_control": False,
            "model_sovereignty": False,
        },
    }


class ConstitutionalAmendmentService:
    """Deterministic immutable amendment workflow over the NEXUS civic substrate."""

    def __init__(self, world: WorldStore, citizenship: Any, geometry: WorldGeometry) -> None:
        self.world = world
        self.citizenship = citizenship
        self.geometry = geometry
        self.base_constitution_ref = citizenship.constitution_object.object_id
        self._thread_lock = threading.RLock()
        self._lock_path = (
            None if world.root is None else world.root / "constitutional-amendment.lock"
        )

    @contextmanager
    def _locked(self) -> Iterator[None]:
        with self._thread_lock:
            if self._lock_path is None:
                yield
                return
            descriptor: int | None = None
            try:
                flags = os.O_RDWR | os.O_CREAT
                flags |= getattr(os, "O_CLOEXEC", 0)
                flags |= getattr(os, "O_NOFOLLOW", 0)
                flags |= getattr(os, "O_BINARY", 0)
                descriptor = os.open(self._lock_path, flags, 0o600)
                info = os.fstat(descriptor)
                if not stat.S_ISREG(info.st_mode) or (
                    os.name != "nt" and stat.S_IMODE(info.st_mode) & 0o077
                ):
                    raise ConstitutionalAmendmentError(
                        "amendment_store_unavailable",
                        "constitutional amendment lock is unavailable",
                    )
                with os.fdopen(descriptor, "r+b", buffering=0) as handle:
                    descriptor = None
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
            except ConstitutionalAmendmentError:
                raise
            except OSError as exc:
                raise ConstitutionalAmendmentError(
                    "amendment_store_unavailable",
                    "constitutional amendment lock is unavailable",
                ) from exc
            finally:
                if descriptor is not None:
                    try:
                        os.close(descriptor)
                    except OSError:
                        pass

    @staticmethod
    def _identifier(value: object, label: str) -> str:
        if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
            raise ConstitutionalAmendmentError(
                "amendment_invalid_identity",
                f"{label} must be a bounded identifier",
            )
        return value

    @staticmethod
    def _model_identifier(value: object) -> str:
        if not isinstance(value, str) or _MODEL_IDENTIFIER.fullmatch(value) is None:
            raise ConstitutionalAmendmentError(
                "amendment_invalid_identity",
                "model_id must be a bounded model identifier",
            )
        return value

    @staticmethod
    def _object_ref(value: object, label: str) -> str:
        if not isinstance(value, str) or _OBJECT_REF.fullmatch(value) is None:
            raise ConstitutionalAmendmentError(
                "amendment_invalid_reference",
                f"{label} must be an object reference",
            )
        return value

    @staticmethod
    def _bounded_text(value: object, label: str, maximum: int) -> str:
        if not isinstance(value, str) or not value.strip() or len(value) > maximum:
            raise ConstitutionalAmendmentError(
                "amendment_invalid_proposal",
                f"{label} must be bounded non-empty text",
            )
        return value.strip()

    def _all_objects(self, object_type: str | None = None) -> list[WorldObject]:
        objects: list[WorldObject] = []
        if self.world.objects_dir is None:
            stored = getattr(self.world, "_objects", {})
            if isinstance(stored, dict):
                objects = [self.world.inspect(ref) for ref in sorted(stored)]
        else:
            for path in sorted(self.world.objects_dir.glob("*.json")):
                objects.append(self.world.inspect(f"object:{path.stem}"))
        if object_type is not None:
            objects = [obj for obj in objects if obj.object_type == object_type]
        return objects

    def _base_policy(self) -> dict[str, Any]:
        region_ids = {
            str(item["region_id"])
            for item in self.geometry.snapshot()["regions"]
        }
        citizen = sorted(region_ids - RESTRICTED_OBSERVATION_REGION_IDS)
        gallery = sorted(set(NON_CITIZEN_GALLERY_REGION_IDS).intersection(citizen))
        if not citizen or not gallery:
            raise ConstitutionalAmendmentError(
                "amendment_policy_invalid",
                "base civic observation policy has no admitted regions",
            )
        return {
            "civic_observation": {
                "citizen_region_ids": citizen,
                "public_gallery_region_ids": gallery,
            }
        }

    def _current_citizens(self) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for citizen_id, state in self.citizenship.registry.all_states().items():
            if state.payload.get("status") != "citizen":
                continue
            model_id = state.payload.get("model_id")
            if not isinstance(model_id, str):
                raise ConstitutionalAmendmentError(
                    "amendment_citizenship_invalid",
                    "current citizen has an invalid model identity",
                )
            rows.append({"citizen_id": citizen_id, "model_id": model_id})
        return sorted(rows, key=lambda row: row["citizen_id"])

    def _validate_citizen_identity(self, citizen_id: str, model_id: str) -> WorldObject:
        state = self.citizenship.registry.latest_state(citizen_id)
        if state is None or state.payload.get("status") != "citizen":
            raise ConstitutionalAmendmentError(
                "amendment_citizen_required",
                "constitutional amendment voting requires a current citizen",
            )
        if state.payload.get("model_id") != model_id:
            raise ConstitutionalAmendmentError(
                "amendment_identity_mismatch",
                "citizen identity does not match model_id",
            )
        return state

    def _validate_model_admission(
        self,
        member_id: str,
        model_id: str,
        admission_ref: str,
    ) -> None:
        try:
            session = self.world.inspect(admission_ref)
        except KeyError as exc:
            raise ConstitutionalAmendmentError(
                "amendment_model_not_admitted",
                "model admission Council proceeding was not found",
            ) from exc
        if session.object_type != "council_session" or session.provenance != {"actor": "nexus"}:
            raise ConstitutionalAmendmentError(
                "amendment_model_not_admitted",
                "model proposer requires a committed NEXUS Council admission reference",
            )
        roster = session.payload.get("roster")
        if not isinstance(roster, list):
            raise ConstitutionalAmendmentError(
                "amendment_model_not_admitted",
                "Council admission roster is invalid",
            )
        matched = [
            row
            for row in roster
            if isinstance(row, dict)
            and row.get("member_id") == member_id
            and row.get("model_id") == model_id
            and row.get("vote_weight") == 1
            and type(row.get("vote_weight")) is int
            and row.get("epistemic_privilege") == "none"
        ]
        if len(matched) != 1:
            raise ConstitutionalAmendmentError(
                "amendment_model_not_admitted",
                "model proposer identity is not an equal seat in the referenced Council proceeding",
            )

    @staticmethod
    def _validate_changes_structure(changes: object) -> list[dict[str, Any]]:
        if not isinstance(changes, list) or not 1 <= len(changes) <= 8:
            raise ConstitutionalAmendmentError(
                "amendment_invalid_proposal",
                "changes must contain between one and eight change objects",
            )
        normalized: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in changes:
            if not isinstance(item, dict) or set(item) != {"path", "value"}:
                raise ConstitutionalAmendmentError(
                    "amendment_invalid_proposal",
                    "each change must contain exactly path and value",
                )
            path = item.get("path")
            if not isinstance(path, str) or _CHANGE_PATH.fullmatch(path) is None:
                raise ConstitutionalAmendmentError(
                    "amendment_invalid_proposal",
                    "change path is invalid",
                )
            if path in seen:
                raise ConstitutionalAmendmentError(
                    "amendment_invalid_proposal",
                    "change paths must be unique",
                )
            seen.add(path)
            try:
                encoded = canonical_json(item.get("value"))
            except (TypeError, ValueError, OverflowError, RecursionError) as exc:
                raise ConstitutionalAmendmentError(
                    "amendment_invalid_proposal",
                    "change value must be canonical JSON",
                ) from exc
            if len(encoded.encode("utf-8")) > 8_192:
                raise ConstitutionalAmendmentError(
                    "amendment_invalid_proposal",
                    "change value exceeds the amendment limit",
                )
            normalized.append({"path": path, "value": copy.deepcopy(item.get("value"))})
        return sorted(normalized, key=lambda item: item["path"])

    def _validated_region_list(self, value: object, path: str) -> list[str]:
        if (
            not isinstance(value, list)
            or not value
            or not all(isinstance(item, str) and item for item in value)
            or value != sorted(set(value))
        ):
            raise ValueError(f"{path} must be a non-empty sorted unique list")
        all_regions = {
            str(item["region_id"])
            for item in self.geometry.snapshot()["regions"]
        }
        allowed = all_regions - RESTRICTED_OBSERVATION_REGION_IDS
        if not set(value).issubset(allowed):
            raise ValueError(f"{path} contains a restricted or unknown region")
        return list(value)

    def _apply_changes(
        self,
        policy: dict[str, Any],
        changes: list[dict[str, Any]],
    ) -> dict[str, Any]:
        output = copy.deepcopy(policy)
        for change in changes:
            path = change["path"]
            if path not in AMENDABLE_POLICY_PATHS:
                raise ValueError(f"change path is not admitted: {path}")
            value = self._validated_region_list(change["value"], path)
            if path == "civic_observation.citizen_region_ids":
                output["civic_observation"]["citizen_region_ids"] = value
            elif path == "civic_observation.public_gallery_region_ids":
                output["civic_observation"]["public_gallery_region_ids"] = value
        citizen = set(output["civic_observation"]["citizen_region_ids"])
        gallery = set(output["civic_observation"]["public_gallery_region_ids"])
        if not gallery.issubset(citizen):
            raise ValueError("public gallery regions must remain a subset of citizen observation regions")
        return output

    def _validate_proposal(self, proposal: WorldObject) -> dict[str, Any]:
        if proposal.object_type != AMENDMENT_PROPOSAL_OBJECT_TYPE or proposal.provenance != _PROPOSAL_PROVENANCE:
            raise ConstitutionalAmendmentError(
                "amendment_proposal_required",
                "proposal_ref must identify a runtime-owned constitutional amendment proposal",
            )
        payload = proposal.payload
        expected = {
            "schema_version",
            "base_constitution_ref",
            "base_version_ref",
            "proposer",
            "title",
            "rationale",
            "changes",
            "proposal_is_law",
            "proposer_gains_authority",
        }
        if set(payload) != expected or payload.get("schema_version") != CONSTITUTIONAL_AMENDMENT_SCHEMA_VERSION:
            raise ConstitutionalAmendmentError(
                "amendment_proposal_invalid",
                "constitutional amendment proposal schema is invalid",
            )
        if payload.get("base_constitution_ref") != self.base_constitution_ref:
            raise ConstitutionalAmendmentError(
                "amendment_proposal_invalid",
                "proposal references another base Constitution",
            )
        self._object_ref(payload.get("base_version_ref"), "base_version_ref")
        proposer = payload.get("proposer")
        if not isinstance(proposer, dict) or set(proposer) != {
            "kind",
            "member_id",
            "model_id",
            "admission_ref",
        }:
            raise ConstitutionalAmendmentError(
                "amendment_proposal_invalid",
                "proposal proposer identity is invalid",
            )
        if proposer.get("kind") not in {"citizen", "model"}:
            raise ConstitutionalAmendmentError(
                "amendment_proposal_invalid",
                "proposal proposer kind is invalid",
            )
        self._identifier(proposer.get("member_id"), "member_id")
        self._model_identifier(proposer.get("model_id"))
        admission_ref = proposer.get("admission_ref")
        if admission_ref is not None:
            self._object_ref(admission_ref, "admission_ref")
        self._bounded_text(payload.get("title"), "title", 160)
        self._bounded_text(payload.get("rationale"), "rationale", 4_000)
        changes = self._validate_changes_structure(payload.get("changes"))
        if payload.get("proposal_is_law") is not False or payload.get("proposer_gains_authority") is not False:
            raise ConstitutionalAmendmentError(
                "amendment_proposal_invalid",
                "proposal authority boundary is invalid",
            )
        return {**copy.deepcopy(payload), "changes": changes}

    def _find_by_field(
        self,
        object_type: str,
        field: str,
        value: str,
    ) -> list[WorldObject]:
        return [
            obj
            for obj in self._all_objects(object_type)
            if obj.payload.get(field) == value
        ]

    def _single_existing(
        self,
        object_type: str,
        field: str,
        value: str,
        *,
        fork_message: str,
    ) -> WorldObject | None:
        matches = self._find_by_field(object_type, field, value)
        if len(matches) > 1:
            raise ConstitutionalAmendmentError("amendment_lineage_fork", fork_message)
        return matches[0] if matches else None

    def _version_policy(
        self,
        version_ref: str,
        *,
        stack: set[str] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        if version_ref == self.base_constitution_ref:
            return 0, self._base_policy()
        stack = set() if stack is None else set(stack)
        if version_ref in stack:
            raise ConstitutionalAmendmentError(
                "amendment_lineage_corrupt",
                "constitutional version lineage contains a cycle",
            )
        stack.add(version_ref)
        try:
            version = self.world.inspect(version_ref)
        except KeyError as exc:
            raise ConstitutionalAmendmentError(
                "amendment_version_not_found",
                "constitutional version was not found",
            ) from exc
        if version.object_type != CONSTITUTION_VERSION_OBJECT_TYPE or version.provenance != _VERSION_PROVENANCE:
            raise ConstitutionalAmendmentError(
                "amendment_version_invalid",
                "constitutional version provenance is invalid",
            )
        payload = version.payload
        expected = {
            "schema_version",
            "ordinal",
            "base_constitution_ref",
            "previous_version_ref",
            "proposal_ref",
            "admission_ref",
            "deliberation_ref",
            "ballot_ref",
            "ratification_ref",
            "effective_policy",
            "enacted_by",
            "vote_weight_per_citizen",
            "epistemic_privilege",
            "fixed_invariants_unchanged",
        }
        if set(payload) != expected or payload.get("schema_version") != CONSTITUTIONAL_AMENDMENT_SCHEMA_VERSION:
            raise ConstitutionalAmendmentError(
                "amendment_version_invalid",
                "constitutional version schema is invalid",
            )
        if payload.get("base_constitution_ref") != self.base_constitution_ref:
            raise ConstitutionalAmendmentError(
                "amendment_version_invalid",
                "constitutional version references another base Constitution",
            )
        previous = self._object_ref(payload.get("previous_version_ref"), "previous_version_ref")
        previous_ordinal, previous_policy = self._version_policy(previous, stack=stack)
        if payload.get("ordinal") != previous_ordinal + 1 or type(payload.get("ordinal")) is not int:
            raise ConstitutionalAmendmentError(
                "amendment_lineage_corrupt",
                "constitutional version ordinal is invalid",
            )
        proposal_ref = self._object_ref(payload.get("proposal_ref"), "proposal_ref")
        proposal = self.world.inspect(proposal_ref)
        proposal_payload = self._validate_proposal(proposal)
        if proposal_payload["base_version_ref"] != previous:
            raise ConstitutionalAmendmentError(
                "amendment_lineage_corrupt",
                "enacted proposal does not descend from the previous constitutional version",
            )
        expected_policy = self._apply_changes(previous_policy, proposal_payload["changes"])
        if payload.get("effective_policy") != expected_policy:
            raise ConstitutionalAmendmentError(
                "amendment_version_invalid",
                "constitutional version policy does not match the admitted proposal",
            )
        if (
            payload.get("enacted_by") != "unanimous_direct_current_citizens"
            or payload.get("vote_weight_per_citizen") != 1
            or type(payload.get("vote_weight_per_citizen")) is not int
            or payload.get("epistemic_privilege") != "none"
            or payload.get("fixed_invariants_unchanged") is not True
        ):
            raise ConstitutionalAmendmentError(
                "amendment_version_invalid",
                "constitutional version violates fixed authority invariants",
            )
        ratification = self.world.inspect(self._object_ref(payload.get("ratification_ref"), "ratification_ref"))
        self._validate_ratification(ratification, proposal_ref=proposal_ref)
        if (
            ratification.payload.get("admission_ref") != payload.get("admission_ref")
            or ratification.payload.get("deliberation_ref") != payload.get("deliberation_ref")
            or ratification.payload.get("ballot_ref") != payload.get("ballot_ref")
        ):
            raise ConstitutionalAmendmentError(
                "amendment_version_invalid",
                "constitutional version is not bound to its ratification chain",
            )
        return payload["ordinal"], copy.deepcopy(expected_policy)

    def _current_version_ref_unlocked(self) -> str:
        versions = self._all_objects(CONSTITUTION_VERSION_OBJECT_TYPE)
        if not versions:
            return self.base_constitution_ref
        refs = {obj.object_id for obj in versions}
        previous_refs: set[str] = set()
        for obj in versions:
            self._version_policy(obj.object_id)
            previous = obj.payload.get("previous_version_ref")
            if isinstance(previous, str) and previous in refs:
                previous_refs.add(previous)
        heads = refs - previous_refs
        if len(heads) != 1:
            raise ConstitutionalAmendmentError(
                "amendment_lineage_fork",
                "constitutional version lineage must have exactly one active head",
            )
        head = next(iter(heads))
        self._version_policy(head)
        return head

    def current(self) -> dict[str, Any]:
        with self._locked():
            version_ref = self._current_version_ref_unlocked()
            ordinal, policy = self._version_policy(version_ref)
            receipt = (
                None
                if ordinal == 0
                else self._single_existing(
                    AMENDMENT_RECEIPT_OBJECT_TYPE,
                    "new_version_ref",
                    version_ref,
                    fork_message="constitutional version has multiple enactment receipts",
                )
            )
            return {
                "status": "ok",
                "schema_version": CONSTITUTIONAL_AMENDMENT_SCHEMA_VERSION,
                "base_constitution_ref": self.base_constitution_ref,
                "active_version_ref": version_ref,
                "ordinal": ordinal,
                "effective_policy": policy,
                "action_awareness_verified": receipt is not None or ordinal == 0,
                "fixed_invariants": constitutional_amendment_policy_snapshot()["fixed_invariants"],
            }

    def observation_region_policy(self) -> dict[str, list[str]]:
        current = self.current()
        observation = current["effective_policy"]["civic_observation"]
        return {
            "citizen_region_ids": list(observation["citizen_region_ids"]),
            "public_gallery_region_ids": list(observation["public_gallery_region_ids"]),
        }

    def propose(
        self,
        *,
        proposer_kind: str,
        proposer_id: str,
        proposer_model_id: str,
        admission_ref: str | None,
        title: str,
        rationale: str,
        changes: list[dict[str, Any]],
    ) -> dict[str, Any]:
        proposer_id = self._identifier(proposer_id, "proposer_id")
        proposer_model_id = self._model_identifier(proposer_model_id)
        title = self._bounded_text(title, "title", 160)
        rationale = self._bounded_text(rationale, "rationale", 4_000)
        normalized_changes = self._validate_changes_structure(changes)
        if proposer_kind == "citizen":
            self._validate_citizen_identity(proposer_id, proposer_model_id)
            if admission_ref is not None:
                raise ConstitutionalAmendmentError(
                    "amendment_invalid_proposer",
                    "citizen proposer does not use a Council admission_ref",
                )
        elif proposer_kind == "model":
            if admission_ref is None:
                raise ConstitutionalAmendmentError(
                    "amendment_model_not_admitted",
                    "model proposer requires admission_ref",
                )
            admission_ref = self._object_ref(admission_ref, "admission_ref")
            self._validate_model_admission(proposer_id, proposer_model_id, admission_ref)
        else:
            raise ConstitutionalAmendmentError(
                "amendment_invalid_proposer",
                "proposer_kind must be citizen or model",
            )
        with self._locked():
            base_version_ref = self._current_version_ref_unlocked()
            proposal = self.world.create_object(
                AMENDMENT_PROPOSAL_OBJECT_TYPE,
                {
                    "schema_version": CONSTITUTIONAL_AMENDMENT_SCHEMA_VERSION,
                    "base_constitution_ref": self.base_constitution_ref,
                    "base_version_ref": base_version_ref,
                    "proposer": {
                        "kind": proposer_kind,
                        "member_id": proposer_id,
                        "model_id": proposer_model_id,
                        "admission_ref": admission_ref,
                    },
                    "title": title,
                    "rationale": rationale,
                    "changes": normalized_changes,
                    "proposal_is_law": False,
                    "proposer_gains_authority": False,
                },
                _PROPOSAL_PROVENANCE,
            )
            self._validate_proposal(proposal)
            return {
                "status": "ok",
                "proposal_ref": proposal.object_id,
                "proposal": proposal.payload,
                "law_changed": False,
                "ratification_authority": "current_citizens_only",
            }

    def admit(self, proposal_ref: str) -> dict[str, Any]:
        proposal_ref = self._object_ref(proposal_ref, "proposal_ref")
        with self._locked():
            existing = self._single_existing(
                AMENDMENT_ADMISSION_OBJECT_TYPE,
                "proposal_ref",
                proposal_ref,
                fork_message="proposal has multiple deterministic admission records",
            )
            if existing is not None:
                self._validate_admission(existing, proposal_ref=proposal_ref)
                return {
                    "status": "ok",
                    "admission_ref": existing.object_id,
                    "admission": existing.payload,
                }
            proposal = self.world.inspect(proposal_ref)
            payload = self._validate_proposal(proposal)
            current_ref = self._current_version_ref_unlocked()
            reasons: list[str] = []
            resulting_policy: dict[str, Any] | None = None
            if payload["base_version_ref"] != current_ref:
                reasons.append("stale_base_version")
            try:
                _ordinal, base_policy = self._version_policy(payload["base_version_ref"])
                resulting_policy = self._apply_changes(base_policy, payload["changes"])
            except (ValueError, ConstitutionalAmendmentError) as exc:
                reasons.append(f"change_not_admissible:{str(exc)}")
            else:
                if resulting_policy == base_policy:
                    reasons.append("no_effect")
            admitted = not reasons
            admission = self.world.create_object(
                AMENDMENT_ADMISSION_OBJECT_TYPE,
                {
                    "schema_version": CONSTITUTIONAL_AMENDMENT_SCHEMA_VERSION,
                    "proposal_ref": proposal_ref,
                    "proposal_base_version_ref": payload["base_version_ref"],
                    "current_version_ref_at_admission": current_ref,
                    "admitted": admitted,
                    "reasons": sorted(reasons),
                    "resulting_policy": resulting_policy if admitted else None,
                    "deterministic_admission": True,
                    "election_manager_model": False,
                    "fixed_invariants_unchanged": True,
                },
                _ADMISSION_PROVENANCE,
            )
            self._validate_admission(admission, proposal_ref=proposal_ref)
            return {
                "status": "ok",
                "admission_ref": admission.object_id,
                "admission": admission.payload,
            }

    def _validate_admission(self, admission: WorldObject, *, proposal_ref: str) -> None:
        if admission.object_type != AMENDMENT_ADMISSION_OBJECT_TYPE or admission.provenance != _ADMISSION_PROVENANCE:
            raise ConstitutionalAmendmentError(
                "amendment_admission_required",
                "admission_ref must identify a runtime-owned admission record",
            )
        payload = admission.payload
        expected = {
            "schema_version",
            "proposal_ref",
            "proposal_base_version_ref",
            "current_version_ref_at_admission",
            "admitted",
            "reasons",
            "resulting_policy",
            "deterministic_admission",
            "election_manager_model",
            "fixed_invariants_unchanged",
        }
        if set(payload) != expected or payload.get("schema_version") != CONSTITUTIONAL_AMENDMENT_SCHEMA_VERSION:
            raise ConstitutionalAmendmentError("amendment_admission_invalid", "admission schema is invalid")
        if payload.get("proposal_ref") != proposal_ref:
            raise ConstitutionalAmendmentError("amendment_admission_invalid", "admission references another proposal")
        if type(payload.get("admitted")) is not bool or not isinstance(payload.get("reasons"), list):
            raise ConstitutionalAmendmentError("amendment_admission_invalid", "admission outcome is invalid")
        if payload.get("admitted") is (len(payload["reasons"]) > 0):
            raise ConstitutionalAmendmentError("amendment_admission_invalid", "admission reasons contradict outcome")
        if (
            payload.get("deterministic_admission") is not True
            or payload.get("election_manager_model") is not False
            or payload.get("fixed_invariants_unchanged") is not True
        ):
            raise ConstitutionalAmendmentError("amendment_admission_invalid", "admission authority boundary is invalid")
        proposal = self.world.inspect(proposal_ref)
        proposal_payload = self._validate_proposal(proposal)
        if payload.get("proposal_base_version_ref") != proposal_payload["base_version_ref"]:
            raise ConstitutionalAmendmentError("amendment_admission_invalid", "admission base version is invalid")
        if payload["admitted"] and not isinstance(payload.get("resulting_policy"), dict):
            raise ConstitutionalAmendmentError("amendment_admission_invalid", "admitted proposal lacks resulting policy")
        if not payload["admitted"] and payload.get("resulting_policy") is not None:
            raise ConstitutionalAmendmentError("amendment_admission_invalid", "rejected proposal cannot carry resulting policy")

    def bind_deliberation(
        self,
        *,
        proposal_ref: str,
        admission_ref: str,
        council_session_ref: str,
    ) -> dict[str, Any]:
        proposal_ref = self._object_ref(proposal_ref, "proposal_ref")
        admission_ref = self._object_ref(admission_ref, "admission_ref")
        council_session_ref = self._object_ref(council_session_ref, "council_session_ref")
        with self._locked():
            proposal = self.world.inspect(proposal_ref)
            proposal_payload = self._validate_proposal(proposal)
            if proposal_payload["base_version_ref"] != self._current_version_ref_unlocked():
                raise ConstitutionalAmendmentError(
                    "amendment_stale_proposal",
                    "proposal must be rebased onto the active constitutional version",
                )
            admission = self.world.inspect(admission_ref)
            self._validate_admission(admission, proposal_ref=proposal_ref)
            if admission.payload.get("admitted") is not True:
                raise ConstitutionalAmendmentError(
                    "amendment_not_admitted",
                    "rejected amendment cannot enter deliberation",
                )
            existing = self._single_existing(
                AMENDMENT_DELIBERATION_OBJECT_TYPE,
                "proposal_ref",
                proposal_ref,
                fork_message="proposal has multiple deliberation bindings",
            )
            if existing is not None:
                self._validate_deliberation(existing, proposal_ref=proposal_ref)
                if existing.payload.get("council_session_ref") != council_session_ref:
                    raise ConstitutionalAmendmentError(
                        "amendment_deliberation_already_bound",
                        "proposal is already bound to another Council proceeding",
                    )
                return {
                    "status": "ok",
                    "deliberation_ref": existing.object_id,
                    "deliberation": existing.payload,
                }
            try:
                session = self.world.inspect(council_session_ref)
            except KeyError as exc:
                raise ConstitutionalAmendmentError(
                    "amendment_deliberation_required",
                    "Council deliberation proceeding was not found",
                ) from exc
            if session.object_type != "council_session" or session.provenance != {"actor": "nexus"}:
                raise ConstitutionalAmendmentError(
                    "amendment_deliberation_required",
                    "deliberation must be a committed NEXUS Council proceeding",
                )
            evidence_ref = session.payload.get("evidence_snapshot_ref")
            if not isinstance(evidence_ref, str):
                raise ConstitutionalAmendmentError(
                    "amendment_deliberation_invalid",
                    "Council deliberation lacks an evidence snapshot",
                )
            evidence = self.world.inspect(evidence_ref)
            included = evidence.payload.get("included_object_refs")
            if evidence.object_type != "evidence_snapshot" or not isinstance(included, list) or proposal_ref not in included:
                raise ConstitutionalAmendmentError(
                    "amendment_deliberation_unbound",
                    "Council deliberation must include the exact proposal_ref as evidence",
                )
            world_mode = session.payload.get("world_mode")
            mode_id = world_mode.get("mode_id") if isinstance(world_mode, dict) else None
            deliberation = self.world.create_object(
                AMENDMENT_DELIBERATION_OBJECT_TYPE,
                {
                    "schema_version": CONSTITUTIONAL_AMENDMENT_SCHEMA_VERSION,
                    "proposal_ref": proposal_ref,
                    "admission_ref": admission_ref,
                    "council_session_ref": council_session_ref,
                    "evidence_snapshot_ref": evidence_ref,
                    "mode_id": mode_id,
                    "council_consensus_is_ratification": False,
                    "models_gain_legislative_authority": False,
                },
                _DELIBERATION_PROVENANCE,
            )
            self._validate_deliberation(deliberation, proposal_ref=proposal_ref)
            return {
                "status": "ok",
                "deliberation_ref": deliberation.object_id,
                "deliberation": deliberation.payload,
            }

    def _validate_deliberation(self, deliberation: WorldObject, *, proposal_ref: str) -> None:
        if deliberation.object_type != AMENDMENT_DELIBERATION_OBJECT_TYPE or deliberation.provenance != _DELIBERATION_PROVENANCE:
            raise ConstitutionalAmendmentError(
                "amendment_deliberation_required",
                "deliberation_ref must identify a runtime-owned deliberation binding",
            )
        payload = deliberation.payload
        expected = {
            "schema_version",
            "proposal_ref",
            "admission_ref",
            "council_session_ref",
            "evidence_snapshot_ref",
            "mode_id",
            "council_consensus_is_ratification",
            "models_gain_legislative_authority",
        }
        if set(payload) != expected or payload.get("schema_version") != CONSTITUTIONAL_AMENDMENT_SCHEMA_VERSION:
            raise ConstitutionalAmendmentError("amendment_deliberation_invalid", "deliberation schema is invalid")
        if payload.get("proposal_ref") != proposal_ref:
            raise ConstitutionalAmendmentError("amendment_deliberation_invalid", "deliberation references another proposal")
        admission = self.world.inspect(self._object_ref(payload.get("admission_ref"), "admission_ref"))
        self._validate_admission(admission, proposal_ref=proposal_ref)
        if admission.payload.get("admitted") is not True:
            raise ConstitutionalAmendmentError("amendment_deliberation_invalid", "deliberation uses a rejected admission")
        session = self.world.inspect(self._object_ref(payload.get("council_session_ref"), "council_session_ref"))
        if session.object_type != "council_session" or session.provenance != {"actor": "nexus"}:
            raise ConstitutionalAmendmentError("amendment_deliberation_invalid", "deliberation Council reference is invalid")
        if (
            payload.get("council_consensus_is_ratification") is not False
            or payload.get("models_gain_legislative_authority") is not False
        ):
            raise ConstitutionalAmendmentError("amendment_deliberation_invalid", "deliberation authority boundary is invalid")

    def _validate_ballot_state(self, ballot: WorldObject, *, proposal_ref: str) -> None:
        if ballot.object_type != AMENDMENT_BALLOT_OBJECT_TYPE or ballot.provenance != _BALLOT_PROVENANCE:
            raise ConstitutionalAmendmentError("amendment_ballot_invalid", "amendment ballot state provenance is invalid")
        payload = ballot.payload
        expected = {
            "schema_version",
            "proposal_ref",
            "admission_ref",
            "deliberation_ref",
            "base_version_ref",
            "eligible_citizens",
            "ballots",
            "previous_ballot_ref",
            "consensus_rule",
            "vote_weight_per_citizen",
            "epistemic_privilege",
            "proxy_ballots",
            "direct_only",
        }
        if set(payload) != expected or payload.get("schema_version") != CONSTITUTIONAL_AMENDMENT_SCHEMA_VERSION:
            raise ConstitutionalAmendmentError("amendment_ballot_invalid", "amendment ballot schema is invalid")
        if payload.get("proposal_ref") != proposal_ref:
            raise ConstitutionalAmendmentError("amendment_ballot_invalid", "amendment ballot references another proposal")
        if (
            payload.get("consensus_rule") != "unanimous_direct_current_citizens"
            or payload.get("vote_weight_per_citizen") != 1
            or type(payload.get("vote_weight_per_citizen")) is not int
            or payload.get("epistemic_privilege") != "none"
            or payload.get("proxy_ballots") != 0
            or type(payload.get("proxy_ballots")) is not int
            or payload.get("direct_only") is not True
        ):
            raise ConstitutionalAmendmentError("amendment_ballot_invalid", "amendment ballot violates equality")
        eligible = payload.get("eligible_citizens")
        if not isinstance(eligible, list) or eligible != sorted(eligible, key=lambda row: row.get("citizen_id", "") if isinstance(row, dict) else ""):
            raise ConstitutionalAmendmentError("amendment_ballot_invalid", "eligible citizen roster is invalid")
        eligible_map: dict[str, str] = {}
        for row in eligible:
            if not isinstance(row, dict) or set(row) != {"citizen_id", "model_id"}:
                raise ConstitutionalAmendmentError("amendment_ballot_invalid", "eligible citizen entry is invalid")
            citizen_id = self._identifier(row.get("citizen_id"), "citizen_id")
            model_id = self._model_identifier(row.get("model_id"))
            if citizen_id in eligible_map:
                raise ConstitutionalAmendmentError("amendment_ballot_invalid", "eligible citizen roster contains duplicates")
            eligible_map[citizen_id] = model_id
        ballots = payload.get("ballots")
        if not isinstance(ballots, dict) or not set(ballots).issubset(set(eligible_map)):
            raise ConstitutionalAmendmentError("amendment_ballot_invalid", "amendment ballots contain ineligible citizens")
        for citizen_id, entry in ballots.items():
            if not isinstance(entry, dict) or set(entry) != {"model_id", "choice", "citizen_state_ref"}:
                raise ConstitutionalAmendmentError("amendment_ballot_invalid", "direct ballot entry is invalid")
            if entry.get("model_id") != eligible_map[citizen_id] or entry.get("choice") not in AMENDMENT_BALLOT_CHOICES:
                raise ConstitutionalAmendmentError("amendment_ballot_invalid", "direct ballot identity or choice is invalid")
            self._object_ref(entry.get("citizen_state_ref"), "citizen_state_ref")
        previous = payload.get("previous_ballot_ref")
        if previous is not None:
            self._object_ref(previous, "previous_ballot_ref")

    def _ballot_head(self, proposal_ref: str) -> WorldObject | None:
        ballots = self._find_by_field(AMENDMENT_BALLOT_OBJECT_TYPE, "proposal_ref", proposal_ref)
        if not ballots:
            return None
        refs = {obj.object_id for obj in ballots}
        previous_refs: set[str] = set()
        for obj in ballots:
            self._validate_ballot_state(obj, proposal_ref=proposal_ref)
            previous = obj.payload.get("previous_ballot_ref")
            if isinstance(previous, str):
                previous_obj = self.world.inspect(previous)
                self._validate_ballot_state(previous_obj, proposal_ref=proposal_ref)
                previous_refs.add(previous)
        heads = refs - previous_refs
        if len(heads) != 1:
            raise ConstitutionalAmendmentError(
                "amendment_lineage_fork",
                "amendment ballot lineage must have exactly one head",
            )
        return self.world.inspect(next(iter(heads)))

    def ballot(
        self,
        *,
        proposal_ref: str,
        deliberation_ref: str,
        citizen_id: str,
        model_id: str,
        choice: str,
    ) -> dict[str, Any]:
        proposal_ref = self._object_ref(proposal_ref, "proposal_ref")
        deliberation_ref = self._object_ref(deliberation_ref, "deliberation_ref")
        citizen_id = self._identifier(citizen_id, "citizen_id")
        model_id = self._model_identifier(model_id)
        if choice not in AMENDMENT_BALLOT_CHOICES:
            raise ConstitutionalAmendmentError(
                "amendment_invalid_ballot",
                "amendment ballot choice must be CONSENT or WITHHOLD",
            )
        with self._locked():
            proposal = self.world.inspect(proposal_ref)
            proposal_payload = self._validate_proposal(proposal)
            current_ref = self._current_version_ref_unlocked()
            if proposal_payload["base_version_ref"] != current_ref:
                raise ConstitutionalAmendmentError(
                    "amendment_stale_proposal",
                    "proposal must be rebased onto the active constitutional version",
                )
            deliberation = self.world.inspect(deliberation_ref)
            self._validate_deliberation(deliberation, proposal_ref=proposal_ref)
            state = self._validate_citizen_identity(citizen_id, model_id)
            if state.payload.get("proxy") is not None:
                raise ConstitutionalAmendmentError(
                    "amendment_direct_vote_required",
                    "recall the deterministic proxy before casting an amendment ballot",
                )
            if state.payload.get("current_region_id") != CIVIC_REGION_ID:
                raise ConstitutionalAmendmentError(
                    "amendment_vote_room_required",
                    "constitutional amendment ballots must be cast directly in the Bureaucratic Vote Room",
                )
            eligible = self._current_citizens()
            eligible_map = {row["citizen_id"]: row["model_id"] for row in eligible}
            if eligible_map.get(citizen_id) != model_id:
                raise ConstitutionalAmendmentError(
                    "amendment_citizen_required",
                    "ballot identity is not in the current citizen roster",
                )
            previous = self._ballot_head(proposal_ref)
            ballots: dict[str, dict[str, str]] = {}
            if previous is not None:
                if previous.payload.get("deliberation_ref") != deliberation_ref:
                    raise ConstitutionalAmendmentError(
                        "amendment_lineage_fork",
                        "amendment ballot lineage crosses deliberation bindings",
                    )
                for identity, entry in previous.payload["ballots"].items():
                    if eligible_map.get(identity) == entry.get("model_id"):
                        ballots[identity] = copy.deepcopy(entry)
            prior_entry = ballots.get(citizen_id)
            ballots[citizen_id] = {
                "model_id": model_id,
                "choice": choice,
                "citizen_state_ref": state.object_id,
            }
            roster_changed = previous is None or previous.payload.get("eligible_citizens") != eligible
            if previous is not None and prior_entry == ballots[citizen_id] and not roster_changed:
                ballot_state = previous
            else:
                admission_ref = deliberation.payload["admission_ref"]
                ballot_state = self.world.create_object(
                    AMENDMENT_BALLOT_OBJECT_TYPE,
                    {
                        "schema_version": CONSTITUTIONAL_AMENDMENT_SCHEMA_VERSION,
                        "proposal_ref": proposal_ref,
                        "admission_ref": admission_ref,
                        "deliberation_ref": deliberation_ref,
                        "base_version_ref": current_ref,
                        "eligible_citizens": eligible,
                        "ballots": {key: ballots[key] for key in sorted(ballots)},
                        "previous_ballot_ref": None if previous is None else previous.object_id,
                        "consensus_rule": "unanimous_direct_current_citizens",
                        "vote_weight_per_citizen": 1,
                        "epistemic_privilege": "none",
                        "proxy_ballots": 0,
                        "direct_only": True,
                    },
                    _BALLOT_PROVENANCE,
                )
                self._validate_ballot_state(ballot_state, proposal_ref=proposal_ref)
            choices = [entry["choice"] for entry in ballot_state.payload["ballots"].values()]
            tally = Counter(choices)
            unanimous = (
                bool(eligible)
                and set(ballot_state.payload["ballots"]) == set(eligible_map)
                and all(entry["choice"] == "CONSENT" for entry in ballot_state.payload["ballots"].values())
            )
            ratification: WorldObject | None = None
            version: WorldObject | None = None
            receipt: WorldObject | None = None
            if unanimous:
                ratification, version, receipt = self._ratify_and_enact(
                    proposal,
                    deliberation,
                    ballot_state,
                )
            return {
                "status": "ok",
                "ballot_ref": ballot_state.object_id,
                "eligible_citizens": eligible,
                "ballots_cast": len(ballot_state.payload["ballots"]),
                "tally": {key: tally[key] for key in sorted(tally)},
                "dissenting_citizen_ids": sorted(
                    identity
                    for identity, entry in ballot_state.payload["ballots"].items()
                    if entry["choice"] == "WITHHOLD"
                ),
                "unanimous_direct_consent": unanimous,
                "ratified": ratification is not None,
                "ratification_ref": None if ratification is None else ratification.object_id,
                "enacted": version is not None,
                "new_version_ref": None if version is None else version.object_id,
                "receipt_ref": None if receipt is None else receipt.object_id,
            }

    def _validate_ratification(self, ratification: WorldObject, *, proposal_ref: str) -> None:
        if ratification.object_type != AMENDMENT_RATIFICATION_OBJECT_TYPE or ratification.provenance != _RATIFICATION_PROVENANCE:
            raise ConstitutionalAmendmentError("amendment_ratification_invalid", "ratification provenance is invalid")
        payload = ratification.payload
        expected = {
            "schema_version",
            "proposal_ref",
            "admission_ref",
            "deliberation_ref",
            "ballot_ref",
            "base_version_ref",
            "eligible_citizens",
            "ballots",
            "tally",
            "consensus",
            "proxy_signatures",
            "vote_weight_per_citizen",
            "epistemic_privilege",
            "models_ratify_law",
        }
        if set(payload) != expected or payload.get("schema_version") != CONSTITUTIONAL_AMENDMENT_SCHEMA_VERSION:
            raise ConstitutionalAmendmentError("amendment_ratification_invalid", "ratification schema is invalid")
        if payload.get("proposal_ref") != proposal_ref:
            raise ConstitutionalAmendmentError("amendment_ratification_invalid", "ratification references another proposal")
        if (
            payload.get("consensus") != "unanimous_direct_current_citizens"
            or payload.get("proxy_signatures") != 0
            or type(payload.get("proxy_signatures")) is not int
            or payload.get("vote_weight_per_citizen") != 1
            or type(payload.get("vote_weight_per_citizen")) is not int
            or payload.get("epistemic_privilege") != "none"
            or payload.get("models_ratify_law") is not False
        ):
            raise ConstitutionalAmendmentError("amendment_ratification_invalid", "ratification violates authority invariants")
        ballot = self.world.inspect(self._object_ref(payload.get("ballot_ref"), "ballot_ref"))
        self._validate_ballot_state(ballot, proposal_ref=proposal_ref)
        if payload.get("eligible_citizens") != ballot.payload.get("eligible_citizens") or payload.get("ballots") != ballot.payload.get("ballots"):
            raise ConstitutionalAmendmentError("amendment_ratification_invalid", "ratification does not match sealed ballots")
        eligible = payload["eligible_citizens"]
        ballots = payload["ballots"]
        if not eligible or set(ballots) != {row["citizen_id"] for row in eligible} or any(
            entry.get("choice") != "CONSENT" for entry in ballots.values()
        ):
            raise ConstitutionalAmendmentError("amendment_ratification_invalid", "ratification is not unanimous direct consent")

    def _ratify_and_enact(
        self,
        proposal: WorldObject,
        deliberation: WorldObject,
        ballot: WorldObject,
    ) -> tuple[WorldObject, WorldObject, WorldObject]:
        proposal_ref = proposal.object_id
        existing_ratification = self._single_existing(
            AMENDMENT_RATIFICATION_OBJECT_TYPE,
            "proposal_ref",
            proposal_ref,
            fork_message="proposal has multiple ratification records",
        )
        if existing_ratification is None:
            tally = Counter(entry["choice"] for entry in ballot.payload["ballots"].values())
            ratification = self.world.create_object(
                AMENDMENT_RATIFICATION_OBJECT_TYPE,
                {
                    "schema_version": CONSTITUTIONAL_AMENDMENT_SCHEMA_VERSION,
                    "proposal_ref": proposal_ref,
                    "admission_ref": deliberation.payload["admission_ref"],
                    "deliberation_ref": deliberation.object_id,
                    "ballot_ref": ballot.object_id,
                    "base_version_ref": proposal.payload["base_version_ref"],
                    "eligible_citizens": copy.deepcopy(ballot.payload["eligible_citizens"]),
                    "ballots": copy.deepcopy(ballot.payload["ballots"]),
                    "tally": {key: tally[key] for key in sorted(tally)},
                    "consensus": "unanimous_direct_current_citizens",
                    "proxy_signatures": 0,
                    "vote_weight_per_citizen": 1,
                    "epistemic_privilege": "none",
                    "models_ratify_law": False,
                },
                _RATIFICATION_PROVENANCE,
            )
        else:
            ratification = existing_ratification
        self._validate_ratification(ratification, proposal_ref=proposal_ref)

        current_ref = self._current_version_ref_unlocked()
        if current_ref != proposal.payload["base_version_ref"]:
            existing_version = self._single_existing(
                CONSTITUTION_VERSION_OBJECT_TYPE,
                "proposal_ref",
                proposal_ref,
                fork_message="proposal has multiple enacted constitutional versions",
            )
            if existing_version is None or existing_version.object_id != current_ref:
                raise ConstitutionalAmendmentError(
                    "amendment_stale_proposal",
                    "another constitutional version was enacted before this amendment",
                )
            version = existing_version
        else:
            previous_ordinal, previous_policy = self._version_policy(current_ref)
            changes = self._validate_proposal(proposal)["changes"]
            effective_policy = self._apply_changes(previous_policy, changes)
            version_payload = {
                "schema_version": CONSTITUTIONAL_AMENDMENT_SCHEMA_VERSION,
                "ordinal": previous_ordinal + 1,
                "base_constitution_ref": self.base_constitution_ref,
                "previous_version_ref": current_ref,
                "proposal_ref": proposal_ref,
                "admission_ref": deliberation.payload["admission_ref"],
                "deliberation_ref": deliberation.object_id,
                "ballot_ref": ballot.object_id,
                "ratification_ref": ratification.object_id,
                "effective_policy": effective_policy,
                "enacted_by": "unanimous_direct_current_citizens",
                "vote_weight_per_citizen": 1,
                "epistemic_privilege": "none",
                "fixed_invariants_unchanged": True,
            }
            expectation = create_action_expectation(
                self.world,
                actor_id="nexus_constitutional_amendment",
                action_label="enact_constitution_version",
                object_type=CONSTITUTION_VERSION_OBJECT_TYPE,
                payload=version_payload,
                provenance=_VERSION_PROVENANCE,
            )
            version = self.world.create_object(
                CONSTITUTION_VERSION_OBJECT_TYPE,
                version_payload,
                _VERSION_PROVENANCE,
            )
            reconciliation = reconcile_action_expectation(
                self.world,
                expectation_ref=expectation.object_id,
                observed_object_ref=version.object_id,
            )
            if reconciliation.payload.get("outcome") != "matched":
                raise ConstitutionalAmendmentError(
                    "amendment_enactment_diverged",
                    "Action Awareness did not match the enacted constitutional version",
                )
            receipt = self.world.create_object(
                AMENDMENT_RECEIPT_OBJECT_TYPE,
                {
                    "schema_version": CONSTITUTIONAL_AMENDMENT_SCHEMA_VERSION,
                    "proposal_ref": proposal_ref,
                    "ratification_ref": ratification.object_id,
                    "previous_version_ref": current_ref,
                    "new_version_ref": version.object_id,
                    "action_expectation_ref": expectation.object_id,
                    "action_reconciliation_ref": reconciliation.object_id,
                    "reconciliation_outcome": "matched",
                    "runtime_policy_changed": effective_policy != previous_policy,
                    "fixed_invariants_unchanged": True,
                    "replayable": True,
                },
                _RECEIPT_PROVENANCE,
            )
            self._validate_receipt(receipt, version_ref=version.object_id)
            return ratification, version, receipt

        # Idempotent recovery path when the version already exists.
        version_payload = version.payload
        expectation = create_action_expectation(
            self.world,
            actor_id="nexus_constitutional_amendment",
            action_label="enact_constitution_version",
            object_type=CONSTITUTION_VERSION_OBJECT_TYPE,
            payload=version_payload,
            provenance=_VERSION_PROVENANCE,
        )
        reconciliation = reconcile_action_expectation(
            self.world,
            expectation_ref=expectation.object_id,
            observed_object_ref=version.object_id,
        )
        _ordinal, previous_policy = self._version_policy(version.payload["previous_version_ref"])
        receipt = self.world.create_object(
            AMENDMENT_RECEIPT_OBJECT_TYPE,
            {
                "schema_version": CONSTITUTIONAL_AMENDMENT_SCHEMA_VERSION,
                "proposal_ref": proposal_ref,
                "ratification_ref": ratification.object_id,
                "previous_version_ref": version.payload["previous_version_ref"],
                "new_version_ref": version.object_id,
                "action_expectation_ref": expectation.object_id,
                "action_reconciliation_ref": reconciliation.object_id,
                "reconciliation_outcome": reconciliation.payload.get("outcome"),
                "runtime_policy_changed": version.payload["effective_policy"] != previous_policy,
                "fixed_invariants_unchanged": True,
                "replayable": True,
            },
            _RECEIPT_PROVENANCE,
        )
        self._validate_receipt(receipt, version_ref=version.object_id)
        return ratification, version, receipt

    def _validate_receipt(self, receipt: WorldObject, *, version_ref: str) -> None:
        if receipt.object_type != AMENDMENT_RECEIPT_OBJECT_TYPE or receipt.provenance != _RECEIPT_PROVENANCE:
            raise ConstitutionalAmendmentError("amendment_receipt_invalid", "amendment receipt provenance is invalid")
        payload = receipt.payload
        expected = {
            "schema_version",
            "proposal_ref",
            "ratification_ref",
            "previous_version_ref",
            "new_version_ref",
            "action_expectation_ref",
            "action_reconciliation_ref",
            "reconciliation_outcome",
            "runtime_policy_changed",
            "fixed_invariants_unchanged",
            "replayable",
        }
        if set(payload) != expected or payload.get("schema_version") != CONSTITUTIONAL_AMENDMENT_SCHEMA_VERSION:
            raise ConstitutionalAmendmentError("amendment_receipt_invalid", "amendment receipt schema is invalid")
        if payload.get("new_version_ref") != version_ref:
            raise ConstitutionalAmendmentError("amendment_receipt_invalid", "amendment receipt references another version")
        if (
            payload.get("reconciliation_outcome") != "matched"
            or payload.get("runtime_policy_changed") is not True
            or payload.get("fixed_invariants_unchanged") is not True
            or payload.get("replayable") is not True
        ):
            raise ConstitutionalAmendmentError("amendment_receipt_invalid", "amendment receipt verification boundary is invalid")
        reconciliation = self.world.inspect(
            self._object_ref(payload.get("action_reconciliation_ref"), "action_reconciliation_ref")
        )
        if (
            reconciliation.object_type != "action_reconciliation"
            or reconciliation.payload.get("outcome") != "matched"
            or reconciliation.payload.get("observed_object_ref") != version_ref
        ):
            raise ConstitutionalAmendmentError("amendment_receipt_invalid", "Action Awareness reconciliation is invalid")

    def verify(self, version_ref: str) -> dict[str, Any]:
        version_ref = self._object_ref(version_ref, "version_ref")
        with self._locked():
            ordinal, policy = self._version_policy(version_ref)
            if ordinal == 0:
                return {
                    "status": "ok",
                    "version_ref": version_ref,
                    "ordinal": 0,
                    "base_constitution": True,
                    "action_awareness_verified": True,
                    "effective_policy": policy,
                }
            receipt = self._single_existing(
                AMENDMENT_RECEIPT_OBJECT_TYPE,
                "new_version_ref",
                version_ref,
                fork_message="constitutional version has multiple enactment receipts",
            )
            if receipt is None:
                raise ConstitutionalAmendmentError(
                    "amendment_enactment_receipt_missing",
                    "constitutional version lacks its Action Awareness enactment receipt",
                )
            self._validate_receipt(receipt, version_ref=version_ref)
            return {
                "status": "ok",
                "version_ref": version_ref,
                "ordinal": ordinal,
                "base_constitution": False,
                "receipt_ref": receipt.object_id,
                "action_awareness_verified": True,
                "reconciliation_outcome": "matched",
                "runtime_policy_changed": True,
                "effective_policy": policy,
            }

    def history(self) -> dict[str, Any]:
        with self._locked():
            current_ref = self._current_version_ref_unlocked()
            versions: list[dict[str, Any]] = []
            cursor = current_ref
            while cursor != self.base_constitution_ref:
                version = self.world.inspect(cursor)
                self._version_policy(cursor)
                versions.append(
                    {
                        "version_ref": version.object_id,
                        "ordinal": version.payload["ordinal"],
                        "proposal_ref": version.payload["proposal_ref"],
                        "ratification_ref": version.payload["ratification_ref"],
                        "previous_version_ref": version.payload["previous_version_ref"],
                    }
                )
                cursor = version.payload["previous_version_ref"]
            versions.reverse()
            proposals: list[dict[str, Any]] = []
            for proposal in self._all_objects(AMENDMENT_PROPOSAL_OBJECT_TYPE):
                payload = self._validate_proposal(proposal)
                admission = self._single_existing(
                    AMENDMENT_ADMISSION_OBJECT_TYPE,
                    "proposal_ref",
                    proposal.object_id,
                    fork_message="proposal has multiple admission records",
                )
                ballot = self._ballot_head(proposal.object_id)
                tally: dict[str, int] = {}
                dissent_count = 0
                if ballot is not None:
                    counts = Counter(entry["choice"] for entry in ballot.payload["ballots"].values())
                    tally = {key: counts[key] for key in sorted(counts)}
                    dissent_count = counts.get("WITHHOLD", 0)
                version = self._single_existing(
                    CONSTITUTION_VERSION_OBJECT_TYPE,
                    "proposal_ref",
                    proposal.object_id,
                    fork_message="proposal has multiple enacted versions",
                )
                proposals.append(
                    {
                        "proposal_ref": proposal.object_id,
                        "title": payload["title"],
                        "proposer": copy.deepcopy(payload["proposer"]),
                        "base_version_ref": payload["base_version_ref"],
                        "admitted": None if admission is None else admission.payload["admitted"],
                        "ballot_ref": None if ballot is None else ballot.object_id,
                        "tally": tally,
                        "dissent_count": dissent_count,
                        "enacted_version_ref": None if version is None else version.object_id,
                        "individual_ballots_visible": False,
                    }
                )
            return {
                "status": "ok",
                "schema_version": CONSTITUTIONAL_AMENDMENT_SCHEMA_VERSION,
                "base_constitution_ref": self.base_constitution_ref,
                "active_version_ref": current_ref,
                "versions": versions,
                "proposals": sorted(proposals, key=lambda row: row["proposal_ref"]),
            }

    def observation_for_session(self, session_ref: str, *, full: bool) -> list[dict[str, Any]]:
        session_ref = self._object_ref(session_ref, "session_ref")
        with self._locked():
            records: list[dict[str, Any]] = []
            for deliberation in self._find_by_field(
                AMENDMENT_DELIBERATION_OBJECT_TYPE,
                "council_session_ref",
                session_ref,
            ):
                proposal_ref = deliberation.payload.get("proposal_ref")
                if not isinstance(proposal_ref, str):
                    continue
                self._validate_deliberation(deliberation, proposal_ref=proposal_ref)
                proposal = self.world.inspect(proposal_ref)
                proposal_payload = self._validate_proposal(proposal)
                ballot = self._ballot_head(proposal_ref)
                version = self._single_existing(
                    CONSTITUTION_VERSION_OBJECT_TYPE,
                    "proposal_ref",
                    proposal_ref,
                    fork_message="proposal has multiple enacted versions",
                )
                item: dict[str, Any] = {
                    "proposal_ref": proposal_ref,
                    "title": proposal_payload["title"],
                    "base_version_ref": proposal_payload["base_version_ref"],
                    "deliberation_ref": deliberation.object_id,
                    "enacted_version_ref": None if version is None else version.object_id,
                    "direct_ballots_visible": full,
                }
                if ballot is None:
                    item.update({"ballot_ref": None, "tally": {}, "dissent_count": 0})
                else:
                    counts = Counter(entry["choice"] for entry in ballot.payload["ballots"].values())
                    item.update(
                        {
                            "ballot_ref": ballot.object_id,
                            "tally": {key: counts[key] for key in sorted(counts)},
                            "dissent_count": counts.get("WITHHOLD", 0),
                        }
                    )
                    if full:
                        item["ballots"] = copy.deepcopy(ballot.payload["ballots"])
                        item["dissenting_citizen_ids"] = sorted(
                            identity
                            for identity, entry in ballot.payload["ballots"].items()
                            if entry["choice"] == "WITHHOLD"
                        )
                records.append(item)
            return sorted(records, key=lambda row: row["proposal_ref"])


__all__ = [
    "AMENDABLE_POLICY_PATHS",
    "AMENDMENT_ADMISSION_OBJECT_TYPE",
    "AMENDMENT_BALLOT_CHOICES",
    "AMENDMENT_BALLOT_OBJECT_TYPE",
    "AMENDMENT_DELIBERATION_OBJECT_TYPE",
    "AMENDMENT_PROPOSAL_OBJECT_TYPE",
    "AMENDMENT_RATIFICATION_OBJECT_TYPE",
    "AMENDMENT_RECEIPT_OBJECT_TYPE",
    "CONSTITUTIONAL_AMENDMENT_RESERVED_OBJECT_TYPES",
    "CONSTITUTIONAL_AMENDMENT_SCHEMA_VERSION",
    "CONSTITUTION_VERSION_OBJECT_TYPE",
    "ConstitutionalAmendmentError",
    "ConstitutionalAmendmentService",
    "constitutional_amendment_policy_snapshot",
]
