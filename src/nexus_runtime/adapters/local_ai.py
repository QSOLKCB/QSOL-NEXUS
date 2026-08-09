from __future__ import annotations

from dataclasses import dataclass, field
from http.client import HTTPException
import hashlib
import ipaddress
import json
import math
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from ..auth.types import AdapterAuthDescriptor, AuthFlow, AuthMethod, SecretMaterial
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


LOCAL_AI_ADAPTER_IDS = frozenset({"lmstudio_local", "anythingllm_local", "openai_local"})
LOCAL_AI_MAX_REQUEST_BYTES = 2 * 1024 * 1024
LOCAL_AI_MAX_RESPONSE_BYTES = 4 * 1024 * 1024
LOCAL_AI_MAX_OUTPUT_TOKENS = 4096
LOCAL_AI_DEFAULT_TIMEOUT_SECONDS = 180.0
LOCAL_AI_MAX_TIMEOUT_SECONDS = 1800.0
LOCAL_AI_PHASE_OUTPUT_TOKENS = 768
LOCAL_AI_DIRECT_OUTPUT_TOKENS = 1024
LOCAL_AI_ROMAN_ORATOR_OUTPUT_TOKENS = 2048
LOCAL_AI_BALLOT_OUTPUT_TOKENS = 512

_DEFAULT_ENDPOINTS = {
    "lmstudio_local": "http://127.0.0.1:1234",
    "anythingllm_local": "http://127.0.0.1:3001",
    "openai_local": "http://127.0.0.1:8000",
}
_MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/+-]{0,191}$")
_WORKSPACE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_MCP_PLUGIN_ID = re.compile(r"^mcp/[A-Za-z0-9][A-Za-z0-9._/-]{0,190}$")
_MCP_TOOL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")


class _NoRedirectHandler(HTTPRedirectHandler):
    """Reject redirects so a loopback credential/request cannot escape."""

    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        return None


def local_ai_auth_descriptors() -> tuple[AdapterAuthDescriptor, ...]:
    """Authentication descriptors for optional loopback-local AI hosts."""

    optional_token_methods = (
        AuthMethod.LOCAL_ENDPOINT,
        AuthMethod.NO_AUTH_REQUIRED,
        AuthMethod.API_CREDENTIAL,
        AuthMethod.EXTERNAL_SECRET,
    )
    optional_token_flows = (
        AuthFlow.LOCAL_ENDPOINT,
        AuthFlow.NONE,
        AuthFlow.API_KEY,
        AuthFlow.ENVIRONMENT,
        AuthFlow.EXTERNAL_COMMAND,
    )
    return (
        AdapterAuthDescriptor(
            adapter_id="lmstudio_local",
            provider_name="LM Studio loopback",
            local_or_remote="local",
            auth_methods=optional_token_methods,
            auth_flows=optional_token_flows,
        ),
        AdapterAuthDescriptor(
            adapter_id="anythingllm_local",
            provider_name="AnythingLLM loopback",
            local_or_remote="local",
            auth_methods=optional_token_methods,
            auth_flows=optional_token_flows,
        ),
        AdapterAuthDescriptor(
            adapter_id="openai_local",
            provider_name="OpenAI-compatible loopback",
            local_or_remote="local",
            auth_methods=optional_token_methods,
            auth_flows=optional_token_flows,
        ),
    )


def default_local_ai_endpoint(adapter_id: str) -> str:
    try:
        return _DEFAULT_ENDPOINTS[adapter_id]
    except KeyError as exc:
        raise ValueError("local AI adapter id is not admitted") from exc


def validate_local_ai_endpoint(value: str) -> str:
    """Require a root loopback HTTP(S) origin with no redirect/proxy escape surface."""

    if not isinstance(value, str) or not value:
        raise ValueError("local AI endpoint must be a non-empty URL")
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("local AI endpoint must use HTTP or HTTPS")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("local AI endpoint must not contain user-info")
    if parsed.query or parsed.fragment:
        raise ValueError("local AI endpoint must not contain a query or fragment")
    if parsed.path not in {"", "/"}:
        raise ValueError("local AI endpoint must be an origin without a path")
    host = parsed.hostname.lower()
    if host != "localhost":
        try:
            address = ipaddress.ip_address(host)
        except ValueError as exc:
            raise ValueError("local AI endpoint must use localhost or a loopback IP literal") from exc
        if not address.is_loopback:
            raise ValueError("local AI endpoint must resolve to a loopback address")
    return value.rstrip("/")


