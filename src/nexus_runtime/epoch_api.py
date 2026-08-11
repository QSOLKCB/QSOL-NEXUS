from __future__ import annotations

from collections import Counter
from typing import Any

from .civilization_api import CivilizationNexusAPI
from .compute_epochs import (
    compute_epoch_policy_snapshot,
    current_compute_epoch,
    pinned_current_compute_epoch,
    small_model_threshold_millions,
)
from .control_plane import RequestBudgetError, validate_control_request
from .epoch_chair import epoch_chair_policy_snapshot
from .genesis_capsule import genesis_capsule_status, reveal_genesis_capsule
from .purgatory import deterministic_exam_selection, purgatory_policy_snapshot
from .trap import TrapError


EPOCH_ADMISSION_RECEIPT_TYPE = "council_epoch_admission_receipt"
EPOCH_ADMISSION_RECEIPT_SCHEMA = "nexus-council-epoch-admission-receipt/1"
EPOCH_RESERVED_OBJECT_TYPES = frozenset({EPOCH_ADMISSION_RECEIPT_TYPE})
_EPOCH_OPERATIONS = frozenset(
    {
        "council.epoch.policy",
        "council.epoch.verify",
        "genesis.capsule.status",
        "genesis.capsule.reveal",
        "security.purgatory.policy",
        "security.purgatory.select",
    }
)


