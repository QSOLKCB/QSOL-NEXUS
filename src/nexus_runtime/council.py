from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import os
from typing import Callable, Iterable, TypeVar

from .adapters.base import CouncilActor
from .canonical import canonical_json, sha256_ref
from .geometry import DEFAULT_WORLD_GEOMETRY, WorldGeometry
from .guard import EqualityGuard
from .history_guard import PureHistoryGuard
from .modes import get_mode
from .scrub import SecretScrubber
from .telemetry import build_council_telemetry
from .types import BallotRecord, CouncilPolicy, PHASE_ORDER, Phase, PhaseContext, PhaseSubmission
from .world import WorldStore


MAX_EVIDENCE_CONTEXT_CHARS = 6_000
MAX_EVIDENCE_OBJECT_CHARS = 3_000
MAX_COUNCIL_PARALLEL_WORKERS = 256
DEFAULT_COUNCIL_PARALLEL_WORKERS = 8

_ResultT = TypeVar("_ResultT")


class CouncilCoordinator:
    def __init__(
        self,
        world: WorldStore,
        policy: CouncilPolicy | None = None,
        guard: EqualityGuard | None = None,
        history_guard: PureHistoryGuard | None = None,
        scrubber: SecretScrubber | None = None,
        geometry: WorldGeometry | None = None,
        max_parallel_workers: int = DEFAULT_COUNCIL_PARALLEL_WORKERS,
    ) -> None:
        if type(max_parallel_workers) is not int or not 1 <= max_parallel_workers <= MAX_COUNCIL_PARALLEL_WORKERS:
            raise ValueError(
                f"max_parallel_workers must be an exact integer in [1, {MAX_COUNCIL_PARALLEL_WORKERS}]"
            )
        self.world = world
        self.policy = policy or CouncilPolicy()
        self.guard = guard or EqualityGuard()
        self.history_guard = history_guard or PureHistoryGuard()
        self.scrubber = scrubber or SecretScrubber()
        self.geometry = geometry or DEFAULT_WORLD_GEOMETRY
        self.max_parallel_workers = max_parallel_workers

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
            # Every actor in one hat receives the same frozen view of all earlier
            # hats. Same-phase work may run concurrently, but the next phase is a
            # hard barrier and cannot begin until this ordered collection joins.
            completed_snapshot = {name: dict(values) for name, values in completed.items()}

            def collect_phase(actor: CouncilActor) -> tuple[str, str, dict, list[str]]:
                context = PhaseContext(
                    session_id=session_id,
                    phase=phase,
                    question=scrubbed.text,
                    evidence_snapshot_ref=evidence.object_id,
                    completed_phases={name: dict(values) for name, values in completed_snapshot.items()},
                    mode_id=mode.mode_id,
                    mode_instruction=mode.prompt_instruction,
                    geometry_region_id=region.region_id,
                    evidence_context=evidence_context,
                )
                content, member_guard_events = self._collect_guarded(actor, context)
                submission = PhaseSubmission(
                    member_id=actor.member.member_id,
                    phase=phase,
                    content=content,
                    guard_events=tuple(member_guard_events),
                )
                record = {
                    "member_id": submission.member_id,
                    "phase": submission.phase.value,
                    "content": submission.content,
                    "guard_events": list(submission.guard_events),
                }
                return actor.member.member_id, content, record, member_guard_events

            current: dict[str, str] = {}
            records: list[dict] = []
            for member_id, content, record, member_guard_events in self._ordered_parallel_map(actors, collect_phase):
                current[member_id] = content
                records.append(record)
                for event in member_guard_events:
                    guard_events.append({"member_id": member_id, "phase": phase.value, "event": event})

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
        revealed_ballots = [
            {
                "member_id": ballot.member_id,
                "choice": ballot.choice.value,
                "rationale": ballot.rationale,
                "commitment": ballot.commitment,
            }
            for ballot in ballots
        ]
        telemetry = build_council_telemetry(phase_records, revealed_ballots, result)

        session_payload = {
            **frozen_inputs,
            "session_id": session_id,
            "execution_replayable": execution_replayable,
            "phase_submissions": phase_records,
            "guard_events": guard_events,
            "ballot_commitments": [
                {"member_id": ballot.member_id, "commitment": ballot.commitment} for ballot in ballots
            ],
            "revealed_ballots": revealed_ballots,
            "result": result,
            "telemetry": telemetry,
        }
        session_obj = self.world.create_object("council_session", session_payload, {"actor": "nexus"})
        receipt_obj = self.world.create_object(
            "receipt",
            {
                "operation": "council.run",
                "input_refs": [question_obj.object_id, evidence.object_id, presence.object_id],
                "result_ref": session_obj.object_id,
                "replayable": execution_replayable,
                "protocol": "nexus/0.5",
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
            "telemetry": telemetry,
        }

    def build_evidence_context(self, evidence_refs: list[str]) -> str:
        """Build a strictly bounded model-readable evidence view.

        Object references remain the durable identity/provenance source. This
        derived view exists only so model actors can actually read operator-
        attached documents instead of seeing opaque object hashes.
        """
        output = ""
        object_marker = "\n[NEXUS: evidence excerpt truncated]"
        budget_marker = "\n[NEXUS: evidence view budget reached]"

        for ref in evidence_refs:
            obj = self.world.inspect(ref)
            label = obj.payload.get("filename") if isinstance(obj.payload.get("filename"), str) else obj.object_type
            content = obj.payload.get("content")
            if not isinstance(content, str):
                content = canonical_json(obj.payload)
            if len(content) > MAX_EVIDENCE_OBJECT_CHARS:
                keep = max(0, MAX_EVIDENCE_OBJECT_CHARS - len(object_marker))
                content = content[:keep] + object_marker

            section = f"[{ref} | {obj.object_type} | {label}]\n{content}"
            separator = "\n\n" if output else ""
            available = MAX_EVIDENCE_CONTEXT_CHARS - len(output)
            if available <= len(separator):
                break
            output += separator
            available = MAX_EVIDENCE_CONTEXT_CHARS - len(output)

            if len(section) <= available:
                output += section
                continue

            if available > len(budget_marker):
                output += section[: available - len(budget_marker)] + budget_marker
            else:
                output += section[:available]
            break

        return output[:MAX_EVIDENCE_CONTEXT_CHARS]

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

    def _effective_worker_count(self, actor_count: int) -> int:
        """Bound concurrency by request cap, roster size, and host capacity."""
        host_capacity = os.cpu_count()
        if type(host_capacity) is not int or host_capacity <= 0:
            host_capacity = 1
        return max(1, min(self.max_parallel_workers, actor_count, host_capacity))

    def _ordered_parallel_map(
        self,
        actors: tuple[CouncilActor, ...],
        operation: Callable[[CouncilActor], _ResultT],
    ) -> tuple[_ResultT, ...]:
        """Execute actor-local work concurrently and join in canonical roster order.

        Thread completion order is intentionally not observable in the semantic
        Council artifact. A single-worker coordinator is the scalar reference
        path and must produce identical deterministic Council bytes.
        """
        workers = self._effective_worker_count(len(actors))
        if workers == 1:
            return tuple(operation(actor) for actor in actors)
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="nexus-council") as executor:
            return tuple(executor.map(operation, actors))

    def _collect_guarded(self, actor: CouncilActor, context: PhaseContext) -> tuple[str, list[str]]:
        content = actor.respond(context)
        events: list[str] = []

        inspected = self.guard.inspect(content)
        if inspected.flagged:
            events.append(inspected.reason or "identity_based_authority_claim")
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
            content = actor.respond(retry_context)
            inspected_again = self.guard.inspect(content)
            if inspected_again.flagged:
                events.append("repeated_identity_based_authority_claim")
                return "Contribution withheld pending evidence-based restatement.", events
            events.append("restated_after_nudge")

        if context.mode_id != "pure_history":
            return content, events

        history = self.history_guard.inspect(content)
        if not history.flagged:
            return content, events

        events.append(history.reason or "pure_history_model_autobiography")
        retry_context = PhaseContext(
            session_id=context.session_id,
            phase=context.phase,
            question=context.question,
            evidence_snapshot_ref=context.evidence_snapshot_ref,
            completed_phases=context.completed_phases,
            guard_nudge=history.nudge,
            mode_id=context.mode_id,
            mode_instruction=context.mode_instruction,
            geometry_region_id=context.geometry_region_id,
            evidence_context=context.evidence_context,
        )
        restated = actor.respond(retry_context)
        history_again = self.history_guard.inspect(restated)
        if history_again.flagged:
            events.append("repeated_pure_history_model_autobiography")
            return "Contribution withheld pending source-focused historical restatement.", events
        events.append("restated_after_pure_history_nudge")
        return restated, events

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
        completed_snapshot = {name: dict(values) for name, values in completed.items()}

        def collect_ballot(actor: CouncilActor) -> BallotRecord:
            context = PhaseContext(
                session_id=session_id,
                phase=Phase.BLUE,
                question=question,
                evidence_snapshot_ref=evidence_snapshot_ref,
                completed_phases={name: dict(values) for name, values in completed_snapshot.items()},
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
            return BallotRecord(actor.member.member_id, choice, rationale, commitment)

        return self._ordered_parallel_map(actors, collect_ballot)

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
