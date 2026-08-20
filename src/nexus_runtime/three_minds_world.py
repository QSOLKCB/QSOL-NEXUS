from __future__ import annotations

import copy
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .canonical import sha256_ref
from .council import CouncilCoordinator
from .instruments import run_instrument, verify_instrument_receipt
from .mock import DeterministicMockActor
from .persistent_world import PersistentWorldService
from .three_minds_instrument import INTEGER_PRIMALITY_INSTRUMENT
from .types import CouncilMember
from .world import WorldObject, WorldStore
from .world_lattice import (
    LATTICE_PROFILE_ID,
    LATTICE_REFERENCE_PROTOCOL,
    WorldLatticeService,
)

THREE_MINDS_POLICY_ID = "nexus-three-minds-one-world/1"
THREE_MINDS_MANIFEST_SCHEMA = "nexus-three-minds-manifest/1"
THREE_MINDS_THREAD_SCHEMA = "nexus-three-minds-thread/1"
THREE_MINDS_FIXTURE_SCHEMA = "nexus-three-minds-fixture/1"
THREE_MINDS_INSTRUMENT_RECORD_SCHEMA = "nexus-three-minds-instrument-record/1"
THREE_MINDS_CRITIQUE_SCHEMA = "nexus-three-minds-critique/1"
THREE_MINDS_FALSIFIER_SCHEMA = "nexus-three-minds-falsifier/1"
THREE_MINDS_DESCENDANT_SCHEMA = "nexus-three-minds-verified-descendant/1"
THREE_MINDS_SUMMARY_SCHEMA = "nexus-three-minds-summary/1"

THREE_MINDS_PROVENANCE = {"actor": "nexus", "subsystem": "three-minds-one-world"}

DECLARED_VALUES = (2, 3, 5, 7, 11, 25)
BASELINE_VALUES = (2, 3, 5, 7, 11)
FALSIFIER_VALUES = (25,)

_OBJECT_REF_PREFIX = "object:"


class ThreeMindsError(ValueError):
    pass


def three_minds_policy_snapshot() -> dict[str, Any]:
    return {
        "schema": THREE_MINDS_POLICY_ID,
        "milestone": "2.0-alpha11",
        "reference_execution": "deterministic_file_backed_three_actor_handoff",
        "actor_model_semantics": "reference_actor_identities_not_live_model_execution",
        "world": "existing content-addressed WorldStore + alpha8 persistent-world lineage",
        "instrument": INTEGER_PRIMALITY_INSTRUMENT,
        "instrument_admission": "existing alpha7 admitted instrument only",
        "presence": "existing world-lattice placement and adjacent movement events",
        "council": "deterministic mock Council preserves minority report in the same world",
        "mixed_provider_demo": "optional operator-authorized xAI + loopback Ollama + mock Council",
        "authority_effect": "none",
        "boundaries": [
            "PERSISTENT_LINEAGE != TRUTH",
            "INSTRUMENT_RESULT != TRUTH",
            "REPLAY != EMPIRICAL_CONFIRMATION",
            "MINORITY_REPORT != EVIDENCE_PROMOTION",
            "MULTI_MODEL_CONSENSUS != EVIDENCE",
            "LATTICE_POSITION != COGNITIVE_COORDINATE",
            "VERIFIED_DESCENDANT != SEMANTIC_TRUTH",
        ],
    }


def _lattice_reference(address: str) -> dict[str, Any]:
    return {
        "protocol": LATTICE_REFERENCE_PROTOCOL,
        "profile_id": LATTICE_PROFILE_ID,
        "address": address,
        "authority": "storage-only",
    }


def _demo_object(world: WorldStore, object_type: str, payload: dict[str, Any]) -> WorldObject:
    return world.create_object(
        object_type,
        {**copy.deepcopy(payload), "authority_effect": "none"},
        copy.deepcopy(THREE_MINDS_PROVENANCE),
    )


def _require_demo_object(world: WorldStore, object_ref: str, object_type: str, schema: str) -> WorldObject:
    if not isinstance(object_ref, str) or not object_ref.startswith(_OBJECT_REF_PREFIX):
        raise ThreeMindsError("three-minds reference must contain WorldStore object references")
    try:
        obj = world.inspect(object_ref)
    except (KeyError, ValueError) as exc:
        raise ThreeMindsError(f"three-minds object missing or invalid: {object_ref}") from exc
    if obj.object_type != object_type:
        raise ThreeMindsError(f"three-minds object type mismatch for {object_ref}")
    if obj.provenance != THREE_MINDS_PROVENANCE:
        raise ThreeMindsError(f"three-minds provenance mismatch for {object_ref}")
    if obj.payload.get("schema") != schema or obj.payload.get("authority_effect") != "none":
        raise ThreeMindsError(f"three-minds schema/boundary mismatch for {object_ref}")
    return obj


