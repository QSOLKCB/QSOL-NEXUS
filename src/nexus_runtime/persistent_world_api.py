from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapters import AdapterError
from .citizenship import CitizenshipError
from .control_plane import RequestBudgetError, validate_control_request
from .culture import CultureError
from .persistent_world import (
    PERSISTENT_WORLD_RESERVED_OBJECT_TYPES,
    PersistentWorldError,
    PersistentWorldService,
    persistent_world_policy_snapshot,
)
from .progression import ProgressionError
from .replay import (
    OperationReplayError,
    OperationReplayService,
    operation_replay_policy_snapshot,
)
from .trap import TrapError
from .wall import WallError
from .wall_api import WallNexusAPI
from .user_modes import (
    USER_MODE_OBJECT_TYPE,
    UserModeError,
    UserModeService,
    user_mode_contextual,
    user_mode_policy_snapshot,
)
from .world_continuity import WorldContinuityError
from .world_lattice import WorldLatticeError


_PERSISTENT_WORLD_OPERATIONS = frozenset(
    {
        "receipt.replay",
        "world.persistence.policy",
        "world.mode.policy",
        "world.mode.define",
        "world.relation.create",
        "world.relation.search",
        "world.hypothesis.create",
        "world.hypothesis.search",
        "world.experiment.create",
        "world.experiment.search",
        "world.minority.search",
        "world.mode.history",
        "world.export",
        "world.import",
    }
)
_PERSISTENT_WORLD_MUTATIONS = frozenset(
    {
        "world.mode.define",
        "world.relation.create",
        "world.hypothesis.create",
        "world.experiment.create",
        "world.import",
    }
)


