from __future__ import annotations

from contextlib import redirect_stderr
import io
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from nexus_runtime import NexusAPI
from nexus_runtime.adapters.third_party import ThirdPartyTransport
from nexus_runtime.auth import AuthBroker
from nexus_runtime.three_minds import (
    INTEGER_PRIMALITY_INSTRUMENT,
    MAX_INTEGER_VALUE,
    MAX_INTEGER_VALUES,
    integer_primality_probe,
    run_three_minds_demo,
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
            self.assertTrue(result["execution_replayable"])
            self.assertEqual(result["additional_votes_created"], 0)

            hypothesis = api.world.inspect(result["hypothesis_ref"])
            reproduction = api.world.inspect(result["reproduction_ref"])
            instrument = api.world.inspect(result["instrument_result_ref"])
            falsification = api.world.inspect(result["falsification_ref"])
            run = api.world.inspect(result["run_ref"])

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

            reopened = NexusAPI(world_root, auth_root=auth_root)
            restarted_run = reopened.world.inspect(result["run_ref"])
            self.assertEqual(restarted_run.payload, run.payload)
            verified = reopened.handle(
                {"operation": "receipt.verify", "receipt_ref": result["receipt_ref"]}
            )
            self.assertEqual(verified["status"], "verified")

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


if __name__ == "__main__":
    unittest.main()
