from __future__ import annotations

from dataclasses import dataclass, field
from http.client import HTTPException
import json
import math
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from ..auth.types import AdapterAuthDescriptor, AuthFlow, AuthMethod, SecretMaterial
from ..scrub import SecretScrubber
from ..types import Ballot, CouncilMember, PhaseContext
from .base import (
    AdapterAuthenticationError,
    AdapterError,
    AdapterProtocolError,
    build_ballot_prompt,
    build_direct_prompt,
    build_phase_prompt,
    parse_ballot_response,
)


XAI_API_BASE_URL = "https://api.x.ai/v1"
XAI_API_HOST = "api.x.ai"
XAI_SETUP_URL = "https://console.x.ai/team/default/api-keys"
XAI_DEFAULT_TIMEOUT_SECONDS = 600.0
XAI_MAX_TIMEOUT_SECONDS = 3600.0
XAI_MAX_REQUEST_BYTES = 2 * 1024 * 1024
XAI_MAX_RESPONSE_BYTES = 4 * 1024 * 1024
XAI_MAX_MODEL_RESPONSE_BYTES = 1024 * 1024
XAI_MAX_MODELS = 512
XAI_PHASE_OUTPUT_TOKENS = 1024
XAI_DIRECT_OUTPUT_TOKENS = 1024
XAI_BALLOT_OUTPUT_TOKENS = 1024

_MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_XAI_API_KEY_SHAPE = re.compile(r"^xai-[A-Za-z0-9_-]{20,}$", re.I)
_MODALITY = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")


class _NoRedirectHandler(HTTPRedirectHandler):
    """Never forward a bearer credential across an HTTP redirect."""

    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        return None


def xai_auth_descriptor() -> AdapterAuthDescriptor:
    """The public xAI API contract admitted by NEXUS.

    xAI documents API-key authentication for third-party inference clients.
    Grok Build browser OAuth is deliberately not registered here because it is
    a first-party CLI session rather than a NEXUS OAuth client identity.
    """

    return AdapterAuthDescriptor(
        adapter_id="xai",
        provider_name="xAI Grok API",
        local_or_remote="remote",
        auth_methods=(AuthMethod.API_CREDENTIAL, AuthMethod.EXTERNAL_SECRET),
        auth_flows=(AuthFlow.API_KEY, AuthFlow.ENVIRONMENT, AuthFlow.EXTERNAL_COMMAND),
        setup_url=XAI_SETUP_URL,
    )


def _validate_model_id(model: str) -> str:
    if (
        not isinstance(model, str)
        or not _MODEL_ID.fullmatch(model)
        or _XAI_API_KEY_SHAPE.fullmatch(model)
    ):
        raise ValueError("xAI model id is invalid")
    return model


def _provider_model_id(value: Any) -> str:
    try:
        return _validate_model_id(value)
    except ValueError as exc:
        raise AdapterProtocolError("xAI returned an invalid language-model id") from exc


def _bounded_text(value: Any, field_name: str, *, maximum: int = 256) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > maximum
        or any(ord(character) < 0x20 for character in value)
        or _XAI_API_KEY_SHAPE.fullmatch(value)
    ):
        raise AdapterProtocolError(f"xAI {field_name} is invalid")
    return value


