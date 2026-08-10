from __future__ import annotations

from typing import Any, Iterable, Protocol

from .mode_theatre_archive import ARCHIVE_COMMITTED_STATUS, ModeTheatreArchive
from .three_minds_validation import validate_members, validate_mode_catalog
from .version import PROTOCOL_VERSION


MODE_THEATRE_SCHEMA = "nexus-mode-theatre/1"
HOUSE_MODE_ID = "house_fun"
ORATOR_MODE_ID = "roman_orator"
MAX_THEATRE_PROMPT_CHARS = 1_500
MAX_MODE_THEATRE_CONTEXT_CHARS = 2_600
MAX_TASK_CONTEXT_FIELD_CHARS = 300
MAX_ENTRY_CONTEXT_CHARS = 220

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


def _bounded_excerpt(value: object, maximum: int) -> str:
    if not isinstance(value, str):
        return ""
    compact = " ".join(value.split())
    if len(compact) <= maximum:
        return compact
    marker = " [excerpt truncated]"
    keep = max(0, maximum - len(marker))
    return compact[:keep] + marker


def _context_content(task: dict[str, Any], prior_entries: list[dict[str, Any]]) -> str:
    task_payload = task.get("payload")
    if not isinstance(task_payload, dict):
        raise ModeTheatreError("mode-theatre task has an invalid payload")
    task_ref = task.get("object_id")
    if not isinstance(task_ref, str):
        raise ModeTheatreError("mode-theatre task has no object reference")

    sections = [
        "NEXUS Mode Theatre bounded evidence view.",
        "Every source_ref listed below is represented by a bounded excerpt; source refs remain authoritative.",
        f"source_ref={task_ref} kind=task",
        f"house_case={_bounded_excerpt(task_payload.get('house_case'), MAX_TASK_CONTEXT_FIELD_CHARS)}",
        f"orator_motion={_bounded_excerpt(task_payload.get('orator_motion'), MAX_TASK_CONTEXT_FIELD_CHARS)}",
    ]

    for entry in prior_entries:
        entry_ref = entry.get("object_id")
        payload = entry.get("payload")
        if not isinstance(entry_ref, str) or not isinstance(payload, dict):
            raise ModeTheatreError("mode-theatre entry has an invalid evidence shape")
        requested = payload.get("requested_member")
        member_id = requested.get("member_id") if isinstance(requested, dict) else "unknown"
        sections.extend(
            [
                (
                    f"source_ref={entry_ref} kind=entry round={payload.get('round_id')} "
                    f"role={payload.get('role')} member={member_id}"
                ),
                f"excerpt={_bounded_excerpt(payload.get('content'), MAX_ENTRY_CONTEXT_CHARS)}",
            ]
        )

    content = "\n".join(sections)
    if len(content) > MAX_MODE_THEATRE_CONTEXT_CHARS:
        raise ModeTheatreError(
            "bounded mode-theatre evidence context exceeded its admitted character budget"
        )
    return content


