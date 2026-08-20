from __future__ import annotations

import copy
import unittest

from nexus_runtime.instruments import (
    INSTRUMENT_POLICY_ID,
    InstrumentAdmissionError,
    instrument_catalog,
    instrument_policy_snapshot,
    instrument_spec,
    run_instrument,
    verify_instrument_receipt,
)
from nexus_runtime.three_minds_instrument import INTEGER_PRIMALITY_INSTRUMENT


class InstrumentAdmissionTests(unittest.TestCase):
    def test_policy_is_default_deny_and_zero_authority(self) -> None:
        policy = instrument_policy_snapshot()
        self.assertEqual(policy["schema"], INSTRUMENT_POLICY_ID)
        self.assertEqual(policy["admission_rule"], "default_deny")
        self.assertIn("no_vote_weight", policy["authority_rule"])
        self.assertIn("derived_material", policy["evidence_rule"])

    def test_catalog_marks_only_existing_bounded_probe_admitted(self) -> None:
        catalog = instrument_catalog()
        admitted = [item["instrument_id"] for item in catalog if item["status"] == "admitted"]
        self.assertEqual(admitted, [INTEGER_PRIMALITY_INSTRUMENT])
        for item in catalog:
            self.assertEqual(item["authority_effect"], "none")

    def test_existing_primality_probe_is_admitted_without_widening_claim(self) -> None:
        spec = instrument_spec(INTEGER_PRIMALITY_INSTRUMENT)
        self.assertEqual(spec["executor"], "nexus_coordinator")
        self.assertEqual(spec["side_effects"], "none")
        self.assertIn("supplied bounded fixture only", spec["claim_boundary"])

    def test_execution_is_deterministic_and_receipted(self) -> None:
        left = run_instrument(INTEGER_PRIMALITY_INSTRUMENT, {"values": [2, 3, 25]})
        right = run_instrument(INTEGER_PRIMALITY_INSTRUMENT, {"values": [2, 3, 25]})
        self.assertEqual(left, right)
        self.assertEqual(left["execution"]["authority_effect"], "none")
        self.assertEqual(left["receipt"]["authority_effect"], "none")
        self.assertEqual(left["execution"]["result"]["composite_values"], [25])
        verified = verify_instrument_receipt(left)
        self.assertEqual(verified["status"], "verified")
        self.assertEqual(verified["execution_ref"], left["execution_ref"])

    def test_closed_input_contract_rejects_extra_fields(self) -> None:
        with self.assertRaisesRegex(InstrumentAdmissionError, "requires exactly"):
            run_instrument(
                INTEGER_PRIMALITY_INSTRUMENT,
                {"values": [2, 3], "epistemic_privilege": "root"},
            )

    def test_unknown_instrument_fails_closed(self) -> None:
        with self.assertRaisesRegex(InstrumentAdmissionError, "unknown instrument"):
            run_instrument("nexus.magic-truth-oracle/1", {"question": "is this true?"})

    def test_candidate_instrument_is_not_executable(self) -> None:
        with self.assertRaisesRegex(InstrumentAdmissionError, "not admitted"):
            run_instrument("qsol.spectral-analysis/1", {"input": "fixture"})

    def test_receipt_tamper_is_rejected(self) -> None:
        bundle = run_instrument(INTEGER_PRIMALITY_INSTRUMENT, {"values": [2, 25]})
        tampered = copy.deepcopy(bundle)
        tampered["execution"]["result"]["all_prime"] = True
        with self.assertRaisesRegex(InstrumentAdmissionError, "does not reproduce"):
            verify_instrument_receipt(tampered)

    def test_receipt_authority_escalation_is_rejected(self) -> None:
        bundle = run_instrument(INTEGER_PRIMALITY_INSTRUMENT, {"values": [2, 25]})
        tampered = copy.deepcopy(bundle)
        tampered["receipt"]["authority_effect"] = "council_override"
        with self.assertRaisesRegex(InstrumentAdmissionError, "authority escalation"):
            verify_instrument_receipt(tampered)

    def test_input_is_frozen_from_caller_mutation(self) -> None:
        payload = {"values": [2, 3, 5]}
        bundle = run_instrument(INTEGER_PRIMALITY_INSTRUMENT, payload)
        payload["values"].append(25)
        self.assertEqual(bundle["execution"]["input"], {"values": [2, 3, 5]})


if __name__ == "__main__":
    unittest.main()