@dataclass
class XAITransport:
    """Bounded stdlib transport for xAI's fixed public inference endpoint."""

    credential: SecretMaterial = field(repr=False)
    timeout_seconds: float = XAI_DEFAULT_TIMEOUT_SECONDS
    _opener: Any = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.credential, SecretMaterial):
            raise AdapterAuthenticationError("xAI credential is unavailable")
        if self.credential.token_type.lower() != "bearer":
            raise AdapterAuthenticationError("xAI requires a bearer credential")
        if (
            isinstance(self.timeout_seconds, bool)
            or not isinstance(self.timeout_seconds, (int, float))
            or not math.isfinite(float(self.timeout_seconds))
            or not 0 < float(self.timeout_seconds) <= XAI_MAX_TIMEOUT_SECONDS
        ):
            raise ValueError(f"xAI timeout_seconds must be between 0 and {int(XAI_MAX_TIMEOUT_SECONDS)}")
        self.timeout_seconds = float(self.timeout_seconds)
        if self._opener is None:
            # Environment proxy variables are intentionally ignored so a
            # bearer token cannot silently leave the fixed xAI destination.
            self._opener = build_opener(ProxyHandler({}), _NoRedirectHandler())

    def probe(self) -> None:
        value = self._request_json("GET", "/models", maximum_bytes=XAI_MAX_MODEL_RESPONSE_BYTES)
        models = value.get("data")
        if not isinstance(models, list) or len(models) > XAI_MAX_MODELS:
            raise AdapterProtocolError("xAI model probe returned an invalid model list")

    def list_language_models(self) -> list[dict[str, Any]]:
        value = self._request_json("GET", "/language-models", maximum_bytes=XAI_MAX_MODEL_RESPONSE_BYTES)
        models = value.get("models")
        if not isinstance(models, list) or len(models) > XAI_MAX_MODELS:
            raise AdapterProtocolError("xAI returned an invalid language-model list")
        public_models = [self._public_model(item) for item in models]
        return sorted(public_models, key=lambda item: item["id"])

    def generate(
        self,
        model: str,
        prompt: str,
        *,
        max_output_tokens: int,
        require_complete: bool = True,
    ) -> str:
        _validate_model_id(model)
        if not isinstance(prompt, str) or not prompt.strip():
            raise AdapterProtocolError("xAI prompt must be non-empty text")
        if len(prompt.encode("utf-8")) > XAI_MAX_REQUEST_BYTES:
            raise AdapterProtocolError("xAI prompt exceeds the adapter request limit")
        if (
            isinstance(max_output_tokens, bool)
            or not isinstance(max_output_tokens, int)
            or not 1 <= max_output_tokens <= 32_768
        ):
            raise ValueError("xAI max_output_tokens must be between 1 and 32768")
        value = self._request_json(
            "POST",
            "/responses",
            payload={
                "model": model,
                "input": prompt,
                "max_output_tokens": max_output_tokens,
                "store": False,
            },
            maximum_bytes=XAI_MAX_RESPONSE_BYTES,
        )
        return self._response_text(value, require_complete=require_complete)

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        maximum_bytes: int,
    ) -> dict[str, Any]:
        if path not in {"/models", "/language-models", "/responses"}:
            raise AdapterProtocolError("xAI adapter attempted an unregistered endpoint")
        data = None
        if payload is not None:
            data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            if len(data) > XAI_MAX_REQUEST_BYTES:
                raise AdapterProtocolError("xAI request exceeds the adapter request limit")
        request = Request(
            f"{XAI_API_BASE_URL}{path}",
            data=data,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self.credential.access_token}",
                "Content-Type": "application/json",
                "User-Agent": "qsol-nexus-runtime/xai-adapter",
            },
            method=method,
        )
        try:
            with self._opener.open(request, timeout=self.timeout_seconds) as response:
                raw = response.read(maximum_bytes + 1)
        except HTTPError as exc:
            self._raise_http_error(exc.code)
        except (URLError, TimeoutError, OSError, HTTPException) as exc:
            raise AdapterError("xAI inference API is unavailable") from exc
        if len(raw) > maximum_bytes:
            raise AdapterProtocolError("xAI response exceeded the adapter size limit")
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
            raise AdapterProtocolError("xAI returned an invalid JSON response") from exc
        if not isinstance(value, dict):
            raise AdapterProtocolError("xAI returned an invalid JSON response")
        credential_kind = self._credential_kind(value)
        if credential_kind == "configured":
            raise AdapterProtocolError("xAI response contained configured credential material")
        if credential_kind == "shaped":
            raise AdapterProtocolError("xAI response contained credential-shaped text")
        return value

    def _credential_kind(self, value: object) -> str | None:
        """Classify secret material anywhere in a bounded provider response."""

        scrubber = SecretScrubber()
        pending = [value]
        while pending:
            item = pending.pop()
            if isinstance(item, str):
                if self.credential.access_token in item:
                    return "configured"
                if scrubber.scrub(item).changed:
                    return "shaped"
            elif isinstance(item, dict):
                pending.extend(item.keys())
                pending.extend(item.values())
            elif isinstance(item, list):
                pending.extend(item)
        return None

    @staticmethod
    def _raise_http_error(status: int) -> None:
        if status in {401, 403}:
            raise AdapterAuthenticationError("xAI rejected the configured credential")
        if 300 <= status < 400:
            raise AdapterProtocolError("xAI redirected a fixed adapter request")
        if status == 429:
            raise AdapterError("xAI request was rate-limited")
        if status in {400, 404, 409, 422}:
            raise AdapterError("xAI rejected the adapter request")
        raise AdapterError("xAI inference API is unavailable")

    @staticmethod
    def _public_model(value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise AdapterProtocolError("xAI returned an invalid language-model entry")
        model_id = _provider_model_id(value.get("id"))
        input_modalities = value.get("input_modalities")
        output_modalities = value.get("output_modalities")
        if (
            not isinstance(input_modalities, list)
            or not isinstance(output_modalities, list)
            or len(input_modalities) > 16
            or len(output_modalities) > 16
            or not all(isinstance(item, str) and _MODALITY.fullmatch(item) for item in input_modalities)
            or not all(isinstance(item, str) and _MODALITY.fullmatch(item) for item in output_modalities)
            or "text" not in input_modalities
            or "text" not in output_modalities
        ):
            raise AdapterProtocolError("xAI language-model modalities are invalid")
        aliases = value.get("aliases", [])
        if not isinstance(aliases, list) or len(aliases) > 32:
            raise AdapterProtocolError("xAI language-model aliases are invalid")
        try:
            public_aliases = [_validate_model_id(alias) for alias in aliases]
        except ValueError as exc:
            raise AdapterProtocolError("xAI language-model aliases are invalid") from exc
        public: dict[str, Any] = {
            "id": model_id,
            "aliases": sorted(set(public_aliases)),
            "input_modalities": list(input_modalities),
            "output_modalities": list(output_modalities),
        }
        for field_name in ("owned_by", "version", "fingerprint"):
            if value.get(field_name) is not None:
                public[field_name] = _bounded_text(value[field_name], field_name)
        for field_name in ("created", "context_length"):
            if value.get(field_name) is not None:
                field_value = value[field_name]
                if (
                    isinstance(field_value, bool)
                    or not isinstance(field_value, int)
                    or field_value < 0
                    or field_value > 2**63 - 1
                ):
                    raise AdapterProtocolError(f"xAI {field_name} is invalid")
                public[field_name] = field_value
        return public

    @staticmethod
    def _response_text(value: dict[str, Any], *, require_complete: bool) -> str:
        status = value.get("status")
        if status not in {"completed", "incomplete"} or value.get("error") is not None:
            raise AdapterProtocolError("xAI response did not complete successfully")
        if require_complete and status != "completed":
            raise AdapterProtocolError("xAI response was truncated before completion")
        output = value.get("output")
        if not isinstance(output, list) or len(output) > 64:
            raise AdapterProtocolError("xAI response output is invalid")
        texts: list[str] = []
        for item in output:
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            content = item.get("content")
            if not isinstance(content, list) or len(content) > 64:
                raise AdapterProtocolError("xAI response content is invalid")
            for part in content:
                if not isinstance(part, dict):
                    raise AdapterProtocolError("xAI response content is invalid")
                if part.get("type") != "output_text":
                    continue
                text = part.get("text")
                if not isinstance(text, str):
                    raise AdapterProtocolError("xAI response text is invalid")
                texts.append(text)
        result = "\n".join(texts).strip()
        if not result:
            raise AdapterProtocolError("xAI returned no response text")
        return result


def xai_connection_test(material: SecretMaterial | None) -> Any:
    # Imported lazily to keep the provider adapter independent of the broker's
    # registry construction path.
    from ..auth.broker import ConnectionCheck

    if material is None:
        return ConnectionCheck("unavailable", "xai_credential_missing")
    try:
        XAITransport(material, timeout_seconds=15.0).probe()
    except AdapterAuthenticationError:
        return ConnectionCheck("unavailable", "xai_auth_rejected")
    except (AdapterError, ValueError):
        return ConnectionCheck("unavailable", "xai_unavailable")
    return ConnectionCheck("healthy", "xai_healthy")


@dataclass
class XAIActor:
    """One equal-vote Council actor backed by xAI's Responses API."""

    member: CouncilMember
    model: str
    transport: XAITransport

    def __post_init__(self) -> None:
        _validate_model_id(self.model)

    @property
    def replayable(self) -> bool:
        return False

    def identity_metadata(self) -> dict[str, Any]:
        return {
            "actor_kind": "xai",
            "provider_model_id": self.model,
            "network_scope": "fixed_remote_https",
            "remote_host": XAI_API_HOST,
            "responses_api_store": False,
        }

    def respond(self, context: PhaseContext) -> str:
        return self.transport.generate(
            self.model,
            build_phase_prompt(context),
            max_output_tokens=XAI_PHASE_OUTPUT_TOKENS,
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
        return self.transport.generate(
            self.model,
            build_direct_prompt(
                message,
                mode_id=mode_id,
                mode_instruction=mode_instruction,
                geometry_region_id=geometry_region_id,
                evidence_context=evidence_context,
            ),
            max_output_tokens=XAI_DIRECT_OUTPUT_TOKENS,
            require_complete=False,
        )

    def ballot(self, context: PhaseContext) -> tuple[Ballot, str]:
        raw = self.transport.generate(
            self.model,
            build_ballot_prompt(context),
            max_output_tokens=XAI_BALLOT_OUTPUT_TOKENS,
            require_complete=True,
        )
        return parse_ballot_response(raw, "xAI")
