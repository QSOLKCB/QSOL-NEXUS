from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from typing import Iterable

from .adapters.base import CouncilActor
from .canonical import canonical_json, sha256_ref
from .geometry import DEFAULT_WORLD_GEOMETRY, WorldGeometry
from .guard import EqualityGuard
from .modes import get_mode
from .scrub import SecretScrubber
from .types import BallotRecord, CouncilPolicy, PHASE_ORDER, Phase, PhaseContext, PhaseSubmission
from .world import WorldStore


MAX_EVIDENCE_CONTEXT_CHARS = 6_000
MAX_EVIDENCE_OBJECT_CHARS = 3_000


class CouncilCoordinator:
    def __init__(
        self,
        world: WorldStore,
        policy: CouncilPolicy | None = None,
        guard: EqualityGuard | None = None,
        scrubber: SecretScrubber | None = None,
        geometry: WorldGeometry | None = None,
    ) -> None:
        self.world = world
        self.policy = policy or CouncilPolicy()
        self.guard = guard or EqualityGuard()
        self.scrubber = scrubber or SecretScrubber()
        self.geometry = geometry or DEFAULT_WORLD_GEOMETRY

    def run(
        self,
        question: str,
        actors: Iterable[CouncilActor],
        *,
        evidence_refs: list[str] | None = None,
        evidence_state: str = "UNTESTED",
        mode_id: str = "analytical",
    ) -> dict:
        actors = tuple(actors)
        self._validate_roster(actors)
        mode = get_mode(mode_id)
        region = self.geometry.region_for_mode(mode.mode_id)
        geometry_snapshot = self.geometry.snapshot()
        evidence_refs = list(evidence_refs or [])
        evidence_context = self.build_evidence_context(evidence_refs)

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

        roster = []
        for actor in actors:
            metadata = actor.identity_metadata()
            roster.append(
                {
                    "member_id": actor.member.member_id,
                    "adapter_id": actor.member.adapter_id,
                    "model_id": actor.member.model_id,
                    "deployment_metadata": dict(actor.member.deployment_metadata),
                    "capability_metadata": dict(actor.member.capability_metadata),
                    "vote_weight": actor.member.vote_weight,
                    "epistemic_privilege": actor.member.epistemic_privilege,
                    "actor_metadata": metadata,
                }
            )

        presence = self.world.create_object(
            "world_presence",
            {
                "mode_id": mode.mode_id,
                "mode_label": mode.label,
                "region_id": region.region_id,
                "region_label": region.label,
                "coordinates": [region.x, region.y],
                "member_ids": [actor.member.member_id for actor in actors],
                "question_ref": question_obj.object_id,
                "geometry_id": geometry_snapshot["geometry_id"],
                "geometry_topology_ref": geometry_snapshot["topology_ref"],
            },
            {"actor": "nexus"},
        )

        frozen_inputs = {
            "question_ref": question_obj.object_id,
            "evidence_snapshot_ref": evidence.object_id,
            "world_presence_ref": presence.object_id,
            "world_mode": mode.as_dict(),
            "geometry_region": region.as_dict(),
            "roster": roster,
            "policy": self._policy_dict(),
        }
        session_id = sha256_ref("council_session", frozen_inputs)
        execution_replayable = all(actor.replayable for actor in actors)

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
                    mode_id=mode.mode_id,
                    mode_instruction=mode.prompt_instruction,
                    geometry_region_id=region.region_id,
                    evidence_context=evidence_context,
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

        ballots = self._collect_ballots(
            session_id,
            actors,
            scrubbed.text,
            evidence.object_id,
            completed,
            mode_id=mode.mode_id,
            mode_instruction=mode.prompt_instruction,
            geometry_region_id=region.region_id,
            evidence_context=evidence_context,
        )
        result = self._tally(ballots, evidence_state)

        session_payload = {
            **frozen_inputs,
            "session_id": session_id,
            "execution_replayable": execution_replayable,
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
                "input_refs": [question_obj.object_id, evidence.object_id, presence.object_id],
                "result_ref": session_obj.object_id,
                "replayable": execution_replayable,
                "protocol": "nexus/0.4",
            },
            {"actor": "nexus"},
        )

        return {
            "status": "ok",
            "session_id": session_id,
            "question_ref": question_obj.object_id,
            "evidence_snapshot_ref": evidence.object_id,
            "world_presence_ref": presence.object_id,
            "mode_id": mode.mode_id,
            "geometry_region_id": region.region_id,
            "session_ref": session_obj.object_id,
            "receipt_ref": receipt_obj.object_id,
            "execution_replayable": execution_replayable,
            "evidence_context_chars": len(evidence_context),
            "secret_scrub": {
                "changed": scrubbed.changed,
                "events": [asdict(event) for event in scrubbed.events],
            },
            "result": result,
        }

    def build_evidence_context(self, evidence_refs: list[str]) -> str:
        """Build a bounded model-readable view over content-addressed evidence.

        Object references remain the durable identity/provenance source. This
        derived view exists only so model actors can actually read operator-
        attached documents instead of seeing opaque object hashes.
        """
        sections: list[str] = []
        remaining = MAX_EVIDENCE_CONTEXT_CHARS
        for ref in evidence_refs:
            obj = self.world.inspect(ref)
            label = obj.payload.get("filename") if isinstance(obj.payload.get("filename"), str) else obj.object_type
            content = obj.payload.get("content")
            if not isinstance(content, str):
                content = canonical_json(obj.payload)
            if len(content) > MAX_EVIDENCE_OBJECT_CHARS:
                content = content[:MAX_EVIDENCE_OBJECT_CHARS] + "\n[NEXUS: evidence excerpt truncated]"
            section = f"[{ref} | {obj.object_type} | {label}]\n{content}"
            if len(section) > remaining:
                if remaining > 96:
                    sections.append(section[:remaining] + "\n[NEXUS: evidence view budget reached]")
                break
            sections.append(section)
            remaining -= len(section)
            if remaining <= 0:
                break
        return "\n\n".join(sections)

    def _validate_roster(self, actors: tuple[CouncilActor, ...]) -> None:
        if len(actors) < self.policy.minimum_members:
            raise ValueError(f"Council requires at least {self.policy.minimum_members} members")
        ids = [actor.member.member_id for actor in actors]
        if len(ids) != len(set(ids)):
            raise ValueError("Council member_id values must be unique")
        for actor in actors:
            if type(actor.member.vote_weight) is not int or actor.member.vote_weight != 1:
                raise ValueError("Council equality invariant violated")
            if actor.member.epistemic_privilege != "none":
                raise ValueError("Council equality invariant violated")

    def _collect_guarded(self, actor: CouncilActor, context: PhaseContext) -> tuple[str, list[str]]:
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
            mode_id=context.mode_id,
            mode_instruction=context.mode_instruction,
            geometry_region_id=context.geometry_region_id,
            evidence_context=context.evidence_context,
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
        actors: tuple[CouncilActor, ...],
        question: str,
        evidence_snapshot_ref: str,
        completed: dict[str, dict[str, str]],
        *,
        mode_id: str,
        mode_instruction: str,
        geometry_region_id: str,
        evidence_context: str,
    ) -> tuple[BallotRecord, ...]:
        records: list[BallotRecord] = []
        for actor in actors:
            context = PhaseContext(
                session_id=session_id,
                phase=Phase.BLUE,
                question=question,
                evidence_snapshot_ref=evidence_snapshot_ref,
                completed_phases={name: dict(values) for name, values in completed.items()},
                mode_id=mode_id,
                mode_instruction=mode_instruction,
                geometry_region_id=geometry_region_id,
                evidence_context=evidence_context,
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
        reaches_threshold = single_winner and self.policy.reaches_consensus(top_count, total)

        if single_winner and top_count == total:
            label = "UNANIMOUS"
        elif reaches_threshold and top_count * 5 >= total * 4:
            label = "STRONG_CONSENSUS"
        elif reaches_threshold:
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
