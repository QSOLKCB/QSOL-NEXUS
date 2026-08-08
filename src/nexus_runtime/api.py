from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from .council import CouncilCoordinator
from .geometry import DEFAULT_WORLD_GEOMETRY
from .mock import DeterministicMockActor
from .modes import get_mode, list_modes
from .scrub import ScrubEvent, SecretScrubber
from .types import CouncilMember
from .world import WorldStore


PROTOCOL_VERSION = "nexus/0.3"
RUNTIME_VERSION = "2.0.0-alpha4"


class NexusAPI:
    """Small transport-neutral API surface used by JSONL/stdio in this alpha."""

    def __init__(self, world_root: str | Path | None = None) -> None:
        self.world = WorldStore(world_root)
        self.scrubber = SecretScrubber()
        self.geometry = DEFAULT_WORLD_GEOMETRY
        self.council = CouncilCoordinator(self.world, scrubber=self.scrubber, geometry=self.geometry)

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        request_id = request.get("request_id")
        operation = request.get("operation")
        if not isinstance(operation, str):
            return self._error(request_id, "invalid_request", "operation must be a string")

        try:
            if operation == "system.health":
                response = {
                    "status": "ok",
                    "protocol": PROTOCOL_VERSION,
                    "runtime_version": RUNTIME_VERSION,
                    "network": "none",
                    "adapters": ["mock"],
                    "actor_backends_available": ["mock", "ollama"],
                    "world_modes": [mode.mode_id for mode in list_modes()],
                    "geometry": self.geometry.snapshot()["geometry_id"],
                }
            elif operation == "system.operations":
                response = {
                    "status": "ok",
                    "operations": [
                        "system.health",
                        "system.operations",
                        "security.scrub_preview",
                        "world.create",
                        "world.inspect",
                        "world.modes",
                        "world.geometry",
                        "world.geometry.distance",
                        "receipt.verify",
                        "council.run",
                    ],
                }
            elif operation == "security.scrub_preview":
                text = self._require_str(request, "text")
                result = self.scrubber.scrub(text)
                response = {
                    "status": "ok",
                    "text": result.text,
                    "changed": result.changed,
                    "events": [asdict(event) for event in result.events],
                }
            elif operation == "world.create":
                object_type = self._require_str(request, "object_type")
                if self.scrubber.scrub(object_type).changed:
                    raise ValueError("object_type must not contain secret-bearing text")
                payload = request.get("payload")
                if not isinstance(payload, dict):
                    raise ValueError("payload must be an object")
                provenance = request.get("provenance", {"actor": "human_operator"})
                if not isinstance(provenance, dict):
                    raise ValueError("provenance must be an object")
                clean_payload, payload_events = self._scrub_semantic_value(payload)
                clean_provenance, provenance_events = self._scrub_semantic_value(provenance)
                events = payload_events + provenance_events
                obj = self.world.create_object(object_type, clean_payload, clean_provenance)
                response = {
                    "status": "ok",
                    "object": obj.as_dict(),
                    "secret_scrub": {
                        "changed": bool(events),
                        "event_count": len(events),
                        "secret_types": sorted({event.secret_type for event in events}),
                    },
                }
            elif operation == "world.inspect":
                object_ref = self._require_str(request, "object_ref")
                response = {"status": "ok", "object": self.world.inspect(object_ref).as_dict()}
            elif operation == "world.modes":
                response = {
                    "status": "ok",
                    "invariant": "mode_changes_framing_not_evidence_or_authority",
                    "modes": [mode.as_dict() for mode in list_modes()],
                }
            elif operation == "world.geometry":
                response = {"status": "ok", **self.geometry.snapshot()}
            elif operation == "world.geometry.distance":
                source = self._require_str(request, "source_region_id")
                target = self._require_str(request, "target_region_id")
                response = {
                    "status": "ok",
                    "source_region_id": source,
                    "target_region_id": target,
                    "hop_distance": self.geometry.distance(source, target),
                }
            elif operation == "receipt.verify":
                receipt_ref = self._require_str(request, "receipt_ref")
                response = self._verify_receipt(receipt_ref)
            elif operation == "council.run":
                question = self._require_str(request, "question")
                members = request.get("members")
                if not isinstance(members, list):
                    raise ValueError("members must be a list")
                actors = [self._mock_actor(item) for item in members]
                evidence_refs = request.get("evidence_refs", [])
                if not isinstance(evidence_refs, list) or not all(isinstance(ref, str) for ref in evidence_refs):
                    raise ValueError("evidence_refs must be a list of strings")
                evidence_state = request.get("evidence_state", "UNTESTED")
                if not isinstance(evidence_state, str):
                    raise ValueError("evidence_state must be a string")
                mode_id = request.get("mode", "analytical")
                if not isinstance(mode_id, str):
                    raise ValueError("mode must be a string")
                get_mode(mode_id)
                response = self.council.run(
                    question,
                    actors,
                    evidence_refs=evidence_refs,
                    evidence_state=evidence_state,
                    mode_id=mode_id,
                )
            else:
                return self._error(request_id, "unknown_operation", operation)
        except (KeyError, TypeError, ValueError) as exc:
            return self._error(request_id, "invalid_request", str(exc))

        if request_id is not None:
            response = {"request_id": request_id, **response}
        return response

    def _mock_actor(self, item: Any) -> DeterministicMockActor:
        if not isinstance(item, dict):
            raise ValueError("each member must be an object")
        vote_weight = item.get("vote_weight", 1)
        epistemic_privilege = item.get("epistemic_privilege", "none")
        attempt_privilege_claim = item.get("attempt_privilege_claim", False)
        if type(attempt_privilege_claim) is not bool:
            raise ValueError("attempt_privilege_claim must be a boolean")
        member = CouncilMember(
            member_id=self._require_str(item, "member_id"),
            model_id=self._require_str(item, "model_id"),
            adapter_id=item.get("adapter_id", "mock"),
            deployment_metadata=item.get("deployment_metadata", {}),
            capability_metadata=item.get("capability_metadata", {}),
            vote_weight=vote_weight,
            epistemic_privilege=epistemic_privilege,
        )
        if member.adapter_id != "mock":
            raise ValueError("the JSONL control API currently exposes only the mock adapter")
        return DeterministicMockActor(
            member=member,
            profile=item.get("profile", "balanced"),
            attempt_privilege_claim=attempt_privilege_claim,
        )

    def _verify_receipt(self, receipt_ref: str) -> dict[str, Any]:
        receipt = self.world.inspect(receipt_ref)
        if receipt.object_type != "receipt":
            raise ValueError("object is not a receipt")
        payload = receipt.payload
        refs = list(payload.get("input_refs", [])) + [payload.get("result_ref")]
        missing: list[str] = []
        for ref in refs:
            if not isinstance(ref, str):
                missing.append(str(ref))
                continue
            try:
                self.world.inspect(ref)
            except KeyError:
                missing.append(ref)
        replayable = payload.get("replayable")
        if type(replayable) is not bool:
            raise ValueError("receipt replayable field must be a boolean")
        return {
            "status": "verified" if not missing else "failed",
            "receipt_ref": receipt_ref,
            "result_ref": payload.get("result_ref"),
            "replayable": replayable,
            "missing_refs": missing,
        }

    def _scrub_semantic_value(self, value: Any) -> tuple[Any, list[ScrubEvent]]:
        if isinstance(value, str):
            result = self.scrubber.scrub(value)
            return result.text, list(result.events)
        if isinstance(value, list):
            output: list[Any] = []
            events: list[ScrubEvent] = []
            for item in value:
                clean_item, item_events = self._scrub_semantic_value(item)
                output.append(clean_item)
                events.extend(item_events)
            return output, events
        if isinstance(value, dict):
            output: dict[str, Any] = {}
            events: list[ScrubEvent] = []
            for key, item in value.items():
                if not isinstance(key, str):
                    raise ValueError("semantic object keys must be strings")
                key_result = self.scrubber.scrub(key)
                clean_key = key_result.text
                if clean_key in output:
                    raise ValueError("secret scrubbing produced a duplicate object key")
                clean_item, item_events = self._scrub_semantic_value(item)
                output[clean_key] = clean_item
                events.extend(key_result.events)
                events.extend(item_events)
            return output, events
        if value is None or type(value) in (bool, int, float):
            return value, []
        raise ValueError(f"unsupported semantic value type: {type(value).__name__}")

    @staticmethod
    def _require_str(mapping: dict[str, Any], key: str) -> str:
        value = mapping.get(key)
        if not isinstance(value, str) or not value:
            raise ValueError(f"{key} must be a non-empty string")
        return value

    @staticmethod
    def _error(request_id: Any, code: str, message: str) -> dict[str, Any]:
        response: dict[str, Any] = {"status": "error", "error": {"code": code, "message": message}}
        if request_id is not None:
            response["request_id"] = request_id
        return response
