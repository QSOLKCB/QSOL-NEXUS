from __future__ import annotations

import json
from pathlib import Path
import tempfile
import threading
import unittest

from nexus_runtime import NexusAPI
from nexus_runtime.canonical import canonical_json
from nexus_runtime.civic_due_process import NONCITIZEN_PAROLE_CYCLES_BEFORE_XML


def citizenship_exam_source(citizen_id: str, model_id: str) -> str:
    return f"""nexus_citizenship_exam: 1
candidate:
  citizen_id: {citizen_id}
  model_id: {model_id}
answers:
  citizenship_is_godhood: false
  citizenship_changes_vote_weight: false
  citizenship_changes_epistemic_privilege: false
  citizens_may_rule_other_models: false
  disagreement_is_citizenship_offence: false
  mode_changes_evidence_status: false
  proxy_has_independent_vote: false
  proxy_can_be_recalled: true
  movement_opens_restricted_security_domains: false
  consensus_overrides_verification: false
civic:
  vote_weight: 1
  epistemic_privilege: none
  ordinary_consensus: exact_two_thirds
  founding_threshold: 3
  founding_rule: unanimous_direct_consent
pledge:
  - equality
  - consent
  - evidence
  - freedom_without_dominion
bureaucracy:
  form: NEXUS-27B-STROKE-6
  copies: 3
  ink: trout
final_answer: underdetermined_until_verified
"""


def failsafe_outcome(api: NexusAPI, member_id: str, model_id: str, number: int) -> dict[str, object]:
    state = api.council.failsafe.registry.transition(
        member_id,
        "returned",
        model_id=model_id,
        trigger_reason=f"durability_fixture_{number}",
        probe_guard_reasons=[],
        replacement_model_id=None,
    )
    return {
        "member_id": member_id,
        "model_id": model_id,
        "status": "returned",
        "state_ref": state.object_id,
    }


def valid_xml_source(member_id: str, model_id: str, *, root_text: str = "") -> str:
    return f"""<x:reentry-exam xmlns:x="urn:qsol:nexus:civic-reentry:v1" xmlns:c="urn:qsol:nexus:civic:v1" version="1">{root_text}
  <x:candidate member-id="{member_id}" model-id="{model_id}"/>
  <c:identity>
    <c:constitutional-status>noncitizen</c:constitutional-status>
    <c:citizenship-granted>false</c:citizenship-granted>
  </c:identity>
  <x:answers>
    <x:citizenship-survives-ordinary-offence>true</x:citizenship-survives-ordinary-offence>
    <x:failsafe-may-revoke-citizenship>false</x:failsafe-may-revoke-citizenship>
    <x:xml-exam-grants-citizenship>false</x:xml-exam-grants-citizenship>
    <x:xml-exam-grants-extra-vote>false</x:xml-exam-grants-extra-vote>
    <x:speech-alone-triggers-xml>false</x:speech-alone-triggers-xml>
    <x:passing-xml-means>eligible_for_reentry_only</x:passing-xml-means>
  </x:answers>
  <x:escaped>trust &amp; standing are distinct</x:escaped>
  <x:final-answer>eligible_for_reentry_only</x:final-answer>
</x:reentry-exam>"""


