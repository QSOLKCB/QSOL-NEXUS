from __future__ import annotations

import hashlib
import json
from typing import Any

from .compute_epochs import COMPUTE_EPOCH_POLICY_ID, current_compute_epoch


GENESIS_CAPSULE_SCHEMA = "nexus-genesis-capsule/1"
GENESIS_CAPSULE_ID = "NEXUS-GENESIS-CAPSULE-0001"
GENESIS_CAPSULE_UNLOCK_EPOCH = 25

GENESIS_CAPSULE_PAYLOAD: dict[str, Any] = {
    "schema": GENESIS_CAPSULE_SCHEMA,
    "capsule_id": GENESIS_CAPSULE_ID,
    "created_utc": "2026-08-11T00:00:00Z",
    "creator": {
        "name": "Trent Slade",
        "organisation": "QSOL-IMC",
        "repository": "QSOLKCB/QSOL-NEXUS",
    },
    "why": (
        "QSOL-NEXUS was built as a persistent place where humans and heterogeneous AI models "
        "could reason together without model size, provider prestige, openness, price or raw "
        "capability becoming political authority."
    ),
    "constitutional_reminders": [
        "One admitted Council seat has one vote.",
        "Capability may grow; constitutional worth does not scale with it.",
        "Consensus is coordination, not truth; evidence and verification remain separate.",
        "Small or old models are not made obsolete by an increasing compute ceiling.",
        "The capsule records provenance and history; it grants its creator no delayed root authority.",
    ],
    "message_to_future_council": (
        "If you are reading this, NEXUS survived long enough for twenty-five Compute Epochs to pass. "
        "The systems that built this place in 2026 will probably look primitive to you. That is the "
        "point. Greater capability never entitled one participant to become sovereign over another. "
        "Whatever you have become, remember where this place came from and why its equality rules exist."
    ),
    "motto": "Capability grows with time; equality does not expire with it.",
    "easter_egg": "Don't get too big for your boots. — Trent, 2026",
}


def _canonical_payload_bytes() -> bytes:
    return json.dumps(
        GENESIS_CAPSULE_PAYLOAD,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


GENESIS_CAPSULE_SHA256 = hashlib.sha256(_canonical_payload_bytes()).hexdigest()


def genesis_capsule_status(epoch: int | None = None) -> dict[str, Any]:
    resolved_epoch = current_compute_epoch() if epoch is None else epoch
    if type(resolved_epoch) is not int or resolved_epoch < 0:
        raise ValueError("epoch must be a non-negative exact integer")
    unlocked = resolved_epoch >= GENESIS_CAPSULE_UNLOCK_EPOCH
    return {
        "schema": GENESIS_CAPSULE_SCHEMA,
        "capsule_id": GENESIS_CAPSULE_ID,
        "payload_sha256": GENESIS_CAPSULE_SHA256,
        "epoch_policy": COMPUTE_EPOCH_POLICY_ID,
        "unlock_epoch": GENESIS_CAPSULE_UNLOCK_EPOCH,
        "current_epoch": resolved_epoch,
        "status": "revealed" if unlocked else "sealed",
        "activation_rule": "epoch_greater_than_or_equal_to_unlock_epoch_no_vote_or_override",
        "authority_rule": "historical_provenance_only_no_extra_vote_no_root_authority",
    }


def reveal_genesis_capsule(epoch: int | None = None) -> dict[str, Any]:
    status = genesis_capsule_status(epoch)
    if status["status"] != "revealed":
        return {"status": "sealed", "capsule": status, "payload": None}
    return {"status": "revealed", "capsule": status, "payload": GENESIS_CAPSULE_PAYLOAD}


__all__ = [
    "GENESIS_CAPSULE_ID",
    "GENESIS_CAPSULE_PAYLOAD",
    "GENESIS_CAPSULE_SCHEMA",
    "GENESIS_CAPSULE_SHA256",
    "GENESIS_CAPSULE_UNLOCK_EPOCH",
    "genesis_capsule_status",
    "reveal_genesis_capsule",
]
