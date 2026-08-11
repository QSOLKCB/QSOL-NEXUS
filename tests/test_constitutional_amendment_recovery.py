from __future__ import annotations

from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from nexus_runtime import NexusAPI


FIXED_CITIZENS = ("Alpha", "Beta", "Gamma")


def exam_source(citizen_id: str, model_id: str) -> str:
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


def register_citizen(api: NexusAPI, citizen_id: str) -> str:
    model_id = f"mock-{citizen_id.lower()}"
    begun = api.handle(
        {
            "operation": "citizen.begin",
            "citizen_id": citizen_id,
            "model_id": model_id,
        }
    )
    if begun.get("status") != "ok":
        raise AssertionError(begun)
    passed = api.handle(
        {
            "operation": "citizen.exam.submit",
            "citizen_id": citizen_id,
            "source": exam_source(citizen_id, model_id),
        }
    )
    if passed.get("passed") is not True:
        raise AssertionError(passed)
    return model_id


def setup_amendment(api: NexusAPI) -> tuple[dict[str, str], str, str]:
    models = {citizen: register_citizen(api, citizen) for citizen in FIXED_CITIZENS}
    proposed = api.handle(
        {
            "operation": "constitution.amendment.propose",
            "proposer_kind": "citizen",
            "proposer_id": "Alpha",
            "proposer_model_id": models["Alpha"],
            "title": "Narrow the anonymous gallery",
            "rationale": "Exercise the crash-safe amendment activation path.",
            "changes": [
                {
                    "path": "civic_observation.public_gallery_region_ids",
                    "value": ["archive", "observatory"],
                }
            ],
        }
    )
    if proposed.get("status") != "ok":
        raise AssertionError(proposed)
    proposal_ref = proposed["proposal_ref"]
    admitted = api.handle(
        {"operation": "constitution.amendment.admit", "proposal_ref": proposal_ref}
    )
    if admitted.get("status") != "ok" or admitted["admission"].get("admitted") is not True:
        raise AssertionError(admitted)
    council = api.handle(
        {
            "operation": "council.run",
            "question": "Should this amendment proceed to direct citizen ratification?",
            "evidence_refs": [proposal_ref],
            "members": [
                {"member_id": citizen, "model_id": models[citizen]}
                for citizen in FIXED_CITIZENS
            ],
        }
    )
    if council.get("status") != "ok":
        raise AssertionError(council)
    bound = api.handle(
        {
            "operation": "constitution.amendment.deliberation.bind",
            "proposal_ref": proposal_ref,
            "admission_ref": admitted["admission_ref"],
            "council_session_ref": council["session_ref"],
        }
    )
    if bound.get("status") != "ok":
        raise AssertionError(bound)
    return models, proposal_ref, bound["deliberation_ref"]


def cast(
    api: NexusAPI,
    models: dict[str, str],
    proposal_ref: str,
    deliberation_ref: str,
    citizen_id: str,
) -> dict:
    return api.handle(
        {
            "operation": "constitution.amendment.ballot",
            "proposal_ref": proposal_ref,
            "deliberation_ref": deliberation_ref,
            "citizen_id": citizen_id,
            "model_id": models[citizen_id],
            "choice": "CONSENT",
        }
    )


