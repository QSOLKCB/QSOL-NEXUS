from __future__ import annotations

import copy
import re
from collections.abc import Mapping, Sequence
from typing import Any

from .canonical import canonical_json, sha256_ref
from .scrub import SecretScrubber
from .world import WorldObject, WorldStore
from .world_continuity import ContinuityWorldStore, WorldContinuityError
from .world_lattice import WORLD_LATTICE_RESERVED_OBJECT_TYPES

PERSISTENT_WORLD_POLICY_ID = "nexus-persistent-world/1"
PERSISTENT_WORLD_EXPORT_SCHEMA = "nexus-persistent-world-export/1"
PERSISTENT_WORLD_IMPORT_RECEIPT_SCHEMA = "nexus-persistent-world-import-receipt/1"

WORLD_RELATION_OBJECT_TYPE = "world_relation"
WORLD_HYPOTHESIS_OBJECT_TYPE = "world_hypothesis"
WORLD_EXPERIMENT_OBJECT_TYPE = "world_experiment"
WORLD_IMPORTED_OBJECT_TYPE = "world_imported_object"
WORLD_IMPORT_RECEIPT_OBJECT_TYPE = "world_import_receipt"

PERSISTENT_WORLD_RESERVED_OBJECT_TYPES = frozenset(
    {
        WORLD_RELATION_OBJECT_TYPE,
        WORLD_HYPOTHESIS_OBJECT_TYPE,
        WORLD_EXPERIMENT_OBJECT_TYPE,
        WORLD_IMPORTED_OBJECT_TYPE,
        WORLD_IMPORT_RECEIPT_OBJECT_TYPE,
    }
)

MAX_WORLD_SCAN_OBJECTS = 100_000
MAX_SEARCH_RESULTS = 50
MAX_EXPORT_OBJECTS = 256
MAX_IMPORT_OBJECTS = 256
MAX_EXCHANGE_BYTES = 1_048_576
MAX_RELATION_METADATA_BYTES = 8_192
MAX_TEXT_CHARS = 4_096
MAX_REF_LIST = 128

_OBJECT_REF_RE = re.compile(r"^object:[0-9a-f]{64}$")
_RELATION_TYPE_RE = re.compile(r"^[a-z][a-z0-9_.:-]{0,63}$")
_SECRET_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "access_token",
        "refresh_token",
        "client_secret",
        "private_key",
        "authorization",
        "password",
        "passwd",
    }
)

_HYPOTHESIS_STATES = frozenset({"PROPOSED", "ACTIVE", "CHALLENGED", "RETIRED"})
_HYPOTHESIS_TRANSITIONS = {
    "PROPOSED": frozenset({"ACTIVE", "CHALLENGED", "RETIRED"}),
    "ACTIVE": frozenset({"ACTIVE", "CHALLENGED", "RETIRED"}),
    "CHALLENGED": frozenset({"ACTIVE", "CHALLENGED", "RETIRED"}),
    "RETIRED": frozenset(),
}
_EXPERIMENT_STAGES = frozenset({"PLANNED", "OBSERVED", "CLOSED"})
_EXPERIMENT_TRANSITIONS = {
    "PLANNED": frozenset({"PLANNED", "OBSERVED", "CLOSED"}),
    "OBSERVED": frozenset({"OBSERVED", "CLOSED"}),
    "CLOSED": frozenset(),
}

_EVENT_PROVENANCE = {"actor": "nexus", "subsystem": "persistent-world"}


class PersistentWorldError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _fail(code: str, message: str) -> PersistentWorldError:
    return PersistentWorldError(code, message)


