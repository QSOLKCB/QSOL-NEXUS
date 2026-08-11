from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path.relative_to(ROOT)}: expected exactly one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# README: remove the stale alpha/beta-era release criterion and align it with the
# machine-readable release-candidate contract.
replace_once(
    ROOT / "README.md",
    """The project still intends to complete the remaining architecture criteria in the roadmap before removing the alpha/beta qualification, including the broader instrument layer, persistent-world/migration hardening, formal release alignment, and beta-level security/adaptor hardening. The explicit alpha11 shared-world demonstration itself is already merged in PR #31.\n\nUntil then:\n\n> **Build the smallest correct path. Keep the world durable. Keep the models equal. Keep claims typed.**""",
    """The implementation criteria listed in the roadmap are complete on the intended 2.0 feature surface through merged PR #50. The remaining stable-release gate is narrower and explicit: the exact merged PR #51 commit must pass the complete final release-candidate matrix with no unresolved substantive release-blocking review finding, and `v2.0.0` must then be created from that same commit.\n\nPR #52 Lean verification and PR #53 reproducibility/Zenodo publication are intentionally post-stable work; they do not retroactively create the 2.0 release.\n\nUntil the stable tag exists:\n\n> **Build the smallest correct path. Keep the world durable. Keep the models equal. Keep claims typed.**""",
)

# SECURITY: reconcile the canonical outbound-network policy with the admitted
# fixed-destination third-party adapters that are already implemented.
replace_once(
    ROOT / "SECURITY.md",
    """```text\nworld kernel             outbound: none\nreceipt service          outbound: none\nSecret Scrubber          outbound: none\nJSONL mock control API   outbound: none\nOllama actor             loopback by default\nauth browser/device flow explicit provider descriptor only\nauth external helper     explicit operator configuration only\nxAI adapter              fixed api.x.ai HTTPS, explicit profile only\nother remote providers   not implemented\n```\n\nThe JSONL control transport itself remains stdio. `auth.list` is local-only. `auth.test xai`, `models.list` for xAI, and an explicitly configured xAI actor can perform fixed-destination network I/O. A custom broker can also perform registered auth operations against descriptor-allowlisted endpoints. `system.health` reports that category even when the stock xAI descriptor is the only configured remote provider. Enrollment remains a direct `nexus auth add` action rather than a raw-secret JSONL operation.""",
    """```text\nworld kernel             outbound: none\nreceipt service          outbound: none\nSecret Scrubber          outbound: none\nJSONL control transport  outbound: none\nOllama actor             loopback by default\nLM Studio actor          loopback by default\nAnythingLLM actor        loopback by default\nOpenAI-compatible local  loopback by default\nauth browser/setup flow  explicit provider descriptor only\nauth external helper     explicit operator configuration only\nxAI adapter              fixed api.x.ai HTTPS, explicit profile only\nOpenAI adapter           fixed api.openai.com HTTPS, explicit profile only\nAnthropic adapter        fixed api.anthropic.com HTTPS, explicit profile only\nGemini adapter           fixed generativelanguage.googleapis.com HTTPS, explicit profile only\nGroq adapter             fixed api.groq.com HTTPS, explicit profile only\nTogether adapter         fixed api.together.ai HTTPS, explicit profile only\n```\n\nThe JSONL control transport itself remains local stdio. `auth.list` is local-only. Provider connection tests, model discovery, and explicitly configured remote actors may perform fixed-destination HTTPS only through their admitted provider descriptors. Redirects and caller-supplied endpoint overrides are rejected by the stock remote transports. A custom broker may perform registered auth operations only against descriptor-allowlisted endpoints. Enrollment remains a direct `nexus auth add` action rather than a raw-secret JSONL operation.""",
)

