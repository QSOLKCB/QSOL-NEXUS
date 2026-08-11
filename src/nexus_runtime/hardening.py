from __future__ import annotations

from dataclasses import asdict
import re
from typing import Any

from .adapters.base import AdapterProtocolError
from .adapters.local_ai import LocalAIActor
from .adapters.ollama import OllamaActor
from .civic_observation import (
    CivicObservationError,
    civic_observation_policy_snapshot,
    view_council_proceeding,
)
from .control_plane import (
    RequestBudgetError,
    control_plane_policy_snapshot,
    validate_control_request,
)
from .provider_api import ProviderNexusAPI as _ProviderNexusAPI
from .scrub import SecretScrubber
from .trap import TrapError


_PATHISH_ERROR = re.compile(
    r"(?:\[Errno\s+\d+\]|No such file|Permission denied|File exists|"
    r"(?:^|[\s'\"(])/(?:[^\s'\")]+)|[A-Za-z]:\\|~[/\\])"
)
_CIVIC_OBSERVATION_OPERATIONS = frozenset(
    {"council.proceedings.policy", "council.proceedings.view"}
)
_RUNTIME_RESERVED_WORLD_TYPES = frozenset(
    {"council_session", "evidence_snapshot", "receipt", "world_presence"}
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


def _public_gallery_result(result: Any) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise CivicObservationError(
            "council_proceeding_invalid",
            "committed Council proceeding has an invalid result",
        )
    tally = result.get("tally")
    threshold = result.get("consensus_threshold")
    minority_reports = result.get("minority_reports")
    if not isinstance(tally, dict) or not isinstance(threshold, dict) or not isinstance(minority_reports, list):
        raise CivicObservationError(
            "council_proceeding_invalid",
            "committed Council proceeding has an invalid result",
        )
    return {
        "disposition": result.get("disposition"),
        "tally": dict(tally),
        "consensus_label": result.get("consensus_label"),
        "consensus_threshold": dict(threshold),
        "evidence_state": result.get("evidence_state"),
        "minority_or_disagreement_present": bool(minority_reports),
        "minority_report_count": len(minority_reports),
        "individual_minority_reports_visible": False,
    }


class HardenedNexusAPI(_ProviderNexusAPI):
    """Provider-aware API with alpha-exit control-plane hardening."""

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        request_id = request.get("request_id") if isinstance(request, dict) else None
        safe_request_id = request_id if self._request_id_is_preflight_safe(request_id) else None
        try:
            validate_control_request(request)
        except (RequestBudgetError, RecursionError) as exc:
            return self._error(safe_request_id, "invalid_request", str(exc))
        if request_id is not None and safe_request_id is None:
            return self._error(
                None,
                "invalid_request",
                "request_id must be a bounded non-secret identifier",
            )

        operation = request.get("operation")
        if operation == "world.create":
            object_type = request.get("object_type")
            provenance = request.get("provenance", {"actor": "human_operator"})
            reserved = (
                isinstance(object_type, str) and object_type in _RUNTIME_RESERVED_WORLD_TYPES
            ) or (
                isinstance(provenance, dict) and provenance.get("actor") == "nexus"
            )
            if reserved:
                # Preserve Trap Base precedence for a mutation that would
                # otherwise be rejected by this hardened public boundary.
                try:
                    self.trap_mutation_gate.assert_mutation_allowed()
                except TrapError:
                    return super().handle(request)
                return self._error(
                    safe_request_id,
                    "invalid_request",
                    "reserved runtime Council objects and nexus provenance require validated runtime operations",
                )

        # Keep malformed/unhashable operation values inside the established
        # Provider/Core structured-error boundary. The civic overlay only owns
        # its two exact string operation names.
        if isinstance(operation, str) and operation in _CIVIC_OBSERVATION_OPERATIONS:
            return self._handle_civic_observation(request, safe_request_id)

        response = super().handle(request)
        if operation == "system.health" and response.get("status") == "ok":
            response = dict(response)
            response["control_plane_limits"] = control_plane_policy_snapshot()
            response["civic_observation"] = civic_observation_policy_snapshot(self.geometry)
        elif operation == "system.operations" and response.get("status") == "ok":
            response = dict(response)
            operations = list(response.get("operations", []))
            operations.extend(sorted(_CIVIC_OBSERVATION_OPERATIONS))
            response["operations"] = sorted(set(operations))

        if operation == "actor.chat" and response.get("status") == "ok":
            text = response.get("response")
            if isinstance(text, str):
                response = dict(response)
                scrubbed_text, summary = _scrub_summary(self.scrubber, text)
                response["response"] = scrubbed_text
                response["response_secret_scrub"] = summary

        return sanitize_public_response(response)

    def _handle_civic_observation(
        self,
        request: dict[str, Any],
        request_id: str | None,
    ) -> dict[str, Any]:
        operation = request.get("operation")
        try:
            if operation == "council.proceedings.policy":
                self._require_exact_fields(request, operation, set())
                response: dict[str, Any] = {
                    "status": "ok",
                    "policy": civic_observation_policy_snapshot(self.geometry),
                }
            elif operation == "council.proceedings.view":
                self._require_exact_fields(
                    request,
                    operation,
                    {
                        "session_ref",
                        "source_mode_id",
                        "viewer_id",
                        "viewer_model_id",
                    },
                )
                session_ref = self._require_str(request, "session_ref")
                source_mode_id = self._require_str(request, "source_mode_id")
                viewer_id = request.get("viewer_id")
                viewer_model_id = request.get("viewer_model_id")
                if viewer_id is not None and not isinstance(viewer_id, str):
                    raise ValueError("viewer_id must be a string when supplied")
                if viewer_model_id is not None and not isinstance(viewer_model_id, str):
                    raise ValueError("viewer_model_id must be a string when supplied")
                response = view_council_proceeding(
                    world=self.world,
                    citizenship=self.citizenship,
                    geometry=self.geometry,
                    scrubber=self.scrubber,
                    session_ref=session_ref,
                    source_mode_id=source_mode_id,
                    viewer_id=viewer_id,
                    viewer_model_id=viewer_model_id,
                )
                if response.get("access_tier") == "public_gallery":
                    council = response.get("council")
                    if not isinstance(council, dict):
                        raise CivicObservationError(
                            "council_proceeding_invalid",
                            "committed Council proceeding has an invalid Council summary",
                        )
                    response = dict(response)
                    response["council"] = dict(council)
                    response["council"]["result"] = _public_gallery_result(council.get("result"))
            else:  # pragma: no cover - dispatch set is closed above
                return self._error(request_id, "unknown_operation", "operation is not supported")
        except CivicObservationError as exc:
            return self._error(request_id, exc.code, str(exc))
        except (KeyError, TypeError, ValueError) as exc:
            return self._error(request_id, "invalid_request", str(exc))
        except OSError:
            return self._error(
                request_id,
                "adapter_unavailable",
                "adapter or local storage operation is unavailable",
            )

        if request_id is not None:
            response = {"request_id": request_id, **response}
        return sanitize_public_response(response)

    def _actor(self, item: Any) -> Any:
        actor = super()._actor(item)
        if isinstance(actor, (LocalAIActor, OllamaActor)):
            return _GuardedLocalActor(actor, self.scrubber)
        # Failsafe/civic LocalRoleActor wrappers are created after this hook.
        # They therefore enforce the same exact-credential + secret-shape guard
        # inside LocalRoleActor._generate before generated language can persist.
        return actor


__all__ = [
    "HardenedNexusAPI",
    "guard_model_text",
    "sanitize_public_response",
]
