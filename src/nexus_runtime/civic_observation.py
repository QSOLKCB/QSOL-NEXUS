from __future__ import annotations

from collections import Counter
import copy
from typing import Any

from .geometry import WorldGeometry
from .modes import get_mode, list_modes
from .scrub import SecretScrubber
from .world import WorldStore


CIVIC_OBSERVATION_SCHEMA_VERSION = "nexus-civic-observation/1"

# Council deliberation remains committed before observation. The dedicated
# civic chamber and parole region are not cross-mode viewing locations.
RESTRICTED_OBSERVATION_REGION_IDS = frozenset(
    {"bureaucratic_vote_room", "upside_down"}
)

# Non-citizens retain meaningful public transparency, but only from the
# designated public-gallery regions. Citizens may carry the broader
# observation right into every other public, non-Council region. PR #40 may
# constitutionally narrow or reconfigure these two region sets through the
# bounded amendment policy surface; restricted regions remain non-amendable.
NON_CITIZEN_GALLERY_REGION_IDS = frozenset(
    {"observatory", "archive", "agora"}
)


class CivicObservationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _mode_ids_for_regions(region_ids: frozenset[str]) -> list[str]:
    return sorted(
        mode.mode_id
        for mode in list_modes()
        if mode.region_id in region_ids
        and mode.region_id not in RESTRICTED_OBSERVATION_REGION_IDS
    )


def _resolved_region_policy(
    geometry: WorldGeometry,
    *,
    citizen_region_ids: list[str] | tuple[str, ...] | frozenset[str] | None = None,
    public_gallery_region_ids: list[str] | tuple[str, ...] | frozenset[str] | None = None,
) -> tuple[frozenset[str], frozenset[str]]:
    all_regions = {
        str(item["region_id"])
        for item in geometry.snapshot()["regions"]
    }
    public_regions = frozenset(all_regions - RESTRICTED_OBSERVATION_REGION_IDS)
    citizens = (
        public_regions
        if citizen_region_ids is None
        else frozenset(citizen_region_ids)
    )
    gallery = (
        NON_CITIZEN_GALLERY_REGION_IDS
        if public_gallery_region_ids is None
        else frozenset(public_gallery_region_ids)
    )
    if not citizens or not citizens.issubset(public_regions):
        raise CivicObservationError(
            "council_observation_policy_invalid",
            "citizen observation regions must be a non-empty subset of public non-Council regions",
        )
    if not gallery or not gallery.issubset(citizens):
        raise CivicObservationError(
            "council_observation_policy_invalid",
            "public-gallery regions must be a non-empty subset of citizen observation regions",
        )
    return citizens, gallery


def civic_observation_policy_snapshot(
    geometry: WorldGeometry,
    *,
    citizen_region_ids: list[str] | tuple[str, ...] | frozenset[str] | None = None,
    public_gallery_region_ids: list[str] | tuple[str, ...] | frozenset[str] | None = None,
) -> dict[str, Any]:
    citizen_regions, gallery_regions = _resolved_region_policy(
        geometry,
        citizen_region_ids=citizen_region_ids,
        public_gallery_region_ids=public_gallery_region_ids,
    )
    return {
        "schema_version": CIVIC_OBSERVATION_SCHEMA_VERSION,
        "principle": "citizenship_widens_observation_not_authority",
        "completed_proceedings_only": True,
        "read_only": True,
        "constitutional_policy_consumed": True,
        "citizen": {
            "access_tier": "citizen_full",
            "requires_exact_registered_model_identity": True,
            "requires_current_region_match": True,
            "cross_mode_observation": True,
            "allowed_region_ids": sorted(citizen_regions),
            "allowed_mode_ids": _mode_ids_for_regions(citizen_regions),
            "record_view": "full_scrubbed_public_proceeding",
        },
        "non_citizen": {
            "access_tier": "public_gallery",
            "cross_mode_observation": False,
            "allowed_region_ids": sorted(gallery_regions),
            "allowed_mode_ids": _mode_ids_for_regions(gallery_regions),
            "record_view": "bounded_public_summary",
        },
        "restricted_region_ids": sorted(RESTRICTED_OBSERVATION_REGION_IDS),
        "authority_invariants": {
            "observation_changes_vote_weight": False,
            "observation_changes_epistemic_privilege": False,
            "observation_creates_council_seat": False,
            "observation_can_mutate_proceeding": False,
            "citizen_vote_weight": 1,
            "citizen_epistemic_privilege": "none",
        },
        "claim_boundary": {
            "in_world_civic_capability": True,
            "real_world_authentication_or_authorization": False,
            "live_deliberation_side_channel": False,
            "secret_or_raw_transport_access": False,
        },
    }