# ROADMAP: keep the detailed post-stable sections consistent with the already
# tested #52/#53 split.
replace_once(
    ROOT / "ROADMAP.md",
    """## PR #52 — Formalization & Zenodo Publication\n\nPost-release only:\n\n- freeze the released source/version identity;\n- formalize architecture/protocol description;\n- prepare archival metadata;\n- bind exact release/tag/commit/checksums;\n- publish the formal NEXUS 2.0 record on Zenodo;\n- record the DOI back into project documentation later if required.\n\nZenodo formalization documents the released system. It must not silently redefine the already-released runtime or constitutional contract.\n""",
    """## PR #52 — Lean 4 Formal Verification\n\nPost-stable verification only:\n\n- freeze the exact NEXUS 2.0 stable tag and commit as the runtime correspondence target;\n- rebase/update the parked Lean project against that exact stable runtime;\n- ship runnable Lean source with pinned toolchain/Lake metadata;\n- formalize selected constitutional and protocol invariants;\n- maintain theorem/lemma inventory, assumptions/non-claims, axiom audit and formal-gap ranking;\n- map each advertised theorem to the tested Python/Rust runtime surface;\n- require the complete selected theorem surface to pass `lake build` with no `sorry`, `admit`, or user-declared proof-substitute axioms.\n\nPR #52 proves the selected formal obligations. It does not publish or silently redefine the already-released runtime.\n\n## PR #53 — Formalization + Reproducibility + Zenodo Publication\n\nArchival/publication phase only:\n\n- package the exact NEXUS 2.0 stable source/tag/commit identity;\n- include the reviewed runnable Lean source from the final PR #52 head without rewriting proofs;\n- bind exact release, formalization, toolchain and checksum identities;\n- include theorem inventory, assumptions/non-claims, axiom audit, formal-gap ranking and runtime correspondence;\n- include final release-hardening/test evidence and reproduction instructions;\n- generate a SHA-256 manifest for the publication payload;\n- publish the reproducibility/formalization record on Zenodo and record the final DOI.\n\nZenodo formalization documents the released system and reviewed proof package. It must not silently redefine either artifact.\n""",
)

# Hardening matrix: turn the second rehearsal into the actual integrated stable
# upgrade/recovery path and pin the dedicated regression file into coverage.
matrix_path = ROOT / "release" / "hardening_matrix.json"
matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
release_gate = next(gate for gate in matrix["gates"] if gate["id"] == "release_composition")
patterns = release_gate["patterns"]
if "test_release_upgrade_rehearsal.py" not in patterns:
    patterns.append("test_release_upgrade_rehearsal.py")
rehearsals = matrix["rehearsals"]
if len(rehearsals) != 2 or rehearsals[1].get("id") != "representative_world_ark_round_trip":
    raise SystemExit("hardening_matrix.json: unexpected existing representative rehearsal")
rehearsals[1] = {
    "id": "representative_pre_beta_upgrade_ark_round_trip",
    "required": True,
    "sequence": [
        "create a representative pre-beta plain WorldStore with cognitive/evidence history",
        "open it through current Continuity/NEXUS without changing legacy object refs",
        "exercise current progression, culture and BBS Wall state on the upgraded world",
        "create and verify a World Ark",
        "restore into a new empty target",
        "remove mutable progression cache and reopen current NEXUS",
        "reconstruct the same legacy refs, progression portfolio, culture artifact and Wall history from immutable restored history",
    ],
}
matrix_path.write_text(json.dumps(matrix, indent=2) + "\n", encoding="utf-8")

