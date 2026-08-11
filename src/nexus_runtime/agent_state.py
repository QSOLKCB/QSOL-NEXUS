from __future__ import annotations

import copy
from typing import Any

from .canonical import sha256_ref
from .world import WorldObject, WorldStore


AGENT_STATE_SCHEMA_VERSION = "nexus-agent-state/1"
CONTEXT_BOTTLENECK_SCHEMA_VERSION = "nexus-context-bottleneck/1"
AGENT_STATE_UPDATE_OBJECT_TYPE = "agent_state_update"
AGENT_STATE_SNAPSHOT_OBJECT_TYPE = "agent_state_snapshot"
AGENT_CONTEXT_OBJECT_TYPE = "agent_context"
AGENT_STATE_RESERVED_OBJECT_TYPES = frozenset(
    {
        AGENT_STATE_UPDATE_OBJECT_TYPE,
        AGENT_STATE_SNAPSHOT_OBJECT_TYPE,
        AGENT_CONTEXT_OBJECT_TYPE,
    }
)

# Lanes are deliberately closed and have deterministic ordering. Completion
# time never chooses precedence. Fast lanes may form a valid partial snapshot
# without waiting for slow reflective lanes.
LANE_POLICY: dict[str, dict[str, Any]] = {
    "safety_control": {"timescale": "fast", "priority": 0},
    "action_awareness": {"timescale": "fast", "priority": 1},
    "world_observation": {"timescale": "fast", "priority": 2},
    "memory": {"timescale": "medium", "priority": 3},
    "social_context": {"timescale": "medium", "priority": 4},
    "goals": {"timescale": "slow", "priority": 5},
}
LANE_ORDER = tuple(sorted(LANE_POLICY, key=lambda lane: LANE_POLICY[lane]["priority"]))
MAX_UPDATE_CONTENT_CHARS = 8_192
MAX_SOURCE_REFS_PER_UPDATE = 8
MAX_UPDATES_PER_SNAPSHOT = len(LANE_ORDER)
MAX_CONTEXT_EXCERPT_CHARS = 320
MAX_CONTEXT_CHARS = 2_700


class AgentStateError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def agent_state_policy_snapshot() -> dict[str, Any]:
    return {
        "schema_version": AGENT_STATE_SCHEMA_VERSION,
        "context_schema_version": CONTEXT_BOTTLENECK_SCHEMA_VERSION,
        "principle": "context_admission_is_not_epistemic_authority",
        "lanes": [
            {
                "lane": lane,
                "timescale": LANE_POLICY[lane]["timescale"],
                "priority": LANE_POLICY[lane]["priority"],
            }
            for lane in LANE_ORDER
        ],
        "limits": {
            "max_update_content_chars": MAX_UPDATE_CONTENT_CHARS,
            "max_source_refs_per_update": MAX_SOURCE_REFS_PER_UPDATE,
            "max_updates_per_snapshot": MAX_UPDATES_PER_SNAPSHOT,
            "max_context_excerpt_chars": MAX_CONTEXT_EXCERPT_CHARS,
            "max_context_chars": MAX_CONTEXT_CHARS,
        },
        "operations": [
            "agent.context.build",
            "agent.context.verify",
            "agent.state.policy",
            "agent.state.publish",
            "agent.state.snapshot",
        ],
        "concurrency_contract": {
            "partial_snapshots_allowed": True,
            "completion_order_is_semantic_authority": False,
            "canonical_lane_order": list(LANE_ORDER),
            "duplicate_lane_updates_in_one_snapshot": False,
            "future_or_missing_source_refs_admitted": False,
        },
        "authority_invariants": {
            "context_router_is_model": False,
            "context_router_has_vote": False,
            "context_router_has_epistemic_privilege": False,
            "context_selection_promotes_evidence_state": False,
            "state_update_creates_council_authority": False,
        },
        "claim_boundary": {
            "shared_state_is_content_addressed": True,
            "model_facing_context_reconstructible": True,
            "external_side_effects_verified": False,
            "semantic_truth_inferred_from_lane_priority": False,
        },
    }


