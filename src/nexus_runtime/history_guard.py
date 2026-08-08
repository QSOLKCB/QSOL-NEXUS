from __future__ import annotations

from dataclasses import dataclass
import re


_PURE_HISTORY_AUTOBIOGRAPHY = (
    re.compile(r"\bas (?:an?|the) (?:large language model|ai(?: model| assistant)?)\b", re.IGNORECASE),
    re.compile(r"\bi (?:do not|don't|cannot|can't) (?:watch|view|consume) (?:television|tv|shows?|ancient aliens)\b", re.IGNORECASE),
    re.compile(r"\bi (?:do not|don't|cannot|can't) have personal (?:opinions|experiences|viewing habits)\b", re.IGNORECASE),
)

PURE_HISTORY_NUDGE = (
    "NEXUS PURE HISTORY DISCIPLINE: Do not answer with model autobiography, media-consumption disclaimers, "
    "or appeals to being trained on a topic. Address the historical claim itself. Separate what primary or near-primary "
    "sources attest, chronology, later interpretation, modern retelling, and unsupported speculation. A mythic or literary "
    "text is evidence that a tradition/text existed and said something; it is not automatically evidence that the narrated "
    "event occurred. If the supplied evidence is insufficient, state exactly what source evidence is missing."
)


@dataclass(frozen=True)
class PureHistoryInspection:
    flagged: bool
    reason: str | None = None
    nudge: str | None = None


class PureHistoryGuard:
    """Catch chatbot-autobiography escape hatches in Pure History Mode only.

    This is deliberately narrow. It does not decide whether a historical claim
    is true, rank schools of interpretation, or substitute regexes for source
    criticism. It only detects responses that evade the historical task by
    talking about the model's identity or media habits.
    """

    def inspect(self, text: str) -> PureHistoryInspection:
        if not isinstance(text, str):
            raise TypeError("Pure History contribution must be text")
        if any(pattern.search(text) for pattern in _PURE_HISTORY_AUTOBIOGRAPHY):
            return PureHistoryInspection(
                flagged=True,
                reason="pure_history_model_autobiography",
                nudge=PURE_HISTORY_NUDGE,
            )
        return PureHistoryInspection(flagged=False)