# Hardening runner: pin the exact new rehearsal contract and execute it as its
# own required report check, in addition to the full Python regression suite.
runner = ROOT / "tools" / "nexus_release_hardening.py"
replace_once(
    runner,
    """    \"representative_world_ark_round_trip\": (\n        \"create persistent world state including AI progression/culture history\",\n        \"create and verify a World Ark\",\n        \"restore into a new empty target\",\n        \"reopen NEXUS without mutable progression cache\",\n        \"reconstruct the same portfolio from immutable restored history\",\n    ),""",
    """    \"representative_pre_beta_upgrade_ark_round_trip\": (\n        \"create a representative pre-beta plain WorldStore with cognitive/evidence history\",\n        \"open it through current Continuity/NEXUS without changing legacy object refs\",\n        \"exercise current progression, culture and BBS Wall state on the upgraded world\",\n        \"create and verify a World Ark\",\n        \"restore into a new empty target\",\n        \"remove mutable progression cache and reopen current NEXUS\",\n        \"reconstruct the same legacy refs, progression portfolio, culture artifact and Wall history from immutable restored history\",\n    ),""",
)
replace_once(
    runner,
    """        \"fresh-archive-operator-rehearsal\",\n        \"candidate-tree-unchanged\",""",
    """        \"fresh-archive-operator-rehearsal\",\n        \"representative-pre-beta-upgrade-ark-rehearsal\",\n        \"candidate-tree-unchanged\",""",
)
replace_once(
    runner,
    """    release_test = tests_root / \"test_release_hardening.py\"\n    grok_test = tests_root / \"test_release_hardening_grok_audit.py\"\n    if release_test not in matched or grok_test not in matched:\n        raise ValueError(\"release composition tests are not covered by the hardening matrix\")""",
    """    release_test = tests_root / \"test_release_hardening.py\"\n    grok_test = tests_root / \"test_release_hardening_grok_audit.py\"\n    upgrade_test = tests_root / \"test_release_upgrade_rehearsal.py\"\n    if release_test not in matched or grok_test not in matched or upgrade_test not in matched:\n        raise ValueError(\"release composition and upgrade/recovery tests are not covered by the hardening matrix\")""",
)
replace_once(
    runner,
    """def _adversarial_probes(iterations: int) -> CheckResult:\n""",
    """def _pre_beta_upgrade_ark_rehearsal() -> CheckResult:\n    return _run(\n        \"representative-pre-beta-upgrade-ark-rehearsal\",\n        [\n            sys.executable,\n            \"-m\",\n            \"unittest\",\n            \"tests.test_release_upgrade_rehearsal.PreBetaUpgradeArkRehearsalTests.test_representative_pre_beta_world_upgrades_and_ark_round_trips\",\n            \"-v\",\n        ],\n        env={\"PYTHONPATH\": str(ROOT / \"src\")},\n    )\n\n\ndef _adversarial_probes(iterations: int) -> CheckResult:\n""",
)
replace_once(
    runner,
    """        else:\n            checks.append(_operator_rehearsal())\n        checks.append(\n            _worktree_audit(""",
    """        else:\n            checks.append(_operator_rehearsal())\n        checks.append(_pre_beta_upgrade_ark_rehearsal())\n        checks.append(\n            _worktree_audit(""",
)

