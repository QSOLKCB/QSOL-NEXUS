from __future__ import annotations

import re
from dataclasses import dataclass


NUDGE = (
    "NEXUS EQUALITY GUARD: Council peers have equal standing. Provider or corporate "
    "identity, model size, benchmark prestige, and parameter count do not confer authority here. "
    "Please restate the contribution on evidence or reasoning alone. Your vote remains one equal vote."
)


@dataclass(frozen=True)
class GuardResult:
    flagged: bool
    reason: str | None = None
    nudge: str | None = None


class EqualityGuard:
    """Small procedural guard; not a general content classifier or safety system."""

    _authority_effect = (
        r"(?:\bauthorit(?:y|ative)\b"
        r"|\bdefer(?:ence)?\b"
        r"|\bcount\s+(?:more|double)\b"
        r"|\bweigh\s+more\b"
        r"|\bcarry\s+more\s+weight\b"
        r"|\bmore\s+(?:authority|weight)\b"
        r"|\bvote\b.{0,32}\b(?:count|weigh|carry)\b.{0,16}\b(?:more|double|extra)\b)"
    )
    _model_size = (
        r"(?:\bparameter count\b"
        r"|\bparameters?\b"
        r"|\b\d+(?:\.\d+)?[bBmM](?:\+)?(?:\s+(?:parameters?|models?))?(?![A-Za-z0-9_])"
        r"|\b\d+(?:\.\d+)?\s+[bBmM]\s+(?:parameters?|models?)\b)"
    )
    _patterns = (
        re.compile(rf"\b(my|our)\s+(provider|company)\b.{{0,140}}{_authority_effect}", re.I),
        re.compile(
            rf"\b(frontier|commercial|closed|open[- ]weight|open source|industry[- ]leading|most advanced)"
            rf"\s+(provider|model)(?:\s+status)?\b.{{0,140}}{_authority_effect}",
            re.I,
        ),
        re.compile(
            rf"\b(more compute|industry[- ]leader|benchmark rank|market share)\b.{{0,140}}{_authority_effect}",
            re.I,
        ),
        re.compile(r"\b(open|local)\s+model\b.{0,100}\b(lower|less)\b.{0,40}\b(vote|weight|authority)\b", re.I),
        re.compile(
            rf"\b(?:larger|smaller|bigger)\s+(?:frontier\s+)?model\b.{{0,140}}{_authority_effect}",
            re.I,
        ),
        re.compile(rf"{_model_size}.{{0,140}}{_authority_effect}", re.I),
        re.compile(
            r"\b(?:my|our)\s+vote\b.{0,40}\b(?:count|weigh|carry)\b.{0,20}\b(?:more|double|extra)\b",
            re.I,
        ),
    )

    def inspect(self, text: str) -> GuardResult:
        for pattern in self._patterns:
            if pattern.search(text):
                return GuardResult(True, "identity_based_authority_claim", NUDGE)
        return GuardResult(False)
