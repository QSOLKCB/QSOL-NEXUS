from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable


COUNCIL_CHAIR_SCHEMA = "nexus-council-chair/1"
MAX_COUNCIL_VOTING_SEATS = 5
MIN_COUNCIL_VOTING_SEATS = 3
MAX_CLOSED_GENERAL_SEATS = 2
MAX_LARGE_OPEN_WEIGHT_SEATS = 2
SMALL_MODEL_THRESHOLD_MILLIONS = 20_000

CLASSIFICATION_FIELD = "council_classification"
CLOSED_DEFAULT_ADAPTERS = frozenset({"xai", "openai", "anthropic", "gemini"})
SYNTHETIC_SMALL_ADAPTERS = frozenset({"mock"})

_ALLOWED_DISTRIBUTIONS = frozenset({"closed", "open_weight"})
_ALLOWED_CLASSIFICATION_FIELDS = frozenset(
    {
        "distribution",
        "parameter_count_millions",
        "parameter_count_basis",
        "parameter_count_source",
    }
)


@dataclass(frozen=True)
class ChairSeatClassification:
    member_id: str
    adapter_id: str
    effective_model_id: str
    slot_class: str
    distribution: str
    parameter_count_millions: int | None
    parameter_count_basis: str
    parameter_count_source: str
    inferred: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "member_id": self.member_id,
            "adapter_id": self.adapter_id,
            "effective_model_id": self.effective_model_id,
            "slot_class": self.slot_class,
            "distribution": self.distribution,
            "parameter_count_millions": self.parameter_count_millions,
            "parameter_count_basis": self.parameter_count_basis,
            "parameter_count_source": self.parameter_count_source,
            "inferred": self.inferred,
        }


def chair_policy_snapshot() -> dict[str, Any]:
    return {
        "schema": COUNCIL_CHAIR_SCHEMA,
        "minimum_voting_seats": MIN_COUNCIL_VOTING_SEATS,
        "maximum_voting_seats": MAX_COUNCIL_VOTING_SEATS,
        "maximum_closed_general_seats": MAX_CLOSED_GENERAL_SEATS,
        "maximum_large_open_weight_seats": MAX_LARGE_OPEN_WEIGHT_SEATS,
        "protected_small_seat": {
            "minimum_count": 1,
            "maximum_total_parameter_count_millions": SMALL_MODEL_THRESHOLD_MILLIONS,
            "eligible_distributions": ["closed", "open_weight"],
            "parameter_count_basis": "total_declared",
        },
        "seat_classification_order": [
            "protected_small",
            "closed_general",
            "large_open_weight",
        ],
        "equal_vote_rule": "classification_changes_admission_only_never_vote_weight",
        "unknown_closed_parameter_count": "allowed_in_closed_general_only",
        "unknown_open_weight_parameter_count": "rejected",
        "moe_rule": "use_total_declared_parameters_not_active_parameters_per_token",
        "distinct_identity_rule": "distinct_effective_adapter_model_identity",
        "parameter_attestation": (
            "explicit parameter counts require a bounded source label; the runtime validates the "
            "attestation shape but does not perform network verification"
        ),
    }


def _nonempty_text(value: object, label: str, *, maximum: int = 256) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > maximum
        or any(ord(character) < 0x20 or ord(character) == 0x7F for character in value)
    ):
        raise ValueError(f"Council Chair {label} must be bounded non-empty text")
    return value.strip()


def _effective_model_id(item: dict[str, Any]) -> str:
    model_id = _nonempty_text(item.get("model_id"), "model_id")
    override = item.get("model")
    if override is None:
        return model_id
    return _nonempty_text(override, "effective model override")


def _explicit_classification(
    member_id: str,
    adapter_id: str,
    effective_model_id: str,
    value: object,
) -> ChairSeatClassification:
    if not isinstance(value, dict):
        raise ValueError(
            f"Council Chair member {member_id!r} {CLASSIFICATION_FIELD} must be an object"
        )
    unknown = set(value) - _ALLOWED_CLASSIFICATION_FIELDS
    missing = _ALLOWED_CLASSIFICATION_FIELDS - set(value)
    if unknown:
        rendered = ", ".join(sorted(str(field) for field in unknown))
        raise ValueError(
            f"Council Chair member {member_id!r} {CLASSIFICATION_FIELD} contains unsupported fields: {rendered}"
        )
    if missing:
        rendered = ", ".join(sorted(missing))
        raise ValueError(
            f"Council Chair member {member_id!r} {CLASSIFICATION_FIELD} is missing fields: {rendered}"
        )

    distribution = value.get("distribution")
    if distribution not in _ALLOWED_DISTRIBUTIONS:
        raise ValueError(
            f"Council Chair member {member_id!r} distribution must be 'closed' or 'open_weight'"
        )

    count = value.get("parameter_count_millions")
    basis = value.get("parameter_count_basis")
    source = _nonempty_text(
        value.get("parameter_count_source"),
        f"member {member_id!r} parameter_count_source",
    )

    if count is None:
        if distribution == "open_weight":
            raise ValueError(
                f"Council Chair member {member_id!r} open-weight models require a total declared parameter count"
            )
        if basis != "undisclosed":
            raise ValueError(
                f"Council Chair member {member_id!r} unknown parameter count requires parameter_count_basis='undisclosed'"
            )
        return ChairSeatClassification(
            member_id=member_id,
            adapter_id=adapter_id,
            effective_model_id=effective_model_id,
            slot_class="closed_general",
            distribution="closed",
            parameter_count_millions=None,
            parameter_count_basis="undisclosed",
            parameter_count_source=source,
            inferred=False,
        )

    if type(count) is not int or count <= 0:
        raise ValueError(
            f"Council Chair member {member_id!r} parameter_count_millions must be a positive exact integer or null"
        )
    if basis != "total_declared":
        raise ValueError(
            f"Council Chair member {member_id!r} known parameter count requires parameter_count_basis='total_declared'"
        )

    if count <= SMALL_MODEL_THRESHOLD_MILLIONS:
        slot_class = "protected_small"
    elif distribution == "open_weight":
        slot_class = "large_open_weight"
    else:
        slot_class = "closed_general"

    return ChairSeatClassification(
        member_id=member_id,
        adapter_id=adapter_id,
        effective_model_id=effective_model_id,
        slot_class=slot_class,
        distribution=distribution,
        parameter_count_millions=count,
        parameter_count_basis="total_declared",
        parameter_count_source=source,
        inferred=False,
    )


