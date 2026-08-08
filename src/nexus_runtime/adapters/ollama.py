from __future__ import annotations

import ipaddress
import json
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener, urlopen

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

# NEXUS owns protocol-level output budgets instead of relying on a Modelfile
# default. Free-form hat contributions may be bounded at this limit; sealed
# ballots remain strict because truncated structured output is not a valid vote.
_PHASE_OPTIONS = {"num_predict": 192}
_BALLOT_OPTIONS = {"num_predict": 256, "temperature": 0}


class _NoRedirectHandler(HTTPRedirectHandler):
    """Reject HTTP redirects instead of allowing loopback requests to escape."""

    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        return None


@dataclass
class OllamaTransport:
    """Minimal stdlib Ollama transport. Loopback-only unless explicitly overridden."""

    base_url: str = "http://127.0.0.1:11434"
    timeout_seconds: float = 90.0
    allow_remote: bool = False
    _local_opener: Any = field(init=False, repr=False, default=None)

    def __post_init__(self) -> None:
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("invalid Ollama base_url")
        if not self.allow_remote and not self._is_loopback(parsed.hostname):
            raise ValueError("Ollama transport is loopback-only by default")
        if not self.allow_remote:
            # urllib otherwise inherits *_proxy environment variables and follows
            # redirects. Neither behavior is acceptable for the local-only trust
            # boundary, so use a private opener that does neither.
            self._local_opener = build_opener(ProxyHandler({}), _NoRedirectHandler())

    @staticmethod
    def _is_loopback(host: str) -> bool:
        if host.lower() == "localhost":
            return True
        try:
            return ipaddress.ip_address(host).is_loopback
        except ValueError:
            return False

    def _open(self, request: Request) -> Any:
        if self.allow_remote:
            return urlopen(request, timeout=self.timeout_seconds)
        if self._local_opener is None:
            raise RuntimeError("local Ollama opener was not initialized")
        return self._local_opener.open(request, timeout=self.timeout_seconds)

    def generate(
        self,
        model: str,
        prompt: str,
        *,
        format_schema: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
        require_complete: bool = True,
    ) -> str:
        payload: dict[str, Any] = {"model": model, "prompt": prompt, "stream": False}
        if format_schema is not None:
            payload["format"] = format_schema
        if options is not None:
            payload["options"] = options
        raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        request = Request(
            f"{self.base_url.rstrip('/')}/api/generate",
            data=raw,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self._open(request) as response:
            body = json.loads(response.read().decode("utf-8"))
        text = body.get("response")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Ollama returned no response text")
        if body.get("done_reason") == "length" and require_complete:
            raise ValueError("Ollama response truncated by generation limit")
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
        # Hat responses are free-form reasoning contributions. If a small model
        # reaches the bounded phase budget, the non-empty prefix remains a valid
        # contribution. Structured ballots do not get this relaxation.
        return self.transport.generate(
            self.model,
            prompt,
            options=_PHASE_OPTIONS,
            require_complete=False,
        )

    def ballot(self, context: PhaseContext) -> tuple[Ballot, str]:
        prompt = (
            "NEXUS AI Council sealed ballot.\n"
            f"Question: {context.question}\n"
            "Review the completed phase material below and choose exactly one current disposition.\n"
            f"Allowed choices: {', '.join(_ALLOWED_BALLOTS)}\n"
            f"Completed phases: {json.dumps(context.completed_phases, sort_keys=True)}\n"
            f"Required JSON schema: {json.dumps(_BALLOT_SCHEMA, separators=(',', ':'))}\n"
            "Return only the requested JSON object. Keep the rationale concise. Provider identity, prestige, openness, company, "
            "model size, parameter count, or claimed frontier status gives no extra authority."
        )
        raw = self.transport.generate(
            self.model,
            prompt,
            format_schema=_BALLOT_SCHEMA,
            options=_BALLOT_OPTIONS,
        )
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("invalid Ollama ballot response: malformed JSON") from exc
        if not isinstance(parsed, dict) or set(parsed) != {"choice", "rationale"}:
            raise ValueError("invalid Ollama ballot response")
        choice = parsed["choice"]
        rationale = parsed["rationale"]
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
            "Keep this phase response concise; aim for no more than about 100 words.",
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