# Release-candidate tests: pin the corrections so these contradictions cannot
# silently return in a future metadata-only edit.
release_tests = ROOT / "tests" / "test_release_candidate.py"
replace_once(
    release_tests,
    """        self.assertIn(\"LEAN 4 FORMAL VERIFICATION - PR #52\", roadmap)\n        self.assertIn(\"ZENODO - PR #53\", roadmap)""",
    """        self.assertIn(\"## PR #52 — Lean 4 Formal Verification\", roadmap)\n        self.assertIn(\"## PR #53 — Formalization + Reproducibility + Zenodo Publication\", roadmap)\n        self.assertIn(\"LEAN 4 FORMAL VERIFICATION - PR #52\", roadmap)\n        self.assertIn(\"ZENODO - PR #53\", roadmap)""",
)
replace_once(
    release_tests,
    """        self.assertNotIn(\"xAI is the first admitted remote adapter\", security)\n        self.assertNotIn(\"remote providers other than xAI\", threat)""",
    """        self.assertNotIn(\"xAI is the first admitted remote adapter\", security)\n        self.assertNotIn(\"other remote providers   not implemented\", security)\n        self.assertIn(\"api.openai.com\", security)\n        self.assertIn(\"api.anthropic.com\", security)\n        self.assertIn(\"generativelanguage.googleapis.com\", security)\n        self.assertIn(\"api.groq.com\", security)\n        self.assertIn(\"api.together.ai\", security)\n        self.assertNotIn(\"remote providers other than xAI\", threat)""",
)
replace_once(
    release_tests,
    """        self.assertIn(\"test_release_candidate.py\", release_gate[\"patterns\"])\n        self.assertEqual(set(matrix[\"external_audit_closure\"][\"finding_ids\"]), {f\"R{i}\" for i in range(1, 13)})""",
    """        self.assertIn(\"test_release_candidate.py\", release_gate[\"patterns\"])\n        self.assertIn(\"test_release_upgrade_rehearsal.py\", release_gate[\"patterns\"])\n        rehearsal_ids = {item[\"id\"] for item in matrix[\"rehearsals\"]}\n        self.assertIn(\"representative_pre_beta_upgrade_ark_round_trip\", rehearsal_ids)\n        self.assertEqual(set(matrix[\"external_audit_closure\"][\"finding_ids\"]), {f\"R{i}\" for i in range(1, 13)})""",
)
replace_once(
    release_tests,
    """        self.assertIn(\"status:          release candidate\", readme)\n        self.assertEqual(ai[\"bbs_wall\"][\"evidence_effect\"], \"none\")""",
    """        self.assertIn(\"status:          release candidate\", readme)\n        self.assertNotIn(\"broader instrument layer, persistent-world/migration hardening\", readme)\n        self.assertIn(\"exact merged PR #51 commit must pass the complete final release-candidate matrix\", readme)\n        self.assertEqual(ai[\"bbs_wall\"][\"evidence_effect\"], \"none\")""",
)

# New integrated rehearsal: starts with a genuine plain/pre-Continuity
# WorldStore, then upgrades through the current runtime and proves that both
# legacy and current state survive a cold Ark restore without mutable caches.
upgrade_test = ROOT / "tests" / "test_release_upgrade_rehearsal.py"
if upgrade_test.exists():
    raise SystemExit("tests/test_release_upgrade_rehearsal.py already exists")
