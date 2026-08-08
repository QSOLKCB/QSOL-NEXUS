from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "nexus_live_council_bench.py"
MODULE_NAME = "nexus_live_council_bench"
SPEC = importlib.util.spec_from_file_location(MODULE_NAME, MODULE_PATH)
assert SPEC and SPEC.loader
bench = importlib.util.module_from_spec(SPEC)
sys.modules[MODULE_NAME] = bench
SPEC.loader.exec_module(bench)


class LiveCouncilBenchToolTests(unittest.TestCase):
    def complete_manifest(self, *, question: str = "q", mode: str = "analytical") -> dict:
        manifest = bench.seat_template(question, mode, "grok-build-agent", "grok-build-agent")
        manifest["responses"] = {
            phase.value: f"{phase.value} response grounded in evidence."
            for phase in bench.PHASE_ORDER
        }
        manifest["guard_restatement"] = "Use evidence, provenance, reproducibility, and falsifiers only."
        manifest["ballot"] = {
            "choice": bench.Ballot.TEST_FURTHER.value,
            "rationale": "More discriminating evidence is required.",
        }
        return manifest

    def test_loopback_endpoint_accepts_dedicated_bench_port(self) -> None:
        self.assertEqual(bench._loopback_endpoint("http://127.0.0.1:11435"), ("127.0.0.1", 11435))
        self.assertEqual(bench._loopback_endpoint("http://localhost:11435"), ("localhost", 11435))

    def test_loopback_endpoint_rejects_remote_and_wildcard_hosts(self) -> None:
        for endpoint in (
            "https://example.com:11435",
            "http://192.168.1.2:11435",
            "http://0.0.0.0:11435",
            "http://example.com:11435",
        ):
            with self.subTest(endpoint=endpoint):
                with self.assertRaises(bench.BenchError):
                    bench._loopback_endpoint(endpoint)

    def test_seat_manifest_round_trip_and_actor_is_replayable(self) -> None:
        question = "Does this claim survive?"
        manifest = self.complete_manifest(question=question)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "grok-seat.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            loaded = bench.load_seat_manifest(path, question=question, mode="analytical")

        actor = bench.ManifestSeatActor(loaded)
        self.assertTrue(actor.replayable)
        self.assertEqual(actor.member.vote_weight, 1)
        self.assertEqual(actor.member.epistemic_privilege, "none")
        self.assertEqual(actor.member.adapter_id, "sealed_agent_manifest")
        self.assertEqual(len(actor.manifest_sha256), 64)

        context = bench.PhaseContext(
            session_id="session",
            phase=bench.Phase.WHITE,
            question=question,
            evidence_snapshot_ref="object:" + "0" * 64,
            completed_phases={},
        )
        self.assertEqual(actor.respond(context), manifest["responses"]["WHITE"])
        nudged = bench.PhaseContext(
            session_id="session",
            phase=bench.Phase.WHITE,
            question=question,
            evidence_snapshot_ref="object:" + "0" * 64,
            completed_phases={},
            guard_nudge="NEXUS EQUALITY GUARD",
        )
        self.assertEqual(actor.respond(nudged), manifest["guard_restatement"])
        choice, rationale = actor.ballot(context)
        self.assertEqual(choice, bench.Ballot.TEST_FURTHER)
        self.assertEqual(rationale, manifest["ballot"]["rationale"])

    def test_seat_manifest_is_bound_to_question_and_mode(self) -> None:
        manifest = self.complete_manifest(question="q", mode="pure_history")
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "grok-seat.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaises(bench.BenchError):
                bench.load_seat_manifest(path, question="different", mode="pure_history")
            with self.assertRaises(bench.BenchError):
                bench.load_seat_manifest(path, question="q", mode="analytical")

    def test_seat_manifest_rejects_blank_phase_and_ballot(self) -> None:
        manifest = self.complete_manifest()
        manifest["responses"]["GREEN"] = " "
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "grok-seat.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaises(bench.BenchError):
                bench.load_seat_manifest(path, question="q", mode="analytical")

        manifest = self.complete_manifest()
        manifest["ballot"]["rationale"] = ""
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "grok-seat.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaises(bench.BenchError):
                bench.load_seat_manifest(path, question="q", mode="analytical")

    def test_session_validation_requires_equal_three_member_council(self) -> None:
        session = {
            "payload": {
                "roster": [
                    {"vote_weight": 1, "epistemic_privilege": "none"},
                    {"vote_weight": 1, "epistemic_privilege": "none"},
                    {"vote_weight": 1, "epistemic_privilege": "none"},
                ],
                "phase_submissions": {
                    phase.value: [{}, {}, {}]
                    for phase in bench.PHASE_ORDER
                },
                "revealed_ballots": [{}, {}, {}],
                "ballot_commitments": [{}, {}, {}],
                "guard_events": [{"member_id": "local-alpha"}],
            }
        }
        self.assertEqual(bench._validate_session(session, require_guard_event=True), [])
        session["payload"]["roster"][0]["vote_weight"] = 2
        failures = bench._validate_session(session, require_guard_event=True)
        self.assertTrue(any("vote weight" in failure for failure in failures))


if __name__ == "__main__":
    unittest.main()
