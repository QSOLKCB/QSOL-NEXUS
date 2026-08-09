from __future__ import annotations

from dataclasses import dataclass, field
from http.client import HTTPException
import json
import math
import re
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit
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


THIRD_PARTY_DEFAULT_TIMEOUT_SECONDS = 600.0
THIRD_PARTY_MAX_TIMEOUT_SECONDS = 3600.0
THIRD_PARTY_MAX_REQUEST_BYTES = 2 * 1024 * 1024
THIRD_PARTY_MAX_RESPONSE_BYTES = 4 * 1024 * 1024
THIRD_PARTY_MAX_MODEL_RESPONSE_BYTES = 2 * 1024 * 1024
THIRD_PARTY_MAX_MODELS = 2048
THIRD_PARTY_MAX_MODEL_PAGES = 64
ANTHROPIC_MODEL_PAGE_LIMIT = 1000
GEMINI_MODEL_PAGE_SIZE = 1000
THIRD_PARTY_PHASE_OUTPUT_TOKENS = 1024
THIRD_PARTY_DIRECT_OUTPUT_TOKENS = 1024
THIRD_PARTY_ROMAN_ORATOR_OUTPUT_TOKENS = 2048
THIRD_PARTY_BALLOT_OUTPUT_TOKENS = 1024

_MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/+-]{0,191}$")
_SAFE_TEXT = re.compile(r"^[^\x00-\x1f\x7f]{1,256}$")


@dataclass(frozen=True)
class ProviderSpec:
    adapter_id: str
    provider_name: str
    base_url: str
    host: str
    api_style: str
    model_list_path: str
    setup_url: str | None = None


_PROVIDER_SPECS: dict[str, ProviderSpec] = {
    "openai": ProviderSpec(
        adapter_id="openai",
        provider_name="OpenAI API",
        base_url="https://api.openai.com/v1",
        host="api.openai.com",
        api_style="responses",
        model_list_path="/models",
        setup_url="https://platform.openai.com/api-keys",
    ),
    "anthropic": ProviderSpec(
        adapter_id="anthropic",
        provider_name="Anthropic Claude API",
        base_url="https://api.anthropic.com/v1",
        host="api.anthropic.com",
        api_style="anthropic_messages",
        model_list_path="/models",
        setup_url="https://console.anthropic.com/settings/keys",
    ),
    "gemini": ProviderSpec(
        adapter_id="gemini",
        provider_name="Google Gemini API",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        host="generativelanguage.googleapis.com",
        api_style="gemini_generate_content",
        model_list_path=f"/models?pageSize={GEMINI_MODEL_PAGE_SIZE}",
        setup_url="https://aistudio.google.com/apikey",
    ),
    "groq": ProviderSpec(
        adapter_id="groq",
        provider_name="Groq API",
        base_url="https://api.groq.com/openai/v1",
        host="api.groq.com",
        api_style="responses",
        model_list_path="/models",
        setup_url="https://console.groq.com/keys",
    ),
    "together": ProviderSpec(
        adapter_id="together",
        provider_name="Together AI API",
        base_url="https://api.together.ai/v1",
        host="api.together.ai",
        api_style="openai_chat",
        model_list_path="/models",
        setup_url=None,
    ),
}

THIRD_PARTY_PROVIDER_IDS = frozenset(_PROVIDER_SPECS)


class _NoRedirectHandler(HTTPRedirectHandler):
    """Do not forward provider credentials across redirects."""

    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        return None


def provider_spec(adapter_id: str) -> ProviderSpec:
    try:
        return _PROVIDER_SPECS[adapter_id]
    except KeyError as exc:
        raise ValueError("third-party provider id is not admitted") from exc


def third_party_auth_descriptors() -> tuple[AdapterAuthDescriptor, ...]:
    return tuple(
        AdapterAuthDescriptor(
            adapter_id=spec.adapter_id,
            provider_name=spec.provider_name,
            local_or_remote="remote",
            auth_methods=(AuthMethod.API_CREDENTIAL, AuthMethod.EXTERNAL_SECRET),
            auth_flows=(AuthFlow.API_KEY, AuthFlow.ENVIRONMENT, AuthFlow.EXTERNAL_COMMAND),
            setup_url=spec.setup_url,
        )
        for spec in _PROVIDER_SPECS.values()
    )


