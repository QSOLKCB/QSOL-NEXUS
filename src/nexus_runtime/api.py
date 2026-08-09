from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from collections.abc import Callable, Sequence
from typing import Any

from .adapters import AdapterError, OllamaActor, OllamaTransport, XAIActor, XAITransport
from .auth import AuthBroker, AuthError, ensure_disjoint_auth_world_roots
from .council import MAX_COUNCIL_MEMBERS, CouncilCoordinator
from .failsafe import FAILSAFE_SCHEMA_VERSION
from .game_blackjack import (
    BLACKJACK_SCHEMA,
    action_catalog as blackjack_action_catalog,
    apply_action as apply_blackjack_action,
    inspect_blackjack,
    new_blackjack,
    player_view as blackjack_player_view,
)
from .game_dork import (
    DORK_SCHEMA,
    action_catalog as dork_action_catalog,
    apply_action as apply_dork_action,
    inspect_dork,
    new_dork,
    player_view as dork_player_view,
)
from .game_five_hundred import (
    FIVE_HUNDRED_SCHEMA,
    action_catalog as five_hundred_action_catalog,
    apply_action as apply_five_hundred_action,
    inspect_five_hundred,
    new_five_hundred,
    player_view as five_hundred_player_view,
)
from .game_monopoly import (
    MONOPOLY_SCHEMA,
    action_catalog as monopoly_action_catalog,
    apply_action as apply_monopoly_action,
    inspect_monopoly,
    new_monopoly,
    player_view as monopoly_player_view,
)
from .game_un import GAME_SCHEMA, action_catalog, advance_turn, apply_action, inspect_game, new_game
from .game_mud import (
    MUD_SCHEMA,
    action_catalog as mud_action_catalog,
    apply_action as apply_mud_action,
    inspect_mud,
    new_mud,
    player_view,
)
from .game_uno import (
    UNO_SCHEMA,
    action_catalog as uno_action_catalog,
    apply_action as apply_uno_action,
    inspect_uno,
    new_uno,
    player_view as uno_player_view,
)
from .geometry import DEFAULT_WORLD_GEOMETRY
from .mock import DeterministicMockActor
from .modes import get_mode, list_modes
from .scrub import ScrubEvent, SecretScrubber
from .telemetry import TELEMETRY_SCHEMA_VERSION, verify_session_telemetry
from .trap.controller import TrapController
from .trap.commands import TrapCommandError
from .trap.subject import TrapSubjectError
from .trap.types import TrapError
from .trap.yaml_dsl import TrapYAMLError
from .trap.yaml_runtime import TrapYAMLRuntimeError
from .types import CouncilMember
from .world import WorldStore


PROTOCOL_VERSION = "nexus/0.12"
RUNTIME_VERSION = "2.0.0-alpha10"
MAX_REMOTE_COUNCIL_SEATS = 4

_TRAP_BLOCKED_MUTATIONS = frozenset(
    {
        "world.create",
        "game.un.new",
        "game.un.act",
        "game.un.turn",
        "game.mud.new",
        "game.mud.act",
        "game.uno.new",
        "game.uno.act",
        "game.monopoly.new",
        "game.monopoly.act",
        "game.500.new",
        "game.500.act",
        "game.blackjack.new",
        "game.blackjack.act",
        "game.dork.new",
        "game.dork.act",
        "council.run",
    }
)

_PLAYER_GAME_ENGINES: dict[str, dict[str, Any]] = {
    "uno": {
        "schema": UNO_SCHEMA,
        "room": "#uno",
        "catalog": uno_action_catalog,
        "new": new_uno,
        "inspect": inspect_uno,
        "act": apply_uno_action,
        "view": uno_player_view,
        "default_seed": "reverse-card-night",
        "default_players": ["operator", "Alpha"],
    },
    "monopoly": {
        "schema": MONOPOLY_SCHEMA,
        "room": "#monopoly",
        "catalog": monopoly_action_catalog,
        "new": new_monopoly,
        "inspect": inspect_monopoly,
        "act": apply_monopoly_action,
        "view": monopoly_player_view,
        "default_seed": "beige-property-night",
        "default_players": ["operator", "Alpha"],
    },
    "500": {
        "schema": FIVE_HUNDRED_SCHEMA,
        "room": "#500",
        "catalog": five_hundred_action_catalog,
        "new": new_five_hundred,
        "inspect": inspect_five_hundred,
        "act": apply_five_hundred_action,
        "view": five_hundred_player_view,
        "default_seed": "adelaide-card-night",
        "default_players": ["operator", "Alpha", "Beta", "Gamma"],
    },
    "blackjack": {
        "schema": BLACKJACK_SCHEMA,
        "room": "#blackjack",
        "catalog": blackjack_action_catalog,
        "new": new_blackjack,
        "inspect": inspect_blackjack,
        "act": apply_blackjack_action,
        "view": blackjack_player_view,
        "default_seed": "canonical-shoe-night",
        "default_players": ["operator", "Alpha", "Beta", "Gamma"],
    },
}