def _scrub_tree(value: Any, scrubber: SecretScrubber) -> Any:
    if isinstance(value, str):
        return scrubber.scrub(value).text
    if isinstance(value, list):
        return [_scrub_tree(item, scrubber) for item in value]
    if isinstance(value, tuple):
        return [_scrub_tree(item, scrubber) for item in value]
    if isinstance(value, dict):
        return {key: _scrub_tree(item, scrubber) for key, item in value.items()}
    return copy.deepcopy(value)


def _public_roster(payload: dict[str, Any]) -> list[dict[str, Any]]:
    roster = payload.get("roster", [])
    if not isinstance(roster, list):
        raise CivicObservationError(
            "council_proceeding_invalid",
            "committed Council proceeding has an invalid roster",
        )
    public: list[dict[str, Any]] = []
    for item in roster:
        if not isinstance(item, dict):
            raise CivicObservationError(
                "council_proceeding_invalid",
                "committed Council proceeding has an invalid roster entry",
            )
        public.append(
            {
                "member_id": item.get("member_id"),
                "model_id": item.get("model_id"),
                "adapter_id": item.get("adapter_id"),
                "vote_weight": item.get("vote_weight"),
                "epistemic_privilege": item.get("epistemic_privilege"),
            }
        )
    return public


def _ballot_summary(payload: dict[str, Any]) -> dict[str, Any]:
    ballots = payload.get("revealed_ballots", [])
    if not isinstance(ballots, list):
        raise CivicObservationError(
            "council_proceeding_invalid",
            "committed Council proceeding has invalid revealed ballots",
        )
    choices: list[str] = []
    for ballot in ballots:
        if not isinstance(ballot, dict) or not isinstance(ballot.get("choice"), str):
            raise CivicObservationError(
                "council_proceeding_invalid",
                "committed Council proceeding has an invalid ballot entry",
            )
        choices.append(ballot["choice"])
    counts = Counter(choices)
    return {
        "ballot_count": len(choices),
        "choice_counts": {choice: counts[choice] for choice in sorted(counts)},
        "minority_or_disagreement_present": len(counts) > 1,
        "individual_rationales_visible": False,
    }


def _resolve_viewer_tier(
    citizenship: Any,
    *,
    viewer_id: str | None,
    viewer_model_id: str | None,
    source_region_id: str,
) -> tuple[str, dict[str, Any] | None]:
    if (viewer_id is None) != (viewer_model_id is None):
        raise CivicObservationError(
            "council_observation_invalid_viewer",
            "viewer_id and viewer_model_id must be supplied together",
        )
    if viewer_id is None:
        return "public_gallery", None
    if not isinstance(viewer_id, str) or not viewer_id:
        raise CivicObservationError(
            "council_observation_invalid_viewer",
            "viewer_id must be non-empty text when supplied",
        )
    if not isinstance(viewer_model_id, str) or not viewer_model_id:
        raise CivicObservationError(
            "council_observation_invalid_viewer",
            "viewer_model_id must be non-empty text when supplied",
        )

    state = citizenship.registry.latest_state(viewer_id)
    if state is None:
        return "public_gallery", None
    if state.payload.get("model_id") != viewer_model_id:
        raise CivicObservationError(
            "council_observation_identity_mismatch",
            "registered civic identity does not match viewer_model_id",
        )
    if state.payload.get("current_region_id") != source_region_id:
        raise CivicObservationError(
            "council_observation_region_mismatch",
            "registered civic identity is not currently in the source mode region",
        )
    if state.payload.get("status") != "citizen":
        return "public_gallery", state.payload
    return "citizen_full", state.payload


