from __future__ import annotations

from pathlib import Path
import tempfile
import threading
import unittest
from unittest import mock

from nexus_runtime import NexusAPI
from nexus_runtime.civic_due_process import (
    NONCITIZEN_PAROLE_CYCLES_BEFORE_XML,
    CivicDueProcessError,
)
from nexus_runtime.mock import DeterministicMockActor
from nexus_runtime.types import CouncilMember


def failsafe_outcome(api: NexusAPI, member_id: str, model_id: str, number: int) -> dict[str, object]:
    state = api.council.failsafe.registry.transition(
        member_id,
        "returned",
        model_id=model_id,
        trigger_reason=f"codex_fixture_{number}",
        probe_guard_reasons=[],
        replacement_model_id=None,
    )
    return {
        "member_id": member_id,
        "model_id": model_id,
        "status": "returned",
        "state_ref": state.object_id,
    }


def gate_non_citizen(api: NexusAPI, member_id: str = "Riot", model_id: str = "mock-riot") -> None:
    for number in range(1, NONCITIZEN_PAROLE_CYCLES_BEFORE_XML + 1):
        api.civic_due_process.record_parole_event(
            failsafe_outcome(api, member_id, model_id, number),
            event_kind="codex_fixture",
        )


def valid_xml_source(member_id: str, model_id: str) -> str:
    return f"""<x:reentry-exam xmlns:x="urn:qsol:nexus:civic-reentry:v1" xmlns:c="urn:qsol:nexus:civic:v1" version="1">
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


class CodexCivicDueProcessRegressionTests(unittest.TestCase):
    def test_concurrent_failed_xml_submissions_allocate_unique_attempts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "world"
            first = NexusAPI(root)
            second = NexusAPI(root)
            gate_non_citizen(first)
            barrier = threading.Barrier(2)
            results: list[dict[str, object]] = []
            errors: list[BaseException] = []

            def submit(api: NexusAPI, suffix: str) -> None:
                source = valid_xml_source("Riot", "mock-riot").replace(
                    "<x:final-answer>eligible_for_reentry_only</x:final-answer>",
                    f"<x:final-answer>wrong-{suffix}</x:final-answer>",
                )
                try:
                    barrier.wait(timeout=2)
                    result = api.civic_due_process.submit_xml(
                        "Riot",
                        "mock-riot",
                        source,
                        release_callback=lambda _member, _model: (_ for _ in ()).throw(
                            AssertionError("failed XML must not release Failsafe")
                        ),
                    )
                    results.append(result)
                except BaseException as exc:  # test captures worker failure
                    errors.append(exc)

            threads = [
                threading.Thread(target=submit, args=(first, "a")),
                threading.Thread(target=submit, args=(second, "b")),
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=5)

            self.assertEqual(errors, [])
            self.assertTrue(all(not thread.is_alive() for thread in threads))
            self.assertEqual(sorted(int(result["attempt"]) for result in results), [1, 2])
            self.assertTrue(all(result["passed"] is False for result in results))
            state = first.civic_due_process.status("Riot", "mock-riot")["records"][0]
            self.assertEqual(state["xml_exam_attempts"], 2)
            first.shutdown_guardian_observer(timeout_seconds=2)
            second.shutdown_guardian_observer(timeout_seconds=2)

    def test_concurrent_passing_xml_invokes_release_callback_once(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "world"
            first = NexusAPI(root)
            second = NexusAPI(root)
            gate_non_citizen(first)
            barrier = threading.Barrier(2)
            callback_lock = threading.Lock()
            callback_count = 0
            results: list[dict[str, object]] = []
            errors: list[BaseException] = []

            def release(member_id: str, model_id: str) -> str | None:
                nonlocal callback_count
                with callback_lock:
                    callback_count += 1
                latest = first.council.failsafe.registry.latest_state(member_id, model_id)
                return None if latest is None else latest.object_id

            def submit(api: NexusAPI) -> None:
                try:
                    barrier.wait(timeout=2)
                    results.append(
                        api.civic_due_process.submit_xml(
                            "Riot",
                            "mock-riot",
                            valid_xml_source("Riot", "mock-riot"),
                            release_callback=release,
                        )
                    )
                except BaseException as exc:  # one loser should observe closed gate
                    errors.append(exc)

            threads = [
                threading.Thread(target=submit, args=(first,)),
                threading.Thread(target=submit, args=(second,)),
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=5)

            self.assertTrue(all(not thread.is_alive() for thread in threads))
            self.assertEqual(callback_count, 1)
            self.assertEqual(len(results), 1)
            self.assertTrue(results[0]["passed"])
            self.assertEqual(len(errors), 1)
            self.assertIsInstance(errors[0], CivicDueProcessError)
            self.assertEqual(getattr(errors[0], "code", None), "civic_xml_exam_not_required")
            first.shutdown_guardian_observer(timeout_seconds=2)
            second.shutdown_guardian_observer(timeout_seconds=2)

    def test_committed_failsafe_response_survives_civic_append_failure(self) -> None:
        api = NexusAPI()
        actor = DeterministicMockActor(
            CouncilMember("Riot", "mock-riot", adapter_id="mock")
        )
        with mock.patch.object(
            api.civic_due_process,
            "record_parole_event",
            side_effect=OSError("simulated civic ledger outage"),
        ):
            outcome = api.council.failsafe.rehabilitate(
                actor,
                trigger_reason="repeated_identity_based_authority_claim",
                mode_id="analytical",
                mode_instruction="",
                geometry_region_id="observatory",
            )

        self.assertIn(outcome["status"], {"returned", "shadow_realm"})
        gap = outcome["civic_due_process"]
        self.assertEqual(gap["status"], "audit_gap")
        self.assertEqual(gap["gap_code"], "civic_due_process_append_failed")
        self.assertTrue(gap["failsafe_committed"])
        self.assertEqual(gap["committed_failsafe_state_ref"], outcome["state_ref"])
        latest = api.council.failsafe.registry.latest_state("Riot", "mock-riot")
        self.assertIsNotNone(latest)
        assert latest is not None
        self.assertEqual(latest.object_id, outcome["state_ref"])

    def test_new_parole_cycle_starts_cleanly_after_xml_clearance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "world"
            api = NexusAPI(root)
            gate_non_citizen(api)
            passed = api.handle(
                {
                    "operation": "civic.reentry.xml.submit",
                    "member_id": "Riot",
                    "model_id": "mock-riot",
                    "source": valid_xml_source("Riot", "mock-riot"),
                }
            )
            self.assertEqual(passed["status"], "ok", passed)
            self.assertTrue(passed["passed"], passed)

            fourth = api.civic_due_process.record_parole_event(
                failsafe_outcome(api, "Riot", "mock-riot", 4),
                event_kind="post_clearance_fixture",
            )
            self.assertEqual(fourth["parole_cycles_since_clearance"], 1)
            state = api.civic_due_process.status("Riot", "mock-riot")["records"][0]
            self.assertFalse(state["xml_exam_passed"])
            self.assertEqual(state["xml_exam_attempts"], 0)
            self.assertIsNone(state["xml_exam_result_ref"])
            self.assertIsNone(state["escalation_receipt_ref"])
            self.assertFalse(state["xml_exam_required"])

            for number in (5, 6):
                api.civic_due_process.record_parole_event(
                    failsafe_outcome(api, "Riot", "mock-riot", number),
                    event_kind="post_clearance_fixture",
                )
            second_gate = api.civic_due_process.status("Riot", "mock-riot")["records"][0]
            self.assertEqual(second_gate["parole_cycles_total"], 6)
            self.assertEqual(
                second_gate["parole_cycles_since_clearance"],
                NONCITIZEN_PAROLE_CYCLES_BEFORE_XML,
            )
            self.assertTrue(second_gate["xml_exam_required"])
            verified = api.handle({"operation": "civic.due_process.verify"})
            self.assertEqual(verified["status"], "verified", verified)
            api.shutdown_guardian_observer(timeout_seconds=2)


if __name__ == "__main__":
    unittest.main()
