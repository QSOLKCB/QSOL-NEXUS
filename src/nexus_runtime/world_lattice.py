from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any

from .canonical import canonical_json


WORLD_LATTICE_POLICY_ID = "nexus-world-lattice/1"
WORLD_PRESENCE_SCHEMA_VERSION = "nexus-world-presence/1"
LATTICE_PROFILE_DESCRIPTOR_PROTOCOL = "qsol-lattice-profile-descriptor/1"
LATTICE_MIGRATION_PROTOCOL = "qsol-lattice-migration/1"
LATTICE_MIGRATED_REFERENCE_PROTOCOL = "qsol-lattice-migrated-reference/1"
LATTICE_REFERENCE_PROTOCOL = "qsol-lattice-reference/1"
LATTICE_PROFILE_ID = "qsol-3x3x3-sierpinski-derived-memory/1"
LATTICE_PROFILE_FINGERPRINT = "sha256:6e7c4a9a781d552a2b561d334a8435c12efe2908fcd24a0f152935aded555bcf"
MAX_LATTICE_MIGRATION_MAPPINGS = 10_000
MAX_WORLD_PRESENCE_LINEAGE = 4_096

WORLD_PLACEMENT_OBJECT_TYPE = "world_presence_placement"
WORLD_MOVE_OBJECT_TYPE = "world_presence_move"
WORLD_LATTICE_MIGRATION_OBJECT_TYPE = "world_presence_lattice_migration"
WORLD_LATTICE_RESERVED_OBJECT_TYPES = frozenset(
    {
        WORLD_PLACEMENT_OBJECT_TYPE,
        WORLD_MOVE_OBJECT_TYPE,
        WORLD_LATTICE_MIGRATION_OBJECT_TYPE,
    }
)

_ADDRESS_RE = re.compile(r"^L\[[0-2],[0-2],[0-2]\](?:/L\[[0-2],[0-2],[0-2]\]){0,7}$")
_OBJECT_REF_RE = re.compile(r"^object:[0-9a-f]{64}$")
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_PROFILE_VERSION_RE = re.compile(r"^(?P<family>.+)/(?P<major>[1-9][0-9]*)$")
_EVENT_PROVENANCE = {"actor": "nexus", "subsystem": "world-lattice"}
_TRANSITION_TO_OBJECT_TYPE = {
    "placed": WORLD_PLACEMENT_OBJECT_TYPE,
    "moved": WORLD_MOVE_OBJECT_TYPE,
    "lattice_migrated": WORLD_LATTICE_MIGRATION_OBJECT_TYPE,
}


class WorldLatticeError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _fail(code: str, message: str) -> WorldLatticeError:
    return WorldLatticeError(code, message)


def _finite_json(value: Any, *, field: str) -> None:
    try:
        json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError, RecursionError) as exc:
        raise _fail("world_lattice_invalid", f"{field} must contain finite JSON data") from exc


def _profile_family_and_major(profile_id: Any) -> tuple[str, int]:
    if not isinstance(profile_id, str):
        raise _fail("world_lattice_profile_unsupported", "profile_id must be a string")
    match = _PROFILE_VERSION_RE.fullmatch(profile_id)
    if match is None:
        raise _fail("world_lattice_profile_unsupported", "profile_id must end in /<major>")
    return match.group("family"), int(match.group("major"))


def current_lattice_profile_descriptor(metadata: Mapping[str, Any] | None = None) -> dict[str, Any]:
    descriptor: dict[str, Any] = {
        "protocol": LATTICE_PROFILE_DESCRIPTOR_PROTOCOL,
        "profile_id": LATTICE_PROFILE_ID,
        "profile_fingerprint": LATTICE_PROFILE_FINGERPRINT,
    }
    if metadata is not None:
        descriptor["metadata"] = copy.deepcopy(dict(metadata))
    return descriptor


