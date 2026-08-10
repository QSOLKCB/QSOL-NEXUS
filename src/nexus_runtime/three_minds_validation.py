from __future__ import annotations

from typing import Any, Iterable


MAX_TASK_QUESTION_CHARS = 1_500


def _member_label(index: int | None, member: Any) -> str:
    prefix = "mind" if index is None else f"mind {index + 1}"
    if isinstance(member, dict):
        member_id = member.get("member_id")
        if isinstance(member_id, str) and member_id:
            return f"{prefix} (member_id={member_id!r})"
    return prefix


def public_member(member: Any, *, index: int | None = None) -> dict[str, str]:
    """Validate constitutional/public identity fields for one alpha11 participant."""

    label = _member_label(index, member)
    if not isinstance(member, dict):
        raise ValueError(f"{label} specification must be an object")

    member_id = member.get("member_id")
    model_id = member.get("model_id")
    adapter_id = member.get("adapter_id", "mock")
    if not isinstance(member_id, str) or not member_id:
        raise ValueError(f"{label} field member_id must be non-empty text")
    if not isinstance(model_id, str) or not model_id:
        raise ValueError(f"{label} field model_id must be non-empty text")
    if not isinstance(adapter_id, str) or not adapter_id:
        raise ValueError(f"{label} field adapter_id must be non-empty text")

    if "model" in member:
        backend_model = member["model"]
        if not isinstance(backend_model, str) or not backend_model:
            raise ValueError(f"{label} field model must be non-empty text when supplied")
        if backend_model != model_id:
            raise ValueError(
                f"{label} field model must equal model_id in the three-minds demo so "
                "the declared identity matches the effective backend model"
            )

    vote_weight = member.get("vote_weight", 1)
    if type(vote_weight) is not int or vote_weight != 1:
        raise ValueError(f"{label} field vote_weight must be the exact integer 1")
    if member.get("epistemic_privilege", "none") != "none":
        raise ValueError(f"{label} field epistemic_privilege must be 'none'")

    return {
        "member_id": member_id,
        "model_id": model_id,
        "adapter_id": adapter_id,
    }


def validate_members(members: Iterable[dict[str, Any]]) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, str], ...]]:
    """Require exactly three distinct declared/effective participant identities."""

    normalized = tuple(members)
    if len(normalized) != 3:
        raise ValueError(
            f"three-minds demo requires exactly three minds; got {len(normalized)}"
        )

    public = tuple(public_member(member, index=index) for index, member in enumerate(normalized))

    member_seen: dict[str, int] = {}
    identity_seen: dict[tuple[str, str], int] = {}
    for index, member in enumerate(public):
        member_id = member["member_id"]
        previous_index = member_seen.get(member_id)
        if previous_index is not None:
            raise ValueError(
                f"mind {index + 1} (member_id={member_id!r}) duplicates member_id from "
                f"mind {previous_index + 1}"
            )
        member_seen[member_id] = index

        identity = (member["adapter_id"], member["model_id"])
        previous_index = identity_seen.get(identity)
        if previous_index is not None:
            raise ValueError(
                f"mind {index + 1} (member_id={member_id!r}) duplicates effective "
                f"adapter/model identity {identity!r} from mind {previous_index + 1}"
            )
        identity_seen[identity] = index

    return normalized, public


def validate_question(question: str | None) -> str:
    if question is None:
        question = (
            "Evaluate the benchmark hypothesis that every supplied integer is prime. "
            "Propose, reproduce, critique, and attempt to falsify the claim without "
            "treating model agreement as evidence."
        )
    if not isinstance(question, str) or not question.strip():
        raise ValueError("question must be non-empty text")
    if len(question) > MAX_TASK_QUESTION_CHARS:
        raise ValueError(
            f"question must be at most {MAX_TASK_QUESTION_CHARS} characters so the complete "
            "task remains visible inside the bounded model evidence view"
        )
    return question


def validate_mode_catalog(mode: str, modes: Any) -> None:
    """Distinguish an unknown mode from a violated world.modes API contract."""

    if not isinstance(mode, str) or not mode:
        raise ValueError("mode must be non-empty text")
    if not isinstance(modes, list):
        raise ValueError(
            "world.modes returned unexpected modes structure: "
            f"expected list, got {type(modes).__name__!r}"
        )

    mode_ids: set[str] = set()
    for index, item in enumerate(modes):
        if not isinstance(item, dict):
            raise ValueError(
                "world.modes returned unexpected item structure at index "
                f"{index}: expected object, got {type(item).__name__!r}"
            )
        mode_id = item.get("mode_id")
        if not isinstance(mode_id, str) or not mode_id:
            raise ValueError(
                f"world.modes returned item {index} without a non-empty mode_id"
            )
        mode_ids.add(mode_id)

    if mode not in mode_ids:
        raise ValueError(f"unknown world mode: {mode}")


__all__ = [
    "MAX_TASK_QUESTION_CHARS",
    "public_member",
    "validate_members",
    "validate_mode_catalog",
    "validate_question",
]