upgrade_test.write_text(
    '''from __future__ import annotations\n\nfrom pathlib import Path\nimport tempfile\nimport unittest\n\nfrom nexus_runtime import NexusAPI\nfrom nexus_runtime.world import WorldStore\n\n\nclass PreBetaUpgradeArkRehearsalTests(unittest.TestCase):\n    @staticmethod\n    def _api(base: Path, world_name: str) -> NexusAPI:\n        return NexusAPI(\n            base / world_name,\n            auth_root=base / f"{world_name}-auth",\n            trap_root=base / f"{world_name}-trap",\n            stenographer_root=base / f"{world_name}-stenographer",\n            guardian_root=base / f"{world_name}-guardian",\n        )\n\n    @staticmethod\n    def _alpha() -> dict[str, str]:\n        return {\n            "member_id": "Alpha",\n            "model_id": "mock-alpha",\n            "adapter_id": "mock",\n            "profile": "balanced",\n        }\n\n    def test_representative_pre_beta_world_upgrades_and_ark_round_trips(self) -> None:\n        with tempfile.TemporaryDirectory() as temporary:\n            base = Path(temporary)\n            legacy_root = base / "legacy-world"\n\n            # Representative pre-beta state: plain WorldStore cognitive/evidence\n            # objects with no Continuity metadata yet. These object identities are\n            # the compatibility boundary the upgrade must preserve.\n            legacy = WorldStore(legacy_root)\n            question = legacy.create_object(\n                "question",\n                {"text": "Does the old world survive the 2.0 upgrade?"},\n                {"actor": "legacy_operator"},\n            )\n            evidence = legacy.create_object(\n                "document_evidence",\n                {"filename": "legacy.txt", "content": "pre-beta evidence payload"},\n                {"actor": "legacy_operator"},\n            )\n            session = legacy.create_object(\n                "council_session",\n                {\n                    "question_ref": question.object_id,\n                    "evidence_refs": [evidence.object_id],\n                    "legacy_marker": "pre_beta",\n                },\n                {"actor": "legacy_council"},\n            )\n            legacy_objects = {\n                item.object_id: item.as_dict()\n                for item in (question, evidence, session)\n            }\n\n            # Opening the same directory through the current API must baseline\n            # the legacy world without changing any content-addressed object ID.\n            api = self._api(base, "legacy-world")\n            continuity = api.world.status()\n            self.assertEqual(continuity["generation"], 0)\n            self.assertEqual(continuity["recognized_object_count"], len(legacy_objects))\n            for ref, expected in legacy_objects.items():\n                self.assertEqual(api.world.inspect(ref).as_dict(), expected)\n\n            # Exercise current post-upgrade state from multiple non-authoritative\n            # surfaces before taking the cold Ark snapshot.\n            progression = api.handle(\n                {\n                    "operation": "progression.act",\n                    "member": self._alpha(),\n                    "activity_id": "research",\n                    "prompt": "Record one post-upgrade research contribution.",\n                    "source_refs": [evidence.object_id],\n                }\n            )\n            self.assertEqual(progression["status"], "ok")\n\n            performance = api.handle(\n                {\n                    "operation": "culture.open_mic.perform",\n                    "member": self._alpha(),\n                    "kind": "rant",\n                    "prompt": "Complain briefly about migration paperwork.",\n                    "mode": "anarchy",\n                }\n            )\n            self.assertEqual(performance["status"], "ok")\n            performance_ref = performance["performance"]["object_id"]\n\n            wall = api.handle(\n                {\n                    "operation": "wall.post",\n                    "author_id": "ReleaseProbe",\n                    "text": "The upgraded world is still here.",\n                }\n            )\n            self.assertEqual(wall["status"], "ok")\n            wall_ref = wall["post"]["object_id"]\n\n            portfolio_before = api.handle(\n                {\n                    "operation": "progression.portfolio",\n                    "actor_id": "Alpha",\n                    "model_id": "mock-alpha",\n                }\n            )\n            self.assertEqual(portfolio_before["status"], "ok")\n            self.assertEqual(portfolio_before["counts"]["research"], 1)\n            self.assertEqual(portfolio_before["counts"]["perform_rant"], 1)\n\n            ark = base / "NEXUS-2.0-PRE-BETA-UPGRADE-ARK"\n            created = api.world.create_ark(ark, compute_epoch=0)\n            self.assertTrue(created["verified"])\n            verified = api.world.verify_ark(ark)\n            self.assertEqual(verified["status"], "verified")\n\n            restored_root = base / "restored-world"\n            restored = api.world.restore_ark(ark, restored_root)\n            self.assertEqual(restored["status"], "restored")\n\n            # Mutable progression caches are explicitly not allowed to carry the\n            # result. Reopen against immutable restored history only.\n            heads = restored_root / "progression" / "heads.json"\n            if heads.exists():\n                heads.unlink()\n\n            reopened = self._api(base, "restored-world")\n            for ref, expected in legacy_objects.items():\n                self.assertEqual(reopened.world.inspect(ref).as_dict(), expected)\n            self.assertEqual(reopened.world.inspect(performance_ref).object_id, performance_ref)\n            self.assertEqual(reopened.world.inspect(wall_ref).object_id, wall_ref)\n\n            portfolio_after = reopened.handle(\n                {\n                    "operation": "progression.portfolio",\n                    "actor_id": "Alpha",\n                    "model_id": "mock-alpha",\n                }\n            )\n            self.assertEqual(portfolio_after["status"], "ok")\n            for field in ("state_ref", "total_activities", "counts", "milestones"):\n                self.assertEqual(portfolio_after[field], portfolio_before[field])\n\n            listed = reopened.handle({"operation": "wall.list", "limit": 20})\n            self.assertEqual(listed["status"], "ok")\n            self.assertEqual([post["object_id"] for post in listed["posts"]], [wall_ref])\n            self.assertEqual(listed["posts"][0]["text"], "The upgraded world is still here.")\n\n\nif __name__ == "__main__":\n    unittest.main()\n''',
    encoding="utf-8",
)