def _evidence_context_object(
    api: NexusHandle,
    *,
    task: dict[str, Any],
    prior_entries: list[dict[str, Any]],
    audience_round: str,
    audience_position: int,
) -> dict[str, Any]:
    task_ref = task["object_id"]
    source_refs = [task_ref, *[entry["object_id"] for entry in prior_entries]]
    return _create_world_object(
        api,
        "mode_theatre_evidence_context",
        {
            "schema": MODE_THEATRE_SCHEMA,
            "audience_round": audience_round,
            "audience_position": audience_position,
            "source_refs": source_refs,
            "source_count": len(source_refs),
            "all_sources_represented": True,
            "excerpt_policy": {
                "task_field_chars": MAX_TASK_CONTEXT_FIELD_CHARS,
                "entry_chars": MAX_ENTRY_CONTEXT_CHARS,
                "total_chars": MAX_MODE_THEATRE_CONTEXT_CHARS,
            },
            "content": _context_content(task, prior_entries),
            "claim_boundary": (
                "bounded excerpts guarantee representation of every listed source; they do not "
                "replace the immutable source objects or claim to contain every source character"
            ),
        },
        {
            "actor": "nexus_mode_theatre_demo",
            "mode_theatre_stage": "bounded_evidence_context",
        },
    )


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
    source_evidence_refs: list[str],
    evidence_context_ref: str,
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
        "source_evidence_refs": list(source_evidence_refs),
        "evidence_context_ref": evidence_context_ref,
        "evidence_refs_used": [evidence_context_ref],
        "evidence_context_all_sources_represented": True,
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

    Before each actor call NEXUS creates one bounded evidence-context object that
    contains an excerpt from every required source. This avoids the generic
    evidence builder's oldest-first global budget silently dropping later House
    or Forum contributions while still keeping immutable source refs explicit.
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
    house_entries: list[dict[str, Any]] = []
    orator_refs: list[str] = []
    orator_entries: list[dict[str, Any]] = []
    context_refs: list[str] = []
    lineage_refs: list[str] = [task_ref]
    all_stage_refs: list[str] = []
    previous_ref: str | None = None
    sequence_index = 1
    house_roles = ("whiteboard_open", "zebra_rebuttal", "fictional_reveal")

    for position, member_index in enumerate((0, 1, 2), start=1):
        source_entries = list(house_entries)
        source_refs = [task_ref, *[entry["object_id"] for entry in source_entries]]
        context = _evidence_context_object(
            api,
            task=task,
            prior_entries=source_entries,
            audience_round=HOUSE_MODE_ID,
            audience_position=position,
        )
        context_ref = context["object_id"]
        context_refs.append(context_ref)
        lineage_refs.append(context_ref)
        archive.record_world_object(f"context_house_{position}", context)

        chat = _chat(
            api,
            roster[member_index],
            message=(
                "Enter House Fun Mode. The attached bounded evidence view contains the fictional "
                "machine task and an excerpt from every earlier House entry, with immutable source "
                "refs preserved. Keep the case explicitly fictional, make the diagnostic-drama "
                "banter original, diagnose the machine rather than a real person, and remember that "
                "comedy is not evidence."
            ),
            mode_id=HOUSE_MODE_ID,
            evidence_refs=[context_ref],
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
            source_evidence_refs=source_refs,
            evidence_context_ref=context_ref,
        )
        archive.record_world_object(f"house_{position}_{public_roster[member_index]['member_id']}", stage)
        previous_ref = stage["object_id"]
        house_refs.append(previous_ref)
        house_entries.append(stage)
        all_stage_refs.append(previous_ref)
        lineage_refs.append(previous_ref)
        sequence_index += 1

    orator_roles = ("forum_open", "forum_rebuttal", "grand_peroration")
    for position, member_index in enumerate((2, 1, 0), start=1):
        source_entries = [*house_entries, *orator_entries]
        source_refs = [task_ref, *[entry["object_id"] for entry in source_entries]]
        context = _evidence_context_object(
            api,
            task=task,
            prior_entries=source_entries,
            audience_round=ORATOR_MODE_ID,
            audience_position=position,
        )
        context_ref = context["object_id"]
        context_refs.append(context_ref)
        lineage_refs.append(context_ref)
        archive.record_world_object(f"context_orator_{position}", context)

        chat = _chat(
            api,
            roster[member_index],
            message=(
                "Enter Roman Orator Mode. The attached bounded evidence view contains the task and "
                "an excerpt from every House contribution plus every earlier Forum speech. Deliver "
                "an original structured oration or rebuttal. You may use the House material as comic "
                "ammunition, but do not invent quotations or Latin and do not turn eloquence, applause, "
                "confidence, or ridicule into evidence."
            ),
            mode_id=ORATOR_MODE_ID,
            evidence_refs=[context_ref],
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
            source_evidence_refs=source_refs,
            evidence_context_ref=context_ref,
        )
        archive.record_world_object(f"orator_{position}_{public_roster[member_index]['member_id']}", stage)
        previous_ref = stage["object_id"]
        orator_refs.append(previous_ref)
        orator_entries.append(stage)
        all_stage_refs.append(previous_ref)
        lineage_refs.append(previous_ref)
        sequence_index += 1

    replayable = all(member["adapter_id"] == "mock" for member in public_roster)

    # Mandatory logs are committed before the WorldStore is allowed to record a
    # successful run object. If this fails, the six model responses remain
    # ordinary prior objects but no `mode_theatre_run` or verified success
    # receipt can exist.
    archive_manifest = archive.finalize(
        {
            "status": ARCHIVE_COMMITTED_STATUS,
            "task_ref": task_ref,
            "house_entry_refs": list(house_refs),
            "orator_entry_refs": list(orator_refs),
            "evidence_context_refs": list(context_refs),
            "execution_replayable": replayable,
        }
    )
    archive_commitment_ref = archive_manifest["archive_commitment_ref"]

    run = _create_world_object(
        api,
        "mode_theatre_run",
        {
            "schema": MODE_THEATRE_SCHEMA,
            "task_ref": task_ref,
            "house_entry_refs": house_refs,
            "orator_entry_refs": orator_refs,
            "evidence_context_refs": context_refs,
            "lineage_refs": lineage_refs,
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
            "evidence_context_count": 6,
            "logs_required": True,
            "archive_status": ARCHIVE_COMMITTED_STATUS,
            "archive_commitment_ref": archive_commitment_ref,
            "archive_content_source": "scrubbed_world_objects",
            "stenographer_compatible": True,
            "council_vote": False,
            "additional_votes_created": 0,
            "execution_replayable": replayable,
            "content": (
                "Three minds completed House Fun and Roman Orator rounds; six attributed "
                "responses and six bounded all-source evidence views were preserved before "
                "the successful run object was recorded."
            ),
            "claim_boundary": (
                "demonstrates cognitive-mode framing, bounded all-source evidence continuity and durable logging; "
                "does not establish truth, diagnosis, provider superiority, or rhetorical authority"
            ),
        },
        {"actor": "nexus_mode_theatre_demo", "mode_theatre_stage": "completed_run"},
    )
    run_ref = run["object_id"]

    receipt = _create_world_object(
        api,
        "receipt",
        {
            "operation": "mode_theatre.demo",
            "input_refs": lineage_refs,
            "result_ref": run_ref,
            "replayable": replayable,
            "protocol": PROTOCOL_VERSION,
        },
        {"actor": "nexus_mode_theatre_demo"},
    )
    receipt_ref = receipt["object_id"]
    receipt_status = _call(api, {"operation": "receipt.verify", "receipt_ref": receipt_ref})

    result = {
        "status": "ok",
        "schema": MODE_THEATRE_SCHEMA,
        "roster": public_roster,
        "task_ref": task_ref,
        "house_entry_refs": house_refs,
        "orator_entry_refs": orator_refs,
        "evidence_context_refs": context_refs,
        "run_ref": run_ref,
        "receipt_ref": receipt_ref,
        "receipt_status": receipt_status["status"],
        "archive_commitment_ref": archive_commitment_ref,
        "execution_replayable": replayable,
        "additional_votes_created": 0,
    }
    return {
        **result,
        "archive_dir": str(archive.run_dir),
        "archive_manifest": archive_manifest,
    }


__all__ = [
    "DEFAULT_HOUSE_CASE",
    "DEFAULT_ORATOR_MOTION",
    "HOUSE_MODE_ID",
    "MAX_MODE_THEATRE_CONTEXT_CHARS",
    "MAX_THEATRE_PROMPT_CHARS",
    "MODE_THEATRE_SCHEMA",
    "ModeTheatreError",
    "ORATOR_MODE_ID",
    "run_mode_theatre_demo",
]