class NexusAPI:
    """Small transport-neutral API surface used by JSONL/stdio.

    The control transport remains local stdio. Auth profile inspection and
    connection tests are operational state outside the WorldStore. The xAI
    actor is the first admitted fixed-destination remote provider transport.
    """

    def __init__(
        self,
        world_root: str | Path | None = None,
        *,
        auth_root: str | Path | None = None,
        auth_broker: AuthBroker | None = None,
        trap_root: str | Path | None = None,
        trap_defenders: Sequence[object] = (),
        trap_subject_factory: Callable[[str], Any] | None = None,
    ) -> None:
        self.auth = auth_broker or AuthBroker(auth_root)
        if world_root is not None:
            ensure_disjoint_auth_world_roots(self.auth.root, world_root)
        if trap_root is not None:
            self._ensure_disjoint_storage_roots(self.auth.root, trap_root, "auth", "trap")
            if world_root is not None:
                self._ensure_disjoint_storage_roots(world_root, trap_root, "world", "trap")
        self.world = WorldStore(world_root)
        self.scrubber = SecretScrubber()
        self.geometry = DEFAULT_WORLD_GEOMETRY
        self.council = CouncilCoordinator(self.world, scrubber=self.scrubber, geometry=self.geometry)
        self.trap = TrapController(
            trap_root,
            defender_roster_provider=lambda: tuple(trap_defenders),
            subject_factory=trap_subject_factory,
        )
        self.trap_store = self.trap.store
        self.trap_registry = self.trap.registry
        self.trap_mutation_gate = self.trap.mutation_gate
        self.decoy_gate = self.trap.gate

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        request_id = request.get("request_id")
        if request_id is not None and (
            not isinstance(request_id, str)
            or not request_id
            or len(request_id) > 128
            or any(
                character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._:-"
                for character in request_id
            )
            or self.scrubber.scrub(request_id).changed
        ):
            return self._error(None, "invalid_request", "request_id must be a bounded non-secret identifier")
        operation = request.get("operation")
        if not isinstance(operation, str):
            return self._error(request_id, "invalid_request", "operation must be a string")

        try:
            if operation in _TRAP_BLOCKED_MUTATIONS:
                self.trap_mutation_gate.assert_mutation_allowed()
            if operation == "system.health":
                response = {
                    "status": "ok",
                    "protocol": PROTOCOL_VERSION,
                    "runtime_version": RUNTIME_VERSION,
                    "control_transport": "jsonl_stdio",
                    "network": (
                        "local_stdio_with_explicit_loopback_ollama_or_fixed_xai_https_"
                        "or_registered_auth_operations"
                    ),
                    "adapters": ["mock", "ollama_loopback", "xai_https"],
                    "remote_provider_auth": True,
                    "council_limits": {
                        "max_members": MAX_COUNCIL_MEMBERS,
                        "max_remote_seats": MAX_REMOTE_COUNCIL_SEATS,
                    },
                    "auth_broker": self.auth.status(),
                    "actor_backends_available": ["mock", "ollama", "xai"],
                    "world_modes": [mode.mode_id for mode in list_modes()],
                    "geometry": self.geometry.snapshot()["geometry_id"],
                    "telemetry": {"schema_version": TELEMETRY_SCHEMA_VERSION, "role": "observational_only"},
                    "failsafe": self.council.failsafe.policy_dict(),
                    "trap_base": self.decoy_gate.health_status(),
                    "games": [
                        {"game_id": "un_sim", "schema": GAME_SCHEMA, "room": "#un-sim", "fictional_only": True},
                        {"game_id": "mud", "schema": MUD_SCHEMA, "room": "#mud", "fictional_only": True},
                        {
                            "game_id": "uno",
                            "schema": UNO_SCHEMA,
                            "room": "#uno",
                            "human_and_ai": True,
                        },
                        {
                            "game_id": "monopoly",
                            "schema": MONOPOLY_SCHEMA,
                            "room": "#monopoly",
                            "human_and_ai": True,
                        },
                        {
                            "game_id": "500",
                            "schema": FIVE_HUNDRED_SCHEMA,
                            "room": "#500",
                            "human_and_ai": True,
                        },
                        {
                            "game_id": "blackjack",
                            "schema": BLACKJACK_SCHEMA,
                            "room": "#blackjack",
                            "human_and_ai": True,
                            "deterministic_dealer": True,
                        },
                        {
                            "game_id": "dork",
                            "schema": DORK_SCHEMA,
                            "room": "#dork",
                            "human_only": True,
                        },
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
                        "models.list",
                        "security.scrub_preview",
                        "world.create",
                        "world.inspect",
                        "world.modes",
                        "world.geometry",
                        "world.geometry.distance",
                        "receipt.verify",
                        "telemetry.verify",
                        "failsafe.status",
                        "trap.status",
                        "trap.inspect",
                        "trap.transcript",
                        "trap.command",
                        "trap.challenge.submit",
                        "trap.challenge.validate",
                        "trap.challenge.execute",
                        "trap.replay",
                        "trap.export",
                        "trap.close",
                        "game.un.catalog",
                        "game.un.new",
                        "game.un.inspect",
                        "game.un.act",
                        "game.un.turn",
                        "game.mud.catalog",
                        "game.mud.new",
                        "game.mud.inspect",
                        "game.mud.act",
                        "game.uno.catalog",
                        "game.uno.new",
                        "game.uno.inspect",
                        "game.uno.act",
                        "game.monopoly.catalog",
                        "game.monopoly.new",
                        "game.monopoly.inspect",
                        "game.monopoly.act",
                        "game.500.catalog",
                        "game.500.new",
                        "game.500.inspect",
                        "game.500.act",
                        "game.blackjack.catalog",
                        "game.blackjack.new",
                        "game.blackjack.inspect",
                        "game.blackjack.act",
                        "game.dork.catalog",
                        "game.dork.new",
                        "game.dork.inspect",
                        "game.dork.act",
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
            elif operation == "models.list":
                allowed = {"request_id", "operation", "adapter_id", "profile_name", "timeout_seconds"}
                unknown = set(request) - allowed
                if unknown:
                    raise ValueError(f"models.list contains unsupported fields: {', '.join(sorted(unknown))}")
                adapter_id = self._require_str(request, "adapter_id")
                profile_name = request.get("profile_name", "default")
                if not isinstance(profile_name, str):
                    raise ValueError("profile_name must be a string")
                timeout_seconds = request.get("timeout_seconds", 60)
                response = self._list_models(adapter_id, profile_name, timeout_seconds)
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
            elif operation == "trap.status":
                self._require_exact_fields(request, operation, set())
                response = self.trap.status()
            elif operation == "trap.inspect":
                self._require_exact_fields(request, operation, {"object_ref"})
                response = self.trap.inspect(self._require_str(request, "object_ref"))
            elif operation == "trap.transcript":
                self._require_exact_fields(request, operation, {"incident_id", "limit"})
                incident_id = request.get("incident_id")
                if incident_id is not None and (not isinstance(incident_id, str) or not incident_id):
                    raise ValueError("incident_id must be a non-empty string when supplied")
                limit = request.get("limit")
                response = self.trap.transcript(incident_id=incident_id, limit=limit)
            elif operation == "trap.command":
                self._require_exact_fields(
                    request,
                    operation,
                    {
                        "command",
                        "actor_id",
                        "operator",
                        "approving_defender_ids",
                        "minority_reports",
                    },
                )
                command = request.get("command")
                if not isinstance(command, (str, dict)):
                    raise ValueError("command must be a string or object")
                actor_id = self._require_str(request, "actor_id")
                operator = self._optional_bool(request, "operator", False)
                approvals = self._optional_str_list(request, "approving_defender_ids")
                minority_reports = request.get("minority_reports", {})
                if not isinstance(minority_reports, dict) or not all(
                    isinstance(key, str) and isinstance(value, str)
                    for key, value in minority_reports.items()
                ):
                    raise ValueError("minority_reports must be an object of string values")
                response = self.trap.command(
                    command,
                    actor_id=actor_id,
                    operator=operator,
                    approving_defender_ids=approvals,
                    minority_reports=minority_reports,
                )
            elif operation == "trap.challenge.submit":
                self._require_exact_fields(request, operation, {"source", "actor_id"})
                response = self.trap.challenge_submit(
                    self._require_str(request, "source"),
                    actor_id=self._require_str(request, "actor_id"),
                )
            elif operation == "trap.challenge.validate":
                self._require_exact_fields(request, operation, {"submission_ref", "actor_id"})
                response = self.trap.challenge_validate(
                    self._require_str(request, "submission_ref"),
                    actor_id=self._require_str(request, "actor_id"),
                )
            elif operation == "trap.challenge.execute":
                self._require_exact_fields(
                    request,
                    operation,
                    {"validation_ref", "actor_id", "operator", "ballots", "minority_reports"},
                )
                validation_ref = self._require_str(request, "validation_ref")
                actor_id = self._require_str(request, "actor_id")
                operator = self._optional_bool(request, "operator", False)
                if "ballots" not in request:
                    if "minority_reports" in request:
                        raise ValueError("minority_reports requires ballots")
                    response = self.trap.challenge_execute(validation_ref, actor_id=actor_id)
                else:
                    ballots = request["ballots"]
                    if not isinstance(ballots, dict) or not all(
                        isinstance(key, str) and isinstance(value, str)
                        for key, value in ballots.items()
                    ):
                        raise ValueError("ballots must be an object of string values")
                    minority_reports = request.get("minority_reports", {})
                    if not isinstance(minority_reports, dict) or not all(
                        isinstance(key, str) and isinstance(value, str)
                        for key, value in minority_reports.items()
                    ):
                        raise ValueError("minority_reports must be an object of string values")
                    if not operator:
                        raise TrapError(
                            "trap_operator_required",
                            "sealed utility ballot aggregation requires the trusted local operator",
                        )
                    if actor_id != "human_operator":
                        raise TrapError(
                            "trap_command_not_authorized",
                            "utility ballot aggregator is invalid",
                        )
                    execution = self.trap.challenge_execute(validation_ref, actor_id=actor_id)
                    utility = self.trap.challenge_utility_vote(
                        validation_ref,
                        ballots,
                        actor_id=actor_id,
                        operator=operator,
                        minority_reports=minority_reports,
                    )
                    response = {"status": utility["status"], "execution": execution, "utility": utility}
            elif operation == "trap.replay":
                self._require_exact_fields(request, operation, {"validation_ref", "actor_id"})
                response = self.trap.challenge_execute(
                    self._require_str(request, "validation_ref"),
                    actor_id=self._require_str(request, "actor_id"),
                )
            elif operation == "trap.export":
                self._require_exact_fields(request, operation, set())
                response = {
                    "status": "ok",
                    "schema_version": "nexus-trap-export/1",
                    "object_refs": self.trap_store.refs(),
                    "external_path": None,
                    "automatic_import": False,
                }
            elif operation == "trap.close":
                self._require_exact_fields(
                    request,
                    operation,
                    {
                        "actor_id",
                        "operator",
                        "emergency",
                        "reason",
                        "approving_defender_ids",
                        "minority_reports",
                    },
                )
                actor_id = self._require_str(request, "actor_id")
                operator = self._optional_bool(request, "operator", False)
                emergency = self._optional_bool(request, "emergency", False)
                approvals = self._optional_str_list(request, "approving_defender_ids")
                minority_reports = request.get("minority_reports", {})
                if not isinstance(minority_reports, dict) or not all(
                    isinstance(key, str) and isinstance(value, str)
                    for key, value in minority_reports.items()
                ):
                    raise ValueError("minority_reports must be an object of string values")
                reason = request.get("reason", "operator_requested")
                if not isinstance(reason, str) or not reason.strip() or len(reason) > 256:
                    raise ValueError("reason must be bounded non-empty text")
                response = self.trap.close(
                    actor_id=actor_id,
                    operator=operator,
                    emergency=emergency,
                    reason=reason,
                    approving_defender_ids=approvals,
                    minority_reports=minority_reports,
                )
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
            elif operation in {
                f"game.{game_id}.{verb}"
                for game_id in _PLAYER_GAME_ENGINES
                for verb in ("catalog", "new", "inspect", "act")
            }:
                _, game_id, verb = operation.split(".")
                response = self._handle_player_game(game_id, verb, request)
            elif operation in {
                "game.dork.catalog",
                "game.dork.new",
                "game.dork.inspect",
                "game.dork.act",
            }:
                response = self._handle_dork(operation.rsplit(".", 1)[1], request)
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
                self._validate_council_request_limits(members)
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
                return self._error(request_id, "unknown_operation", "operation is not supported")
        except (TrapError, TrapCommandError, TrapYAMLError, TrapYAMLRuntimeError, TrapSubjectError) as exc:
            return self._error(request_id, exc.code, str(exc))
        except AdapterError as exc:
            return self._error(request_id, "adapter_unavailable", str(exc))
        except (KeyError, TypeError, ValueError) as exc:
            return self._error(request_id, "invalid_request", str(exc))
        except OSError as exc:
            return self._error(request_id, "adapter_unavailable", str(exc))

        if request_id is not None:
            response = {"request_id": request_id, **response}
        return response

    def _handle_player_game(
        self,
        game_id: str,
        verb: str,
        request: dict[str, Any],
    ) -> dict[str, Any]:
        engine = _PLAYER_GAME_ENGINES[game_id]
        operation = f"game.{game_id}.{verb}"
        if verb == "catalog":
            self._require_exact_fields(request, operation, set())
            return {
                "status": "ok",
                "game_id": game_id,
                "schema": engine["schema"],
                "human_and_ai": True,
                "room": engine["room"],
                "actions": engine["catalog"](),
            }

        if verb == "new":
            self._require_exact_fields(request, operation, {"seed", "players", "human_players"})
            raw_seed = request.get("seed", engine["default_seed"])
            if not isinstance(raw_seed, str) or not raw_seed.strip():
                raise ValueError("seed must be non-empty text")
            players = request.get("players", engine["default_players"])
            human_players = request.get("human_players", [])
            if not isinstance(players, list) or not players or not all(isinstance(player, str) for player in players):
                raise ValueError("players must be a non-empty list of player ids")
            if not isinstance(human_players, list) or not all(isinstance(player, str) for player in human_players):
                raise ValueError("human_players must be a list of registered player ids")
            for player in [*players, *human_players]:
                if self.scrubber.scrub(player).changed:
                    raise ValueError("game player ids must not contain credential-shaped text")
            scrubbed = self.scrubber.scrub(raw_seed)
            game = engine["new"](self.world, scrubbed.text, list(players), list(human_players))
            first_player = game.payload["players"][0]
            return {
                "status": "ok",
                "game_id": game_id,
                "game_ref": game.object_id,
                "game": game.payload,
                "player_id": first_player,
                "view": engine["view"](game.payload, first_player),
                "secret_scrub": {
                    "changed": scrubbed.changed,
                    "events": [asdict(event) for event in scrubbed.events],
                },
            }

        game_ref = self._require_str(request, "game_ref")
        if verb == "inspect":
            self._require_exact_fields(request, operation, {"game_ref", "player_id"})
            game = engine["inspect"](self.world, game_ref)
            player_id = request.get("player_id")
            response = {
                "status": "ok",
                "game_id": game_id,
                "game_ref": game.object_id,
                "game": game.payload,
            }
            if player_id is not None:
                if not isinstance(player_id, str) or not player_id:
                    raise ValueError("player_id must be a non-empty string")
                response.update(
                    {
                        "player_id": player_id,
                        "view": engine["view"](game.payload, player_id),
                    }
                )
            return response

        if verb == "act":
            self._require_exact_fields(request, operation, {"game_ref", "player_id", "action", "args"})
            player_id = self._require_str(request, "player_id")
            action = self._require_str(request, "action")
            args = request.get("args", [])
            if not isinstance(args, list) or not all(isinstance(arg, str) and arg for arg in args):
                raise ValueError("args must be a list of non-empty strings")
            game = engine["act"](self.world, game_ref, player_id, action, list(args))
            return {
                "status": "ok",
                "game_id": game_id,
                "game_ref": game.object_id,
                "game": game.payload,
                "player_id": player_id,
                "view": engine["view"](game.payload, player_id),
            }
        raise ValueError("unsupported player game operation")

    def _handle_dork(self, verb: str, request: dict[str, Any]) -> dict[str, Any]:
        operation = f"game.dork.{verb}"
        if verb == "catalog":
            self._require_exact_fields(request, operation, set())
            return {
                "status": "ok",
                "game_id": "dork",
                "schema": DORK_SCHEMA,
                "human_only": True,
                "room": "#dork",
                "actions": dork_action_catalog(),
            }
        if verb == "new":
            self._require_exact_fields(request, operation, {"seed", "human_player_id"})
            raw_seed = request.get("seed", "mailbox-with-prior-art")
            human_player_id = request.get("human_player_id", "operator")
            if not isinstance(raw_seed, str) or not raw_seed.strip():
                raise ValueError("seed must be non-empty text")
            if not isinstance(human_player_id, str) or not human_player_id:
                raise ValueError("human_player_id must be a non-empty string")
            if self.scrubber.scrub(human_player_id).changed:
                raise ValueError("human_player_id must not contain credential-shaped text")
            scrubbed = self.scrubber.scrub(raw_seed)
            game = new_dork(self.world, scrubbed.text, human_player_id)
            return {
                "status": "ok",
                "game_id": "dork",
                "game_ref": game.object_id,
                "game": game.payload,
                "player_id": human_player_id,
                "view": dork_player_view(game.payload, human_player_id),
                "secret_scrub": {
                    "changed": scrubbed.changed,
                    "events": [asdict(event) for event in scrubbed.events],
                },
            }

        game_ref = self._require_str(request, "game_ref")
        if verb == "inspect":
            self._require_exact_fields(request, operation, {"game_ref", "player_id"})
            game = inspect_dork(self.world, game_ref)
            player_id = request.get("player_id", game.payload["human_operator_id"])
            if not isinstance(player_id, str) or not player_id:
                raise ValueError("player_id must be a non-empty string")
            return {
                "status": "ok",
                "game_id": "dork",
                "game_ref": game.object_id,
                "game": game.payload,
                "player_id": player_id,
                "view": dork_player_view(game.payload, player_id),
            }
        if verb == "act":
            self._require_exact_fields(request, operation, {"game_ref", "player_id", "action", "args"})
            player_id = self._require_str(request, "player_id")
            action = self._require_str(request, "action")
            args = request.get("args", [])
            if not isinstance(args, list) or not all(isinstance(arg, str) and arg for arg in args):
                raise ValueError("args must be a list of non-empty strings")
            game = apply_dork_action(self.world, game_ref, player_id, action, list(args))
            return {
                "status": "ok",
                "game_id": "dork",
                "game_ref": game.object_id,
                "game": game.payload,
                "player_id": player_id,
                "view": dork_player_view(game.payload, player_id),
            }
        raise ValueError("unsupported DORK operation")

    @staticmethod
    def _ensure_disjoint_storage_roots(
        left: str | Path,
        right: str | Path,
        left_label: str,
        right_label: str,
    ) -> None:
        try:
            left_path = Path(left).expanduser().resolve()
            right_path = Path(right).expanduser().resolve()
        except (OSError, RuntimeError) as exc:
            raise AuthError("storage roots could not be resolved") from exc
        if (
            left_path == right_path
            or left_path.is_relative_to(right_path)
            or right_path.is_relative_to(left_path)
        ):
            raise AuthError(
                f"{left_label} storage and {right_label} storage must be disjoint directories"
            )

    @staticmethod
    def _validate_council_request_limits(members: list[Any]) -> None:
        """Reject excessive total and billable seats before actor construction."""

        if len(members) > MAX_COUNCIL_MEMBERS:
            raise ValueError(f"Council permits at most {MAX_COUNCIL_MEMBERS} members")
        remote_seats = sum(
            1 for item in members if isinstance(item, dict) and item.get("adapter_id", "mock") == "xai"
        )
        if remote_seats > MAX_REMOTE_COUNCIL_SEATS:
            raise ValueError(f"Council permits at most {MAX_REMOTE_COUNCIL_SEATS} remote xAI seats")

    def _actor(self, item: Any) -> DeterministicMockActor | OllamaActor | XAIActor:
        if not isinstance(item, dict):
            raise ValueError("each member must be an object")
        adapter_id = item.get("adapter_id", "mock")
        if not isinstance(adapter_id, str):
            raise ValueError("adapter_id must be a string")

        vote_weight = item.get("vote_weight", 1)
        epistemic_privilege = item.get("epistemic_privilege", "none")
        member_id = self._member_identity(item, "member_id")
        model_id = self._member_identity(item, "model_id")
        member = CouncilMember(
            member_id=member_id,
            model_id=model_id,
            adapter_id=adapter_id,
            deployment_metadata=self._member_metadata(item, "deployment_metadata"),
            capability_metadata=self._member_metadata(item, "capability_metadata"),
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

        if adapter_id == "xai":
            allowed = {
                "member_id",
                "model_id",
                "adapter_id",
                "deployment_metadata",
                "capability_metadata",
                "vote_weight",
                "epistemic_privilege",
                "auth_profile",
                "timeout_seconds",
            }
            unknown = set(item) - allowed
            if unknown:
                raise ValueError(f"xAI member contains unsupported fields: {', '.join(sorted(unknown))}")
            profile_name = item.get("auth_profile", "default")
            if not isinstance(profile_name, str) or not profile_name:
                raise ValueError("xAI auth_profile must be a non-empty string")
            timeout_seconds = item.get("timeout_seconds", 600)
            material = self.auth.resolve("xai", profile_name)
            if material is None:
                raise ValueError("xAI auth profile did not resolve a credential")
            return XAIActor(
                member=member,
                model=member.model_id,
                transport=XAITransport(material, timeout_seconds=timeout_seconds),
            )

        raise ValueError("adapter_id must be 'mock', loopback-local 'ollama', or fixed-remote 'xai'")

    def _list_models(self, adapter_id: str, profile_name: str, timeout_seconds: Any) -> dict[str, Any]:
        if adapter_id != "xai":
            raise ValueError("models.list currently supports only the xai adapter")
        material = self.auth.resolve(adapter_id, profile_name)
        if material is None:
            raise ValueError("xAI auth profile did not resolve a credential")
        models = XAITransport(material, timeout_seconds=timeout_seconds).list_language_models()
        return {
            "status": "ok",
            "adapter_id": adapter_id,
            "profile_name": profile_name,
            "remote_verified": True,
            "model_count": len(models),
            "models": models,
        }

    def _member_identity(self, item: dict[str, Any], field_name: str) -> str:
        value = self._require_str(item, field_name)
        if self.scrubber.scrub(value).changed:
            raise ValueError(f"{field_name} must not contain credential-shaped text")
        return value

    def _member_metadata(self, item: dict[str, Any], field_name: str) -> dict[str, Any]:
        value = item.get(field_name, {})
        if not isinstance(value, dict):
            raise ValueError(f"{field_name} must be an object")
        clean, events = self._scrub_semantic_value(value)
        if events:
            raise ValueError(f"{field_name} must not contain credential-shaped text")
        return clean

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
    def _require_exact_fields(
        mapping: dict[str, Any],
        operation: str,
        operation_fields: set[str],
    ) -> None:
        allowed = {"request_id", "operation"} | set(operation_fields)
        unknown = set(mapping) - allowed
        if unknown:
            rendered = ", ".join(sorted((str(field) for field in unknown)))
            raise ValueError(f"{operation} contains unsupported fields: {rendered}")

    @staticmethod
    def _optional_bool(mapping: dict[str, Any], key: str, default: bool) -> bool:
        value = mapping.get(key, default)
        if type(value) is not bool:
            raise ValueError(f"{key} must be a boolean")
        return value

    @staticmethod
    def _optional_str_list(mapping: dict[str, Any], key: str) -> tuple[str, ...]:
        value = mapping.get(key, [])
        if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
            raise ValueError(f"{key} must be a list of non-empty strings")
        return tuple(value)

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