def _validate_model_id(model: str) -> str:
    if not isinstance(model, str) or not _MODEL_ID.fullmatch(model) or ".." in model:
        raise ValueError("provider model id is invalid")
    if model.startswith(("/", ".")) or model.endswith(("/", ".")):
        raise ValueError("provider model id is invalid")
    return model


def _bounded_text(value: Any, field_name: str, *, maximum: int = 256) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > maximum
        or any(ord(character) < 0x20 or ord(character) == 0x7F for character in value)
    ):
        raise AdapterProtocolError(f"provider {field_name} is invalid")
    return value


def _validate_pagination_token(value: Any, provider_name: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 2048
        or any(ord(character) < 0x20 or ord(character) == 0x7F for character in value)
    ):
        raise AdapterProtocolError(f"{provider_name} returned an invalid pagination cursor")
    return value


@dataclass
class ThirdPartyTransport:
    """Bounded fixed-destination stdlib transport for admitted cloud providers."""

    adapter_id: str
    credential: SecretMaterial = field(repr=False)
    timeout_seconds: float = THIRD_PARTY_DEFAULT_TIMEOUT_SECONDS
    _opener: Any = field(default=None, repr=False)

    def __post_init__(self) -> None:
        self.spec = provider_spec(self.adapter_id)
        if not isinstance(self.credential, SecretMaterial):
            raise AdapterAuthenticationError(f"{self.adapter_id} credential is unavailable")
        if isinstance(self.timeout_seconds, bool) or not isinstance(self.timeout_seconds, (int, float)):
            raise ValueError(
                f"provider timeout_seconds must be between 0 and {int(THIRD_PARTY_MAX_TIMEOUT_SECONDS)}"
            )
        try:
            timeout_seconds = float(self.timeout_seconds)
        except (OverflowError, ValueError) as exc:
            raise ValueError(
                f"provider timeout_seconds must be between 0 and {int(THIRD_PARTY_MAX_TIMEOUT_SECONDS)}"
            ) from exc
        if not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= THIRD_PARTY_MAX_TIMEOUT_SECONDS:
            raise ValueError(
                f"provider timeout_seconds must be between 0 and {int(THIRD_PARTY_MAX_TIMEOUT_SECONDS)}"
            )
        self.timeout_seconds = timeout_seconds
        if self._opener is None:
            self._opener = build_opener(ProxyHandler({}), _NoRedirectHandler())

    def probe(self) -> None:
        self.list_language_models()

    def list_language_models(self) -> list[dict[str, Any]]:
        if self.adapter_id == "anthropic":
            return self._list_anthropic_language_models()
        if self.adapter_id == "gemini":
            return self._list_gemini_language_models()

        value = self._request_json(
            "GET",
            self.spec.model_list_path,
            maximum_bytes=THIRD_PARTY_MAX_MODEL_RESPONSE_BYTES,
            allow_list=self.adapter_id == "together",
        )
        if self.adapter_id == "together":
            if not isinstance(value, list):
                raise AdapterProtocolError("together returned an invalid model list")
            models = [self._public_model(item) for item in value]
        else:
            items = value.get("data")
            if not isinstance(items, list):
                raise AdapterProtocolError(f"{self.adapter_id} returned an invalid model list")
            models = [self._public_model(item) for item in items]
        if len(models) > THIRD_PARTY_MAX_MODELS:
            raise AdapterProtocolError(f"{self.adapter_id} returned too many models")
        return sorted(models, key=lambda item: item["id"])

    def _list_anthropic_language_models(self) -> list[dict[str, Any]]:
        models: list[dict[str, Any]] = []
        after_id: str | None = None
        seen_cursors: set[str] = set()
        page_count = 0

        while True:
            page_count += 1
            if page_count > THIRD_PARTY_MAX_MODEL_PAGES:
                raise AdapterProtocolError("anthropic model pagination exceeded the page limit")
            query = {"limit": str(ANTHROPIC_MODEL_PAGE_LIMIT)}
            if after_id is not None:
                query["after_id"] = after_id
            value = self._request_json(
                "GET",
                f"/models?{urlencode(query)}",
                maximum_bytes=THIRD_PARTY_MAX_MODEL_RESPONSE_BYTES,
            )
            items = value.get("data")
            if not isinstance(items, list):
                raise AdapterProtocolError("anthropic returned an invalid model list")
            page = [self._public_model(item) for item in items]
            if len(models) + len(page) > THIRD_PARTY_MAX_MODELS:
                raise AdapterProtocolError("anthropic returned too many models")
            models.extend(page)

            has_more = value.get("has_more", False)
            if type(has_more) is not bool:
                raise AdapterProtocolError("anthropic returned an invalid pagination flag")
            if not has_more:
                break
            if not items:
                raise AdapterProtocolError("anthropic pagination made no progress")
            if len(models) >= THIRD_PARTY_MAX_MODELS:
                raise AdapterProtocolError("anthropic returned too many models")

            last_id = value.get("last_id")
            try:
                cursor = _validate_model_id(last_id)
            except ValueError as exc:
                raise AdapterProtocolError("anthropic returned an invalid pagination cursor") from exc
            if cursor in seen_cursors:
                raise AdapterProtocolError("anthropic repeated a pagination cursor")
            seen_cursors.add(cursor)
            after_id = cursor

        return sorted(models, key=lambda item: item["id"])

    def _list_gemini_language_models(self) -> list[dict[str, Any]]:
        models: list[dict[str, Any]] = []
        page_token: str | None = None
        seen_cursors: set[str] = set()
        page_count = 0

        while True:
            page_count += 1
            if page_count > THIRD_PARTY_MAX_MODEL_PAGES:
                raise AdapterProtocolError("Gemini model pagination exceeded the page limit")
            query = {"pageSize": str(GEMINI_MODEL_PAGE_SIZE)}
            if page_token is not None:
                query["pageToken"] = page_token
            value = self._request_json(
                "GET",
                f"/models?{urlencode(query)}",
                maximum_bytes=THIRD_PARTY_MAX_MODEL_RESPONSE_BYTES,
            )
            items = value.get("models")
            if not isinstance(items, list):
                raise AdapterProtocolError("Gemini returned an invalid model list")
            page = [self._gemini_public_model(item) for item in items]
            page = [item for item in page if item is not None]
            if len(models) + len(page) > THIRD_PARTY_MAX_MODELS:
                raise AdapterProtocolError("Gemini returned too many models")
            models.extend(page)

            next_token = value.get("nextPageToken")
            if next_token in {None, ""}:
                break
            if not items:
                raise AdapterProtocolError("Gemini pagination made no progress")
            cursor = _validate_pagination_token(next_token, "Gemini")
            if cursor in seen_cursors:
                raise AdapterProtocolError("Gemini repeated a pagination cursor")
            seen_cursors.add(cursor)
            page_token = cursor

        return sorted(models, key=lambda item: item["id"])

    def generate(
        self,
        model: str,
        prompt: str,
        *,
        max_output_tokens: int,
        require_complete: bool = True,
    ) -> str:
        model = _validate_model_id(model)
        if self.spec.api_style == "gemini_generate_content" and "/" in model:
            raise ValueError("Gemini model id must not contain a path separator")
        if not isinstance(prompt, str) or not prompt.strip():
            raise AdapterProtocolError("provider prompt must be non-empty text")
        if len(prompt.encode("utf-8")) > THIRD_PARTY_MAX_REQUEST_BYTES:
            raise AdapterProtocolError("provider prompt exceeds the adapter request limit")
        if (
            isinstance(max_output_tokens, bool)
            or not isinstance(max_output_tokens, int)
            or not 1 <= max_output_tokens <= 32_768
        ):
            raise ValueError("provider max_output_tokens must be between 1 and 32768")

        if self.spec.api_style == "responses":
            payload: dict[str, Any] = {
                "model": model,
                "input": prompt,
                "max_output_tokens": max_output_tokens,
            }
            if self.adapter_id == "openai":
                payload["store"] = False
            value = self._request_json(
                "POST",
                "/responses",
                payload=payload,
                maximum_bytes=THIRD_PARTY_MAX_RESPONSE_BYTES,
            )
            return self._responses_text(value, require_complete=require_complete)

        if self.spec.api_style == "anthropic_messages":
            value = self._request_json(
                "POST",
                "/messages",
                payload={
                    "model": model,
                    "max_tokens": max_output_tokens,
                    "messages": [{"role": "user", "content": prompt}],
                },
                maximum_bytes=THIRD_PARTY_MAX_RESPONSE_BYTES,
            )
            return self._anthropic_text(value, require_complete=require_complete)

        if self.spec.api_style == "gemini_generate_content":
            value = self._request_json(
                "POST",
                f"/models/{model}:generateContent",
                payload={
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                    "generationConfig": {"maxOutputTokens": max_output_tokens},
                },
                maximum_bytes=THIRD_PARTY_MAX_RESPONSE_BYTES,
            )
            return self._gemini_text(value, require_complete=require_complete)

        if self.spec.api_style == "openai_chat":
            value = self._request_json(
                "POST",
                "/chat/completions",
                payload={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_output_tokens,
                    "stream": False,
                },
                maximum_bytes=THIRD_PARTY_MAX_RESPONSE_BYTES,
            )
            return self._chat_text(value, require_complete=require_complete)

        raise AdapterProtocolError("provider API style is not implemented")

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        maximum_bytes: int,
        allow_list: bool = False,
    ) -> Any:
        if not self._path_is_admitted(method, path):
            raise AdapterProtocolError("provider adapter attempted an unregistered endpoint")
        data = None
        if payload is not None:
            data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            if len(data) > THIRD_PARTY_MAX_REQUEST_BYTES:
                raise AdapterProtocolError("provider request exceeds the adapter request limit")
        request = Request(
            f"{self.spec.base_url}{path}",
            data=data,
            headers=self._headers(),
            method=method,
        )
        try:
            with self._opener.open(request, timeout=self.timeout_seconds) as response:
                raw = response.read(maximum_bytes + 1)
        except HTTPError as exc:
            self._raise_http_error(exc.code)
        except (URLError, TimeoutError, OSError, HTTPException) as exc:
            raise AdapterError(f"{self.adapter_id} inference API is unavailable") from exc
        if len(raw) > maximum_bytes:
            raise AdapterProtocolError("provider response exceeded the adapter size limit")
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
            raise AdapterProtocolError("provider returned an invalid JSON response") from exc
        if not isinstance(value, dict) and not (allow_list and isinstance(value, list)):
            raise AdapterProtocolError("provider returned an invalid JSON response")
        credential_kind = self._credential_kind(value)
        if credential_kind == "configured":
            raise AdapterProtocolError("provider response contained configured credential material")
        if credential_kind == "shaped":
            raise AdapterProtocolError("provider response contained credential-shaped text")
        return value

    def _path_is_admitted(self, method: str, path: str) -> bool:
        if method == "GET":
            if path == self.spec.model_list_path:
                return True
            if self.adapter_id not in {"anthropic", "gemini"}:
                return False
            parsed = urlsplit(path)
            if parsed.scheme or parsed.netloc or parsed.path != "/models" or parsed.fragment:
                return False
            try:
                query = parse_qs(parsed.query, keep_blank_values=True, strict_parsing=True)
            except ValueError:
                return False

            if self.adapter_id == "anthropic":
                if query.get("limit") != [str(ANTHROPIC_MODEL_PAGE_LIMIT)]:
                    return False
                if set(query) == {"limit"}:
                    return True
                if set(query) != {"limit", "after_id"} or len(query["after_id"]) != 1:
                    return False
                try:
                    _validate_model_id(query["after_id"][0])
                except ValueError:
                    return False
                return True

            if query.get("pageSize") != [str(GEMINI_MODEL_PAGE_SIZE)]:
                return False
            if set(query) == {"pageSize"}:
                return True
            if set(query) != {"pageSize", "pageToken"} or len(query["pageToken"]) != 1:
                return False
            try:
                _validate_pagination_token(query["pageToken"][0], "Gemini")
            except AdapterProtocolError:
                return False
            return True

        if method != "POST":
            return False
        if self.spec.api_style == "responses":
            return path == "/responses"
        if self.spec.api_style == "anthropic_messages":
            return path == "/messages"
        if self.spec.api_style == "openai_chat":
            return path == "/chat/completions"
        if self.spec.api_style == "gemini_generate_content":
            prefix = "/models/"
            suffix = ":generateContent"
            if not path.startswith(prefix) or not path.endswith(suffix):
                return False
            model = path[len(prefix) : -len(suffix)]
            try:
                return "/" not in _validate_model_id(model)
            except ValueError:
                return False
        return False

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": f"qsol-nexus-runtime/{self.adapter_id}-adapter",
        }
        token = self.credential.access_token
        if self.adapter_id == "anthropic":
            headers["x-api-key"] = token
            headers["anthropic-version"] = "2023-06-01"
        elif self.adapter_id == "gemini":
            headers["x-goog-api-key"] = token
        else:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _credential_kind(self, value: object) -> str | None:
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

    def _raise_http_error(self, status: int) -> None:
        if status in {401, 403}:
            raise AdapterAuthenticationError(f"{self.adapter_id} rejected the configured credential")
        if 300 <= status < 400:
            raise AdapterProtocolError(f"{self.adapter_id} redirected a fixed adapter request")
        if status == 429:
            raise AdapterError(f"{self.adapter_id} request was rate-limited")
        if status in {400, 404, 409, 422}:
            raise AdapterError(f"{self.adapter_id} rejected the adapter request")
        raise AdapterError(f"{self.adapter_id} inference API is unavailable")

    @staticmethod
    def _public_model(value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise AdapterProtocolError("provider returned an invalid model entry")
        try:
            model_id = _validate_model_id(value.get("id"))
        except ValueError as exc:
            raise AdapterProtocolError("provider returned an invalid model id") from exc
        public: dict[str, Any] = {"id": model_id}
        for field_name in ("owned_by", "display_name", "type"):
            if value.get(field_name) is not None:
                public[field_name] = _bounded_text(value[field_name], field_name)
        for field_name in ("created", "created_at"):
            field_value = value.get(field_name)
            if field_value is not None:
                if isinstance(field_value, int) and not isinstance(field_value, bool) and 0 <= field_value <= 2**63 - 1:
                    public[field_name] = field_value
                elif isinstance(field_value, str) and _SAFE_TEXT.fullmatch(field_value):
                    public[field_name] = field_value
                else:
                    raise AdapterProtocolError(f"provider {field_name} is invalid")
        return public

    @staticmethod
    def _gemini_public_model(value: Any) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            raise AdapterProtocolError("Gemini returned an invalid model entry")
        name = value.get("name")
        if not isinstance(name, str) or not name.startswith("models/"):
            raise AdapterProtocolError("Gemini returned an invalid model name")
        model_id = name[len("models/") :]
        try:
            _validate_model_id(model_id)
        except ValueError as exc:
            raise AdapterProtocolError("Gemini returned an invalid model id") from exc
        if "/" in model_id:
            raise AdapterProtocolError("Gemini returned a path-shaped model id")
        methods = value.get("supportedGenerationMethods", [])
        if not isinstance(methods, list) or not all(isinstance(item, str) for item in methods):
            raise AdapterProtocolError("Gemini model generation methods are invalid")
        if methods and "generateContent" not in methods:
            return None
        public: dict[str, Any] = {"id": model_id}
        for field_name in ("displayName", "version", "description"):
            if value.get(field_name) is not None:
                public[field_name] = _bounded_text(value[field_name], field_name)
        for field_name in ("inputTokenLimit", "outputTokenLimit"):
            field_value = value.get(field_name)
            if field_value is not None:
                if isinstance(field_value, bool) or not isinstance(field_value, int) or not 0 <= field_value <= 2**63 - 1:
                    raise AdapterProtocolError(f"Gemini {field_name} is invalid")
                public[field_name] = field_value
        return public

    @staticmethod
    def _responses_text(value: dict[str, Any], *, require_complete: bool) -> str:
        status = value.get("status")
        if status not in {"completed", "incomplete"} or value.get("error") is not None:
            raise AdapterProtocolError("Responses API request did not complete successfully")
        if require_complete and status != "completed":
            raise AdapterProtocolError("Responses API output was truncated before completion")
        output = value.get("output")
        if not isinstance(output, list) or len(output) > 128:
            raise AdapterProtocolError("Responses API output is invalid")
        texts: list[str] = []
        for item in output:
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            content = item.get("content")
            if not isinstance(content, list) or len(content) > 128:
                raise AdapterProtocolError("Responses API message content is invalid")
            for part in content:
                if not isinstance(part, dict):
                    raise AdapterProtocolError("Responses API message content is invalid")
                if part.get("type") != "output_text":
                    continue
                text = part.get("text")
                if not isinstance(text, str):
                    raise AdapterProtocolError("Responses API output text is invalid")
                texts.append(text)
        result = "\n".join(texts).strip()
        if not result:
            raise AdapterProtocolError("Responses API returned no response text")
        return result

    @staticmethod
    def _anthropic_text(value: dict[str, Any], *, require_complete: bool) -> str:
        if value.get("type") not in {None, "message"}:
            raise AdapterProtocolError("Anthropic returned an invalid message response")
        stop_reason = value.get("stop_reason")
        if require_complete and stop_reason == "max_tokens":
            raise AdapterProtocolError("Anthropic output was truncated before completion")
        content = value.get("content")
        if not isinstance(content, list) or len(content) > 128:
            raise AdapterProtocolError("Anthropic response content is invalid")
        texts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                raise AdapterProtocolError("Anthropic response content is invalid")
            if item.get("type") != "text":
                continue
            text = item.get("text")
            if not isinstance(text, str):
                raise AdapterProtocolError("Anthropic response text is invalid")
            texts.append(text)
        result = "\n".join(texts).strip()
        if not result:
            raise AdapterProtocolError("Anthropic returned no response text")
        return result

    @staticmethod
    def _gemini_text(value: dict[str, Any], *, require_complete: bool) -> str:
        candidates = value.get("candidates")
        if not isinstance(candidates, list) or not candidates or len(candidates) > 16:
            raise AdapterProtocolError("Gemini returned an invalid candidate list")
        candidate = candidates[0]
        if not isinstance(candidate, dict):
            raise AdapterProtocolError("Gemini returned an invalid candidate")
        finish_reason = candidate.get("finishReason")
        blocked = {"SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII"}
        if finish_reason in blocked:
            raise AdapterProtocolError("Gemini declined the response at the provider boundary")
        if require_complete and finish_reason not in {None, "STOP"}:
            raise AdapterProtocolError("Gemini output was truncated before completion")
        content = candidate.get("content")
        if not isinstance(content, dict):
            raise AdapterProtocolError("Gemini response content is invalid")
        parts = content.get("parts")
        if not isinstance(parts, list) or len(parts) > 128:
            raise AdapterProtocolError("Gemini response parts are invalid")
        texts: list[str] = []
        for part in parts:
            if not isinstance(part, dict):
                raise AdapterProtocolError("Gemini response part is invalid")
            text = part.get("text")
            if text is None:
                continue
            if not isinstance(text, str):
                raise AdapterProtocolError("Gemini response text is invalid")
            texts.append(text)
        result = "\n".join(texts).strip()
        if not result:
            raise AdapterProtocolError("Gemini returned no response text")
        return result

    @staticmethod
    def _chat_text(value: dict[str, Any], *, require_complete: bool) -> str:
        choices = value.get("choices")
        if not isinstance(choices, list) or not choices or len(choices) > 16:
            raise AdapterProtocolError("chat-completions response choices are invalid")
        choice = choices[0]
        if not isinstance(choice, dict):
            raise AdapterProtocolError("chat-completions response choice is invalid")
        if require_complete and choice.get("finish_reason") in {"length", "content_filter"}:
            raise AdapterProtocolError("chat-completions output was truncated before completion")
        message = choice.get("message")
        if not isinstance(message, dict):
            raise AdapterProtocolError("chat-completions response message is invalid")
        text = message.get("content")
        if not isinstance(text, str) or not text.strip():
            raise AdapterProtocolError("chat-completions returned no response text")
        return text.strip()


def third_party_connection_test(adapter_id: str, material: SecretMaterial | None) -> Any:
    from ..auth.broker import ConnectionCheck

    if material is None:
        return ConnectionCheck("unavailable", f"{adapter_id}_credential_missing")
    try:
        ThirdPartyTransport(adapter_id, material, timeout_seconds=15.0).probe()
    except AdapterAuthenticationError:
        return ConnectionCheck("unavailable", f"{adapter_id}_auth_rejected")
    except (AdapterError, ValueError):
        return ConnectionCheck("unavailable", f"{adapter_id}_unavailable")
    return ConnectionCheck("healthy", f"{adapter_id}_healthy")


def third_party_connection_testers() -> dict[str, Callable[[SecretMaterial | None], Any]]:
    return {
        adapter_id: (lambda material, adapter_id=adapter_id: third_party_connection_test(adapter_id, material))
        for adapter_id in THIRD_PARTY_PROVIDER_IDS
    }


@dataclass
class ThirdPartyActor:
    """One equal-vote Council actor backed by an admitted fixed-host provider."""

    member: CouncilMember
    model: str
    transport: ThirdPartyTransport

    def __post_init__(self) -> None:
        _validate_model_id(self.model)
        if self.member.adapter_id != self.transport.adapter_id:
            raise ValueError("Council member adapter does not match provider transport")

    @property
    def replayable(self) -> bool:
        return False

    def identity_metadata(self) -> dict[str, Any]:
        return {
            "actor_kind": self.transport.adapter_id,
            "provider_model_id": self.model,
            "network_scope": "fixed_remote_https",
            "remote_host": self.transport.spec.host,
            "provider_api_style": self.transport.spec.api_style,
            "automatic_tools": False,
        }

    def respond(self, context: PhaseContext) -> str:
        output_tokens = (
            THIRD_PARTY_ROMAN_ORATOR_OUTPUT_TOKENS
            if context.mode_id == "roman_orator"
            else THIRD_PARTY_PHASE_OUTPUT_TOKENS
        )
        return self.transport.generate(
            self.model,
            build_phase_prompt(context),
            max_output_tokens=output_tokens,
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
        output_tokens = (
            THIRD_PARTY_ROMAN_ORATOR_OUTPUT_TOKENS
            if mode_id == "roman_orator"
            else THIRD_PARTY_DIRECT_OUTPUT_TOKENS
        )
        return self.transport.generate(
            self.model,
            build_direct_prompt(
                message,
                mode_id=mode_id,
                mode_instruction=mode_instruction,
                geometry_region_id=geometry_region_id,
                evidence_context=evidence_context,
            ),
            max_output_tokens=output_tokens,
            require_complete=False,
        )

    def ballot(self, context: PhaseContext) -> tuple[Ballot, str]:
        raw = self.transport.generate(
            self.model,
            build_ballot_prompt(context),
            max_output_tokens=THIRD_PARTY_BALLOT_OUTPUT_TOKENS,
            require_complete=True,
        )
        return parse_ballot_response(raw, self.transport.spec.provider_name)
