from __future__ import annotations

import ipaddress
import json
import math
import re
from dataclasses import dataclass, field
from http.client import HTTPException
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from ..types import Ballot, CouncilMember, PhaseContext
from .base import (
    BALLOT_SCHEMA,
    AdapterError,
    AdapterProtocolError,
    build_ballot_prompt,
    build_direct_prompt,
    build_phase_prompt,
    parse_ballot_response,
)

_PHASE_OPTIONS = {"num_predict": 192}
_DIRECT_OPTIONS = {"num_predict": 256}
_ROMAN_ORATOR_PHASE_OPTIONS = {"num_predict": 768}
_ROMAN_ORATOR_DIRECT_OPTIONS = {"num_predict": 1536}
_BALLOT_OPTIONS = {"num_predict": 256, "temperature": 0}

OLLAMA_DEFAULT_TIMEOUT_SECONDS = 90.0
OLLAMA_MAX_TIMEOUT_SECONDS = 1800.0
OLLAMA_MAX_REQUEST_BYTES = 2 * 1024 * 1024
OLLAMA_MAX_RESPONSE_BYTES = 4 * 1024 * 1024
_MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/+\-]{0,191}$")


class _NoRedirectHandler(HTTPRedirectHandler):
    """Reject HTTP redirects instead of allowing configured requests to escape."""

    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        return None


@dataclass
class OllamaTransport:
    """Bounded stdlib Ollama transport; loopback-only unless explicitly overridden."""

    base_url: str = "http://127.0.0.1:11434"
    timeout_seconds: float = OLLAMA_DEFAULT_TIMEOUT_SECONDS
    allow_remote: bool = False
    _local_opener: Any = field(init=False, repr=False, default=None)

    def __post_init__(self) -> None:
        if not isinstance(self.base_url, str) or not self.base_url:
            raise ValueError("invalid Ollama base_url")
        parsed = urlsplit(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("invalid Ollama base_url")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("Ollama base_url must not contain user-info")
        if parsed.query or parsed.fragment:
            raise ValueError("Ollama base_url must not contain a query or fragment")
        if parsed.path not in {"", "/"}:
            raise ValueError("Ollama base_url must be an origin without a path")
        if not self.allow_remote and not self._is_loopback(parsed.hostname):
            raise ValueError("Ollama transport is loopback-only by default")
        if isinstance(self.timeout_seconds, bool) or not isinstance(self.timeout_seconds, (int, float)):
            raise ValueError(
                f"Ollama timeout_seconds must be between 0 and {int(OLLAMA_MAX_TIMEOUT_SECONDS)}"
            )
        try:
            timeout_seconds = float(self.timeout_seconds)
        except (OverflowError, ValueError) as exc:
            raise ValueError(
                f"Ollama timeout_seconds must be between 0 and {int(OLLAMA_MAX_TIMEOUT_SECONDS)}"
            ) from exc
        if not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= OLLAMA_MAX_TIMEOUT_SECONDS:
            raise ValueError(
                f"Ollama timeout_seconds must be between 0 and {int(OLLAMA_MAX_TIMEOUT_SECONDS)}"
            )
        self.timeout_seconds = timeout_seconds
        self.base_url = self.base_url.rstrip("/")
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
        if self._local_opener is None:
            raise RuntimeError("Ollama opener was not initialized")
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
        if not isinstance(model, str) or _MODEL_ID.fullmatch(model) is None or ".." in model:
            raise ValueError("Ollama model id is invalid")
        if not isinstance(prompt, str) or not prompt.strip():
            raise AdapterProtocolError("Ollama prompt must be non-empty text")
        if len(prompt.encode("utf-8")) > OLLAMA_MAX_REQUEST_BYTES:
            raise AdapterProtocolError("Ollama prompt exceeds the request limit")

        payload: dict[str, Any] = {"model": model, "prompt": prompt, "stream": False}
        if format_schema is not None:
            payload["format"] = format_schema
        if options is not None:
            payload["options"] = options
        raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        if len(raw) > OLLAMA_MAX_REQUEST_BYTES:
            raise AdapterProtocolError("Ollama request exceeds the request limit")
        request = Request(
            f"{self.base_url}/api/generate",
            data=raw,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with self._open(request) as response:
                encoded = response.read(OLLAMA_MAX_RESPONSE_BYTES + 1)
        except HTTPError as exc:
            if 300 <= exc.code < 400:
                raise AdapterProtocolError("Ollama host attempted to redirect the request") from exc
            raise AdapterError("Ollama inference host rejected the request") from exc
        except (URLError, TimeoutError, OSError, HTTPException) as exc:
            raise AdapterError("Ollama inference host is unavailable") from exc
        if len(encoded) > OLLAMA_MAX_RESPONSE_BYTES:
            raise AdapterProtocolError("Ollama response exceeded the size limit")
        try:
            body = json.loads(encoded.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
            raise AdapterProtocolError("Ollama returned invalid JSON") from exc
        if not isinstance(body, dict):
            raise AdapterProtocolError("Ollama returned a non-object response")
        text = body.get("response")
        if not isinstance(text, str) or not text.strip():
            raise AdapterProtocolError("Ollama returned no response text")
        if body.get("done_reason") == "length" and require_complete:
            raise AdapterProtocolError("Ollama response truncated by generation limit")
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
        """One non-Council local DCC-style exchange."""
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