def validate_lattice_profile_descriptor(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise _fail("world_lattice_profile_unsupported", "profile descriptor must be an object")
    allowed = {"protocol", "profile_id", "profile_fingerprint", "metadata"}
    unexpected = set(value) - allowed
    if unexpected:
        raise _fail(
            "world_lattice_profile_unsupported",
            f"profile descriptor contains unsupported fields: {sorted(unexpected)}",
        )
    if value.get("protocol") != LATTICE_PROFILE_DESCRIPTOR_PROTOCOL:
        raise _fail("world_lattice_profile_unsupported", "profile descriptor protocol mismatch")

    family, major = _profile_family_and_major(value.get("profile_id"))
    current_family, current_major = _profile_family_and_major(LATTICE_PROFILE_ID)
    if major != current_major:
        raise _fail("world_lattice_profile_unsupported", f"unsupported profile major: {major}")
    if family != current_family or value.get("profile_id") != LATTICE_PROFILE_ID:
        raise _fail("world_lattice_profile_unsupported", "unsupported lattice profile")
    if value.get("profile_fingerprint") != LATTICE_PROFILE_FINGERPRINT:
        raise _fail(
            "world_lattice_profile_drift",
            "profile semantic fingerprint mismatch; a versioned migration is required",
        )

    metadata = value.get("metadata")
    if metadata is not None:
        if not isinstance(metadata, Mapping):
            raise _fail("world_lattice_invalid", "profile metadata must be an object")
        _finite_json(metadata, field="profile metadata")
    return {
        "status": "compatible",
        "compatibility": "additive-metadata" if metadata else "exact",
        "profile_id": LATTICE_PROFILE_ID,
        "profile_fingerprint": LATTICE_PROFILE_FINGERPRINT,
    }


def lattice_reference_identity(reference: Mapping[str, Any]) -> dict[str, str]:
    return {
        "profile_id": reference["profile_id"],
        "address": reference["address"],
    }


def validate_lattice_reference(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise _fail("world_lattice_reference_invalid", "lattice reference must be an object")
    required = {"protocol", "profile_id", "address", "authority"}
    missing = required - set(value)
    if missing:
        raise _fail(
            "world_lattice_reference_invalid",
            f"lattice reference missing fields: {sorted(missing)}",
        )
    allowed = required | {"content_ref", "note"}
    unexpected = set(value) - allowed
    if unexpected:
        raise _fail(
            "world_lattice_reference_invalid",
            f"lattice reference contains unsupported fields: {sorted(unexpected)}",
        )
    if value.get("protocol") != LATTICE_REFERENCE_PROTOCOL:
        raise _fail("world_lattice_reference_invalid", "lattice reference protocol mismatch")
    if value.get("profile_id") != LATTICE_PROFILE_ID:
        _profile_family_and_major(value.get("profile_id"))
        raise _fail("world_lattice_profile_unsupported", "unsupported lattice profile")
    address = value.get("address")
    if not isinstance(address, str) or len(address) > 71 or _ADDRESS_RE.fullmatch(address) is None:
        raise _fail("world_lattice_reference_invalid", "invalid lattice address")
    if value.get("authority") != "storage-only":
        raise _fail(
            "world_lattice_authority_forbidden",
            "lattice references are storage-only and cannot claim epistemic or governance authority",
        )
    content_ref = value.get("content_ref")
    if content_ref is not None and (
        not isinstance(content_ref, str) or _SHA256_RE.fullmatch(content_ref) is None
    ):
        raise _fail(
            "world_lattice_reference_invalid",
            "content_ref must be null or a lowercase sha256 reference",
        )
    note = value.get("note")
    if note is not None and (not isinstance(note, str) or len(note) > 2048):
        raise _fail("world_lattice_reference_invalid", "note must be at most 2048 characters")
    return copy.deepcopy(dict(value))


def validate_lattice_migration_manifest(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise _fail("world_lattice_migration_invalid", "migration manifest must be an object")
    required = {
        "protocol",
        "migration_id",
        "source_profile",
        "target_profile",
        "mode",
        "preserve_source_identity",
        "mappings",
        "metadata",
    }
    missing = required - set(value)
    if missing:
        raise _fail(
            "world_lattice_migration_invalid",
            f"migration manifest missing fields: {sorted(missing)}",
        )
    unexpected = set(value) - required
    if unexpected:
        raise _fail(
            "world_lattice_migration_invalid",
            f"migration manifest contains unsupported fields: {sorted(unexpected)}",
        )
    if value.get("protocol") != LATTICE_MIGRATION_PROTOCOL:
        raise _fail("world_lattice_migration_invalid", "migration manifest protocol mismatch")
    migration_id = value.get("migration_id")
    if not isinstance(migration_id, str) or not migration_id or len(migration_id) > 256:
        raise _fail(
            "world_lattice_migration_invalid",
            "migration_id must be a non-empty string of at most 256 characters",
        )
    if value.get("preserve_source_identity") is not True:
        raise _fail("world_lattice_migration_invalid", "migration must preserve source identity")

    source_report = validate_lattice_profile_descriptor(value.get("source_profile"))
    target_report = validate_lattice_profile_descriptor(value.get("target_profile"))
    source = value["source_profile"]
    target = value["target_profile"]

    mode = value.get("mode")
    if mode not in {"identity", "explicit-map"}:
        raise _fail(
            "world_lattice_migration_invalid",
            "migration mode must be identity or explicit-map",
        )
    mappings = value.get("mappings")
    if not isinstance(mappings, list):
        raise _fail("world_lattice_migration_invalid", "migration mappings must be an array")
    if len(mappings) > MAX_LATTICE_MIGRATION_MAPPINGS:
        raise _fail(
            "world_lattice_migration_invalid",
            f"migration mappings exceed limit: {MAX_LATTICE_MIGRATION_MAPPINGS}",
        )
    seen_sources: set[str] = set()
    normalized: list[dict[str, str]] = []
    for row in mappings:
        if not isinstance(row, Mapping) or set(row) != {"source_address", "target_address"}:
            raise _fail(
                "world_lattice_migration_invalid",
                "migration mapping rows require source_address and target_address only",
            )
        source_ref = {
            "protocol": LATTICE_REFERENCE_PROTOCOL,
            "profile_id": source["profile_id"],
            "address": row.get("source_address"),
            "authority": "storage-only",
        }
        target_ref = {
            "protocol": LATTICE_REFERENCE_PROTOCOL,
            "profile_id": target["profile_id"],
            "address": row.get("target_address"),
            "authority": "storage-only",
        }
        validate_lattice_reference(source_ref)
        validate_lattice_reference(target_ref)
        source_address = source_ref["address"]
        target_address = target_ref["address"]
        if source_address in seen_sources:
            raise _fail(
                "world_lattice_migration_invalid",
                "migration mapping source addresses must be unique",
            )
        seen_sources.add(source_address)
        normalized.append({"source_address": source_address, "target_address": target_address})

    if mode == "identity":
        if source["profile_id"] != target["profile_id"]:
            raise _fail(
                "world_lattice_migration_invalid",
                "identity migration requires the same profile_id",
            )
        if source["profile_fingerprint"] != target["profile_fingerprint"]:
            raise _fail(
                "world_lattice_migration_invalid",
                "identity migration requires the same profile fingerprint",
            )
        if any(row["source_address"] != row["target_address"] for row in normalized):
            raise _fail(
                "world_lattice_migration_invalid",
                "identity migration cannot change address meaning",
            )
    elif not normalized:
        raise _fail(
            "world_lattice_migration_invalid",
            "explicit-map migration requires at least one address mapping",
        )

    metadata = value.get("metadata")
    if not isinstance(metadata, Mapping):
        raise _fail("world_lattice_migration_invalid", "migration metadata must be an object")
    _finite_json(metadata, field="migration metadata")

    return {
        "status": "valid",
        "migration_id": migration_id,
        "mode": mode,
        "source_profile": source_report["profile_id"],
        "target_profile": target_report["profile_id"],
        "mapping_count": len(normalized),
        "preserve_source_identity": True,
    }


def migrate_lattice_reference(reference: Any, manifest: Any) -> dict[str, Any]:
    source_reference = validate_lattice_reference(reference)
    validate_lattice_migration_manifest(manifest)
    source_profile = manifest["source_profile"]["profile_id"]
    target_profile = manifest["target_profile"]["profile_id"]
    if source_reference["profile_id"] != source_profile:
        raise _fail(
            "world_lattice_migration_invalid",
            "reference profile does not match migration source profile",
        )
    source_address = source_reference["address"]
    if manifest["mode"] == "identity":
        target_address = source_address
    else:
        mapping = {
            row["source_address"]: row["target_address"]
            for row in manifest["mappings"]
        }
        try:
            target_address = mapping[source_address]
        except KeyError as exc:
            raise _fail(
                "world_lattice_migration_invalid",
                "reference address has no explicit migration mapping",
            ) from exc
    target_reference = copy.deepcopy(source_reference)
    target_reference["profile_id"] = target_profile
    target_reference["address"] = target_address
    validate_lattice_reference(target_reference)
    return {
        "protocol": LATTICE_MIGRATED_REFERENCE_PROTOCOL,
        "migration_id": manifest["migration_id"],
        "source_identity": lattice_reference_identity(source_reference),
        "target_identity": lattice_reference_identity(target_reference),
        "source_reference": source_reference,
        "target_reference": target_reference,
    }


def world_object_content_ref(world_object: Any) -> str:
    try:
        body = canonical_json(world_object.as_dict()).encode("utf-8")
    except (AttributeError, TypeError, ValueError, RecursionError) as exc:
        raise _fail("world_lattice_invalid", "world object cannot be canonically serialized") from exc
    return f"sha256:{hashlib.sha256(body).hexdigest()}"


def world_lattice_policy_snapshot() -> dict[str, Any]:
    return {
        "policy_id": WORLD_LATTICE_POLICY_ID,
        "presence_schema_version": WORLD_PRESENCE_SCHEMA_VERSION,
        "lattice_profile": current_lattice_profile_descriptor(),
        "compatibility": {
            "unknown_major": "reject",
            "unknown_profile_same_major": "reject",
            "same_profile_same_fingerprint": "compatible",
            "same_profile_changed_fingerprint": "reject-version-bump-required",
            "additive_non_semantic_metadata": "compatible",
            "historical_identity": "profile_id+address",
            "migration": "explicit-derived-reference-only",
        },
        "placement": {
            "nexus_region_identity": "named operational region",
            "lattice_identity": "profile_id+address",
            "coupling": "explicit-only",
            "automatic_semantic_coordinate_inference": False,
            "move_requires_adjacent_named_region": True,
            "movement_history": "append-only immutable WorldStore objects",
        },
        "content_binding": {
            "nexus_object_id_preserved": True,
            "lattice_content_ref": "sha256(canonical_json(WorldObject.as_dict()))",
            "object_id_is_not_relabelled_as_content_ref": True,
        },
        "boundaries": [
            "LATTICE_ADDRESS != NEXUS_WORLD_REGION",
            "LATTICE_POSITION != TRUTH_SCORE",
            "LATTICE_POSITION != COGNITIVE_COORDINATE",
            "MIGRATION != SILENT_REWRITE",
            "PROFILE_COMPATIBILITY != EPISTEMIC_AUTHORITY",
            "WORLD_MOVEMENT != GOVERNANCE_AUTHORITY",
        ],
        "authority_effect": "none",
    }


class WorldLatticeService:
    def __init__(self, world: Any, geometry: Any | None = None) -> None:
        self.world = world
        if geometry is None:
            from .geometry import DEFAULT_WORLD_GEOMETRY

            geometry = DEFAULT_WORLD_GEOMETRY
        self.geometry = geometry

    def _geometry_identity(self) -> dict[str, str]:
        snapshot = self.geometry.snapshot()
        return {
            "geometry_id": snapshot["geometry_id"],
            "topology_ref": snapshot["topology_ref"],
            "semantics": snapshot["semantics"],
        }

    def _subject(self, object_ref: str) -> Any:
        if not isinstance(object_ref, str) or _OBJECT_REF_RE.fullmatch(object_ref) is None:
            raise _fail(
                "world_lattice_object_invalid",
                "object_ref must be 'object:' followed by exactly 64 lowercase hex characters",
            )
        try:
            obj = self.world.inspect(object_ref)
        except KeyError as exc:
            raise _fail("world_lattice_object_not_found", "subject WorldStore object was not found") from exc
        except ValueError as exc:
            raise _fail("world_lattice_object_invalid", str(exc)) from exc
        if obj.object_type in WORLD_LATTICE_RESERVED_OBJECT_TYPES:
            raise _fail(
                "world_lattice_object_invalid",
                "world-presence event objects cannot themselves be placed as subjects",
            )
        return obj

    def _region(self, region_id: str) -> Any:
        if not isinstance(region_id, str) or not region_id:
            raise _fail("world_lattice_region_invalid", "region_id must be non-empty text")
        try:
            return self.geometry.region(region_id)
        except ValueError as exc:
            raise _fail("world_lattice_region_invalid", str(exc)) from exc

    def _bind_reference(self, reference: Any, subject: Any) -> dict[str, Any]:
        normalized = validate_lattice_reference(reference)
        expected = world_object_content_ref(subject)
        supplied = normalized.get("content_ref")
        if supplied is not None and supplied != expected:
            raise _fail(
                "world_lattice_content_mismatch",
                "lattice content_ref does not match the canonical NEXUS WorldObject",
            )
        normalized["content_ref"] = expected
        return normalized

    @staticmethod
    def _presence_identity(payload: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "region_id": payload["region_id"],
            "lattice_identity": lattice_reference_identity(payload["lattice_reference"]),
        }

    def _create_event(
        self,
        *,
        object_type: str,
        transition: str,
        subject_ref: str,
        sequence: int,
        region_id: str,
        lattice_reference: dict[str, Any],
        previous_presence_ref: str | None,
        transition_detail: dict[str, Any],
    ) -> Any:
        payload = {
            "schema_version": WORLD_PRESENCE_SCHEMA_VERSION,
            "transition": transition,
            "subject_object_ref": subject_ref,
            "sequence": sequence,
            "region_id": region_id,
            "geometry": self._geometry_identity(),
            "lattice_reference": copy.deepcopy(lattice_reference),
            "previous_presence_ref": previous_presence_ref,
            "transition_detail": copy.deepcopy(transition_detail),
            "authority_effect": "none",
        }
        _finite_json(payload, field="world presence event")
        return self.world.create_object(object_type, payload, copy.deepcopy(_EVENT_PROVENANCE))

    def place(self, object_ref: str, region_id: str, lattice_reference: Any) -> Any:
        subject = self._subject(object_ref)
        self._region(region_id)
        bound = self._bind_reference(lattice_reference, subject)
        return self._create_event(
            object_type=WORLD_PLACEMENT_OBJECT_TYPE,
            transition="placed",
            subject_ref=object_ref,
            sequence=0,
            region_id=region_id,
            lattice_reference=bound,
            previous_presence_ref=None,
            transition_detail={
                "placement_rule": "explicit-region-plus-storage-only-lattice-reference",
                "root_uniqueness_claimed": False,
            },
        )

    def _inspect_presence_event(self, event_ref: str) -> Any:
        if not isinstance(event_ref, str) or _OBJECT_REF_RE.fullmatch(event_ref) is None:
            raise _fail("world_lattice_history_invalid", "presence event_ref must be an object reference")
        try:
            event = self.world.inspect(event_ref)
        except KeyError as exc:
            raise _fail("world_lattice_history_not_found", "presence event was not found") from exc
        except ValueError as exc:
            raise _fail("world_lattice_history_invalid", str(exc)) from exc
        expected_transition = None
        for transition, object_type in _TRANSITION_TO_OBJECT_TYPE.items():
            if event.object_type == object_type:
                expected_transition = transition
                break
        if expected_transition is None:
            raise _fail("world_lattice_history_invalid", "object is not a world-presence event")
        if event.provenance != _EVENT_PROVENANCE:
            raise _fail("world_lattice_history_invalid", "world-presence event provenance is invalid")
        payload = event.payload
        required = {
            "schema_version",
            "transition",
            "subject_object_ref",
            "sequence",
            "region_id",
            "geometry",
            "lattice_reference",
            "previous_presence_ref",
            "transition_detail",
            "authority_effect",
        }
        if set(payload) != required:
            raise _fail("world_lattice_history_invalid", "world-presence event schema is invalid")
        if payload.get("schema_version") != WORLD_PRESENCE_SCHEMA_VERSION:
            raise _fail("world_lattice_history_invalid", "world-presence schema version is unsupported")
        if payload.get("transition") != expected_transition:
            raise _fail("world_lattice_history_invalid", "world-presence transition/object type mismatch")
        sequence = payload.get("sequence")
        if type(sequence) is not int or sequence < 0:
            raise _fail("world_lattice_history_invalid", "world-presence sequence must be a non-negative integer")
        subject_ref = payload.get("subject_object_ref")
        if not isinstance(subject_ref, str) or _OBJECT_REF_RE.fullmatch(subject_ref) is None:
            raise _fail("world_lattice_history_invalid", "world-presence subject reference is invalid")
        self._region(payload.get("region_id"))
        geometry = payload.get("geometry")
        if not isinstance(geometry, Mapping) or set(geometry) != {"geometry_id", "topology_ref", "semantics"}:
            raise _fail("world_lattice_history_invalid", "world-presence geometry identity is invalid")
        if not all(isinstance(geometry[key], str) and geometry[key] for key in geometry):
            raise _fail("world_lattice_history_invalid", "world-presence geometry identity is invalid")
        normalized_reference = validate_lattice_reference(payload.get("lattice_reference"))
        try:
            subject = self.world.inspect(subject_ref)
        except KeyError as exc:
            raise _fail("world_lattice_history_invalid", "world-presence subject object is missing") from exc
        except ValueError as exc:
            raise _fail("world_lattice_history_invalid", str(exc)) from exc
        if subject.object_type in WORLD_LATTICE_RESERVED_OBJECT_TYPES:
            raise _fail("world_lattice_history_invalid", "world-presence subject cannot be another presence event")
        if normalized_reference.get("content_ref") != world_object_content_ref(subject):
            raise _fail("world_lattice_history_invalid", "world-presence content binding does not match subject object")
        previous = payload.get("previous_presence_ref")
        if previous is not None and (
            not isinstance(previous, str) or _OBJECT_REF_RE.fullmatch(previous) is None
        ):
            raise _fail("world_lattice_history_invalid", "previous presence reference is invalid")
        if not isinstance(payload.get("transition_detail"), Mapping):
            raise _fail("world_lattice_history_invalid", "transition_detail must be an object")
        if payload.get("authority_effect") != "none":
            raise _fail("world_lattice_history_invalid", "world-presence events cannot create authority")
        return event

    def _require_current_geometry(self, event: Any) -> None:
        if event.payload["geometry"] != self._geometry_identity():
            raise _fail(
                "world_lattice_geometry_migration_required",
                "presence event uses a different world geometry; an explicit geometry migration contract is required",
            )

    def move(
        self,
        object_ref: str,
        previous_presence_ref: str,
        region_id: str,
        lattice_reference: Any,
    ) -> Any:
        subject = self._subject(object_ref)
        previous = self._inspect_presence_event(previous_presence_ref)
        if previous.payload["subject_object_ref"] != object_ref:
            raise _fail("world_lattice_history_invalid", "previous presence event belongs to a different object")
        self._require_current_geometry(previous)
        self._region(region_id)
        source_region = previous.payload["region_id"]
        if region_id == source_region:
            raise _fail("world_lattice_move_invalid", "world.move requires a different target region")
        try:
            hop_distance = self.geometry.distance(source_region, region_id)
        except ValueError as exc:
            raise _fail("world_lattice_region_invalid", str(exc)) from exc
        if hop_distance != 1:
            raise _fail(
                "world_lattice_move_invalid",
                "world.move requires one explicit adjacent-region transition per recorded event",
            )
        bound = self._bind_reference(lattice_reference, subject)
        if bound["profile_id"] != previous.payload["lattice_reference"]["profile_id"]:
            raise _fail(
                "world_lattice_migration_required",
                "world.move cannot change lattice profile; use an explicit migration manifest",
            )
        return self._create_event(
            object_type=WORLD_MOVE_OBJECT_TYPE,
            transition="moved",
            subject_ref=object_ref,
            sequence=previous.payload["sequence"] + 1,
            region_id=region_id,
            lattice_reference=bound,
            previous_presence_ref=previous_presence_ref,
            transition_detail={
                "source_region_id": source_region,
                "target_region_id": region_id,
                "hop_distance": hop_distance,
                "source_lattice_identity": lattice_reference_identity(previous.payload["lattice_reference"]),
                "target_lattice_identity": lattice_reference_identity(bound),
            },
        )

    def migrate(
        self,
        object_ref: str,
        previous_presence_ref: str,
        migration_manifest: Any,
    ) -> Any:
        subject = self._subject(object_ref)
        previous = self._inspect_presence_event(previous_presence_ref)
        if previous.payload["subject_object_ref"] != object_ref:
            raise _fail("world_lattice_history_invalid", "previous presence event belongs to a different object")
        self._require_current_geometry(previous)
        migrated = migrate_lattice_reference(previous.payload["lattice_reference"], migration_manifest)
        target = self._bind_reference(migrated["target_reference"], subject)
        migrated["target_reference"] = copy.deepcopy(target)
        migrated["target_identity"] = lattice_reference_identity(target)
        return self._create_event(
            object_type=WORLD_LATTICE_MIGRATION_OBJECT_TYPE,
            transition="lattice_migrated",
            subject_ref=object_ref,
            sequence=previous.payload["sequence"] + 1,
            region_id=previous.payload["region_id"],
            lattice_reference=target,
            previous_presence_ref=previous_presence_ref,
            transition_detail={
                "migration_id": migration_manifest["migration_id"],
                "migrated_reference": migrated,
                "region_unchanged": True,
            },
        )

    def presence(self, event_ref: str) -> dict[str, Any]:
        lineage: list[Any] = []
        seen: set[str] = set()
        current_ref: str | None = event_ref
        while current_ref is not None:
            if current_ref in seen:
                raise _fail("world_lattice_history_invalid", "world-presence lineage contains a loop")
            if len(lineage) >= MAX_WORLD_PRESENCE_LINEAGE:
                raise _fail(
                    "world_lattice_history_invalid",
                    f"world-presence lineage exceeds limit: {MAX_WORLD_PRESENCE_LINEAGE}",
                )
            seen.add(current_ref)
            event = self._inspect_presence_event(current_ref)
            lineage.append(event)
            current_ref = event.payload["previous_presence_ref"]

        lineage.reverse()
        for index, event in enumerate(lineage):
            payload = event.payload
            if payload["sequence"] != index:
                raise _fail("world_lattice_history_invalid", "world-presence sequence is discontinuous")
            if index == 0:
                if payload["transition"] != "placed" or payload["previous_presence_ref"] is not None:
                    raise _fail("world_lattice_history_invalid", "world-presence lineage must begin with placement")
                continue
            previous = lineage[index - 1]
            if payload["previous_presence_ref"] != previous.object_id:
                raise _fail("world_lattice_history_invalid", "world-presence lineage predecessor mismatch")
            if payload["subject_object_ref"] != previous.payload["subject_object_ref"]:
                raise _fail("world_lattice_history_invalid", "world-presence lineage changes subject identity")
            if payload["transition"] == "moved":
                detail = payload["transition_detail"]
                if detail.get("source_region_id") != previous.payload["region_id"]:
                    raise _fail("world_lattice_history_invalid", "world.move source region does not match predecessor")
                if detail.get("source_lattice_identity") != lattice_reference_identity(previous.payload["lattice_reference"]):
                    raise _fail("world_lattice_history_invalid", "world.move source lattice identity does not match predecessor")
            elif payload["transition"] == "lattice_migrated":
                detail = payload["transition_detail"]
                migrated = detail.get("migrated_reference")
                if not isinstance(migrated, Mapping):
                    raise _fail("world_lattice_history_invalid", "migration transition is missing migrated reference")
                if migrated.get("source_identity") != lattice_reference_identity(previous.payload["lattice_reference"]):
                    raise _fail("world_lattice_history_invalid", "migration source identity does not match predecessor")
                if payload["region_id"] != previous.payload["region_id"]:
                    raise _fail("world_lattice_history_invalid", "lattice migration cannot silently move world region")

        current = lineage[-1]
        return {
            "schema_version": WORLD_PRESENCE_SCHEMA_VERSION,
            "event_ref": current.object_id,
            "subject_object_ref": current.payload["subject_object_ref"],
            "current": {
                "sequence": current.payload["sequence"],
                **self._presence_identity(current.payload),
                "lattice_reference": copy.deepcopy(current.payload["lattice_reference"]),
                "geometry": copy.deepcopy(current.payload["geometry"]),
            },
            "lineage": [event.as_dict() for event in lineage],
            "lineage_length": len(lineage),
            "branching_uniqueness_claimed": False,
            "authority_effect": "none",
        }
