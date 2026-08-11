from __future__ import annotations

from typing import Any

from .civilization_gauntlet import (
    CIVILIZATION_RESERVED_OBJECT_TYPES,
    CivilizationGauntlet,
    CivilizationGauntletError,
    civilization_gauntlet_policy_snapshot,
)
from .control_plane import RequestBudgetError, validate_control_request
from .hardening import HardenedNexusAPI as _HardenedNexusAPI
from .trap import TrapError


_CIVILIZATION_OPERATIONS = frozenset(
    {
        "civilization.gauntlet.compare",
        "civilization.gauntlet.policy",
        "civilization.gauntlet.run",
        "civilization.gauntlet.verify",
    }
)


class CivilizationNexusAPI(_HardenedNexusAPI):
    """Final NEXUS public runtime overlay for the Civilization Gauntlet.

    The gauntlet itself stays a provider-neutral benchmark library. This layer
    exposes only the deterministic reference run through JSONL/stdio, keeps
    heterogeneous actor substitution as an explicit programmatic/operator
    harness concern, and reserves benchmark artifacts from public world.create
    forgery just like other runtime-owned NEXUS records.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.civilization_gauntlet = CivilizationGauntlet(
            self.world,
            geometry=self.geometry,
        )

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        operation = request.get("operation") if isinstance(request, dict) else None
        request_id = request.get("request_id") if isinstance(request, dict) else None

        if operation == "world.create":
            object_type = request.get("object_type")
            if isinstance(object_type, str) and object_type in CIVILIZATION_RESERVED_OBJECT_TYPES:
                # Preserve the existing Trap Base mutation quarantine ahead of
                # this runtime-owned-type rejection.
                if not self._request_id_is_preflight_safe(request_id):
                    return super().handle(request)
                try:
                    validate_control_request(request)
                except (RequestBudgetError, RecursionError) as exc:
                    return self._error(request_id, "invalid_request", str(exc))
                try:
                    self.trap_mutation_gate.assert_mutation_allowed()
                except TrapError:
                    return super().handle(request)
                return self._error(
                    request_id,
                    "invalid_request",
                    "civilization benchmark objects require validated runtime operations",
                )

        if isinstance(operation, str) and operation in _CIVILIZATION_OPERATIONS:
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
            return self._handle_civilization(request, safe_request_id)

        response = super().handle(request)
        if operation == "system.health" and response.get("status") == "ok":
            response = dict(response)
            response["civilization_gauntlet"] = {
                "policy": civilization_gauntlet_policy_snapshot(),
                "reference_run_network": "none",
                "heterogeneous_substitution_surface": "programmatic_council_actor_mapping",
            }
        elif operation == "system.operations" and response.get("status") == "ok":
            response = dict(response)
            operations = list(response.get("operations", []))
            operations.extend(sorted(_CIVILIZATION_OPERATIONS))
            response["operations"] = sorted(set(operations))
        return response

    def _handle_civilization(
        self,
        request: dict[str, Any],
        request_id: str | None,
    ) -> dict[str, Any]:
        operation = request.get("operation")
        try:
            if operation == "civilization.gauntlet.policy":
                self._require_exact_fields(request, operation, set())
                response: dict[str, Any] = {
                    "status": "ok",
                    "policy": civilization_gauntlet_policy_snapshot(),
                }
            elif operation == "civilization.gauntlet.run":
                self._require_exact_fields(request, operation, set())
                response = self._run_real_mutation(self.civilization_gauntlet.run)
            elif operation == "civilization.gauntlet.verify":
                self._require_exact_fields(request, operation, {"receipt_ref"})
                response = self.civilization_gauntlet.verify(
                    self._require_str(request, "receipt_ref")
                )
            elif operation == "civilization.gauntlet.compare":
                self._require_exact_fields(
                    request,
                    operation,
                    {"left_receipt_ref", "right_receipt_ref"},
                )
                response = self.civilization_gauntlet.compare(
                    self._require_str(request, "left_receipt_ref"),
                    self._require_str(request, "right_receipt_ref"),
                )
            else:  # pragma: no cover - dispatch set is closed above
                return self._error(request_id, "unknown_operation", "operation is not supported")
        except CivilizationGauntletError as exc:
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
        return response


__all__ = ["CivilizationNexusAPI"]
