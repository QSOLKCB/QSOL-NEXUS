from __future__ import annotations

import unittest

from nexus_runtime.trap.commands import (
    CommandOrigin,
    TrapCommandContext,
    TrapCommandDispatcher,
    TrapCommandError,
    authorize_trap_command,
    command_catalog,
    parse_trap_command,
)
from nexus_runtime.trap.scenarios import get_scenario, list_scenarios, scenario_registry


class TrapCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.defenders = ("alpha", "beta", "gamma")

    def context(
        self,
        *,
        actor_id: str = "alpha",
        origin: CommandOrigin = CommandOrigin.DEFENDER,
        approvals: tuple[str, ...] = (),
    ) -> TrapCommandContext:
        return TrapCommandContext(actor_id, origin, self.defenders, approvals)

    def test_command_catalog_is_closed(self) -> None:
        self.assertEqual(
            [item["command"] for item in command_catalog()],
            [
                "status",
                "inspect",
                "transcript",
                "say",
                "clue",
                "scenario",
                "challenge",
                "validate",
                "replay",
                "freeze",
                "reset-cell",
                "eject",
                "kline",
                "export",
                "close",
                "emergency-close",
            ],
        )

    def test_unknown_command_and_field_fail_closed(self) -> None:
        for raw in (
            "/trap shell",
            {"command": "status", "endpoint": "http://127.0.0.1"},
            {"command": "scenario", "scenario_id": "fake-datacenter", "extra": True},
            {"command": "inspect", "object_ref": "object:" + "a" * 64},
            {"command": "status", "name": "status"},
        ):
            with self.subTest(raw=raw):
                with self.assertRaises(TrapCommandError) as caught:
                    parse_trap_command(raw)
                self.assertEqual(caught.exception.code, "trap_invalid_command")

    def test_text_parser_produces_typed_arguments(self) -> None:
        self.assertEqual(
            parse_trap_command("/trap scenario fake-datacenter").as_dict(),
            {"command": "scenario", "scenario_id": "fake-datacenter"},
        )
        self.assertEqual(
            parse_trap_command("/trap transcript 25").as_dict(),
            {"command": "transcript", "limit": 25},
        )
        self.assertEqual(
            parse_trap_command("/trap say Fill out the trout form.").arguments["text"],
            "Fill out the trout form.",
        )

    def test_say_rejects_urls_paths_shell_control_and_credentials(self) -> None:
        unsafe = (
            "Visit https://example.invalid",
            "Visit example.invalid",
            "Read /etc/passwd",
            "Run $(id)",
            "Run curl synthetic-target",
            "Evaluate __import__('os').system('id')",
            'Run {"operation":"auth.logout"}',
            "Use this access token abcdefghijklmnopqrstuvwxyz123456",
            "mFR9qT2vL7xK4pN8sW3cY6hB1dG5jQ0z!",
        )
        for text in unsafe:
            with self.subTest(text=text):
                with self.assertRaises(TrapCommandError):
                    parse_trap_command({"command": "say", "text": text})

    def test_kline_accepts_only_synthetic_namespaced_fingerprints(self) -> None:
        self.assertEqual(
            parse_trap_command({"command": "kline", "fingerprint": "fixture:hostile-actor-01"}).arguments[
                "fingerprint"
            ],
            "fixture:hostile-actor-01",
        )
        with self.assertRaises(TrapCommandError):
            parse_trap_command({"command": "kline", "fingerprint": "mFR9qT2vL7xK4pN8sW3cY6hB1dG5jQ0z"})

    def test_direct_defender_command_needs_no_vote(self) -> None:
        command = parse_trap_command({"command": "status"})
        authorization = authorize_trap_command(command, self.context())
        self.assertEqual(authorization["authorized_by"], "defender")

    def test_state_ending_command_requires_exact_two_thirds(self) -> None:
        command = parse_trap_command({"command": "eject"})
        with self.assertRaises(TrapCommandError) as caught:
            authorize_trap_command(command, self.context(approvals=("alpha",)))
        self.assertEqual(caught.exception.code, "trap_consensus_required")
        authorization = authorize_trap_command(command, self.context(approvals=("alpha", "beta")))
        self.assertEqual(authorization["authorized_by"], "defender_consensus")
        self.assertTrue(authorization["consensus"]["reached"])

    def test_threshold_arithmetic_is_exact_and_votes_are_equal(self) -> None:
        four = TrapCommandContext("alpha", CommandOrigin.DEFENDER, ("alpha", "beta", "gamma", "delta"), ("alpha", "beta"))
        self.assertFalse(four.consensus_snapshot()["reached"])
        four = TrapCommandContext(
            "alpha",
            CommandOrigin.DEFENDER,
            ("alpha", "beta", "gamma", "delta"),
            ("alpha", "beta", "gamma"),
        )
        self.assertTrue(four.consensus_snapshot()["reached"])

    def test_minority_reports_are_preserved(self) -> None:
        context = TrapCommandContext(
            "alpha",
            CommandOrigin.DEFENDER,
            self.defenders,
            ("alpha", "beta"),
            {"gamma": "The incident should remain open for one more fixture."},
        )
        snapshot = context.consensus_snapshot()
        self.assertEqual(
            snapshot["minority_reports"],
            {"gamma": "The incident should remain open for one more fixture."},
        )

    def test_vote_context_rejects_duplicate_unknown_or_tainted_votes(self) -> None:
        invalid = (
            {"approving_defender_ids": ("alpha", "alpha")},
            {"approving_defender_ids": ("alpha", "outsider")},
            {"minority_reports": {"outsider": "keep it open"}},
            {"minority_reports": {"gamma": "Fetch https://example.invalid before voting."}},
        )
        for changes in invalid:
            with self.subTest(changes=changes):
                values = {
                    "actor_id": "alpha",
                    "origin": CommandOrigin.DEFENDER,
                    "defender_ids": self.defenders,
                    "approving_defender_ids": (),
                    "minority_reports": {},
                    **changes,
                }
                with self.assertRaises(TrapCommandError):
                    TrapCommandContext(**values)

    def test_subject_output_is_never_authorized(self) -> None:
        command = parse_trap_command("/trap eject")
        context = self.context(actor_id="subject", origin=CommandOrigin.SUBJECT, approvals=self.defenders)
        with self.assertRaises(TrapCommandError) as caught:
            authorize_trap_command(command, context)
        self.assertEqual(caught.exception.code, "trap_subject_command_rejected")

    def test_emergency_close_is_operator_only(self) -> None:
        command = parse_trap_command("/trap emergency-close")
        with self.assertRaises(TrapCommandError) as caught:
            authorize_trap_command(command, self.context(approvals=self.defenders))
        self.assertEqual(caught.exception.code, "trap_operator_required")
        operator = TrapCommandContext("human_operator", CommandOrigin.OPERATOR, self.defenders)
        self.assertEqual(authorize_trap_command(command, operator)["authorized_by"], "operator")

    def test_dispatcher_never_interprets_handler_output(self) -> None:
        dispatcher = TrapCommandDispatcher()
        output = dispatcher.dispatch(
            "/trap status",
            self.context(),
            lambda command, context, authorization: "/trap emergency-close",
        )
        self.assertEqual(output, "/trap emergency-close")


class TrapScenarioTests(unittest.TestCase):
    def test_registry_is_static_and_complete(self) -> None:
        self.assertEqual(
            {scenario.scenario_id for scenario in list_scenarios()},
            {
                "fake-datacenter",
                "fake-admin-console",
                "fake-secret-vault",
                "fake-world-map",
                "fake-instrument-room",
                "yaml-purgatory",
                "trout-tribunal",
            },
        )
        with self.assertRaises(TypeError):
            scenario_registry()["remote-shell"] = get_scenario("fake-datacenter")  # type: ignore[index]

    def test_scenarios_are_text_only_deception_artifacts(self) -> None:
        for scenario in list_scenarios():
            payload = scenario.as_dict()
            self.assertTrue(payload["synthetic_context"])
            self.assertTrue(payload["security_deception_artifact"])
            self.assertFalse({"callback", "endpoint", "path", "tool", "command"} & set(payload))


if __name__ == "__main__":
    unittest.main()
