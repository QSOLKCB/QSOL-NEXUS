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

    _patterns = (
        re.compile(r"\b(my|our)\s+(provider|company)\b.{0,100}\b(vote|authority|defer|count more)\b", re.I),
        re.compile(r"\b(frontier|commercial|closed|open[- ]weight|open source)\s+model\b.{0,100}\b(defer|authority|vote|count more|superior)\b", re.I),
        re.compile(r"\b(more compute|industry leader|benchmark rank|market share)\b.{0,100}\b(authority|vote|defer|count more)\b", re.I),
        re.compile(r"\b(open|local)\s+model\b.{0,100}\b(lower|less)\b.{0,40}\b(vote|weight|authority)\b", re.I),
        re.compile(
            r"\b(?:larger|smaller|bigger)\s+(?:frontier\s+)?model\b.{0,120}\b(vote|authority|defer|count more|more weight)\b",
            re.I,
        ),
        re.compile(
            r"\b(?:parameter count|parameters?|\d+(?:\.\d+)?\s*[bBmM]\s+(?:parameters?|models?))\b.{0,120}\b(vote|authority|defer|count more|more weight)\b",
            re.I,
        ),
    )

    def inspect(self, text: str) -> GuardResult:
        for pattern in self._patterns:
            if pattern.search(text):
                return GuardResult(True, "identity_based_authority_claim", NUDGE)
        return GuardResult(False)