def persistent_world_policy_snapshot() -> dict[str, Any]:
    return {
        "schema": PERSISTENT_WORLD_POLICY_ID,
        "storage_foundation": "existing content-addressed WorldStore and ContinuityWorldStore",
        "canonical_object_identity": "object:<sha256>",
        "provenance": "existing immutable per-object provenance is preserved",
        "relations": "explicit typed WorldStore objects only",
        "hypotheses": "immutable workflow lineage; state labels do not establish truth",
        "experiments": "immutable plan/observation lineage; recorded result refs do not establish empirical truth",
        "council_sessions": "existing council_session objects remain canonical",
        "world_presence": "existing world-presence and LATTICE movement objects remain canonical",
        "minority_reports": "derived searchable views over committed local council_session objects",
        "mode_history": "derived ordered view over committed Council sessions and explicit world-presence transitions",
        "export": "bounded provenance-closed exact-object bundle",
        "import": "validate complete bundle before append; preserve foreign exact objects inside inert same-WorldStore wrappers; append separate import receipt",
        "migration": {
            "current_major": 1,
            "legacy_rule": "pre-alpha8 objects remain valid and are never rewritten merely to gain alpha8 metadata",
            "unknown_major": "reject",
            "additive_rule": "new semantic object types are additive WorldStore objects",
            "rewrite_rule": "in-place reinterpretation of historical objects is forbidden",
        },
        "search_rule": "deterministic derived scan; search rank or text match creates no evidence authority",
        "import_authority_rule": "foreign source object types are never materialized as live local Council/governance/runtime objects by world.import",
        "boundaries": [
            "RELATION != FACT",
            "HYPOTHESIS_STATE != TRUTH",
            "EXPERIMENT_RECORD != EMPIRICAL_VERIFICATION",
            "MINORITY_REPORT != EVIDENCE_PROMOTION",
            "MODE_HISTORY != COGNITIVE_GEOMETRY",
            "EXPORT_HASH != SEMANTIC_TRUTH",
            "IMPORT != AUTHORITY",
            "IMPORTED_OBJECT != LOCAL_COMMITTED_OBJECT",
            "PERSISTENCE != EPISTEMIC_PRIVILEGE",
        ],
        "authority_effect": "none",
    }


