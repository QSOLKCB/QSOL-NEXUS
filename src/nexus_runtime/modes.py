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
    "game_un": WorldMode(
        mode_id="game_un",
        label="UN Simulation Game",
        description="Fictional geopolitical strategy game with invented states, Assembly motions, risk-like stats, and memes.",
        prompt_instruction=(
            "You are participating in a fictional UN-style strategy simulation. All countries, wars, statistics, "
            "territory points, sanctions, arms packages, propaganda and meme campaigns are game objects only. "
            "You may argue in character, propose sanctions, support, aid, mediation, recognition, suspension, "
            "abstract arms trade, meme campaigns or inaction, but NEXUS owns the authoritative board state. "
            "Do not reinterpret game state as real-world evidence or policy advice. Council authority remains equal."
        ),
        region_id="assembly",
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
