from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .canonical import sha256_ref
from .three_minds_instrument import (
    INTEGER_PRIMALITY_INSTRUMENT,
    integer_primality_probe,
)


INSTRUMENT_POLICY_ID = "nexus-instrument-admission/1"
INSTRUMENT_EXECUTION_SCHEMA = "nexus-instrument-execution/1"
INSTRUMENT_RECEIPT_SCHEMA = "nexus-instrument-receipt/1"


class InstrumentAdmissionError(ValueError):
    """Raised when an instrument request violates the alpha7 admission contract."""


@dataclass(frozen=True)
class InstrumentSpec:
    instrument_id: str
    title: str
    status: str
    executor: str
    deterministic: bool
    replayable: bool
    side_effects: str
    evidence_effect: str
    authority_effect: str
    input_contract: str
    output_contract: str
    claim_boundary: str
    runner: Callable[[Mapping[str, Any]], dict[str, Any]] | None = None

    def public_dict(self) -> dict[str, Any]:
        return {
            "instrument_id": self.instrument_id,
            "title": self.title,
            "status": self.status,
            "executor": self.executor,
            "deterministic": self.deterministic,
            "replayable": self.replayable,
            "side_effects": self.side_effects,
            "evidence_effect": self.evidence_effect,
            "authority_effect": self.authority_effect,
            "input_contract": self.input_contract,
            "output_contract": self.output_contract,
            "claim_boundary": self.claim_boundary,
        }


def _run_integer_primality(payload: Mapping[str, Any]) -> dict[str, Any]:
    if set(payload) != {"values"}:
        raise InstrumentAdmissionError("integer-primality input requires exactly: values")
    values = payload["values"]
    if not isinstance(values, list):
        raise InstrumentAdmissionError("integer-primality values must be a JSON array")
    return integer_primality_probe(values)


_SPECS: tuple[InstrumentSpec, ...] = (
    InstrumentSpec(
        instrument_id=INTEGER_PRIMALITY_INSTRUMENT,
        title="Bounded integer primality",
        status="admitted",
        executor="nexus_coordinator",
        deterministic=True,
        replayable=True,
        side_effects="none",
        evidence_effect="derived_result_only",
        authority_effect="none",
        input_contract="{values: integer[1..128], each 2..10000000}",
        output_contract="exact bounded primality classifications and smallest factors",
        claim_boundary="exact integer primality for the supplied bounded fixture only",
        runner=_run_integer_primality,
    ),
    InstrumentSpec(
        instrument_id="qsol.qec-receipt-replay/1",
        title="QEC receipt/replay adapter",
        status="candidate_not_admitted",
        executor="external_versioned_adapter",
        deterministic=True,
        replayable=True,
        side_effects="none_required",
        evidence_effect="none_until_admitted",
        authority_effect="none",
        input_contract="not frozen",
        output_contract="not frozen",
        claim_boundary="candidate only; no executable QEC authority imported into NEXUS",
    ),
    InstrumentSpec(
        instrument_id="qsol.spectral-analysis/1",
        title="SPECTRAL analysis adapter",
        status="candidate_not_admitted",
        executor="external_versioned_adapter",
        deterministic=False,
        replayable=False,
        side_effects="not_assessed",
        evidence_effect="none_until_admitted",
        authority_effect="none",
        input_contract="not frozen",
        output_contract="not frozen",
        claim_boundary="candidate only; analysis output is not automatically evidence or truth",
    ),
    InstrumentSpec(
        instrument_id="qsol.sonification/1",
        title="QSOL sonification adapter",
        status="candidate_not_admitted",
        executor="external_versioned_adapter",
        deterministic=False,
        replayable=False,
        side_effects="not_assessed",
        evidence_effect="none_until_admitted",
        authority_effect="none",
        input_contract="not frozen",
        output_contract="not frozen",
        claim_boundary="candidate only; sonification is a representation, not semantic authority",
    ),
    InstrumentSpec(
        instrument_id="nexus.symbolic-numeric/1",
        title="Numerical and symbolic computation adapter",
        status="candidate_not_admitted",
        executor="versioned_local_adapter",
        deterministic=False,
        replayable=False,
        side_effects="not_assessed",
        evidence_effect="none_until_admitted",
        authority_effect="none",
        input_contract="not frozen",
        output_contract="not frozen",
        claim_boundary="candidate only; computed output must carry its declared mathematical scope",
    ),
)

_SPEC_BY_ID = {spec.instrument_id: spec for spec in _SPECS}


def instrument_policy_snapshot() -> dict[str, Any]:
    return {
        "schema": INSTRUMENT_POLICY_ID,
        "admission_rule": "default_deny",
        "execution_rule": "only_explicitly_admitted_exact_instrument_ids_may_run",
        "input_rule": "closed_per_instrument_contract",
        "output_rule": "bounded_structured_result_with_explicit_claim_boundary",
        "receipt_rule": "every_execution_is_content_addressed_and_revalidated",
        "side_effect_rule": "side_effects_must_be_explicitly_declared_before_admission",
        "authority_rule": "instrument_execution_confers_no_vote_weight_epistemic_privilege_or_governance_authority",
        "evidence_rule": "instrument_output_is_derived_material_unless_an_independent_evidence_contract_says_otherwise",
        "model_rule": "models_may_request_or_interpret_instruments_but_do_not_gain_executor_authority",
        "candidate_rule": "roadmap_candidates_are_non_executable_until_their_exact_contract_is_admitted",
    }


