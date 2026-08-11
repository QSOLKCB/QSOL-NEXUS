from __future__ import annotations

from dataclasses import asdict
import re
from typing import Any

from .adapters.base import AdapterProtocolError
from .adapters.local_ai import LocalAIActor
from .adapters.ollama import OllamaActor
from .control_plane import (
    RequestBudgetError,
    control_plane_policy_snapshot,
    validate_control_request,
)
from .provider_api import ProviderNexusAPI as _ProviderNexusAPI
from .scrub import SecretScrubber


_PATHISH_ERROR = re.compile(
    r"(?:\[Errno\s+\d+\]|No such file|Permission denied|File exists|"
    r"(?:^|[\s'\"(])/(?:[^\s'\")]+)|[A-Za-z]:\\|~[/\\])"
)


def _scrub_summary(scrubber: SecretScrubber, text: str) -> tuple[str, dict[str, Any]]:
    result = scrubber.scrub(text)
    return result.text, {
        "changed": result.changed,
        "events": [asdict(event) for event in result.events],
    }


def guard_model_text(
    text: str,
    *,
    scrubber: SecretScrubber,
    configured_secret: str | None = None,
    label: str = "local model",
) -> str:
    if not isinstance(text, str):
        raise AdapterProtocolError(f"{label} response text is invalid")
    if configured_secret and configured_secret in text:
        raise AdapterProtocolError(f"{label} response contained configured credential material")
    if scrubber.scrub(text).changed:
        raise AdapterProtocolError(f"{label} response contained credential-shaped text")
    return text


class _GuardedLocalActor:
    """Delegate actor that rejects secret reflection before Council persistence."""

    def __init__(self, actor: Any, scrubber: SecretScrubber) -> None:
        self._actor = actor
        self._scrubber = scrubber
        self.member = actor.member

    @property
    def replayable(self) -> bool:
        return self._actor.replayable

    def identity_metadata(self) -> dict[str, Any]:
        metadata = dict(self._actor.identity_metadata())
        metadata["output_credential_guard"] = "configured_exact_plus_secret_shape"
        return metadata

    def _secret(self) -> str | None:
        transport = getattr(self._actor, "transport", None)
        credential = getattr(transport, "credential", None)
        token = getattr(credential, "access_token", None)
        return token if isinstance(token, str) and token else None

    def _guard(self, text: str) -> str:
        return guard_model_text(
            text,
            scrubber=self._scrubber,
            configured_secret=self._secret(),
            label=self.member.adapter_id,
        )

    def respond(self, context: Any) -> str:
        return self._guard(self._actor.respond(context))

    def direct_message(self, *args: Any, **kwargs: Any) -> str:
        return self._guard(self._actor.direct_message(*args, **kwargs))

    def ballot(self, context: Any) -> Any:
        choice, rationale = self._actor.ballot(context)
        return choice, self._guard(rationale)


def sanitize_public_response(response: dict[str, Any]) -> dict[str, Any]:
    if response.get("status") != "error":
        return response
    error = response.get("error")
    if not isinstance(error, dict) or error.get("code") != "adapter_unavailable":
        return response
    message = error.get("message")
    if not isinstance(message, str) or _PATHISH_ERROR.search(message) is None:
        return response
    sanitized = dict(response)
    sanitized_error = dict(error)
    sanitized_error["message"] = "adapter or local storage operation is unavailable"
    sanitized["error"] = sanitized_error
    return sanitized


class HardenedNexusAPI(_ProviderNexusAPI):
    """Provider-aware API with alpha-exit control-plane hardening."""

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        request_id = request.get("request_id") if isinstance(request, dict) else None
        safe_request_id = request_id if self._request_id_is_preflight_safe(request_id) else None
        try:
            validate_control_request(request)
        except (RequestBudgetError, RecursionError) as exc:
            return self._error(safe_request_id, "invalid_request", str(exc))

        response = super().handle(request)
        if request.get("operation") == "system.health" and response.get("status") == "ok":
            response = dict(response)
            response["control_plane_limits"] = control_plane_policy_snapshot()

        if request.get("operation") == "actor.chat" and response.get("status") == "ok":
            text = response.get("response")
            if isinstance(text, str):
                response = dict(response)
                scrubbed_text, summary = _scrub_summary(self.scrubber, text)
                response["response"] = scrubbed_text
                response["response_secret_scrub"] = summary

        return sanitize_public_response(response)

    def _actor(self, item: Any) -> Any:
        actor = super()._actor(item)
        if isinstance(actor, (LocalAIActor, OllamaActor)):
            return _GuardedLocalActor(actor, self.scrubber)
        return actor


__all__ = [
    "HardenedNexusAPI",
    "guard_model_text",
    "sanitize_public_response",
]
