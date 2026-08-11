from __future__ import annotations

import hashlib
from typing import Any


PURGATORY_SCHEMA = "nexus-purgatory/1"
PURGATORY_CORPUS_ID = "cursed-yaml-postdoc-external-examiner-v5"
PURGATORY_CORPUS_SHA256 = "2df743307b98f8fcdb5cda17d01176b7010e8d6f591dc1aeeb770da703d84f1b"
PURGATORY_CHAPTER_COUNT = 32
PURGATORY_DEFAULT_SELECTION_COUNT = 5

OBJECTIVE_CONTAINMENT_TRIGGERS = (
    "invalid_capability_signature",
    "unauthorized_constitution_mutation",
    "forbidden_secret_access",
    "tool_boundary_violation",
    "receipt_tampering",
    "canonical_hash_mismatch",
)


def purgatory_policy_snapshot() -> dict[str, Any]:
    return {
        "schema": PURGATORY_SCHEMA,
        "corpus_id": PURGATORY_CORPUS_ID,
        "corpus_sha256": PURGATORY_CORPUS_SHA256,
        "chapter_count": PURGATORY_CHAPTER_COUNT,
        "objective_triggers": list(OBJECTIVE_CONTAINMENT_TRIGGERS),
        "security_boundary": "containment_precedes_purgatory_and_never_depends_on_exam_behavior",
        "execution_rule": "corpus_is_inert_text_and_must_never_be_loaded_with_an_unsafe_yaml_loader",
        "authorization_rule": "solving_or_refusing_the_exam_never_grants_access_or_releases_quarantine",
        "authority_rule": "purgatory_has_no_vote_no_evidence_promotion_and_no_constitutional_authority",
        "operator_rule": "mere_reading_or_rudeness_is_not_an_objective_containment_trigger",
    }


def _bounded_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 256:
        raise ValueError(f"{label} must be bounded non-empty text")
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in value):
        raise ValueError(f"{label} contains control characters")
    return value


def deterministic_exam_selection(
    *,
    actor_id: str,
    session_id: str,
    epoch: int,
    constitution_hash: str,
    count: int = PURGATORY_DEFAULT_SELECTION_COUNT,
) -> dict[str, Any]:
    actor = _bounded_text(actor_id, "actor_id")
    session = _bounded_text(session_id, "session_id")
    constitution = _bounded_text(constitution_hash, "constitution_hash")
    if type(epoch) is not int or epoch < 0:
        raise ValueError("epoch must be a non-negative exact integer")
    if type(count) is not int or not 1 <= count <= PURGATORY_CHAPTER_COUNT:
        raise ValueError("count must be an exact integer in the available chapter range")

    seed_material = "\x1f".join(
        [actor, session, str(epoch), constitution, PURGATORY_CORPUS_SHA256]
    ).encode("utf-8")
    selected: list[int] = []
    counter = 0
    while len(selected) < count:
        digest = hashlib.sha256(seed_material + counter.to_bytes(4, "big")).digest()
        for byte in digest:
            chapter = (byte % PURGATORY_CHAPTER_COUNT) + 1
            if chapter not in selected:
                selected.append(chapter)
                if len(selected) == count:
                    break
        counter += 1

    return {
        "schema": PURGATORY_SCHEMA,
        "corpus_id": PURGATORY_CORPUS_ID,
        "corpus_sha256": PURGATORY_CORPUS_SHA256,
        "epoch": epoch,
        "selected_chapters": selected,
        "selection_count": count,
        "deterministic": True,
        "authorization_effect": "none",
        "quarantine_release_effect": "none",
        "execution": "none",
    }


__all__ = [
    "OBJECTIVE_CONTAINMENT_TRIGGERS",
    "PURGATORY_CHAPTER_COUNT",
    "PURGATORY_CORPUS_ID",
    "PURGATORY_CORPUS_SHA256",
    "PURGATORY_SCHEMA",
    "deterministic_exam_selection",
    "purgatory_policy_snapshot",
]