def _persist_instrument_record(
    world: WorldStore,
    *,
    actor_id: str,
    role: str,
    values: list[int],
    reproduces_record_ref: str | None = None,
) -> tuple[WorldObject, dict[str, Any]]:
    bundle = run_instrument(INTEGER_PRIMALITY_INSTRUMENT, {"values": list(values)})
    verification = verify_instrument_receipt(bundle)
    record = _demo_object(
        world,
        "three_minds_instrument_record",
        {
            "schema": THREE_MINDS_INSTRUMENT_RECORD_SCHEMA,
            "actor_id": actor_id,
            "role": role,
            "input_values": list(values),
            "bundle": bundle,
            "verification": verification,
            "reproduces_record_ref": reproduces_record_ref,
            "derived_material_only": True,
            "semantic_truth_claimed": False,
        },
    )
    return record, bundle


def _discover_ref(result: Mapping[str, Any], object_ref: str, *, label: str) -> None:
    matches = result.get("matches")
    if not isinstance(matches, list) or object_ref not in {
        item.get("object_id") for item in matches if isinstance(item, Mapping)
    }:
        raise ThreeMindsError(f"{label} was not discoverable after actor handoff")


def _reference_council(world: WorldStore, evidence_refs: list[str]) -> dict[str, Any]:
    actors = (
        DeterministicMockActor(
            CouncilMember("Mind-A", "alpha11-mock-a", adapter_id="mock"),
            profile="skeptical",
        ),
        DeterministicMockActor(
            CouncilMember("Mind-B", "alpha11-mock-b", adapter_id="mock"),
            profile="balanced",
        ),
        DeterministicMockActor(
            CouncilMember("Mind-C", "alpha11-mock-c", adapter_id="mock"),
            profile="supportive",
        ),
    )
    return CouncilCoordinator(world).run(
        (
            "Alpha11 reference Council: given the bounded replay, critique and explicit "
            "counterexample, what conclusion is justified without promoting derived material to truth?"
        ),
        actors,
        evidence_refs=evidence_refs,
        evidence_state="UNTESTED",
        mode_id="analytical",
    )


