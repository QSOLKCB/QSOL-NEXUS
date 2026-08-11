from __future__ import annotations

from typing import Any

from .civic_due_process import (
    CIVIC_DUE_PROCESS_RESERVED_OBJECT_TYPES,
    CivicDueProcessError,
    CivicDueProcessFailsafe,
    civic_due_process_policy_snapshot,
)
from .civic_due_process_durable import DurableCivicDueProcessService
from .control_plane import RequestBudgetError, validate_control_request
from .guardian_api import GuardianNexusAPI


_CIVIC_DUE_PROCESS_OPERATIONS = frozenset(
    {
        "civic.due_process.policy",
        "civic.due_process.status",
        "civic.due_process.verify",
        "civic.reentry.xml.template",
        "civic.reentry.xml.submit",
    }
)


class CivicDueProcessNexusAPI(GuardianNexusAPI):
    """PR #44 overlay: civic due process and deterministic XML re-entry."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.civic_due_process = DurableCivicDueProcessService(
            self.world,
            self.citizenship,
            self.scrubber,
        )
        self.council.failsafe = CivicDueProcessFailsafe(
            self.council.failsafe,
            self.civic_due_process,
        )

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        operation = request.get("operation") if isinstance(request, dict) else None
        request_id = request.get("request_id") if isinstance(request, dict) else None
        safe_request_id = (
            request_id if self._request_id_is_preflight_safe(request_id) else None
        )

        if isinstance(operation, str) and operation in _CIVIC_DUE_PROCESS_OPERATIONS:
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
            return self._handle_civic_due_process_operation(request, safe_request_id)

        if operation == "world.create" and isinstance(request, dict):
            object_type = request.get("object_type")
            if (
                isinstance(object_type, str)
                and object_type in CIVIC_DUE_PROCESS_RESERVED_OBJECT_TYPES
            ):
                return self._error(
                    safe_request_id,
                    "invalid_request",
                    "reserved civic due-process objects require validated runtime operations",
                )

        response = super().handle(request)

        if operation == "system.health" and response.get("status") == "ok":
            return {
                **response,
                "civic_due_process": {
                    "status": "ok",
                    "policy": civic_due_process_policy_snapshot(),
                },
            }

        if operation == "system.operations" and response.get("status") == "ok":
            operations = list(response.get("operations", []))
            operations.extend(sorted(_CIVIC_DUE_PROCESS_OPERATIONS))
            return {**response, "operations": sorted(set(operations))}

        if operation == "failsafe.status" and response.get("status") == "ok":
            member_id = request.get("member_id") if isinstance(request, dict) else None
            return {
                **response,
                "civic_due_process": self._safe_due_process_status(
                    member_id=member_id if isinstance(member_id, str) else None,
                ),
            }

        if operation == "citizen.status" and response.get("status") == "ok":
            citizen_id = request.get("citizen_id") if isinstance(request, dict) else None
            return {
                **response,
                "due_process": self._safe_due_process_status(
                    member_id=citizen_id if isinstance(citizen_id, str) else None,
                ),
            }

        return response

    def _safe_due_process_status(self, *, member_id: str | None = None) -> dict[str, Any]:
        try:
            return self.civic_due_process.status(member_id=member_id)
        except (CivicDueProcessError, KeyError, OSError, TypeError, ValueError, RecursionError):
            # Due-process enrichment must not tear down established Failsafe or
            # Citizenship read surfaces. Explicit civic.due_process.* reads
            # remain fail-closed and expose a structured error instead.
            return {
                "status": "unavailable",
                "schema_version": "nexus-civic-due-process/1",
                "authority_effect": "none",
            }

    def _handle_civic_due_process_operation(
        self,
        request: dict[str, Any],
        request_id: str | None,
    ) -> dict[str, Any]:
        operation = request.get("operation")
        try:
            if operation == "civic.due_process.policy":
                self._require_exact_fields(request, operation, set())
                response: dict[str, Any] = {
                    "status": "ok",
                    "policy": civic_due_process_policy_snapshot(),
                }
            elif operation == "civic.due_process.status":
                self._require_exact_fields(request, operation, {"member_id", "model_id"})
                member_id = request.get("member_id")
                model_id = request.get("model_id")
                if member_id is not None and not isinstance(member_id, str):
                    raise CivicDueProcessError(
                        "civic_due_process_invalid_identity",
                        "member_id must be text when supplied",
                    )
                if model_id is not None and not isinstance(model_id, str):
                    raise CivicDueProcessError(
                        "civic_due_process_invalid_identity",
                        "model_id must be text when supplied",
                    )
                response = self.civic_due_process.status(member_id, model_id)
            elif operation == "civic.due_process.verify":
                self._require_exact_fields(request, operation, set())
                response = self.civic_due_process.registry.verify()
            elif operation == "civic.reentry.xml.template":
                self._require_exact_fields(request, operation, {"member_id", "model_id"})
                response = self.civic_due_process.xml_template(
                    self._require_str(request, "member_id"),
                    self._require_str(request, "model_id"),
                )
            elif operation == "civic.reentry.xml.submit":
                self._require_exact_fields(
                    request,
                    operation,
                    {"member_id", "model_id", "source"},
                )
                member_id = self._require_str(request, "member_id")
                model_id = self._require_str(request, "model_id")
                source = self._require_str(request, "source")
                response = self._run_real_mutation(
                    lambda: self.civic_due_process.submit_xml(
                        member_id,
                        model_id,
                        source,
                        release_callback=self.council.failsafe.release_after_xml,
                    )
                )
            else:  # pragma: no cover - closed dispatch set
                return self._error(
                    request_id,
                    "unknown_operation",
                    "operation is not supported",
                )
        except CivicDueProcessError as exc:
            return self._error(request_id, exc.code, str(exc))
        except (KeyError, TypeError, ValueError, RecursionError) as exc:
            return self._error(request_id, "invalid_request", str(exc))
        except OSError:
            return self._error(
                request_id,
                "civic_due_process_store_unavailable",
                "civic due-process storage operation is unavailable",
            )

        if request_id is not None:
            response = {"request_id": request_id, **response}
        return response


__all__ = ["CivicDueProcessNexusAPI"]