class EpochNexusAPI(CivilizationNexusAPI):
    """Public overlay for Temporal Compute Equality and the Genesis Capsule."""

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        operation = request.get("operation") if isinstance(request, dict) else None
        request_id = request.get("request_id") if isinstance(request, dict) else None

        if operation == "world.create":
            object_type = request.get("object_type")
            if isinstance(object_type, str) and object_type in EPOCH_RESERVED_OBJECT_TYPES:
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
                    "Compute Epoch admission receipts require validated runtime operations",
                )

        if operation == "council.run":
            # Resolve the wall clock exactly once. Provider admission, the
            # returned Chair summary and the durable admission receipt all see
            # this same ContextVar-pinned epoch even if a slow live Council
            # happens to cross an epoch boundary while inference is running.
            with pinned_current_compute_epoch():
                response = super().handle(request)
                if response.get("status") == "ok":
                    return self._attach_epoch_admission_receipt(response)
                return response

        if isinstance(operation, str) and operation in _EPOCH_OPERATIONS:
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
            return self._handle_epoch_operation(request, safe_request_id)

        response = super().handle(request)
        if operation == "system.health" and response.get("status") == "ok":
            response = dict(response)
            response["compute_epoch"] = compute_epoch_policy_snapshot()
            response["genesis_capsule"] = genesis_capsule_status()
            response["purgatory"] = purgatory_policy_snapshot()
        elif operation == "system.operations" and response.get("status") == "ok":
            response = dict(response)
            operations = list(response.get("operations", []))
            operations.extend(sorted(_EPOCH_OPERATIONS))
            response["operations"] = sorted(set(operations))
        return response

    def _attach_epoch_admission_receipt(self, response: dict[str, Any]) -> dict[str, Any]:
        admission = response.get("council_chair")
        session_ref = response.get("session_ref")
        if not isinstance(admission, dict) or not isinstance(session_ref, str):
            return response
        payload = {
            "schema": EPOCH_ADMISSION_RECEIPT_SCHEMA,
            "session_ref": session_ref,
            "admission": admission,
            "replay_rule": "verify_against_recorded_epoch_not_current_wall_clock",
            "authority_rule": "receipt_records_admission_only_and_cannot_change_vote_weight",
        }
        receipt = self._run_real_mutation(
            lambda: self.world.create_object(
                EPOCH_ADMISSION_RECEIPT_TYPE,
                payload,
                {"actor": "nexus"},
            )
        )
        enriched = dict(response)
        enriched["epoch_admission_receipt_ref"] = receipt.object_id
        return enriched

    def _handle_epoch_operation(
        self,
        request: dict[str, Any],
        request_id: str | None,
    ) -> dict[str, Any]:
        operation = request.get("operation")
        try:
            if operation == "council.epoch.policy":
                self._require_exact_fields(request, operation, set())
                response: dict[str, Any] = {
                    "status": "ok",
                    "compute_epoch": compute_epoch_policy_snapshot(),
                    "council_chair": epoch_chair_policy_snapshot(),
                }
            elif operation == "council.epoch.verify":
                self._require_exact_fields(request, operation, {"receipt_ref"})
                response = self._verify_epoch_admission_receipt(
                    self._require_str(request, "receipt_ref")
                )
            elif operation == "genesis.capsule.status":
                self._require_exact_fields(request, operation, set())
                response = {"status": "ok", "capsule": genesis_capsule_status()}
            elif operation == "genesis.capsule.reveal":
                self._require_exact_fields(request, operation, set())
                response = reveal_genesis_capsule()
            elif operation == "security.purgatory.policy":
                self._require_exact_fields(request, operation, set())
                response = {"status": "ok", "policy": purgatory_policy_snapshot()}
            elif operation == "security.purgatory.select":
                self._require_exact_fields(
                    request,
                    operation,
                    {"actor_id", "session_id", "constitution_hash", "count"},
                )
                count = request.get("count", 5)
                response = {
                    "status": "ok",
                    "selection": deterministic_exam_selection(
                        actor_id=self._require_str(request, "actor_id"),
                        session_id=self._require_str(request, "session_id"),
                        epoch=current_compute_epoch(),
                        constitution_hash=self._require_str(request, "constitution_hash"),
                        count=count,
                    ),
                }
            else:  # pragma: no cover - closed dispatch set
                return self._error(request_id, "unknown_operation", "operation is not supported")
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

    def _verify_epoch_admission_receipt(self, receipt_ref: str) -> dict[str, Any]:
        receipt = self.world.inspect(receipt_ref)
        if receipt.object_type != EPOCH_ADMISSION_RECEIPT_TYPE:
            raise ValueError("object is not a Compute Epoch admission receipt")
        payload = receipt.payload
        if payload.get("schema") != EPOCH_ADMISSION_RECEIPT_SCHEMA:
            raise ValueError("Compute Epoch admission receipt schema is unsupported")
        session_ref = payload.get("session_ref")
        admission = payload.get("admission")
        if not isinstance(session_ref, str) or not isinstance(admission, dict):
            raise ValueError("Compute Epoch admission receipt is malformed")

        session = self.world.inspect(session_ref)
        if session.object_type != "council_session":
            raise ValueError("Compute Epoch admission receipt does not reference a council_session")
        epoch_meta = admission.get("compute_epoch")
        seats = admission.get("seats")
        if not isinstance(epoch_meta, dict) or not isinstance(seats, list):
            raise ValueError("Compute Epoch admission receipt lacks epoch or seat data")
        epoch = epoch_meta.get("number")
        if type(epoch) is not int or epoch < 0:
            raise ValueError("recorded Compute Epoch is invalid")
        threshold = small_model_threshold_millions(epoch)
        if epoch_meta.get("effective_small_model_threshold_millions") != threshold:
            raise ValueError("recorded Compute Epoch threshold does not match the pinned policy")

        expected_classes: list[str] = []
        member_ids: list[str] = []
        for seat in seats:
            if not isinstance(seat, dict):
                raise ValueError("recorded Council seat is malformed")
            member_id = seat.get("member_id")
            distribution = seat.get("distribution")
            count = seat.get("parameter_count_millions")
            if not isinstance(member_id, str) or distribution not in {"closed", "open_weight"}:
                raise ValueError("recorded Council seat identity or distribution is invalid")
            if count is not None and (type(count) is not int or count <= 0):
                raise ValueError("recorded Council parameter count is invalid")
            if count is not None and count <= threshold:
                expected_class = "protected_small"
            elif distribution == "open_weight":
                expected_class = "large_open_weight"
            else:
                expected_class = "closed_general"
            if seat.get("slot_class") != expected_class:
                raise ValueError("recorded Council seat class does not match the pinned epoch")
            expected_classes.append(expected_class)
            member_ids.append(member_id)

        counts = Counter(expected_classes)
        if counts["protected_small"] < 1:
            raise ValueError("recorded Council violates the Small-Mind Guarantee")
        if counts["closed_general"] > 2 or counts["large_open_weight"] > 2:
            raise ValueError("recorded Council exceeds constitutional Chair slot limits")
        if admission.get("vote_weight_per_seat") != 1:
            raise ValueError("recorded Council epoch receipt changed vote weight")
        if admission.get("epistemic_privilege_per_seat") != "none":
            raise ValueError("recorded Council epoch receipt changed epistemic privilege")

        session_roster = session.payload.get("roster")
        if not isinstance(session_roster, list):
            raise ValueError("referenced Council session roster is malformed")
        session_member_ids = [
            item.get("member_id") for item in session_roster if isinstance(item, dict)
        ]
        if session_member_ids != member_ids:
            raise ValueError("recorded epoch admission roster does not match the Council session")

        return {
            "status": "verified",
            "receipt_ref": receipt_ref,
            "session_ref": session_ref,
            "compute_epoch": epoch,
            "effective_small_model_threshold_millions": threshold,
            "vote_weight_per_seat": 1,
            "epistemic_privilege_per_seat": "none",
            "replay_clock_used": False,
        }


__all__ = [
    "EPOCH_ADMISSION_RECEIPT_SCHEMA",
    "EPOCH_ADMISSION_RECEIPT_TYPE",
    "EPOCH_RESERVED_OBJECT_TYPES",
    "EpochNexusAPI",
]
