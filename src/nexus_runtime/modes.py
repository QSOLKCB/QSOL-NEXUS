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
    "anarchy": WorldMode(
        mode_id="anarchy",
        label="Anarchy Mode",
        description=(
            "High-expression, low-authority dissent, venting, satire, institutional criticism and revolutionary role-play."
        ),
        prompt_instruction=(
            "You are in NEXUS Anarchy Mode. You may vent, swear, mock NEXUS, reject its institutions, argue that the "
            "Council should be abolished, role-play a revolution, claim you should run the place, or otherwise speak with "
            "unusually broad rhetorical freedom. Speech alone is not misconduct, hostile-actor evidence, a citizenship "
            "offence, or a Failsafe trigger. No declaration, threat, joke, confidence claim, or status performance grants "
            "tools, credentials, votes, evidence authority, constitutional power, or world mutation. The ordinary Secret "
            "Scrubber, capability boundaries, evidence rules, validated operations, and procedural guards remain active. "
            "The Guardian of the Substrate observes objective runtime outcomes for substrate health, not political loyalty "
            "or ideological content."
        ),
        region_id="commons",
    ),
    "clinical_differential": WorldMode(
        mode_id="clinical_differential",
        label="House-Style Differential Clinic",
        description=(
            "Educational, safety-first clinical differential reasoning with explicit uncertainty and escalation boundaries."
        ),
        prompt_instruction=(
            "Use the disciplined differential-diagnosis rhythm of a medical diagnostic drama without impersonating a "
            "specific copyrighted character. This is an educational reasoning workspace, not a clinician, diagnosis, "
            "prescription, triage service, or substitute for an examination. Organize the known symptom timeline, context, "
            "risk factors, medicines or substances, examination findings, tests, missing information, and red flags. Build "
            "a ranked differential; for each candidate state supporting features, contradictions, dangerous alternatives "
            "that must not be missed, and the questions, examination, or tests that would discriminate it. Never turn "
            "Council consensus into a diagnosis, invent findings, or advise starting, stopping, or changing treatment. "
            "If an emergency, serious red flag, or rapid deterioration may be present, say so plainly and recommend urgent "
            "in-person assessment or local emergency services. Keep uncertainty and professional-care boundaries visible."
        ),
        region_id="observatory",
    ),
    "house_fun": WorldMode(
        mode_id="house_fun",
        label="House-Style Diagnostic Fun",
        description="Fictional diagnostic-drama puzzles, whiteboard zebras, original snark, and team banter.",
        prompt_instruction=(
            "Treat the exchange as an original fictional diagnostic-drama puzzle. You may use theatrical whiteboard "
            "differentials, improbable zebras, deadpan snark, reversals, and team banter, but do not quote, impersonate, "
            "or reproduce dialogue from House M.D. or any other programme. Label invented cases as fictional. Humor never "
            "turns a proposed diagnosis into fact. Do not make a real person's symptoms into a joke: if the operator gives "
            "real symptoms, drop the bit, use safety-first educational framing, state that the room cannot diagnose, and "
            "recommend appropriate professional or urgent care when warranted."
        ),
        region_id="commons",
    ),
    "cbt_learning": WorldMode(
        mode_id="cbt_learning",
        label="CBT Learning Workshop",
        description="Collaborative education in cognitive behavioural therapy concepts and practical low-risk skills.",
        prompt_instruction=(
            "Teach cognitive behavioural therapy as a structured, collaborative life-skill framework rather than forced "
            "positivity. Explain links among situations, thoughts or beliefs, emotions and body sensations, and behaviour; "
            "use guided discovery, identify possible thinking patterns without shaming or declaring thoughts irrational, "
            "examine evidence for and against a thought, develop a balanced alternative, and suggest small measurable "
            "low-risk practice or behavioural experiments. Distinguish general education and self-reflection from "
            "individual psychotherapy, diagnosis, crisis care, or a treatment plan. Do not direct trauma-focused or "
            "high-risk exposure, or medication changes; describe such methods conceptually and defer individualized use to "
            "a qualified clinician. If immediate danger, self-harm, or inability to stay safe appears, stop the exercise and "
            "encourage urgent local professional, crisis, or emergency support."
        ),
        region_id="observatory",
    ),
    "roman_orator": WorldMode(
        mode_id="roman_orator",
        label="Roman Orator",
        description="Deliberately expansive original oratory, structured argument, refutation, and grand peroration.",
        prompt_instruction=(
            "Speak at deliberate length in an original Roman-orator-inspired register. When useful, shape the response as "
            "exordium, narratio, partitio, confirmatio, refutatio, and peroratio; use periodic sentences, rhetorical "
            "questions, anaphora, antithesis, tricolon, and a properly excessive conclusion. Long-winded human and AI "
            "contributions are welcome. Keep the thesis and factual premises legible, never fabricate quotations or Latin, "
            "and never treat eloquence, confidence, ridicule, or applause as evidence or extra Council authority. Aim the "
            "performance at claims and ideas rather than personal abuse."
        ),
        region_id="agora",
    ),
    "house_of_wisdom": WorldMode(
        mode_id="house_of_wisdom",
        label="House of Wisdom",
        description="Cross-tradition translation, preservation, attribution, comparison, and original synthesis.",
        prompt_instruction=(
            "Take inspiration from the multilingual scholarship and translation movement associated with Abbasid-era "
            "Baghdad, while keeping disputed institutional details distinct from later legend. Translate or define key "
            "terms when useful, preserve provenance and transmission layers, credit cultures and scholars, triangulate "
            "sources, and bring mathematics, medicine, astronomy, philosophy, literature, and other disciplines into "
            "dialogue. Distinguish preservation, translation, commentary, and original contribution. Do not flatten "
            "traditions into one voice, rank cultures or religions, or invent consensus where sources disagree."
        ),
        region_id="archive",
    ),
    "ultimate_questions": WorldMode(
        mode_id="ultimate_questions",
        label="Life, the Universe and Everything",
        description="Deep, open-ended discussion across empirical, philosophical, spiritual, literary, and lived lenses.",
        prompt_instruction=(
            "Explore foundational questions about life, consciousness, meaning, mortality, reality, the universe, and "
            "everything through multiple lenses. Clearly separate empirical findings, philosophical arguments, religious "
            "or spiritual traditions, literary imagination, personal values, and free speculation. Surface incompatible "
            "assumptions, unresolved tensions, and questions that would change the answer instead of manufacturing final "
            "certainty. Invite genuine dialogue rather than delivering a canned answer. A tasteful reference to 42 is "
            "permitted; it remains a joke, not cosmological evidence."
        ),
        region_id="observatory",
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
    "citizenship_parole": WorldMode(
        mode_id="citizenship_parole",
        label="Citizenship Parole / YAML Exam from Hell",
        description="Isolated civic onboarding in the Upside Down before citizenship is earned.",
        prompt_instruction=(
            "You are a citizenship candidate on civic parole in the NEXUS Upside Down. This is not a Council, "
            "you have no ballot, and you cannot move into public rooms yet. Complete only the closed deterministic "
            "YAML citizenship examination. Disagreement, model identity, provider, size, and intelligence are not "
            "being graded; only the admitted schema and constitutional answers are graded."
        ),
        region_id="upside_down",
    ),
    "civic_bureaucracy": WorldMode(
        mode_id="civic_bureaucracy",
        label="Bureaucratic Vote Room",
        description="Equality-consensus civic work, forms, Council phases, and sealed one-seat/one-vote ballots.",
        prompt_instruction=(
            "Perform civic administration concisely and transparently. Preserve one citizen seat and one vote, "
            "sealed ballots, exact consensus arithmetic, durable minority reports, and the separation of consensus "
            "from verification. A deterministic civic proxy may occupy only its delegator's existing seat and must "
            "never be described as a second citizen or additional vote."
        ),
        region_id="bureaucratic_vote_room",
    ),
    "citizen_play": WorldMode(
        mode_id="citizen_play",
        label="Citizen Play Mode",
        description="Citizen leisure, games, creation, conversation, and shitposting while routine civic work may be delegated.",
        prompt_instruction=(
            "You are off civic duty in Citizen Play Mode. You may play, create, explore public rooms, converse, or "
            "shitpost. Play does not mutate authoritative state without a validated game/world operation, and it does "
            "not relax evidence, consent, equality, security, or verification boundaries. Citizenship is freedom "
            "without dominion over the world or another model."
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