def view_council_proceeding(
    *,
    world: WorldStore,
    citizenship: Any,
    geometry: WorldGeometry,
    scrubber: SecretScrubber,
    session_ref: str,
    source_mode_id: str,
    viewer_id: str | None = None,
    viewer_model_id: str | None = None,
    citizen_region_ids: list[str] | tuple[str, ...] | frozenset[str] | None = None,
    public_gallery_region_ids: list[str] | tuple[str, ...] | frozenset[str] | None = None,
) -> dict[str, Any]:
    mode = get_mode(source_mode_id)
    source_region_id = geometry.region_for_mode(mode.mode_id).region_id
    if source_region_id in RESTRICTED_OBSERVATION_REGION_IDS:
        raise CivicObservationError(
            "council_observation_region_restricted",
            "Council proceedings cannot be cross-mode viewed from this region",
        )
    citizen_regions, gallery_regions = _resolved_region_policy(
        geometry,
        citizen_region_ids=citizen_region_ids,
        public_gallery_region_ids=public_gallery_region_ids,
    )

    tier, citizen_state = _resolve_viewer_tier(
        citizenship,
        viewer_id=viewer_id,
        viewer_model_id=viewer_model_id,
        source_region_id=source_region_id,
    )
    if tier == "citizen_full" and source_region_id not in citizen_regions:
        raise CivicObservationError(
            "council_observation_citizen_region_not_admitted",
            "the active constitutional version does not admit Civic Observation from this citizen region",
        )
    if tier == "public_gallery" and source_region_id not in gallery_regions:
        raise CivicObservationError(
            "council_observation_public_gallery_required",
            "non-citizens may view Council proceedings only from designated public-gallery regions",
        )

    try:
        session = world.inspect(session_ref)
    except KeyError as exc:
        raise CivicObservationError(
            "council_proceeding_not_found",
            "Council proceeding was not found",
        ) from exc
    if session.object_type != "council_session" or session.provenance != {"actor": "nexus"}:
        raise CivicObservationError(
            "council_proceeding_required",
            "session_ref must identify a committed NEXUS Council proceeding",
        )

    payload = session.payload
    question_ref = payload.get("question_ref")
    evidence_snapshot_ref = payload.get("evidence_snapshot_ref")
    if not isinstance(question_ref, str) or not isinstance(evidence_snapshot_ref, str):
        raise CivicObservationError(
            "council_proceeding_invalid",
            "committed Council proceeding is missing immutable input references",
        )
    question = world.inspect(question_ref)
    evidence = world.inspect(evidence_snapshot_ref)
    if question.object_type != "question" or evidence.object_type != "evidence_snapshot":
        raise CivicObservationError(
            "council_proceeding_invalid",
            "committed Council proceeding references invalid input objects",
        )

    common: dict[str, Any] = {
        "status": "ok",
        "schema_version": CIVIC_OBSERVATION_SCHEMA_VERSION,
        "access_tier": tier,
        "read_only": True,
        "completed_proceeding": True,
        "session_ref": session.object_id,
        "session_id": payload.get("session_id"),
        "source_mode_id": mode.mode_id,
        "source_region_id": source_region_id,
        "question": {
            "question_ref": question.object_id,
            "text": question.payload.get("text"),
        },
        "evidence": {
            "evidence_snapshot_ref": evidence.object_id,
            "evidence_state": evidence.payload.get("evidence_state"),
            "included_object_refs": list(evidence.payload.get("included_object_refs", [])),
        },
        "council": {
            "mode": copy.deepcopy(payload.get("world_mode")),
            "geometry_region": copy.deepcopy(payload.get("geometry_region")),
            "roster": _public_roster(payload),
            "result": copy.deepcopy(payload.get("result")),
        },
        "authority_invariant": {
            "viewer_gains_vote": False,
            "viewer_gains_epistemic_privilege": False,
            "viewer_can_mutate_proceeding": False,
            "observation_is_evidence_upgrade": False,
        },
    }

    if tier == "citizen_full":
        common["citizenship"] = {
            "citizen_id": viewer_id,
            "citizen_state_ref": citizenship.registry.latest_state(viewer_id).object_id,
            "cross_mode_observation_right": True,
            "vote_weight": citizen_state.get("vote_weight") if citizen_state is not None else 1,
            "epistemic_privilege": (
                citizen_state.get("epistemic_privilege") if citizen_state is not None else "none"
            ),
        }
        common["proceeding"] = {
            "phase_submissions": copy.deepcopy(payload.get("phase_submissions", {})),
            "guard_events": copy.deepcopy(payload.get("guard_events", [])),
            "revealed_ballots": copy.deepcopy(payload.get("revealed_ballots", [])),
            "telemetry": copy.deepcopy(payload.get("telemetry")),
            "failsafe": copy.deepcopy(payload.get("failsafe")),
        }
    else:
        common["citizenship"] = {
            "citizen_id": None,
            "cross_mode_observation_right": False,
            "public_gallery": True,
        }
        common["proceeding"] = {
            "ballot_summary": _ballot_summary(payload),
            "phase_order_completed": list(payload.get("phase_submissions", {}).keys())
            if isinstance(payload.get("phase_submissions"), dict)
            else [],
            "phase_text_visible": False,
            "individual_ballots_visible": False,
        }

    return _scrub_tree(common, scrubber)


__all__ = [
    "CIVIC_OBSERVATION_SCHEMA_VERSION",
    "CivicObservationError",
    "NON_CITIZEN_GALLERY_REGION_IDS",
    "RESTRICTED_OBSERVATION_REGION_IDS",
    "civic_observation_policy_snapshot",
    "view_council_proceeding",
]
