from __future__ import annotations

from contextvars import ContextVar
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
from .guardian_observer import GuardianObserver


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
_ANARCHY_COUNCIL_SCOPE: ContextVar[bool] = ContextVar(
    "nexus_anarchy_council_scope",
    default=False,
)


class _AnarchyAwareFailsafe:
    """Delegate Failsafe while suppressing rhetoric-only equality escalation.

    The Equality Guard still records/nudges identity-based authority claims in
    Anarchy Mode, so rhetoric never gains mechanical authority. The only change
    is that repeated rhetoric cannot become durable Failsafe/Shadow-Realm state.
    Other registered procedural triggers remain unchanged.
    """

    def __init__(self, delegate: Any) -> None:
        object.__setattr__(self, "_delegate", delegate)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._delegate, name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "_delegate":
            object.__setattr__(self, name, value)
        else:
            setattr(self._delegate, name, value)

    def trigger_reason(self, events: list[str]) -> str | None:
        reason = self._delegate.trigger_reason(events)
        if (
            _ANARCHY_COUNCIL_SCOPE.get()
            and reason == "repeated_identity_based_authority_claim"
        ):
            return None
        return reason


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
        self.council.failsafe = _AnarchyAwareFailsafe(self.council.failsafe)
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
        self.guardian_observer: GuardianObserver | None = None
        self._guardian_init_error: str | None = None
        try:
            self.guardian = GuardianOfSubstrate(guardian_root, self.scrubber)
            self.guardian_observer = GuardianObserver(self.guardian)
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

    def _guardian_fast_status(self) -> dict[str, Any]:
        if self.guardian is None or self.guardian_observer is None:
            return self._guardian_unavailable()
        return {
            "status": "ok",
            "policy": guardian_policy_snapshot(),
            "ledger": {
                "available": True,
                "persistent": self.guardian.store.root is not None,
                "authority_effect": "none",
                "substrate_availability_effect": "none",
            },
            "observer": self.guardian_observer.status(),
        }

    def _require_guardian(self) -> GuardianOfSubstrate:
        if self.guardian is None:
            raise GuardianError(
                "guardian_store_unavailable",
                "Guardian ledger is unavailable; substrate runtime remains active",
            )
        return self.guardian

    def _drain_guardian_for_read(self) -> None:
        if self.guardian_observer is None:
            self._require_guardian()
            return
        if not self.guardian_observer.wait_for_idle():
            raise GuardianError(
                "guardian_observer_busy",
                "Guardian observations are still pending; retry the explicit read",
            )

    def shutdown_guardian_observer(self, timeout_seconds: float = 1.0) -> bool:
        if self.guardian_observer is None:
            return True
        return self.guardian_observer.shutdown(timeout_seconds)

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

        anarchy_council = (
            operation == "council.run"
            and isinstance(request, dict)
            and request.get("mode", "analytical") == ANARCHY_MODE_ID
        )
        token = _ANARCHY_COUNCIL_SCOPE.set(True) if anarchy_council else None
        try:
            response = super().handle(request)
        finally:
            if token is not None:
                _ANARCHY_COUNCIL_SCOPE.reset(token)

        if operation == "system.health" and response.get("status") == "ok":
            enriched = dict(response)
            # Health must remain a fast snapshot: do not drain or scan the
            # optional Guardian ledger from this ordinary runtime path.
            enriched["guardian_of_the_substrate"] = self._guardian_fast_status()
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
        observer = self.guardian_observer
        if observer is None:
            enriched["anarchy_guardian"] = {
                "accepted": False,
                "persistence": "gap",
                "gap_code": self._guardian_init_error
                or "guardian_store_unavailable",
                "authority_effect": "none",
                "runtime_response_changed": False,
            }
            return enriched
        try:
            accepted = observer.submit(request, response)
        except Exception:
            observer.mark_gap("guardian_internal_observer_error")
            accepted = False
        enriched["anarchy_guardian"] = {
            "accepted": accepted,
            "persistence": "queued" if accepted else "gap",
            "gap_code": None if accepted else "guardian_observer_queue_full",
            "speech_classified": False,
            "authority_effect": "none",
            "runtime_response_changed": False,
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
            elif operation == "guardian.status":
                self._require_exact_fields(request, operation, set())
                self._drain_guardian_for_read()
                guardian = self._require_guardian()
                response = guardian.status()
                if self.guardian_observer is not None:
                    response = {**response, "observer": self.guardian_observer.status()}
            else:
                self._drain_guardian_for_read()
                guardian = self._require_guardian()
                if operation == "guardian.list":
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
