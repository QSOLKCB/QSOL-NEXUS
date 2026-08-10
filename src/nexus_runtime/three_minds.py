from __future__ import annotations

from typing import Any, Iterable, Protocol

from .three_minds_instrument import (
    DEFAULT_INTEGER_VALUES,
    INTEGER_PRIMALITY_INSTRUMENT,
    MAX_INTEGER_VALUE,
    MAX_INTEGER_VALUES,
    integer_primality_probe,
    normalize_integer_values,
    render_integer_primality_evidence,
)
from .three_minds_validation import (
    MAX_TASK_QUESTION_CHARS,
    validate_members,
    validate_mode_catalog,
    validate_question,
)
from .version import PROTOCOL_VERSION


THREE_MINDS_SCHEMA = "nexus-three-minds/1"


class NexusHandle(Protocol):
    def handle(self, request: dict[str, Any]) -> dict[str, Any]: ...


class ThreeMindsError(RuntimeError):
    """Raised when an alpha11 demonstration step fails closed."""


def _call(api: NexusHandle, request: dict[str, Any]) -> dict[str, Any]:
    operation = str(request.get("operation", "unknown"))
    response = api.handle(request)
    if response.get("status") in {"ok", "verified"}:
        return response
    error = response.get("error")
    if isinstance(error, dict):
        code = error.get("code", "unknown_error")
        message = error.get("message", "operation failed")
        raise ThreeMindsError(f"{operation} failed: {code}: {message}")
    raise ThreeMindsError(f"{operation} failed without a structured error")


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
        raise ThreeMindsError("world.create returned an invalid object shape")
    return obj


def _chat(
    api: NexusHandle,
    member: dict[str, Any],
    message: str,
    *,
    mode: str,
    evidence_refs: list[str],
) -> dict[str, Any]:
    response = _call(
        api,
        {
            "operation": "actor.chat",
            "member": member,
            "message": message,
            "mode": mode,
            "evidence_refs": evidence_refs,
        },
    )
    if not isinstance(response.get("response"), str):
        raise ThreeMindsError("actor.chat returned no text response")
    return response


def _stage_object(
    api: NexusHandle,
    *,
    object_type: str,
    schema_stage: str,
    sequence_index: int,
    requested_member: dict[str, str],
    chat: dict[str, Any],
    task_ref: str,
    previous_stage_ref: str | None,
    evidence_refs: list[str],
    claim_status: str,
) -> dict[str, Any]:
    payload = {
        "schema": THREE_MINDS_SCHEMA,
        "stage": schema_stage,
        "sequence_index": sequence_index,
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
        "claim_status": claim_status,
        "failsafe_replaced": chat.get("failsafe_replacement") is not None,
        "additional_votes_created": 0,
    }
    return _create_world_object(
        api,
        object_type,
        payload,
        {
            "actor": requested_member["member_id"],
            "model_id": requested_member["model_id"],
            "adapter_id": requested_member["adapter_id"],
            "alpha11_stage": schema_stage,
        },
    )


def _task_content(question: str, values: tuple[int, ...]) -> str:
    rendered_values = ",".join(str(value) for value in values)
    return (
        "Alpha11 shared-world task.\n"
        "benchmark_hypothesis=all_supplied_integers_are_prime\n"
        f"values=[{rendered_values}]\n"
        f"question={question}\n"
        "constraint=model consensus is not evidence."
    )