def _validate_actor_id(actor_id: str) -> None:
    if not isinstance(actor_id, str) or not actor_id.strip():
        raise ValueError("actor_id must be non-empty text")
    if len(actor_id) > 128:
        raise ValueError("actor_id must be at most 128 characters")


def _validate_lane(lane: str) -> None:
    if not isinstance(lane, str) or lane not in LANE_POLICY:
        allowed = ", ".join(LANE_ORDER)
        raise ValueError(f"lane must be one of: {allowed}")


def _validated_existing_refs(world: WorldStore, source_refs: list[str]) -> list[str]:
    if not isinstance(source_refs, list) or not all(isinstance(ref, str) and ref for ref in source_refs):
        raise ValueError("source_refs must be a list of non-empty object references")
    if len(source_refs) > MAX_SOURCE_REFS_PER_UPDATE:
        raise ValueError(
            f"source_refs permits at most {MAX_SOURCE_REFS_PER_UPDATE} references"
        )
    canonical_refs = sorted(set(source_refs))
    if len(canonical_refs) != len(source_refs):
        raise ValueError("source_refs must not contain duplicates")
    for ref in canonical_refs:
        try:
            world.inspect(ref)
        except KeyError as exc:
            raise AgentStateError(
                "agent_state_source_not_found",
                "agent state source object was not found",
            ) from exc
    return canonical_refs


def publish_agent_state_update(
    world: WorldStore,
    *,
    actor_id: str,
    lane: str,
    content: str,
    source_refs: list[str],
) -> WorldObject:
    _validate_actor_id(actor_id)
    _validate_lane(lane)
    if not isinstance(content, str) or not content.strip():
        raise ValueError("content must be non-empty text")
    if len(content) > MAX_UPDATE_CONTENT_CHARS:
        raise ValueError(
            f"content must be at most {MAX_UPDATE_CONTENT_CHARS} characters"
        )
    canonical_refs = _validated_existing_refs(world, source_refs)
    policy = LANE_POLICY[lane]
    return world.create_object(
        AGENT_STATE_UPDATE_OBJECT_TYPE,
        {
            "schema_version": AGENT_STATE_SCHEMA_VERSION,
            "actor_id": actor_id,
            "lane": lane,
            "timescale": policy["timescale"],
            "priority": policy["priority"],
            "source_refs": canonical_refs,
            "content": content,
            "completion_order_has_authority": False,
        },
        {"actor": "nexus", "subsystem": "agent_state"},
    )


def _validated_update(world: WorldStore, update_ref: str) -> WorldObject:
    try:
        update = world.inspect(update_ref)
    except KeyError as exc:
        raise AgentStateError(
            "agent_state_update_not_found",
            "agent state update was not found",
        ) from exc
    if (
        update.object_type != AGENT_STATE_UPDATE_OBJECT_TYPE
        or update.provenance != {"actor": "nexus", "subsystem": "agent_state"}
    ):
        raise AgentStateError(
            "agent_state_update_required",
            "update_ref must identify a runtime-owned agent state update",
        )
    payload = update.payload
    lane = payload.get("lane")
    if (
        payload.get("schema_version") != AGENT_STATE_SCHEMA_VERSION
        or not isinstance(payload.get("actor_id"), str)
        or not isinstance(lane, str)
        or lane not in LANE_POLICY
        or payload.get("timescale") != LANE_POLICY[lane]["timescale"]
        or payload.get("priority") != LANE_POLICY[lane]["priority"]
        or not isinstance(payload.get("source_refs"), list)
        or not isinstance(payload.get("content"), str)
    ):
        raise AgentStateError(
            "agent_state_update_invalid",
            "agent state update schema is invalid",
        )
    return update


