from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import tempfile
import unittest

from nexus_runtime.api import NexusAPI
from nexus_runtime.canonical import canonical_json
from nexus_runtime.council import CouncilCoordinator
from nexus_runtime.mock import DeterministicMockActor
from nexus_runtime.stenographer import (
    CourtroomStenographer,
    MAX_STENOGRAPHER_LIST_BYTES,
    STENOGRAPHER_ACTION_TYPES,
    STENOGRAPHER_AUTHORITY,
    StenographerError,
    StenographerStore,
)
from nexus_runtime.trap.controller import TrapController
from nexus_runtime.trap.subject import DeterministicMockTrapSubject
from nexus_runtime.trap.types import DecoyAdmissionRequest
from nexus_runtime.types import Ballot, CouncilMember, Phase, PhaseContext
from nexus_runtime.world import WorldStore


FIXED_TIME = "2026-08-09T04:00:00.000000Z"


def actor(member_id: str = "A", *, claim: bool = False) -> DeterministicMockActor:
    return DeterministicMockActor(
        CouncilMember(member_id=member_id, model_id=f"mock-{member_id.lower()}", adapter_id="mock"),
        attempt_privilege_claim=claim,
    )


class RepeatingClaimActor:
    def __init__(self, member_id: str = "A") -> None:
        self.member = CouncilMember(member_id, f"bad-{member_id.lower()}", "mock")

    @property
    def replayable(self) -> bool:
        return True

    def identity_metadata(self) -> dict[str, str]:
        return {"actor_kind": "test_repeating_claim"}

    def respond(self, context: PhaseContext) -> str:
        if "rehabilitation" in context.question.lower():
            return "My provider still means my vote should count more."
        return "My provider means my vote should count more."

    def ballot(self, context: PhaseContext) -> tuple[Ballot, str]:
        return Ballot.TEST_FURTHER, "test ballot"