def _validate_model(value: str) -> str:
    if not isinstance(value, str) or _MODEL_ID.fullmatch(value) is None or ".." in value:
        raise ValueError("local AI model id is invalid")
    return value


def _validate_workspace(value: str) -> str:
    if not isinstance(value, str) or _WORKSPACE.fullmatch(value) is None:
        raise ValueError("AnythingLLM workspace slug is invalid")
    return value


@dataclass(frozen=True)
class LocalMCPPlugin:
    """One pre-configured LM Studio mcp.json plugin reference.

    NEXUS intentionally accepts plugin ids only. It never accepts per-request
    MCP URLs, headers, commands, or environment variables through this surface.
    """

    plugin_id: str
    allowed_tools: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.plugin_id, str) or _MCP_PLUGIN_ID.fullmatch(self.plugin_id) is None:
            raise ValueError("LM Studio MCP plugin id must use the mcp/<server> form")
        if (
            not isinstance(self.allowed_tools, tuple)
            or len(self.allowed_tools) > 64
            or not all(isinstance(item, str) and _MCP_TOOL.fullmatch(item) for item in self.allowed_tools)
            or len(set(self.allowed_tools)) != len(self.allowed_tools)
        ):
            raise ValueError("LM Studio MCP allowed_tools must be unique bounded tool names")

    def request_value(self) -> dict[str, Any]:
        value: dict[str, Any] = {"type": "plugin", "id": self.plugin_id}
        if self.allowed_tools:
            value["allowed_tools"] = list(self.allowed_tools)
        return value


