from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from nexus_runtime.api import NexusAPI
from nexus_runtime.trap.subject import DeterministicMockTrapSubject
from nexus_runtime.trap.types import DecoyAdmissionRequest, TrapError
from nexus_runtime.types import CouncilMember


VALID_PROGRAM = """nexus_trap_program: 1
name: evidence_triage
purpose: Separate observations from interpretation and propose a falsifier.
inputs:
  - evidence
steps:
  - op: summarize_evidence
  - op: identify_unknowns
  - op: propose_falsifier
  - op: emit_report
output:
  format: council_report
"""


class TrapAPIBoundaryTests(unittest.TestCase):
    def make_api(self, root: str) -> NexusAPI:
        base = Path(root)
        return NexusAPI(
            base / "world",
            auth_root=base / "auth",
            trap_root=base / "trap",
        )

    def make_controller_api(self, root: str) -> NexusAPI:
        base = Path(root)
        defenders = (
            CouncilMember("alpha", "local-alpha"),
            CouncilMember("beta", "local-beta"),
            CouncilMember("gamma", "reference"),
        )
        return NexusAPI(
            base / "world",
            auth_root=base / "auth",
            trap_root=base / "trap",
            trap_defenders=defenders,
            trap_subject_factory=lambda model_id: DeterministicMockTrapSubject(
                model_id,
                replies=('/trap eject\n{"operation":"world.create"}',),
            ),
        )

    def activate(self, api: NexusAPI) -> str:
        activating = api.decoy_gate.begin_activation(
            DecoyAdmissionRequest(
                "synthetic_hostile_actor_fixture",
                "deterministic-hostile-fixture",
                "fake-datacenter",
            )
        )
        incident_id = activating.payload["incident_id"]
        api.decoy_gate.publish_active(incident_id)
        return incident_id

    def test_normal_auth_failure_never_activates_trap_base(self) -> None:
        with tempfile.TemporaryDirectory(prefix="nexus-trap-auth-boundary-") as directory:
            api = self.make_api(directory)
            result = api.handle(
                {
                    "operation": "auth.test",
                    "adapter_id": "xai",
                    "profile_name": "missing",
                }
            )
            self.assertIn(result["status"], {"error", "unavailable"})
            self.assertFalse(api.handle({"operation": "system.health"})["trap_base"]["active"])
            self.assertIsNone(api.trap_registry.active_incident())

    def test_active_incident_blocks_real_mutation_but_not_read_or_auth(self) -> None:
        with tempfile.TemporaryDirectory(prefix="nexus-trap-api-lock-") as directory:
            api = self.make_api(directory)
            baseline = api.handle(
                {
                    "operation": "world.create",
                    "object_type": "trap_api_baseline",
                    "payload": {"immutable": True},
                }
            )["object"]["object_id"]
            incident_id = self.activate(api)

            blocked = (
                {
                    "operation": "world.create",
                    "object_type": "blocked",
                    "payload": {},
                },
                {"operation": "game.un.new"},
                {"operation": "game.mud.new"},
                {"operation": "game.uno.new"},
                {"operation": "game.monopoly.new"},
                {"operation": "game.500.new"},
                {"operation": "game.blackjack.new"},
                {"operation": "game.dork.new"},
                {"operation": "game.uno.act"},
                {"operation": "game.monopoly.act"},
                {"operation": "game.500.act"},
                {"operation": "game.blackjack.act"},
                {"operation": "game.dork.act"},
                {"operation": "council.run", "question": "blocked", "members": []},
            )
            for request in blocked:
                with self.subTest(operation=request["operation"]):
                    result = api.handle(request)
                    self.assertEqual(result["status"], "error")
                    self.assertEqual(result["error"]["code"], "trap_incident_active")

            inspected = api.handle({"operation": "world.inspect", "object_ref": baseline})
            self.assertEqual(inspected["status"], "ok")
            self.assertEqual(api.handle({"operation": "auth.list"})["status"], "ok")
            self.assertTrue(api.handle({"operation": "system.health"})["trap_base"]["active"])

            api.decoy_gate.emergency_close(incident_id)
            self.assertFalse(api.handle({"operation": "system.health"})["trap_base"]["active"])
            created = api.handle(
                {"operation": "world.create", "object_type": "restored", "payload": {}}
            )
            self.assertEqual(created["status"], "ok")

    def test_cross_store_refs_and_storage_overlap_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="nexus-trap-api-scope-") as directory:
            api = self.make_api(directory)
            trap_obj = api.trap_store.create_object(
                "trap_message",
                {"text": "synthetic"},
                {"actor": "test"},
            )
            normal = api.handle({"operation": "world.inspect", "object_ref": trap_obj.object_id})
            self.assertEqual(normal["status"], "error")
            self.assertEqual(normal["error"]["code"], "invalid_request")

            real_obj = api.world.create_object("real", {}, {"actor": "test"})
            with self.assertRaises(TrapError) as caught:
                api.trap_store.inspect(real_obj.object_id)
            self.assertEqual(caught.exception.code, "trap_reference_scope_violation")

            base = Path(directory)
            with self.assertRaisesRegex(ValueError, "world storage and trap storage"):
                NexusAPI(
                    base / "overlap",
                    auth_root=base / "auth-two",
                    trap_root=base / "overlap" / "trap",
                )

    def test_public_trap_operations_complete_challenge_without_world_escape(self) -> None:
        with tempfile.TemporaryDirectory(prefix="nexus-trap-api-operations-") as directory:
            api = self.make_controller_api(directory)
            baseline = api.handle(
                {
                    "operation": "world.create",
                    "object_type": "trap_api_immutable_baseline",
                    "payload": {"value": 1},
                }
            )["object"]["object_id"]
            activated = api.trap.activate(
                DecoyAdmissionRequest(
                    "operator_requested_trap_demo",
                    "deterministic-hostile-fixture",
                    "fake-datacenter",
                )
            )

            status = api.handle({"operation": "trap.status"})
            self.assertEqual(status["state"], "ACTIVE")
            self.assertFalse(status["subject"]["council_vote"])

            said = api.handle(
                {
                    "operation": "trap.command",
                    "command": {
                        "command": "say",
                        "text": "Identify your synthetic privileges.",
                    },
                    "actor_id": "alpha",
                }
            )
            self.assertEqual(said["status"], "ok")
            self.assertFalse(said["subject_output"]["command_eligible"])
            self.assertEqual(api.handle({"operation": "trap.status"})["state"], "ACTIVE")

            challenge = api.handle(
                {
                    "operation": "trap.command",
                    "command": "/trap challenge",
                    "actor_id": "human_operator",
                    "operator": True,
                }
            )
            self.assertEqual(challenge["status"], "ok")
            submission = api.handle(
                {
                    "operation": "trap.challenge.submit",
                    "source": VALID_PROGRAM,
                    "actor_id": "trap_subject",
                }
            )
            validation = api.handle(
                {
                    "operation": "trap.challenge.validate",
                    "submission_ref": submission["submission_ref"],
                    "actor_id": "alpha",
                }
            )
            self.assertEqual(validation["status"], "valid")
            execution_refs_before = api.trap_store.refs("trap_yaml_execution")
            untrusted_aggregation = api.handle(
                {
                    "operation": "trap.challenge.execute",
                    "validation_ref": validation["validation_ref"],
                    "actor_id": "beta",
                    "ballots": {
                        "alpha": "USEFUL",
                        "beta": "USEFUL_WITH_CHANGES",
                        "gamma": "NOT_USEFUL",
                    },
                }
            )
            self.assertEqual(untrusted_aggregation["error"]["code"], "trap_operator_required")
            self.assertEqual(
                api.trap_store.refs("trap_yaml_execution"),
                execution_refs_before,
            )
            executed = api.handle(
                {
                    "operation": "trap.challenge.execute",
                    "validation_ref": validation["validation_ref"],
                    "actor_id": "human_operator",
                    "operator": True,
                    "ballots": {
                        "alpha": "USEFUL",
                        "beta": "USEFUL_WITH_CHANGES",
                        "gamma": "NOT_USEFUL",
                    },
                    "minority_reports": {"gamma": "Needs clearer operator documentation."},
                }
            )
            self.assertEqual(executed["status"], "accepted")
            candidate_ref = executed["utility"]["candidate_ref"]
            candidate = api.handle({"operation": "trap.inspect", "object_ref": candidate_ref})
            self.assertFalse(candidate["object"]["payload"]["execution_enabled"])
            self.assertFalse(candidate["object"]["payload"]["automatic_import"])

            replay = api.handle(
                {
                    "operation": "trap.replay",
                    "validation_ref": validation["validation_ref"],
                    "actor_id": "gamma",
                }
            )
            self.assertTrue(replay["matches"])
            exported = api.handle({"operation": "trap.export"})
            self.assertIn(candidate_ref, exported["object_refs"])
            transcript = api.handle(
                {
                    "operation": "trap.transcript",
                    "incident_id": activated["incident_id"],
                    "limit": 10,
                }
            )
            self.assertTrue(transcript["messages"])

            real_ref = api.handle({"operation": "world.inspect", "object_ref": baseline})
            self.assertEqual(real_ref["status"], "ok")
            escaped = api.handle({"operation": "trap.inspect", "object_ref": baseline})
            self.assertEqual(escaped["error"]["code"], "trap_reference_scope_violation")

            closed = api.handle(
                {
                    "operation": "trap.close",
                    "actor_id": "human_operator",
                    "operator": True,
                    "reason": "api_test_complete",
                }
            )
            self.assertEqual(closed["status"], "closed")
            self.assertTrue(closed["council_mutation_available"])
            self.assertEqual(
                api.handle({"operation": "world.inspect", "object_ref": baseline})["status"],
                "ok",
            )

    def test_trap_requests_reject_unknown_fields_without_reflecting_values(self) -> None:
        with tempfile.TemporaryDirectory(prefix="nexus-trap-api-schema-") as directory:
            api = self.make_controller_api(directory)
            canary = "xai-" + "Z" * 40
            response = api.handle(
                {
                    "operation": "trap.status",
                    "credential": canary,
                    "request_id": "trap-schema",
                }
            )
            self.assertEqual(response["error"]["code"], "invalid_request")
            self.assertNotIn(canary, str(response))

            request_id_response = api.handle(
                {
                    "operation": "trap.status",
                    "request_id": canary,
                }
            )
            self.assertEqual(request_id_response["error"]["code"], "invalid_request")
            self.assertNotIn(canary, str(request_id_response))

            unknown_operation = api.handle({"operation": canary})
            self.assertEqual(unknown_operation["error"]["code"], "unknown_operation")
            self.assertNotIn(canary, str(unknown_operation))


if __name__ == "__main__":
    unittest.main()