def create_agent_state_snapshot(
    world: WorldStore,
    *,
    actor_id: str,
    update_refs: list[str],
) -> WorldObject:
    _validate_actor_id(actor_id)
    if not isinstance(update_refs, list) or not update_refs:
        raise ValueError("update_refs must be a non-empty list")
    if len(update_refs) > MAX_UPDATES_PER_SNAPSHOT:
        raise ValueError(
            f"update_refs permits at most {MAX_UPDATES_PER_SNAPSHOT} references"
        )
    if not all(isinstance(ref, str) and ref for ref in update_refs):
        raise ValueError("update_refs must contain non-empty object references")
    if len(set(update_refs)) != len(update_refs):
        raise ValueError("update_refs must not contain duplicates")

    by_lane: dict[str, WorldObject] = {}
    for ref in update_refs:
        update = _validated_update(world, ref)
        if update.payload["actor_id"] != actor_id:
            raise AgentStateError(
                "agent_state_identity_mismatch",
                "all state updates in a snapshot must belong to the requested actor",
            )
        lane = update.payload["lane"]
        if lane in by_lane:
            raise AgentStateError(
                "agent_state_lane_conflict",
                "a snapshot may contain at most one update for each state lane",
            )
        by_lane[lane] = update

    canonical_updates: list[dict[str, Any]] = []
    flattened_sources: set[str] = set()
    for lane in LANE_ORDER:
        update = by_lane.get(lane)
        if update is None:
            continue
        sources = list(update.payload["source_refs"])
        flattened_sources.update(sources)
        canonical_updates.append(
            {
                "lane": lane,
                "timescale": LANE_POLICY[lane]["timescale"],
                "priority": LANE_POLICY[lane]["priority"],
                "update_ref": update.object_id,
                "source_refs": sources,
            }
        )

    return world.create_object(
        AGENT_STATE_SNAPSHOT_OBJECT_TYPE,
        {
            "schema_version": AGENT_STATE_SCHEMA_VERSION,
            "actor_id": actor_id,
            "canonical_lane_order": list(LANE_ORDER),
            "update_refs": [item["update_ref"] for item in canonical_updates],
            "updates": canonical_updates,
            "source_refs": sorted(flattened_sources),
            "partial_snapshot": len(canonical_updates) < len(LANE_ORDER),
            "completion_order_has_authority": False,
        },
        {"actor": "nexus", "subsystem": "agent_state"},
    )


def _validated_snapshot(world: WorldStore, snapshot_ref: str) -> WorldObject:
    try:
        snapshot = world.inspect(snapshot_ref)
    except KeyError as exc:
        raise AgentStateError(
            "agent_state_snapshot_not_found",
            "agent state snapshot was not found",
        ) from exc
    if (
        snapshot.object_type != AGENT_STATE_SNAPSHOT_OBJECT_TYPE
        or snapshot.provenance != {"actor": "nexus", "subsystem": "agent_state"}
    ):
        raise AgentStateError(
            "agent_state_snapshot_required",
            "snapshot_ref must identify a runtime-owned agent state snapshot",
        )
    payload = snapshot.payload
    refs = payload.get("update_refs")
    if (
        payload.get("schema_version") != AGENT_STATE_SCHEMA_VERSION
        or not isinstance(payload.get("actor_id"), str)
        or payload.get("canonical_lane_order") != list(LANE_ORDER)
        or not isinstance(refs, list)
        or not refs
    ):
        raise AgentStateError(
            "agent_state_snapshot_invalid",
            "agent state snapshot schema is invalid",
        )

    # Reconstruct the snapshot from immutable updates and require byte-identical
    # identity. This prevents forged ordering or stale copied lane metadata from
    # becoming model-facing state.
    reconstructed = create_agent_state_snapshot(
        world,
        actor_id=payload["actor_id"],
        update_refs=list(refs),
    )
    if reconstructed.object_id != snapshot.object_id:
        raise AgentStateError(
            "agent_state_snapshot_invalid",
            "agent state snapshot failed deterministic reconstruction",
        )
    return snapshot


def _bounded_excerpt(text: str) -> str:
    compact = " ".join(text.split())
    if len(compact) <= MAX_CONTEXT_EXCERPT_CHARS:
        return compact
    marker = " [excerpt truncated]"
    keep = max(0, MAX_CONTEXT_EXCERPT_CHARS - len(marker))
    return compact[:keep] + marker


