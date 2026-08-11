from __future__ import annotations

from dataclasses import asdict
import re
from typing import Any

from .action_awareness import (
    ACTION_AWARENESS_RESERVED_OBJECT_TYPES,
    ActionAwarenessError,
    action_awareness_policy_snapshot,
    create_action_expectation,
    reconcile_action_expectation,
)
from .agent_state import (
    AGENT_STATE_RESERVED_OBJECT_TYPES,
    AgentStateError,
    agent_state_policy_snapshot,
    build_agent_context,
    create_agent_state_snapshot,
    publish_agent_state_update,
    verify_agent_context,
)
from .adapters.base import AdapterProtocolError
from .adapters.local_ai import LocalAIActor
from .adapters.ollama import OllamaActor
from .civic_observation import (
    CivicObservationError,
    civic_observation_policy_snapshot,
    view_council_proceeding,
)
from .constitutional_amendment import (
    AMENDMENT_BALLOT_OBJECT_TYPE,
    AMENDMENT_RATIFICATION_OBJECT_TYPE,
    CONSTITUTIONAL_AMENDMENT_RESERVED_OBJECT_TYPES,
    ConstitutionalAmendmentError,
    ConstitutionalAmendmentService,
    constitutional_amendment_policy_snapshot,
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
_ACTION_AWARENESS_OPERATIONS = frozenset(
    {
        "action.awareness.expect_create",
        "action.awareness.policy",
        "action.awareness.reconcile",
    }
)
_AGENT_STATE_OPERATIONS = frozenset(
    {
        "agent.context.build",
        "agent.context.verify",
        "agent.state.policy",
        "agent.state.publish",
        "agent.state.snapshot",
    }
)
_CONSTITUTIONAL_AMENDMENT_OPERATIONS = frozenset(
    {
        "constitution.amendment.admit",
        "constitution.amendment.ballot",
        "constitution.amendment.current",
        "constitution.amendment.deliberation.bind",
        "constitution.amendment.history",
        "constitution.amendment.policy",
        "constitution.amendment.propose",
        "constitution.amendment.verify",
    }
)
_PRIVATE_AMENDMENT_OBJECT_TYPES = frozenset(
    {AMENDMENT_BALLOT_OBJECT_TYPE, AMENDMENT_RATIFICATION_OBJECT_TYPE}
)
_RUNTIME_RESERVED_WORLD_TYPES = (
    frozenset({"council_session"})
    | ACTION_AWARENESS_RESERVED_OBJECT_TYPES
    | AGENT_STATE_RESERVED_OBJECT_TYPES
    | CONSTITUTIONAL_AMENDMENT_RESERVED_OBJECT_TYPES
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

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.constitutional_amendments = ConstitutionalAmendmentService(
            self.world,
            self.citizenship,
            self.geometry,
        )

    def _amendment_ballot_complete(self, ballot_ref: object) -> tuple[bool, int, int]:
        if not isinstance(ballot_ref, str):
            return False, 0, 0
        ballot = self.world.inspect(ballot_ref)
        if ballot.object_type != AMENDMENT_BALLOT_OBJECT_TYPE:
            raise ConstitutionalAmendmentError(
                "amendment_ballot_invalid",
                "amendment ballot reference is invalid",
            )
        eligible = ballot.payload.get("eligible_citizens")
        ballots = ballot.payload.get("ballots")
        if not isinstance(eligible, list) or not isinstance(ballots, dict):
            raise ConstitutionalAmendmentError(
                "amendment_ballot_invalid",
                "amendment ballot state is invalid",
            )
        return len(ballots) == len(eligible) and bool(eligible), len(ballots), len(eligible)

    def _seal_amendment_record(self, item: dict[str, Any], *, full: bool) -> dict[str, Any]:
        result = dict(item)
        ballot_ref = result.get("ballot_ref")
        if ballot_ref is None:
            result["ballot_status"] = "not_started"
            return result
        complete, ballots_cast, eligible_count = self._amendment_ballot_complete(ballot_ref)
        result["ballots_cast"] = ballots_cast
        result["eligible_citizen_count"] = eligible_count
        if complete:
            result["ballot_status"] = "revealed_complete"
            return result
        result["ballot_status"] = "sealed_pending"
        result["tally"] = {}
        result["dissent_count"] = 0
        result.pop("ballots", None)
        result.pop("dissenting_citizen_ids", None)
        result["direct_ballots_visible"] = False
        return result

    def _seal_amendment_history(self, response: dict[str, Any]) -> dict[str, Any]:
        proposals = response.get("proposals")
        if not isinstance(proposals, list):
            raise ConstitutionalAmendmentError(
                "amendment_history_invalid",
                "constitutional amendment history is invalid",
            )
        output = dict(response)
        output["proposals"] = [
            self._seal_amendment_record(item, full=False)
            if isinstance(item, dict)
            else item
            for item in proposals
        ]
        return output

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
            if isinstance(object_type, str) and object_type in _RUNTIME_RESERVED_WORLD_TYPES:
                # Preserve Trap Base precedence for a mutation that would
                # otherwise be rejected by this hardened public boundary.
                try:
                    self.trap_mutation_gate.assert_mutation_allowed()
                except TrapError:
                    return super().handle(request)
                return self._error(
                    safe_request_id,
                    "invalid_request",
                    "runtime-owned world object type requires a validated runtime operation",
                )
        elif operation == "world.inspect":
            object_ref = request.get("object_ref")
            if isinstance(object_ref, str):
                try:
                    inspected = self.world.inspect(object_ref)
                except (KeyError, ValueError):
                    # Preserve the existing Core API's structured invalid/cross-
                    # store reference handling. This preflight only owns valid
                    # world refs that resolve to amendment-private objects.
                    pass
                except OSError:
                    return self._error(
                        safe_request_id,
                        "adapter_unavailable",
                        "adapter or local storage operation is unavailable",
                    )
                else:
                    if inspected.object_type in _PRIVATE_AMENDMENT_OBJECT_TYPES:
                        return self._error(
                            safe_request_id,
                            "civic_private_record",
                            "direct constitutional amendment ballots are available only through the Civic Observation access tiers",
                        )

        # Keep malformed/unhashable operation values inside the established
        # Provider/Core structured-error boundary. Hardened overlays only own
        # their exact string operation names.
        if isinstance(operation, str) and operation in _CIVIC_OBSERVATION_OPERATIONS:
            return self._handle_civic_observation(request, safe_request_id)
        if isinstance(operation, str) and operation in _ACTION_AWARENESS_OPERATIONS:
            return self._handle_action_awareness(request, safe_request_id)
        if isinstance(operation, str) and operation in _AGENT_STATE_OPERATIONS:
            return self._handle_agent_state(request, safe_request_id)
        if isinstance(operation, str) and operation in _CONSTITUTIONAL_AMENDMENT_OPERATIONS:
            return self._handle_constitutional_amendment(request, safe_request_id)

        response = super().handle(request)
        if operation == "system.health" and response.get("status") == "ok":
            try:
                amendment_current = self.constitutional_amendments.current()
                region_policy = self.constitutional_amendments.observation_region_policy()
            except ConstitutionalAmendmentError as exc:
                return self._error(safe_request_id, exc.code, str(exc))
            except OSError:
                return self._error(
                    safe_request_id,
                    "adapter_unavailable",
                    "adapter or local storage operation is unavailable",
                )
            response = dict(response)
            response["control_plane_limits"] = control_plane_policy_snapshot()
            response["civic_observation"] = civic_observation_policy_snapshot(
                self.geometry,
                citizen_region_ids=region_policy["citizen_region_ids"],
                public_gallery_region_ids=region_policy["public_gallery_region_ids"],
            )
            response["action_awareness"] = action_awareness_policy_snapshot()
            response["agent_state"] = agent_state_policy_snapshot()
            response["constitutional_amendments"] = {
                "policy": constitutional_amendment_policy_snapshot(),
                "current": amendment_current,
            }
        elif operation == "system.operations" and response.get("status") == "ok":
            response = dict(response)
            operations = list(response.get("operations", []))
            operations.extend(sorted(_CIVIC_OBSERVATION_OPERATIONS))
            operations.extend(sorted(_ACTION_AWARENESS_OPERATIONS))
            operations.extend(sorted(_AGENT_STATE_OPERATIONS))
            operations.extend(sorted(_CONSTITUTIONAL_AMENDMENT_OPERATIONS))
            response["operations"] = sorted(set(operations))

        if operation == "actor.chat" and response.get("status") == "ok":
            text = response.get("response")
            if isinstance(text, str):
                response = dict(response)
                scrubbed_text, summary = _scrub_summary(self.scrubber, text)
                response["response"] = scrubbed_text
                response["response_secret_scrub"] = summary

        return sanitize_public_response(response)

    def _handle_constitutional_amendment(
        self,
        request: dict[str, Any],
        request_id: str | None,
    ) -> dict[str, Any]:
        operation = request.get("operation")
        try:
            if operation == "constitution.amendment.policy":
                self._require_exact_fields(request, operation, set())
                response: dict[str, Any] = {
                    "status": "ok",
                    "policy": constitutional_amendment_policy_snapshot(),
                }
            elif operation == "constitution.amendment.current":
                self._require_exact_fields(request, operation, set())
                response = self.constitutional_amendments.current()
            elif operation == "constitution.amendment.history":
                self._require_exact_fields(request, operation, set())
                response = self._seal_amendment_history(
                    self.constitutional_amendments.history()
                )
            elif operation == "constitution.amendment.verify":
                self._require_exact_fields(request, operation, {"version_ref"})
                response = self.constitutional_amendments.verify(
                    self._require_str(request, "version_ref")
                )
            elif operation == "constitution.amendment.propose":
                self._require_exact_fields(
                    request,
                    operation,
                    {
                        "proposer_kind",
                        "proposer_id",
                        "proposer_model_id",
                        "admission_ref",
                        "title",
                        "rationale",
                        "changes",
                    },
                )
                proposer_kind = self._require_str(request, "proposer_kind")
                proposer_id = self._require_str(request, "proposer_id")
                proposer_model_id = self._require_str(request, "proposer_model_id")
                for label, value in (
                    ("proposer_kind", proposer_kind),
                    ("proposer_id", proposer_id),
                    ("proposer_model_id", proposer_model_id),
                ):
                    if self.scrubber.scrub(value).changed:
                        raise ValueError(f"{label} must not contain credential-shaped text")
                admission_ref = request.get("admission_ref")
                if admission_ref is not None and (
                    not isinstance(admission_ref, str) or not admission_ref
                ):
                    raise ValueError("admission_ref must be a non-empty string when supplied")
                title_result = self.scrubber.scrub(self._require_str(request, "title"))
                rationale_result = self.scrubber.scrub(self._require_str(request, "rationale"))
                raw_changes = request.get("changes")
                if not isinstance(raw_changes, list):
                    raise ValueError("changes must be a list")
                clean_changes, payload_events = self._scrub_semantic_value(raw_changes)
                response = self._run_real_mutation(
                    lambda: self.constitutional_amendments.propose(
                        proposer_kind=proposer_kind,
                        proposer_id=proposer_id,
                        proposer_model_id=proposer_model_id,
                        admission_ref=admission_ref,
                        title=title_result.text,
                        rationale=rationale_result.text,
                        changes=clean_changes,
                    )
                )
                events = list(title_result.events) + list(rationale_result.events) + payload_events
                response = dict(response)
                response["secret_scrub"] = {
                    "changed": bool(events),
                    "event_count": len(events),
                    "secret_types": sorted({event.secret_type for event in events}),
                }
            elif operation == "constitution.amendment.admit":
                self._require_exact_fields(request, operation, {"proposal_ref"})
                proposal_ref = self._require_str(request, "proposal_ref")
                response = self._run_real_mutation(
                    lambda: self.constitutional_amendments.admit(proposal_ref)
                )
            elif operation == "constitution.amendment.deliberation.bind":
                self._require_exact_fields(
                    request,
                    operation,
                    {"proposal_ref", "admission_ref", "council_session_ref"},
                )
                proposal_ref = self._require_str(request, "proposal_ref")
                admission_ref = self._require_str(request, "admission_ref")
                council_session_ref = self._require_str(request, "council_session_ref")
                response = self._run_real_mutation(
                    lambda: self.constitutional_amendments.bind_deliberation(
                        proposal_ref=proposal_ref,
                        admission_ref=admission_ref,
                        council_session_ref=council_session_ref,
                    )
                )
            elif operation == "constitution.amendment.ballot":
                self._require_exact_fields(
                    request,
                    operation,
                    {"proposal_ref", "deliberation_ref", "citizen_id", "model_id", "choice"},
                )
                proposal_ref = self._require_str(request, "proposal_ref")
                deliberation_ref = self._require_str(request, "deliberation_ref")
                citizen_id = self._require_str(request, "citizen_id")
                model_id = self._require_str(request, "model_id")
                choice = self._require_str(request, "choice")
                for label, value in (("citizen_id", citizen_id), ("model_id", model_id)):
                    if self.scrubber.scrub(value).changed:
                        raise ValueError(f"{label} must not contain credential-shaped text")
                response = self._run_real_mutation(
                    lambda: self.constitutional_amendments.ballot(
                        proposal_ref=proposal_ref,
                        deliberation_ref=deliberation_ref,
                        citizen_id=citizen_id,
                        model_id=model_id,
                        choice=choice,
                    )
                )
                eligible = response.get("eligible_citizens")
                ballots_cast = response.get("ballots_cast")
                eligible_count = len(eligible) if isinstance(eligible, list) else 0
                complete = (
                    type(ballots_cast) is int
                    and eligible_count > 0
                    and ballots_cast == eligible_count
                )
                response = dict(response)
                response["eligible_citizen_count"] = eligible_count
                if complete:
                    response["ballot_status"] = "revealed_complete"
                else:
                    response["ballot_status"] = "sealed_pending"
                    response.pop("tally", None)
                    response.pop("dissenting_citizen_ids", None)
            else:  # pragma: no cover - dispatch set is closed above
                return self._error(request_id, "unknown_operation", "operation is not supported")
        except ConstitutionalAmendmentError as exc:
            return self._error(request_id, exc.code, str(exc))
        except TrapError as exc:
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

    def _handle_agent_state(
        self,
        request: dict[str, Any],
        request_id: str | None,
    ) -> dict[str, Any]:
        operation = request.get("operation")
        try:
            if operation == "agent.state.policy":
                self._require_exact_fields(request, operation, set())
                response: dict[str, Any] = {
                    "status": "ok",
                    "policy": agent_state_policy_snapshot(),
                }
            elif operation == "agent.state.publish":
                self._require_exact_fields(
                    request,
                    operation,
                    {"actor_id", "lane", "content", "source_refs"},
                )
                actor_id = request.get("actor_id")
                lane = request.get("lane")
                raw_content = self._require_str(request, "content")
                source_refs = request.get("source_refs", [])
                scrubbed = self.scrubber.scrub(raw_content)
                update = self._run_real_mutation(
                    lambda: publish_agent_state_update(
                        self.world,
                        actor_id=actor_id,
                        lane=lane,
                        content=scrubbed.text,
                        source_refs=source_refs,
                    )
                )
                response = {
                    "status": "ok",
                    "update_ref": update.object_id,
                    "update": update.payload,
                    "secret_scrub": {
                        "changed": scrubbed.changed,
                        "events": [asdict(event) for event in scrubbed.events],
                    },
                }
            elif operation == "agent.state.snapshot":
                self._require_exact_fields(
                    request,
                    operation,
                    {"actor_id", "update_refs"},
                )
                actor_id = request.get("actor_id")
                update_refs = request.get("update_refs")
                snapshot = self._run_real_mutation(
                    lambda: create_agent_state_snapshot(
                        self.world,
                        actor_id=actor_id,
                        update_refs=update_refs,
                    )
                )
                response = {
                    "status": "ok",
                    "snapshot_ref": snapshot.object_id,
                    "snapshot": snapshot.payload,
                }
            elif operation == "agent.context.build":
                self._require_exact_fields(request, operation, {"snapshot_ref"})
                snapshot_ref = self._require_str(request, "snapshot_ref")
                context = self._run_real_mutation(
                    lambda: build_agent_context(self.world, snapshot_ref=snapshot_ref)
                )
                response = {
                    "status": "ok",
                    "context_ref": context.object_id,
                    "context": context.payload,
                    "use_as_evidence_ref": context.object_id,
                }
            elif operation == "agent.context.verify":
                self._require_exact_fields(request, operation, {"context_ref"})
                context_ref = self._require_str(request, "context_ref")
                response = verify_agent_context(self.world, context_ref=context_ref)
            else:  # pragma: no cover - dispatch set is closed above
                return self._error(request_id, "unknown_operation", "operation is not supported")
        except AgentStateError as exc:
            return self._error(request_id, exc.code, str(exc))
        except TrapError as exc:
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

    def _handle_action_awareness(
        self,
        request: dict[str, Any],
        request_id: str | None,
    ) -> dict[str, Any]:
        operation = request.get("operation")
        try:
            if operation == "action.awareness.policy":
                self._require_exact_fields(request, operation, set())
                response: dict[str, Any] = {
                    "status": "ok",
                    "policy": action_awareness_policy_snapshot(),
                }
            elif operation == "action.awareness.expect_create":
                self._require_exact_fields(
                    request,
                    operation,
                    {"actor_id", "action_label", "object_type", "payload", "provenance"},
                )
                actor_id = self._require_str(request, "actor_id")
                object_type = self._require_str(request, "object_type")
                action_label = self._require_str(request, "action_label")
                if self.scrubber.scrub(actor_id).changed:
                    raise ValueError("actor_id must not contain credential-shaped text")
                if self.scrubber.scrub(object_type).changed:
                    raise ValueError("object_type must not contain credential-shaped text")

                payload = request.get("payload")
                if not isinstance(payload, dict):
                    raise ValueError("payload must be an object")
                provenance = request.get("provenance", {"actor": "human_operator"})
                if not isinstance(provenance, dict):
                    raise ValueError("provenance must be an object")

                label_result = self.scrubber.scrub(action_label)
                clean_payload, payload_events = self._scrub_semantic_value(payload)
                clean_provenance, provenance_events = self._scrub_semantic_value(provenance)
                events = list(label_result.events) + payload_events + provenance_events
                expectation = self._run_real_mutation(
                    lambda: create_action_expectation(
                        self.world,
                        actor_id=actor_id,
                        action_label=label_result.text,
                        object_type=object_type,
                        payload=clean_payload,
                        provenance=clean_provenance,
                    )
                )
                response = {
                    "status": "ok",
                    "expectation_ref": expectation.object_id,
                    "expectation": expectation.payload,
                    "secret_scrub": {
                        "changed": bool(events),
                        "event_count": len(events),
                        "secret_types": sorted({event.secret_type for event in events}),
                    },
                }
            elif operation == "action.awareness.reconcile":
                self._require_exact_fields(
                    request,
                    operation,
                    {"expectation_ref", "observed_object_ref"},
                )
                expectation_ref = self._require_str(request, "expectation_ref")
                observed_object_ref = request.get("observed_object_ref")
                if observed_object_ref is not None and (
                    not isinstance(observed_object_ref, str) or not observed_object_ref
                ):
                    raise ValueError("observed_object_ref must be a non-empty string when supplied")
                reconciliation = self._run_real_mutation(
                    lambda: reconcile_action_expectation(
                        self.world,
                        expectation_ref=expectation_ref,
                        observed_object_ref=observed_object_ref,
                    )
                )
                response = {
                    "status": "ok",
                    "reconciliation_ref": reconciliation.object_id,
                    "reconciliation": reconciliation.payload,
                }
            else:  # pragma: no cover - dispatch set is closed above
                return self._error(request_id, "unknown_operation", "operation is not supported")
        except ActionAwarenessError as exc:
            return self._error(request_id, exc.code, str(exc))
        except TrapError as exc:
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

    def _handle_civic_observation(
        self,
        request: dict[str, Any],
        request_id: str | None,
    ) -> dict[str, Any]:
        operation = request.get("operation")
        try:
            region_policy = self.constitutional_amendments.observation_region_policy()
            if operation == "council.proceedings.policy":
                self._require_exact_fields(request, operation, set())
                response: dict[str, Any] = {
                    "status": "ok",
                    "policy": civic_observation_policy_snapshot(
                        self.geometry,
                        citizen_region_ids=region_policy["citizen_region_ids"],
                        public_gallery_region_ids=region_policy["public_gallery_region_ids"],
                    ),
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
                    citizen_region_ids=region_policy["citizen_region_ids"],
                    public_gallery_region_ids=region_policy["public_gallery_region_ids"],
                )
                amendment_records = self.constitutional_amendments.observation_for_session(
                    session_ref,
                    full=response.get("access_tier") == "citizen_full",
                )
                if amendment_records:
                    full = response.get("access_tier") == "citizen_full"
                    response = dict(response)
                    response["constitutional_amendments"] = [
                        self._seal_amendment_record(item, full=full)
                        for item in amendment_records
                    ]
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
        except ConstitutionalAmendmentError as exc:
            return self._error(request_id, exc.code, str(exc))
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
