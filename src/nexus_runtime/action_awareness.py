from __future__ import annotations

import copy
from typing import Any

from .canonical import sha256_ref
from .world import WorldObject, WorldStore


ACTION_AWARENESS_SCHEMA_VERSION = "nexus-action-awareness/1"
ACTION_EXPECTATION_OBJECT_TYPE = "action_expectation"
ACTION_RECONCILIATION_OBJECT_TYPE = "action_reconciliation"
ACTION_AWARENESS_RESERVED_OBJECT_TYPES = frozenset(
    {ACTION_EXPECTATION_OBJECT_TYPE, ACTION_RECONCILIATION_OBJECT_TYPE}
)
RECONCILIATION_OUTCOMES = ("matched", "diverged", "missing")


class ActionAwarenessError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def action_awareness_policy_snapshot() -> dict[str, Any]:
    return {
        "schema_version": ACTION_AWARENESS_SCHEMA_VERSION,
        "principle": "world_state_over_model_self_report",
        "scope": "content_addressed_world_object_creation",
        "operations": [
            "action.awareness.expect_create",
            "action.awareness.policy",
            "action.awareness.reconcile",
        ],
        "reconciliation_outcomes": list(RECONCILIATION_OUTCOMES),
        "deterministic_observation": True,
        "model_self_report_is_authoritative": False,
        "authority_invariants": {
            "expectation_creates_world_object": False,
            "reconciliation_mutates_observed_object": False,
            "reconciliation_promotes_evidence_state": False,
            "model_may_declare_its_own_success": False,
        },
        "claim_boundary": {
            "verifies_expected_content_addressed_object_presence": True,
            "verifies_real_world_effects": False,
            "verifies_external_provider_side_effects": False,
            "generalized_operation_replay": False,
        },
    }


def expected_world_object_ref(
    object_type: str,
    payload: dict[str, Any],
    provenance: dict[str, Any],
) -> str:
    if not isinstance(object_type, str) or not object_type:
        raise ValueError("expected object_type must be non-empty text")
    if not isinstance(payload, dict):
        raise ValueError("expected payload must be an object")
    if not isinstance(provenance, dict):
        raise ValueError("expected provenance must be an object")
    return sha256_ref(
        "object",
        {
            "object_type": object_type,
            "payload": copy.deepcopy(payload),
            "provenance": copy.deepcopy(provenance),
        },
    )


def create_action_expectation(
    world: WorldStore,
    *,
    actor_id: str,
    action_label: str,
    object_type: str,
    payload: dict[str, Any],
    provenance: dict[str, Any],
) -> WorldObject:
    if not isinstance(actor_id, str) or not actor_id:
        raise ValueError("actor_id must be non-empty text")
    if not isinstance(action_label, str) or not action_label:
        raise ValueError("action_label must be non-empty text")
    if object_type in ACTION_AWARENESS_RESERVED_OBJECT_TYPES:
        raise ValueError("action awareness cannot recursively expect its own runtime object types")

    expected_ref = expected_world_object_ref(object_type, payload, provenance)
    return world.create_object(
        ACTION_EXPECTATION_OBJECT_TYPE,
        {
            "schema_version": ACTION_AWARENESS_SCHEMA_VERSION,
            "expectation_kind": "world_object_create",
            "actor_id": actor_id,
            "action_label": action_label,
            "expected_object": {
                "object_ref": expected_ref,
                "object_type": object_type,
                "payload": copy.deepcopy(payload),
                "provenance": copy.deepcopy(provenance),
            },
            "model_self_report_is_authoritative": False,
        },
        {"actor": "nexus", "subsystem": "action_awareness"},
    )


def _validated_expectation(world: WorldStore, expectation_ref: str) -> WorldObject:
    try:
        expectation = world.inspect(expectation_ref)
    except KeyError as exc:
        raise ActionAwarenessError(
            "action_expectation_not_found",
            "action expectation was not found",
        ) from exc
    if expectation.object_type != ACTION_EXPECTATION_OBJECT_TYPE:
        raise ActionAwarenessError(
            "action_expectation_required",
            "expectation_ref must identify an action expectation",
        )
    if expectation.provenance != {"actor": "nexus", "subsystem": "action_awareness"}:
        raise ActionAwarenessError(
            "action_expectation_invalid",
            "action expectation provenance is invalid",
        )
    payload = expectation.payload
    expected_object = payload.get("expected_object")
    if (
        payload.get("schema_version") != ACTION_AWARENESS_SCHEMA_VERSION
        or payload.get("expectation_kind") != "world_object_create"
        or not isinstance(expected_object, dict)
    ):
        raise ActionAwarenessError(
            "action_expectation_invalid",
            "action expectation schema is invalid",
        )
    object_ref = expected_object.get("object_ref")
    object_type = expected_object.get("object_type")
    object_payload = expected_object.get("payload")
    object_provenance = expected_object.get("provenance")
    if (
        not isinstance(object_ref, str)
        or not isinstance(object_type, str)
        or not isinstance(object_payload, dict)
        or not isinstance(object_provenance, dict)
    ):
        raise ActionAwarenessError(
            "action_expectation_invalid",
            "action expectation expected-object fields are invalid",
        )
    recomputed = expected_world_object_ref(object_type, object_payload, object_provenance)
    if recomputed != object_ref:
        raise ActionAwarenessError(
            "action_expectation_invalid",
            "action expectation failed content-address verification",
        )
    return expectation


def reconcile_action_expectation(
    world: WorldStore,
    *,
    expectation_ref: str,
    observed_object_ref: str | None = None,
) -> WorldObject:
    expectation = _validated_expectation(world, expectation_ref)
    expected = expectation.payload["expected_object"]
    expected_ref = expected["object_ref"]

    observed: WorldObject | None = None
    effective_observed_ref: str | None = observed_object_ref
    if observed_object_ref is None:
        try:
            observed = world.inspect(expected_ref)
            effective_observed_ref = expected_ref
        except KeyError:
            observed = None
    else:
        try:
            observed = world.inspect(observed_object_ref)
        except KeyError as exc:
            raise ActionAwarenessError(
                "action_observation_not_found",
                "observed world object was not found",
            ) from exc

    if observed is None:
        outcome = "missing"
        matched = False
    elif observed.object_id == expected_ref:
        outcome = "matched"
        matched = True
    else:
        outcome = "diverged"
        matched = False

    reconciliation = world.create_object(
        ACTION_RECONCILIATION_OBJECT_TYPE,
        {
            "schema_version": ACTION_AWARENESS_SCHEMA_VERSION,
            "expectation_ref": expectation.object_id,
            "actor_id": expectation.payload["actor_id"],
            "action_label": expectation.payload["action_label"],
            "expected_object_ref": expected_ref,
            "observed_object_ref": effective_observed_ref,
            "observed_object_type": None if observed is None else observed.object_type,
            "outcome": outcome,
            "matched": matched,
            "world_observation_only": True,
            "model_self_report_used": False,
            "observed_object_mutated": False,
            "evidence_state_promoted": False,
        },
        {"actor": "nexus", "subsystem": "action_awareness"},
    )
    return reconciliation


__all__ = [
    "ACTION_AWARENESS_RESERVED_OBJECT_TYPES",
    "ACTION_AWARENESS_SCHEMA_VERSION",
    "ACTION_EXPECTATION_OBJECT_TYPE",
    "ACTION_RECONCILIATION_OBJECT_TYPE",
    "ActionAwarenessError",
    "action_awareness_policy_snapshot",
    "create_action_expectation",
    "expected_world_object_ref",
    "reconcile_action_expectation",
]
