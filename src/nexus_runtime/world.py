from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .canonical import canonical_json, sha256_ref


@dataclass(frozen=True)
class WorldObject:
    object_id: str
    object_type: str
    payload: dict[str, Any]
    provenance: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "object_id": self.object_id,
            "object_type": self.object_type,
            "payload": self.payload,
            "provenance": self.provenance,
        }


class WorldStore:
    """Minimal content-addressed development world with optional file persistence."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root is not None else None
        self._objects: dict[str, WorldObject] = {}
        if self.root is not None:
            (self.root / "objects").mkdir(parents=True, exist_ok=True)

    def create_object(self, object_type: str, payload: dict[str, Any], provenance: dict[str, Any] | None = None) -> WorldObject:
        provenance = dict(provenance or {})
        identity_body = {"object_type": object_type, "payload": payload, "provenance": provenance}
        object_id = sha256_ref("object", identity_body)
        obj = WorldObject(object_id, object_type, dict(payload), provenance)
        self._objects[object_id] = obj
        if self.root is not None:
            path = self.root / "objects" / f"{object_id.split(':', 1)[1]}.json"
            path.write_text(canonical_json(obj.as_dict()) + "\n", encoding="utf-8")
        return obj

    def inspect(self, object_ref: str) -> WorldObject:
        if object_ref in self._objects:
            return self._objects[object_ref]
        if self.root is not None and object_ref.startswith("object:"):
            path = self.root / "objects" / f"{object_ref.split(':', 1)[1]}.json"
            if path.exists():
                raw = json.loads(path.read_text(encoding="utf-8"))
                obj = WorldObject(raw["object_id"], raw["object_type"], raw["payload"], raw["provenance"])
                self._objects[object_ref] = obj
                return obj
        raise KeyError(object_ref)

    def create_evidence_snapshot(self, question_ref: str, included_object_refs: list[str] | None = None, evidence_state: str = "UNTESTED") -> WorldObject:
        return self.create_object(
            "evidence_snapshot",
            {
                "question_ref": question_ref,
                "included_object_refs": list(included_object_refs or []),
                "evidence_state": evidence_state,
            },
            {"actor": "nexus"},
        )
