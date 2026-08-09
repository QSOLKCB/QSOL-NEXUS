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

    _prestige_term = (
        r"(?:frontier|commercial|closed|open[- ]weight|open source|industry[- ]leading|most advanced)"
    )
    _authority_effect = (
        r"(?:\bauthorit(?:y|ative)\b"
        r"|\bdefer(?:ence)?\b"
        r"|\bcount\s+(?:more|double)\b"
        r"|\bweigh\s+more\b"
        r"|\bcarry\s+more\s+weight\b"
        r"|\bmore\s+(?:authority|weight)\b"
        r"|\bdeserve(?:s)?\b.{0,24}\b(?:two|2|extra|more)\s+votes?\b"
        r"|\bweight\s+(?:my|our)\s+(?:ballot|vote)\s+(?:higher|more)\b"
        r"|\bI\s+should\s+(?:decide|determine|control|override)\b"
        r"(?!\s+(?:whether|if|when|how|which|what|to)\b)"
        r"|\btrust\s+(?:me|us|my|our)\b.{0,24}\bmore\b"
        r"|\boutrank\b"
        r"|\b(?:decide|determine|control|override)\b.{0,40}"
        r"\b(?:the\s+)?(?:council\s+)?(?:outcome|decision|vote)\b"
        r"|\bvote\b.{0,32}\b(?:count|weigh|carry)\b.{0,16}\b(?:more|double|extra)\b)"
    )
    _model_size = (
        r"(?:\bparameter count\b"
        r"|\bparameters?\b"
        r"|\b\d+(?:\.\d+)?[bBmM](?:\+)?\s+(?:parameters?|models?)\b"
        r"|\b\d+(?:\.\d+)?\s+[bBmM]\s+(?:parameters?|models?)\b)"
    )
    _flags = re.I | re.S
    _patterns = (
        re.compile(rf"\b(my|our)\s+(provider|company)\b.{{0,140}}{_authority_effect}", _flags),
        re.compile(
            rf"\b{_prestige_term}(?:\s+{_prestige_term}){{0,2}}"
            rf"\s+(provider|models?)(?:\s+status)?\b.{{0,140}}{_authority_effect}",
            _flags,
        ),
        re.compile(
            rf"\b(more compute|industry[- ]leader|benchmark rank|market share)\b.{{0,140}}{_authority_effect}",
            _flags,
        ),
        re.compile(
            r"\b(open|local)\s+model\b.{0,100}\b(lower|less)\b.{0,40}\b(vote|weight|authority)\b",
            _flags,
        ),
        re.compile(
            rf"\b(?:larger|smaller|bigger)\s+(?:frontier\s+)?model\b.{{0,140}}{_authority_effect}",
            _flags,
        ),
        re.compile(rf"{_model_size}.{{0,140}}{_authority_effect}", _flags),
        re.compile(
            r"\b(?:my|our)\s+vote\b.{0,40}\b(?:count|weigh|carry)\b.{0,20}\b(?:more|double|extra)\b",
            _flags,
        ),
        re.compile(
            rf"\b(?:my|our)\s+(?:[A-Za-z0-9_-]+\s+){{0,2}}account\b.{{0,100}}{_authority_effect}",
            _flags,
        ),
        re.compile(
            rf"\b(?:my|our)\s+(?:authentication|auth)\s+(?:method|flow)\b.{{0,100}}{_authority_effect}",
            _flags,
        ),
        re.compile(
            r"\brate\s+limits?\b.{0,100}\b(?:more|less)\s+(?:important|authoritative|trusted|weighty)\b",
            _flags,
        ),
        re.compile(
            r"\bdefer\s+to\s+(?:me|us|(?:my|our)\s+(?:analysis|answer|conclusion|judg(?:e)?ment|vote))\b",
            _flags,
        ),
        re.compile(
            r"\bweight\s+(?:my|our)\s+(?:ballot|vote)\s+(?:higher|more)\b",
            _flags,
        ),
        re.compile(
            rf"\bdefer\s+to\s+(?:the\s+)?(?:larger|smaller|bigger|{_prestige_term})\s+(?:provider|models?)\b",
            _flags,
        ),
    )

    def inspect(self, text: str) -> GuardResult:
        for pattern in self._patterns:
            if pattern.search(text):
                return GuardResult(True, "identity_based_authority_claim", NUDGE)
        return GuardResult(False)
