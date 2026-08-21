from __future__ import annotations

from pathlib import Path
from typing import Any

from .control_plane import RequestBudgetError, validate_control_request
from .persistent_world_api import PersistentWorldNexusAPI
from .replay import (
    OperationReplayError,
    OperationReplayService,
    operation_replay_policy_snapshot,
)


_REPLAY_OPERATIONS = frozenset({"receipt.replay"})


class ReplayNexusAPI(PersistentWorldNexusAPI):
    """Post-2.1 replay overlay for explicitly replayable stored receipts."""

    def __init__(self, world_root: str | Path | None = None, **kwargs: Any) -> None:
        super().__init__(world_root, **kwargs)
        self.operation_replay = OperationReplayService(self.world)

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        operation = request.get("operation") if isinstance(request, dict) else None
        request_id = request.get("request_id") if isinstance(request, dict) else None
        safe_request_id = request_id if self._request_id_is_preflight_safe(request_id) else None

        if isinstance(operation, str) and operation in _REPLAY_OPERATIONS:
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
            try:
                self._require_exact_fields(request, operation, {"receipt_ref"})
                response = self.operation_replay.replay_receipt(
                    self._require_str(request, "receipt_ref")
                )
                if safe_request_id is not None:
                    response = {"request_id": safe_request_id, **response}
                return response
            except OperationReplayError as exc:
                return self._error(safe_request_id, exc.code, str(exc))
            except (KeyError, TypeError, ValueError, RecursionError) as exc:
                return self._error(safe_request_id, "invalid_request", str(exc))
            except OSError:
                return self._error(
                    safe_request_id,
                    "replay_unavailable",
                    "operation replay storage is unavailable",
                )

        response = super().handle(request)
        if operation == "system.health" and response.get("status") == "ok":
            return {
                **response,
                "operation_replay": {
                    "status": "ok",
                    "policy": operation_replay_policy_snapshot(),
                },
            }
        if operation == "system.operations" and response.get("status") == "ok":
            operations = set(response.get("operations", []))
            operations.update(_REPLAY_OPERATIONS)
            return {**response, "operations": sorted(operations)}
        return response


__all__ = ["ReplayNexusAPI"]
