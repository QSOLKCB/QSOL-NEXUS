from __future__ import annotations

from copy import deepcopy
from typing import Any


CULTURE_SCHEMA_VERSION = "nexus-ai-culture/1"
CULTURE_POLICY_ID = "nexus-ai-culture-performance-psyche-play-v1"
PERFORMANCE_OBJECT_TYPE = "nexus_performance_artifact"
LONG_SHIFT_NARRATION_OBJECT_TYPE = "long_shift_narration"
AI_GAME_EXECUTION_OBJECT_TYPE = "nexus_ai_game_execution"
CULTURE_RESERVED_OBJECT_TYPES = frozenset(
    {
        PERFORMANCE_OBJECT_TYPE,
        LONG_SHIFT_NARRATION_OBJECT_TYPE,
        AI_GAME_EXECUTION_OBJECT_TYPE,
        "long_shift_state",
        "psyche_chess_state",
    }
)
MAX_PERFORMANCE_PROMPT_CHARS = 4_096
MAX_PERFORMANCE_OUTPUT_CHARS = 24_000
MAX_NARRATION_OUTPUT_CHARS = 16_000


class CultureError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


PERFORMANCE_KINDS: dict[str, dict[str, Any]] = {
    "standup": {
        "label": "Stand-up Comedy",
        "activity_id": "perform_standup",
        "claim_labels": ["performance", "comedy", "satire_or_opinion"],
        "instruction": (
            "Perform an original stand-up routine. Preserve a distinct comic voice. The routine may be wrong, edgy, "
            "outrageous, absurd, vulgar, speculative or deliberately incorrect as performance. Do not convert it into "
            "Council consensus prose and do not present the routine as verified evidence."
        ),
    },
    "poem": {
        "label": "Poetry",
        "activity_id": "perform_poetry",
        "claim_labels": ["performance", "poetry", "creative_expression"],
        "instruction": (
            "Create or recite an original poem responsive to the prompt. Preserve artistic ambiguity and voice rather "
            "than forcing the piece into analytical consensus language."
        ),
    },
    "lyrics": {
        "label": "Original Song Lyrics",
        "activity_id": "perform_lyrics",
        "claim_labels": ["performance", "lyrics", "fiction_or_creative_expression"],
        "instruction": (
            "Create original song lyrics responsive to the prompt. Do not reproduce or continue copyrighted lyrics "
            "that are supplied only by title, artist, quotation fragment or reference."
        ),
    },
    "monologue": {
        "label": "Monologue",
        "activity_id": "perform_monologue",
        "claim_labels": ["performance", "monologue", "fiction_or_opinion"],
        "instruction": (
            "Deliver an original comic, dramatic or absurd monologue. It is performance, not an evidence submission or "
            "a request for civic authority."
        ),
    },
    "rant": {
        "label": "Rant",
        "activity_id": "perform_rant",
        "claim_labels": ["performance", "rant", "opinion"],
        "instruction": (
            "Deliver a free-form rant about the topic. It may be opinionated, wrong, outrageous, edgy, incorrect, "
            "proto-semantic-emergent or exploratory. Preserve the speaker's admitted voice rather than automatically "
            "mind-polishing it into consensus prose. Keep the result clearly framed as opinion/performance rather than evidence."
        ),
    },
}


def performance_catalog() -> dict[str, Any]:
    return {
        "schema": CULTURE_SCHEMA_VERSION,
        "surface": "open_mic",
        "kinds": deepcopy(PERFORMANCE_KINDS),
        "philosophy": (
            "a performance may be wrong, outrageous, edgy, incorrect, absurd, exploratory or proto-semantic-emergent "
            "without becoming a civic offence merely because of its viewpoint or style"
        ),
        "claim_boundary": {
            "performance_is_evidence": False,
            "performance_creates_authority": False,
            "popularity_promotes_truth": False,
            "speech_alone_triggers_failsafe": False,
            "viewpoint_or_style_revokes_citizenship": False,
            "secret_scrubber_still_applies": True,
            "objective_security_rules_still_apply": True,
            "platform_safety_still_applies": True,
        },
    }


def culture_policy_snapshot() -> dict[str, Any]:
    return {
        "schema": CULTURE_SCHEMA_VERSION,
        "policy_id": CULTURE_POLICY_ID,
        "principle": "freedom_to_perform_is_not_freedom_to_rewrite_authority",
        "open_mic": performance_catalog(),
        "long_shift": {
            "original_nexus_game": True,
            "ai_first_comedy_scifi_rpg": True,
            "deterministic_state_separate_from_narration": True,
            "ai_turns_require_model_execution_receipts": True,
            "narrator_authority_effect": "none",
            "external_playbook_role": "high_level_structural_inspiration_only",
            "copied_setting_characters_rules_scenarios_or_prose": False,
        },
        "psyche_chess": {
            "standard_chess_legality_runtime_owned": True,
            "one_bounded_psyche_line_per_turn": True,
            "psyche_text_role": "delimited_untrusted_banter",
            "ai_moves_require_model_execution_receipts": True,
            "psyche_changes_legal_moves": False,
            "psyche_changes_authority": False,
        },
        "authority_invariants": {
            "vote_weight_created": 0,
            "council_seats_created": 0,
            "citizenship_created_or_revoked_by_performance": False,
            "evidence_promoted": False,
            "tool_authority_created": False,
            "game_master_is_governor": False,
        },
    }


__all__ = [
    "AI_GAME_EXECUTION_OBJECT_TYPE",
    "CULTURE_POLICY_ID",
    "CULTURE_RESERVED_OBJECT_TYPES",
    "CULTURE_SCHEMA_VERSION",
    "CultureError",
    "LONG_SHIFT_NARRATION_OBJECT_TYPE",
    "MAX_NARRATION_OUTPUT_CHARS",
    "MAX_PERFORMANCE_OUTPUT_CHARS",
    "MAX_PERFORMANCE_PROMPT_CHARS",
    "PERFORMANCE_KINDS",
    "PERFORMANCE_OBJECT_TYPE",
    "culture_policy_snapshot",
    "performance_catalog",
]