def run_three_minds_demo(
    api: NexusHandle,
    *,
    members: Iterable[dict[str, Any]],
    values: Iterable[int] = DEFAULT_INTEGER_VALUES,
    question: str | None = None,
    mode: str = "analytical",
) -> dict[str, Any]:
    """Run the alpha11 sequential shared-world demonstration.

    Mind A proposes a falsifiable interpretation, Mind B arrives later and
    reproduces/critiques it from immutable evidence, the NEXUS coordinator then
    executes one bounded deterministic instrument, and Mind C interprets that
    result while attempting falsification. Every stage is preserved as a
    content-addressed object in the same WorldStore lineage.
    """

    roster, public_roster_tuple = validate_members(members)
    public_roster = [dict(member) for member in public_roster_tuple]
    normalized_values = normalize_integer_values(values)
    validated_question = validate_question(question)

    modes_response = _call(api, {"operation": "world.modes"})
    validate_mode_catalog(mode, modes_response.get("modes"))

    task = _create_world_object(
        api,
        "three_minds_task",
        {
            "schema": THREE_MINDS_SCHEMA,
            "benchmark_hypothesis": "all_supplied_integers_are_prime",
            "question": validated_question,
            "values": list(normalized_values),
            "mode_id": mode,
            "roster": public_roster,
            "stage_contract": [
                "mind_a_hypothesis",
                "mind_b_reproduction_and_critique",
                "coordinator_integer_primality_probe",
                "mind_c_falsification_from_instrument",
            ],
            "content": _task_content(validated_question, normalized_values),
            "claim_boundary": (
                "demonstration fixture for persistent multi-model lineage; not a general "
                "scientific truth claim"
            ),
        },
        {"actor": "nexus_three_minds_demo", "alpha11_stage": "task"},
    )
    task_ref = task["object_id"]

    mind_a_evidence = [task_ref]
    mind_a = _chat(
        api,
        roster[0],
        (
            "You are Mind A entering a persistent NEXUS world. Read the attached task, "
            "including its exact question and integer fixture. Propose one explicit "
            "falsifiable hypothesis and a reproducible test. Separate observation from "
            "interpretation. Do not claim verification merely because you proposed it."
        ),
        mode=mode,
        evidence_refs=mind_a_evidence,
    )
    hypothesis = _stage_object(
        api,
        object_type="three_minds_hypothesis",
        schema_stage="mind_a_hypothesis",
        sequence_index=1,
        requested_member=public_roster[0],
        chat=mind_a,
        task_ref=task_ref,
        previous_stage_ref=None,
        evidence_refs=mind_a_evidence,
        claim_status="HYPOTHESIS",
    )
    hypothesis_ref = hypothesis["object_id"]

    mind_b_evidence = [task_ref, hypothesis_ref]
    mind_b = _chat(
        api,
        roster[1],
        (
            "You are Mind B arriving after Mind A has left. Read the immutable task, its "
            "exact question and integer fixture, and Mind A's hypothesis object. Reproduce "
            "the proposed test independently, identify assumptions or confounders, and "
            "state what observation would discriminate the benchmark claim. Preserve "
            "disagreement rather than rewriting Mind A's contribution."
        ),
        mode=mode,
        evidence_refs=mind_b_evidence,
    )
    reproduction = _stage_object(
        api,
        object_type="three_minds_reproduction",
        schema_stage="mind_b_reproduction_and_critique",
        sequence_index=2,
        requested_member=public_roster[1],
        chat=mind_b,
        task_ref=task_ref,
        previous_stage_ref=hypothesis_ref,
        evidence_refs=mind_b_evidence,
        claim_status="REPRODUCTION_AND_CRITIQUE",
    )
    reproduction_ref = reproduction["object_id"]

    probe = integer_primality_probe(normalized_values)
    instrument = _create_world_object(
        api,
        "instrument_result",
        {
            "schema": "nexus-instrument-result/1",
            "task_ref": task_ref,
            "previous_stage_ref": reproduction_ref,
            "instrument_id": probe["instrument_id"],
            "input_ref": probe["input_ref"],
            "values": probe["values"],
            "results": probe["results"],
            "all_prime": probe["all_prime"],
            "composite_values": probe["composite_values"],
            "content": render_integer_primality_evidence(probe),
            "claim_boundary": probe["claim_boundary"],
            "execution_initiator": {
                "actor": "nexus_three_minds_demo",
                "reason": "fixed_alpha11_stage_contract",
            },
            "made_available_to": public_roster[2],
        },
        {
            "actor": "nexus_integer_primality_instrument",
            "execution_initiator": "nexus_three_minds_demo",
            "instrument_id": INTEGER_PRIMALITY_INSTRUMENT,
            "alpha11_stage": "coordinator_integer_primality_probe",
        },
    )
    instrument_ref = instrument["object_id"]

    mind_c_evidence = [task_ref, hypothesis_ref, reproduction_ref, instrument_ref]
    mind_c = _chat(
        api,
        roster[2],
        (
            "You are Mind C arriving after Minds A and B. The NEXUS coordinator has already "
            "executed the bounded integer-primality probe; you did not invoke it. Read the "
            "immutable task, both earlier model contributions, and the attached instrument "
            "result. Attempt to falsify the benchmark hypothesis. Treat the instrument "
            "output as verified only for the exact supplied finite integer fixture, "
            "distinguish arithmetic from broader interpretation, and preserve earlier "
            "minority or mistaken hypotheses in lineage."
        ),
        mode=mode,
        evidence_refs=mind_c_evidence,
    )
    falsification = _stage_object(
        api,
        object_type="three_minds_falsification",
        schema_stage="mind_c_falsification_from_instrument",
        sequence_index=3,
        requested_member=public_roster[2],
        chat=mind_c,
        task_ref=task_ref,
        previous_stage_ref=instrument_ref,
        evidence_refs=mind_c_evidence,
        claim_status="FALSIFICATION_ATTEMPT",
    )
    falsification_ref = falsification["object_id"]

    result_state = (
        "FALSIFIED_BY_INTEGER_FIXTURE"
        if probe["composite_values"]
        else "NOT_FALSIFIED_WITHIN_INTEGER_FIXTURE"
    )
    replayable = all(member["adapter_id"] == "mock" for member in public_roster)
    run = _create_world_object(
        api,
        "three_minds_run",
        {
            "schema": THREE_MINDS_SCHEMA,
            "task_ref": task_ref,
            "hypothesis_ref": hypothesis_ref,
            "reproduction_ref": reproduction_ref,
            "instrument_result_ref": instrument_ref,
            "falsification_ref": falsification_ref,
            "lineage_refs": [
                task_ref,
                hypothesis_ref,
                reproduction_ref,
                instrument_ref,
                falsification_ref,
            ],
            "roster": public_roster,
            "mind_count": 3,
            "shared_world": True,
            "sequential_arrival": True,
            "result_state": result_state,
            "instrument_id": INTEGER_PRIMALITY_INSTRUMENT,
            "instrument_execution_actor": "nexus_three_minds_demo",
            "instrument_evidence_state": "VERIFIED_FOR_SUPPLIED_INTEGER_FIXTURE",
            "council_vote": False,
            "additional_votes_created": 0,
            "execution_replayable": replayable,
            "content": (
                f"Three minds completed one shared-world lineage; result={result_state}; "
                f"instrument={INTEGER_PRIMALITY_INSTRUMENT}."
            ),
            "claim_boundary": (
                "the run demonstrates world persistence, sequential evidence discovery, "
                "coordinator-owned bounded instrument execution and lineage; it does not "
                "prove model truth, scientific validity, consciousness, or provider superiority"
            ),
        },
        {"actor": "nexus_three_minds_demo", "alpha11_stage": "completed_run"},
    )
    run_ref = run["object_id"]

    receipt = _create_world_object(
        api,
        "receipt",
        {
            "operation": "three_minds.demo",
            "input_refs": [
                task_ref,
                hypothesis_ref,
                reproduction_ref,
                instrument_ref,
                falsification_ref,
            ],
            "result_ref": run_ref,
            "replayable": replayable,
            "protocol": PROTOCOL_VERSION,
        },
        {"actor": "nexus_three_minds_demo"},
    )
    receipt_ref = receipt["object_id"]
    receipt_status = _call(
        api,
        {"operation": "receipt.verify", "receipt_ref": receipt_ref},
    )

    return {
        "status": "ok",
        "schema": THREE_MINDS_SCHEMA,
        "result_state": result_state,
        "roster": public_roster,
        "task_ref": task_ref,
        "hypothesis_ref": hypothesis_ref,
        "reproduction_ref": reproduction_ref,
        "instrument_result_ref": instrument_ref,
        "falsification_ref": falsification_ref,
        "run_ref": run_ref,
        "receipt_ref": receipt_ref,
        "receipt_status": receipt_status["status"],
        "execution_replayable": replayable,
        "additional_votes_created": 0,
    }


__all__ = [
    "DEFAULT_INTEGER_VALUES",
    "INTEGER_PRIMALITY_INSTRUMENT",
    "MAX_INTEGER_VALUE",
    "MAX_INTEGER_VALUES",
    "MAX_TASK_QUESTION_CHARS",
    "THREE_MINDS_SCHEMA",
    "ThreeMindsError",
    "integer_primality_probe",
    "run_three_minds_demo",
]
