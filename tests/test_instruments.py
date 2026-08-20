from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from nexus_runtime import NexusAPI
from nexus_runtime.canonical import sha256_ref
from nexus_runtime.instruments import (
    INSTRUMENT_POLICY_ID,
    InstrumentAdmissionError,
    instrument_catalog,
    instrument_policy_snapshot,
    instrument_spec,
    run_instrument,
    verify_instrument_receipt,
)
from nexus_runtime.persistent_world import (
    MAX_EXCHANGE_BYTES,
    PERSISTENT_WORLD_EXPORT_SCHEMA,
    PERSISTENT_WORLD_POLICY_ID,
    PersistentWorldError,
    PersistentWorldService,
    WORLD_EXPERIMENT_OBJECT_TYPE,
    WORLD_HYPOTHESIS_OBJECT_TYPE,
    WORLD_IMPORTED_OBJECT_TYPE,
    WORLD_IMPORT_RECEIPT_OBJECT_TYPE,
    WORLD_RELATION_OBJECT_TYPE,
    persistent_world_policy_snapshot,
    validate_world_export_bundle,
)
from nexus_runtime.persistent_world_api import PersistentWorldNexusAPI
from nexus_runtime.three_minds_instrument import INTEGER_PRIMALITY_INSTRUMENT
from nexus_runtime.world import WorldStore


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


class PersistentWorldPolicyTests(unittest.TestCase):
    def test_policy_preserves_existing_canonical_foundations_and_zero_authority(self) -> None:
        policy = persistent_world_policy_snapshot()
        self.assertEqual(policy["schema"], PERSISTENT_WORLD_POLICY_ID)
        self.assertEqual(policy["authority_effect"], "none")
        self.assertIn("RELATION != FACT", policy["boundaries"])
        self.assertIn("HYPOTHESIS_STATE != TRUTH", policy["boundaries"])
        self.assertIn("IMPORT != AUTHORITY", policy["boundaries"])
        self.assertIn("IMPORTED_OBJECT != LOCAL_COMMITTED_OBJECT", policy["boundaries"])
        self.assertIn("existing content-addressed WorldStore", policy["storage_foundation"])

    def test_public_alias_promotes_alpha8_overlay_and_operations(self) -> None:
        self.assertIs(NexusAPI, PersistentWorldNexusAPI)
        api = NexusAPI()
        health = api.handle({"operation": "system.health"})
        self.assertEqual(health["status"], "ok")
        self.assertEqual(health["persistent_world"]["policy"]["schema"], PERSISTENT_WORLD_POLICY_ID)
        operations = api.handle({"operation": "system.operations"})
        for operation in (
            "world.relation.create",
            "world.hypothesis.create",
            "world.experiment.create",
            "world.minority.search",
            "world.mode.history",
            "world.export",
            "world.import",
        ):
            self.assertIn(operation, operations["operations"])

    def test_reserved_alpha8_objects_cannot_be_forged_by_world_create(self) -> None:
        api = NexusAPI()
        for object_type in (
            WORLD_RELATION_OBJECT_TYPE,
            WORLD_HYPOTHESIS_OBJECT_TYPE,
            WORLD_EXPERIMENT_OBJECT_TYPE,
            WORLD_IMPORTED_OBJECT_TYPE,
            WORLD_IMPORT_RECEIPT_OBJECT_TYPE,
        ):
            response = api.handle(
                {
                    "operation": "world.create",
                    "object_type": object_type,
                    "payload": {"forged": True},
                }
            )
            self.assertEqual(response["status"], "error")
            self.assertEqual(response["error"]["code"], "invalid_request")


class PersistentWorldLineageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = WorldStore()
        self.service = PersistentWorldService(self.world)
        self.a = self.world.create_object("note", {"content": "alpha"}, {"actor": "test"})
        self.b = self.world.create_object("note", {"content": "beta"}, {"actor": "test"})
        self.c = self.world.create_object("measurement", {"value": 17}, {"actor": "test"})

    def test_relation_is_explicit_searchable_and_non_authoritative(self) -> None:
        relation = self.service.create_relation(
            relation_type="supports",
            source_ref=self.a.object_id,
            target_ref=self.b.object_id,
            metadata={"scope": "fixture"},
        )
        self.assertEqual(relation.object_type, WORLD_RELATION_OBJECT_TYPE)
        self.assertEqual(relation.payload["authority_effect"], "none")
        result = self.service.search_relations(
            query="fixture",
            relation_type="supports",
            source_ref=self.a.object_id,
        )
        self.assertEqual(result["returned"], 1)
        self.assertEqual(result["matches"][0]["object_id"], relation.object_id)
        self.assertFalse(result["search_is_evidence"])

    def test_relation_rejects_explicit_non_object_metadata(self) -> None:
        for malformed in ([], False, 0, ""):
            with self.subTest(metadata=malformed):
                with self.assertRaises(PersistentWorldError) as raised:
                    self.service.create_relation(
                        relation_type="supports",
                        source_ref=self.a.object_id,
                        target_ref=self.b.object_id,
                        metadata=malformed,  # type: ignore[arg-type]
                    )
                self.assertEqual(raised.exception.code, "world_relation_invalid")

    def test_hypothesis_lineage_is_immutable_and_retired_is_terminal(self) -> None:
        proposed = self.service.create_hypothesis(
            statement="A bounded fixture may support this hypothesis.",
            state="PROPOSED",
            evidence_refs=[self.a.object_id],
        )
        active = self.service.create_hypothesis(
            statement="A bounded fixture may support this hypothesis.",
            state="ACTIVE",
            evidence_refs=[self.a.object_id, self.b.object_id],
            previous_hypothesis_ref=proposed.object_id,
        )
        retired = self.service.create_hypothesis(
            statement="The hypothesis is retired from the active workflow.",
            state="RETIRED",
            evidence_refs=[self.a.object_id, self.b.object_id],
            previous_hypothesis_ref=active.object_id,
        )
        self.assertEqual(active.payload["previous_hypothesis_ref"], proposed.object_id)
        self.assertEqual(retired.payload["state_semantics"], "workflow_label_not_truth_classification")
        with self.assertRaises(PersistentWorldError):
            self.service.create_hypothesis(
                statement="Attempted resurrection.",
                state="ACTIVE",
                evidence_refs=[],
                previous_hypothesis_ref=retired.object_id,
            )

    def test_legacy_hypothesis_object_cannot_be_reinterpreted_as_alpha8_predecessor(self) -> None:
        legacy = self.world.create_object(
            WORLD_HYPOTHESIS_OBJECT_TYPE,
            {"state": "ACTIVE", "statement": "legacy object with colliding type name"},
            {"actor": "legacy"},
        )
        with self.assertRaises(PersistentWorldError) as raised:
            self.service.create_hypothesis(
                statement="new alpha8 hypothesis",
                state="CHALLENGED",
                evidence_refs=[],
                previous_hypothesis_ref=legacy.object_id,
            )
        self.assertEqual(raised.exception.code, "world_persistence_invalid_lineage")

    def test_experiment_lineage_requires_plan_before_observation_and_result_refs(self) -> None:
        hypothesis = self.service.create_hypothesis(
            statement="17 is observed in the fixture.",
            state="PROPOSED",
            evidence_refs=[self.c.object_id],
        )
        plan = self.service.create_experiment(
            title="Fixture check",
            stage="PLANNED",
            method="Inspect the bounded measurement object.",
            hypothesis_refs=[hypothesis.object_id],
            input_refs=[self.a.object_id],
            result_refs=[],
        )
        observed = self.service.create_experiment(
            title="Fixture check",
            stage="OBSERVED",
            method="Inspect the bounded measurement object.",
            hypothesis_refs=[hypothesis.object_id],
            input_refs=[self.a.object_id],
            result_refs=[self.c.object_id],
            previous_experiment_ref=plan.object_id,
        )
        self.assertEqual(observed.object_type, WORLD_EXPERIMENT_OBJECT_TYPE)
        self.assertEqual(observed.payload["claim_boundary"], "recorded_world_lineage_not_empirical_truth")
        with self.assertRaises(PersistentWorldError):
            self.service.create_experiment(
                title="Bad initial observation",
                stage="OBSERVED",
                method="No plan.",
                hypothesis_refs=[],
                input_refs=[],
                result_refs=[self.c.object_id],
            )

    def test_legacy_experiment_object_cannot_be_reinterpreted_as_alpha8_predecessor(self) -> None:
        legacy = self.world.create_object(
            WORLD_EXPERIMENT_OBJECT_TYPE,
            {"stage": "PLANNED", "title": "legacy collision", "method": "legacy"},
            {"actor": "legacy"},
        )
        with self.assertRaises(PersistentWorldError) as raised:
            self.service.create_experiment(
                title="new alpha8 experiment",
                stage="PLANNED",
                method="new method",
                hypothesis_refs=[],
                input_refs=[],
                result_refs=[],
                previous_experiment_ref=legacy.object_id,
            )
        self.assertEqual(raised.exception.code, "world_persistence_invalid_lineage")


class PersistentWorldDerivedViewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = WorldStore()
        self.service = PersistentWorldService(self.world)

    def test_minority_report_search_reads_committed_sessions_without_promoting_them(self) -> None:
        question = self.world.create_object("question", {"text": "fixture?"}, {"actor": "test"})
        session = self.world.create_object(
            "council_session",
            {
                "session_id": "council_session:" + "1" * 64,
                "question_ref": question.object_id,
                "world_mode": {"mode_id": "analytical"},
                "geometry_region": {"region_id": "observatory"},
                "result": {
                    "evidence_state": "UNTESTED",
                    "minority_reports": [
                        {
                            "member_id": "skeptic",
                            "choice": "TEST_FURTHER",
                            "rationale": "The fixture needs independent replication.",
                        }
                    ],
                },
            },
            {"actor": "nexus"},
        )
        result = self.service.search_minority_reports(query="replication")
        self.assertEqual(result["returned"], 1)
        self.assertEqual(result["matches"][0]["session_ref"], session.object_id)
        self.assertEqual(result["matches"][0]["minority_report"]["member_id"], "skeptic")
        self.assertFalse(result["search_is_evidence"])

    def test_mode_history_is_a_derived_view_not_geometry_authority(self) -> None:
        question = self.world.create_object("question", {"text": "mode fixture"}, {"actor": "test"})
        session = self.world.create_object(
            "council_session",
            {
                "session_id": "council_session:" + "2" * 64,
                "question_ref": question.object_id,
                "world_mode": {"mode_id": "historical"},
                "geometry_region": {"region_id": "archive"},
                "result": {"minority_reports": []},
            },
            {"actor": "nexus"},
        )
        history = self.service.mode_history()
        self.assertEqual(history["events"][0]["event_ref"], session.object_id)
        self.assertEqual(history["events"][0]["mode_id"], "historical")
        self.assertFalse(history["geometry_is_semantic_authority"])

    def test_plain_file_world_reports_hash_order_honestly(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            world = WorldStore(Path(temporary) / "world")
            a = world.create_object("note", {"content": "alpha"}, {"actor": "test"})
            b = world.create_object("note", {"content": "beta"}, {"actor": "test"})
            service = PersistentWorldService(world)
            service.create_relation(relation_type="related_to", source_ref=a.object_id, target_ref=b.object_id)
            service.create_relation(relation_type="supports", source_ref=b.object_id, target_ref=a.object_id)
            result = service.search_relations(limit=1)
            self.assertEqual(result["order_basis"], "lexical_object_ref")
            self.assertEqual(result["order"], "lexical_descending_object_ref")
            self.assertNotEqual(result["order"], "newest_first")


class PersistentWorldExportImportTests(unittest.TestCase):
    @staticmethod
    def _bundle_for_objects(objects: list[dict]) -> dict:
        body = {
            "schema": PERSISTENT_WORLD_EXPORT_SCHEMA,
            "world_policy": PERSISTENT_WORLD_POLICY_ID,
            "order_basis": "memory_insertion_order",
            "source_head_ref": None,
            "object_count": len(objects),
            "objects": objects,
            "authority_effect": "none",
        }
        return {**body, "bundle_ref": sha256_ref("world-export", body)}

    def test_export_import_quarantines_foreign_objects_and_adds_receipt(self) -> None:
        source = WorldStore()
        service = PersistentWorldService(source)
        a = source.create_object("note", {"content": "alpha"}, {"actor": "test"})
        b = source.create_object("note", {"content": "beta"}, {"actor": "test"})
        relation = service.create_relation(
            relation_type="related_to",
            source_ref=a.object_id,
            target_ref=b.object_id,
        )
        bundle = service.export_bundle()
        self.assertEqual(bundle["schema"], PERSISTENT_WORLD_EXPORT_SCHEMA)
        verified = validate_world_export_bundle(bundle)
        self.assertEqual(verified["object_count"], 3)

        target = WorldStore()
        imported = PersistentWorldService(target).import_bundle(bundle)
        self.assertFalse(imported["foreign_objects_materialized_as_live_world_objects"])
        self.assertEqual(
            {item["source_ref"] for item in imported["quarantined_objects"]},
            {a.object_id, b.object_id, relation.object_id},
        )
        with self.assertRaises(KeyError):
            target.inspect(a.object_id)
        for item in imported["quarantined_objects"]:
            wrapper = target.inspect(item["wrapper_ref"])
            self.assertEqual(wrapper.object_type, WORLD_IMPORTED_OBJECT_TYPE)
            self.assertEqual(wrapper.payload["source_object_ref"], item["source_ref"])
            self.assertFalse(wrapper.payload["materialized_as_live_world_object"])
        receipt = target.inspect(imported["import_receipt_ref"])
        self.assertEqual(receipt.object_type, WORLD_IMPORT_RECEIPT_OBJECT_TYPE)
        self.assertTrue(receipt.payload["source_objects_preserved"])
        self.assertFalse(receipt.payload["foreign_objects_materialized_as_live_world_objects"])
        self.assertEqual(receipt.payload["authority_effect"], "none")

    def test_foreign_council_session_cannot_enter_local_minority_history(self) -> None:
        source = WorldStore()
        session = source.create_object(
            "council_session",
            {
                "session_id": "council_session:" + "9" * 64,
                "question_ref": "object:" + "1" * 64,
                "world_mode": {"mode_id": "analytical"},
                "geometry_region": {"region_id": "observatory"},
                "result": {
                    "evidence_state": "KNOWN",
                    "minority_reports": [
                        {
                            "member_id": "foreign",
                            "choice": "ACCEPT",
                            "rationale": "This must not become local committed Council history.",
                        }
                    ],
                },
            },
            {"actor": "nexus"},
        )
        bundle = PersistentWorldService(source).export_bundle()
        target = WorldStore()
        imported = PersistentWorldService(target).import_bundle(bundle)
        wrapper = target.inspect(imported["quarantined_objects"][0]["wrapper_ref"])
        self.assertEqual(wrapper.payload["source_object_ref"], session.object_id)
        self.assertEqual(wrapper.object_type, WORLD_IMPORTED_OBJECT_TYPE)
        self.assertEqual(PersistentWorldService(target).search_minority_reports()["returned"], 0)

    def test_reimport_reuses_existing_quarantine_wrapper(self) -> None:
        source = WorldStore()
        obj = source.create_object("note", {"content": "alpha"}, {"actor": "test"})
        bundle = PersistentWorldService(source).export_bundle()
        target = WorldStore()
        service = PersistentWorldService(target)
        first = service.import_bundle(bundle)
        second = service.import_bundle(bundle)
        self.assertEqual(
            first["quarantined_objects"][0]["wrapper_ref"],
            second["quarantined_objects"][0]["wrapper_ref"],
        )
        self.assertEqual(first["quarantined_objects"][0]["source_ref"], obj.object_id)

    def test_tampered_bundle_is_rejected_before_import(self) -> None:
        source = WorldStore()
        source.create_object("note", {"content": "alpha"}, {"actor": "test"})
        bundle = PersistentWorldService(source).export_bundle()
        tampered = copy.deepcopy(bundle)
        tampered["objects"][0]["payload"]["content"] = "tampered"
        target = WorldStore()
        with self.assertRaises(PersistentWorldError):
            PersistentWorldService(target).import_bundle(tampered)
        self.assertEqual(len(target._objects), 0)

    def test_import_rejects_credential_shaped_source_material_even_when_hash_valid(self) -> None:
        raw = {
            "object_type": "note",
            "payload": {"content": "sk-" + "A" * 48},
            "provenance": {"actor": "fixture"},
        }
        object_id = sha256_ref("object", raw)
        bundle = self._bundle_for_objects([{"object_id": object_id, **raw}])
        validate_world_export_bundle(bundle)
        target = WorldStore()
        with self.assertRaises(PersistentWorldError) as raised:
            PersistentWorldService(target).import_bundle(bundle)
        self.assertEqual(raised.exception.code, "world_import_secret_rejected")

    def test_import_rejects_credential_shaped_object_type_before_mutation(self) -> None:
        raw = {
            "object_type": "sk-" + "B" * 48,
            "payload": {"content": "safe"},
            "provenance": {"actor": "fixture"},
        }
        object_id = sha256_ref("object", raw)
        bundle = self._bundle_for_objects([{"object_id": object_id, **raw}])
        target = WorldStore()
        with self.assertRaises(PersistentWorldError) as raised:
            PersistentWorldService(target).import_bundle(bundle)
        self.assertEqual(raised.exception.code, "world_import_secret_rejected")
        self.assertEqual(len(target._objects), 0)

    def test_conflicting_existing_wrapper_is_preflighted_before_any_new_wrapper(self) -> None:
        source = WorldStore()
        first = source.create_object("note", {"content": "first"}, {"actor": "source"})
        second = source.create_object("note", {"content": "second"}, {"actor": "source"})
        bundle = PersistentWorldService(source).export_bundle()

        target = WorldStore()
        target.create_object(
            WORLD_IMPORTED_OBJECT_TYPE,
            {
                "schema": PERSISTENT_WORLD_POLICY_ID,
                "source_object_ref": second.object_id,
                "source_object": {**second.as_dict(), "payload": {"content": "conflicting"}},
                "materialized_as_live_world_object": False,
                "authority_effect": "none",
            },
            {"actor": "legacy"},
        )
        before = set(target._objects)
        with self.assertRaises(PersistentWorldError) as raised:
            PersistentWorldService(target).import_bundle(bundle)
        self.assertEqual(raised.exception.code, "world_export_invalid")
        self.assertEqual(set(target._objects), before)
        with self.assertRaises(KeyError):
            target.inspect(first.object_id)

    def test_exchange_bundle_has_canonical_byte_ceiling(self) -> None:
        source = WorldStore()
        source.create_object(
            "note",
            {"content": "x" * MAX_EXCHANGE_BYTES},
            {"actor": "test"},
        )
        with self.assertRaises(PersistentWorldError) as raised:
            PersistentWorldService(source).export_bundle()
        self.assertEqual(raised.exception.code, "world_persistence_limit")


if __name__ == "__main__":
    unittest.main()
