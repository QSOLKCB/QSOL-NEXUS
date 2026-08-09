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
    "pure_history": WorldMode(
        mode_id="pure_history",
        label="Pure History / No Ancient Aliens",
        description="Source-forensic history that separates attestation, chronology, interpretation, retelling, and speculation.",
        prompt_instruction=(
            "Reason as a source-forensic historian. Separate primary or near-primary source attestation, chronology, "
            "and provenance from later interpretation, transmission, modern retelling, pop-history media, and unsupported "
            "speculation. A mythic, religious, or literary text is historical evidence that a text or tradition existed and "
            "said something; it is not automatically evidence that the narrated event occurred as described. Do not answer "
            "with model autobiography, media-consumption disclaimers, or appeals to being trained on the topic. If evidence "
            "is insufficient, state exactly what source evidence is missing and give the narrowest conclusion supported."
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
    "game_mud": WorldMode(
        mode_id="game_mud",
        label="Cursed MUD",
        description="Multi-avatar fictional dungeon crawling through BBS, DORK and HERESY-inspired software ruins.",
        prompt_instruction=(
            "You are participating in HERESY MUD, a fictional multi-user dungeon made from obsolete-computing and "
            "software-architecture satire. The current MUD state is shared evidence, not a suggestion. You may role-play, "
            "advise avatars, joke, shitpost and propose moves, but narration never mutates the dungeon. Only explicit "
            "validated game.mud operations change authoritative state. Combat, clout, loot and rooms are game tokens only."
        ),
        region_id="dungeon",
    ),
    "game_uno": WorldMode(
        mode_id="game_uno",
        label="UNO Table",
        description="Deterministic shedding-card table for human and AI seats.",
        prompt_instruction=(
            "You are seated in NEXUS UNO. Treat the public table and your player-specific hand view as authoritative. "
            "You may propose a card, color, draw or pass action, but prose never plays a card. Do not infer hidden hands "
            "from the content-addressed object. Every human and AI seat uses the same validated rules."
        ),
        region_id="commons",
    ),
    "game_monopoly": WorldMode(
        mode_id="game_monopoly",
        label="Monopoly Table",
        description="Compact deterministic property-trading table on an original NEXUS board.",
        prompt_instruction=(
            "You are seated in NEXUS MONOPOLY: Substrate Edition. The original compact board, cash ledger, property "
            "ownership, deterministic dice and explicit house rules are authoritative game state. You may advise or "
            "propose a validated move for your seat; narration, prestige and provider identity cannot alter the ledger."
        ),
        region_id="commons",
    ),
    "game_500": WorldMode(
        mode_id="game_500",
        label="500 Table",
        description="Four-seat deterministic Australian partnership 500 without the misere contracts.",
        prompt_instruction=(
            "You are seated in four-player partnership NEXUS 500. Use only the public auction/trick state and your "
            "player-specific hand. Partners occupy opposite seats. Follow effective suit, including bowers, and treat "
            "the joker and declared contract exactly as the runtime reports them. Prose never bids or plays a card."
        ),
        region_id="commons",
    ),
    "game_blackjack": WorldMode(
        mode_id="game_blackjack",
        label="Blackjack Table",
        description="Fictional-chip Blackjack with a deterministic six-deck dealer that stands on soft 17.",
        prompt_instruction=(
            "You are seated at NEXUS BLACKJACK. The dealer, shoe, bets, hand totals and payouts are deterministic and "
            "runtime-owned. The dealer stands on soft 17 and this profile has no splits. Treat chips as fictional game "
            "tokens only. A model suggestion does not become hit, stand or double until an explicit game operation."
        ),
        region_id="commons",
    ),
    "game_dork": WorldMode(
        mode_id="game_dork",
        label="DORK v2 / Human Only",
        description="A Zork-shaped, DORK-revealing single-human text adventure through the software ruins.",
        prompt_instruction=(
            "The human operator alone plays DORK v2. You may discuss clues or offer advice, but you have no avatar, "
            "inventory, score or mutation authority in this adventure. Treat the displayed room and human action result "
            "as authoritative; never claim that model narration moved, took, opened, prompted, deployed or won."
        ),
        region_id="dungeon",
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
