from __future__ import annotations

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
            self.assertEqual(falsification.payload["previous_stage_ref"], result["instrument_result_ref"])
            self.assertIn(result["instrument_result_ref"], falsification.payload["evidence_refs_used"])
            self.assertTrue(run.payload["shared_world"])
            self.assertTrue(run.payload["sequential_arrival"])
            self.assertEqual(run.payload["mind_count"], 3)
            self.assertEqual(run.payload["additional_votes_created"], 0)

            reopened = NexusAPI(world_root, auth_root=auth_root)
            restarted_run = reopened.world.inspect(result["run_ref"])
            self.assertEqual(restarted_run.payload, run.payload)
            verified = reopened.handle(
                {"operation": "receipt.verify", "receipt_ref": result["receipt_ref"]}
            )
            self.assertEqual(verified["status"], "verified")

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
            with self.assertRaises(ValueError):
                run_three_minds_demo(api, members=duplicate)

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


if __name__ == "__main__":
    unittest.main()
