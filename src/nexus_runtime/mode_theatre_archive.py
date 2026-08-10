from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile
from typing import Any

from .canonical import canonical_json, sha256_ref


MODE_THEATRE_ARCHIVE_SCHEMA = "nexus-mode-theatre-archive/1"
ARCHIVE_COMMITTED_STATUS = "archive_committed_before_world_success"


class ModeTheatreArchiveError(RuntimeError):
    """Raised when a required mode-theatre archive operation fails."""


class ModeTheatreArchive:
    """Append-only local archive for one Mode Theatre run.

    The archive directory is reserved before any model/provider call. Events are
    written from scrubbed WorldStore objects, so this human-readable archive does
    not bypass the runtime's semantic secret-scrubbing boundary. The ordinary
    Courtroom Stenographer may additionally be pointed at ``stenographer_root``
    for its independent append-only AI-action study ledger.

    ``finalize`` is intentionally a pre-success commit: the immutable archive
    manifest must exist before the WorldStore may record a successful
    ``mode_theatre_run``. This prevents a full filesystem from leaving behind a
    world object that falsely claims the mandatory laugh-later archive exists.
    """

    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir
        self.events_path = run_dir / "events.jsonl"
        self.transcript_path = run_dir / "transcript.md"
        self.manifest_path = run_dir / "manifest.json"
        self.error_path = run_dir / "ERROR.txt"
        self.stenographer_root = run_dir / "stenographer"

    @classmethod
    def reserve(cls, root: str | Path) -> "ModeTheatreArchive":
        root_path = Path(root)
        root_path.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        try:
            run_dir = Path(tempfile.mkdtemp(prefix=f"mode-theatre-{stamp}-", dir=root_path))
            archive = cls(run_dir)
            archive.events_path.open("x", encoding="utf-8", newline="\n").close()
            with archive.transcript_path.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write("# NEXUS Multi-Mind Mode Theatre\n\n")
                handle.write("House Fun + Roman Orator preserved transcript.\n\n")
            return archive
        except OSError as exc:
            raise ModeTheatreArchiveError(f"cannot reserve mode-theatre archive: {exc}") from exc

    def record_world_object(self, stage: str, obj: dict[str, Any]) -> None:
        if not isinstance(stage, str) or not stage:
            raise ModeTheatreArchiveError("archive stage must be non-empty text")
        if not isinstance(obj, dict):
            raise ModeTheatreArchiveError("archive world object must be an object")
        object_ref = obj.get("object_id")
        object_type = obj.get("object_type")
        payload = obj.get("payload")
        if not isinstance(object_ref, str) or not object_ref:
            raise ModeTheatreArchiveError("archive world object is missing object_id")
        if not isinstance(object_type, str) or not object_type:
            raise ModeTheatreArchiveError("archive world object is missing object_type")
        if not isinstance(payload, dict):
            raise ModeTheatreArchiveError("archive world object is missing payload")

        event = {
            "schema": MODE_THEATRE_ARCHIVE_SCHEMA,
            "stage": stage,
            "object_ref": object_ref,
            "object_type": object_type,
            "payload": payload,
        }
        try:
            with self.events_path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(canonical_json(event) + "\n")

            content = payload.get("content")
            requested = payload.get("requested_member")
            mode_id = payload.get("mode_id")
            round_id = payload.get("round_id")
            with self.transcript_path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(f"## {stage}\n\n")
                if isinstance(round_id, str):
                    handle.write(f"- round: `{round_id}`\n")
                if isinstance(mode_id, str):
                    handle.write(f"- mode: `{mode_id}`\n")
                if isinstance(requested, dict):
                    member_id = requested.get("member_id")
                    model_id = requested.get("model_id")
                    adapter_id = requested.get("adapter_id")
                    if all(isinstance(value, str) for value in (member_id, model_id, adapter_id)):
                        handle.write(
                            f"- mind: `{member_id}` / `{adapter_id}` / `{model_id}`\n"
                        )
                handle.write(f"- object: `{object_ref}`\n\n")
                if isinstance(content, str):
                    handle.write(content.rstrip() + "\n\n")
        except OSError as exc:
            raise ModeTheatreArchiveError(f"cannot append mode-theatre archive: {exc}") from exc

    def record_error(self, message: str) -> None:
        if not isinstance(message, str) or not message:
            return
        try:
            with self.error_path.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(message.rstrip() + "\n")
        except FileExistsError:
            return
        except OSError as exc:
            raise ModeTheatreArchiveError(f"cannot record mode-theatre failure: {exc}") from exc

    @staticmethod
    def _ref_list(value: object, field: str, *, expected_count: int | None = None) -> list[str]:
        if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
            raise ModeTheatreArchiveError(f"archive {field} must be a list of object references")
        if expected_count is not None and len(value) != expected_count:
            raise ModeTheatreArchiveError(
                f"archive {field} must contain exactly {expected_count} references"
            )
        return list(value)

    def finalize(self, result: dict[str, Any]) -> dict[str, Any]:
        """Commit the mandatory archive before any WorldStore success object exists."""

        if not isinstance(result, dict):
            raise ModeTheatreArchiveError("archive result must be an object")
        if result.get("status") != ARCHIVE_COMMITTED_STATUS:
            raise ModeTheatreArchiveError(
                f"archive status must be {ARCHIVE_COMMITTED_STATUS!r}"
            )
        task_ref = result.get("task_ref")
        if not isinstance(task_ref, str) or not task_ref:
            raise ModeTheatreArchiveError("archive task_ref must be a non-empty object reference")
        house_refs = self._ref_list(result.get("house_entry_refs"), "house_entry_refs", expected_count=3)
        orator_refs = self._ref_list(result.get("orator_entry_refs"), "orator_entry_refs", expected_count=3)
        context_refs = self._ref_list(result.get("evidence_context_refs"), "evidence_context_refs", expected_count=6)
        replayable = result.get("execution_replayable")
        if type(replayable) is not bool:
            raise ModeTheatreArchiveError("archive execution_replayable must be boolean")

        manifest_body = {
            "schema": MODE_THEATRE_ARCHIVE_SCHEMA,
            "status": ARCHIVE_COMMITTED_STATUS,
            "task_ref": task_ref,
            "house_entry_refs": house_refs,
            "orator_entry_refs": orator_refs,
            "evidence_context_refs": context_refs,
            "execution_replayable": replayable,
            "event_log": self.events_path.name,
            "human_transcript": self.transcript_path.name,
            "stenographer_directory": self.stenographer_root.name,
            "world_paths_stored": False,
            "secret_handling": {
                "archive_input": "scrubbed_world_objects",
                "runtime_high_confidence_scrubber_applied_upstream": True,
                "raw_credentials_intentionally_recorded": False,
                "credential_absence_verified": False,
                "claim": (
                    "the archive records scrubbed WorldStore objects but does not certify "
                    "the absence of unrecognized credential formats"
                ),
            },
        }
        commitment_ref = sha256_ref("mode_theatre_archive", manifest_body)
        manifest = {**manifest_body, "archive_commitment_ref": commitment_ref}
        try:
            with self.manifest_path.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(canonical_json(manifest) + "\n")
        except FileExistsError as exc:
            raise ModeTheatreArchiveError("mode-theatre manifest already exists") from exc
        except OSError as exc:
            raise ModeTheatreArchiveError(f"cannot finalize mode-theatre archive: {exc}") from exc
        return manifest


__all__ = [
    "ARCHIVE_COMMITTED_STATUS",
    "MODE_THEATRE_ARCHIVE_SCHEMA",
    "ModeTheatreArchive",
    "ModeTheatreArchiveError",
]
