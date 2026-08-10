from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from nexus_runtime import NexusAPI
from nexus_runtime.adapters.third_party import ThirdPartyTransport
from nexus_runtime.auth import AuthBroker
from nexus_runtime.council import MAX_EVIDENCE_OBJECT_CHARS
from nexus_runtime.mode_theatre import (
    HOUSE_MODE_ID,
    MAX_MODE_THEATRE_CONTEXT_CHARS,
    MODE_THEATRE_SCHEMA,
    ORATOR_MODE_ID,
    run_mode_theatre_demo,
)
from nexus_runtime.mode_theatre_archive import (
    ARCHIVE_COMMITTED_STATUS,
    ModeTheatreArchive,
    ModeTheatreArchiveError,
)


FAKE_PROVIDER_KEY = "fixture-mode-theatre-provider-key"
ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "tools" / "nexus_mode_theatre_demo.py"
TOOL_SPEC = importlib.util.spec_from_file_location("nexus_mode_theatre_demo_tool", TOOL_PATH)
assert TOOL_SPEC is not None and TOOL_SPEC.loader is not None
TOOL = importlib.util.module_from_spec(TOOL_SPEC)
TOOL_SPEC.loader.exec_module(TOOL)


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


def persisted_world_types(world_root: Path) -> list[str]:
    objects_dir = world_root / "objects"
    if not objects_dir.exists():
        return []
    result: list[str] = []
    for path in sorted(objects_dir.glob("*.json")):
        decoded = json.loads(path.read_text(encoding="utf-8"))
        result.append(decoded["object_type"])
    return result