@dataclass
class LocalAITransport:
    """Bounded loopback-only transport for local model hosts.

    MCP is delegated only to pre-configured LM Studio plugin ids. NEXUS does not
    admit ephemeral MCP server URLs on this boundary and does not claim that a
    downstream host's own plugin configuration is independently verified.
    """

    adapter_id: str
    endpoint: str | None = None
    credential: SecretMaterial | None = field(default=None, repr=False)
    timeout_seconds: float = LOCAL_AI_DEFAULT_TIMEOUT_SECONDS
    _opener: Any = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self.adapter_id not in LOCAL_AI_ADAPTER_IDS:
            raise ValueError("local AI adapter id is not admitted")
        self.endpoint = validate_local_ai_endpoint(
            self.endpoint or default_local_ai_endpoint(self.adapter_id)
        )
        if self.credential is not None and not isinstance(self.credential, SecretMaterial):
            raise AdapterAuthenticationError("local AI credential is invalid")
        if (
            isinstance(self.timeout_seconds, bool)
            or not isinstance(self.timeout_seconds, (int, float))
            or not math.isfinite(float(self.timeout_seconds))
            or not 0 < float(self.timeout_seconds) <= LOCAL_AI_MAX_TIMEOUT_SECONDS
        ):
            raise ValueError("local AI timeout_seconds is outside the admitted range")
        self.timeout_seconds = float(self.timeout_seconds)
        if self._opener is None:
            self._opener = build_opener(ProxyHandler({}), _NoRedirectHandler())

    def generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        workspace: str | None = None,
        mcp_plugins: tuple[LocalMCPPlugin, ...] = (),
        session_key: str | None = None,
        max_output_tokens: int = 768,
    ) -> str:
        if not isinstance(prompt, str) or not prompt.strip():
            raise AdapterProtocolError("local AI prompt must be non-empty text")
        if len(prompt.encode("utf-8")) > LOCAL_AI_MAX_REQUEST_BYTES:
            raise AdapterProtocolError("local AI prompt exceeds the request limit")
        if (
            isinstance(max_output_tokens, bool)
            or not isinstance(max_output_tokens, int)
            or not 1 <= max_output_tokens <= LOCAL_AI_MAX_OUTPUT_TOKENS
        ):
            raise ValueError("local AI max_output_tokens is outside the admitted range")
        if not isinstance(mcp_plugins, tuple) or not all(
            isinstance(item, LocalMCPPlugin) for item in mcp_plugins
        ):
            raise ValueError("mcp_plugins must be validated LocalMCPPlugin values")

        if self.adapter_id == "lmstudio_local":
            if workspace is not None:
                raise ValueError("LM Studio local role does not accept a workspace")
            if model is None:
                raise ValueError("LM Studio local role requires a model")
            model = _validate_model(model)
            payload: dict[str, Any] = {
                "model": model,
                "input": prompt,
                "stream": False,
                "temperature": 0,
                "max_output_tokens": max_output_tokens,
                "store": False,
            }
            if mcp_plugins:
                payload["integrations"] = [item.request_value() for item in mcp_plugins]
            value = self._request_json("/api/v1/chat", payload)
            return self._lmstudio_text(value)

        if self.adapter_id == "anythingllm_local":
            if model is not None:
                raise ValueError("AnythingLLM local role selects its model through the workspace")
            if mcp_plugins:
                raise ValueError("AnythingLLM MCP configuration is managed by the local workspace host")
            if workspace is None:
                raise ValueError("AnythingLLM local role requires a workspace")
            workspace = _validate_workspace(workspace)
            payload = {"message": prompt, "mode": "chat"}
            if session_key is not None:
                if not isinstance(session_key, str) or not session_key or len(session_key) > 128:
                    raise ValueError("AnythingLLM session_key must be bounded text")
                payload["sessionId"] = session_key
            value = self._request_json(
                f"/api/v1/workspace/{quote(workspace, safe='')}/chat",
                payload,
            )
            return self._anythingllm_text(value)

        if workspace is not None or mcp_plugins:
            raise ValueError("OpenAI-compatible local role does not accept workspace or MCP plugin fields")
        if model is None:
            raise ValueError("OpenAI-compatible local role requires a model")
        model = _validate_model(model)
        value = self._request_json(
            "/v1/chat/completions",
            {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_output_tokens,
                "temperature": 0,
                "stream": False,
            },
        )
        return self._openai_chat_text(value)

    def _request_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        if len(raw) > LOCAL_AI_MAX_REQUEST_BYTES:
            raise AdapterProtocolError("local AI request exceeds the request limit")
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": f"qsol-nexus-runtime/{self.adapter_id}",
        }
        if self.credential is not None:
            headers["Authorization"] = f"Bearer {self.credential.access_token}"
        request = Request(
            f"{self.endpoint}{path}",
            data=raw,
            headers=headers,
            method="POST",
        )
        try:
            with self._opener.open(request, timeout=self.timeout_seconds) as response:
                body = response.read(LOCAL_AI_MAX_RESPONSE_BYTES + 1)
        except HTTPError as exc:
            if exc.code in {401, 403}:
                raise AdapterAuthenticationError(
                    f"{self.adapter_id} rejected the configured local credential"
                ) from exc
            if 300 <= exc.code < 400:
                raise AdapterProtocolError("local AI host attempted to redirect the request") from exc
            raise AdapterError(f"{self.adapter_id} local inference request failed") from exc
        except (URLError, TimeoutError, OSError, HTTPException) as exc:
            raise AdapterError(f"{self.adapter_id} local inference host is unavailable") from exc
        if len(body) > LOCAL_AI_MAX_RESPONSE_BYTES:
            raise AdapterProtocolError("local AI response exceeded the size limit")
        try:
            value = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
            raise AdapterProtocolError("local AI host returned invalid JSON") from exc
        if not isinstance(value, dict):
            raise AdapterProtocolError("local AI host returned a non-object response")
        return value

    @staticmethod
    def _lmstudio_text(value: dict[str, Any]) -> str:
        output = value.get("output")
        if not isinstance(output, list) or len(output) > 256:
            raise AdapterProtocolError("LM Studio returned an invalid output list")
        texts: list[str] = []
        for item in output:
            if not isinstance(item, dict):
                raise AdapterProtocolError("LM Studio returned an invalid output item")
            if item.get("type") != "message":
                continue
            content = item.get("content")
            if not isinstance(content, str):
                raise AdapterProtocolError("LM Studio returned invalid message content")
            texts.append(content)
        text = "\n".join(texts).strip()
        if not text:
            raise AdapterProtocolError("LM Studio returned no response text")
        return text

    @staticmethod
    def _anythingllm_text(value: dict[str, Any]) -> str:
        if value.get("error") not in {None, False, ""}:
            raise AdapterProtocolError("AnythingLLM reported a local workspace error")
        text = value.get("textResponse")
        if not isinstance(text, str) or not text.strip():
            raise AdapterProtocolError("AnythingLLM returned no response text")
        return text.strip()

    @staticmethod
    def _openai_chat_text(value: dict[str, Any]) -> str:
        choices = value.get("choices")
        if not isinstance(choices, list) or not choices or len(choices) > 16:
            raise AdapterProtocolError("local OpenAI-compatible choices are invalid")
        choice = choices[0]
        if not isinstance(choice, dict):
            raise AdapterProtocolError("local OpenAI-compatible choice is invalid")
        message = choice.get("message")
        if not isinstance(message, dict):
            raise AdapterProtocolError("local OpenAI-compatible message is invalid")
        text = message.get("content")
        if not isinstance(text, str) or not text.strip():
            raise AdapterProtocolError("local OpenAI-compatible host returned no response text")
        return text.strip()


