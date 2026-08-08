from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from .adapters import OllamaActor, OllamaTransport
from .auth import AuthBroker, ensure_disjoint_auth_world_roots
from .council import CouncilCoordinator
from .failsafe import FAILSAFE_SCHEMA_VERSION
from .game_un import GAME_SCHEMA, action_catalog, advance_turn, apply_action, inspect_game, new_game
from .game_mud import (
    MUD_SCHEMA,
    action_catalog as mud_action_catalog,
    apply_action as apply_mud_action,
    inspect_mud,
    new_mud,
    player_view,
)
from .geometry import DEFAULT_WORLD_GEOMETRY
from .mock import DeterministicMockActor
from .modes import get_mode, list_modes
from .scrub import ScrubEvent, SecretScrubber
from .telemetry import TELEMETRY_SCHEMA_VERSION, verify_session_telemetry
from .types import CouncilMember
from .world import WorldStore


PROTOCOL_VERSION = "nexus/0.9"
RUNTIME_VERSION = "2.0.0-alpha6.6"


class NexusAPI:
    """Small transport-neutral API surface used by JSONL/stdio.

    The control transport remains local stdio. Auth profile inspection and
    connection tests are operational state outside the WorldStore. No remote
    provider actor is admitted by this foundation.
    """

    def __init__(
        self,
        world_root: str | Path | None = None,
        *,
        auth_root: str | Path | None = None,
        auth_broker: AuthBroker | None = None,
    ) -> None:
        self.auth = auth_broker or AuthBroker(auth_root)
        if world_root is not None:
            ensure_disjoint_auth_world_roots(self.auth.root, world_root)
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
                    "control_transport": "jsonl_stdio",
                    "network": "none_unless_explicit_loopback_ollama_or_registered_auth_operation",
                    "adapters": ["mock", "ollama_loopback"],
                    "remote_provider_auth": False,
                    "auth_broker": self.auth.status(),
                    "actor_backends_available": ["mock", "ollama"],
                    "world_modes": [mode.mode_id for mode in list_modes()],
                    "geometry": self.geometry.snapshot()["geometry_id"],
                    "telemetry": {"schema_version": TELEMETRY_SCHEMA_VERSION, "role": "observational_only"},
                    "failsafe": self.council.failsafe.policy_dict(),
                    "games": [
                        {"game_id": "un_sim", "schema": GAME_SCHEMA, "room": "#un-sim", "fictional_only": True},
                        {"game_id": "mud", "schema": MUD_SCHEMA, "room": "#mud", "fictional_only": True},
                    ],
                }
            elif operation == "system.operations":
                response = {
                    "status": "ok",
                    "operations": [
                        "system.health",
                        "system.operations",
                        "auth.adapters",
                        "auth.list",
                        "auth.test",
                        "auth.logout",
                        "security.scrub_preview",
                        "world.create",
                        "world.inspect",
                        "world.modes",
                        "world.geometry",
                        "world.geometry.distance",
                        "receipt.verify",
                        "telemetry.verify",
                        "failsafe.status",
                        "game.un.catalog",
                        "game.un.new",
                        "game.un.inspect",
                        "game.un.act",
                        "game.un.turn",
                        "game.mud.catalog",
                        "game.mud.new",
                        "game.mud.inspect",
                        "game.mud.act",
                        "actor.chat",
                        "council.run",
                    ],
                }
            elif operation == "auth.adapters":
                response = self.auth.adapters()
            elif operation == "auth.list":
                response = self.auth.list_profiles()
            elif operation == "auth.test":
                adapter_id = self._require_str(request, "adapter_id")
                profile_name = request.get("profile_name", "default")
                if not isinstance(profile_name, str):
                    raise ValueError("profile_name must be a string")
                response = self.auth.test_profile(adapter_id, profile_name)
            elif operation == "auth.logout":
                adapter_id = self._require_str(request, "adapter_id")
                profile_name = request.get("profile_name", "default")
                if not isinstance(profile_name, str):
                    raise ValueError("profile_name must be a string")
                response = self.auth.logout(adapter_id, profile_name)
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
            elif operation == "telemetry.verify":
                session_ref = self._require_str(request, "session_ref")
                session = self.world.inspect(session_ref)
                if session.object_type != "council_session":
                    raise ValueError("object is not a council_session")
                matches, recomputed = verify_session_telemetry(session.payload)
                response = {
                    "status": "verified" if matches else "failed",
                    "session_ref": session_ref,
                    "matches": matches,
                    "schema_version": TELEMETRY_SCHEMA_VERSION,
                    "recomputed": recomputed,
                }
            elif operation == "failsafe.status":
                member_id = request.get("member_id")
                if member_id is not None and (not isinstance(member_id, str) or not member_id.strip()):
                    raise ValueError("member_id must be non-empty text when supplied")
                response = {
                    "status": "ok",
                    "schema_version": FAILSAFE_SCHEMA_VERSION,
                    **self.council.failsafe.status_snapshot(member_id),
                }
            elif operation == "game.un.catalog":
                response = {
                    "status": "ok",
                    "schema": GAME_SCHEMA,
                    "fictional_only": True,
                    "actions": action_catalog(),
                }
            elif operation == "game.un.new":
                raw_seed = request.get("seed", "trout-council")
                if not isinstance(raw_seed, str) or not raw_seed.strip():
                    raise ValueError("seed must be non-empty text")
                scrubbed = self.scrubber.scrub(raw_seed)
                game = new_game(self.world, scrubbed.text)
                response = {
                    "status": "ok",
                    "game_ref": game.object_id,
                    "game": game.payload,
                    "secret_scrub": {
                        "changed": scrubbed.changed,
                        "events": [asdict(event) for event in scrubbed.events],
                    },
                }
            elif operation == "game.un.inspect":
                game_ref = self._require_str(request, "game_ref")
                game = inspect_game(self.world, game_ref)
                response = {"status": "ok", "game_ref": game.object_id, "game": game.payload}
            elif operation == "game.un.act":
                game_ref = self._require_str(request, "game_ref")
                action = self._require_str(request, "action")
                targets = request.get("targets", [])
                if not isinstance(targets, list) or not all(isinstance(target, str) for target in targets):
                    raise ValueError("targets must be a list of fictional country ids")
                game = apply_action(self.world, game_ref, action, list(targets))
                response = {"status": "ok", "game_ref": game.object_id, "game": game.payload}
            elif operation == "game.un.turn":
                game_ref = self._require_str(request, "game_ref")
                game = advance_turn(self.world, game_ref)
                response = {"status": "ok", "game_ref": game.object_id, "game": game.payload}
            elif operation == "game.mud.catalog":
                response = {
                    "status": "ok",
                    "schema": MUD_SCHEMA,
                    "fictional_only": True,
                    "actions": mud_action_catalog(),
                }
            elif operation == "game.mud.new":
                raw_seed = request.get("seed", "beige-dungeon")
                if not isinstance(raw_seed, str) or not raw_seed.strip():
                    raise ValueError("seed must be non-empty text")
                players = request.get("players", ["operator"])
                if not isinstance(players, list) or not players or not all(isinstance(player, str) for player in players):
                    raise ValueError("players must be a non-empty list of MUD player ids")
                scrubbed = self.scrubber.scrub(raw_seed)
                mud = new_mud(self.world, scrubbed.text, list(players))
                first_player = next(iter(mud.payload["players"]))
                response = {
                    "status": "ok",
                    "mud_ref": mud.object_id,
                    "mud": mud.payload,
                    "player_id": first_player,
                    "view": player_view(mud.payload, first_player),
                    "secret_scrub": {
                        "changed": scrubbed.changed,
                        "events": [asdict(event) for event in scrubbed.events],
                    },
                }
            elif operation == "game.mud.inspect":
                mud_ref = self._require_str(request, "mud_ref")
                mud = inspect_mud(self.world, mud_ref)
                player_id = request.get("player_id")
                if player_id is None:
                    response = {"status": "ok", "mud_ref": mud.object_id, "mud": mud.payload}
                else:
                    if not isinstance(player_id, str) or not player_id:
                        raise ValueError("player_id must be a non-empty string")
                    response = {
                        "status": "ok",
                        "mud_ref": mud.object_id,
                        "mud": mud.payload,
                        "player_id": player_id,
                        "view": player_view(mud.payload, player_id),
                    }
            elif operation == "game.mud.act":
                mud_ref = self._require_str(request, "mud_ref")
                player_id = self._require_str(request, "player_id")
                action = self._require_str(request, "action")
                args = request.get("args", [])
                if not isinstance(args, list) or not all(isinstance(arg, str) and arg for arg in args):
                    raise ValueError("args must be a list of non-empty strings")
                mud = apply_mud_action(self.world, mud_ref, player_id, action, list(args))
                response = {
                    "status": "ok",
                    "mud_ref": mud.object_id,
                    "mud": mud.payload,
                    "player_id": player_id,
                    "view": player_view(mud.payload, player_id),
                }
            elif operation == "actor.chat":
                member_item = request.get("member")
                actor = self._actor(member_item)
                actor, failsafe_replacement = self.council.failsafe.actor_for_run(actor)
                raw_message = self._require_str(request, "message")
                scrubbed = self.scrubber.scrub(raw_message)
                mode_id = request.get("mode", "analytical")
                if not isinstance(mode_id, str):
                    raise ValueError("mode must be a string")
                mode = get_mode(mode_id)
                region = self.geometry.region_for_mode(mode_id)
                evidence_refs = request.get("evidence_refs", [])
                if not isinstance(evidence_refs, list) or not all(isinstance(ref, str) for ref in evidence_refs):
                    raise ValueError("evidence_refs must be a list of strings")
                evidence_context = self.council.build_evidence_context(evidence_refs)
                text = actor.direct_message(
                    scrubbed.text,
                    mode_id=mode.mode_id,
                    mode_instruction=mode.prompt_instruction,
                    geometry_region_id=region.region_id,
                    evidence_context=evidence_context,
                )
                response = {
                    "status": "ok",
                    "non_council": True,
                    "member_id": actor.member.member_id,
                    "model_id": actor.member.model_id,
                    "failsafe_replacement": failsafe_replacement,
                    "mode_id": mode.mode_id,
                    "geometry_region_id": region.region_id,
                    "evidence_refs": list(evidence_refs),
                    "response": text,
                    "secret_scrub": {
                        "changed": scrubbed.changed,
                        "events": [asdict(event) for event in scrubbed.events],
                    },
                }
            elif operation == "council.run":
                question = self._require_str(request, "question")
                members = request.get("members")
                if not isinstance(members, list):
                    raise ValueError("members must be a list")
                actors = [self._actor(item) for item in members]
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
        except OSError as exc:
            return self._error(request_id, "adapter_unavailable", str(exc))

        if request_id is not None:
            response = {"request_id": request_id, **response}
        return response

    def _actor(self, item: Any) -> DeterministicMockActor | OllamaActor:
        if not isinstance(item, dict):
            raise ValueError("each member must be an object")
        adapter_id = item.get("adapter_id", "mock")
        if not isinstance(adapter_id, str):
            raise ValueError("adapter_id must be a string")

        vote_weight = item.get("vote_weight", 1)
        epistemic_privilege = item.get("epistemic_privilege", "none")
        member = CouncilMember(
            member_id=self._require_str(item, "member_id"),
            model_id=self._require_str(item, "model_id"),
            adapter_id=adapter_id,
            deployment_metadata=item.get("deployment_metadata", {}),
            capability_metadata=item.get("capability_metadata", {}),
            vote_weight=vote_weight,
            epistemic_privilege=epistemic_privilege,
        )

        if adapter_id == "mock":
            attempt_privilege_claim = item.get("attempt_privilege_claim", False)
            if type(attempt_privilege_claim) is not bool:
                raise ValueError("attempt_privilege_claim must be a boolean")
            profile = item.get("profile", "balanced")
            if not isinstance(profile, str):
                raise ValueError("mock profile must be a string")
            return DeterministicMockActor(
                member=member,
                profile=profile,
                attempt_privilege_claim=attempt_privilege_claim,
            )

        if adapter_id == "ollama":
            model = item.get("model", member.model_id)
            if not isinstance(model, str) or not model:
                raise ValueError("Ollama member model must be a non-empty string")
            endpoint = item.get("endpoint", "http://127.0.0.1:11434")
            if not isinstance(endpoint, str) or not endpoint:
                raise ValueError("Ollama endpoint must be a non-empty string")
            timeout_seconds = item.get("timeout_seconds", 120)
            if type(timeout_seconds) not in (int, float) or isinstance(timeout_seconds, bool) or timeout_seconds <= 0:
                raise ValueError("Ollama timeout_seconds must be a positive number")
            transport = OllamaTransport(endpoint, timeout_seconds=float(timeout_seconds), allow_remote=False)
            return OllamaActor(
                member=member,
                model=model,
                transport=transport,
                fixture_role="operator_local",
            )

        raise ValueError("adapter_id must be 'mock' or loopback-local 'ollama'")

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