class PersistentWorldNexusAPI(WallNexusAPI):
    """Alpha8+ overlay: typed world lineage plus fail-closed operation replay."""

    def __init__(self, world_root: str | Path | None = None, **kwargs: Any) -> None:
        super().__init__(world_root, **kwargs)
        self.persistent_world = PersistentWorldService(self.world, scrubber=self.scrubber)
        self.operation_replay = OperationReplayService(self.world)
        self.user_modes = UserModeService(
            self.world,
            self.geometry,
            scrubber=self.scrubber,
            ordered_refs_provider=self.persistent_world._ordered_refs,
        )

    @staticmethod
    def _optional_text(request: dict[str, Any], field: str) -> str | None:
        value = request.get(field)
        if value is not None and not isinstance(value, str):
            raise PersistentWorldError("world_persistence_invalid", f"{field} must be text when supplied")
        return value

    @staticmethod
    def _optional_limit(request: dict[str, Any], default: int = 20) -> int:
        return request.get("limit", default)

    def _scrub_structure(self, value: Any) -> tuple[Any, dict[str, Any]]:
        clean, events = self._scrub_semantic_value(value)
        return clean, {
            "changed": bool(events),
            "event_count": len(events),
            "secret_types": sorted({event.secret_type for event in events}),
        }

    def _handle_persistent_world_operation(
        self,
        request: dict[str, Any],
        request_id: str | None,
    ) -> dict[str, Any]:
        operation = request.get("operation")
        try:
            if operation == "receipt.replay":
                self._require_exact_fields(request, operation, {"receipt_ref"})
                response: dict[str, Any] = self.operation_replay.replay_receipt(
                    self._require_str(request, "receipt_ref")
                )

            elif operation == "world.persistence.policy":
                self._require_exact_fields(request, operation, set())
                response = {
                    "status": "ok",
                    "policy": persistent_world_policy_snapshot(),
                }

            elif operation == "world.mode.policy":
                self._require_exact_fields(request, operation, set())
                response = {
                    "status": "ok",
                    "policy": user_mode_policy_snapshot(),
                    "defined_user_modes": len(self.user_modes.list_user_modes()),
                }

            elif operation == "world.mode.define":
                self._require_exact_fields(
                    request,
                    operation,
                    {"mode_id", "label", "description", "prompt_instruction", "region_id"},
                )
                response = {
                    "status": "ok",
                    **self._run_real_mutation(
                        lambda: self.user_modes.define_mode(
                            mode_id=self._require_str(request, "mode_id"),
                            label=self._require_str(request, "label"),
                            description=self._require_str(request, "description"),
                            prompt_instruction=self._require_str(request, "prompt_instruction"),
                            region_id=self._require_str(request, "region_id"),
                        )
                    ),
                }

            elif operation == "world.relation.create":
                self._require_exact_fields(
                    request,
                    operation,
                    {"relation_type", "source_ref", "target_ref", "metadata"},
                )
                relation_type = self._require_str(request, "relation_type")
                if self.scrubber.scrub(relation_type).changed:
                    raise PersistentWorldError(
                        "world_relation_invalid",
                        "relation_type must not contain credential-shaped material",
                    )
                metadata, secret_scrub = self._scrub_structure(request.get("metadata", {}))
                relation = self._run_real_mutation(
                    lambda: self.persistent_world.create_relation(
                        relation_type=relation_type,
                        source_ref=self._require_str(request, "source_ref"),
                        target_ref=self._require_str(request, "target_ref"),
                        metadata=metadata,
                    )
                )
                response = {
                    "status": "ok",
                    "relation": relation.as_dict(),
                    "secret_scrub": secret_scrub,
                    "authority_effect": "none",
                }

            elif operation == "world.relation.search":
                self._require_exact_fields(
                    request,
                    operation,
                    {"query", "relation_type", "source_ref", "target_ref", "limit"},
                )
                response = {
                    "status": "ok",
                    **self.persistent_world.search_relations(
                        query=self._optional_text(request, "query"),
                        relation_type=self._optional_text(request, "relation_type"),
                        source_ref=self._optional_text(request, "source_ref"),
                        target_ref=self._optional_text(request, "target_ref"),
                        limit=self._optional_limit(request),
                    ),
                }

            elif operation == "world.hypothesis.create":
                self._require_exact_fields(
                    request,
                    operation,
                    {"statement", "state", "evidence_refs", "previous_hypothesis_ref"},
                )
                statement = self.scrubber.scrub(self._require_str(request, "statement"))
                evidence_refs = request.get("evidence_refs", [])
                if not isinstance(evidence_refs, list):
                    raise PersistentWorldError(
                        "world_hypothesis_invalid",
                        "evidence_refs must be a JSON array",
                    )
                hypothesis = self._run_real_mutation(
                    lambda: self.persistent_world.create_hypothesis(
                        statement=statement.text,
                        state=self._require_str(request, "state"),
                        evidence_refs=evidence_refs,
                        previous_hypothesis_ref=self._optional_text(
                            request,
                            "previous_hypothesis_ref",
                        ),
                    )
                )
                response = {
                    "status": "ok",
                    "hypothesis": hypothesis.as_dict(),
                    "secret_scrub": {"changed": statement.changed},
                    "authority_effect": "none",
                }

            elif operation == "world.hypothesis.search":
                self._require_exact_fields(request, operation, {"query", "state", "limit"})
                response = {
                    "status": "ok",
                    **self.persistent_world.search_hypotheses(
                        query=self._optional_text(request, "query"),
                        state=self._optional_text(request, "state"),
                        limit=self._optional_limit(request),
                    ),
                }

            elif operation == "world.experiment.create":
                self._require_exact_fields(
                    request,
                    operation,
                    {
                        "title",
                        "stage",
                        "method",
                        "hypothesis_refs",
                        "input_refs",
                        "result_refs",
                        "previous_experiment_ref",
                    },
                )
                title = self.scrubber.scrub(self._require_str(request, "title"))
                method = self.scrubber.scrub(self._require_str(request, "method"))
                hypothesis_refs = request.get("hypothesis_refs", [])
                input_refs = request.get("input_refs", [])
                result_refs = request.get("result_refs", [])
                if not all(isinstance(value, list) for value in (hypothesis_refs, input_refs, result_refs)):
                    raise PersistentWorldError(
                        "world_experiment_invalid",
                        "hypothesis_refs, input_refs and result_refs must be JSON arrays",
                    )
                experiment = self._run_real_mutation(
                    lambda: self.persistent_world.create_experiment(
                        title=title.text,
                        stage=self._require_str(request, "stage"),
                        method=method.text,
                        hypothesis_refs=hypothesis_refs,
                        input_refs=input_refs,
                        result_refs=result_refs,
                        previous_experiment_ref=self._optional_text(
                            request,
                            "previous_experiment_ref",
                        ),
                    )
                )
                response = {
                    "status": "ok",
                    "experiment": experiment.as_dict(),
                    "secret_scrub": {
                        "title_changed": title.changed,
                        "method_changed": method.changed,
                    },
                    "authority_effect": "none",
                }

            elif operation == "world.experiment.search":
                self._require_exact_fields(request, operation, {"query", "stage", "limit"})
                response = {
                    "status": "ok",
                    **self.persistent_world.search_experiments(
                        query=self._optional_text(request, "query"),
                        stage=self._optional_text(request, "stage"),
                        limit=self._optional_limit(request),
                    ),
                }

            elif operation == "world.minority.search":
                self._require_exact_fields(
                    request,
                    operation,
                    {"query", "choice", "member_id", "limit"},
                )
                response = {
                    "status": "ok",
                    **self.persistent_world.search_minority_reports(
                        query=self._optional_text(request, "query"),
                        choice=self._optional_text(request, "choice"),
                        member_id=self._optional_text(request, "member_id"),
                        limit=self._optional_limit(request),
                    ),
                }

            elif operation == "world.mode.history":
                self._require_exact_fields(request, operation, {"limit"})
                response = {
                    "status": "ok",
                    **self.persistent_world.mode_history(limit=self._optional_limit(request, 50)),
                }

            elif operation == "world.export":
                self._require_exact_fields(request, operation, {"object_refs"})
                object_refs = request.get("object_refs")
                if object_refs is not None and not isinstance(object_refs, list):
                    raise PersistentWorldError(
                        "world_export_invalid",
                        "object_refs must be a JSON array when supplied",
                    )
                response = {
                    "status": "ok",
                    "bundle": self.persistent_world.export_bundle(object_refs=object_refs),
                    "authority_effect": "none",
                }

            elif operation == "world.import":
                self._require_exact_fields(request, operation, {"bundle"})
                bundle = request.get("bundle")
                if not isinstance(bundle, dict):
                    raise PersistentWorldError(
                        "world_export_invalid",
                        "bundle must be a JSON object",
                    )
                response = self._run_real_mutation(
                    lambda: self.persistent_world.import_bundle(bundle)
                )

            else:  # pragma: no cover
                return self._error(request_id, "unknown_operation", "operation is not supported")

            if request_id is not None:
                response = {"request_id": request_id, **response}
            return response

        except UserModeError as exc:
            return self._error(request_id, exc.code, str(exc))
        except OperationReplayError as exc:
            return self._error(request_id, exc.code, str(exc))
        except PersistentWorldError as exc:
            return self._error(request_id, exc.code, str(exc))
        except WorldLatticeError as exc:
            return self._error(request_id, exc.code, str(exc))
        except WorldContinuityError as exc:
            return self._error(request_id, exc.code, str(exc))
        except WallError as exc:
            return self._error(request_id, exc.code, str(exc))
        except CultureError as exc:
            return self._error(request_id, exc.code, str(exc))
        except ProgressionError as exc:
            return self._error(request_id, exc.code, str(exc))
        except CitizenshipError as exc:
            return self._error(request_id, exc.code, str(exc))
        except AdapterError as exc:
            return self._error(request_id, "adapter_unavailable", str(exc))
        except TrapError as exc:
            return self._error(request_id, exc.code, str(exc))
        except OSError:
            return self._error(
                request_id,
                "world_persistence_unavailable",
                "persistent world storage is unavailable",
            )
        except (KeyError, TypeError, ValueError, RecursionError) as exc:
            return self._error(request_id, "invalid_request", str(exc))

    @user_mode_contextual
    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        operation = request.get("operation") if isinstance(request, dict) else None
        request_id = request.get("request_id") if isinstance(request, dict) else None
        safe_request_id = request_id if self._request_id_is_preflight_safe(request_id) else None

        if isinstance(operation, str) and operation in _PERSISTENT_WORLD_OPERATIONS:
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
            if operation in _PERSISTENT_WORLD_MUTATIONS:
                try:
                    self.trap_mutation_gate.assert_mutation_allowed()
                except TrapError as exc:
                    return self._error(safe_request_id, exc.code, str(exc))
            return self._handle_persistent_world_operation(request, safe_request_id)

        if operation == "world.create" and isinstance(request, dict):
            object_type = request.get("object_type")
            if isinstance(object_type, str) and (
                object_type in PERSISTENT_WORLD_RESERVED_OBJECT_TYPES
                or object_type == USER_MODE_OBJECT_TYPE
            ):
                return self._error(
                    safe_request_id,
                    "invalid_request",
                    "reserved persistent-world objects require validated alpha8 operations",
                )

        response = super().handle(request)

        if operation == "receipt.verify" and response.get("status") in {"verified", "failed"}:
            receipt_ref = request.get("receipt_ref") if isinstance(request, dict) else None
            if isinstance(receipt_ref, str):
                try:
                    definition_ref = self.user_modes.receipt_definition_ref(receipt_ref)
                    if definition_ref is not None:
                        try:
                            self.user_modes.validate_definition_ref(definition_ref)
                        except UserModeError as exc:
                            if exc.code != "user_mode_definition_not_found":
                                return self._error(safe_request_id, exc.code, str(exc))
                            missing = list(response.get("missing_refs", []))
                            if definition_ref not in missing:
                                missing.append(definition_ref)
                            response = {
                                **response,
                                "status": "failed",
                                "missing_refs": missing,
                                "mode_definition_ref": definition_ref,
                            }
                        else:
                            response = {**response, "mode_definition_ref": definition_ref}
                except UserModeError as exc:
                    return self._error(safe_request_id, exc.code, str(exc))

        if operation == "system.health" and response.get("status") == "ok":
            return {
                **response,
                "persistent_world": {
                    "status": "ok",
                    "policy": persistent_world_policy_snapshot(),
                    "authority_effect": "none",
                },
                "operation_replay": {
                    "status": "ok",
                    "policy": operation_replay_policy_snapshot(),
                },
                "user_modes": {
                    "status": "ok",
                    "policy": user_mode_policy_snapshot(),
                    "defined_user_modes": len(self.user_modes.list_user_modes()),
                },
            }
        if operation == "system.operations" and response.get("status") == "ok":
            operations = list(response.get("operations", []))
            operations.extend(sorted(_PERSISTENT_WORLD_OPERATIONS))
            return {**response, "operations": sorted(set(operations))}
        return response


__all__ = ["PersistentWorldNexusAPI"]
