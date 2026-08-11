from __future__ import annotations

from pathlib import Path
import threading
from typing import Any, Sequence

from . import api as _base_api
from .auth.storage import default_auth_root
from .civic_due_process_api import CivicDueProcessNexusAPI
from .compute_epochs import ComputeEpochClockError, current_compute_epoch
from .control_plane import RequestBudgetError, validate_control_request
from .guardian import GuardianError
from .world_continuity import (
    CONTINUITY_RESERVED_OBJECT_TYPES,
    ContinuityWorldStore,
    WorldContinuityError,
    continuity_policy_snapshot,
)


_WORLD_CONTINUITY_OPERATIONS = frozenset(
    {
        "world.continuity.policy",
        "world.continuity.status",
        "world.continuity.scrub",
        "world.continuity.migration.receipt",
        "world.ark.create",
        "world.ark.verify",
        "world.recovery.inspect",
        "world.recovery.restore",
    }
)
_WORLDSTORE_FACTORY_LOCK = threading.RLock()


def _resolved(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def _assert_disjoint(left: str | Path, right: str | Path, left_name: str, right_name: str) -> None:
    a = _resolved(left)
    b = _resolved(right)
    if a == b or a.is_relative_to(b) or b.is_relative_to(a):
        raise WorldContinuityError(
            "world_continuity_storage_overlap",
            f"{left_name} and {right_name} storage roots must be disjoint",
        )


class WorldContinuityNexusAPI(CivicDueProcessNexusAPI):
    """PR #46 overlay: quorum continuity, deterministic scrub and World Arks."""

    def __init__(
        self,
        world_root: str | Path | None = None,
        *,
        world_replica_roots: Sequence[str | Path] = (),
        world_write_quorum: int | None = None,
        guardian_root: str | Path | None = None,
        **kwargs: Any,
    ) -> None:
        replicas = tuple(world_replica_roots)
        if replicas and world_root is None:
            raise WorldContinuityError(
                "world_continuity_requires_primary",
                "replica roots require a persistent primary WorldStore",
            )

        if world_root is not None:
            roots: list[tuple[str, str | Path]] = [("world", world_root)]
            roots.extend((f"world_replica_{index}", root) for index, root in enumerate(replicas, start=1))
            for index, (left_name, left) in enumerate(roots):
                for right_name, right in roots[index + 1 :]:
                    _assert_disjoint(left, right, left_name, right_name)

            auth_broker = kwargs.get("auth_broker")
            auth_root = getattr(auth_broker, "root", None) if auth_broker is not None else kwargs.get("auth_root")
            if auth_root is None:
                auth_root = default_auth_root()
            trap_root = kwargs.get("trap_root")
            stenographer_root = kwargs.get("stenographer_root")
            selected_guardian_root = guardian_root
            if selected_guardian_root is None:
                primary = Path(world_root).absolute()
                selected_guardian_root = primary.with_name(f"{primary.name}-guardian")

            protected: list[tuple[str, str | Path | None]] = [
                ("auth", auth_root),
                ("trap", trap_root),
                ("stenographer", stenographer_root),
                ("guardian", selected_guardian_root),
            ]
            for replica_index, replica_root in enumerate(replicas, start=1):
                for protected_name, protected_root in protected:
                    if protected_root is not None:
                        _assert_disjoint(
                            replica_root,
                            protected_root,
                            f"world_replica_{replica_index}",
                            protected_name,
                        )

        def configured_world_store(root: str | Path | None = None) -> ContinuityWorldStore:
            return ContinuityWorldStore(
                root,
                replica_roots=replicas,
                write_quorum=world_write_quorum,
            )

        # The historical base API constructs its WorldStore internally. Keep
        # that API untouched and replace only its module-local factory while
        # this instance is being built. Construction is serialized so another
        # thread cannot observe the temporary factory.
        with _WORLDSTORE_FACTORY_LOCK:
            previous_factory = _base_api.WorldStore
            _base_api.WorldStore = configured_world_store  # type: ignore[assignment]
            try:
                super().__init__(world_root, guardian_root=guardian_root, **kwargs)
            finally:
                _base_api.WorldStore = previous_factory

        if not isinstance(self.world, ContinuityWorldStore):
            raise WorldContinuityError(
                "world_continuity_initialization_failed",
                "public runtime did not receive the continuity WorldStore",
            )

    def _continuity_error(self, request_id: str | None, exc: WorldContinuityError) -> dict[str, Any]:
        return self._error(request_id, exc.code, str(exc))

    def _record_guardian_storage_scar(self, scrub: dict[str, Any]) -> str | None:
        repair_ref = scrub.get("repair_receipt_ref")
        if not isinstance(repair_ref, str) or self.guardian is None:
            return None
        try:
            record = self.guardian.store.append(
                "substrate_scar",
                {
                    "source": "worldstore_continuity_scrub",
                    "repair_receipt_ref": repair_ref,
                    "continuity_head_ref": scrub.get("head_ref"),
                    "repair_count": scrub.get("repair_count", 0),
                    "verification": "content_addressed_replica_repair_reverified_by_worldstore",
                    "guardian_performed_repair": False,
                    "guardian_storage_authority": False,
                    "authority_effect": "none",
                },
            )
            return record.record_ref
        except GuardianError:
            # Guardian recording remains fail-passive. The continuity repair
            # receipt is authoritative for storage repair regardless of whether
            # the observational scar ledger is available.
            return None

    def _handle_world_continuity_operation(
        self,
        request: dict[str, Any],
        request_id: str | None,
    ) -> dict[str, Any]:
        operation = request.get("operation")
        try:
            if operation == "world.continuity.policy":
                self._require_exact_fields(request, operation, set())
                response: dict[str, Any] = {
                    "status": "ok",
                    "policy": continuity_policy_snapshot(),
                }
            elif operation == "world.continuity.status":
                self._require_exact_fields(request, operation, set())
                response = {"status": "ok", "continuity": self.world.status()}
            elif operation == "world.continuity.scrub":
                self._require_exact_fields(request, operation, {"repair"})
                repair = request.get("repair", False)
                if type(repair) is not bool:
                    raise WorldContinuityError(
                        "world_continuity_invalid_request",
                        "repair must be a boolean",
                    )
                scrub = self.world.scrub(repair=repair)
                guardian_scar_ref = self._record_guardian_storage_scar(scrub) if repair else None
                response = {
                    "status": "ok",
                    "scrub": scrub,
                    "guardian_scar_ref": guardian_scar_ref,
                    "guardian_storage_authority": False,
                }
            elif operation == "world.continuity.migration.receipt":
                self._require_exact_fields(
                    request,
                    operation,
                    {"object_ref", "target_digest_algorithm"},
                )
                object_ref = self._require_str(request, "object_ref")
                algorithm = request.get("target_digest_algorithm", "sha512")
                if not isinstance(algorithm, str):
                    raise WorldContinuityError(
                        "world_continuity_invalid_request",
                        "target_digest_algorithm must be text",
                    )
                receipt = self.world.create_migration_receipt(
                    object_ref,
                    target_digest_algorithm=algorithm,
                )
                response = {
                    "status": "ok",
                    "migration_receipt": receipt.as_dict(),
                    "source_ref_preserved": True,
                }
            elif operation == "world.ark.create":
                self._require_exact_fields(request, operation, {"destination"})
                destination = self._require_str(request, "destination")
                try:
                    epoch = current_compute_epoch()
                except ComputeEpochClockError:
                    epoch = None
                response = self.world.create_ark(destination, compute_epoch=epoch)
            elif operation == "world.ark.verify":
                self._require_exact_fields(request, operation, {"ark_root"})
                response = self.world.verify_ark(self._require_str(request, "ark_root"))
            elif operation == "world.recovery.inspect":
                self._require_exact_fields(request, operation, {"ark_root"})
                response = self.world.inspect_recovery(self._require_str(request, "ark_root"))
            elif operation == "world.recovery.restore":
                self._require_exact_fields(request, operation, {"ark_root", "target_root"})
                response = self.world.restore_ark(
                    self._require_str(request, "ark_root"),
                    self._require_str(request, "target_root"),
                )
            else:  # pragma: no cover - closed dispatch set
                return self._error(request_id, "unknown_operation", "operation is not supported")
        except WorldContinuityError as exc:
            return self._continuity_error(request_id, exc)
        except (KeyError, OSError, TypeError, ValueError, RecursionError) as exc:
            return self._error(request_id, "invalid_request", str(exc))

        if request_id is not None:
            response = {"request_id": request_id, **response}
        return response

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        operation = request.get("operation") if isinstance(request, dict) else None
        request_id = request.get("request_id") if isinstance(request, dict) else None
        safe_request_id = request_id if self._request_id_is_preflight_safe(request_id) else None

        if isinstance(operation, str) and operation in _WORLD_CONTINUITY_OPERATIONS:
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
            return self._handle_world_continuity_operation(request, safe_request_id)

        if operation == "world.create" and isinstance(request, dict):
            object_type = request.get("object_type")
            if isinstance(object_type, str) and object_type in CONTINUITY_RESERVED_OBJECT_TYPES:
                return self._error(
                    safe_request_id,
                    "invalid_request",
                    "reserved continuity objects require validated runtime operations",
                )

        response = super().handle(request)

        if operation == "system.health" and response.get("status") == "ok":
            try:
                continuity = self.world.status()
            except (OSError, ValueError, WorldContinuityError):
                continuity = {
                    "schema_version": "nexus-world-continuity/1",
                    "status": "unavailable",
                    "read_only": True,
                    "authority_effect": "none",
                }
            return {
                **response,
                "world_continuity": {
                    "status": "ok" if continuity.get("status") != "unavailable" else "unavailable",
                    "policy": continuity_policy_snapshot(),
                    "continuity": continuity,
                },
            }

        if operation == "system.operations" and response.get("status") == "ok":
            operations = list(response.get("operations", []))
            operations.extend(sorted(_WORLD_CONTINUITY_OPERATIONS))
            return {**response, "operations": sorted(set(operations))}

        return response


__all__ = ["WorldContinuityNexusAPI"]
