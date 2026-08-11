from __future__ import annotations

from collections import Counter
from dataclasses import replace
from typing import Any, Iterable

from .compute_epochs import (
    compute_epoch_policy_snapshot,
    current_compute_epoch,
    small_model_threshold_millions,
)
from .council_chair import (
    COUNCIL_CHAIR_SCHEMA,
    MAX_CLOSED_GENERAL_SEATS,
    MAX_COUNCIL_VOTING_SEATS,
    MAX_LARGE_OPEN_WEIGHT_SEATS,
    MIN_COUNCIL_VOTING_SEATS,
    ChairSeatClassification,
    chair_policy_snapshot,
    classify_member_request,
)


EPOCH_CHAIR_SCHEMA = "nexus-council-chair-epoch/1"


def classify_member_request_at_epoch(
    item: object,
    *,
    epoch: int,
) -> ChairSeatClassification:
    classification = classify_member_request(item)
    count = classification.parameter_count_millions
    threshold = small_model_threshold_millions(epoch)

    if count is not None and count <= threshold:
        slot_class = "protected_small"
    elif classification.distribution == "open_weight":
        slot_class = "large_open_weight"
    else:
        slot_class = "closed_general"

    return replace(classification, slot_class=slot_class)


def evaluate_epoch_council_roster_request(
    members: Iterable[object],
    *,
    epoch: int | None = None,
) -> dict[str, Any]:
    resolved_epoch = current_compute_epoch() if epoch is None else epoch
    threshold = small_model_threshold_millions(resolved_epoch)
    roster = list(members)
    if not MIN_COUNCIL_VOTING_SEATS <= len(roster) <= MAX_COUNCIL_VOTING_SEATS:
        raise ValueError(
            f"Council Chair requires {MIN_COUNCIL_VOTING_SEATS} to {MAX_COUNCIL_VOTING_SEATS} voting seats"
        )

    classifications = [
        classify_member_request_at_epoch(item, epoch=resolved_epoch) for item in roster
    ]
    identities = [
        (classification.adapter_id, classification.effective_model_id)
        for classification in classifications
    ]
    if len(identities) != len(set(identities)):
        raise ValueError(
            "Council Chair requires distinct effective adapter/model identities for every voting seat"
        )

    counts = Counter(classification.slot_class for classification in classifications)
    if counts["protected_small"] < 1:
        raise ValueError(
            "Council Chair Small-Mind Guarantee requires at least one protected "
            f"<={threshold}M total-parameter voting seat at Compute Epoch {resolved_epoch}"
        )
    if counts["closed_general"] > MAX_CLOSED_GENERAL_SEATS:
        raise ValueError(
            f"Council Chair permits at most {MAX_CLOSED_GENERAL_SEATS} closed-model general seats; "
            f"a <={threshold}M closed model may instead qualify for the protected small seat"
        )
    if counts["large_open_weight"] > MAX_LARGE_OPEN_WEIGHT_SEATS:
        raise ValueError(
            f"Council Chair permits at most {MAX_LARGE_OPEN_WEIGHT_SEATS} large open-weight "
            f"(>{threshold}M at Compute Epoch {resolved_epoch}) seats"
        )

    return {
        "schema": COUNCIL_CHAIR_SCHEMA,
        "epoch_schema": EPOCH_CHAIR_SCHEMA,
        "status": "admitted",
        "seat_count": len(classifications),
        "slot_counts": {
            "protected_small": counts["protected_small"],
            "closed_general": counts["closed_general"],
            "large_open_weight": counts["large_open_weight"],
        },
        "compute_epoch": compute_epoch_policy_snapshot(resolved_epoch),
        "small_mind_guarantee_satisfied": True,
        "vote_weight_per_seat": 1,
        "epistemic_privilege_per_seat": "none",
        "seats": [classification.as_dict() for classification in classifications],
    }


def validate_epoch_council_roster_request(
    members: Iterable[object],
    *,
    epoch: int | None = None,
) -> None:
    evaluate_epoch_council_roster_request(members, epoch=epoch)


def epoch_chair_policy_snapshot(epoch: int | None = None) -> dict[str, Any]:
    resolved_epoch = current_compute_epoch() if epoch is None else epoch
    legacy = chair_policy_snapshot()
    threshold = small_model_threshold_millions(resolved_epoch)
    protected = dict(legacy["protected_small_seat"])
    protected["base_maximum_total_parameter_count_millions"] = protected[
        "maximum_total_parameter_count_millions"
    ]
    protected["maximum_total_parameter_count_millions"] = threshold
    protected["compute_epoch"] = resolved_epoch
    return {
        **legacy,
        "schema": COUNCIL_CHAIR_SCHEMA,
        "epoch_schema": EPOCH_CHAIR_SCHEMA,
        "compute_epoch": compute_epoch_policy_snapshot(resolved_epoch),
        "protected_small_seat": protected,
        "temporal_compute_equality": (
            "time_may_enlarge_the_chair_but_may_not_enlarge_the_vote"
        ),
    }


__all__ = [
    "EPOCH_CHAIR_SCHEMA",
    "classify_member_request_at_epoch",
    "epoch_chair_policy_snapshot",
    "evaluate_epoch_council_roster_request",
    "validate_epoch_council_roster_request",
]