def _validate_object_ref(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or _OBJECT_REF_RE.fullmatch(value) is None:
        raise _fail("world_persistence_invalid_ref", f"{field} must be an object:<sha256> reference")
    return value


def _bounded_text(value: Any, *, field: str, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise _fail("world_persistence_invalid", f"{field} must be text")
    if (not allow_empty and not value.strip()) or len(value) > MAX_TEXT_CHARS:
        prefix = "at most" if allow_empty else "non-empty and at most"
        raise _fail(
            "world_persistence_invalid",
            f"{field} must be {prefix} {MAX_TEXT_CHARS} characters",
        )
    return value


def _finite_json(value: Any, *, field: str) -> None:
    try:
        canonical_json(value)
    except (TypeError, ValueError, RecursionError) as exc:
        raise _fail("world_persistence_invalid", f"{field} must contain finite JSON data") from exc


def _canonical_size(value: Any, *, field: str) -> int:
    try:
        return len(canonical_json(value).encode("utf-8"))
    except (TypeError, ValueError, RecursionError) as exc:
        raise _fail("world_persistence_invalid", f"{field} must contain finite JSON data") from exc


def _validate_ref_list(
    values: Any,
    *,
    field: str,
    allow_empty: bool = True,
) -> list[str]:
    if not isinstance(values, list):
        raise _fail("world_persistence_invalid", f"{field} must be a JSON array")
    if len(values) > MAX_REF_LIST:
        raise _fail("world_persistence_limit", f"{field} permits at most {MAX_REF_LIST} object references")
    normalized = [_validate_object_ref(value, field=field) for value in values]
    if len(set(normalized)) != len(normalized):
        raise _fail("world_persistence_invalid", f"{field} must not contain duplicate object references")
    normalized = sorted(normalized)
    if not allow_empty and not normalized:
        raise _fail("world_persistence_invalid", f"{field} must not be empty")
    return normalized


def _world_object_from_raw(raw: Any) -> WorldObject:
    if not isinstance(raw, Mapping):
        raise _fail("world_export_invalid", "export object entry must be a JSON object")
    if set(raw) != {"object_id", "object_type", "payload", "provenance"}:
        raise _fail("world_export_invalid", "export object entry has an unsupported shape")
    object_id = _validate_object_ref(raw.get("object_id"), field="object_id")
    object_type = raw.get("object_type")
    payload = raw.get("payload")
    provenance = raw.get("provenance")
    if (
        not isinstance(object_type, str)
        or not object_type
        or not isinstance(payload, Mapping)
        or not isinstance(provenance, Mapping)
    ):
        raise _fail("world_export_invalid", "export object entry has invalid field types")
    identity_body = {
        "object_type": object_type,
        "payload": copy.deepcopy(dict(payload)),
        "provenance": copy.deepcopy(dict(provenance)),
    }
    _finite_json(identity_body, field="export object")
    expected = sha256_ref("object", identity_body)
    if expected != object_id:
        raise _fail("world_export_invalid", "export object failed content-address verification")
    return WorldObject(
        object_id=object_id,
        object_type=object_type,
        payload=copy.deepcopy(dict(payload)),
        provenance=copy.deepcopy(dict(provenance)),
    )


def validate_world_export_bundle(bundle: Any) -> dict[str, Any]:
    if not isinstance(bundle, Mapping):
        raise _fail("world_export_invalid", "world export bundle must be a JSON object")
    if _canonical_size(dict(bundle), field="world export bundle") > MAX_EXCHANGE_BYTES:
        raise _fail(
            "world_persistence_limit",
            f"world exchange bundle exceeds {MAX_EXCHANGE_BYTES} canonical UTF-8 bytes",
        )
    expected_fields = {
        "schema",
        "world_policy",
        "order_basis",
        "source_head_ref",
        "object_count",
        "objects",
        "authority_effect",
        "bundle_ref",
    }
    if set(bundle) != expected_fields:
        raise _fail("world_export_invalid", "world export bundle has an unsupported shape")
    if bundle.get("schema") != PERSISTENT_WORLD_EXPORT_SCHEMA:
        raise _fail("world_export_version_unsupported", "unsupported persistent-world export schema")
    if bundle.get("world_policy") != PERSISTENT_WORLD_POLICY_ID:
        raise _fail("world_export_invalid", "persistent-world policy identity mismatch")
    if bundle.get("authority_effect") != "none":
        raise _fail("world_export_invalid", "world export bundle cannot create authority")
    order_basis = bundle.get("order_basis")
    if order_basis not in {"continuity_commit_order", "memory_insertion_order", "lexical_object_ref"}:
        raise _fail("world_export_invalid", "world export order_basis is unsupported")
    source_head_ref = bundle.get("source_head_ref")
    if source_head_ref is not None and (
        not isinstance(source_head_ref, str)
        or not re.fullmatch(r"world-manifest:[0-9a-f]{64}", source_head_ref)
    ):
        raise _fail("world_export_invalid", "source_head_ref is invalid")
    objects = bundle.get("objects")
    count = bundle.get("object_count")
    if not isinstance(objects, list) or type(count) is not int or count != len(objects):
        raise _fail("world_export_invalid", "world export object_count does not match objects")
    if count < 0 or count > MAX_IMPORT_OBJECTS:
        raise _fail("world_persistence_limit", f"world import permits at most {MAX_IMPORT_OBJECTS} objects")
    parsed = [_world_object_from_raw(raw) for raw in objects]
    ids = [obj.object_id for obj in parsed]
    if len(set(ids)) != len(ids):
        raise _fail("world_export_invalid", "world export contains duplicate object identities")
    body = {key: copy.deepcopy(bundle[key]) for key in expected_fields if key != "bundle_ref"}
    expected_ref = sha256_ref("world-export", body)
    if bundle.get("bundle_ref") != expected_ref:
        raise _fail("world_export_invalid", "world export bundle_ref does not match canonical content")
    return {
        "status": "verified",
        "bundle_ref": expected_ref,
        "object_count": count,
        "object_refs": ids,
        "authority_effect": "none",
    }


class PersistentWorldService:
    def __init__(self, world: WorldStore, *, scrubber: SecretScrubber | None = None) -> None:
        self.world = world
        self.scrubber = scrubber or SecretScrubber()

    def _ordered_refs(self) -> tuple[list[str], str, str | None]:
        if isinstance(self.world, ContinuityWorldStore) and self.world.root is not None:
            with self.world._locked_continuity():
                head_ref, _ = self.world._resolve_head(require_chain=True)
                _, manifest_refs = self.world._history(head_ref)
                ordered: list[str] = []
                seen: set[str] = set()
                for manifest_ref in manifest_refs:
                    sources = self.world._manifest_sources(manifest_ref)
                    if not sources:
                        raise WorldContinuityError(
                            "world_continuity_corrupt",
                            "recognized manifest has no verified source",
                        )
                    raw = self.world._read_manifest(sources[0].state.root, manifest_ref)
                    candidates = (
                        raw["inventory_refs"]
                        if raw["event_type"] == "legacy_baseline"
                        else [raw["object_ref"]]
                    )
                    for object_ref in candidates:
                        if object_ref not in seen:
                            seen.add(object_ref)
                            ordered.append(object_ref)
                            if len(ordered) > MAX_WORLD_SCAN_OBJECTS:
                                raise _fail(
                                    "world_persistence_limit",
                                    f"recognized world exceeds scan limit {MAX_WORLD_SCAN_OBJECTS}",
                                )
                return ordered, "continuity_commit_order", head_ref

        if self.world.root is None:
            refs = list(self.world._objects.keys())
            if len(refs) > MAX_WORLD_SCAN_OBJECTS:
                raise _fail(
                    "world_persistence_limit",
                    f"in-memory world exceeds scan limit {MAX_WORLD_SCAN_OBJECTS}",
                )
            return refs, "memory_insertion_order", None

        refs: list[str] = []
        assert self.world.objects_dir is not None
        for path in sorted(self.world.objects_dir.glob("*.json"), key=lambda item: item.name):
            if len(refs) >= MAX_WORLD_SCAN_OBJECTS:
                raise _fail(
                    "world_persistence_limit",
                    f"persistent world exceeds scan limit {MAX_WORLD_SCAN_OBJECTS}",
                )
            object_ref = f"object:{path.stem}"
            self.world.inspect(object_ref)
            refs.append(object_ref)
        return refs, "lexical_object_ref", None

    def _inspect(self, object_ref: str) -> WorldObject:
        _validate_object_ref(object_ref, field="object_ref")
        try:
            return self.world.inspect(object_ref)
        except KeyError as exc:
            raise _fail("world_persistence_not_found", "referenced WorldStore object was not found") from exc
        except ValueError as exc:
            raise _fail("world_persistence_invalid_ref", str(exc)) from exc

    def _inspect_expected_type(self, object_ref: str, expected_type: str, *, field: str) -> WorldObject:
        obj = self._inspect(object_ref)
        if obj.object_type != expected_type:
            raise _fail(
                "world_persistence_invalid_lineage",
                f"{field} must reference a {expected_type} object",
            )
        return obj

    def _require_existing_refs(self, refs: Sequence[str]) -> None:
        for object_ref in refs:
            self._inspect(object_ref)

    def create_relation(
        self,
        *,
        relation_type: str,
        source_ref: str,
        target_ref: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> WorldObject:
        if not isinstance(relation_type, str) or _RELATION_TYPE_RE.fullmatch(relation_type) is None:
            raise _fail(
                "world_relation_invalid",
                "relation_type must be a lowercase versioned-safe identifier up to 64 characters",
            )
        source_ref = _validate_object_ref(source_ref, field="source_ref")
        target_ref = _validate_object_ref(target_ref, field="target_ref")
        self._require_existing_refs([source_ref, target_ref])
        normalized_metadata = copy.deepcopy(dict(metadata or {}))
        _finite_json(normalized_metadata, field="relation metadata")
        if len(canonical_json(normalized_metadata).encode("utf-8")) > MAX_RELATION_METADATA_BYTES:
            raise _fail("world_persistence_limit", "relation metadata exceeds the admitted byte limit")
        return self.world.create_object(
            WORLD_RELATION_OBJECT_TYPE,
            {
                "schema": PERSISTENT_WORLD_POLICY_ID,
                "relation_type": relation_type,
                "source_ref": source_ref,
                "target_ref": target_ref,
                "metadata": normalized_metadata,
                "semantic_effect": "none",
                "authority_effect": "none",
            },
            copy.deepcopy(_EVENT_PROVENANCE),
        )

    def create_hypothesis(
        self,
        *,
        statement: str,
        state: str,
        evidence_refs: list[str],
        previous_hypothesis_ref: str | None = None,
    ) -> WorldObject:
        statement = _bounded_text(statement, field="statement")
        if state not in _HYPOTHESIS_STATES:
            raise _fail("world_hypothesis_invalid", f"unsupported hypothesis state: {state}")
        normalized_evidence = _validate_ref_list(evidence_refs, field="evidence_refs")
        self._require_existing_refs(normalized_evidence)
        if previous_hypothesis_ref is None:
            if state != "PROPOSED":
                raise _fail(
                    "world_hypothesis_invalid",
                    "initial hypothesis state must be PROPOSED",
                )
        else:
            previous_hypothesis_ref = _validate_object_ref(
                previous_hypothesis_ref,
                field="previous_hypothesis_ref",
            )
            previous = self._inspect_expected_type(
                previous_hypothesis_ref,
                WORLD_HYPOTHESIS_OBJECT_TYPE,
                field="previous_hypothesis_ref",
            )
            previous_state = previous.payload.get("state")
            if previous_state not in _HYPOTHESIS_TRANSITIONS or state not in _HYPOTHESIS_TRANSITIONS[previous_state]:
                raise _fail(
                    "world_hypothesis_invalid",
                    f"hypothesis state transition {previous_state!r} -> {state!r} is not admitted",
                )
        return self.world.create_object(
            WORLD_HYPOTHESIS_OBJECT_TYPE,
            {
                "schema": PERSISTENT_WORLD_POLICY_ID,
                "statement": statement,
                "state": state,
                "evidence_refs": normalized_evidence,
                "previous_hypothesis_ref": previous_hypothesis_ref,
                "state_semantics": "workflow_label_not_truth_classification",
                "authority_effect": "none",
            },
            copy.deepcopy(_EVENT_PROVENANCE),
        )

    def create_experiment(
        self,
        *,
        title: str,
        stage: str,
        method: str,
        hypothesis_refs: list[str],
        input_refs: list[str],
        result_refs: list[str],
        previous_experiment_ref: str | None = None,
    ) -> WorldObject:
        title = _bounded_text(title, field="title")
        method = _bounded_text(method, field="method")
        if stage not in _EXPERIMENT_STAGES:
            raise _fail("world_experiment_invalid", f"unsupported experiment stage: {stage}")
        normalized_hypotheses = _validate_ref_list(hypothesis_refs, field="hypothesis_refs")
        normalized_inputs = _validate_ref_list(input_refs, field="input_refs")
        normalized_results = _validate_ref_list(result_refs, field="result_refs")
        for hypothesis_ref in normalized_hypotheses:
            self._inspect_expected_type(
                hypothesis_ref,
                WORLD_HYPOTHESIS_OBJECT_TYPE,
                field="hypothesis_refs",
            )
        self._require_existing_refs(normalized_inputs)
        self._require_existing_refs(normalized_results)

        if previous_experiment_ref is None:
            if stage != "PLANNED":
                raise _fail("world_experiment_invalid", "initial experiment stage must be PLANNED")
            if normalized_results:
                raise _fail("world_experiment_invalid", "PLANNED experiments cannot already contain result_refs")
        else:
            previous_experiment_ref = _validate_object_ref(
                previous_experiment_ref,
                field="previous_experiment_ref",
            )
            previous = self._inspect_expected_type(
                previous_experiment_ref,
                WORLD_EXPERIMENT_OBJECT_TYPE,
                field="previous_experiment_ref",
            )
            previous_stage = previous.payload.get("stage")
            if previous_stage not in _EXPERIMENT_TRANSITIONS or stage not in _EXPERIMENT_TRANSITIONS[previous_stage]:
                raise _fail(
                    "world_experiment_invalid",
                    f"experiment stage transition {previous_stage!r} -> {stage!r} is not admitted",
                )
            if stage in {"OBSERVED", "CLOSED"} and not normalized_results:
                raise _fail(
                    "world_experiment_invalid",
                    f"{stage} experiment records require at least one result_ref",
                )
            if stage == "PLANNED" and normalized_results:
                raise _fail("world_experiment_invalid", "PLANNED experiments cannot contain result_refs")

        return self.world.create_object(
            WORLD_EXPERIMENT_OBJECT_TYPE,
            {
                "schema": PERSISTENT_WORLD_POLICY_ID,
                "title": title,
                "stage": stage,
                "method": method,
                "hypothesis_refs": normalized_hypotheses,
                "input_refs": normalized_inputs,
                "result_refs": normalized_results,
                "previous_experiment_ref": previous_experiment_ref,
                "claim_boundary": "recorded_world_lineage_not_empirical_truth",
                "authority_effect": "none",
            },
            copy.deepcopy(_EVENT_PROVENANCE),
        )

    def _search_objects(
        self,
        *,
        object_type: str,
        query: str | None,
        limit: int,
        exact_filters: Mapping[str, str | None],
    ) -> dict[str, Any]:
        if type(limit) is not int or not 1 <= limit <= MAX_SEARCH_RESULTS:
            raise _fail("world_persistence_limit", f"limit must be an integer in [1, {MAX_SEARCH_RESULTS}]")
        if query is not None:
            query = _bounded_text(query, field="query", allow_empty=True).casefold()
        refs, order_basis, head_ref = self._ordered_refs()
        matches: list[dict[str, Any]] = []
        for object_ref in reversed(refs):
            obj = self._inspect(object_ref)
            if obj.object_type != object_type:
                continue
            rejected = False
            for field, expected in exact_filters.items():
                if expected is not None and obj.payload.get(field) != expected:
                    rejected = True
                    break
            if rejected:
                continue
            if query and query not in canonical_json(obj.payload).casefold():
                continue
            matches.append(obj.as_dict())
            if len(matches) >= limit:
                break
        return {
            "matches": matches,
            "returned": len(matches),
            "limit": limit,
            "order": "newest_first",
            "order_basis": order_basis,
            "source_head_ref": head_ref,
            "search_is_evidence": False,
            "authority_effect": "none",
        }

    def search_relations(
        self,
        *,
        query: str | None = None,
        relation_type: str | None = None,
        source_ref: str | None = None,
        target_ref: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        if relation_type is not None and (
            not isinstance(relation_type, str) or _RELATION_TYPE_RE.fullmatch(relation_type) is None
        ):
            raise _fail("world_relation_invalid", "relation_type filter is invalid")
        if source_ref is not None:
            source_ref = _validate_object_ref(source_ref, field="source_ref")
        if target_ref is not None:
            target_ref = _validate_object_ref(target_ref, field="target_ref")
        return self._search_objects(
            object_type=WORLD_RELATION_OBJECT_TYPE,
            query=query,
            limit=limit,
            exact_filters={
                "relation_type": relation_type,
                "source_ref": source_ref,
                "target_ref": target_ref,
            },
        )

    def search_hypotheses(
        self,
        *,
        query: str | None = None,
        state: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        if state is not None and state not in _HYPOTHESIS_STATES:
            raise _fail("world_hypothesis_invalid", "hypothesis state filter is invalid")
        return self._search_objects(
            object_type=WORLD_HYPOTHESIS_OBJECT_TYPE,
            query=query,
            limit=limit,
            exact_filters={"state": state},
        )

    def search_experiments(
        self,
        *,
        query: str | None = None,
        stage: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        if stage is not None and stage not in _EXPERIMENT_STAGES:
            raise _fail("world_experiment_invalid", "experiment stage filter is invalid")
        return self._search_objects(
            object_type=WORLD_EXPERIMENT_OBJECT_TYPE,
            query=query,
            limit=limit,
            exact_filters={"stage": stage},
        )

    def search_minority_reports(
        self,
        *,
        query: str | None = None,
        choice: str | None = None,
        member_id: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        if type(limit) is not int or not 1 <= limit <= MAX_SEARCH_RESULTS:
            raise _fail("world_persistence_limit", f"limit must be an integer in [1, {MAX_SEARCH_RESULTS}]")
        if query is not None:
            query = _bounded_text(query, field="query", allow_empty=True).casefold()
        if choice is not None:
            choice = _bounded_text(choice, field="choice")
        if member_id is not None:
            member_id = _bounded_text(member_id, field="member_id")
        refs, order_basis, head_ref = self._ordered_refs()
        matches: list[dict[str, Any]] = []
        sessions_scanned = 0
        for object_ref in reversed(refs):
            obj = self._inspect(object_ref)
            if obj.object_type != "council_session":
                continue
            sessions_scanned += 1
            result = obj.payload.get("result")
            if not isinstance(result, Mapping):
                continue
            minority = result.get("minority_reports")
            if not isinstance(minority, list):
                continue
            for report in minority:
                if not isinstance(report, Mapping):
                    continue
                report_choice = report.get("choice")
                report_member = report.get("member_id")
                rationale = report.get("rationale")
                if choice is not None and report_choice != choice:
                    continue
                if member_id is not None and report_member != member_id:
                    continue
                if query and (
                    not isinstance(rationale, str)
                    or query not in rationale.casefold()
                ):
                    continue
                matches.append(
                    {
                        "session_ref": obj.object_id,
                        "session_id": obj.payload.get("session_id"),
                        "question_ref": obj.payload.get("question_ref"),
                        "mode_id": (
                            obj.payload.get("world_mode", {}).get("mode_id")
                            if isinstance(obj.payload.get("world_mode"), Mapping)
                            else None
                        ),
                        "evidence_state": result.get("evidence_state"),
                        "minority_report": copy.deepcopy(dict(report)),
                    }
                )
                if len(matches) >= limit:
                    return {
                        "matches": matches,
                        "returned": len(matches),
                        "sessions_scanned": sessions_scanned,
                        "order": "newest_first",
                        "order_basis": order_basis,
                        "source_head_ref": head_ref,
                        "search_is_evidence": False,
                        "authority_effect": "none",
                    }
        return {
            "matches": matches,
            "returned": len(matches),
            "sessions_scanned": sessions_scanned,
            "order": "newest_first",
            "order_basis": order_basis,
            "source_head_ref": head_ref,
            "search_is_evidence": False,
            "authority_effect": "none",
        }

    def mode_history(self, *, limit: int = 50) -> dict[str, Any]:
        if type(limit) is not int or not 1 <= limit <= MAX_SEARCH_RESULTS:
            raise _fail("world_persistence_limit", f"limit must be an integer in [1, {MAX_SEARCH_RESULTS}]")
        refs, order_basis, head_ref = self._ordered_refs()
        events: list[dict[str, Any]] = []
        presence_types = set(WORLD_LATTICE_RESERVED_OBJECT_TYPES)
        for object_ref in reversed(refs):
            obj = self._inspect(object_ref)
            if obj.object_type == "council_session":
                world_mode = obj.payload.get("world_mode")
                region = obj.payload.get("geometry_region")
                if isinstance(world_mode, Mapping):
                    events.append(
                        {
                            "event_ref": obj.object_id,
                            "kind": "council_session",
                            "mode_id": world_mode.get("mode_id"),
                            "region_id": region.get("region_id") if isinstance(region, Mapping) else None,
                            "question_ref": obj.payload.get("question_ref"),
                            "authority_effect": "none",
                        }
                    )
            elif obj.object_type in presence_types:
                events.append(
                    {
                        "event_ref": obj.object_id,
                        "kind": obj.payload.get("transition"),
                        "mode_id": None,
                        "region_id": obj.payload.get("region_id"),
                        "subject_object_ref": obj.payload.get("subject_object_ref"),
                        "previous_presence_ref": obj.payload.get("previous_presence_ref"),
                        "authority_effect": "none",
                    }
                )
            if len(events) >= limit:
                break
        return {
            "events": events,
            "returned": len(events),
            "order": "newest_first",
            "order_basis": order_basis,
            "source_head_ref": head_ref,
            "geometry_is_semantic_authority": False,
            "authority_effect": "none",
        }

    def export_bundle(self, *, object_refs: list[str] | None = None) -> dict[str, Any]:
        all_refs, order_basis, head_ref = self._ordered_refs()
        if object_refs is None:
            selected = all_refs
        else:
            selected_set = set(_validate_ref_list(object_refs, field="object_refs"))
            missing = sorted(selected_set - set(all_refs))
            if missing:
                raise _fail("world_export_invalid", "requested export object_refs are not in recognized world history")
            selected = [object_ref for object_ref in all_refs if object_ref in selected_set]
        if len(selected) > MAX_EXPORT_OBJECTS:
            raise _fail(
                "world_persistence_limit",
                f"world export permits at most {MAX_EXPORT_OBJECTS} objects; select an explicit subset",
            )
        objects = [self._inspect(object_ref).as_dict() for object_ref in selected]
        body = {
            "schema": PERSISTENT_WORLD_EXPORT_SCHEMA,
            "world_policy": PERSISTENT_WORLD_POLICY_ID,
            "order_basis": order_basis,
            "source_head_ref": head_ref,
            "object_count": len(objects),
            "objects": objects,
            "authority_effect": "none",
        }
        bundle_ref = sha256_ref("world-export", body)
        bundle = {**body, "bundle_ref": bundle_ref}
        if _canonical_size(bundle, field="world export bundle") > MAX_EXCHANGE_BYTES:
            raise _fail(
                "world_persistence_limit",
                f"world exchange bundle exceeds {MAX_EXCHANGE_BYTES} canonical UTF-8 bytes; select a smaller subset",
            )
        return bundle

    def _reject_secret_material(self, value: Any) -> None:
        if isinstance(value, str):
            if self.scrubber.scrub(value).changed:
                raise _fail(
                    "world_import_secret_rejected",
                    "import bundle contains credential-shaped string material",
                )
            return
        if isinstance(value, Mapping):
            for key, child in value.items():
                if not isinstance(key, str):
                    raise _fail("world_export_invalid", "imported JSON object keys must be strings")
                lowered = key.casefold().replace("-", "_")
                if lowered in _SECRET_KEYS:
                    raise _fail(
                        "world_import_secret_rejected",
                        "import bundle contains credential-labelled fields",
                    )
                self._reject_secret_material(child)
            return
        if isinstance(value, list):
            for child in value:
                self._reject_secret_material(child)

    def _existing_import_wrappers(self, refs: Sequence[str]) -> dict[str, tuple[str, dict[str, Any]]]:
        wrappers: dict[str, tuple[str, dict[str, Any]]] = {}
        for object_ref in refs:
            obj = self._inspect(object_ref)
            if obj.object_type != WORLD_IMPORTED_OBJECT_TYPE:
                continue
            source_ref = obj.payload.get("source_object_ref")
            source_object = obj.payload.get("source_object")
            if (
                isinstance(source_ref, str)
                and _OBJECT_REF_RE.fullmatch(source_ref) is not None
                and isinstance(source_object, Mapping)
            ):
                wrappers[source_ref] = (obj.object_id, copy.deepcopy(dict(source_object)))
        return wrappers

    def import_bundle(self, bundle: Mapping[str, Any]) -> dict[str, Any]:
        verification = validate_world_export_bundle(bundle)
        parsed = [_world_object_from_raw(raw) for raw in bundle["objects"]]
        for obj in parsed:
            self._reject_secret_material(obj.payload)
            self._reject_secret_material(obj.provenance)

        recognized, _, _ = self._ordered_refs()
        recognized_set = set(recognized)
        existing_wrappers = self._existing_import_wrappers(recognized)
        already_local_refs: list[str] = []
        quarantined: list[dict[str, str]] = []

        for obj in parsed:
            if obj.object_id in recognized_set:
                current = self._inspect(obj.object_id)
                if current.as_dict() != obj.as_dict():
                    raise _fail(
                        "world_export_invalid",
                        "recognized object identity resolves to different canonical content",
                    )
                already_local_refs.append(obj.object_id)
                continue

            existing = existing_wrappers.get(obj.object_id)
            if existing is not None:
                wrapper_ref, source_object = existing
                if source_object != obj.as_dict():
                    raise _fail(
                        "world_export_invalid",
                        "existing import wrapper does not preserve the supplied source object",
                    )
                quarantined.append({"source_ref": obj.object_id, "wrapper_ref": wrapper_ref})
                continue

            wrapper = self.world.create_object(
                WORLD_IMPORTED_OBJECT_TYPE,
                {
                    "schema": PERSISTENT_WORLD_POLICY_ID,
                    "source_object_ref": obj.object_id,
                    "source_object": obj.as_dict(),
                    "materialized_as_live_world_object": False,
                    "authority_effect": "none",
                },
                copy.deepcopy(_EVENT_PROVENANCE),
            )
            quarantined.append({"source_ref": obj.object_id, "wrapper_ref": wrapper.object_id})
            existing_wrappers[obj.object_id] = (wrapper.object_id, obj.as_dict())

        receipt = self.world.create_object(
            WORLD_IMPORT_RECEIPT_OBJECT_TYPE,
            {
                "schema": PERSISTENT_WORLD_IMPORT_RECEIPT_SCHEMA,
                "bundle_ref": verification["bundle_ref"],
                "source_head_ref": bundle.get("source_head_ref"),
                "source_object_count": verification["object_count"],
                "already_local_refs": sorted(already_local_refs),
                "quarantined_objects": quarantined,
                "source_objects_preserved": True,
                "foreign_objects_materialized_as_live_world_objects": False,
                "authority_effect": "none",
            },
            copy.deepcopy(_EVENT_PROVENANCE),
        )
        return {
            "status": "ok",
            "bundle_ref": verification["bundle_ref"],
            "import_receipt_ref": receipt.object_id,
            "already_local_refs": sorted(already_local_refs),
            "quarantined_objects": quarantined,
            "foreign_objects_materialized_as_live_world_objects": False,
            "authority_effect": "none",
        }


__all__ = [
    "MAX_EXCHANGE_BYTES",
    "MAX_EXPORT_OBJECTS",
    "MAX_IMPORT_OBJECTS",
    "MAX_SEARCH_RESULTS",
    "PERSISTENT_WORLD_EXPORT_SCHEMA",
    "PERSISTENT_WORLD_IMPORT_RECEIPT_SCHEMA",
    "PERSISTENT_WORLD_POLICY_ID",
    "PERSISTENT_WORLD_RESERVED_OBJECT_TYPES",
    "PersistentWorldError",
    "PersistentWorldService",
    "WORLD_EXPERIMENT_OBJECT_TYPE",
    "WORLD_HYPOTHESIS_OBJECT_TYPE",
    "WORLD_IMPORTED_OBJECT_TYPE",
    "WORLD_IMPORT_RECEIPT_OBJECT_TYPE",
    "WORLD_RELATION_OBJECT_TYPE",
    "persistent_world_policy_snapshot",
    "validate_world_export_bundle",
]
