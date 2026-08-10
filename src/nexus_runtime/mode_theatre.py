from __future__ import annotations

from typing import Any, Iterable, Protocol

from .mode_theatre_archive import ModeTheatreArchive
from .three_minds_validation import validate_members, validate_mode_catalog
from .version import PROTOCOL_VERSION


MODE_THEATRE_SCHEMA = "nexus-mode-theatre/1"
HOUSE_MODE_ID = "house_fun"
ORATOR_MODE_ID = "roman_orator"
MAX_THEATRE_PROMPT_CHARS = 1_500

DEFAULT_HOUSE_CASE = (
    "Fictional case: the Observatory's ancient printer emits a perfect ECG trace only "
    "when somebody says YAML, turns blue during karaoke, and refuses to print unless "
    "the operator diagnoses it with a completely unreasonable zebra. Diagnose the machine, not a person."
)
DEFAULT_ORATOR_MOTION = (
    "Resolved: after the printer incident, YAML indentation remains the final pillar "
    "holding civilisation together, and the maintainers must defend it before the Forum."
)


class NexusHandle(Protocol):
    def handle(self, request: dict[str, Any]) -> dict[str, Any]: ...


class ModeTheatreError(RuntimeError):
    """Raised when the multi-mind mode-theatre demonstration fails closed."""


def _call(api: NexusHandle, request: dict[str, Any]) -> dict[str, Any]:
    operation = str(request.get("operation", "unknown"))
    response = api.handle(request)
    if response.get("status") in {"ok", "verified"}:
        return response
    error = response.get("error")
    if isinstance(error, dict):
        code = error.get("code", "unknown_error")
        message = error.get("message", "operation failed")
        raise ModeTheatreError(f"{operation} failed: {code}: {message}")
    raise ModeTheatreError(f"{operation} failed without a structured error")


def _validate_prompt(value: str | None, *, default: str, field: str) -> str:
    if value is None:
        value = default
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be non-empty text")
    if len(value) > MAX_THEATRE_PROMPT_CHARS:
        raise ValueError(f"{field} must be at most {MAX_THEATRE_PROMPT_CHARS} characters")
    return value.strip()


def _create_world_object(
    api: NexusHandle,
    object_type: str,
    payload: dict[str, Any],
    provenance: dict[str, Any],
) -> dict[str, Any]:
    response = _call(
        api,
        {
            "operation": "world.create",
            "object_type": object_type,
            "payload": payload,
            "provenance": provenance,
        },
    )
    obj = response.get("object")
    if not isinstance(obj, dict) or not isinstance(obj.get("object_id"), str):
        raise ModeTheatreError("world.create returned an invalid object shape")
    return obj


def _chat(
    api: NexusHandle,
    member: dict[str, Any],
    *,
    message: str,
    mode_id: str,
    evidence_refs: list[str],
) -> dict[str, Any]:
    response = _call(
        api,
        {
            "operation": "actor.chat",
            "member": member,
            "message": message,
            "mode": mode_id,
            "evidence_refs": evidence_refs,
        },
    )
    if not isinstance(response.get("response"), str):
        raise ModeTheatreError("actor.chat returned no text response")
    return response


def _stage_object(
    api: NexusHandle,
    *,
    sequence_index: int,
    round_id: str,
    round_position: int,
    role: str,
    requested_member: dict[str, str],
    chat: dict[str, Any],
    task_ref: str,
    previous_stage_ref: str | None,
    evidence_refs: list[str],
) -> dict[str, Any]:
    payload = {
        "schema": MODE_THEATRE_SCHEMA,
        "sequence_index": sequence_index,
        "round_id": round_id,
        "round_position": round_position,
        "role": role,
        "task_ref": task_ref,
        "previous_stage_ref": previous_stage_ref,
        "requested_member": dict(requested_member),
        "effective_member": {
            "member_id": chat.get("member_id"),
            "model_id": chat.get("model_id"),
        },
        "mode_id": chat.get("mode_id"),
        "geometry_region_id": chat.get("geometry_region_id"),
        "evidence_refs_used": list(evidence_refs),
        "content": chat["response"],
        "failsafe_replaced": chat.get("failsafe_replacement") is not None,
        "council_vote": False,
        "additional_votes_created": 0,
    }
    return _create_world_object(
        api,
        "mode_theatre_entry",
        payload,
        {
            "actor": requested_member["member_id"],
            "model_id": requested_member["model_id"],
            "adapter_id": requested_member["adapter_id"],
            "mode_theatre_round": round_id,
            "mode_theatre_role": role,
        },
    )


