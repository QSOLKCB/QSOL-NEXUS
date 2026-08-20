from __future__ import annotations

from contextlib import redirect_stderr
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from nexus_runtime import NexusAPI
from nexus_runtime.adapters.third_party import ThirdPartyTransport
from nexus_runtime.auth import AuthBroker
from nexus_runtime.instruments import verify_instrument_receipt
from nexus_runtime.three_minds import (
    INTEGER_PRIMALITY_INSTRUMENT,
    MAX_INTEGER_VALUE,
    MAX_INTEGER_VALUES,
    THREE_MINDS_INTEGRATION_SCHEMA,
    ThreeMindsError,
    integer_primality_probe,
    run_three_minds_council_demo,
    run_three_minds_demo,
    run_three_minds_reference_council,
    verify_three_minds_integration,
)
from tools import nexus_three_minds_demo as demo_cli


FAKE_PROVIDER_KEY = "fixture-three-minds-provider-key"


def mock_roster() -> tuple[dict[str, object], ...]:
    return (
        {
            "member_id": "Alpha",
            "model_id": "mock-alpha",
            "adapter_id": "mock",
            "profile": "exploratory",
        },
        {
            "member_id": "Beta",
            "model_id": "mock-beta",
            "adapter_id": "mock",
            "profile": "skeptical",
        },
        {
            "member_id": "Gamma",
            "model_id": "mock-gamma",
            "adapter_id": "mock",
            "profile": "balanced",
        },
    )


class IntegerPrimalityInstrumentTests(unittest.TestCase):
    def test_probe_is_bounded_exact_and_finds_smallest_factor(self) -> None:
        first = integer_primality_probe([2, 3, 5, 25])
        second = integer_primality_probe([2, 3, 5, 25])
        self.assertEqual(first, second)
        self.assertEqual(first["instrument_id"], INTEGER_PRIMALITY_INSTRUMENT)
        self.assertFalse(first["all_prime"])
        self.assertEqual(first["composite_values"], [25])
        twenty_five = next(item for item in first["results"] if item["value"] == 25)
        self.assertEqual(twenty_five["smallest_factor"], 5)

    def test_probe_rejects_boolean_oversized_and_excessive_inputs(self) -> None:
        for values in (
            [True],
            [MAX_INTEGER_VALUE + 1],
            [2] * (MAX_INTEGER_VALUES + 1),
        ):
            with self.subTest(values_len=len(values)):
                with self.assertRaises(ValueError):
                    integer_primality_probe(values)


