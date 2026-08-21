from __future__ import annotations

import copy
import re
from collections.abc import Mapping
from typing import Any

from .canonical import canonical_json, sha256_ref
from .version import PROTOCOL_VERSION, RUNTIME_VERSION


SCHEMA_MIGRATION_POLICY_ID = "nexus-schema-migration/1"
SCHEMA_MIGRATION_PLAN_SCHEMA = "nexus-schema-migration-plan/1"

_KIND_SCHEMA = "schema"
_KIND_PROTOCOL = "protocol"
_KIND_RUNTIME = "runtime"
_KINDS = frozenset({_KIND_SCHEMA, _KIND_PROTOCOL, _KIND_RUNTIME})

_SCHEMA_ID_RE = re.compile(r"^(?P<family>[a-z][a-z0-9._-]{0,95})/(?P<major>0|[1-9][0-9]{0,8})$")
_PROTOCOL_RE = re.compile(r"^nexus/(?P<major>0|[1-9][0-9]{0,8})\.(?P<minor>0|[1-9][0-9]{0,8})$")
_RUNTIME_RE = re.compile(
    r"^(?P<major>0|[1-9][0-9]{0,8})\."
    r"(?P<minor>0|[1-9][0-9]{0,8})\."
    r"(?P<patch>0|[1-9][0-9]{0,8})"
    r"(?:-(?P<prerelease>[0-9A-Za-z.-]{1,64}))?$"
)
_PRERELEASE_IDENTIFIER_RE = re.compile(r"^[0-9A-Za-z-]+$")
_OBJECT_REF_RE = re.compile(r"^object:[0-9a-f]{64}$")


