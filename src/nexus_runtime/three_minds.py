from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Iterable, Protocol

from .instruments import run_instrument, verify_instrument_receipt
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
from .world_lattice import LATTICE_PROFILE_ID, LATTICE_REFERENCE_PROTOCOL


THREE_MINDS_SCHEMA = "nexus-three-minds/1"
THREE_MINDS_INTEGRATION_SCHEMA = "nexus-three-minds-integration/1"
THREE_MINDS_INSTRUMENT_RECORD_SCHEMA = "nexus-three-minds-instrument-record/1"
THREE_MINDS_VERIFIED_DESCENDANT_SCHEMA = "nexus-three-minds-verified-descendant/1"

THREE_MINDS_BOUNDARIES = (
    "PERSISTENT_LINEAGE != TRUTH",
    "INSTRUMENT_RESULT != TRUTH",
    "REPLAY != EMPIRICAL_CONFIRMATION",
    "MINORITY_REPORT != EVIDENCE_PROMOTION",
    "MULTI_MODEL_CONSENSUS != EVIDENCE",
    "LATTICE_POSITION != COGNITIVE_COORDINATE",
    "VERIFIED_DESCENDANT != SEMANTIC_TRUTH",
)


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


def _response_object(response: Mapping[str, Any], key: str, *, operation: str) -> dict[str, Any]:
    obj = response.get(key)
    if not isinstance(obj, dict) or not isinstance(obj.get("object_id"), str):
        raise ThreeMindsError(f"{operation} returned an invalid object shape")
    return obj


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
    return _response_object(response, "object", operation="world.create")


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


def _lattice_reference(address: str) -> dict[str, Any]:
    return {
        "protocol": LATTICE_REFERENCE_PROTOCOL,
        "profile_id": LATTICE_PROFILE_ID,
        "address": address,
        "authority": "storage-only",
    }


def _presence_ref(response: Mapping[str, Any], *, operation: str) -> str:
    event = _response_object(response, "presence_event", operation=operation)
    return event["object_id"]


def _persistent_hypothesis(
    api: NexusHandle,
    *,
    statement: str,
    state: str,
    previous_ref: str | None = None,
) -> dict[str, Any]:
    request: dict[str, Any] = {
        "operation": "world.hypothesis.create",
        "statement": statement,
        "state": state,
        "evidence_refs": [],
    }
    if previous_ref is not None:
        request["previous_hypothesis_ref"] = previous_ref
    return _response_object(
        _call(api, request),
        "hypothesis",
        operation="world.hypothesis.create",
    )


def _persistent_experiment(
    api: NexusHandle,
    *,
    title: str,
    stage: str,
    method: str,
    hypothesis_refs: list[str],
    input_refs: list[str],
    result_refs: list[str],
    previous_ref: str | None = None,
) -> dict[str, Any]:
    request: dict[str, Any] = {
        "operation": "world.experiment.create",
        "title": title,
        "stage": stage,
        "method": method,
        "hypothesis_refs": list(hypothesis_refs),
        "input_refs": list(input_refs),
        "result_refs": list(result_refs),
    }
    if previous_ref is not None:
        request["previous_experiment_ref"] = previous_ref
    return _response_object(
        _call(api, request),
        "experiment",
        operation="world.experiment.create",
    )


