from __future__ import annotations

from math import isqrt
from typing import Any, Iterable, Protocol

from .canonical import sha256_ref
from .version import PROTOCOL_VERSION


THREE_MINDS_SCHEMA = "nexus-three-minds/1"
INTEGER_PRIMALITY_INSTRUMENT = "nexus.integer-primality/1"
MAX_INTEGER_VALUES = 128
MAX_INTEGER_VALUE = 10_000_000
DEFAULT_INTEGER_VALUES = (2, 3, 5, 7, 11, 13, 17, 19, 23, 25)


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


def _public_member(member: dict[str, Any]) -> dict[str, str]:
    member_id = member.get("member_id")
    model_id = member.get("model_id")
    adapter_id = member.get("adapter_id", "mock")
    if not isinstance(member_id, str) or not member_id:
        raise ValueError("each mind requires a non-empty member_id")
    if not isinstance(model_id, str) or not model_id:
        raise ValueError("each mind requires a non-empty model_id")
    if not isinstance(adapter_id, str) or not adapter_id:
        raise ValueError("each mind requires a non-empty adapter_id")
    vote_weight = member.get("vote_weight", 1)
    if type(vote_weight) is not int or vote_weight != 1:
        raise ValueError("three-minds demo preserves vote_weight = 1")
    if member.get("epistemic_privilege", "none") != "none":
        raise ValueError("three-minds demo preserves epistemic_privilege = none")
    return {
        "member_id": member_id,
        "model_id": model_id,
        "adapter_id": adapter_id,
    }


def _validate_members(members: Iterable[dict[str, Any]]) -> tuple[dict[str, Any], ...]:
    normalized = tuple(members)
    if len(normalized) != 3:
        raise ValueError("three-minds demo requires exactly three minds")
    public = tuple(_public_member(member) for member in normalized)
    if len({member["member_id"] for member in public}) != 3:
        raise ValueError("three-minds demo requires three distinct member_id values")
    if len({(member["adapter_id"], member["model_id"]) for member in public}) != 3:
        raise ValueError("three-minds demo requires three distinct adapter/model identities")
    return normalized


def _normalize_values(values: Iterable[int]) -> tuple[int, ...]:
    normalized = tuple(values)
    if not normalized:
        raise ValueError("integer fixture must contain at least one value")
    if len(normalized) > MAX_INTEGER_VALUES:
        raise ValueError(f"integer fixture permits at most {MAX_INTEGER_VALUES} values")
    for value in normalized:
        if type(value) is not int:
            raise ValueError("integer fixture values must be exact integers")
        if not 2 <= value <= MAX_INTEGER_VALUE:
            raise ValueError(
                f"integer fixture values must be in [2, {MAX_INTEGER_VALUE}]"
            )
    return normalized


def _smallest_factor(value: int) -> int | None:
    if value == 2:
        return None
    if value % 2 == 0:
        return 2
    limit = isqrt(value)
    candidate = 3
    while candidate <= limit:
        if value % candidate == 0:
            return candidate
        candidate += 2
    return None


def integer_primality_probe(values: Iterable[int]) -> dict[str, Any]:
    """Run one bounded, deterministic integer-only alpha11 instrument.

    The result verifies primality only for the supplied finite fixture. It is
    deliberately not a general scientific-validation or truth oracle.
    """

    normalized = _normalize_values(values)
    results: list[dict[str, Any]] = []
    composites: list[int] = []
    for value in normalized:
        factor = _smallest_factor(value)
        is_prime = factor is None
        if not is_prime:
            composites.append(value)
        results.append(
            {
                "value": value,
                "is_prime": is_prime,
                "smallest_factor": factor,
            }
        )
    input_ref = sha256_ref("integer_fixture", {"values": list(normalized)})
    return {
        "instrument_id": INTEGER_PRIMALITY_INSTRUMENT,
        "input_ref": input_ref,
        "value_count": len(normalized),
        "values": list(normalized),
        "results": results,
        "all_prime": not composites,
        "composite_values": composites,
        "claim_boundary": "exact integer primality for the supplied bounded fixture only",
    }