def _context_payload(world: WorldStore, snapshot: WorldObject) -> dict[str, Any]:
    payload = snapshot.payload
    sections = [
        "NEXUS deterministic Agent State context.",
        "Context admission and lane priority do not establish truth, authority, or vote weight.",
        f"state_snapshot_ref={snapshot.object_id}",
        f"actor_id={payload['actor_id']}",
    ]
    selected_refs: list[str] = []
    source_refs: set[str] = set()

    for update_ref in payload["update_refs"]:
        update = _validated_update(world, update_ref)
        selected_refs.append(update.object_id)
        source_refs.update(update.payload["source_refs"])
        sections.extend(
            [
                (
                    f"update_ref={update.object_id} lane={update.payload['lane']} "
                    f"timescale={update.payload['timescale']} "
                    f"source_count={len(update.payload['source_refs'])}"
                ),
                f"excerpt={_bounded_excerpt(update.payload['content'])}",
            ]
        )

    content = "\n".join(sections)
    if len(content) > MAX_CONTEXT_CHARS:
        raise AgentStateError(
            "agent_context_budget_exceeded",
            "deterministic context exceeded its admitted character budget",
        )
    return {
        "schema_version": CONTEXT_BOTTLENECK_SCHEMA_VERSION,
        "state_snapshot_ref": snapshot.object_id,
        "actor_id": payload["actor_id"],
        "selected_update_refs": selected_refs,
        "source_refs": sorted(source_refs),
        "selection_policy": "closed_lane_order_bounded_excerpt_v1",
        "context_chars": len(content),
        "max_context_chars": MAX_CONTEXT_CHARS,
        "all_selected_updates_represented": True,
        "completion_order_has_authority": False,
        "epistemic_privilege": "none",
        "vote_weight_created": 0,
        "content": content,
        "claim_boundary": (
            "this is a deterministic bounded view of immutable state updates; "
            "lane order is routing priority and does not establish semantic truth"
        ),
    }


def build_agent_context(world: WorldStore, *, snapshot_ref: str) -> WorldObject:
    snapshot = _validated_snapshot(world, snapshot_ref)
    return world.create_object(
        AGENT_CONTEXT_OBJECT_TYPE,
        _context_payload(world, snapshot),
        {"actor": "nexus", "subsystem": "context_bottleneck"},
    )


def verify_agent_context(world: WorldStore, *, context_ref: str) -> dict[str, Any]:
    try:
        context = world.inspect(context_ref)
    except KeyError as exc:
        raise AgentStateError(
            "agent_context_not_found",
            "agent context was not found",
        ) from exc
    if (
        context.object_type != AGENT_CONTEXT_OBJECT_TYPE
        or context.provenance != {"actor": "nexus", "subsystem": "context_bottleneck"}
    ):
        raise AgentStateError(
            "agent_context_required",
            "context_ref must identify a runtime-owned agent context",
        )
    snapshot_ref = context.payload.get("state_snapshot_ref")
    if not isinstance(snapshot_ref, str):
        raise AgentStateError(
            "agent_context_invalid",
            "agent context schema is invalid",
        )
    snapshot = _validated_snapshot(world, snapshot_ref)
    expected_payload = _context_payload(world, snapshot)
    expected_ref = sha256_ref(
        "object",
        {
            "object_type": AGENT_CONTEXT_OBJECT_TYPE,
            "payload": copy.deepcopy(expected_payload),
            "provenance": {"actor": "nexus", "subsystem": "context_bottleneck"},
        },
    )
    verified = context.object_id == expected_ref and context.payload == expected_payload
    return {
        "status": "verified" if verified else "mismatch",
        "context_ref": context.object_id,
        "state_snapshot_ref": snapshot.object_id,
        "reconstructed_context_ref": expected_ref,
        "verified": verified,
        "model_inference_used": False,
    }


__all__ = [
    "AGENT_CONTEXT_OBJECT_TYPE",
    "AGENT_STATE_RESERVED_OBJECT_TYPES",
    "AGENT_STATE_SCHEMA_VERSION",
    "AGENT_STATE_SNAPSHOT_OBJECT_TYPE",
    "AGENT_STATE_UPDATE_OBJECT_TYPE",
    "AgentStateError",
    "CONTEXT_BOTTLENECK_SCHEMA_VERSION",
    "LANE_ORDER",
    "agent_state_policy_snapshot",
    "build_agent_context",
    "create_agent_state_snapshot",
    "publish_agent_state_update",
    "verify_agent_context",
]