def _relation(
    api: NexusHandle,
    *,
    relation_type: str,
    source_ref: str,
    target_ref: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    return _response_object(
        _call(
            api,
            {
                "operation": "world.relation.create",
                "relation_type": relation_type,
                "source_ref": source_ref,
                "target_ref": target_ref,
                "metadata": metadata,
            },
        ),
        "relation",
        operation="world.relation.create",
    )


def _instrument_record(
    api: NexusHandle,
    *,
    stage_owner: dict[str, str],
    role: str,
    values: tuple[int, ...],
    reproduces_record_ref: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    bundle = run_instrument(INTEGER_PRIMALITY_INSTRUMENT, {"values": list(values)})
    verification = verify_instrument_receipt(bundle)
    record = _create_world_object(
        api,
        "three_minds_instrument_record",
        {
            "schema": THREE_MINDS_INSTRUMENT_RECORD_SCHEMA,
            "role": role,
            "stage_owner": dict(stage_owner),
            "execution_initiator": "nexus_three_minds_demo",
            "values": list(values),
            "instrument_bundle": bundle,
            "receipt_verification": verification,
            "reproduces_record_ref": reproduces_record_ref,
            "derived_material_only": True,
            "semantic_truth_claimed": False,
            "authority_effect": "none",
        },
        {
            "actor": "nexus_three_minds_demo",
            "instrument_id": INTEGER_PRIMALITY_INSTRUMENT,
            "alpha11_stage": role,
        },
    )
    return record, bundle


def run_three_minds_demo(
    api: NexusHandle,
    *,
    members: Iterable[dict[str, Any]],
    values: Iterable[int] = DEFAULT_INTEGER_VALUES,
    question: str | None = None,
    mode: str = "analytical",
) -> dict[str, Any]:
    """Run the alpha11 sequential shared-world demonstration.

    The original alpha11 model-stage lineage remains intact. The post-alpha7/8
    completion layer additionally records admitted instrument receipts, typed
    hypothesis/experiment/relations, and explicit LATTICE handoffs without
    granting any of those records semantic or governance authority.
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
    presence_a_ref = _presence_ref(
        _call(
            api,
            {
                "operation": "world.place",
                "object_ref": task_ref,
                "region_id": "observatory",
                "lattice_reference": _lattice_reference("L[0,0,0]"),
            },
        ),
        operation="world.place",
    )

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

    persistent_hypothesis_a = _persistent_hypothesis(
        api,
        statement="All integers in the declared alpha11 fixture are prime.",
        state="PROPOSED",
    )
    persistent_plan_a = _persistent_experiment(
        api,
        title="Alpha11 bounded integer-primality experiment",
        stage="PLANNED",
        method=(
            "Execute the admitted bounded integer-primality instrument; interpret only the "
            "exact finite values supplied by the alpha11 task."
        ),
        hypothesis_refs=[persistent_hypothesis_a["object_id"]],
        input_refs=[task_ref],
        result_refs=[],
    )
    relation_a = _relation(
        api,
        relation_type="interprets",
        source_ref=hypothesis_ref,
        target_ref=persistent_hypothesis_a["object_id"],
        metadata={"model_stage_is_interpretation_not_evidence": True},
    )

    baseline_values = normalized_values[:-1] if len(normalized_values) > 1 else normalized_values
    initially_untested_values = normalized_values[len(baseline_values) :]
    baseline_a, baseline_bundle_a = _instrument_record(
        api,
        stage_owner=public_roster[0],
        role="mind_a_baseline_execution",
        values=baseline_values,
    )

    presence_b_ref = _presence_ref(
        _call(
            api,
            {
                "operation": "world.move",
                "object_ref": task_ref,
                "previous_presence_ref": presence_a_ref,
                "region_id": "archive",
                "lattice_reference": _lattice_reference("L[0,0,1]"),
            },
        ),
        operation="world.move",
    )

    mind_b_evidence = [task_ref, hypothesis_ref, baseline_a["object_id"]]
    mind_b = _chat(
        api,
        roster[1],
        (
            "You are Mind B arriving after Mind A has left. Read the immutable task, its "
            "exact question and integer fixture, Mind A's hypothesis object, and the bounded "
            "coordinator-owned baseline instrument record. Reproduce the proposed test "
            "independently, identify assumptions or confounders, and preserve disagreement "
            "rather than rewriting Mind A's contribution."
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

    baseline_b, baseline_bundle_b = _instrument_record(
        api,
        stage_owner=public_roster[1],
        role="mind_b_baseline_replay",
        values=baseline_values,
        reproduces_record_ref=baseline_a["object_id"],
    )
    if baseline_bundle_b != baseline_bundle_a:
        raise ThreeMindsError("Mind B baseline replay did not reproduce Mind A instrument bundle exactly")

    persistent_hypothesis_b = _persistent_hypothesis(
        api,
        statement="All integers in the declared alpha11 fixture are prime.",
        state="CHALLENGED",
        previous_ref=persistent_hypothesis_a["object_id"],
    )
    persistent_observed_b = _persistent_experiment(
        api,
        title="Alpha11 bounded integer-primality experiment",
        stage="OBSERVED",
        method=(
            "Mind B reproduces the fixed baseline instrument bytes and records critique; "
            "exact replay does not widen the tested scope."
        ),
        hypothesis_refs=[persistent_hypothesis_b["object_id"]],
        input_refs=[task_ref],
        result_refs=[baseline_a["object_id"], baseline_b["object_id"], reproduction_ref],
        previous_ref=persistent_plan_a["object_id"],
    )
    relation_b_replay = _relation(
        api,
        relation_type="replays",
        source_ref=baseline_b["object_id"],
        target_ref=baseline_a["object_id"],
        metadata={"byte_identical_instrument_bundle": True, "authority_effect": "none"},
    )
    relation_b_critique = _relation(
        api,
        relation_type="critiques",
        source_ref=reproduction_ref,
        target_ref=persistent_hypothesis_b["object_id"],
        metadata={
            "initially_untested_values": list(initially_untested_values),
            "replay_is_empirical_confirmation": False,
        },
    )

    presence_c_ref = _presence_ref(
        _call(
            api,
            {
                "operation": "world.move",
                "object_ref": task_ref,
                "previous_presence_ref": presence_b_ref,
                "region_id": "agora",
                "lattice_reference": _lattice_reference("L[0,1,1]"),
            },
        ),
        operation="world.move",
    )

    full_bundle = run_instrument(
        INTEGER_PRIMALITY_INSTRUMENT,
        {"values": list(normalized_values)},
    )
    full_verification = verify_instrument_receipt(full_bundle)
    probe = full_bundle["execution"]["result"]
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
            "instrument_execution_ref": full_bundle["execution_ref"],
            "instrument_receipt_ref": full_bundle["receipt"]["receipt_ref"],
            "instrument_bundle": full_bundle,
            "receipt_verification": full_verification,
            "derived_material_only": True,
            "authority_effect": "none",
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

    mind_c_evidence = [
        task_ref,
        hypothesis_ref,
        reproduction_ref,
        instrument_ref,
        persistent_hypothesis_b["object_id"],
        persistent_observed_b["object_id"],
    ]
    mind_c = _chat(
        api,
        roster[2],
        (
            "You are Mind C arriving after Minds A and B. The NEXUS coordinator has already "
            "executed the bounded integer-primality probe; you did not invoke it. Read the "
            "immutable task, both earlier model contributions, the alpha8 challenged lineage, "
            "and the attached instrument result. Attempt to falsify the benchmark hypothesis. "
            "Treat the instrument output as verified only for the exact supplied finite integer "
            "fixture and preserve earlier minority or mistaken hypotheses in lineage."
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
    final_hypothesis_state = "RETIRED" if probe["composite_values"] else "CHALLENGED"
    persistent_hypothesis_c = _persistent_hypothesis(
        api,
        statement="All integers in the declared alpha11 fixture are prime.",
        state=final_hypothesis_state,
        previous_ref=persistent_hypothesis_b["object_id"],
    )
    persistent_closed_c = _persistent_experiment(
        api,
        title="Alpha11 bounded integer-primality experiment",
        stage="CLOSED",
        method=(
            "Close the workflow after the admitted full-fixture instrument execution and "
            "Mind C interpretation; CLOSED is workflow state, not a general truth label."
        ),
        hypothesis_refs=[persistent_hypothesis_b["object_id"]],
        input_refs=[task_ref],
        result_refs=[instrument_ref, falsification_ref],
        previous_ref=persistent_observed_b["object_id"],
    )
    verified_descendant = _create_world_object(
        api,
        "three_minds_verified_descendant",
        {
            "schema": THREE_MINDS_VERIFIED_DESCENDANT_SCHEMA,
            "persistent_hypothesis_ref": persistent_hypothesis_c["object_id"],
            "closed_experiment_ref": persistent_closed_c["object_id"],
            "instrument_result_ref": instrument_ref,
            "instrument_execution_ref": full_bundle["execution_ref"],
            "instrument_receipt_ref": full_bundle["receipt"]["receipt_ref"],
            "receipt_verification": full_verification,
            "verified_scope": "admitted_instrument_receipt_and_exact_input_only",
            "semantic_truth_claimed": False,
            "authority_effect": "none",
        },
        {"actor": "nexus_three_minds_demo", "alpha11_stage": "verified_descendant"},
    )
    relation_c_result = _relation(
        api,
        relation_type="bears_on",
        source_ref=instrument_ref,
        target_ref=persistent_hypothesis_c["object_id"],
        metadata={"instrument_result_is_general_truth": False},
    )
    relation_c_verified = _relation(
        api,
        relation_type="verifies_receipt_for",
        source_ref=verified_descendant["object_id"],
        target_ref=persistent_closed_c["object_id"],
        metadata={"verified_scope": "instrument_receipt_only", "authority_effect": "none"},
    )

    final_presence_ref = _presence_ref(
        _call(
            api,
            {
                "operation": "world.move",
                "object_ref": task_ref,
                "previous_presence_ref": presence_c_ref,
                "region_id": "observatory",
                "lattice_reference": _lattice_reference("L[1,1,1]"),
            },
        ),
        operation="world.move",
    )

    replayable = all(member["adapter_id"] == "mock" for member in public_roster)
    integration = _create_world_object(
        api,
        "three_minds_integration",
        {
            "schema": THREE_MINDS_INTEGRATION_SCHEMA,
            "task_ref": task_ref,
            "mind_a_persistent_hypothesis_ref": persistent_hypothesis_a["object_id"],
            "mind_a_planned_experiment_ref": persistent_plan_a["object_id"],
            "mind_a_baseline_record_ref": baseline_a["object_id"],
            "mind_b_replay_record_ref": baseline_b["object_id"],
            "mind_b_persistent_hypothesis_ref": persistent_hypothesis_b["object_id"],
            "mind_b_observed_experiment_ref": persistent_observed_b["object_id"],
            "mind_c_persistent_hypothesis_ref": persistent_hypothesis_c["object_id"],
            "mind_c_closed_experiment_ref": persistent_closed_c["object_id"],
            "verified_descendant_ref": verified_descendant["object_id"],
            "full_instrument_result_ref": instrument_ref,
            "presence_refs": [presence_a_ref, presence_b_ref, presence_c_ref, final_presence_ref],
            "final_presence_ref": final_presence_ref,
            "relations": [
                relation_a["object_id"],
                relation_b_replay["object_id"],
                relation_b_critique["object_id"],
                relation_c_result["object_id"],
                relation_c_verified["object_id"],
            ],
            "baseline_values": list(baseline_values),
            "initially_untested_values": list(initially_untested_values),
            "mind_b_replay_exact": True,
            "final_workflow_hypothesis_state": final_hypothesis_state,
            "boundaries": list(THREE_MINDS_BOUNDARIES),
            "authority_effect": "none",
        },
        {"actor": "nexus_three_minds_demo", "alpha11_stage": "post_alpha8_integration"},
    )
    integration_ref = integration["object_id"]
    integration_receipt = _create_world_object(
        api,
        "receipt",
        {
            "operation": "three_minds.integration",
            "input_refs": [
                persistent_hypothesis_a["object_id"],
                persistent_plan_a["object_id"],
                baseline_a["object_id"],
                baseline_b["object_id"],
                persistent_hypothesis_b["object_id"],
                persistent_observed_b["object_id"],
                instrument_ref,
                falsification_ref,
                persistent_hypothesis_c["object_id"],
                persistent_closed_c["object_id"],
                verified_descendant["object_id"],
                final_presence_ref,
            ],
            "result_ref": integration_ref,
            "replayable": replayable,
            "protocol": PROTOCOL_VERSION,
        },
        {"actor": "nexus_three_minds_demo"},
    )
    integration_receipt_ref = integration_receipt["object_id"]
    integration_receipt_status = _call(
        api,
        {"operation": "receipt.verify", "receipt_ref": integration_receipt_ref},
    )

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
            "integration_ref": integration_ref,
            "integration_receipt_ref": integration_receipt_ref,
            "final_presence_ref": final_presence_ref,
            "persistent_hypothesis_ref": persistent_hypothesis_c["object_id"],
            "persistent_experiment_ref": persistent_closed_c["object_id"],
            "verified_descendant_ref": verified_descendant["object_id"],
            "baseline_replay_exact": True,
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
        "integration_ref": integration_ref,
        "integration_receipt_ref": integration_receipt_ref,
        "integration_receipt_status": integration_receipt_status["status"],
        "final_presence_ref": final_presence_ref,
        "persistent_hypothesis_ref": persistent_hypothesis_c["object_id"],
        "persistent_experiment_ref": persistent_closed_c["object_id"],
        "mind_a_baseline_record_ref": baseline_a["object_id"],
        "mind_b_replay_record_ref": baseline_b["object_id"],
        "verified_descendant_ref": verified_descendant["object_id"],
        "baseline_replay_exact": True,
        "execution_replayable": replayable,
        "additional_votes_created": 0,
    }


def verify_three_minds_integration(api: NexusHandle, result: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "integration_ref",
        "integration_receipt_ref",
        "final_presence_ref",
        "persistent_hypothesis_ref",
        "persistent_experiment_ref",
        "mind_a_baseline_record_ref",
        "mind_b_replay_record_ref",
        "verified_descendant_ref",
        "instrument_result_ref",
    }
    missing = sorted(key for key in required if not isinstance(result.get(key), str))
    if missing:
        raise ThreeMindsError(f"three-minds integration result is missing refs: {missing}")

    receipt = _call(
        api,
        {"operation": "receipt.verify", "receipt_ref": result["integration_receipt_ref"]},
    )
    if receipt.get("status") != "verified":
        raise ThreeMindsError("three-minds integration receipt did not verify")

    def inspect(ref: str) -> dict[str, Any]:
        response = _call(api, {"operation": "world.inspect", "object_ref": ref})
        obj = response.get("object")
        if not isinstance(obj, dict):
            raise ThreeMindsError(f"world.inspect returned invalid object for {ref}")
        return obj

    baseline_a = inspect(result["mind_a_baseline_record_ref"])
    baseline_b = inspect(result["mind_b_replay_record_ref"])
    bundle_a = baseline_a.get("payload", {}).get("instrument_bundle")
    bundle_b = baseline_b.get("payload", {}).get("instrument_bundle")
    if not isinstance(bundle_a, Mapping) or not isinstance(bundle_b, Mapping):
        raise ThreeMindsError("baseline instrument records are missing bundles")
    verify_instrument_receipt(bundle_a)
    verify_instrument_receipt(bundle_b)
    if bundle_a != bundle_b:
        raise ThreeMindsError("Mind B replay no longer reproduces Mind A instrument bundle")

    instrument = inspect(result["instrument_result_ref"])
    full_bundle = instrument.get("payload", {}).get("instrument_bundle")
    if not isinstance(full_bundle, Mapping):
        raise ThreeMindsError("full alpha11 instrument result is missing admitted receipt bundle")
    verify_instrument_receipt(full_bundle)

    presence = _call(
        api,
        {"operation": "world.presence", "event_ref": result["final_presence_ref"]},
    ).get("presence")
    if not isinstance(presence, Mapping):
        raise ThreeMindsError("world.presence returned invalid alpha11 handoff lineage")
    if presence.get("lineage_length") != 4:
        raise ThreeMindsError("alpha11 handoff must contain one placement plus three moves")
    current = presence.get("current")
    if not isinstance(current, Mapping) or current.get("region_id") != "observatory":
        raise ThreeMindsError("alpha11 final presence must return the shared task to Observatory")

    persistent_hypothesis = inspect(result["persistent_hypothesis_ref"])
    hypothesis_payload = persistent_hypothesis.get("payload")
    if not isinstance(hypothesis_payload, Mapping) or hypothesis_payload.get("state") not in {"RETIRED", "CHALLENGED"}:
        raise ThreeMindsError("alpha11 persistent hypothesis has invalid final workflow state")
    if hypothesis_payload.get("state_semantics") != "workflow_label_not_truth_classification":
        raise ThreeMindsError("alpha11 persistent hypothesis widened workflow state into truth")

    persistent_experiment = inspect(result["persistent_experiment_ref"])
    experiment_payload = persistent_experiment.get("payload")
    if not isinstance(experiment_payload, Mapping) or experiment_payload.get("stage") != "CLOSED":
        raise ThreeMindsError("alpha11 persistent experiment is not CLOSED")
    if experiment_payload.get("claim_boundary") != "recorded_world_lineage_not_empirical_truth":
        raise ThreeMindsError("alpha11 experiment widened lineage into empirical truth")

    descendant = inspect(result["verified_descendant_ref"])
    descendant_payload = descendant.get("payload")
    if not isinstance(descendant_payload, Mapping) or descendant_payload.get("semantic_truth_claimed") is not False:
        raise ThreeMindsError("alpha11 verified descendant widened receipt verification into truth")

    return {
        "status": "verified",
        "integration_ref": result["integration_ref"],
        "integration_receipt_ref": result["integration_receipt_ref"],
        "presence_lineage_length": presence["lineage_length"],
        "final_region_id": current["region_id"],
        "baseline_replay_exact": True,
        "full_instrument_receipt_verified": True,
        "persistent_hypothesis_state": hypothesis_payload["state"],
        "persistent_experiment_stage": experiment_payload["stage"],
        "semantic_truth_claimed": False,
        "authority_effect": "none",
    }


def run_three_minds_council_demo(
    api: NexusHandle,
    *,
    members: Iterable[dict[str, Any]],
    evidence_refs: Iterable[str],
    question: str | None = None,
    mode: str = "analytical",
) -> dict[str, Any]:
    roster, public_roster_tuple = validate_members(members)
    public_roster = [dict(member) for member in public_roster_tuple]
    refs = list(evidence_refs)
    if not refs or not all(isinstance(ref, str) for ref in refs):
        raise ValueError("alpha11 Council evidence_refs must be a non-empty list of object refs")
    council_question = question or (
        "Alpha11 Council: given the shared-world lineage and bounded instrument receipts, "
        "what conclusion is justified without turning consensus into evidence?"
    )
    response = _call(
        api,
        {
            "operation": "council.run",
            "question": council_question,
            "members": roster,
            "evidence_refs": refs,
            "evidence_state": "UNTESTED",
            "mode": mode,
        },
    )
    return {
        "status": "ok",
        "session_ref": response.get("session_ref"),
        "receipt_ref": response.get("receipt_ref"),
        "execution_replayable": response.get("execution_replayable"),
        "roster": public_roster,
        "result": response.get("result"),
        "telemetry": response.get("telemetry"),
        "provider_consensus_is_evidence": False,
        "authority_effect": "none",
    }


def run_three_minds_reference_council(
    api: NexusHandle,
    *,
    evidence_refs: Iterable[str],
) -> dict[str, Any]:
    members = (
        {
            "member_id": "Mind-A",
            "model_id": "alpha11-council-a",
            "adapter_id": "mock",
            "profile": "skeptical",
        },
        {
            "member_id": "Mind-B",
            "model_id": "alpha11-council-b",
            "adapter_id": "mock",
            "profile": "balanced",
        },
        {
            "member_id": "Mind-C",
            "model_id": "alpha11-council-c",
            "adapter_id": "mock",
            "profile": "supportive",
        },
    )
    council = run_three_minds_council_demo(
        api,
        members=members,
        evidence_refs=evidence_refs,
    )
    minority = _call(
        api,
        {
            "operation": "world.minority.search",
            "choice": "ACCEPT_WITH_CHANGES",
            "member_id": "Mind-C",
            "limit": 10,
        },
    )
    if minority.get("returned") != 1:
        raise ThreeMindsError("alpha11 reference Council did not preserve exactly one minority report")
    return {
        **council,
        "minority_search": {
            "returned": minority["returned"],
            "search_is_evidence": minority.get("search_is_evidence"),
        },
    }


__all__ = [
    "DEFAULT_INTEGER_VALUES",
    "INTEGER_PRIMALITY_INSTRUMENT",
    "MAX_INTEGER_VALUE",
    "MAX_INTEGER_VALUES",
    "MAX_TASK_QUESTION_CHARS",
    "THREE_MINDS_BOUNDARIES",
    "THREE_MINDS_INTEGRATION_SCHEMA",
    "THREE_MINDS_SCHEMA",
    "ThreeMindsError",
    "integer_primality_probe",
    "run_three_minds_council_demo",
    "run_three_minds_demo",
    "run_three_minds_reference_council",
    "verify_three_minds_integration",
]