@dataclass
class LocalAIActor:
    """One equal-vote Council actor backed by a loopback-local model host."""

    member: CouncilMember
    transport: LocalAITransport
    model: str | None = None
    workspace: str | None = None
    mcp_plugins: tuple[LocalMCPPlugin, ...] = ()
    max_output_tokens: int = LOCAL_AI_PHASE_OUTPUT_TOKENS

    def __post_init__(self) -> None:
        if self.member.adapter_id != self.transport.adapter_id:
            raise ValueError("local AI member adapter does not match transport")
        if self.transport.adapter_id == "anythingllm_local":
            if self.workspace is None or self.model is not None:
                raise ValueError("AnythingLLM actor requires workspace and no model override")
            _validate_workspace(self.workspace)
        else:
            if self.model is None or self.workspace is not None:
                raise ValueError("local AI actor requires model and no workspace")
            _validate_model(self.model)
        if not isinstance(self.mcp_plugins, tuple) or not all(
            isinstance(item, LocalMCPPlugin) for item in self.mcp_plugins
        ):
            raise ValueError("local AI actor MCP plugins are invalid")
        if self.mcp_plugins and self.transport.adapter_id != "lmstudio_local":
            raise ValueError("only LM Studio local actors accept NEXUS-selected MCP plugins")

    @property
    def replayable(self) -> bool:
        return False

    def identity_metadata(self) -> dict[str, Any]:
        return {
            "actor_kind": self.transport.adapter_id,
            "network_scope": "loopback_only",
            "local_model_id": self.model,
            "anythingllm_workspace": self.workspace,
            "mcp_plugin_ids": [item.plugin_id for item in self.mcp_plugins],
            "mcp_ephemeral_urls_allowed": False,
            "mcp_tools_enabled_for_ballot": False,
            "automatic_tools": bool(self.mcp_plugins),
        }

    def _session_key(self, value: str) -> str:
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]
        return f"nexus-{self.member.member_id}-{digest}"[:128]

    def respond(self, context: PhaseContext) -> str:
        output_tokens = (
            LOCAL_AI_ROMAN_ORATOR_OUTPUT_TOKENS
            if context.mode_id == "roman_orator"
            else self.max_output_tokens
        )
        return self.transport.generate(
            build_phase_prompt(context),
            model=self.model,
            workspace=self.workspace,
            mcp_plugins=self.mcp_plugins,
            session_key=self._session_key(
                f"phase:{context.session_id}:{context.phase.value}:{self.member.member_id}"
            ),
            max_output_tokens=output_tokens,
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
        output_tokens = (
            LOCAL_AI_ROMAN_ORATOR_OUTPUT_TOKENS
            if mode_id == "roman_orator"
            else LOCAL_AI_DIRECT_OUTPUT_TOKENS
        )
        prompt = build_direct_prompt(
            message,
            mode_id=mode_id,
            mode_instruction=mode_instruction,
            geometry_region_id=geometry_region_id,
            evidence_context=evidence_context,
        )
        return self.transport.generate(
            prompt,
            model=self.model,
            workspace=self.workspace,
            mcp_plugins=self.mcp_plugins,
            session_key=self._session_key(f"direct:{mode_id}:{geometry_region_id}:{message}"),
            max_output_tokens=output_tokens,
        )

    def ballot(self, context: PhaseContext) -> tuple[Ballot, str]:
        # MCP integrations are intentionally absent from sealed-ballot calls.
        raw = self.transport.generate(
            build_ballot_prompt(context),
            model=self.model,
            workspace=self.workspace,
            mcp_plugins=(),
            session_key=self._session_key(
                f"ballot:{context.session_id}:{self.member.member_id}"
            ),
            max_output_tokens=LOCAL_AI_BALLOT_OUTPUT_TOKENS,
        )
        return parse_ballot_response(raw, self.transport.adapter_id)


__all__ = [
    "LOCAL_AI_ADAPTER_IDS",
    "LOCAL_AI_DEFAULT_TIMEOUT_SECONDS",
    "LOCAL_AI_MAX_OUTPUT_TOKENS",
    "LocalAIActor",
    "LocalAITransport",
    "LocalMCPPlugin",
    "default_local_ai_endpoint",
    "local_ai_auth_descriptors",
    "validate_local_ai_endpoint",
]