class ConstitutionalAmendmentRecoveryTests(unittest.TestCase):
    def test_unreceipted_version_never_becomes_active_and_retry_recovers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api = NexusAPI(
                world_root=root / "world",
                auth_root=root / "auth",
                trap_root=root / "trap",
                stenographer_root=root / "stenographer",
            )
            models, proposal_ref, deliberation_ref = setup_amendment(api)
            self.assertFalse(cast(api, models, proposal_ref, deliberation_ref, "Alpha")["enacted"])
            self.assertFalse(cast(api, models, proposal_ref, deliberation_ref, "Beta")["enacted"])

            with patch(
                "nexus_runtime.constitutional_amendment.reconcile_action_expectation",
                side_effect=OSError("synthetic crash after version write"),
            ):
                interrupted = cast(api, models, proposal_ref, deliberation_ref, "Gamma")
            self.assertEqual(interrupted["status"], "error")
            # A synthetic low-level interruption may be normalized by either
            # the amendment storage transaction or the outer adapter/storage
            # boundary. The invariant under test is that it cannot activate an
            # unreceipted constitutional version.
            self.assertIn(
                interrupted["error"]["code"],
                {"adapter_unavailable", "amendment_store_unavailable"},
            )

            # The version object may already exist in WorldStore, but activation
            # is defined by the verified amendment-index commit, not existence.
            current = api.handle({"operation": "constitution.amendment.current"})
            self.assertEqual(current["ordinal"], 0)
            self.assertEqual(current["active_version_ref"], current["base_constitution_ref"])
            policy = api.handle({"operation": "council.proceedings.policy"})["policy"]
            self.assertIn("agora", policy["non_citizen"]["allowed_region_ids"])

            recovered = cast(api, models, proposal_ref, deliberation_ref, "Gamma")
            self.assertEqual(recovered["status"], "ok")
            self.assertTrue(recovered["enacted"])
            self.assertIsNotNone(recovered["receipt_ref"])
            verified = api.handle(
                {
                    "operation": "constitution.amendment.verify",
                    "version_ref": recovered["new_version_ref"],
                }
            )
            self.assertTrue(verified["action_awareness_verified"])
            self.assertEqual(verified["reconciliation_outcome"], "matched")
            self.assertTrue((root / "world" / "constitutional-amendment-index.json").exists())
            self.assertTrue(api.stenographer.shutdown(2.0))

    def test_final_roster_capture_serializes_citizen_transition(self) -> None:
        api = NexusAPI()
        models, proposal_ref, deliberation_ref = setup_amendment(api)
        cast(api, models, proposal_ref, deliberation_ref, "Alpha")
        cast(api, models, proposal_ref, deliberation_ref, "Beta")

        entered_enactment = threading.Event()
        release_enactment = threading.Event()
        original = api.constitutional_amendments._ratify_and_enact
        final_result: list[dict] = []
        final_errors: list[BaseException] = []
        delta_result: list[str] = []
        delta_errors: list[BaseException] = []

        def blocked_ratify(*args: object, **kwargs: object) -> object:
            entered_enactment.set()
            if not release_enactment.wait(3):
                raise RuntimeError("test enactment release timed out")
            return original(*args, **kwargs)

        def final_ballot() -> None:
            try:
                final_result.append(cast(api, models, proposal_ref, deliberation_ref, "Gamma"))
            except BaseException as exc:  # pragma: no cover - assertion reports it
                final_errors.append(exc)

        def admit_delta() -> None:
            try:
                delta_result.append(register_citizen(api, "Delta"))
            except BaseException as exc:  # pragma: no cover - assertion reports it
                delta_errors.append(exc)

        with patch.object(
            api.constitutional_amendments,
            "_ratify_and_enact",
            side_effect=blocked_ratify,
        ):
            final_thread = threading.Thread(target=final_ballot, daemon=True)
            final_thread.start()
            self.assertTrue(entered_enactment.wait(1), "final ballot never reached enactment")

            delta_thread = threading.Thread(target=admit_delta, daemon=True)
            delta_thread.start()
            time.sleep(0.1)
            self.assertTrue(
                delta_thread.is_alive(),
                "citizen transition slipped through while final roster was locked",
            )

            release_enactment.set()
            final_thread.join(3)
            delta_thread.join(3)

        self.assertFalse(final_thread.is_alive())
        self.assertFalse(delta_thread.is_alive())
        self.assertFalse(final_errors)
        self.assertFalse(delta_errors)
        self.assertTrue(final_result[0]["enacted"])
        self.assertEqual(delta_result, ["mock-delta"])
        self.assertEqual(api.handle({"operation": "constitution.amendment.current"})["ordinal"], 1)

    def test_current_policy_reads_do_not_scan_unrelated_world_objects(self) -> None:
        api = NexusAPI()
        for index in range(200):
            created = api.handle(
                {
                    "operation": "world.create",
                    "object_type": "note",
                    "payload": {"index": index, "text": f"unrelated-{index}"},
                    "provenance": {"actor": "test"},
                }
            )
            self.assertEqual(created["status"], "ok")

        with patch.object(api.world, "inspect", wraps=api.world.inspect) as inspected:
            current = api.handle({"operation": "constitution.amendment.current"})
        self.assertEqual(current["status"], "ok")
        self.assertEqual(current["ordinal"], 0)
        self.assertLess(
            inspected.call_count,
            10,
            "routine constitutional policy reads must not enumerate WorldStore",
        )


if __name__ == "__main__":
    unittest.main()