def instrument_catalog() -> list[dict[str, Any]]:
    return [spec.public_dict() for spec in _SPECS]


def instrument_spec(instrument_id: str) -> dict[str, Any]:
    spec = _SPEC_BY_ID.get(instrument_id)
    if spec is None:
        raise InstrumentAdmissionError(f"unknown instrument: {instrument_id}")
    return spec.public_dict()


def _admitted_spec(instrument_id: str) -> InstrumentSpec:
    spec = _SPEC_BY_ID.get(instrument_id)
    if spec is None:
        raise InstrumentAdmissionError(f"unknown instrument: {instrument_id}")
    if spec.status != "admitted" or spec.runner is None:
        raise InstrumentAdmissionError(f"instrument is not admitted for execution: {instrument_id}")
    if spec.authority_effect != "none":
        raise InstrumentAdmissionError("admitted instruments must have zero authority effect")
    return spec


def run_instrument(instrument_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(instrument_id, str) or not instrument_id:
        raise InstrumentAdmissionError("instrument_id must be a non-empty string")
    if not isinstance(payload, Mapping):
        raise InstrumentAdmissionError("instrument input must be a JSON object")

    spec = _admitted_spec(instrument_id)
    frozen_input = deepcopy(dict(payload))
    intent = {
        "schema": "nexus-instrument-intent/1",
        "instrument_id": instrument_id,
        "input": frozen_input,
    }
    intent_ref = sha256_ref("instrument-intent", intent)
    result = spec.runner(frozen_input)
    execution = {
        "schema": INSTRUMENT_EXECUTION_SCHEMA,
        "instrument_id": instrument_id,
        "intent_ref": intent_ref,
        "input": frozen_input,
        "result": result,
        "executor": spec.executor,
        "deterministic": spec.deterministic,
        "replayable": spec.replayable,
        "side_effects": spec.side_effects,
        "evidence_effect": spec.evidence_effect,
        "authority_effect": spec.authority_effect,
        "claim_boundary": spec.claim_boundary,
    }
    execution_ref = sha256_ref("instrument-execution", execution)
    receipt_body = {
        "schema": INSTRUMENT_RECEIPT_SCHEMA,
        "policy": INSTRUMENT_POLICY_ID,
        "instrument_id": instrument_id,
        "intent_ref": intent_ref,
        "execution_ref": execution_ref,
        "replayable": spec.replayable,
        "authority_effect": "none",
    }
    receipt_ref = sha256_ref("instrument-receipt", receipt_body)
    return {
        "execution": execution,
        "execution_ref": execution_ref,
        "receipt": {**receipt_body, "receipt_ref": receipt_ref},
    }


def verify_instrument_receipt(bundle: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(bundle, Mapping):
        raise InstrumentAdmissionError("instrument bundle must be a JSON object")
    if set(bundle) != {"execution", "execution_ref", "receipt"}:
        raise InstrumentAdmissionError("instrument bundle has an unexpected shape")

    execution = bundle["execution"]
    receipt = bundle["receipt"]
    if not isinstance(execution, Mapping) or not isinstance(receipt, Mapping):
        raise InstrumentAdmissionError("instrument execution and receipt must be JSON objects")
    if execution.get("schema") != INSTRUMENT_EXECUTION_SCHEMA:
        raise InstrumentAdmissionError("unsupported instrument execution schema")
    if receipt.get("schema") != INSTRUMENT_RECEIPT_SCHEMA:
        raise InstrumentAdmissionError("unsupported instrument receipt schema")

    instrument_id = execution.get("instrument_id")
    if receipt.get("instrument_id") != instrument_id:
        raise InstrumentAdmissionError("receipt instrument identity mismatch")
    if receipt.get("policy") != INSTRUMENT_POLICY_ID:
        raise InstrumentAdmissionError("receipt policy mismatch")
    if execution.get("authority_effect") != "none" or receipt.get("authority_effect") != "none":
        raise InstrumentAdmissionError("instrument receipt attempts authority escalation")

    expected = run_instrument(instrument_id, execution.get("input"))
    if bundle != expected:
        raise InstrumentAdmissionError("instrument receipt does not reproduce from admitted input")
    return {
        "status": "verified",
        "instrument_id": instrument_id,
        "execution_ref": expected["execution_ref"],
        "receipt_ref": expected["receipt"]["receipt_ref"],
        "claim_boundary": expected["execution"]["claim_boundary"],
        "authority_effect": "none",
    }


__all__ = [
    "INSTRUMENT_EXECUTION_SCHEMA",
    "INSTRUMENT_POLICY_ID",
    "INSTRUMENT_RECEIPT_SCHEMA",
    "InstrumentAdmissionError",
    "InstrumentSpec",
    "instrument_catalog",
    "instrument_policy_snapshot",
    "instrument_spec",
    "run_instrument",
    "verify_instrument_receipt",
]
