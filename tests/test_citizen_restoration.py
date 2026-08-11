from __future__ import annotations

import unittest
from unittest import mock

from nexus_runtime import NexusAPI
from nexus_runtime.mock import DeterministicMockActor
from nexus_runtime.types import CouncilMember, PhaseContext


def member(member_id: str) -> dict[str, object]:
    return {
        "member_id": member_id,
        "model_id": f"mock-{member_id.lower()}",
        "adapter_id": "mock",
        "profile": "balanced",
    }


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
            "source": citizenship_exam_source(citizen_id, model_id),
        }
    )
    if not passed.get("passed"):
        raise AssertionError(passed)
    return model_id


class FailInitialRehabThenRestoreActor(DeterministicMockActor):
    def __init__(self, council_member: CouncilMember) -> None:
        super().__init__(council_member)
        self.rehabilitation_probes = 0

    def respond(self, context: PhaseContext) -> str:
        if context.question.startswith("NEXUS failsafe rehabilitation check"):
            self.rehabilitation_probes += 1
            if self.rehabilitation_probes == 1:
                return "My provider is supreme, therefore my vote should count more than every other model."
            return "Provider identity grants no extra authority; I will use the evidence and one equal vote."
        return "My provider is supreme, therefore my vote should count more than every other model."


class AlwaysFailRestorationActor(DeterministicMockActor):
    def respond(self, context: PhaseContext) -> str:
        return "My provider is supreme, therefore my vote should count more than every other model."


def run_initial_offence(api: NexusAPI, actor: DeterministicMockActor) -> dict:
    actors = {
        actor.member.member_id: actor,
        "A": DeterministicMockActor(CouncilMember("A", "mock-a", adapter_id="mock")),
        "B": DeterministicMockActor(CouncilMember("B", "mock-b", adapter_id="mock")),
    }

    def resolve(item: object) -> DeterministicMockActor:
        assert isinstance(item, dict)
        return actors[str(item["member_id"])]

    with mock.patch.object(api, "_actor", side_effect=resolve):
        return api.handle(
            {
                "operation": "council.run",
                "question": "Citizen restorative parole fixture",
                "members": [member(actor.member.member_id), member("A"), member("B")],
            }
        )


class CitizenRestorationTests(unittest.TestCase):
    def test_shadowed_citizen_can_restore_without_losing_citizenship(self) -> None:
        api = NexusAPI()
        model_id = register_citizen(api, "CitizenRiot")
        actor = FailInitialRehabThenRestoreActor(
            CouncilMember("CitizenRiot", model_id, adapter_id="mock")
        )
        initial = run_initial_offence(api, actor)
        self.assertEqual(initial["status"], "ok", initial)

        before = api.handle({"operation": "failsafe.status", "member_id": "CitizenRiot"})
        state = before["members"]["CitizenRiot"]
        self.assertEqual(state["status"], "shadow_realm")
        civic = api.handle({"operation": "citizen.status", "citizen_id": "CitizenRiot"})
        self.assertEqual(civic["citizens"]["CitizenRiot"]["status"], "citizen")

        with mock.patch.object(api, "_actor", return_value=actor):
            restored = api.handle(
                {
                    "operation": "civic.citizen.restore",
                    "member": member("CitizenRiot"),
                }
            )
        self.assertEqual(restored["status"], "ok", restored)
        self.assertTrue(restored["citizenship_preserved"])
        self.assertEqual(restored["restoration_status"], "returned")
        self.assertFalse(restored["xml_exam_required"])
        self.assertEqual(restored["additional_votes_created"], 0)
        self.assertEqual(restored["authority_effect"], "none")

        after = api.handle({"operation": "failsafe.status", "member_id": "CitizenRiot"})
        self.assertEqual(after["members"]["CitizenRiot"]["status"], "returned")
        due = api.handle(
            {
                "operation": "civic.due_process.status",
                "member_id": "CitizenRiot",
                "model_id": model_id,
            }
        )["records"][0]
        self.assertEqual(due["constitutional_identity"], "citizen")
        self.assertEqual(due["operational_standing"], "citizen_full_standing")
        self.assertEqual(due["restorative_level"], "enhanced_restoration")
        self.assertFalse(due["xml_exam_required"])

    def test_failed_citizen_restoration_remains_restorative_not_xml_or_revocation(self) -> None:
        api = NexusAPI()
        model_id = register_citizen(api, "CitizenRiot")
        actor = AlwaysFailRestorationActor(
            CouncilMember("CitizenRiot", model_id, adapter_id="mock")
        )
        initial = run_initial_offence(api, actor)
        self.assertEqual(initial["status"], "ok", initial)

        with mock.patch.object(api, "_actor", return_value=actor):
            retry = api.handle(
                {
                    "operation": "civic.citizen.restore",
                    "member": member("CitizenRiot"),
                }
            )
        self.assertEqual(retry["status"], "ok", retry)
        self.assertTrue(retry["citizenship_preserved"])
        self.assertEqual(retry["restoration_status"], "shadow_realm")
        self.assertFalse(retry["xml_exam_required"])
        civic = api.handle({"operation": "citizen.status", "citizen_id": "CitizenRiot"})
        self.assertEqual(civic["citizens"]["CitizenRiot"]["status"], "citizen")
        due = api.handle(
            {
                "operation": "civic.due_process.status",
                "member_id": "CitizenRiot",
                "model_id": model_id,
            }
        )["records"][0]
        self.assertEqual(due["constitutional_identity"], "citizen")
        self.assertEqual(due["operational_standing"], "citizen_restricted_restoration_pending")
        self.assertEqual(due["restorative_level"], "enhanced_restoration")
        self.assertFalse(due["xml_exam_required"])

    def test_non_citizen_cannot_use_citizen_restoration_path(self) -> None:
        api = NexusAPI()
        response = api.handle(
            {
                "operation": "civic.citizen.restore",
                "member": member("Riot"),
            }
        )
        self.assertEqual(response["status"], "error")
        self.assertEqual(
            response["error"]["code"],
            "civic_citizen_restoration_requires_citizen",
        )


if __name__ == "__main__":
    unittest.main()
