from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest import mock

from nexus_runtime import NexusAPI
from nexus_runtime.council_chair import (
    COUNCIL_CHAIR_SCHEMA,
    MAX_COUNCIL_VOTING_SEATS,
    SMALL_MODEL_THRESHOLD_MILLIONS,
    chair_policy_snapshot,
    evaluate_council_roster_request,
)


def classification(
    distribution: str,
    count_millions: int | None,
    *,
    source: str = "fixture:model-card",
) -> dict[str, object]:
    return {
        "council_classification": {
            "distribution": distribution,
            "parameter_count_millions": count_millions,
            "parameter_count_basis": "undisclosed" if count_millions is None else "total_declared",
            "parameter_count_source": source,
        }
    }


def member(
    member_id: str,
    model_id: str,
    *,
    adapter_id: str = "mock",
    distribution: str | None = None,
    count_millions: int | None = None,
    model: str | None = None,
) -> dict[str, object]:
    item: dict[str, object] = {
        "member_id": member_id,
        "model_id": model_id,
        "adapter_id": adapter_id,
    }
    if distribution is not None:
        item["capability_metadata"] = classification(distribution, count_millions)
    if model is not None:
        item["model"] = model
    return item


class CouncilChairPolicyTests(unittest.TestCase):
    def test_policy_snapshot_is_machine_readable_and_keeps_equal_vote(self) -> None:
        policy = chair_policy_snapshot()
        self.assertEqual(policy["schema"], COUNCIL_CHAIR_SCHEMA)
        self.assertEqual(policy["maximum_voting_seats"], 5)
        self.assertEqual(
            policy["protected_small_seat"]["maximum_total_parameter_count_millions"],
            20_000,
        )
        self.assertEqual(
            policy["equal_vote_rule"],
            "classification_changes_admission_only_never_vote_weight",
        )
        self.assertEqual(policy["moe_rule"], "use_total_declared_parameters_not_active_parameters_per_token")
        self.assertEqual(
            policy["unknown_unclassified_adapter"],
            "conservative_closed_general_not_protected_small",
        )

    def test_full_five_seat_roster_admits_two_closed_two_large_open_and_one_small(self) -> None:
        roster = [
            member("ClosedA", "closed-a", distribution="closed", count_millions=None),
            member("ClosedB", "closed-b", distribution="closed", count_millions=90_000),
            member("OpenA", "open-a", distribution="open_weight", count_millions=70_000),
            member("OpenB", "open-b", distribution="open_weight", count_millions=120_000),
            member("Small", "small-20b", distribution="open_weight", count_millions=20_000),
        ]
        result = evaluate_council_roster_request(roster)
        self.assertEqual(result["status"], "admitted")
        self.assertEqual(result["seat_count"], 5)
        self.assertEqual(
            result["slot_counts"],
            {"protected_small": 1, "closed_general": 2, "large_open_weight": 2},
        )
        self.assertEqual(result["vote_weight_per_seat"], 1)
        self.assertEqual(result["epistemic_privilege_per_seat"], "none")

    def test_small_closed_model_occupies_protected_slot_not_third_general_closed_slot(self) -> None:
        roster = [
            member("ClosedA", "closed-a", distribution="closed", count_millions=None),
            member("ClosedB", "closed-b", distribution="closed", count_millions=80_000),
            member("ClosedSmall", "closed-small", distribution="closed", count_millions=7_000),
        ]
        result = evaluate_council_roster_request(roster)
        self.assertEqual(result["slot_counts"]["closed_general"], 2)
        self.assertEqual(result["slot_counts"]["protected_small"], 1)
        small = next(seat for seat in result["seats"] if seat["member_id"] == "ClosedSmall")
        self.assertEqual(small["slot_class"], "protected_small")

    def test_chatgpt_and_gpt_oss_20b_can_both_be_admitted(self) -> None:
        roster = [
            member("ChatGPT", "gpt-chat", adapter_id="openai"),
            member(
                "gpt-oss",
                "gpt-oss:20b",
                adapter_id="ollama",
                distribution="open_weight",
                count_millions=20_000,
            ),
            member("IndependentSmall", "mock-small"),
        ]
        result = evaluate_council_roster_request(roster)
        seats = {seat["member_id"]: seat for seat in result["seats"]}
        self.assertEqual(seats["ChatGPT"]["slot_class"], "closed_general")
        self.assertEqual(seats["gpt-oss"]["slot_class"], "protected_small")
        self.assertEqual(seats["gpt-oss"]["parameter_count_millions"], 20_000)

    def test_missing_small_seat_is_rejected(self) -> None:
        roster = [
            member("ClosedA", "closed-a", distribution="closed", count_millions=None),
            member("ClosedB", "closed-b", distribution="closed", count_millions=None),
            member("OpenLarge", "open-large", distribution="open_weight", count_millions=70_000),
        ]
        with self.assertRaisesRegex(ValueError, "Small-Mind Guarantee"):
            evaluate_council_roster_request(roster)

    def test_more_than_two_closed_general_seats_are_rejected(self) -> None:
        roster = [
            member("Small", "small"),
            member("ClosedA", "closed-a", distribution="closed", count_millions=None),
            member("ClosedB", "closed-b", distribution="closed", count_millions=80_000),
            member("ClosedC", "closed-c", distribution="closed", count_millions=90_000),
        ]
        with self.assertRaisesRegex(ValueError, "at most 2 closed-model general seats"):
            evaluate_council_roster_request(roster)

    def test_more_than_two_large_open_weight_seats_are_rejected(self) -> None:
        roster = [
            member("Small", "small"),
            member("OpenA", "open-a", distribution="open_weight", count_millions=30_000),
            member("OpenB", "open-b", distribution="open_weight", count_millions=70_000),
            member("OpenC", "open-c", distribution="open_weight", count_millions=120_000),
        ]
        with self.assertRaisesRegex(ValueError, "at most 2 large open-weight"):
            evaluate_council_roster_request(roster)

    def test_roster_is_capped_at_five(self) -> None:
        roster = [member(f"Small{index}", f"small-{index}") for index in range(6)]
        with self.assertRaisesRegex(ValueError, "3 to 5 voting seats"):
            evaluate_council_roster_request(roster)

    def test_open_weight_requires_known_total_parameter_count(self) -> None:
        roster = [
            member("Small", "small"),
            member("Other", "other"),
            member("OpenUnknown", "open-unknown", distribution="open_weight", count_millions=None),
        ]
        with self.assertRaisesRegex(ValueError, "open-weight models require a total declared parameter count"):
            evaluate_council_roster_request(roster)

    def test_parameter_count_rejects_bool_and_uses_inclusive_20b_boundary(self) -> None:
        bad = member("Bad", "bad", distribution="open_weight", count_millions=20_000)
        metadata = bad["capability_metadata"]
        assert isinstance(metadata, dict)
        classified = metadata["council_classification"]
        assert isinstance(classified, dict)
        classified["parameter_count_millions"] = True
        with self.assertRaisesRegex(ValueError, "positive exact integer"):
            evaluate_council_roster_request([member("A", "a"), member("B", "b"), bad])

        boundary = evaluate_council_roster_request(
            [
                member("A", "a"),
                member("B", "b"),
                member(
                    "Exactly20B",
                    "exactly-20b",
                    distribution="open_weight",
                    count_millions=SMALL_MODEL_THRESHOLD_MILLIONS,
                ),
            ]
        )
        seat = next(item for item in boundary["seats"] if item["member_id"] == "Exactly20B")
        self.assertEqual(seat["slot_class"], "protected_small")

    def test_effective_model_override_cannot_fake_distinct_seats(self) -> None:
        roster = [
            member("Small", "small"),
            member(
                "LocalA",
                "declared-a",
                adapter_id="ollama",
                distribution="open_weight",
                count_millions=8_000,
                model="same-backend",
            ),
            member(
                "LocalB",
                "declared-b",
                adapter_id="ollama",
                distribution="open_weight",
                count_millions=8_000,
                model="same-backend",
            ),
        ]
        with self.assertRaisesRegex(ValueError, "distinct effective adapter/model identities"):
            evaluate_council_roster_request(roster)

    def test_unclassified_model_host_is_conservative_general_not_small(self) -> None:
        result = evaluate_council_roster_request(
            [
                member("SmallA", "small-a"),
                member("SmallB", "small-b"),
                member("Local", "local-model", adapter_id="ollama"),
            ]
        )
        local = next(seat for seat in result["seats"] if seat["member_id"] == "Local")
        self.assertEqual(local["slot_class"], "closed_general")
        self.assertIsNone(local["parameter_count_millions"])
        self.assertTrue(local["inferred"])
        self.assertIn("unclassified_adapter_conservative", local["parameter_count_source"])