def run_mode_theatre_demo(
    api: NexusHandle,
    archive: ModeTheatreArchive,
    *,
    members: Iterable[dict[str, Any]],
    house_case: str | None = None,
    orator_motion: str | None = None,
) -> dict[str, Any]:
    """Run House Fun then Roman Orator with three equal multi-mind participants.

    The House round runs A -> B -> C against one explicitly fictional case. The
    Orator round deliberately reverses the order C -> B -> A so the model that
    closed the diagnostic bit has to open the Forum. Every contribution becomes
    immutable WorldStore evidence and is also appended to a required local
    archive. The demo is not a Council vote and creates no additional authority.
    """

    roster, public_roster_tuple = validate_members(
        members,
        context="mode-theatre demo",
    )
    public_roster = [dict(member) for member in public_roster_tuple]
    validated_house = _validate_prompt(
        house_case,
        default=DEFAULT_HOUSE_CASE,
        field="house_case",
    )
    validated_orator = _validate_prompt(
        orator_motion,
        default=DEFAULT_ORATOR_MOTION,
        field="orator_motion",
    )

    modes_response = _call(api, {"operation": "world.modes"})
    modes = modes_response.get("modes")
    validate_mode_catalog(HOUSE_MODE_ID, modes)
    validate_mode_catalog(ORATOR_MODE_ID, modes)

    task = _create_world_object(
        api,
        "mode_theatre_task",
        {
            "schema": MODE_THEATRE_SCHEMA,
            "roster": public_roster,
            "house_mode_id": HOUSE_MODE_ID,
            "orator_mode_id": ORATOR_MODE_ID,
            "house_case": validated_house,
            "orator_motion": validated_orator,
            "house_order": [member["member_id"] for member in public_roster],
            "orator_order": [
                public_roster[2]["member_id"],
                public_roster[1]["member_id"],
                public_roster[0]["member_id"],
            ],
            "content": (
                "NEXUS Mode Theatre task.\n"
                f"house_case={validated_house}\n"
                f"orator_motion={validated_orator}\n"
                "rules=fictional_house_case; original_banter; rhetoric_is_not_evidence; "
                "one_mind_one_identity; no_council_vote."
            ),
            "claim_boundary": (
                "entertainment and cognitive-mode demonstration only; the House round is fictional "
                "and the Orator round changes style rather than evidence or authority"
            ),
        },
        {"actor": "nexus_mode_theatre_demo", "mode_theatre_stage": "task"},
    )
    archive.record_world_object("task", task)
    task_ref = task["object_id"]

    house_refs: list[str] = []
    all_stage_refs: list[str] = []
    previous_ref: str | None = None
    sequence_index = 1
    house_roles = ("whiteboard_open", "zebra_rebuttal", "fictional_reveal")

    for position, member_index in enumerate((0, 1, 2), start=1):
        evidence_refs = [task_ref, *house_refs]
        chat = _chat(
            api,
            roster[member_index],
            message=(
                "Enter House Fun Mode. Read the attached fictional machine case and any earlier "
                "House-round entries. Keep the case explicitly fictional, make the diagnostic-drama "
                "banter original, and diagnose the machine rather than a real person. Add or challenge "
                "zebras, preserve earlier jokes in evidence, and remember that comedy is not evidence."
            ),
            mode_id=HOUSE_MODE_ID,
            evidence_refs=evidence_refs,
        )
        stage = _stage_object(
            api,
            sequence_index=sequence_index,
            round_id="house_fun",
            round_position=position,
            role=house_roles[position - 1],
            requested_member=public_roster[member_index],
            chat=chat,
            task_ref=task_ref,
            previous_stage_ref=previous_ref,
            evidence_refs=evidence_refs,
        )
        archive.record_world_object(f"house_{position}_{public_roster[member_index]['member_id']}", stage)
        previous_ref = stage["object_id"]
        house_refs.append(previous_ref)
        all_stage_refs.append(previous_ref)
        sequence_index += 1

    orator_refs: list[str] = []
    orator_roles = ("forum_open", "forum_rebuttal", "grand_peroration")
    for position, member_index in enumerate((2, 1, 0), start=1):
        evidence_refs = [task_ref, *house_refs, *orator_refs]
        chat = _chat(
            api,
            roster[member_index],
            message=(
                "Enter Roman Orator Mode. Read the task's motion, the complete House Fun round, and "
                "any earlier Forum speeches. Deliver an original structured oration or rebuttal. You "
                "may use the House transcript as comic ammunition, but do not invent quotations or "
                "Latin and do not turn eloquence, applause, confidence, or ridicule into evidence."
            ),
            mode_id=ORATOR_MODE_ID,
            evidence_refs=evidence_refs,
        )
        stage = _stage_object(
            api,
            sequence_index=sequence_index,
            round_id="roman_orator",
            round_position=position,
            role=orator_roles[position - 1],
            requested_member=public_roster[member_index],
            chat=chat,
            task_ref=task_ref,
            previous_stage_ref=previous_ref,
            evidence_refs=evidence_refs,
        )
        archive.record_world_object(f"orator_{position}_{public_roster[member_index]['member_id']}", stage)
        previous_ref = stage["object_id"]
        orator_refs.append(previous_ref)
        all_stage_refs.append(previous_ref)
        sequence_index += 1

    replayable = all(member["adapter_id"] == "mock" for member in public_roster)
    run = _create_world_object(
        api,
        "mode_theatre_run",
        {
            "schema": MODE_THEATRE_SCHEMA,
            "task_ref": task_ref,
            "house_entry_refs": house_refs,
            "orator_entry_refs": orator_refs,
            "lineage_refs": [task_ref, *all_stage_refs],
            "roster": public_roster,
            "house_order": [member["member_id"] for member in public_roster],
            "orator_order": [
                public_roster[2]["member_id"],
                public_roster[1]["member_id"],
                public_roster[0]["member_id"],
            ],
            "modes_exercised": [HOUSE_MODE_ID, ORATOR_MODE_ID],
            "mind_count": 3,
            "entry_count": 6,
            "logs_required": True,
            "archive_content_source": "scrubbed_world_objects",
            "stenographer_compatible": True,
            "council_vote": False,
            "additional_votes_created": 0,
            "execution_replayable": replayable,
            "content": (
                "Three minds completed House Fun and Roman Orator rounds; six attributed "
                "responses were preserved in immutable lineage and the required local archive."
            ),
            "claim_boundary": (
                "demonstrates cognitive-mode framing, multi-mind evidence continuity and durable logging; "
                "does not establish truth, diagnosis, provider superiority, or rhetorical authority"
            ),
        },
        {"actor": "nexus_mode_theatre_demo", "mode_theatre_stage": "completed_run"},
    )
    archive.record_world_object("run", run)
    run_ref = run["object_id"]

    receipt = _create_world_object(
        api,
        "receipt",
        {
            "operation": "mode_theatre.demo",
            "input_refs": [task_ref, *all_stage_refs],
            "result_ref": run_ref,
            "replayable": replayable,
            "protocol": PROTOCOL_VERSION,
        },
        {"actor": "nexus_mode_theatre_demo"},
    )
    archive.record_world_object("receipt", receipt)
    receipt_ref = receipt["object_id"]
    receipt_status = _call(api, {"operation": "receipt.verify", "receipt_ref": receipt_ref})

    result = {
        "status": "ok",
        "schema": MODE_THEATRE_SCHEMA,
        "roster": public_roster,
        "task_ref": task_ref,
        "house_entry_refs": house_refs,
        "orator_entry_refs": orator_refs,
        "run_ref": run_ref,
        "receipt_ref": receipt_ref,
        "receipt_status": receipt_status["status"],
        "execution_replayable": replayable,
        "additional_votes_created": 0,
    }
    archive_manifest = archive.finalize(result)
    return {
        **result,
        "archive_dir": str(archive.run_dir),
        "archive_manifest": archive_manifest,
    }


__all__ = [
    "DEFAULT_HOUSE_CASE",
    "DEFAULT_ORATOR_MOTION",
    "HOUSE_MODE_ID",
    "MAX_THEATRE_PROMPT_CHARS",
    "MODE_THEATRE_SCHEMA",
    "ModeTheatreError",
    "ORATOR_MODE_ID",
    "run_mode_theatre_demo",
]
