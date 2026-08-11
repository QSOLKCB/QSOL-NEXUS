from __future__ import annotations

import os
from pathlib import Path
import stat
import tempfile
import threading
import unittest
from unittest.mock import patch

from nexus_runtime.__main__ import _drain_stenographer_on_exit
from nexus_runtime.mock import DeterministicMockActor
from nexus_runtime.stenographer import (
    CourtroomStenographer,
    StenographerError,
    StenographerStore,
)
from nexus_runtime.types import CouncilMember


FIXED_TIME = "2026-08-11T00:00:00.000000Z"


def _actor() -> DeterministicMockActor:
    return DeterministicMockActor(
        CouncilMember(member_id="A", model_id="mock-a", adapter_id="mock")
    )


def _record_one(stenographer: CourtroomStenographer, text: str = "hello") -> str:
    record = stenographer.record_text(
        "actor.direct_response",
        _actor(),
        text,
        stimulus={"operator_message": "study this"},
        mode_id="analytical",
        geometry_region_id="observatory",
        attempt="direct_response",
    )
    return record.record_ref


class StenographerTmpDebrisTests(unittest.TestCase):
    def test_legacy_object_tmp_without_permanent_record_does_not_corrupt_store(self) -> None:
        """Exact old NEXUS scratch names are debris, not immutable ledger objects."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "stenographer"
            stenographer = CourtroomStenographer(root, clock=lambda: FIXED_TIME)
            _record_one(stenographer)

            debris = root / "objects" / f".{('a' * 64)}.tmp-99999-1234567890"
            debris.write_bytes(b"partial")
            if os.name != "nt":
                os.chmod(debris, 0o600)

            reopened = StenographerStore(root)
            verified = reopened.verify()
            self.assertEqual(verified["status"], "ok")
            self.assertEqual(verified["integrity"], "valid")
            self.assertEqual(verified["record_count"], 1)
            # Do not reap an unmatched legacy temp: another old-version process
            # could still be writing it. Ignoring the exact pattern is enough.
            self.assertTrue(debris.exists())

    def test_legacy_object_tmp_is_reaped_when_permanent_record_exists(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "stenographer"
            stenographer = CourtroomStenographer(root, clock=lambda: FIXED_TIME)
            record_ref = _record_one(stenographer)
            digest = record_ref.removeprefix("steno:")
            debris = root / "objects" / f".{digest}.tmp-99999-1234567890"
            debris.write_bytes(b"already committed")
            if os.name != "nt":
                os.chmod(debris, 0o600)

            reopened = StenographerStore(root)
            self.assertEqual(reopened.verify()["record_count"], 1)
            self.assertFalse(debris.exists())

    def test_foreign_filename_still_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "stenographer"
            StenographerStore(root)
            foreign = root / "objects" / "not-a-record.txt"
            foreign.write_text("nope\n", encoding="utf-8")
            if os.name != "nt":
                os.chmod(foreign, 0o600)

            with self.assertRaises(StenographerError) as ctx:
                StenographerStore(root)
            self.assertEqual(ctx.exception.code, "stenographer_store_corrupt")

    @unittest.skipIf(os.name == "nt", "POSIX symlink semantics")
    def test_temp_shaped_symlink_still_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "stenographer"
            StenographerStore(root)
            outside = Path(directory) / "outside"
            outside.write_text("not a temp", encoding="utf-8")
            debris = root / "objects" / f".{('b' * 64)}.tmp-111-222"
            debris.symlink_to(outside)

            with self.assertRaises(StenographerError) as ctx:
                StenographerStore(root)
            self.assertEqual(ctx.exception.code, "stenographer_store_corrupt")

    def test_write_temp_directory_is_private_and_not_scanned_as_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "stenographer"
            store = StenographerStore(root)
            assert store.write_tmp_dir is not None
            junk = store.write_tmp_dir / "crash-leftover.bin"
            junk.write_bytes(b"unfinished private scratch")
            if os.name != "nt":
                os.chmod(junk, 0o600)
                self.assertEqual(stat.S_IMODE(store.write_tmp_dir.stat().st_mode), 0o700)

            reopened = StenographerStore(root)
            self.assertEqual(reopened.verify()["integrity"], "valid")
            self.assertTrue(junk.exists())

    def test_atomic_record_temp_is_created_outside_objects_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "stenographer"
            stenographer = CourtroomStenographer(root, clock=lambda: FIXED_TIME)
            real_link = os.link
            link_sources: list[Path] = []

            def capture_link(source: os.PathLike[str] | str, target: os.PathLike[str] | str) -> None:
                link_sources.append(Path(source))
                real_link(source, target)

            with patch("nexus_runtime.stenographer.os.link", side_effect=capture_link):
                _record_one(stenographer, "structural isolation")

            self.assertEqual(len(link_sources), 1)
            self.assertEqual(link_sources[0].parent, root / ".write-tmp")
            self.assertEqual(list((root / "objects").glob(".*.tmp-*")), [])
            self.assertEqual(list((root / ".write-tmp").glob(".*.tmp-*")), [])

    def test_shutdown_drains_pending_observations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "stenographer"
            stenographer = CourtroomStenographer(root, clock=lambda: FIXED_TIME)
            original_append = stenographer.store.append_action
            entered = threading.Event()
            release = threading.Event()

            def blocked_append(*args: object, **kwargs: object) -> object:
                entered.set()
                if not release.wait(2):
                    raise RuntimeError("test release timed out")
                return original_append(*args, **kwargs)

            stenographer.store.append_action = blocked_append  # type: ignore[method-assign]
            self.assertTrue(
                stenographer.observe_text(
                    "actor.direct_response",
                    _actor(),
                    "drain me",
                    stimulus={"operator_message": "x"},
                    mode_id="analytical",
                    geometry_region_id="observatory",
                    attempt="direct_response",
                )
            )
            self.assertTrue(entered.wait(1))
            timer = threading.Timer(0.05, release.set)
            timer.start()
            try:
                self.assertTrue(stenographer.shutdown(2.0))
            finally:
                release.set()
                timer.cancel()
            self.assertEqual(stenographer.pending_observations, 0)
            self.assertEqual(list((root / "objects").glob(".*.tmp-*")), [])

    def test_cli_exit_helper_invokes_fail_passive_shutdown(self) -> None:
        class FakeStenographer:
            def __init__(self) -> None:
                self.calls = 0

            def shutdown(self) -> bool:
                self.calls += 1
                return True

        class FakeAPI:
            stenographer = FakeStenographer()

        api = FakeAPI()
        _drain_stenographer_on_exit(api)
        self.assertEqual(api.stenographer.calls, 1)

        class FailingStenographer:
            def shutdown(self) -> None:
                raise RuntimeError("shutdown failure must remain fail-passive")

        class FailingAPI:
            stenographer = FailingStenographer()

        _drain_stenographer_on_exit(FailingAPI())


if __name__ == "__main__":
    unittest.main()