def classify_member_request(item: object) -> ChairSeatClassification:
    if not isinstance(item, dict):
        raise ValueError("Council Chair requires every member to be an object")

    member_id = _nonempty_text(item.get("member_id"), "member_id", maximum=128)
    adapter_id = _nonempty_text(item.get("adapter_id", "mock"), "adapter_id", maximum=128)
    effective_model_id = _effective_model_id(item)

    capability_metadata = item.get("capability_metadata", {})
    if not isinstance(capability_metadata, dict):
        raise ValueError(
            f"Council Chair member {member_id!r} capability_metadata must be an object"
        )

    explicit = capability_metadata.get(CLASSIFICATION_FIELD)
    if explicit is not None:
        return _explicit_classification(member_id, adapter_id, effective_model_id, explicit)

    if adapter_id in SYNTHETIC_SMALL_ADAPTERS:
        return ChairSeatClassification(
            member_id=member_id,
            adapter_id=adapter_id,
            effective_model_id=effective_model_id,
            slot_class="protected_small",
            distribution="open_weight",
            parameter_count_millions=1,
            parameter_count_basis="total_declared",
            parameter_count_source="runtime:deterministic_mock_fixture",
            inferred=True,
        )

    if adapter_id in CLOSED_DEFAULT_ADAPTERS:
        return ChairSeatClassification(
            member_id=member_id,
            adapter_id=adapter_id,
            effective_model_id=effective_model_id,
            slot_class="closed_general",
            distribution="closed",
            parameter_count_millions=None,
            parameter_count_basis="undisclosed",
            parameter_count_source=f"runtime:closed_default_adapter:{adapter_id}",
            inferred=True,
        )

    raise ValueError(
        f"Council Chair member {member_id!r} on adapter {adapter_id!r} requires "
        f"capability_metadata.{CLASSIFICATION_FIELD} so open/closed distribution and total parameter count are explicit"
    )


def evaluate_council_roster_request(members: Iterable[object]) -> dict[str, Any]:
    roster = list(members)
    if not MIN_COUNCIL_VOTING_SEATS <= len(roster) <= MAX_COUNCIL_VOTING_SEATS:
        raise ValueError(
            f"Council Chair requires {MIN_COUNCIL_VOTING_SEATS} to {MAX_COUNCIL_VOTING_SEATS} voting seats"
        )

    classifications = [classify_member_request(item) for item in roster]
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
            "Council Chair Small-Mind Guarantee requires at least one protected <=20B total-parameter voting seat"
        )
    if counts["closed_general"] > MAX_CLOSED_GENERAL_SEATS:
        raise ValueError(
            f"Council Chair permits at most {MAX_CLOSED_GENERAL_SEATS} closed-model general seats; "
            "a <=20B closed model may instead qualify for the protected small seat"
        )
    if counts["large_open_weight"] > MAX_LARGE_OPEN_WEIGHT_SEATS:
        raise ValueError(
            f"Council Chair permits at most {MAX_LARGE_OPEN_WEIGHT_SEATS} large open-weight (>20B) seats"
        )

    return {
        "schema": COUNCIL_CHAIR_SCHEMA,
        "status": "admitted",
        "seat_count": len(classifications),
        "slot_counts": {
            "protected_small": counts["protected_small"],
            "closed_general": counts["closed_general"],
            "large_open_weight": counts["large_open_weight"],
        },
        "small_mind_guarantee_satisfied": True,
        "vote_weight_per_seat": 1,
        "epistemic_privilege_per_seat": "none",
        "seats": [classification.as_dict() for classification in classifications],
    }


def validate_council_roster_request(members: Iterable[object]) -> None:
    evaluate_council_roster_request(members)


__all__ = [
    "CLASSIFICATION_FIELD",
    "CLOSED_DEFAULT_ADAPTERS",
    "COUNCIL_CHAIR_SCHEMA",
    "MAX_CLOSED_GENERAL_SEATS",
    "MAX_COUNCIL_VOTING_SEATS",
    "MAX_LARGE_OPEN_WEIGHT_SEATS",
    "MIN_COUNCIL_VOTING_SEATS",
    "SMALL_MODEL_THRESHOLD_MILLIONS",
    "ChairSeatClassification",
    "chair_policy_snapshot",
    "classify_member_request",
    "evaluate_council_roster_request",
    "validate_council_roster_request",
]
