from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from nexus_runtime import NexusAPI
from nexus_runtime.adapters.third_party import ThirdPartyTransport
from nexus_runtime.auth import AuthBroker
from nexus_runtime.mode_theatre import (
    HOUSE_MODE_ID,
    MODE_THEATRE_SCHEMA,
    ORATOR_MODE_ID,
    run_mode_theatre_demo,
)
from nexus_runtime.mode_theatre_archive import ModeTheatreArchive


FAKE_PROVIDER_KEY = "fixture-mode-theatre-provider-key"


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


class ModeTheatreDemoTests(unittest.TestCase):
    def test_house_then_orator_preserves_six_entries_and_required_archive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            archive = ModeTheatreArchive.reserve(base / "archives")
            api = NexusAPI(
                base / "world",
                auth_root=base / "auth",
                stenographer_root=archive.stenographer_root,
            )
            result = run_mode_theatre_demo(
                api,
                archive,
                members=mock_roster(),
            )

            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["schema"], MODE_THEATRE_SCHEMA)
            self.assertEqual(result["receipt_status"], "verified")
            self.assertTrue(result["execution_replayable"])
            self.assertEqual(result["additional_votes_created"], 0)
            self.assertEqual(len(result["house_entry_refs"]), 3)
            self.assertEqual(len(result["orator_entry_refs"]), 3)

            house_entries = [api.world.inspect(ref) for ref in result["house_entry_refs"]]
            orator_entries = [api.world.inspect(ref) for ref in result["orator_entry_refs"]]
            self.assertEqual([entry.payload["mode_id"] for entry in house_entries], [HOUSE_MODE_ID] * 3)
            self.assertEqual([entry.payload["mode_id"] for entry in orator_entries], [ORATOR_MODE_ID] * 3)
            self.assertEqual(
                [entry.payload["requested_member"]["member_id"] for entry in house_entries],
                ["Alpha", "Beta", "Gamma"],
            )
            self.assertEqual(
                [entry.payload["requested_member"]["member_id"] for entry in orator_entries],
                ["Gamma", "Beta", "Alpha"],
            )
            self.assertEqual(house_entries[0].payload["round_position"], 1)
            self.assertEqual(orator_entries[-1].payload["role"], "grand_peroration")
            self.assertIn(
                result["house_entry_refs"][-1],
                orator_entries[0].payload["evidence_refs_used"],
            )

            run = api.world.inspect(result["run_ref"])
            self.assertTrue(run.payload["logs_required"])
            self.assertEqual(run.payload["entry_count"], 6)
            self.assertFalse(run.payload["council_vote"])
            self.assertEqual(run.payload["modes_exercised"], [HOUSE_MODE_ID, ORATOR_MODE_ID])

            self.assertTrue(archive.events_path.is_file())
            self.assertTrue(archive.transcript_path.is_file())
            self.assertTrue(archive.manifest_path.is_file())
            transcript = archive.transcript_path.read_text(encoding="utf-8")
            self.assertIn("house_1_Alpha", transcript)
            self.assertIn("orator_1_Gamma", transcript)
            self.assertIn("grand_peroration", archive.events_path.read_text(encoding="utf-8"))

            manifest = json.loads(archive.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["run_ref"], result["run_ref"])
            self.assertEqual(manifest["receipt_status"], "verified")
            self.assertFalse(manifest["credentials_stored"])

            stenographer = api.handle({"operation": "stenographer.summary"})
            self.assertEqual(stenographer["status"], "ok")
            self.assertGreaterEqual(stenographer["record_count"], 6)

    def test_custom_prompts_are_scrubbed_before_archive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            archive = ModeTheatreArchive.reserve(base / "archives")
            api = NexusAPI(base / "world", auth_root=base / "auth")
            secretish = "api_key=sk-abcdefghijklmnopqrstuvwxyz123456"
            result = run_mode_theatre_demo(
                api,
                archive,
                members=mock_roster(),
                house_case=f"Fictional printer case with accidental operator paste {secretish}",
                orator_motion="Resolved: the printer owes the Forum an apology.",
            )
            task = api.world.inspect(result["task_ref"])
            self.assertNotIn("sk-abcdefghijklmnopqrstuvwxyz123456", task.payload["content"])
            transcript = archive.transcript_path.read_text(encoding="utf-8")
            self.assertNotIn("sk-abcdefghijklmnopqrstuvwxyz123456", transcript)
            self.assertIn("<REDACTED:", transcript)

    def test_member_validation_uses_mode_theatre_context(self) -> None:
        bad = list(mock_roster())
        bad.pop()
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            archive = ModeTheatreArchive.reserve(base / "archives")
            api = NexusAPI(base / "world", auth_root=base / "auth")
            with self.assertRaisesRegex(ValueError, "mode-theatre demo requires exactly three minds"):
                run_mode_theatre_demo(api, archive, members=bad)

    def test_mock_openai_and_gemini_can_perform_hermetically(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            environment = {
                "OPENAI_API_KEY": FAKE_PROVIDER_KEY,
                "GEMINI_API_KEY": FAKE_PROVIDER_KEY,
            }
            broker = AuthBroker(base / "auth", environment=environment)
            broker.add_environment("openai", "default", "OPENAI_API_KEY")
            broker.add_environment("gemini", "default", "GEMINI_API_KEY")
            archive = ModeTheatreArchive.reserve(base / "archives")
            api = NexusAPI(
                base / "world",
                auth_broker=broker,
                stenographer_root=archive.stenographer_root,
            )
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
            # Remote actors are called four times total: OpenAI twice and Gemini twice.
            with mock.patch.object(
                ThirdPartyTransport,
                "generate",
                side_effect=[
                    "House B: the printer has acute YAML exposure.",
                    "House C: fictional reveal, it was the karaoke driver.",
                    "Forum C: citizens of the dependency graph, hear me.",
                    "Forum B: I rise in magnificent rebuttal.",
                ],
            ):
                result = run_mode_theatre_demo(api, archive, members=roster)

            self.assertFalse(result["execution_replayable"])
            run = api.world.inspect(result["run_ref"])
            self.assertFalse(run.payload["execution_replayable"])
            self.assertEqual(run.payload["entry_count"], 6)


if __name__ == "__main__":
    unittest.main()
