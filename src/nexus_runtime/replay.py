from __future__ import annotations

from typing import Any

from .council import CouncilCoordinator
from .mock import DeterministicMockActor
from .types import CouncilMember, CouncilPolicy, PHASE_ORDER
from .version import PROTOCOL_VERSION
from .world import WorldObject, WorldStore


OPERATION_REPLAY_POLICY_ID = "nexus-operation-replay/1"
OPERATION_REPLAY_RESULT_SCHEMA = "nexus-operation-replay-result/1"


class OperationReplayError(ValueError):
    """Raised when a stored receipt cannot be replayed under the closed policy."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def operation_replay_policy_snapshot() -> dict[str, Any]:
    return {
        "schema": OPERATION_REPLAY_POLICY_ID,
        "admission_rule": "default_deny_per_operation_replay_adapter",
        "registered_operations": ["council.run"],
        "source_world_rule": "read_only_source_replay_executes_in_isolated_in_memory_world",
        "receipt_rule": "receipt_must_be_content_addressed_present_replayable_and_current_protocol",
        "council_rule": "only_reconstructible_deterministic_mock_rosters_without_preexisting_failsafe_state",
        "secret_rule": "scrubbed_original_question_cannot_be_reconstructed_without_retained_raw_secret_and_is_rejected",
        "protocol_rule": "cross_protocol_replay_requires_separately_reviewed_migration_adapter",
        "comparison_rule": "replayed_result_and_replayed_receipt_must_match_original_content_addresses_exactly",
        "authority_effect": "none",
        "evidence_effect": "none",
        "boundaries": [
            "REPLAYABLE != REPLAYED",
            "REPLAY_MATCH != SEMANTIC_TRUTH",
            "DETERMINISTIC != AUTHORITATIVE",
            "REPLAY != EVIDENCE_PROMOTION",
            "SOURCE_WORLD != REPLAY_WORLD",
            "PROTOCOL_MIGRATION != SILENT_REPLAY",
        ],
    }


class OperationReplayService:
    """Replay admitted stored operations without mutating the source world."""

    def __init__(self, source_world: WorldStore) -> None:
        self.source_world = source_world

    @staticmethod
    def _require_object(value: Any, label: str) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise OperationReplayError("replay_invalid", f"{label} must be a JSON object")
        return value

    @staticmethod
    def _require_text(value: Any, label: str) -> str:
        if not isinstance(value, str) or not value:
            raise OperationReplayError("replay_invalid", f"{label} must be non-empty text")
        return value

    @staticmethod
    def _require_text_list(value: Any, label: str) -> list[str]:
        if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
            raise OperationReplayError("replay_invalid", f"{label} must be a list of non-empty strings")
        return list(value)

    def _inspect_source(self, object_ref: str, label: str) -> WorldObject:
        try:
            return self.source_world.inspect(object_ref)
        except KeyError as exc:
            raise OperationReplayError(
                "replay_context_not_reconstructible",
                f"{label} is missing from the source world",
            ) from exc
        except ValueError as exc:
            raise OperationReplayError(
                "replay_invalid",
                f"{label} failed source-world validation",
            ) from exc

    def replay_receipt(self, receipt_ref: str) -> dict[str, Any]:
        receipt = self._inspect_source(receipt_ref, "receipt")
        if receipt.object_type != "receipt":
            raise OperationReplayError("replay_invalid", "object is not a standard NEXUS receipt")
        payload = self._require_object(receipt.payload, "receipt payload")
        operation = self._require_text(payload.get("operation"), "receipt operation")
        replayable = payload.get("replayable")
        if type(replayable) is not bool:
            raise OperationReplayError("replay_invalid", "receipt replayable field must be a boolean")
        if not replayable:
            raise OperationReplayError(
                "replay_not_replayable",
                "receipt explicitly records a non-replayable execution",
            )
        if payload.get("protocol") != PROTOCOL_VERSION:
            raise OperationReplayError(
                "replay_protocol_mismatch",
                "receipt protocol differs from the current runtime; no migration adapter is admitted",
            )
        if operation != "council.run":
            raise OperationReplayError(
                "replay_unsupported_operation",
                f"no generalized replay adapter is admitted for operation: {operation}",
            )
        return self._replay_council(receipt_ref, payload)

    def _copy_isolated_object(self, target: WorldStore, object_ref: str) -> None:
        source = self._inspect_source(object_ref, "referenced replay input")
        copied = target.create_object(source.object_type, source.payload, source.provenance)
        if copied.object_id != object_ref:
            raise OperationReplayError(
                "replay_context_not_reconstructible",
                f"source object identity could not be reconstructed: {object_ref}",
            )

    def _replay_council(self, receipt_ref: str, receipt: dict[str, Any]) -> dict[str, Any]:
        input_refs = self._require_text_list(receipt.get("input_refs"), "receipt input_refs")
        if len(input_refs) != 3:
            raise OperationReplayError(
                "replay_context_not_reconstructible",
                "council receipt includes stateful inputs beyond question/evidence/presence",
            )
        result_ref = self._require_text(receipt.get("result_ref"), "receipt result_ref")
        session = self._inspect_source(result_ref, "council result")
        if session.object_type != "council_session":
            raise OperationReplayError("replay_invalid", "council receipt result is not a council_session")
        session_payload = self._require_object(session.payload, "council session payload")
        if session_payload.get("execution_replayable") is not True:
            raise OperationReplayError(
                "replay_not_replayable",
                "stored Council session does not declare replayable execution",
            )

        question_ref = self._require_text(session_payload.get("question_ref"), "session question_ref")
        evidence_ref = self._require_text(
            session_payload.get("evidence_snapshot_ref"),
            "session evidence_snapshot_ref",
        )
        presence_ref = self._require_text(
            session_payload.get("world_presence_ref"),
            "session world_presence_ref",
        )
        if input_refs != [question_ref, evidence_ref, presence_ref]:
            raise OperationReplayError(
                "replay_invalid",
                "receipt input refs do not exactly bind the Council frozen input refs",
            )

        question = self._inspect_source(question_ref, "Council question")
        if question.object_type != "question":
            raise OperationReplayError("replay_invalid", "Council question ref is not a question object")
        question_payload = self._require_object(question.payload, "question payload")
        if question_payload.get("secret_scrubbed") is not False:
            raise OperationReplayError(
                "replay_context_not_reconstructible",
                "raw secret-bearing question text is intentionally not retained and cannot be replayed",
            )
        if question_payload.get("scrubbed_types") != []:
            raise OperationReplayError(
                "replay_context_not_reconstructible",
                "question scrub metadata is inconsistent with a reconstructible replay",
            )
        question_text = self._require_text(question_payload.get("text"), "question text")

        evidence = self._inspect_source(evidence_ref, "Council evidence snapshot")
        if evidence.object_type != "evidence_snapshot":
            raise OperationReplayError("replay_invalid", "Council evidence ref is not an evidence_snapshot")
        evidence_payload = self._require_object(evidence.payload, "evidence snapshot payload")
        if evidence_payload.get("question_ref") != question_ref:
            raise OperationReplayError("replay_invalid", "evidence snapshot is not bound to the Council question")
        evidence_refs = self._require_text_list(
            evidence_payload.get("included_object_refs"),
            "evidence included_object_refs",
        )
        evidence_state = self._require_text(evidence_payload.get("evidence_state"), "evidence state")

        presence = self._inspect_source(presence_ref, "Council world presence")
        if presence.object_type != "world_presence":
            raise OperationReplayError("replay_invalid", "Council presence ref is not a world_presence object")
        presence_payload = self._require_object(presence.payload, "world presence payload")
        if presence_payload.get("question_ref") != question_ref:
            raise OperationReplayError("replay_invalid", "world presence is not bound to the Council question")

        roster = session_payload.get("roster")
        if not isinstance(roster, list) or not roster:
            raise OperationReplayError("replay_invalid", "Council roster must be a non-empty list")
        actors: list[DeterministicMockActor] = []
        expected_roster_fields = {
            "member_id",
            "adapter_id",
            "model_id",
            "deployment_metadata",
            "capability_metadata",
            "vote_weight",
            "epistemic_privilege",
            "actor_metadata",
            "failsafe_state_ref",
        }
        for index, item in enumerate(roster):
            row = self._require_object(item, f"roster[{index}]")
            if set(row) != expected_roster_fields:
                raise OperationReplayError(
                    "replay_context_not_reconstructible",
                    "Council roster schema is not the admitted deterministic replay shape",
                )
            if row.get("adapter_id") != "mock" or row.get("failsafe_state_ref") is not None:
                raise OperationReplayError(
                    "replay_context_not_reconstructible",
                    "only deterministic mock seats without preexisting failsafe state are replay-admitted",
                )
            actor_metadata = self._require_object(row.get("actor_metadata"), "mock actor metadata")
            if set(actor_metadata) != {
                "actor_kind",
                "mock_profile",
                "mock_attempt_privilege_claim",
            } or actor_metadata.get("actor_kind") != "mock":
                raise OperationReplayError(
                    "replay_context_not_reconstructible",
                    "mock actor metadata is not the admitted replay shape",
                )
            profile = actor_metadata.get("mock_profile")
            if not isinstance(profile, str):
                raise OperationReplayError("replay_invalid", "mock profile must be a string")
            cheat = actor_metadata.get("mock_attempt_privilege_claim")
            if type(cheat) is not bool:
                raise OperationReplayError("replay_invalid", "mock privilege flag must be boolean")
            deployment = self._require_object(row.get("deployment_metadata"), "deployment metadata")
            capability = self._require_object(row.get("capability_metadata"), "capability metadata")
            actors.append(
                DeterministicMockActor(
                    CouncilMember(
                        member_id=self._require_text(row.get("member_id"), "member_id"),
                        model_id=self._require_text(row.get("model_id"), "model_id"),
                        adapter_id="mock",
                        deployment_metadata=deployment,
                        capability_metadata=capability,
                        vote_weight=row.get("vote_weight"),
                        epistemic_privilege=row.get("epistemic_privilege"),
                    ),
                    profile=profile,
                    attempt_privilege_claim=cheat,
                )
            )

        expected_member_ids = [actor.member.member_id for actor in actors]
        if presence_payload.get("member_ids") != expected_member_ids:
            raise OperationReplayError("replay_invalid", "world presence member_ids do not match the Council roster")

        policy_payload = self._require_object(session_payload.get("policy"), "Council policy")
        if policy_payload.get("vote_weight") != 1:
            raise OperationReplayError("replay_invalid", "Council replay requires unit vote weight")
        if policy_payload.get("phase_order") != [phase.value for phase in PHASE_ORDER]:
            raise OperationReplayError("replay_invalid", "Council phase order differs from current protocol")
        policy = CouncilPolicy(
            consensus_numerator=policy_payload.get("consensus_numerator"),
            consensus_denominator=policy_payload.get("consensus_denominator"),
            minimum_members=policy_payload.get("minimum_members"),
            first_pass_blind=policy_payload.get("first_pass_blind"),
            ballot_sealed=policy_payload.get("ballot_sealed"),
        )

        world_mode = self._require_object(session_payload.get("world_mode"), "world_mode")
        mode_id = self._require_text(world_mode.get("mode_id"), "world mode id")
        geometry_region = self._require_object(session_payload.get("geometry_region"), "geometry_region")
        region_id = self._require_text(geometry_region.get("region_id"), "geometry region id")
        if presence_payload.get("mode_id") != mode_id or presence_payload.get("region_id") != region_id:
            raise OperationReplayError("replay_invalid", "world presence mode/region does not match the Council session")

        replay_world = WorldStore()
        for ref in evidence_refs:
            self._copy_isolated_object(replay_world, ref)
        coordinator = CouncilCoordinator(
            replay_world,
            policy=policy,
            max_parallel_workers=1,
        )
        geometry_snapshot = coordinator.geometry.snapshot()
        if (
            presence_payload.get("geometry_id") != geometry_snapshot.get("geometry_id")
            or presence_payload.get("geometry_topology_ref") != geometry_snapshot.get("topology_ref")
        ):
            raise OperationReplayError(
                "replay_protocol_mismatch",
                "stored Council world presence geometry differs from the current replay runtime",
            )
        if session_payload.get("failsafe_policy") != coordinator.failsafe.policy_dict():
            raise OperationReplayError(
                "replay_protocol_mismatch",
                "stored Council failsafe policy differs from the current replay runtime",
            )

        replayed = coordinator.run(
            question_text,
            actors,
            evidence_refs=evidence_refs,
            evidence_state=evidence_state,
            mode_id=mode_id,
        )
        result_matches = replayed.get("session_ref") == result_ref
        receipt_matches = replayed.get("receipt_ref") == receipt_ref
        if not result_matches or not receipt_matches:
            raise OperationReplayError(
                "replay_mismatch",
                "replayed deterministic Council did not reproduce the stored result/receipt identity",
            )

        return {
            "status": "verified",
            "schema": OPERATION_REPLAY_RESULT_SCHEMA,
            "policy": OPERATION_REPLAY_POLICY_ID,
            "operation": "council.run",
            "source_receipt_ref": receipt_ref,
            "source_result_ref": result_ref,
            "replayed_receipt_ref": replayed["receipt_ref"],
            "replayed_result_ref": replayed["session_ref"],
            "result_identity_match": True,
            "receipt_identity_match": True,
            "isolated_replay": True,
            "source_world_write_effect": "none",
            "evidence_effect": "none",
            "authority_effect": "none",
            "claim_boundary": "deterministic protocol replay identity only; not semantic truth or evidence promotion",
        }


__all__ = [
    "OPERATION_REPLAY_POLICY_ID",
    "OPERATION_REPLAY_RESULT_SCHEMA",
    "OperationReplayError",
    "OperationReplayService",
    "operation_replay_policy_snapshot",
]
