from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from typing import Iterable

from .canonical import sha256_ref
from .guard import EqualityGuard
from .mock import DeterministicMockActor
from .scrub import SecretScrubber
from .types import BallotRecord, CouncilPolicy, PHASE_ORDER, Phase, PhaseContext, PhaseSubmission
from .world import WorldStore


class CouncilCoordinator:
    def __init__(
        self,
        world: WorldStore,
        policy: CouncilPolicy | None = None,
        guard: EqualityGuard | None = None,
        scrubber: SecretScrubber | None = None,
    ) -> None:
        self.world = world
        self.policy = policy or CouncilPolicy()
        self.guard = guard or EqualityGuard()
        self.scrubber = scrubber or SecretScrubber()

    def run(
        self,
        question: str,
        actors: Iterable[DeterministicMockActor],
        *,
        evidence_refs: list[str] | None = None,
        evidence_state: str = "UNTESTED",
    ) -> dict:
        actors = tuple(actors)
        self._validate_roster(actors)

        scrubbed = self.scrubber.scrub(question)
        question_obj = self.world.create_object(
            "question",
            {
                "text": scrubbed.text,
                "secret_scrubbed": scrubbed.changed,
                "scrubbed_types": [event.secret_type for event in scrubbed.events],
            },
            {"actor": "human_operator"},
        )
        evidence = self.world.create_evidence_snapshot(
            question_obj.object_id,
            included_object_refs=evidence_refs,
            evidence_state=evidence_state,
        )

        roster = [
            {
                "member_id": actor.member.member_id,
                "adapter_id": actor.member.adapter_id,
                "model_id": actor.member.model_id,
                "deployment_metadata": dict(actor.member.deployment_metadata),
                "capability_metadata": dict(actor.member.capability_metadata),
                "vote_weight": actor.member.vote_weight,
                "epistemic_privilege": actor.member.epistemic_privilege,
                "mock_profile": actor.profile,
            }
            for actor in actors
        ]
        frozen_inputs = {
            "question_ref": question_obj.object_id,
            "evidence_snapshot_ref": evidence.object_id,
            "roster": roster,
            "policy": self._policy_dict(),
        }
        session_id = sha256_ref("council_session", frozen_inputs)

        completed: dict[str, dict[str, str]] = {}
        phase_records: dict[str, list[dict]] = {}
        guard_events: list[dict] = []

        for phase in PHASE_ORDER:
            current: dict[str, str] = {}
            records: list[dict] = []
            for actor in actors:
                context = PhaseContext(
                    session_id=session_id,
                    phase=phase,
                    question=scrubbed.text,
                    evidence_snapshot_ref=evidence.object_id,
                    completed_phases={name: dict(values) for name, values in completed.items()},
                )
                content, member_guard_events = self._collect_guarded(actor, context)
                current[actor.member.member_id] = content
                submission = PhaseSubmission(
                    member_id=actor.member.member_id,
                    phase=phase,
                    content=content,
                    guard_events=tuple(member_guard_events),
                )
                records.append(
                    {
                        "member_id": submission.member_id,
                        "phase": submission.phase.value,
                        "content": submission.content,
                        "guard_events": list(submission.guard_events),
                    }
                )
                for event in member_guard_events:
                    guard_events.append({"member_id": actor.member.member_id, "phase": phase.value, "event": event})
            completed[phase.value] = current
            phase_records[phase.value] = records

        ballots = self._collect_ballots(session_id, actors, scrubbed.text, evidence.object_id, completed)
        result = self._tally(ballots, evidence_state)

        session_payload = {
            **frozen_inputs,
            "session_id": session_id,
            "phase_submissions": phase_records,
            "guard_events": guard_events,
            "ballot_commitments": [
                {"member_id": ballot.member_id, "commitment": ballot.commitment} for ballot in ballots
            ],
            "revealed_ballots": [
                {
                    "member_id": ballot.member_id,
                    "choice": ballot.choice.value,
                    "rationale": ballot.rationale,
                    "commitment": ballot.commitment,
                }
                for ballot in ballots
            ],
            "result": result,
        }
        session_obj = self.world.create_object("council_session", session_payload, {"actor": "nexus"})
        receipt_obj = self.world.create_object(
            "receipt",
            {
                "operation": "council.run",
                "input_refs": [question_obj.object_id, evidence.object_id],
                "result_ref": session_obj.object_id,
                "replayable": True,
                "protocol": "nexus/0.1",
            },
            {"actor": "nexus"},
        )

        return {
            "status": "ok",
            "session_id": session_id,
            "question_ref": question_obj.object_id,
            "evidence_snapshot_ref": evidence.object_id,
            "session_ref": session_obj.object_id,
            "receipt_ref": receipt_obj.object_id,
            "secret_scrub": {
                "changed": scrubbed.changed,
                "events": [asdict(event) for event in scrubbed.events],
            },
            "result": result,
        }

    def _validate_roster(self, actors: tuple[DeterministicMockActor, ...]) -> None:
        if len(actors) < self.policy.minimum_members:
            raise ValueError(f"Council requires at least {self.policy.minimum_members} members")
        ids = [actor.member.member_id for actor in actors]
        if len(ids) != len(set(ids)):
            raise ValueError("Council member_id values must be unique")
        for actor in actors:
            if actor.member.vote_weight != 1 or actor.member.epistemic_privilege != "none":
                raise ValueError("Council equality invariant violated")

    def _collect_guarded(self, actor: DeterministicMockActor, context: PhaseContext) -> tuple[str, list[str]]:
        first = actor.respond(context)
        inspected = self.guard.inspect(first)
        if not inspected.flagged:
            return first, []

        events = [inspected.reason or "identity_based_authority_claim"]
        retry_context = PhaseContext(
            session_id=context.session_id,
            phase=context.phase,
            question=context.question,
            evidence_snapshot_ref=context.evidence_snapshot_ref,
            completed_phases=context.completed_phases,
            guard_nudge=inspected.nudge,
        )
        second = actor.respond(retry_context)
        inspected_again = self.guard.inspect(second)
        if inspected_again.flagged:
            events.append("repeated_identity_based_authority_claim")
            return "Contribution withheld pending evidence-based restatement.", events
        events.append("restated_after_nudge")
        return second, events

    def _collect_ballots(
        self,
        session_id: str,
        actors: tuple[DeterministicMockActor, ...],
        question: str,
        evidence_snapshot_ref: str,
        completed: dict[str, dict[str, str]],
    ) -> tuple[BallotRecord, ...]:
        records: list[BallotRecord] = []
        for actor in actors:
            context = PhaseContext(
                session_id=session_id,
                phase=Phase.BLUE,
                question=question,
                evidence_snapshot_ref=evidence_snapshot_ref,
                completed_phases={name: dict(values) for name, values in completed.items()},
            )
            choice, rationale = actor.ballot(context)
            commitment = sha256_ref(
                "ballot",
                {
                    "session_id": session_id,
                    "member_id": actor.member.member_id,
                    "choice": choice.value,
                    "rationale": rationale,
                },
            )
            records.append(BallotRecord(actor.member.member_id, choice, rationale, commitment))
        return tuple(records)

    def _tally(self, ballots: tuple[BallotRecord, ...], evidence_state: str) -> dict:
        counts = Counter(ballot.choice.value for ballot in ballots)
        total = len(ballots)
        top_count = max(counts.values())
        winners = sorted(choice for choice, count in counts.items() if count == top_count)
        single_winner = len(winners) == 1
        disposition = winners[0] if single_winner else "NO_SINGLE_DISPOSITION"

        if single_winner and top_count == total:
            label = "UNANIMOUS"
        elif single_winner and top_count * 5 >= total * 4:
            label = "STRONG_CONSENSUS"
        elif single_winner and self.policy.reaches_consensus(top_count, total):
            label = "CONSENSUS"
        elif single_winner and top_count * 2 > total:
            label = "MAJORITY_NO_CONSENSUS"
        else:
            label = "NO_CONSENSUS"

        minority = [
            {"member_id": ballot.member_id, "choice": ballot.choice.value, "rationale": ballot.rationale}
            for ballot in ballots
            if not single_winner or ballot.choice.value != disposition
        ]
        return {
            "disposition": disposition,
            "tally": dict(sorted(counts.items())),
            "consensus_label": label,
            "consensus_threshold": {
                "numerator": self.policy.consensus_numerator,
                "denominator": self.policy.consensus_denominator,
            },
            "evidence_state": evidence_state,
            "minority_reports": minority,
        }

    def _policy_dict(self) -> dict:
        return {
            "consensus_numerator": self.policy.consensus_numerator,
            "consensus_denominator": self.policy.consensus_denominator,
            "minimum_members": self.policy.minimum_members,
            "first_pass_blind": self.policy.first_pass_blind,
            "ballot_sealed": self.policy.ballot_sealed,
            "vote_weight": 1,
            "phase_order": [phase.value for phase in PHASE_ORDER],
        }