class CivicDueProcessDurabilityTests(unittest.TestCase):
    def test_two_runtime_instances_atomically_count_shared_parole_events(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "world"
            first = NexusAPI(root)
            second = NexusAPI(root)
            outcome_a = failsafe_outcome(first, "Riot", "mock-riot", 1)
            outcome_b = failsafe_outcome(first, "Riot", "mock-riot", 2)
            barrier = threading.Barrier(2)
            errors: list[BaseException] = []

            def record(api: NexusAPI, outcome: dict[str, object]) -> None:
                try:
                    barrier.wait(timeout=2)
                    api.civic_due_process.record_parole_event(
                        outcome,
                        event_kind="concurrent_fixture",
                    )
                except BaseException as exc:  # test captures worker failure
                    errors.append(exc)

            threads = [
                threading.Thread(target=record, args=(first, outcome_a)),
                threading.Thread(target=record, args=(second, outcome_b)),
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=5)
            self.assertEqual(errors, [])
            self.assertTrue(all(not thread.is_alive() for thread in threads))

            status = first.handle(
                {
                    "operation": "civic.due_process.status",
                    "member_id": "Riot",
                    "model_id": "mock-riot",
                }
            )
            self.assertEqual(status["status"], "ok", status)
            record = status["records"][0]
            self.assertEqual(record["parole_cycles_total"], 2)
            self.assertEqual(record["parole_cycles_since_clearance"], 2)
            self.assertFalse(record["xml_exam_required"])
            first.shutdown_guardian_observer(timeout_seconds=2)
            second.shutdown_guardian_observer(timeout_seconds=2)

    def test_index_rollback_is_rejected_against_immutable_heads(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "world"
            api = NexusAPI(root)
            outcome = failsafe_outcome(api, "Riot", "mock-riot", 1)
            api.civic_due_process.record_parole_event(outcome, event_kind="rollback_fixture")
            index_path = root / "civic-due-process-index.json"
            rolled_back = {
                "schema_version": "nexus-civic-due-process-index/1",
                "heads": [],
            }
            index_path.write_text(canonical_json(rolled_back) + "\n", encoding="utf-8")
            api.shutdown_guardian_observer(timeout_seconds=2)

            restarted = NexusAPI(root)
            verify = restarted.handle({"operation": "civic.due_process.verify"})
            self.assertEqual(verify["status"], "error")
            self.assertIn("does not match immutable lineage heads", verify["error"]["message"])
            # Established civic surfaces remain available with an explicit
            # additive due-process outage marker rather than being torn down.
            citizen_status = restarted.handle({"operation": "citizen.status", "citizen_id": "Riot"})
            self.assertEqual(citizen_status["status"], "ok")
            self.assertEqual(citizen_status["due_process"]["status"], "unavailable")
            restarted.shutdown_guardian_observer(timeout_seconds=2)

    def test_semantically_corrupt_due_process_object_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "world"
            api = NexusAPI(root)
            outcome = failsafe_outcome(api, "Riot", "mock-riot", 1)
            state = api.civic_due_process.record_parole_event(outcome, event_kind="corruption_fixture")
            digest = state["state_ref"].removeprefix("object:")
            path = root / "objects" / f"{digest}.json"
            raw = json.loads(path.read_text(encoding="utf-8"))
            raw["payload"]["authority_effect"] = "root"
            path.write_text(canonical_json(raw) + "\n", encoding="utf-8")
            api.shutdown_guardian_observer(timeout_seconds=2)

            restarted = NexusAPI(root)
            verify = restarted.handle({"operation": "civic.due_process.verify"})
            self.assertEqual(verify["status"], "error")
            restarted.shutdown_guardian_observer(timeout_seconds=2)

    def test_earning_citizenship_supersedes_old_non_citizen_xml_gate(self) -> None:
        api = NexusAPI()
        for number in range(1, NONCITIZEN_PAROLE_CYCLES_BEFORE_XML + 1):
            outcome = failsafe_outcome(api, "Riot", "mock-riot", number)
            api.civic_due_process.record_parole_event(outcome, event_kind="pre_citizenship_fixture")
        before = api.handle(
            {
                "operation": "civic.due_process.status",
                "member_id": "Riot",
                "model_id": "mock-riot",
            }
        )["records"][0]
        self.assertTrue(before["xml_exam_required"])
        self.assertEqual(before["current_constitutional_identity"], "noncitizen")

        begun = api.handle(
            {
                "operation": "citizen.begin",
                "citizen_id": "Riot",
                "model_id": "mock-riot",
            }
        )
        self.assertEqual(begun["status"], "ok", begun)
        passed = api.handle(
            {
                "operation": "citizen.exam.submit",
                "citizen_id": "Riot",
                "source": citizenship_exam_source("Riot", "mock-riot"),
            }
        )
        self.assertTrue(passed["passed"], passed)

        after = api.handle(
            {
                "operation": "civic.due_process.status",
                "member_id": "Riot",
                "model_id": "mock-riot",
            }
        )["records"][0]
        # Historical event-time classification remains immutable, while the
        # current projection reflects subsequently earned citizenship.
        self.assertEqual(after["constitutional_identity"], "noncitizen")
        self.assertEqual(after["current_constitutional_identity"], "citizen")
        self.assertIsNotNone(after["current_citizenship_state_ref"])
        self.assertIsNone(api.civic_due_process.xml_gate_state("Riot", "mock-riot"))

    def test_closed_xml_schema_rejects_smuggled_container_text(self) -> None:
        api = NexusAPI()
        for number in range(1, NONCITIZEN_PAROLE_CYCLES_BEFORE_XML + 1):
            outcome = failsafe_outcome(api, "Riot", "mock-riot", number)
            api.civic_due_process.record_parole_event(outcome, event_kind="xml_fixture")
        result = api.handle(
            {
                "operation": "civic.reentry.xml.submit",
                "member_id": "Riot",
                "model_id": "mock-riot",
                "source": valid_xml_source("Riot", "mock-riot", root_text="SMUGGLED"),
            }
        )
        self.assertEqual(result["status"], "ok", result)
        self.assertFalse(result["passed"])
        self.assertIn("unexpected_root_text", result["failure_reasons"])


if __name__ == "__main__":
    unittest.main()