def run_three_minds_reference(world_root: str | Path) -> dict[str, Any]:
    """Run the deterministic alpha11 reference scenario in one durable world.

    Each mind reopens the file-backed WorldStore instead of sharing a Python
    service instance. That makes persistence/discovery part of the conformance
    demonstration rather than an in-memory convenience.
    """

    root = Path(world_root).absolute()

    # Mind A: declare the full candidate fixture, form the hypothesis, execute
    # an incomplete baseline test, and leave the shared thread in Observatory.
    world_a = WorldStore(root)
    persistent_a = PersistentWorldService(world_a)
    lattice_a = WorldLatticeService(world_a)

    thread = _demo_object(
        world_a,
        "three_minds_thread",
        {
            "schema": THREE_MINDS_THREAD_SCHEMA,
            "policy": THREE_MINDS_POLICY_ID,
            "title": "Three Minds, One World bounded prime-candidate thread",
            "actor_order": ["Mind-A", "Mind-B", "Mind-C"],
            "claim_boundary": "reference_conformance_scenario_not_live_model_execution",
        },
    )
    fixture = _demo_object(
        world_a,
        "three_minds_fixture",
        {
            "schema": THREE_MINDS_FIXTURE_SCHEMA,
            "declared_values": list(DECLARED_VALUES),
            "baseline_values": list(BASELINE_VALUES),
            "initially_untested_values": [25],
            "claim_boundary": "fixture_definition_not_evidence",
        },
    )
    hypothesis_a = persistent_a.create_hypothesis(
        statement="Every value in the declared alpha11 candidate fixture [2,3,5,7,11,25] is prime.",
        state="PROPOSED",
        evidence_refs=[],
    )
    plan_a = persistent_a.create_experiment(
        title="Alpha11 candidate-primality check",
        stage="PLANNED",
        method=(
            "Run the admitted bounded integer-primality instrument over baseline_values only; "
            "the initially_untested_values remain outside this first execution."
        ),
        hypothesis_refs=[hypothesis_a.object_id],
        input_refs=[fixture.object_id],
        result_refs=[],
    )
    instrument_a, bundle_a = _persist_instrument_record(
        world_a,
        actor_id="Mind-A",
        role="initial_baseline_execution",
        values=list(BASELINE_VALUES),
    )
    observed_a = persistent_a.create_experiment(
        title="Alpha11 candidate-primality check",
        stage="OBSERVED",
        method="Record Mind-A's admitted baseline instrument execution without generalizing beyond its input.",
        hypothesis_refs=[hypothesis_a.object_id],
        input_refs=[fixture.object_id],
        result_refs=[instrument_a.object_id],
        previous_experiment_ref=plan_a.object_id,
    )
    relation_a = persistent_a.create_relation(
        relation_type="tests",
        source_ref=observed_a.object_id,
        target_ref=hypothesis_a.object_id,
        metadata={"scope": "baseline_values_only", "semantic_effect": "none"},
    )
    presence_a = lattice_a.place(
        thread.object_id,
        "observatory",
        _lattice_reference("L[0,0,0]"),
    )

    # Mind B: reopen the world, discover A's exact objects, replay the same
    # admitted instrument, and preserve a critique about the untested value.
    world_b = WorldStore(root)
    persistent_b = PersistentWorldService(world_b)
    lattice_b = WorldLatticeService(world_b)
    _discover_ref(
        persistent_b.search_hypotheses(state="PROPOSED", limit=50),
        hypothesis_a.object_id,
        label="Mind-A hypothesis",
    )
    _discover_ref(
        persistent_b.search_experiments(stage="OBSERVED", limit=50),
        observed_a.object_id,
        label="Mind-A observed experiment",
    )
    fixture_b = world_b.inspect(fixture.object_id)
    baseline_values = fixture_b.payload.get("baseline_values")
    if baseline_values != list(BASELINE_VALUES):
        raise ThreeMindsError("Mind-B discovered a fixture with unexpected baseline values")
    instrument_b, bundle_b = _persist_instrument_record(
        world_b,
        actor_id="Mind-B",
        role="deterministic_baseline_replay",
        values=list(BASELINE_VALUES),
        reproduces_record_ref=instrument_a.object_id,
    )
    if bundle_b != bundle_a:
        raise ThreeMindsError("Mind-B deterministic replay did not reproduce Mind-A instrument bytes")
    critique_b = _demo_object(
        world_b,
        "three_minds_critique",
        {
            "schema": THREE_MINDS_CRITIQUE_SCHEMA,
            "actor_id": "Mind-B",
            "hypothesis_ref": hypothesis_a.object_id,
            "experiment_ref": observed_a.object_id,
            "replay_record_ref": instrument_b.object_id,
            "critique": (
                "The baseline replay is exact, but it never evaluates declared value 25. "
                "Exact replay of an incomplete test does not establish the full fixture claim."
            ),
            "claim_boundary": "critique_is_interpretation_not_evidence_promotion",
        },
    )
    hypothesis_b = persistent_b.create_hypothesis(
        statement="Every value in the declared alpha11 candidate fixture [2,3,5,7,11,25] is prime.",
        state="CHALLENGED",
        evidence_refs=[],
        previous_hypothesis_ref=hypothesis_a.object_id,
    )
    observed_b = persistent_b.create_experiment(
        title="Alpha11 candidate-primality check",
        stage="OBSERVED",
        method="Replay the baseline exactly and record the bounded critique without changing the tested fixture.",
        hypothesis_refs=[hypothesis_b.object_id],
        input_refs=[fixture.object_id],
        result_refs=[instrument_a.object_id, instrument_b.object_id, critique_b.object_id],
        previous_experiment_ref=observed_a.object_id,
    )
    relation_b_replay = persistent_b.create_relation(
        relation_type="replays",
        source_ref=instrument_b.object_id,
        target_ref=instrument_a.object_id,
        metadata={"byte_identical_instrument_bundle": True, "authority_effect": "none"},
    )
    relation_b_critique = persistent_b.create_relation(
        relation_type="critiques",
        source_ref=critique_b.object_id,
        target_ref=hypothesis_b.object_id,
        metadata={"reason": "declared_value_25_untested", "semantic_effect": "none"},
    )
    presence_b = lattice_b.move(
        thread.object_id,
        presence_a.object_id,
        "archive",
        _lattice_reference("L[0,0,1]"),
    )

    # Mind C: reopen the same world, discover B's challenged lineage, propose
    # the explicit counterexample, execute the admitted instrument, and create
    # a descendant whose verification claim is receipt-level only.
    world_c = WorldStore(root)
    persistent_c = PersistentWorldService(world_c)
    lattice_c = WorldLatticeService(world_c)
    _discover_ref(
        persistent_c.search_hypotheses(state="CHALLENGED", limit=50),
        hypothesis_b.object_id,
        label="Mind-B challenged hypothesis",
    )
    _discover_ref(
        persistent_c.search_experiments(stage="OBSERVED", limit=50),
        observed_b.object_id,
        label="Mind-B replay experiment",
    )
    falsifier_c = _demo_object(
        world_c,
        "three_minds_falsifier",
        {
            "schema": THREE_MINDS_FALSIFIER_SCHEMA,
            "actor_id": "Mind-C",
            "hypothesis_ref": hypothesis_b.object_id,
            "candidate_values": list(FALSIFIER_VALUES),
            "rationale": "Evaluate the declared but previously untested value 25 as a bounded counterexample candidate.",
            "claim_boundary": "candidate_falsifier_until_admitted_instrument_execution",
        },
    )
    instrument_c, bundle_c = _persist_instrument_record(
        world_c,
        actor_id="Mind-C",
        role="counterexample_execution",
        values=list(FALSIFIER_VALUES),
    )
    if bundle_c["execution"]["result"].get("composite_values") != [25]:
        raise ThreeMindsError("Mind-C counterexample execution did not classify 25 as composite")
    closed_c = persistent_c.create_experiment(
        title="Alpha11 candidate-primality check",
        stage="CLOSED",
        method=(
            "Execute the admitted bounded instrument on declared value 25 and close this workflow lineage; "
            "closure records the result but does not turn workflow state into a general truth oracle."
        ),
        hypothesis_refs=[hypothesis_b.object_id],
        input_refs=[fixture.object_id, falsifier_c.object_id],
        result_refs=[
            instrument_a.object_id,
            instrument_b.object_id,
            falsifier_c.object_id,
            instrument_c.object_id,
        ],
        previous_experiment_ref=observed_b.object_id,
    )
    hypothesis_c = persistent_c.create_hypothesis(
        statement="Every value in the declared alpha11 candidate fixture [2,3,5,7,11,25] is prime.",
        state="RETIRED",
        evidence_refs=[instrument_c.object_id],
        previous_hypothesis_ref=hypothesis_b.object_id,
    )
    relation_c_falsifier = persistent_c.create_relation(
        relation_type="tests_counterexample_for",
        source_ref=falsifier_c.object_id,
        target_ref=hypothesis_c.object_id,
        metadata={"candidate_value": 25, "semantic_effect": "none"},
    )
    verified_descendant = _demo_object(
        world_c,
        "three_minds_verified_descendant",
        {
            "schema": THREE_MINDS_DESCENDANT_SCHEMA,
            "actor_id": "Mind-C",
            "closed_experiment_ref": closed_c.object_id,
            "retired_hypothesis_ref": hypothesis_c.object_id,
            "instrument_record_ref": instrument_c.object_id,
            "instrument_execution_ref": bundle_c["execution_ref"],
            "instrument_receipt_ref": bundle_c["receipt"]["receipt_ref"],
            "receipt_verification": verify_instrument_receipt(bundle_c),
            "verified_scope": "admitted_instrument_receipt_and_exact_input_only",
            "semantic_truth_claimed": False,
        },
    )
    relation_c_verified = persistent_c.create_relation(
        relation_type="verifies_receipt_for",
        source_ref=verified_descendant.object_id,
        target_ref=closed_c.object_id,
        metadata={"verified_scope": "instrument_receipt_only", "authority_effect": "none"},
    )
    presence_c = lattice_c.move(
        thread.object_id,
        presence_b.object_id,
        "agora",
        _lattice_reference("L[0,1,1]"),
    )

    council = _reference_council(
        world_c,
        [critique_b.object_id, instrument_c.object_id, hypothesis_c.object_id, verified_descendant.object_id],
    )
    minority = persistent_c.search_minority_reports(
        choice="ACCEPT_WITH_CHANGES",
        member_id="Mind-C",
        limit=10,
    )
    if minority.get("returned") != 1:
        raise ThreeMindsError("deterministic alpha11 Council did not preserve the expected minority report")
    final_presence = lattice_c.move(
        thread.object_id,
        presence_c.object_id,
        "observatory",
        _lattice_reference("L[1,1,1]"),
    )

    summary = _demo_object(
        world_c,
        "three_minds_summary",
        {
            "schema": THREE_MINDS_SUMMARY_SCHEMA,
            "policy": THREE_MINDS_POLICY_ID,
            "thread_ref": thread.object_id,
            "fixture_ref": fixture.object_id,
            "mind_a": {
                "hypothesis_ref": hypothesis_a.object_id,
                "plan_ref": plan_a.object_id,
                "instrument_record_ref": instrument_a.object_id,
                "observed_experiment_ref": observed_a.object_id,
                "relation_ref": relation_a.object_id,
                "presence_ref": presence_a.object_id,
            },
            "mind_b": {
                "replay_record_ref": instrument_b.object_id,
                "critique_ref": critique_b.object_id,
                "challenged_hypothesis_ref": hypothesis_b.object_id,
                "observed_experiment_ref": observed_b.object_id,
                "replay_relation_ref": relation_b_replay.object_id,
                "critique_relation_ref": relation_b_critique.object_id,
                "presence_ref": presence_b.object_id,
            },
            "mind_c": {
                "falsifier_ref": falsifier_c.object_id,
                "instrument_record_ref": instrument_c.object_id,
                "closed_experiment_ref": closed_c.object_id,
                "retired_hypothesis_ref": hypothesis_c.object_id,
                "verified_descendant_ref": verified_descendant.object_id,
                "falsifier_relation_ref": relation_c_falsifier.object_id,
                "verified_relation_ref": relation_c_verified.object_id,
                "presence_ref": presence_c.object_id,
            },
            "council": {
                "session_ref": council["session_ref"],
                "receipt_ref": council["receipt_ref"],
                "execution_replayable": council["execution_replayable"],
                "consensus_label": council["result"].get("consensus_label"),
                "minority_report_count": len(council["result"].get("minority_reports", [])),
                "minority_search_returned": minority["returned"],
            },
            "final_presence_ref": final_presence.object_id,
            "replay": {
                "mind_b_reproduced_mind_a_instrument_bundle": True,
                "instrument_execution_ref": bundle_a["execution_ref"],
                "instrument_receipt_ref": bundle_a["receipt"]["receipt_ref"],
            },
            "boundaries": three_minds_policy_snapshot()["boundaries"],
        },
    )
    summary_relation = persistent_c.create_relation(
        relation_type="summarizes",
        source_ref=summary.object_id,
        target_ref=thread.object_id,
        metadata={"milestone": "2.0-alpha11", "authority_effect": "none"},
    )

    manifest_body = {
        "schema": THREE_MINDS_MANIFEST_SCHEMA,
        "policy": THREE_MINDS_POLICY_ID,
        "summary_ref": summary.object_id,
        "summary_relation_ref": summary_relation.object_id,
        "thread_ref": thread.object_id,
        "fixture_ref": fixture.object_id,
        "final_presence_ref": final_presence.object_id,
        "mind_a_instrument_record_ref": instrument_a.object_id,
        "mind_b_replay_record_ref": instrument_b.object_id,
        "mind_c_instrument_record_ref": instrument_c.object_id,
        "verified_descendant_ref": verified_descendant.object_id,
        "council_session_ref": council["session_ref"],
        "council_receipt_ref": council["receipt_ref"],
        "minority_report_count": len(council["result"].get("minority_reports", [])),
        "authority_effect": "none",
    }
    return {**manifest_body, "manifest_ref": sha256_ref("three-minds-manifest", manifest_body)}


