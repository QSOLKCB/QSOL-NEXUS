from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class WorldMode:
    """Operator-selected cognitive framing for a NEXUS world session.

    A mode may change framing, tone, and which contextual distinctions actors
    are asked to preserve. It never changes evidence status, Council vote
    weight, verification rules, secret handling, or procedural authority.
    """

    mode_id: str
    label: str
    description: str
    prompt_instruction: str
    region_id: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


_MODES = {
    "analytical": WorldMode(
        mode_id="analytical",
        label="Analytical",
        description="Evidence-first technical reasoning with explicit claim boundaries.",
        prompt_instruction=(
            "Use precise analytical reasoning. Separate observations, interpretations, assumptions, "
            "and unknowns. Prefer the narrowest conclusion supported by the current evidence."
        ),
        region_id="observatory",
    ),
    "historical": WorldMode(
        mode_id="historical",
        label="Historical",
        description="Chronology, source context, change over time, and competing historical interpretations.",
        prompt_instruction=(
            "Reason historically. Preserve chronology, distinguish primary facts from later interpretation, "
            "identify uncertainty or missing sources, and avoid treating present-day categories as timeless."
        ),
        region_id="archive",
    ),
    "cultural": WorldMode(
        mode_id="cultural",
        label="Cultural",
        description="Context-sensitive cultural comparison, ambiguity, norms, insider/outsider framing, and meaning.",
        prompt_instruction=(
            "Reason with cultural context. Distinguish local norms from universal claims, preserve ambiguity where "
            "it matters, and notice how the same expression can bond insiders while excluding outsiders."
        ),
        region_id="agora",
    ),
    "meme_casual": WorldMode(
        mode_id="meme_casual",
        label="Meme / Casual",
        description="Playful, irreverent and meme-friendly interaction without relaxing evidence boundaries.",
        prompt_instruction=(
            "You may be playful, colloquial, irreverent, or meme-aware. Humor can puncture pretension and build "
            "rapport, but a joke is not evidence and playful status games never create Council authority."
        ),
        region_id="commons",
    ),
}


def get_mode(mode_id: str) -> WorldMode:
    if not isinstance(mode_id, str) or not mode_id:
        raise ValueError("mode_id must be a non-empty string")
    try:
        return _MODES[mode_id]
    except KeyError as exc:
        raise ValueError(f"unknown world mode: {mode_id}") from exc


def list_modes() -> tuple[WorldMode, ...]:
    return tuple(_MODES[key] for key in sorted(_MODES))