class ThreeMindsSharedWorldTests(unittest.TestCase):
    def test_three_minds_preserve_one_restartable_lineage_and_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            world_root = base / "world"
            auth_root = base / "auth"
            api = NexusAPI(world_root, auth_root=auth_root)
            result = run_three_minds_demo(
                api,
                members=mock_roster(),
                values=[2, 3, 5, 7, 11, 25],
            )

            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["result_state"], "FALSIFIED_BY_INTEGER_FIXTURE")
            self.assertEqual(result["receipt_status"], "verified")
            self.assertEqual(result["integration_receipt_status"], "verified")
            self.assertTrue(result["baseline_replay_exact"])
            self.assertTrue(result["execution_replayable"])
            self.assertEqual(result["additional_votes_created"], 0)

            hypothesis = api.world.inspect(result["hypothesis_ref"])
            reproduction = api.world.inspect(result["reproduction_ref"])
            instrument = api.world.inspect(result["instrument_result_ref"])
            falsification = api.world.inspect(result["falsification_ref"])
            run = api.world.inspect(result["run_ref"])
            integration = api.world.inspect(result["integration_ref"])
            descendant = api.world.inspect(result["verified_descendant_ref"])

            self.assertEqual(hypothesis.payload["sequence_index"], 1)
            self.assertIsNone(hypothesis.payload["previous_stage_ref"])
            self.assertEqual(reproduction.payload["previous_stage_ref"], result["hypothesis_ref"])
            self.assertIn(result["hypothesis_ref"], reproduction.payload["evidence_refs_used"])
            self.assertEqual(instrument.payload["previous_stage_ref"], result["reproduction_ref"])
            self.assertEqual(instrument.payload["composite_values"], [25])
            self.assertEqual(
                instrument.payload["execution_initiator"]["actor"],
                "nexus_three_minds_demo",
            )
            self.assertEqual(instrument.payload["made_available_to"]["member_id"], "Gamma")
            self.assertNotIn("requested_by_member_id", instrument.provenance)
            self.assertEqual(falsification.payload["previous_stage_ref"], result["instrument_result_ref"])
            self.assertIn(result["instrument_result_ref"], falsification.payload["evidence_refs_used"])
            self.assertTrue(run.payload["shared_world"])
            self.assertTrue(run.payload["sequential_arrival"])
            self.assertEqual(run.payload["mind_count"], 3)
            self.assertEqual(run.payload["instrument_execution_actor"], "nexus_three_minds_demo")
            self.assertEqual(run.payload["additional_votes_created"], 0)
            self.assertEqual(integration.payload["schema"], THREE_MINDS_INTEGRATION_SCHEMA)
            self.assertTrue(integration.payload["mind_b_replay_exact"])
            self.assertFalse(descendant.payload["semantic_truth_claimed"])

            reopened = NexusAPI(world_root, auth_root=auth_root)
            restarted_run = reopened.world.inspect(result["run_ref"])
            self.assertEqual(restarted_run.payload, run.payload)
            verified = reopened.handle(
                {"operation": "receipt.verify", "receipt_ref": result["receipt_ref"]}
            )
            self.assertEqual(verified["status"], "verified")
            integration_verified = verify_three_minds_integration(reopened, result)
            self.assertEqual(integration_verified["status"], "verified")
            self.assertEqual(integration_verified["presence_lineage_length"], 4)
            self.assertEqual(integration_verified["final_region_id"], "observatory")
            self.assertTrue(integration_verified["baseline_replay_exact"])
            self.assertFalse(integration_verified["semantic_truth_claimed"])

    def test_alpha7_receipts_alpha8_workflow_and_lattice_handoff_verify(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            api = NexusAPI(base / "world", auth_root=base / "auth")
            result = run_three_minds_demo(
                api,
                members=mock_roster(),
                values=[2, 3, 5, 7, 11, 25],
            )

            baseline_a = api.world.inspect(result["mind_a_baseline_record_ref"])
            baseline_b = api.world.inspect(result["mind_b_replay_record_ref"])
            bundle_a = baseline_a.payload["instrument_bundle"]
            bundle_b = baseline_b.payload["instrument_bundle"]
            self.assertEqual(bundle_a, bundle_b)
            self.assertEqual(verify_instrument_receipt(bundle_a)["status"], "verified")
            self.assertEqual(verify_instrument_receipt(bundle_b)["status"], "verified")

            instrument = api.world.inspect(result["instrument_result_ref"])
            self.assertEqual(
                verify_instrument_receipt(instrument.payload["instrument_bundle"])["status"],
                "verified",
            )
            self.assertEqual(instrument.payload["composite_values"], [25])
            self.assertTrue(instrument.payload["derived_material_only"])

            persistent_hypothesis = api.world.inspect(result["persistent_hypothesis_ref"])
            self.assertEqual(persistent_hypothesis.object_type, "world_hypothesis")
            self.assertEqual(persistent_hypothesis.payload["state"], "RETIRED")
            self.assertEqual(persistent_hypothesis.payload["evidence_refs"], [result["task_ref"]])
            self.assertEqual(
                persistent_hypothesis.payload["state_semantics"],
                "workflow_label_not_truth_classification",
            )
            persistent_experiment = api.world.inspect(result["persistent_experiment_ref"])
            self.assertEqual(persistent_experiment.object_type, "world_experiment")
            self.assertEqual(persistent_experiment.payload["stage"], "CLOSED")
            self.assertEqual(
                persistent_experiment.payload["hypothesis_refs"],
                [result["persistent_hypothesis_ref"]],
            )
            self.assertEqual(
                persistent_experiment.payload["claim_boundary"],
                "recorded_world_lineage_not_empirical_truth",
            )

            presence = api.handle(
                {"operation": "world.presence", "event_ref": result["final_presence_ref"]}
            )
            self.assertEqual(presence["status"], "ok")
            self.assertEqual(presence["presence"]["lineage_length"], 4)
            self.assertEqual(presence["presence"]["current"]["region_id"], "observatory")
            self.assertEqual(presence["presence"]["authority_effect"], "none")

    def test_restart_verifier_rejects_refs_mixed_across_runs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            api = NexusAPI(base / "world", auth_root=base / "auth")
            first = run_three_minds_demo(
                api,
                members=mock_roster(),
                values=[2, 3, 5, 25],
                question="first integration fixture",
            )
            second = run_three_minds_demo(
                api,
                members=mock_roster(),
                values=[2, 3, 5, 9],
                question="second integration fixture",
            )
            mixed = dict(first)
            for key in (
                "final_presence_ref",
                "persistent_hypothesis_ref",
                "persistent_experiment_ref",
                "mind_a_baseline_record_ref",
                "mind_b_replay_record_ref",
                "verified_descendant_ref",
                "instrument_result_ref",
            ):
                mixed[key] = second[key]

            with self.assertRaisesRegex(ThreeMindsError, "integration ref mismatch"):
                verify_three_minds_integration(api, mixed)

    def test_persistent_hypotheses_are_bound_to_each_task(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            api = NexusAPI(base / "world", auth_root=base / "auth")
            first = run_three_minds_demo(
                api,
                members=mock_roster(),
                values=[2, 3, 5, 25],
                question="task-bound fixture one",
            )
            second = run_three_minds_demo(
                api,
                members=mock_roster(),
                values=[2, 3, 5, 9],
                question="task-bound fixture two",
            )

            self.assertNotEqual(first["task_ref"], second["task_ref"])
            self.assertNotEqual(first["persistent_hypothesis_ref"], second["persistent_hypothesis_ref"])
            first_hypothesis = api.world.inspect(first["persistent_hypothesis_ref"])
            second_hypothesis = api.world.inspect(second["persistent_hypothesis_ref"])
            self.assertEqual(first_hypothesis.payload["evidence_refs"], [first["task_ref"]])
            self.assertEqual(second_hypothesis.payload["evidence_refs"], [second["task_ref"]])

    def test_reference_council_preserves_one_searchable_minority_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            api = NexusAPI(base / "world", auth_root=base / "auth")
            result = run_three_minds_demo(
                api,
                members=mock_roster(),
                values=[2, 3, 5, 7, 11, 25],
            )
            council = run_three_minds_reference_council(
                api,
                evidence_refs=[result["run_ref"], result["integration_ref"]],
            )
            self.assertEqual(council["status"], "ok")
            self.assertEqual(council["minority_search"]["returned"], 1)
            self.assertEqual(council["minority_search"]["matched_count"], 1)
            self.assertEqual(
                council["minority_search"]["matched_session_ref"],
                council["session_ref"],
            )
            self.assertFalse(council["minority_search"]["search_is_evidence"])
            self.assertFalse(council["provider_consensus_is_evidence"])
            self.assertEqual(council["authority_effect"], "none")
            self.assertEqual(council["result"]["tally"]["TEST_FURTHER"], 2)
            self.assertEqual(council["result"]["tally"]["ACCEPT_WITH_CHANGES"], 1)

    def test_reference_council_repeated_runs_scope_minority_to_current_session(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            api = NexusAPI(base / "world", auth_root=base / "auth")
            first = run_three_minds_demo(
                api,
                members=mock_roster(),
                values=[2, 3, 5, 25],
                question="first council fixture",
            )
            first_council = run_three_minds_reference_council(
                api,
                evidence_refs=[first["run_ref"], first["integration_ref"]],
            )
            second = run_three_minds_demo(
                api,
                members=mock_roster(),
                values=[2, 3, 5, 9],
                question="second council fixture",
            )
            second_council = run_three_minds_reference_council(
                api,
                evidence_refs=[second["run_ref"], second["integration_ref"]],
            )

            self.assertNotEqual(first_council["session_ref"], second_council["session_ref"])
            self.assertGreaterEqual(second_council["minority_search"]["returned"], 2)
            self.assertEqual(second_council["minority_search"]["matched_count"], 1)
            self.assertEqual(
                second_council["minority_search"]["matched_session_ref"],
                second_council["session_ref"],
            )
            self.assertFalse(second_council["minority_search"]["search_is_evidence"])

    def test_configured_mock_council_uses_same_constitutional_roster(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            api = NexusAPI(base / "world", auth_root=base / "auth")
            result = run_three_minds_demo(api, members=mock_roster())
            council = run_three_minds_council_demo(
                api,
                members=mock_roster(),
                evidence_refs=[result["run_ref"], result["integration_ref"]],
            )
            self.assertEqual(council["status"], "ok")
            self.assertTrue(council["execution_replayable"])
            self.assertFalse(council["provider_consensus_is_evidence"])
            self.assertEqual(council["authority_effect"], "none")
            self.assertEqual(
                [member["adapter_id"] for member in council["roster"]],
                ["mock", "mock", "mock"],
            )

    def test_task_and_instrument_evidence_expose_exact_custom_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            api = NexusAPI(base / "world", auth_root=base / "auth")
            question = "Custom framing: independently test this exact finite fixture."
            result = run_three_minds_demo(
                api,
                members=mock_roster(),
                values=[2, 3, 5, 7, 11, 13],
                question=question,
            )
            task = api.world.inspect(result["task_ref"])
            instrument = api.world.inspect(result["instrument_result_ref"])

            self.assertIn(question, task.payload["content"])
            self.assertIn("values=[2,3,5,7,11,13]", task.payload["content"])
            self.assertIn("values=[2,3,5,7,11,13]", instrument.payload["content"])

    def test_prime_fixture_is_not_overclaimed_as_proof(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            api = NexusAPI(base / "world", auth_root=base / "auth")
            result = run_three_minds_demo(
                api,
                members=mock_roster(),
                values=[2, 3, 5, 7, 11, 13],
            )
            self.assertEqual(
                result["result_state"],
                "NOT_FALSIFIED_WITHIN_INTEGER_FIXTURE",
            )
            run = api.world.inspect(result["run_ref"])
            self.assertEqual(
                run.payload["instrument_evidence_state"],
                "VERIFIED_FOR_SUPPLIED_INTEGER_FIXTURE",
            )
            self.assertIn("does not prove model truth", run.payload["claim_boundary"])
            final_hypothesis = api.world.inspect(result["persistent_hypothesis_ref"])
            self.assertEqual(final_hypothesis.payload["state"], "CHALLENGED")
            self.assertEqual(final_hypothesis.payload["evidence_refs"], [result["task_ref"]])

    def test_exactly_three_distinct_identities_are_required_before_run(self) -> None:
        duplicate = list(mock_roster())
        duplicate[2] = dict(duplicate[1])
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            api = NexusAPI(base / "world", auth_root=base / "auth")
            with self.assertRaisesRegex(ValueError, "mind 3.*duplicates member_id.*mind 2"):
                run_three_minds_demo(api, members=duplicate)

    def test_member_validation_names_index_member_and_bad_field(self) -> None:
        roster = [dict(member) for member in mock_roster()]
        roster[0].update(
            {
                "adapter_id": "ollama",
                "model_id": "declared-model",
                "model": "different-effective-model",
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            api = NexusAPI(base / "world", auth_root=base / "auth")
            with self.assertRaisesRegex(
                ValueError,
                "mind 1.*member_id='Alpha'.*field model.*equal model_id",
            ):
                run_three_minds_demo(api, members=roster)

    def test_world_modes_contract_failure_is_not_reported_as_unknown_mode(self) -> None:
        class BadModesAPI:
            def handle(self, request: dict[str, object]) -> dict[str, object]:
                self.assert_request = request
                return {"status": "ok", "modes": None}

        with self.assertRaisesRegex(
            ValueError,
            "world.modes returned unexpected modes structure: expected list, got 'NoneType'",
        ):
            run_three_minds_demo(BadModesAPI(), members=mock_roster())

    def test_mock_openai_and_gemini_can_share_one_hermetic_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            environment = {
                "OPENAI_API_KEY": FAKE_PROVIDER_KEY,
                "GEMINI_API_KEY": FAKE_PROVIDER_KEY,
            }
            broker = AuthBroker(base / "auth", environment=environment)
            broker.add_environment("openai", "default", "OPENAI_API_KEY")
            broker.add_environment("gemini", "default", "GEMINI_API_KEY")
            api = NexusAPI(base / "world", auth_broker=broker)
            roster = (
                {
                    "member_id": "LocalOpen",
                    "model_id": "mock-local-open",
                    "adapter_id": "mock",
                    "profile": "exploratory",
                },
                {
                    "member_id": "RemoteOpenAI",
                    "model_id": "fixture-openai-model",
                    "adapter_id": "openai",
                    "auth_profile": "default",
                },
                {
                    "member_id": "RemoteGemini",
                    "model_id": "fixture-gemini-model",
                    "adapter_id": "gemini",
                    "auth_profile": "default",
                },
            )
            with mock.patch.object(
                ThirdPartyTransport,
                "generate",
                side_effect=[
                    "Mind B independently critiques the benchmark claim.",
                    "Mind C accepts the bounded arithmetic falsifier for this fixture only.",
                ],
            ):
                result = run_three_minds_demo(
                    api,
                    members=roster,
                    values=[2, 3, 5, 9],
                )

            self.assertFalse(result["execution_replayable"])
            self.assertEqual(
                [member["adapter_id"] for member in result["roster"]],
                ["mock", "openai", "gemini"],
            )
            run = api.world.inspect(result["run_ref"])
            self.assertFalse(run.payload["execution_replayable"])
            self.assertEqual(run.payload["result_state"], "FALSIFIED_BY_INTEGER_FIXTURE")
            self.assertEqual(run.payload["additional_votes_created"], 0)
            integration_verified = verify_three_minds_integration(api, result)
            self.assertEqual(integration_verified["status"], "verified")


class ThreeMindsCLITests(unittest.TestCase):
    def test_existing_json_output_fails_before_runtime_or_model_calls(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            output = base / "existing.json"
            output.write_text("preserve-me\n", encoding="utf-8")
            stderr = io.StringIO()
            with mock.patch.object(demo_cli, "NexusAPI") as api_constructor, redirect_stderr(stderr):
                code = demo_cli.main(
                    [
                        "--world",
                        str(base / "world"),
                        "--json-out",
                        str(output),
                    ]
                )

            self.assertEqual(code, 3)
            api_constructor.assert_not_called()
            self.assertEqual(output.read_text(encoding="utf-8"), "preserve-me\n")
            self.assertIn("refusing to overwrite", stderr.getvalue())

    def test_failed_run_removes_only_its_reserved_empty_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            output = base / "reserved.json"
            stderr = io.StringIO()
            with (
                mock.patch.object(demo_cli, "NexusAPI", return_value=object()),
                mock.patch.object(
                    demo_cli,
                    "run_three_minds_demo",
                    side_effect=ValueError("fixture failure"),
                ),
                redirect_stderr(stderr),
            ):
                code = demo_cli.main(
                    [
                        "--world",
                        str(base / "world"),
                        "--json-out",
                        str(output),
                    ]
                )

            self.assertEqual(code, 2)
            self.assertFalse(output.exists())
            self.assertIn("fixture failure", stderr.getvalue())

    def test_non_mock_extra_council_requires_authorization_before_runtime(self) -> None:
        remote = json.dumps(
            {
                "member_id": "RemoteXAI",
                "model_id": "grok-fixture",
                "adapter_id": "xai",
                "auth_profile": "default",
            }
        )
        stderr = io.StringIO()
        with mock.patch.object(demo_cli, "NexusAPI") as api_constructor, redirect_stderr(stderr):
            code = demo_cli.main(["--council", "--mind-a", remote])
        self.assertEqual(code, 2)
        api_constructor.assert_not_called()
        self.assertIn("--authorize-council", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