class SchemaMigrationError(ValueError):
    """Raised when a version classification or migration plan is invalid."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _fail(code: str, message: str) -> SchemaMigrationError:
    return SchemaMigrationError(code, message)


def schema_migration_policy_snapshot() -> dict[str, Any]:
    return {
        "schema": SCHEMA_MIGRATION_POLICY_ID,
        "current_runtime": RUNTIME_VERSION,
        "current_protocol": PROTOCOL_VERSION,
        "identity_kinds": sorted(_KINDS),
        "schema_identity_rule": "family/major where major is an exact non-negative integer",
        "protocol_identity_rule": "nexus/major.minor with exact integer components",
        "runtime_identity_rule": "SemVer major.minor.patch with optional bounded SemVer prerelease",
        "validator_precedence_rule": "subsystem closed-shape validators outrank generic compatibility classification",
        "same_major_rule": "same major never implies automatic compatibility; explicit validator support is still required",
        "unknown_major_rule": "reject unless a separately reviewed exact migration adapter is registered",
        "migration_rule": "migration is copy-on-write and source-preserving; historical source identity is never rewritten in place",
        "adapter_rule": "every executable adapter must bind exact kind/source/target identities and be separately reviewed",
        "registered_adapters": [],
        "automatic_execution": False,
        "authority_effect": "none",
        "evidence_effect": "none",
        "boundaries": [
            "VERSION_CHANGE != MIGRATION_AUTHORITY",
            "SAME_MAJOR != AUTOMATIC_COMPATIBILITY",
            "PLAN != EXECUTION",
            "MIGRATION != REWRITE",
            "HASH_MATCH != SEMANTIC_COMPATIBILITY",
            "RUNTIME_VERSION != ARTIFACT_SCHEMA",
            "PROTOCOL_VERSION != STORAGE_SCHEMA",
        ],
    }


def _require_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise _fail("schema_migration_invalid", f"{field} must be non-empty text")
    return value


def _parse_prerelease(value: str | None) -> tuple[tuple[bool, int | str], ...] | None:
    if value is None:
        return None
    identifiers = value.split(".")
    if any(not identifier for identifier in identifiers):
        raise _fail(
            "schema_migration_invalid_identity",
            "runtime prerelease must contain non-empty dot-separated SemVer identifiers",
        )
    parsed: list[tuple[bool, int | str]] = []
    for identifier in identifiers:
        if _PRERELEASE_IDENTIFIER_RE.fullmatch(identifier) is None:
            raise _fail(
                "schema_migration_invalid_identity",
                "runtime prerelease identifiers may contain only ASCII alphanumerics and hyphens",
            )
        if identifier.isdigit():
            if len(identifier) > 1 and identifier.startswith("0"):
                raise _fail(
                    "schema_migration_invalid_identity",
                    "numeric runtime prerelease identifiers must not contain leading zeroes",
                )
            parsed.append((True, int(identifier)))
        else:
            parsed.append((False, identifier))
    return tuple(parsed)


def _parse_identity(kind: str, identity: str) -> dict[str, Any]:
    if kind == _KIND_SCHEMA:
        match = _SCHEMA_ID_RE.fullmatch(identity)
        if match is None:
            raise _fail(
                "schema_migration_invalid_identity",
                "schema identity must use family/major with a bounded non-negative integer major",
            )
        return {
            "kind": kind,
            "identity": identity,
            "family": match.group("family"),
            "major": int(match.group("major")),
        }
    if kind == _KIND_PROTOCOL:
        match = _PROTOCOL_RE.fullmatch(identity)
        if match is None:
            raise _fail(
                "schema_migration_invalid_identity",
                "protocol identity must use nexus/major.minor with bounded non-negative integers",
            )
        return {
            "kind": kind,
            "identity": identity,
            "family": "nexus",
            "major": int(match.group("major")),
            "minor": int(match.group("minor")),
        }
    if kind == _KIND_RUNTIME:
        match = _RUNTIME_RE.fullmatch(identity)
        if match is None:
            raise _fail(
                "schema_migration_invalid_identity",
                "runtime identity must use bounded SemVer major.minor.patch syntax",
            )
        prerelease = match.group("prerelease")
        _parse_prerelease(prerelease)
        return {
            "kind": kind,
            "identity": identity,
            "family": "nexus-runtime",
            "major": int(match.group("major")),
            "minor": int(match.group("minor")),
            "patch": int(match.group("patch")),
            "prerelease": prerelease,
        }
    raise _fail("schema_migration_invalid_kind", f"unsupported version identity kind: {kind}")


def _runtime_core(parsed: Mapping[str, Any]) -> tuple[int, int, int]:
    return int(parsed["major"]), int(parsed["minor"]), int(parsed["patch"])


def _compare_prerelease(source: str | None, target: str | None) -> int:
    if source is None and target is None:
        return 0
    if source is None:
        return 1
    if target is None:
        return -1
    left = _parse_prerelease(source)
    right = _parse_prerelease(target)
    assert left is not None and right is not None
    for left_identifier, right_identifier in zip(left, right):
        if left_identifier == right_identifier:
            continue
        left_numeric, left_value = left_identifier
        right_numeric, right_value = right_identifier
        if left_numeric and not right_numeric:
            return -1
        if right_numeric and not left_numeric:
            return 1
        return -1 if left_value < right_value else 1
    if len(left) == len(right):
        return 0
    return -1 if len(left) < len(right) else 1


def _compare_runtime(source: Mapping[str, Any], target: Mapping[str, Any]) -> int:
    source_core = _runtime_core(source)
    target_core = _runtime_core(target)
    if source_core != target_core:
        return -1 if source_core < target_core else 1
    return _compare_prerelease(source.get("prerelease"), target.get("prerelease"))


def classify_version_change(kind: str, source: str, target: str) -> dict[str, Any]:
    kind = _require_text(kind, "kind")
    source = _require_text(source, "source")
    target = _require_text(target, "target")
    if kind not in _KINDS:
        raise _fail("schema_migration_invalid_kind", f"unsupported version identity kind: {kind}")

    source_parsed = _parse_identity(kind, source)
    target_parsed = _parse_identity(kind, target)

    if source == target:
        classification = "EXACT_IDENTITY"
        compatible = True
        migration_required = False
        adapter_required = False
        reason = "source and target identities are exactly equal"
    elif kind == _KIND_SCHEMA:
        if source_parsed["family"] != target_parsed["family"]:
            classification = "SCHEMA_FAMILY_INCOMPATIBLE"
            compatible = False
            migration_required = False
            adapter_required = False
            reason = "schema families differ; migration cannot silently reinterpret one family as another"
        elif source_parsed["major"] > target_parsed["major"]:
            classification = "SCHEMA_DOWNGRADE_UNSUPPORTED"
            compatible = False
            migration_required = False
            adapter_required = False
            reason = "generic schema downgrade is not admitted"
        else:
            classification = "SCHEMA_MAJOR_MIGRATION_REQUIRED"
            compatible = False
            migration_required = True
            adapter_required = True
            reason = "schema major advanced and requires an exact separately reviewed migration adapter"
    elif kind == _KIND_PROTOCOL:
        if source_parsed["major"] > target_parsed["major"]:
            classification = "PROTOCOL_DOWNGRADE_UNSUPPORTED"
            compatible = False
            migration_required = False
            adapter_required = False
            reason = "generic protocol downgrade is not admitted"
        elif source_parsed["major"] < target_parsed["major"]:
            classification = "PROTOCOL_MAJOR_INCOMPATIBLE"
            compatible = False
            migration_required = True
            adapter_required = True
            reason = "protocol major advanced and requires separately reviewed compatibility or migration"
        elif source_parsed["minor"] < target_parsed["minor"]:
            classification = "PROTOCOL_MINOR_FORWARD_REVIEW_REQUIRED"
            compatible = False
            migration_required = True
            adapter_required = True
            reason = "protocol minor advanced; each operation must explicitly admit compatibility or migration"
        else:
            classification = "PROTOCOL_DOWNGRADE_UNSUPPORTED"
            compatible = False
            migration_required = False
            adapter_required = False
            reason = "generic protocol downgrade is not admitted"
    else:
        direction = _compare_runtime(source_parsed, target_parsed)
        if direction > 0:
            classification = "RUNTIME_DOWNGRADE_UNSUPPORTED"
            compatible = False
            migration_required = False
            adapter_required = False
            reason = "generic runtime downgrade is not admitted"
        elif source_parsed["major"] < target_parsed["major"]:
            classification = "RUNTIME_MAJOR_REVIEW_REQUIRED"
            compatible = False
            migration_required = True
            adapter_required = True
            reason = "runtime major advanced; durable artifact migration must be reviewed per subsystem"
        else:
            classification = "RUNTIME_FORWARD_CHANGE_VALIDATOR_OWNED"
            compatible = False
            migration_required = False
            adapter_required = False
            reason = "runtime advanced by SemVer precedence; durable artifact compatibility remains subsystem-validator-owned"

    return {
        "policy": SCHEMA_MIGRATION_POLICY_ID,
        "kind": kind,
        "source": copy.deepcopy(source_parsed),
        "target": copy.deepcopy(target_parsed),
        "classification": classification,
        "compatible_by_generic_policy": compatible,
        "migration_required": migration_required,
        "adapter_required": adapter_required,
        "registered_adapter": None,
        "automatic_execution": False,
        "validator_precedence": "subsystem_validator",
        "reason": reason,
        "authority_effect": "none",
        "evidence_effect": "none",
    }


def build_migration_plan(
    kind: str,
    source: str,
    target: str,
    *,
    source_ref: str | None = None,
) -> dict[str, Any]:
    if source_ref is not None and (
        not isinstance(source_ref, str) or _OBJECT_REF_RE.fullmatch(source_ref) is None
    ):
        raise _fail(
            "schema_migration_invalid_ref",
            "source_ref must be an object:<sha256> reference when supplied",
        )
    classification = classify_version_change(kind, source, target)
    body = {
        "schema": SCHEMA_MIGRATION_PLAN_SCHEMA,
        "policy": SCHEMA_MIGRATION_POLICY_ID,
        "kind": classification["kind"],
        "source_identity": classification["source"]["identity"],
        "target_identity": classification["target"]["identity"],
        "source_ref": source_ref,
        "classification": classification["classification"],
        "compatible_by_generic_policy": classification["compatible_by_generic_policy"],
        "migration_required": classification["migration_required"],
        "adapter_required": classification["adapter_required"],
        "registered_adapter": classification["registered_adapter"],
        "automatic_execution": False,
        "source_preservation": "required",
        "in_place_rewrite": False,
        "validator_precedence": "subsystem_validator",
        "authority_effect": "none",
        "evidence_effect": "none",
    }
    return {**body, "plan_ref": sha256_ref("schema-migration-plan", body)}


def verify_migration_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(plan, Mapping):
        raise _fail("schema_migration_invalid_plan", "migration plan must be a JSON object")
    expected_fields = {
        "schema",
        "policy",
        "kind",
        "source_identity",
        "target_identity",
        "source_ref",
        "classification",
        "compatible_by_generic_policy",
        "migration_required",
        "adapter_required",
        "registered_adapter",
        "automatic_execution",
        "source_preservation",
        "in_place_rewrite",
        "validator_precedence",
        "authority_effect",
        "evidence_effect",
        "plan_ref",
    }
    if set(plan) != expected_fields:
        raise _fail("schema_migration_invalid_plan", "migration plan has an unsupported shape")
    if plan.get("schema") != SCHEMA_MIGRATION_PLAN_SCHEMA or plan.get("policy") != SCHEMA_MIGRATION_POLICY_ID:
        raise _fail("schema_migration_invalid_plan", "migration plan schema/policy identity mismatch")

    expected = build_migration_plan(
        _require_text(plan.get("kind"), "kind"),
        _require_text(plan.get("source_identity"), "source_identity"),
        _require_text(plan.get("target_identity"), "target_identity"),
        source_ref=plan.get("source_ref"),
    )
    try:
        supplied_bytes = canonical_json(dict(plan))
        expected_bytes = canonical_json(expected)
    except (TypeError, ValueError, RecursionError) as exc:
        raise _fail(
            "schema_migration_invalid_plan",
            "migration plan must contain finite canonical JSON values",
        ) from exc
    if supplied_bytes != expected_bytes:
        raise _fail(
            "schema_migration_invalid_plan",
            "migration plan does not reproduce byte-for-byte under the current policy",
        )
    return {
        "status": "verified",
        "policy": SCHEMA_MIGRATION_POLICY_ID,
        "plan_ref": expected["plan_ref"],
        "classification": expected["classification"],
        "automatic_execution": False,
        "authority_effect": "none",
        "evidence_effect": "none",
    }


__all__ = [
    "SCHEMA_MIGRATION_PLAN_SCHEMA",
    "SCHEMA_MIGRATION_POLICY_ID",
    "SchemaMigrationError",
    "build_migration_plan",
    "classify_version_change",
    "schema_migration_policy_snapshot",
    "verify_migration_plan",
]
