from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile
from typing import Any

from .canonical import canonical_json


MODE_THEATRE_ARCHIVE_SCHEMA = "nexus-mode-theatre-archive/1"


class ModeTheatreArchiveError(RuntimeError):
    """Raised when a required mode-theatre archive operation fails."""


class ModeTheatreArchive:
    """Append-only local archive for one Mode Theatre run.

    The archive directory is reserved before any model/provider call. Events are
    written from scrubbed WorldStore objects, so this human-readable archive does
    not bypass the runtime's semantic secret-scrubbing boundary. The ordinary
    Courtroom Stenographer may additionally be pointed at ``stenographer_root``
    for its independent append-only AI-action study ledger.
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

    def finalize(self, result: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(result, dict):
            raise ModeTheatreArchiveError("archive result must be an object")
        manifest = {
            "schema": MODE_THEATRE_ARCHIVE_SCHEMA,
            "status": result.get("status"),
            "run_ref": result.get("run_ref"),
            "receipt_ref": result.get("receipt_ref"),
            "receipt_status": result.get("receipt_status"),
            "event_log": self.events_path.name,
            "human_transcript": self.transcript_path.name,
            "stenographer_directory": self.stenographer_root.name,
            "world_paths_stored": False,
            "credentials_stored": False,
        }
        try:
            with self.manifest_path.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(canonical_json(manifest) + "\n")
        except FileExistsError as exc:
            raise ModeTheatreArchiveError("mode-theatre manifest already exists") from exc
        except OSError as exc:
            raise ModeTheatreArchiveError(f"cannot finalize mode-theatre archive: {exc}") from exc
        return manifest


__all__ = [
    "MODE_THEATRE_ARCHIVE_SCHEMA",
    "ModeTheatreArchive",
    "ModeTheatreArchiveError",
]