class FailingFinalizeArchive(ModeTheatreArchive):
    def finalize(self, result: dict[str, object]) -> dict[str, object]:
        raise ModeTheatreArchiveError("simulated archive commit failure")


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
            self.assertEqual(len(result["evidence_context_refs"]), 6)

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

            first_orator_context_ref = result["evidence_context_refs"][3]
            self.assertEqual(
                orator_entries[0].payload["evidence_refs_used"],
                [first_orator_context_ref],
            )
            self.assertEqual(
                orator_entries[0].payload["source_evidence_refs"],
                [result["task_ref"], *result["house_entry_refs"]],
            )

            run = api.world.inspect(result["run_ref"])
            self.assertTrue(run.payload["logs_required"])
            self.assertEqual(run.payload["entry_count"], 6)
            self.assertEqual(run.payload["evidence_context_count"], 6)
            self.assertFalse(run.payload["council_vote"])
            self.assertEqual(run.payload["modes_exercised"], [HOUSE_MODE_ID, ORATOR_MODE_ID])
            self.assertEqual(run.payload["archive_status"], ARCHIVE_COMMITTED_STATUS)
            self.assertEqual(run.payload["archive_commitment_ref"], result["archive_commitment_ref"])

            self.assertTrue(archive.events_path.is_file())
            self.assertTrue(archive.transcript_path.is_file())
            self.assertTrue(archive.manifest_path.is_file())
            transcript = archive.transcript_path.read_text(encoding="utf-8")
            self.assertIn("house_1_Alpha", transcript)
            self.assertIn("orator_1_Gamma", transcript)
            self.assertIn("context_orator_3", transcript)
            self.assertIn("grand_peroration", archive.events_path.read_text(encoding="utf-8"))

            manifest = json.loads(archive.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], ARCHIVE_COMMITTED_STATUS)
            self.assertEqual(manifest["archive_commitment_ref"], result["archive_commitment_ref"])
            self.assertNotIn("run_ref", manifest)
            self.assertNotIn("receipt_ref", manifest)
            self.assertNotIn("credentials_stored", manifest)
            self.assertFalse(manifest["secret_handling"]["credential_absence_verified"])
            self.assertEqual(
                manifest["secret_handling"]["archive_input"],
                "scrubbed_world_objects",
            )

            stenographer = api.handle({"operation": "stenographer.summary"})
            self.assertEqual(stenographer["status"], "ok")
            self.assertGreaterEqual(stenographer["record_count"], 6)

    def test_bounded_context_represents_every_required_source_inside_evidence_limit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            archive = ModeTheatreArchive.reserve(base / "archives")
            api = NexusAPI(base / "world", auth_root=base / "auth")
            result = run_mode_theatre_demo(api, archive, members=mock_roster())

            self.assertLess(MAX_MODE_THEATRE_CONTEXT_CHARS, MAX_EVIDENCE_OBJECT_CHARS)
            final_context = api.world.inspect(result["evidence_context_refs"][-1])
            expected_sources = [
                result["task_ref"],
                *result["house_entry_refs"],
                *result["orator_entry_refs"][:2],
            ]
            self.assertEqual(final_context.payload["source_refs"], expected_sources)
            self.assertTrue(final_context.payload["all_sources_represented"])
            self.assertLessEqual(
                len(final_context.payload["content"]),
                MAX_MODE_THEATRE_CONTEXT_CHARS,
            )

            rendered = api.council.build_evidence_context([final_context.object_id])
            for source_ref in expected_sources:
                with self.subTest(source_ref=source_ref):
                    self.assertIn(source_ref, rendered)
            self.assertNotIn("[NEXUS: evidence excerpt truncated]", rendered)
            self.assertNotIn("[NEXUS: evidence view budget reached]", rendered)

    def test_archive_commit_failure_prevents_success_run_and_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            reserved = ModeTheatreArchive.reserve(base / "archives")
            archive = FailingFinalizeArchive(reserved.run_dir)
            api = NexusAPI(base / "world", auth_root=base / "auth")

            with self.assertRaisesRegex(ModeTheatreArchiveError, "simulated archive commit failure"):
                run_mode_theatre_demo(api, archive, members=mock_roster())

            object_types = persisted_world_types(base / "world")
            self.assertNotIn("mode_theatre_run", object_types)
            self.assertNotIn("receipt", object_types)

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
            # Long outputs exercise the bounded evidence-context compaction path.
            long_tail = " rhetoric" * 500
            with mock.patch.object(
                ThirdPartyTransport,
                "generate",
                side_effect=[
                    "House B: the printer has acute YAML exposure." + long_tail,
                    "House C: fictional reveal, it was the karaoke driver." + long_tail,
                    "Forum C: citizens of the dependency graph, hear me." + long_tail,
                    "Forum B: I rise in magnificent rebuttal." + long_tail,
                ],
            ):
                result = run_mode_theatre_demo(api, archive, members=roster)

            self.assertFalse(result["execution_replayable"])
            run = api.world.inspect(result["run_ref"])
            self.assertFalse(run.payload["execution_replayable"])
            self.assertEqual(run.payload["entry_count"], 6)
            final_context = api.world.inspect(result["evidence_context_refs"][-1])
            self.assertLessEqual(len(final_context.payload["content"]), MAX_MODE_THEATRE_CONTEXT_CHARS)
            # actor.chat records asynchronously; drain before TemporaryDirectory
            # teardown so the worker cannot race removal of stenographer files.
            self.assertTrue(api.stenographer.wait_for_idle())


class ModeTheatreCLITests(unittest.TestCase):
    def test_keyboard_interrupt_records_error_then_propagates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            archive_root = base / "archives"
            with mock.patch.object(TOOL, "run_mode_theatre_demo", side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):
                    TOOL.main(
                        [
                            "--world",
                            str(base / "world"),
                            "--auth-root",
                            str(base / "auth"),
                            "--archive-root",
                            str(archive_root),
                        ]
                    )

            run_dirs = [path for path in archive_root.iterdir() if path.is_dir()]
            self.assertEqual(len(run_dirs), 1)
            error_text = (run_dirs[0] / "ERROR.txt").read_text(encoding="utf-8")
            self.assertEqual(
                error_text,
                "MODE THEATRE INTERRUPTED: operator keyboard interrupt\n",
            )


if __name__ == "__main__":
    unittest.main()