def _instrument_content(probe: dict[str, Any]) -> str:
    composites = []
    for result in probe["results"]:
        if not result["is_prime"]:
            composites.append(f"{result['value']} (factor {result['smallest_factor']})")
    rendered = ", ".join(composites) if composites else "none"
    return (
        f"{INTEGER_PRIMALITY_INSTRUMENT} checked {probe['value_count']} integers; "
        f"all_prime={str(probe['all_prime']).lower()}; composites={rendered}."
    )


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
    requested_member: dict[str, Any],
    chat: dict[str, Any],
    task_ref: str,
    previous_stage_ref: str | None,
    evidence_refs: list[str],
    claim_status: str,
) -> dict[str, Any]:
    public = _public_member(requested_member)
    payload = {
        "schema": THREE_MINDS_SCHEMA,
        "stage": schema_stage,
        "sequence_index": sequence_index,
        "task_ref": task_ref,
        "previous_stage_ref": previous_stage_ref,
        "requested_member": public,
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
            "actor": public["member_id"],
            "model_id": public["model_id"],
            "adapter_id": public["adapter_id"],
            "alpha11_stage": schema_stage,
        },
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
    reproduces/critiques it from immutable evidence, then Mind C invokes a
    bounded deterministic instrument and attempts falsification. Every stage is
    preserved as a content-addressed object in the same WorldStore lineage.
    """

    roster = _validate_members(members)
    public_roster = [_public_member(member) for member in roster]
    normalized_values = _normalize_values(values)
    if question is None:
        question = (
            "Evaluate the benchmark hypothesis that every supplied integer is prime. "
            "Propose, reproduce, critique, and attempt to falsify the claim without "
            "treating model agreement as evidence."
        )
    if not isinstance(question, str) or not question.strip():
        raise ValueError("question must be non-empty text")
    if len(question) > 4_096:
        raise ValueError("question must be at most 4096 characters")
    if not isinstance(mode, str) or not mode:
        raise ValueError("mode must be non-empty text")

    modes = _call(api, {"operation": "world.modes"}).get("modes")
    if not isinstance(modes, list) or mode not in {
        item.get("mode_id") for item in modes if isinstance(item, dict)
    }:
        raise ValueError(f"unknown world mode: {mode}")

    task = _create_world_object(
        api,
        "three_minds_task",
        {
            "schema": THREE_MINDS_SCHEMA,
            "benchmark_hypothesis": "all_supplied_integers_are_prime",
            "question": question,
            "values": list(normalized_values),
            "mode_id": mode,
            "roster": public_roster,
            "stage_contract": [
                "mind_a_hypothesis",
                "mind_b_reproduction_and_critique",
                "mind_c_instrument_and_falsification",
            ],
            "content": (
                "Alpha11 shared-world task: test whether every supplied integer is prime; "
                "model consensus is not evidence."
            ),
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
            "You are Mind A entering a persistent NEXUS world. Read the attached task. "
            "Propose one explicit falsifiable hypothesis about the supplied integers and "
            "a reproducible test. Separate observation from interpretation. Do not claim "
            "verification merely because you proposed it."
        ),
        mode=mode,
        evidence_refs=mind_a_evidence,
    )
    hypothesis = _stage_object(
        api,
        object_type="three_minds_hypothesis",
        schema_stage="mind_a_hypothesis",
        sequence_index=1,
        requested_member=roster[0],
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
            "You are Mind B arriving after Mind A has left. Read the immutable task and "
            "Mind A hypothesis objects attached as evidence. Reproduce the proposed test "
            "independently, identify assumptions or confounders, and state what observation "
            "would discriminate the benchmark claim. Preserve disagreement rather than "
            "rewriting Mind A's contribution."
        ),
        mode=mode,
        evidence_refs=mind_b_evidence,
    )
    reproduction = _stage_object(
        api,
        object_type="three_minds_reproduction",
        schema_stage="mind_b_reproduction_and_critique",
        sequence_index=2,
        requested_member=roster[1],
        chat=mind_b,
        task_ref=task_ref,
        previous_stage_ref=hypothesis_ref,
        evidence_refs=mind_b_evidence,
        claim_status="REPRODUCTION_AND_CRITIQUE",
    )
    reproduction_ref = reproduction["object_id"]

    probe = integer_primality_probe(normalized_values)
    mind_c_public = _public_member(roster[2])
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
            "content": _instrument_content(probe),
            "claim_boundary": probe["claim_boundary"],
            "requested_by": mind_c_public,
        },
        {
            "actor": "nexus_integer_primality_instrument",
            "requested_by_member_id": mind_c_public["member_id"],
            "instrument_id": INTEGER_PRIMALITY_INSTRUMENT,
        },
    )
    instrument_ref = instrument["object_id"]

    mind_c_evidence = [task_ref, hypothesis_ref, reproduction_ref, instrument_ref]
    mind_c = _chat(
        api,
        roster[2],
        (
            "You are Mind C arriving after Minds A and B. Read their immutable lineage and "
            "the attached deterministic integer-primality instrument result. Attempt to "
            "falsify the benchmark hypothesis. Treat the instrument output as verified only "
            "for the supplied finite integer fixture, distinguish arithmetic from broader "
            "interpretation, and preserve earlier minority or mistaken hypotheses in lineage."
        ),
        mode=mode,
        evidence_refs=mind_c_evidence,
    )
    falsification = _stage_object(
        api,
        object_type="three_minds_falsification",
        schema_stage="mind_c_instrument_and_falsification",
        sequence_index=3,
        requested_member=roster[2],
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
                "bounded instrument execution and lineage; it does not prove model truth, "
                "scientific validity, consciousness, or provider superiority"
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
    "THREE_MINDS_SCHEMA",
    "ThreeMindsError",
    "integer_primality_probe",
    "run_three_minds_demo",
]
