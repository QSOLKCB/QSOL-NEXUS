from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .canonical import canonical_json, sha256_ref


_OBJECT_REF = re.compile(r"^object:[0-9a-f]{64}$")


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
            "payload": copy.deepcopy(self.payload),
            "provenance": copy.deepcopy(self.provenance),
        }


class WorldStore:
    """Minimal content-addressed development world with optional file persistence."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root is not None else None
        self._objects: dict[str, WorldObject] = {}
        if self.root is not None:
            (self.root / "objects").mkdir(parents=True, exist_ok=True)

    def create_object(
        self,
        object_type: str,
        payload: dict[str, Any],
        provenance: dict[str, Any] | None = None,
    ) -> WorldObject:
        isolated_payload = copy.deepcopy(payload)
        isolated_provenance = copy.deepcopy(provenance or {})
        identity_body = {
            "object_type": object_type,
            "payload": isolated_payload,
            "provenance": isolated_provenance,
        }
        object_id = sha256_ref("object", identity_body)
        internal = WorldObject(object_id, object_type, isolated_payload, isolated_provenance)
        self._objects[object_id] = internal
        if self.root is not None:
            path = self.root / "objects" / f"{object_id.split(':', 1)[1]}.json"
            path.write_text(canonical_json(internal.as_dict()) + "\n", encoding="utf-8")
        return self._clone(internal)

    def inspect(self, object_ref: str) -> WorldObject:
        self._validate_object_ref(object_ref)
        if object_ref in self._objects:
            return self._clone(self._objects[object_ref])
        if self.root is not None:
            digest = object_ref.removeprefix("object:")
            path = self.root / "objects" / f"{digest}.json"
            if path.exists():
                raw = json.loads(path.read_text(encoding="utf-8"))
                internal = self._load_validated(object_ref, raw)
                self._objects[object_ref] = internal
                return self._clone(internal)
        raise KeyError(object_ref)

    def create_evidence_snapshot(
        self,
        question_ref: str,
        included_object_refs: list[str] | None = None,
        evidence_state: str = "UNTESTED",
    ) -> WorldObject:
        return self.create_object(
            "evidence_snapshot",
            {
                "question_ref": question_ref,
                "included_object_refs": list(included_object_refs or []),
                "evidence_state": evidence_state,
            },
            {"actor": "nexus"},
        )

    @staticmethod
    def _clone(obj: WorldObject) -> WorldObject:
        return WorldObject(
            obj.object_id,
            obj.object_type,
            copy.deepcopy(obj.payload),
            copy.deepcopy(obj.provenance),
        )

    @staticmethod
    def _validate_object_ref(object_ref: str) -> None:
        if not isinstance(object_ref, str) or _OBJECT_REF.fullmatch(object_ref) is None:
            raise ValueError("object_ref must be 'object:' followed by exactly 64 lowercase hex characters")

    @staticmethod
    def _load_validated(object_ref: str, raw: Any) -> WorldObject:
        if not isinstance(raw, dict):
            raise ValueError("persisted world object must be a JSON object")
        try:
            object_id = raw["object_id"]
            object_type = raw["object_type"]
            payload = raw["payload"]
            provenance = raw["provenance"]
        except KeyError as exc:
            raise ValueError(f"persisted world object missing field: {exc.args[0]}") from exc
        if not isinstance(object_type, str) or not isinstance(payload, dict) or not isinstance(provenance, dict):
            raise ValueError("persisted world object has invalid field types")
        expected = sha256_ref(
            "object",
            {"object_type": object_type, "payload": payload, "provenance": provenance},
        )
        if object_id != object_ref or expected != object_ref:
            raise ValueError("persisted world object failed content-address verification")
        return WorldObject(
            object_ref,
            object_type,
            copy.deepcopy(payload),
            copy.deepcopy(provenance),
        )