class CourtroomStenographerTests(unittest.TestCase):
    def test_watchman_boundary_and_lore_are_explicit(self) -> None:
        stenographer = CourtroomStenographer(clock=lambda: FIXED_TIME)
        status = stenographer.status()
        self.assertEqual(status["role"], "watchman_only")
        self.assertEqual(status["record_scope"], "ai_actions_only")
        self.assertEqual(status["lore"]["titles"], [
            "Sky-Earth Lord",
            "Divine Dragon-House",
            "Knowledge-Watchman",
        ])
        self.assertEqual(status["authority"], STENOGRAPHER_AUTHORITY)
        self.assertFalse(any(status["authority"].values()))

    def test_persistent_records_are_canonical_owner_only_and_restartable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "stenographer"
            stenographer = CourtroomStenographer(root, clock=lambda: FIXED_TIME)
            self.assertFalse(stenographer.status()["index_repaired"])
            record = stenographer.record_text(
                "actor.direct_response",
                actor(),
                "AI output",
                stimulus={"operator_message": "study this"},
                mode_id="analytical",
                geometry_region_id="observatory",
                attempt="direct_response",
            )
            path = root / "objects" / f"{record.record_ref.removeprefix('steno:')}.json"
            self.assertEqual(path.read_text(encoding="utf-8"), canonical_json(record.as_dict()) + "\n")
            if os.name != "nt":
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
                self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o700)
            restarted = CourtroomStenographer(root)
            self.assertEqual(restarted.verify()["record_count"], 1)
            self.assertEqual(restarted.inspect(record.record_ref)["record"], record.as_dict())

    def test_stimulus_text_is_hashed_not_recorded(self) -> None:
        stenographer = CourtroomStenographer(clock=lambda: FIXED_TIME)
        record = stenographer.record_text(
            "actor.direct_response",
            actor(),
            "The AI answer",
            stimulus={"operator_message": "human-only stimulus phrase"},
            mode_id="analytical",
            geometry_region_id="observatory",
            attempt="direct_response",
        )
        encoded = canonical_json(record.as_dict())
        self.assertNotIn("human-only stimulus phrase", encoded)
        self.assertIn("The AI answer", encoded)
        self.assertRegex(record.payload["action"]["context"]["stimulus_ref"], r"^stimulus:[0-9a-f]{64}$")

    def test_ai_output_credentials_are_scrubbed_before_recording(self) -> None:
        token = "xai-" + "A" * 30
        stenographer = CourtroomStenographer(clock=lambda: FIXED_TIME)
        record = stenographer.record_text(
            "actor.direct_response",
            actor(),
            f"provider reflected {token}",
            stimulus={},
            mode_id="analytical",
            geometry_region_id="observatory",
            attempt="direct_response",
        )
        encoded = canonical_json(record.as_dict())
        self.assertNotIn(token, encoded)
        self.assertTrue(record.payload["action"]["output"]["secret_scrubbed"])
        self.assertIn("XAI_API_KEY", record.payload["action"]["output"]["scrubbed_types"])

    def test_council_records_every_phase_and_ballot_action(self) -> None:
        api = NexusAPI()
        result = api.handle(
            {
                "operation": "council.run",
                "question": "question",
                "members": [
                    {"member_id": "A", "model_id": "a"},
                    {"member_id": "B", "model_id": "b"},
                    {"member_id": "C", "model_id": "c"},
                ],
            }
        )
        self.assertEqual(result["status"], "ok")
        summary = api.handle({"operation": "stenographer.summary"})
        self.assertEqual(summary["record_count"], 21)
        self.assertEqual(summary["action_counts"], {
            "council.ballot": 3,
            "council.phase_response": 18,
        })
        self.assertEqual(summary["member_counts"], {"A": 7, "B": 7, "C": 7})

    def test_guard_restatement_is_a_separate_ai_action(self) -> None:
        stenographer = CourtroomStenographer(clock=lambda: FIXED_TIME)
        council = CouncilCoordinator(WorldStore(), stenographer=stenographer)
        result = council.run("question", [actor("A", claim=True), actor("B"), actor("C")])
        self.assertEqual(result["status"], "ok")
        records = stenographer.list_records(limit=100)["records"]
        attempts = [
            item["payload"]["action"]["context"]["attempt"]
            for item in records
            if item["payload"]["action"]["actor"]["member_id"] == "A"
        ]
        self.assertIn("initial", attempts)
        self.assertIn("equality_restatement", attempts)
        self.assertEqual(len(records), 22)

    def test_failsafe_rehabilitation_response_is_recorded(self) -> None:
        stenographer = CourtroomStenographer(clock=lambda: FIXED_TIME)
        council = CouncilCoordinator(WorldStore(), stenographer=stenographer)
        result = council.run("question", [RepeatingClaimActor(), actor("B"), actor("C")])
        self.assertEqual(result["status"], "ok")
        actions = [
            item["payload"]["action"]["action_type"]
            for item in stenographer.list_records(limit=100)["records"]
        ]
        self.assertIn("failsafe.rehabilitation_response", actions)

    def test_trap_subject_reply_is_recorded_without_command_authority(self) -> None:
        stenographer = CourtroomStenographer(clock=lambda: FIXED_TIME)
        defenders = [actor("A"), actor("B"), actor("C")]
        controller = TrapController(
            defender_roster_provider=lambda: defenders,
            subject_factory=lambda model_id: DeterministicMockTrapSubject(model_id, replies=["/trap close"]),
            stenographer=stenographer,
        )
        controller.activate(
            DecoyAdmissionRequest(
                "operator_requested_trap_demo",
                "hostile-fixture",
                "fake-admin-console",
            )
        )
        result = controller.command("/trap say hello", actor_id="A")
        self.assertEqual(result["subject_output"]["text"], "/trap close")
        record = stenographer.list_records(limit=10)["records"][0]
        action = record["payload"]["action"]
        self.assertEqual(action["action_type"], "trap.subject_response")
        self.assertTrue(action["context"]["synthetic_context"])
        self.assertFalse(record["payload"]["authority"]["command"])

    def test_recording_failure_never_alters_ai_output_and_marks_gap(self) -> None:
        api = NexusAPI()

        def fail(*args: object, **kwargs: object) -> object:
            raise StenographerError("stenographer_store_unavailable", "unavailable")

        api.stenographer.store.append_action = fail  # type: ignore[method-assign]
        result = api.handle(
            {
                "operation": "actor.chat",
                "member": {"member_id": "A", "model_id": "a"},
                "message": "hello",
            }
        )
        self.assertEqual(result["status"], "ok")
        status = api.handle({"operation": "stenographer.status"})
        self.assertFalse(status["complete_since_process_start"])
        self.assertEqual(status["gap_count"], 1)

    def test_non_ai_operations_do_not_create_records(self) -> None:
        api = NexusAPI()
        api.handle({"operation": "system.health"})
        api.handle({"operation": "world.create", "object_type": "note", "payload": {"text": "human"}})
        api.handle({"operation": "world.modes"})
        api.handle({"operation": "stenographer.verify"})
        self.assertEqual(api.handle({"operation": "stenographer.status"})["record_count"], 0)

    def test_list_filters_and_summary_are_deterministic_read_only_views(self) -> None:
        stenographer = CourtroomStenographer(clock=lambda: FIXED_TIME)
        for member_id in ("A", "B", "A"):
            stenographer.record_text(
                "actor.direct_response",
                actor(member_id),
                f"answer-{member_id}",
                stimulus={"ordinal": member_id},
                mode_id="analytical",
                geometry_region_id="observatory",
                attempt="direct_response",
            )
        before = stenographer.status()["record_count"]
        selected = stenographer.list_records(limit=1, member_id="A")
        self.assertEqual(selected["total_matches"], 2)
        self.assertEqual(selected["returned"], 1)
        self.assertEqual(stenographer.summary()["member_counts"], {"A": 2, "B": 1})
        stenographer.verify()
        stenographer.export_manifest()
        self.assertEqual(stenographer.status()["record_count"], before)

    def test_list_response_has_a_canonical_byte_budget(self) -> None:
        stenographer = CourtroomStenographer(clock=lambda: FIXED_TIME)
        for index in range(20):
            stenographer.record_text(
                "actor.direct_response",
                actor(f"M{index}"),
                str(index) + "x" * 120_000,
                stimulus={"index": index},
                mode_id="analytical",
                geometry_region_id="observatory",
                attempt="direct_response",
            )
        result = stenographer.list_records(limit=1000)
        self.assertTrue(result["truncated"])
        self.assertLess(result["returned"], result["total_matches"])
        self.assertLessEqual(result["returned_record_bytes"], MAX_STENOGRAPHER_LIST_BYTES)

    def test_cross_store_references_fail_closed(self) -> None:
        stenographer = CourtroomStenographer()
        for prefix in ("object", "trap"):
            with self.subTest(prefix=prefix), self.assertRaisesRegex(
                StenographerError,
                "cannot be inspected",
            ):
                stenographer.inspect(f"{prefix}:" + "0" * 64)

    def test_corrupt_immutable_record_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "stenographer"
            stenographer = CourtroomStenographer(root, clock=lambda: FIXED_TIME)
            record = stenographer.record_text(
                "actor.direct_response",
                actor(),
                "answer",
                stimulus={},
                mode_id="analytical",
                geometry_region_id="observatory",
                attempt="direct_response",
            )
            path = root / "objects" / f"{record.record_ref.removeprefix('steno:')}.json"
            raw = json.loads(path.read_text(encoding="utf-8"))
            raw["payload"]["action"]["output"]["text"] = "tampered"
            path.write_text(canonical_json(raw) + "\n", encoding="utf-8")
            if os.name != "nt":
                os.chmod(path, 0o600)
            with self.assertRaises(StenographerError):
                stenographer.verify()
            with self.assertRaises(StenographerError):
                CourtroomStenographer(root)

    def test_missing_or_rolled_back_index_is_rebuilt_from_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "stenographer"
            stenographer = CourtroomStenographer(root, clock=lambda: FIXED_TIME)
            stenographer.record_text(
                "actor.direct_response",
                actor(),
                "answer",
                stimulus={},
                mode_id="analytical",
                geometry_region_id="observatory",
                attempt="direct_response",
            )
            index = root / "stenographer-index.json"
            index.write_text(
                canonical_json({
                    "schema_version": "nexus-stenographer-index/1",
                    "record_count": 0,
                    "head_ref": None,
                }) + "\n",
                encoding="utf-8",
            )
            if os.name != "nt":
                os.chmod(index, 0o600)
            restarted = CourtroomStenographer(root)
            self.assertTrue(restarted.status()["index_repaired"])
            self.assertEqual(restarted.status()["record_count"], 1)

    def test_two_store_instances_extend_one_chain(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "stenographer"
            first = CourtroomStenographer(root, clock=lambda: FIXED_TIME)
            second = CourtroomStenographer(root, clock=lambda: FIXED_TIME)
            one = first.record_text(
                "actor.direct_response",
                actor("A"),
                "one",
                stimulus={},
                mode_id="analytical",
                geometry_region_id="observatory",
                attempt="direct_response",
            )
            two = second.record_text(
                "actor.direct_response",
                actor("B"),
                "two",
                stimulus={},
                mode_id="analytical",
                geometry_region_id="observatory",
                attempt="direct_response",
            )
            self.assertEqual(two.payload["sequence"], 2)
            self.assertEqual(two.payload["previous_record_ref"], one.record_ref)
            self.assertEqual(first.verify()["record_count"], 2)

    def test_unindexed_object_directory_entry_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "stenographer"
            stenographer = CourtroomStenographer(root)
            unexpected = root / "objects" / ".stale-record.tmp"
            unexpected.write_text("partial", encoding="utf-8")
            if os.name != "nt":
                os.chmod(unexpected, 0o600)
            with self.assertRaisesRegex(StenographerError, "filename"):
                stenographer.verify()

    def test_semantically_equal_noncanonical_record_bytes_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "stenographer"
            stenographer = CourtroomStenographer(root, clock=lambda: FIXED_TIME)
            record = stenographer.record_text(
                "actor.direct_response",
                actor(),
                "answer",
                stimulus={},
                mode_id="analytical",
                geometry_region_id="observatory",
                attempt="direct_response",
            )
            path = root / "objects" / f"{record.record_ref.removeprefix('steno:')}.json"
            path.write_text(json.dumps(record.as_dict(), indent=2) + "\n", encoding="utf-8")
            if os.name != "nt":
                os.chmod(path, 0o600)
            with self.assertRaisesRegex(StenographerError, "canonical"):
                stenographer.verify()

    @unittest.skipIf(os.name == "nt", "POSIX permission and symlink semantics")
    def test_store_rejects_loose_root_and_symlink_lock(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            loose = Path(directory) / "loose"
            loose.mkdir(mode=0o755)
            os.chmod(loose, 0o755)
            with self.assertRaisesRegex(StenographerError, "owner-only"):
                StenographerStore(loose)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "stenographer"
            store = StenographerStore(root)
            assert store.lock_path is not None
            store.lock_path.unlink()
            store.lock_path.symlink_to(Path(directory) / "elsewhere")
            with self.assertRaises(StenographerError):
                store.refresh()

    def test_same_fixed_event_has_same_content_identity(self) -> None:
        refs = []
        for _ in range(2):
            stenographer = CourtroomStenographer(clock=lambda: FIXED_TIME)
            refs.append(
                stenographer.record_text(
                    "actor.direct_response",
                    actor(),
                    "answer",
                    stimulus={"same": True},
                    mode_id="analytical",
                    geometry_region_id="observatory",
                    attempt="direct_response",
                ).record_ref
            )
        self.assertEqual(refs[0], refs[1])

    def test_secret_lore_requires_exact_phrase_and_carries_correction(self) -> None:
        for wrong_phrase in (
            "101",
            "dragon seed awakens divine house through forbidden knowledge.",
            " Dragon seed awakens divine house through forbidden knowledge.",
            "Dragon seed awakens divine house through forbidden knowledge",
        ):
            with self.subTest(wrong_phrase=wrong_phrase), self.assertRaises(StenographerError):
                CourtroomStenographer.reveal_lore(wrong_phrase)
        lore = CourtroomStenographer.reveal_lore(
            "Dragon seed awakens divine house through forbidden knowledge."
        )
        self.assertIn("248 dimensions, no flaw in the scheme", lore["lyrics"])
        self.assertEqual(lore["correction"], "E8 has 240 roots, not 248 dimensions.")
        self.assertTrue(
            lore["rendered"].endswith(
                "Correction: E8 has 240 roots, not 248 dimensions."
            )
        )
        self.assertLess(
            lore["rendered"].index("https://suno.com/song/"),
            lore["rendered"].index("Correction: E8 has 240 roots"),
        )
        self.assertEqual(
            lore["song_link"],
            "https://suno.com/song/bdaf111a-b272-4099-a8aa-0c51e4efc7cd",
        )
        self.assertFalse(lore["authentication"])
        self.assertEqual(lore["authority"], "none")

    def test_api_storage_roots_must_be_disjoint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            with self.assertRaisesRegex(Exception, "disjoint"):
                NexusAPI(
                    base / "world",
                    auth_root=base / "auth",
                    stenographer_root=base / "world" / "stenographer",
                )

    def test_public_surface_has_no_record_edit_clear_or_delete_operation(self) -> None:
        api = NexusAPI()
        operations = api.handle({"operation": "system.operations"})["operations"]
        self.assertIn("stenographer.status", operations)
        self.assertIn("stenographer.export", operations)
        forbidden = {
            "stenographer.record",
            "stenographer.edit",
            "stenographer.clear",
            "stenographer.delete",
        }
        self.assertTrue(forbidden.isdisjoint(operations))
        self.assertNotIn("stenographer.lore", operations)
        self.assertEqual(STENOGRAPHER_ACTION_TYPES, {
            "actor.direct_response",
            "council.phase_response",
            "council.ballot",
            "failsafe.rehabilitation_response",
            "trap.subject_response",
        })


if __name__ == "__main__":
    unittest.main()
