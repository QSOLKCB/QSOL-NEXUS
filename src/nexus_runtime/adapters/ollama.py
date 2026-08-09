from __future__ import annotations

import ipaddress
import json
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener, urlopen

from ..types import Ballot, CouncilMember, PhaseContext
from .base import BALLOT_SCHEMA, build_ballot_prompt, build_direct_prompt, build_phase_prompt, parse_ballot_response

_PHASE_OPTIONS = {"num_predict": 192}
_DIRECT_OPTIONS = {"num_predict": 256}
_ROMAN_ORATOR_PHASE_OPTIONS = {"num_predict": 768}
_ROMAN_ORATOR_DIRECT_OPTIONS = {"num_predict": 1536}
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
        return False

    def identity_metadata(self) -> dict[str, Any]:
        return {
            "actor_kind": "ollama",
            "ollama_model": self.model,
            "fixture_role": self.fixture_role,
            "network_scope": "loopback" if not self.transport.allow_remote else "configured_remote",
        }

    def respond(self, context: PhaseContext) -> str:
        options = _ROMAN_ORATOR_PHASE_OPTIONS if context.mode_id == "roman_orator" else _PHASE_OPTIONS
        return self.transport.generate(
            self.model,
            build_phase_prompt(context),
            options=options,
            require_complete=False,
        )

    def direct_message(
        self,
        message: str,
        *,
        mode_id: str,
        mode_instruction: str,
        geometry_region_id: str,
        evidence_context: str = "",
    ) -> str:
        """One non-Council local DCC-style exchange.

        This path confers no vote, Council phase, or evidence privilege. It is
        used by the Rust TUI's explicit private Direct Cognitive Channel view.
        """
        options = _ROMAN_ORATOR_DIRECT_OPTIONS if mode_id == "roman_orator" else _DIRECT_OPTIONS
        return self.transport.generate(
            self.model,
            build_direct_prompt(
                message,
                mode_id=mode_id,
                mode_instruction=mode_instruction,
                geometry_region_id=geometry_region_id,
                evidence_context=evidence_context,
            ),
            options=options,
            require_complete=False,
        )

    def ballot(self, context: PhaseContext) -> tuple[Ballot, str]:
        raw = self.transport.generate(
            self.model,
            build_ballot_prompt(context),
            format_schema=BALLOT_SCHEMA,
            options=_BALLOT_OPTIONS,
        )
        return parse_ballot_response(raw, "Ollama")
