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