class CouncilChairAPITests(unittest.TestCase):
    def test_health_advertises_hard_five_seat_chair_policy(self) -> None:
        api = NexusAPI()
        health = api.handle({"operation": "system.health"})
        self.assertEqual(health["status"], "ok")
        # council_limits remains the lower-level coordinator/spend surface for
        # backward compatibility; public voting admission is the Chair object.
        self.assertEqual(health["council_limits"], {"max_members": 32, "max_remote_seats": 4})
        chair = health["council_chair"]
        self.assertEqual(chair["schema"], COUNCIL_CHAIR_SCHEMA)
        self.assertEqual(chair["maximum_voting_seats"], MAX_COUNCIL_VOTING_SEATS)
        self.assertEqual(chair["maximum_closed_general_seats"], 2)
        self.assertEqual(chair["maximum_large_open_weight_seats"], 2)

    def test_public_council_returns_auditable_admission_summary(self) -> None:
        roster = [
            member("ClosedA", "closed-a", distribution="closed", count_millions=None),
            member("ClosedB", "closed-b", distribution="closed", count_millions=90_000),
            member("OpenA", "open-a", distribution="open_weight", count_millions=70_000),
            member("OpenB", "open-b", distribution="open_weight", count_millions=120_000),
            member("Small", "small-20b", distribution="open_weight", count_millions=20_000),
        ]
        with tempfile.TemporaryDirectory() as directory:
            api = NexusAPI(Path(directory) / "world")
            result = api.handle(
                {
                    "operation": "council.run",
                    "question": "Does scale create authority?",
                    "members": roster,
                }
            )
        self.assertEqual(result["status"], "ok", result)
        self.assertEqual(result["council_chair"]["slot_counts"]["protected_small"], 1)
        self.assertEqual(result["council_chair"]["vote_weight_per_seat"], 1)

    def test_third_closed_general_model_is_rejected_before_credentials(self) -> None:
        api = NexusAPI()
        roster = [
            member("OpenAI", "gpt", adapter_id="openai"),
            member("Anthropic", "claude", adapter_id="anthropic"),
            member("Gemini", "gemini", adapter_id="gemini"),
            member("Small", "small"),
        ]
        with mock.patch.object(api.auth, "resolve") as resolve:
            result = api.handle(
                {
                    "operation": "council.run",
                    "question": "three closed seats?",
                    "members": roster,
                }
            )
        self.assertEqual(result["status"], "error")
        self.assertIn("at most 2 closed-model general seats", result["error"]["message"])
        resolve.assert_not_called()

    def test_parole_semantic_rejection_precedes_chair_roster_shape(self) -> None:
        api = NexusAPI()
        result = api.handle(
            {
                "operation": "council.run",
                "question": "May parole vote?",
                "mode": "citizenship_parole",
                "members": [{"member_id": "Only", "model_id": "mock-only"}],
            }
        )
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "citizen_parole_has_no_council")


if __name__ == "__main__":
    unittest.main()
