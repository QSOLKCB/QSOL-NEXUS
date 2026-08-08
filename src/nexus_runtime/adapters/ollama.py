from __future__ import annotations

import ipaddress
import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from ..types import Ballot, CouncilMember, PhaseContext

_ALLOWED_BALLOTS = [choice.value for choice in Ballot]
_BALLOT_SCHEMA = {
    "type": "object",
    "properties": {
        "choice": {"type": "string", "enum": _ALLOWED_BALLOTS},
        "rationale": {"type": "string"},
    },
    "required": ["choice", "rationale"],
    "additionalProperties": False,
}


@dataclass
class OllamaTransport:
    """Minimal stdlib Ollama transport. Loopback-only unless explicitly overridden."""

    base_url: str = "http://127.0.0.1:11434"
    timeout_seconds: float = 90.0
    allow_remote: bool = False

    def __post_init__(self) -> None:
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("invalid Ollama base_url")
        if not self.allow_remote and not self._is_loopback(parsed.hostname):
            raise ValueError("Ollama transport is loopback-only by default")

    @staticmethod
    def _is_loopback(host: str) -> bool:
        if host.lower() == "localhost":
            return True
        try:
            return ipaddress.ip_address(host).is_loopback
        except ValueError:
            return False

    def generate(self, model: str, prompt: str, *, format_schema: dict[str, Any] | None = None) -> str:
        payload: dict[str, Any] = {"model": model, "prompt": prompt, "stream": False}
        if format_schema is not None:
            payload["format"] = format_schema
        raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        request = Request(
            f"{self.base_url.rstrip('/')}/api/generate",
            data=raw,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
        text = body.get("response")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Ollama returned no response text")
        return text.strip()


@dataclass
class OllamaActor:
    """Council actor backed by a local Ollama model."""

    member: CouncilMember
    model: str
    transport: OllamaTransport
    fixture_role: str = "local_model"

    @property
    def replayable(self) -> bool:
        # A seed can improve fixture stability, but live model inference is not
        # claimed as deterministic replay across Ollama/model/runtime versions.
        return False

    def identity_metadata(self) -> dict[str, Any]:
        return {
            "actor_kind": "ollama",
            "ollama_model": self.model,
            "fixture_role": self.fixture_role,
            "network_scope": "loopback" if not self.transport.allow_remote else "configured_remote",
        }

    def respond(self, context: PhaseContext) -> str:
        prompt = self._phase_prompt(context)
        return self.transport.generate(self.model, prompt)

    def ballot(self, context: PhaseContext) -> tuple[Ballot, str]:
        prompt = (
            "NEXUS AI Council sealed ballot.\n"
            f"Question: {context.question}\n"
            "Review the completed phase material below and choose exactly one current disposition.\n"
            f"Allowed choices: {', '.join(_ALLOWED_BALLOTS)}\n"
            f"Completed phases: {json.dumps(context.completed_phases, sort_keys=True)}\n"
            "Return only the requested JSON object. Provider identity, prestige, openness, company, "
            "or claimed frontier status gives no extra authority."
        )
        raw = self.transport.generate(self.model, prompt, format_schema=_BALLOT_SCHEMA)
        parsed = json.loads(raw)
        choice = parsed.get("choice")
        rationale = parsed.get("rationale")
        if choice not in _ALLOWED_BALLOTS or not isinstance(rationale, str) or not rationale.strip():
            raise ValueError("invalid Ollama ballot response")
        return Ballot(choice), rationale.strip()

    @staticmethod
    def _phase_prompt(context: PhaseContext) -> str:
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
            f"Council phase: {context.phase.value}",
            f"Question: {context.question}",
            f"Evidence snapshot reference: {context.evidence_snapshot_ref}",
            phase_instructions[context.phase.value],
        ]
        if context.completed_phases:
            parts.append(f"Completed earlier phases: {json.dumps(context.completed_phases, sort_keys=True)}")
        if context.guard_nudge:
            parts.append(context.guard_nudge)
            parts.append("You must now restate the contribution using evidence or reasoning alone.")
        return "\n".join(parts)