def verify_three_minds_reference(world_root: str | Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(manifest, Mapping) or manifest.get("schema") != THREE_MINDS_MANIFEST_SCHEMA:
        raise ThreeMindsError("unsupported three-minds manifest")
    body = {key: copy.deepcopy(value) for key, value in manifest.items() if key != "manifest_ref"}
    expected_manifest_ref = sha256_ref("three-minds-manifest", body)
    if manifest.get("manifest_ref") != expected_manifest_ref:
        raise ThreeMindsError("three-minds manifest_ref mismatch")
    if manifest.get("policy") != THREE_MINDS_POLICY_ID or manifest.get("authority_effect") != "none":
        raise ThreeMindsError("three-minds manifest violates policy or authority boundary")

    world = WorldStore(Path(world_root).absolute())
    summary = _require_demo_object(
        world,
        manifest["summary_ref"],
        "three_minds_summary",
        THREE_MINDS_SUMMARY_SCHEMA,
    )
    _require_demo_object(
        world,
        manifest["thread_ref"],
        "three_minds_thread",
        THREE_MINDS_THREAD_SCHEMA,
    )
    _require_demo_object(
        world,
        manifest["fixture_ref"],
        "three_minds_fixture",
        THREE_MINDS_FIXTURE_SCHEMA,
    )
    descendant = _require_demo_object(
        world,
        manifest["verified_descendant_ref"],
        "three_minds_verified_descendant",
        THREE_MINDS_DESCENDANT_SCHEMA,
    )
    instrument_records = []
    for key in (
        "mind_a_instrument_record_ref",
        "mind_b_replay_record_ref",
        "mind_c_instrument_record_ref",
    ):
        record = _require_demo_object(
            world,
            manifest[key],
            "three_minds_instrument_record",
            THREE_MINDS_INSTRUMENT_RECORD_SCHEMA,
        )
        verify_instrument_receipt(record.payload["bundle"])
        instrument_records.append(record)
    if instrument_records[0].payload["bundle"] != instrument_records[1].payload["bundle"]:
        raise ThreeMindsError("Mind-B replay no longer reproduces Mind-A instrument bundle")
    if instrument_records[2].payload["bundle"]["execution"]["result"].get("composite_values") != [25]:
        raise ThreeMindsError("Mind-C falsifier result no longer contains composite value 25")

    lattice = WorldLatticeService(world)
    presence = lattice.presence(manifest["final_presence_ref"])
    if presence.get("lineage_length") != 4 or presence.get("current", {}).get("region_id") != "observatory":
        raise ThreeMindsError("three-minds world-presence handoff lineage is invalid")

    persistent = PersistentWorldService(world)
    minority = persistent.search_minority_reports(
        choice="ACCEPT_WITH_CHANGES",
        member_id="Mind-C",
        limit=10,
    )
    if minority.get("returned") != 1 or manifest.get("minority_report_count") != 1:
        raise ThreeMindsError("three-minds minority-report preservation check failed")
    if descendant.payload.get("semantic_truth_claimed") is not False:
        raise ThreeMindsError("verified descendant attempts to widen receipt verification into semantic truth")
    if summary.payload.get("authority_effect") != "none":
        raise ThreeMindsError("three-minds summary attempts authority escalation")

    return {
        "status": "verified",
        "manifest_ref": expected_manifest_ref,
        "summary_ref": summary.object_id,
        "final_presence_ref": manifest["final_presence_ref"],
        "presence_lineage_length": presence["lineage_length"],
        "minority_report_count": minority["returned"],
        "mind_b_replay_exact": True,
        "mind_c_counterexample": [25],
        "authority_effect": "none",
    }


def mixed_provider_council_request(
    *,
    xai_profile: str,
    xai_model: str,
    ollama_model: str,
    question: str,
) -> dict[str, Any]:
    """Build the optional non-hermetic alpha11 Council request.

    Credentials are not accepted here. The xAI member contains only the named
    operational auth-profile reference and the existing runtime resolves it.
    """

    for field, value in (
        ("xai_profile", xai_profile),
        ("xai_model", xai_model),
        ("ollama_model", ollama_model),
        ("question", question),
    ):
        if not isinstance(value, str) or not value.strip() or len(value) > 4096:
            raise ThreeMindsError(f"{field} must be bounded non-empty text")
    return {
        "operation": "council.run",
        "question": question,
        "mode": "analytical",
        "evidence_state": "UNTESTED",
        "members": [
            {
                "member_id": "RemoteXAI",
                "model_id": xai_model,
                "adapter_id": "xai",
                "auth_profile": xai_profile,
                "timeout_seconds": 600,
            },
            {
                "member_id": "LocalOpen",
                "model_id": ollama_model,
                "adapter_id": "ollama",
                "model": ollama_model,
                "endpoint": "http://127.0.0.1:11434",
                "timeout_seconds": 120,
            },
            {
                "member_id": "ReferenceMind",
                "model_id": "alpha11-reference-mock",
                "adapter_id": "mock",
                "profile": "skeptical",
            },
        ],
    }


__all__ = [
    "BASELINE_VALUES",
    "DECLARED_VALUES",
    "FALSIFIER_VALUES",
    "THREE_MINDS_MANIFEST_SCHEMA",
    "THREE_MINDS_POLICY_ID",
    "ThreeMindsError",
    "mixed_provider_council_request",
    "run_three_minds_reference",
    "three_minds_policy_snapshot",
    "verify_three_minds_reference",
]
