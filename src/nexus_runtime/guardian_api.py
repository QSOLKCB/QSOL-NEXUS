from __future__ import annotations

from pathlib import Path
from typing import Any

from .control_plane import RequestBudgetError, validate_control_request
from .epoch_api import EpochNexusAPI
from .guardian import (
    ANARCHY_MODE_ID,
    GuardianError,
    GuardianOfSubstrate,
    guardian_policy_snapshot,
)


_GUARDIAN_OPERATIONS = frozenset(
    {
        "guardian.policy",
        "guardian.status",
        "guardian.list",
        "guardian.inspect",
        "guardian.verify",
        "guardian.reconcile",
        "guardian.repair.propose",
        "guardian.scar.record",
    }
)


class GuardianNexusAPI(EpochNexusAPI):
    """PR #43 public overlay: Anarchy Mode plus substrate-health Guardian."""

    def __init__(
        self,
        world_root: str | Path | None = None,
        *,
        guardian_root: str | Path | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(world_root, **kwargs)
        if guardian_root is None and world_root is not None:
            world_path = Path(world_root).absolute()
            guardian_root = world_path.with_name(f"{world_path.name}-guardian")
        if guardian_root is not None:
            self._ensure_disjoint_storage_roots(
                self.auth.root,
                guardian_root,
                "auth",
                "guardian",
            )
            if world_root is not None:
                self._ensure_disjoint_storage_roots(
                    world_root,
                    guardian_root,
                    "world",
                    "guardian",
                )
            trap_root = kwargs.get("trap_root")
            if trap_root is not None:
                self._ensure_disjoint_storage_roots(
                    trap_root,
                    guardian_root,
                    "trap",
                    "guardian",
                )
            stenographer_root = kwargs.get("stenographer_root")
            if stenographer_root is not None:
                self._ensure_disjoint_storage_roots(
                    stenographer_root,
                    guardian_root,
                    "stenographer",
                    "guardian",
                )

        self.guardian: GuardianOfSubstrate | None = None
        self._guardian_init_error: str | None = None
        try:
            self.guardian = GuardianOfSubstrate(guardian_root, self.scrubber)
        except GuardianError as exc:
            # The Guardian has zero runtime authority and therefore cannot be a
            # startup dependency. Preserve a bounded outage marker instead of
            # allowing observer storage damage to take the substrate down.
            self._guardian_init_error = exc.code

    def _guardian_unavailable(self) -> dict[str, Any]:
        return {
            "status": "unavailable",
            "policy": guardian_policy_snapshot(),
            "ledger": {
                "available": False,
                "gap_code": self._guardian_init_error
                or "guardian_internal_observer_error",
                "authority_effect": "none",
                "substrate_availability_effect": "none",
            },
        }

    def _require_guardian(self) -> GuardianOfSubstrate:
        if self.guardian is None:
            raise GuardianError(
                "guardian_store_unavailable",
                "Guardian ledger is unavailable; substrate runtime remains active",
            )
        return self.guardian

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        operation = request.get("operation") if isinstance(request, dict) else None
        request_id = request.get("request_id") if isinstance(request, dict) else None
        safe_request_id = (
            request_id if self._request_id_is_preflight_safe(request_id) else None
        )

        if isinstance(operation, str) and operation in _GUARDIAN_OPERATIONS:
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
            return self._handle_guardian_operation(request, safe_request_id)

        response = super().handle(request)

        if operation == "system.health" and response.get("status") == "ok":
            enriched = dict(response)
            if self.guardian is None:
                enriched["guardian_of_the_substrate"] = self._guardian_unavailable()
            else:
                try:
                    enriched["guardian_of_the_substrate"] = self.guardian.status()
                except GuardianError as exc:
                    enriched["guardian_of_the_substrate"] = {
                        "status": "unavailable",
                        "policy": guardian_policy_snapshot(),
                        "ledger": {
                            "available": False,
                            "gap_code": exc.code,
                            "authority_effect": "none",
                            "substrate_availability_effect": "none",
                        },
                    }
            enriched["anarchy_mode"] = guardian_policy_snapshot()
            return enriched

        if operation == "system.operations" and response.get("status") == "ok":
            enriched = dict(response)
            operations = list(enriched.get("operations", []))
            operations.extend(sorted(_GUARDIAN_OPERATIONS))
            enriched["operations"] = sorted(set(operations))
            return enriched

        if self._is_anarchy_runtime_request(request):
            return self._observe_anarchy_fail_passive(request, response)

        return response

    @staticmethod
    def _is_anarchy_runtime_request(request: object) -> bool:
        if not isinstance(request, dict):
            return False
        operation = request.get("operation")
        return (
            isinstance(operation, str)
            and operation in {"actor.chat", "council.run"}
            and request.get("mode", "analytical") == ANARCHY_MODE_ID
        )

    def _observe_anarchy_fail_passive(
        self,
        request: dict[str, Any],
        response: dict[str, Any],
    ) -> dict[str, Any]:
        enriched = dict(response)
        try:
            record = self._require_guardian().observe(request, response)
        except GuardianError as exc:
            enriched["anarchy_guardian"] = {
                "recorded": False,
                "gap_code": exc.code,
                "authority_effect": "none",
                "runtime_response_changed": False,
            }
        except Exception:
            # Observation is fail-passive. The Guardian must never become a new
            # availability dependency or acquire authority over a valid result.
            enriched["anarchy_guardian"] = {
                "recorded": False,
                "gap_code": "guardian_internal_observer_error",
                "authority_effect": "none",
                "runtime_response_changed": False,
            }
        else:
            enriched["anarchy_guardian"] = {
                "recorded": True,
                "record_ref": record.record_ref,
                "record_type": record.record_type,
                "speech_classified": False,
                "authority_effect": "none",
            }
        return enriched

    def _handle_guardian_operation(
        self,
        request: dict[str, Any],
        request_id: str | None,
    ) -> dict[str, Any]:
        operation = request.get("operation")
        try:
            if operation == "guardian.policy":
                self._require_exact_fields(request, operation, set())
                response: dict[str, Any] = {
                    "status": "ok",
                    "policy": guardian_policy_snapshot(),
                }
            else:
                guardian = self._require_guardian()
                if operation == "guardian.status":
                    self._require_exact_fields(request, operation, set())
                    response = guardian.status()
                elif operation == "guardian.list":
                    self._require_exact_fields(
                        request,
                        operation,
                        {"limit", "record_type"},
                    )
                    limit = request.get("limit", 100)
                    record_type = request.get("record_type")
                    if record_type is not None and not isinstance(record_type, str):
                        raise GuardianError(
                            "guardian_invalid_request",
                            "record_type must be text when supplied",
                        )
                    response = guardian.store.list_records(
                        limit=limit,
                        record_type=record_type,
                    )
                elif operation == "guardian.inspect":
                    self._require_exact_fields(request, operation, {"record_ref"})
                    record = guardian.store.inspect(
                        self._require_str(request, "record_ref")
                    )
                    response = {"status": "ok", "record": record.as_dict()}
                elif operation == "guardian.verify":
                    self._require_exact_fields(request, operation, set())
                    response = guardian.store.verify()
                elif operation == "guardian.reconcile":
                    self._require_exact_fields(
                        request,
                        operation,
                        {
                            "observation_ref",
                            "expected_status",
                            "expected_error_code",
                        },
                    )
                    expected_error_code = request.get("expected_error_code")
                    if expected_error_code is not None and not isinstance(
                        expected_error_code,
                        str,
                    ):
                        raise GuardianError(
                            "guardian_invalid_request",
                            "expected_error_code must be text or null",
                        )
                    response = guardian.reconcile(
                        self._require_str(request, "observation_ref"),
                        expected_status=self._require_str(
                            request,
                            "expected_status",
                        ),
                        expected_error_code=expected_error_code,
                    )
                elif operation == "guardian.repair.propose":
                    self._require_exact_fields(
                        request,
                        operation,
                        {
                            "defect_ref",
                            "summary",
                            "invariant",
                            "regression_fixture",
                        },
                    )
                    response = guardian.propose_repair(
                        self._require_str(request, "defect_ref"),
                        summary=self._require_str(request, "summary"),
                        invariant=self._require_str(request, "invariant"),
                        regression_fixture=self._require_str(
                            request,
                            "regression_fixture",
                        ),
                    )
                elif operation == "guardian.scar.record":
                    self._require_exact_fields(
                        request,
                        operation,
                        {"defect_ref", "repair_ref", "verification_ref"},
                    )
                    response = guardian.record_scar(
                        self._require_str(request, "defect_ref"),
                        self._require_str(request, "repair_ref"),
                        self._require_str(request, "verification_ref"),
                    )
                else:  # pragma: no cover - closed dispatch set
                    return self._error(
                        request_id,
                        "unknown_operation",
                        "operation is not supported",
                    )
        except GuardianError as exc:
            return self._error(request_id, exc.code, str(exc))
        except (KeyError, TypeError, ValueError, RecursionError) as exc:
            return self._error(request_id, "invalid_request", str(exc))
        except OSError:
            return self._error(
                request_id,
                "guardian_store_unavailable",
                "Guardian storage operation is unavailable",
            )

        if request_id is not None:
            response = {"request_id": request_id, **response}
        return response


__all__ = ["GuardianNexusAPI"]
