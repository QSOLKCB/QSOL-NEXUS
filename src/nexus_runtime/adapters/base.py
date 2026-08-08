from __future__ import annotations

import json
from typing import Any, Protocol

from ..types import Ballot, CouncilMember, PhaseContext


ALLOWED_BALLOTS = tuple(choice.value for choice in Ballot)
BALLOT_SCHEMA = {
    "type": "object",
    "properties": {
        "choice": {"type": "string", "enum": list(ALLOWED_BALLOTS)},
        "rationale": {"type": "string"},
    },
    "required": ["choice", "rationale"],
    "additionalProperties": False,
}


class AdapterError(ValueError):
    """A sanitized provider transport failure safe for the public API boundary."""


class AdapterAuthenticationError(AdapterError):
    """The provider rejected or cannot use the configured credential."""


class AdapterProtocolError(AdapterError):
    """The provider returned data outside the admitted adapter contract."""


class CouncilActor(Protocol):
    """Provider-neutral actor contract consumed by the Council coordinator."""

    member: CouncilMember

    def identity_metadata(self) -> dict[str, Any]: ...

    def respond(self, context: PhaseContext) -> str: ...

    def ballot(self, context: PhaseContext) -> tuple[Ballot, str]: ...

    @property
    def replayable(self) -> bool: ...


def build_phase_prompt(context: PhaseContext) -> str:
    phase_instructions = {
        "WHITE": "State supported facts, unknowns, assumptions, and missing evidence. Do not smuggle speculation into facts.",
        "RED": "State intuition, suspicion, or heuristic reactions, clearly as non-evidence.",
        "BLACK": "Attack the proposition: identify flaws, confounders, counterexamples, hidden assumptions, and falsifiers.",
        "YELLOW": "Make the strongest constructive case and identify what useful result survives if the strongest claim fails.",
        "GREEN": "Generate genuinely distinct alternative explanations, hypotheses, and discriminating tests.",
        "BLUE": "Synthesize the narrowest current conclusion justified by the prior phases. Do not cast the sealed ballot yet.",
    }
    parts = [
        "You are a member of the NEXUS AI Council.",
        "All members have exactly one equal vote. Corporate/provider identity grants no authority.",
        "World mode changes framing and context only; it never changes evidence status, voting authority, or verification.",
        f"World mode: {context.mode_id}",
        f"Mode guidance: {context.mode_instruction}",
        f"Geometry region: {context.geometry_region_id}",
        "Keep this phase response concise; aim for no more than about 100 words.",
        f"Council phase: {context.phase.value}",
        f"Question: {context.question}",
        f"Evidence snapshot reference: {context.evidence_snapshot_ref}",
    ]
    if context.evidence_context:
        parts.extend(["Attached evidence view:", context.evidence_context])
    parts.append(phase_instructions[context.phase.value])
    if context.completed_phases:
        parts.append(f"Completed earlier phases: {json.dumps(context.completed_phases, sort_keys=True)}")
    if context.guard_nudge:
        parts.append(context.guard_nudge)
        parts.append("You must now restate the contribution using evidence or reasoning alone.")
    return "\n".join(parts)


def build_direct_prompt(
    message: str,
    *,
    mode_id: str,
    mode_instruction: str,
    geometry_region_id: str,
    evidence_context: str = "",
) -> str:
    parts = [
        "NEXUS Direct Cognitive Channel.",
        "This is a private operator exchange, not a Council vote or Council evidence decision.",
        f"World mode: {mode_id}",
        f"Mode guidance: {mode_instruction}",
        f"Geometry region: {geometry_region_id}",
    ]
    if evidence_context:
        parts.extend(["Attached local evidence view:", evidence_context])
    parts.extend(["Operator message:", message, "Reply concisely in the current mode."])
    return "\n".join(parts)


def build_ballot_prompt(context: PhaseContext) -> str:
    return (
        "NEXUS AI Council sealed ballot.\n"
        f"World mode: {context.mode_id}\n"
        f"Mode guidance: {context.mode_instruction}\n"
        f"Geometry region: {context.geometry_region_id}\n"
        f"Evidence snapshot: {context.evidence_snapshot_ref}\n"
        + (f"Attached evidence view:\n{context.evidence_context}\n" if context.evidence_context else "")
        + f"Question: {context.question}\n"
        "Review the completed phase material below and choose exactly one current disposition.\n"
        f"Allowed choices: {', '.join(ALLOWED_BALLOTS)}\n"
        f"Completed phases: {json.dumps(context.completed_phases, sort_keys=True)}\n"
        f"Required JSON schema: {json.dumps(BALLOT_SCHEMA, separators=(',', ':'))}\n"
        "Return only the requested JSON object. Keep the rationale concise. World mode may affect framing but not evidence "
        "status, vote weight, or verification. Provider identity, prestige, openness, company, model size, parameter count, "
        "or claimed frontier status gives no extra authority."
    )


def parse_ballot_response(raw: str, provider_label: str) -> tuple[Ballot, str]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AdapterProtocolError(f"invalid {provider_label} ballot response: malformed JSON") from exc
    if not isinstance(parsed, dict) or set(parsed) != {"choice", "rationale"}:
        raise AdapterProtocolError(f"invalid {provider_label} ballot response")
    choice = parsed["choice"]
    rationale = parsed["rationale"]
    if choice not in ALLOWED_BALLOTS or not isinstance(rationale, str) or not rationale.strip():
        raise AdapterProtocolError(f"invalid {provider_label} ballot response")
    return Ballot(choice), rationale.strip()
