from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    if old not in text:
        raise SystemExit(f"anchor not found in {path}: {old[:100]!r}")
    p.write_text(text.replace(old, new, 1))


telemetry_py = r'''from __future__ import annotations

from collections import Counter
from hashlib import sha256
from math import log2
import re
import unicodedata
from typing import Mapping, Sequence


TELEMETRY_SCHEMA_VERSION = "nexus-council-telemetry/1"
PHASE_NAMES = ("WHITE", "RED", "BLACK", "YELLOW", "GREEN", "BLUE")
_FLOAT_DIGITS = 12
_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def _round(value: float) -> float:
    return round(value, _FLOAT_DIGITS)


def shannon_entropy_bits_from_counts(counts: Mapping[str, int]) -> float:
    """Shannon entropy over an explicit categorical count distribution."""
    total = sum(count for count in counts.values() if count > 0)
    if total <= 0:
        return 0.0
    entropy = 0.0
    for count in counts.values():
        if count <= 0:
            continue
        probability = count / total
        entropy -= probability * log2(probability)
    return _round(entropy)


def normalize_exact_response(text: str) -> str:
    """Deterministic normalization for exact-response categories.

    This deliberately does not attempt semantic equivalence. It normalizes
    Unicode compatibility forms, case, and whitespace only.
    """
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(normalized.split())


def response_fingerprint(text: str) -> str:
    normalized = normalize_exact_response(text)
    return "sha256:" + sha256(normalized.encode("utf-8")).hexdigest()


def _token_set(text: str) -> set[str]:
    normalized = normalize_exact_response(text)
    return {token for token in _TOKEN_RE.findall(normalized) if token}


def mean_pairwise_lexical_jaccard_distance(texts: Sequence[str]) -> float:
    """Mean pairwise token-set Jaccard distance in [0, 1]."""
    if len(texts) < 2:
        return 0.0
    token_sets = [_token_set(text) for text in texts]
    total = 0.0
    pairs = 0
    for left_index in range(len(token_sets)):
        for right_index in range(left_index + 1, len(token_sets)):
            left = token_sets[left_index]
            right = token_sets[right_index]
            union = left | right
            distance = 0.0 if not union else 1.0 - (len(left & right) / len(union))
            total += distance
            pairs += 1
    return _round(total / pairs) if pairs else 0.0


def _phase_metric(entries: Sequence[Mapping[str, object]]) -> dict[str, object]:
    texts: list[str] = []
    for entry in entries:
        content = entry.get("content")
        if isinstance(content, str):
            texts.append(content)
    fingerprints = [response_fingerprint(text) for text in texts]
    counts = Counter(fingerprints)
    return {
        "member_count": len(texts),
        "unique_exact_response_count": len(counts),
        "exact_response_entropy_bits": shannon_entropy_bits_from_counts(counts),
        "mean_pairwise_lexical_jaccard_distance": mean_pairwise_lexical_jaccard_distance(texts),
    }


def build_council_telemetry(
    phase_submissions: Mapping[str, Sequence[Mapping[str, object]]],
    revealed_ballots: Sequence[Mapping[str, object]],
    result: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Derive deterministic observational telemetry from captured Council artifacts."""
    phase_metrics: dict[str, object] = {}
    for phase in PHASE_NAMES:
        entries = phase_submissions.get(phase, ())
        phase_metrics[phase] = _phase_metric(entries)

    ballot_choices = [
        choice
        for ballot in revealed_ballots
        if isinstance((choice := ballot.get("choice")), str)
    ]
    ballot_counts = Counter(ballot_choices)
    minority_reports = []
    if result is not None:
        candidate = result.get("minority_reports")
        if isinstance(candidate, list):
            minority_reports = candidate
    ballot_total = len(ballot_choices)

    return {
        "schema_version": TELEMETRY_SCHEMA_VERSION,
        "role": "observational_only",
        "authority_effects": {
            "changes_vote_weight": False,
            "changes_consensus_threshold": False,
            "changes_evidence_state": False,
            "changes_verification_state": False,
        },
        "claim_boundaries": {
            "ballot_entropy_is_shannon_entropy": True,
            "exact_response_entropy_is_semantic_entropy": False,
            "lexical_divergence_is_truth_metric": False,
            "high_entropy_is_automatically_good": False,
            "low_entropy_is_automatically_true": False,
        },
        "phase_metrics": phase_metrics,
        "ballot_metrics": {
            "member_count": ballot_total,
            "choice_counts": dict(sorted(ballot_counts.items())),
            "unique_choice_count": len(ballot_counts),
            "shannon_entropy_bits": shannon_entropy_bits_from_counts(ballot_counts),
            "minority_report_count": len(minority_reports),
            "minority_member_fraction": _round(len(minority_reports) / ballot_total) if ballot_total else 0.0,
        },
        "implemented_metrics": [
            "per_hat_exact_response_entropy",
            "per_hat_lexical_jaccard_divergence",
            "ballot_shannon_entropy",
            "minority_report_snapshot",
        ],
        "deferred_metrics": [
            "semantic_response_entropy",
            "hypothesis_branching_multiplicity",
            "controlled_perturbation_recovery",
            "loop_repeated_motif_indicators",
            "mode_transition_cost",
            "minority_branch_persistence_across_sessions",
        ],
    }


def verify_session_telemetry(session_payload: Mapping[str, object]) -> tuple[bool, dict[str, object]]:
    phase_submissions = session_payload.get("phase_submissions")
    revealed_ballots = session_payload.get("revealed_ballots")
    result = session_payload.get("result")
    stored = session_payload.get("telemetry")
    if not isinstance(phase_submissions, dict):
        raise ValueError("Council session phase_submissions missing")
    if not isinstance(revealed_ballots, list):
        raise ValueError("Council session revealed_ballots missing")
    if not isinstance(result, dict):
        raise ValueError("Council session result missing")
    if not isinstance(stored, dict):
        raise ValueError("Council session telemetry missing")
    recomputed = build_council_telemetry(phase_submissions, revealed_ballots, result)
    return stored == recomputed, recomputed
'''
Path('src/nexus_runtime/telemetry.py').write_text(telemetry_py)

# Council integration.
replace_once(
    'src/nexus_runtime/council.py',
    'from .scrub import SecretScrubber\n',
    'from .scrub import SecretScrubber\nfrom .telemetry import build_council_telemetry\n',
)
replace_once(
    'src/nexus_runtime/council.py',
    '        result = self._tally(ballots, evidence_state)\n\n        session_payload = {\n',
    '''        result = self._tally(ballots, evidence_state)\n        revealed_ballots = [\n            {\n                "member_id": ballot.member_id,\n                "choice": ballot.choice.value,\n                "rationale": ballot.rationale,\n                "commitment": ballot.commitment,\n            }\n            for ballot in ballots\n        ]\n        telemetry = build_council_telemetry(phase_records, revealed_ballots, result)\n\n        session_payload = {\n''',
)
replace_once(
    'src/nexus_runtime/council.py',
    '''            "revealed_ballots": [\n                {\n                    "member_id": ballot.member_id,\n                    "choice": ballot.choice.value,\n                    "rationale": ballot.rationale,\n                    "commitment": ballot.commitment,\n                }\n                for ballot in ballots\n            ],\n            "result": result,\n''',
    '''            "revealed_ballots": revealed_ballots,\n            "result": result,\n            "telemetry": telemetry,\n''',
)
replace_once(
    'src/nexus_runtime/council.py',
    '                "protocol": "nexus/0.4",\n',
    '                "protocol": "nexus/0.5",\n',
)
replace_once(
    'src/nexus_runtime/council.py',
    '            "result": result,\n        }\n\n    def build_evidence_context',
    '            "result": result,\n            "telemetry": telemetry,\n        }\n\n    def build_evidence_context',
)

# API operation and version surface.
replace_once(
    'src/nexus_runtime/api.py',
    'from .scrub import ScrubEvent, SecretScrubber\n',
    'from .scrub import ScrubEvent, SecretScrubber\nfrom .telemetry import TELEMETRY_SCHEMA_VERSION, verify_session_telemetry\n',
)
replace_once('src/nexus_runtime/api.py', 'PROTOCOL_VERSION = "nexus/0.4"', 'PROTOCOL_VERSION = "nexus/0.5"')
replace_once('src/nexus_runtime/api.py', 'RUNTIME_VERSION = "2.0.0-alpha5"', 'RUNTIME_VERSION = "2.0.0-alpha6"')
replace_once(
    'src/nexus_runtime/api.py',
    '                    "geometry": self.geometry.snapshot()["geometry_id"],\n',
    '                    "geometry": self.geometry.snapshot()["geometry_id"],\n                    "telemetry": {"schema_version": TELEMETRY_SCHEMA_VERSION, "role": "observational_only"},\n',
)
replace_once(
    'src/nexus_runtime/api.py',
    '                        "receipt.verify",\n                        "actor.chat",\n',
    '                        "receipt.verify",\n                        "telemetry.verify",\n                        "actor.chat",\n',
)
replace_once(
    'src/nexus_runtime/api.py',
    '''            elif operation == "receipt.verify":\n                receipt_ref = self._require_str(request, "receipt_ref")\n                response = self._verify_receipt(receipt_ref)\n            elif operation == "actor.chat":\n''',
    '''            elif operation == "receipt.verify":\n                receipt_ref = self._require_str(request, "receipt_ref")\n                response = self._verify_receipt(receipt_ref)\n            elif operation == "telemetry.verify":\n                session_ref = self._require_str(request, "session_ref")\n                session = self.world.inspect(session_ref)\n                if session.object_type != "council_session":\n                    raise ValueError("object is not a council_session")\n                matches, recomputed = verify_session_telemetry(session.payload)\n                response = {\n                    "status": "verified" if matches else "failed",\n                    "session_ref": session_ref,\n                    "matches": matches,\n                    "schema_version": TELEMETRY_SCHEMA_VERSION,\n                    "recomputed": recomputed,\n                }\n            elif operation == "actor.chat":\n''',
)

# Versions.
replace_once('pyproject.toml', 'version = "2.0.0a5"', 'version = "2.0.0a6"')
replace_once('tui/Cargo.toml', 'version = "2.0.0-alpha5"', 'version = "2.0.0-alpha6"')
replace_once('tests/test_runtime.py', 'self.assertEqual(result["protocol"], "nexus/0.4")', 'self.assertEqual(result["protocol"], "nexus/0.5")')

# TUI display: telemetry is text-only, copy-friendly, and explicitly observational.
replace_once(
    'tui/src/main.rs',
    '''        self.append(&format!(\n            "*** Council: {label} / {disposition} | Evidence: {evidence_state}"\n        ));\n        Ok(())\n''',
    '''        self.append(&format!(\n            "*** Council: {label} / {disposition} | Evidence: {evidence_state}"\n        ));\n        if let Some(telemetry) = payload.get("telemetry").and_then(Value::as_object) {\n            self.append("--- COUNCIL TELEMETRY (OBSERVATIONAL ONLY) ---");\n            if let Some(ballot) = telemetry.get("ballot_metrics").and_then(Value::as_object) {\n                let entropy = ballot\n                    .get("shannon_entropy_bits")\n                    .and_then(Value::as_f64)\n                    .unwrap_or(0.0);\n                let unique = ballot\n                    .get("unique_choice_count")\n                    .and_then(Value::as_u64)\n                    .unwrap_or(0);\n                self.append(&format!(\n                    "*** BALLOT: H={entropy:.3} bits | unique choices={unique}"\n                ));\n            }\n            if let Some(phases) = telemetry.get("phase_metrics").and_then(Value::as_object) {\n                for phase in ["WHITE", "RED", "BLACK", "YELLOW", "GREEN", "BLUE"] {\n                    if let Some(metric) = phases.get(phase).and_then(Value::as_object) {\n                        let exact = metric\n                            .get("exact_response_entropy_bits")\n                            .and_then(Value::as_f64)\n                            .unwrap_or(0.0);\n                        let lexical = metric\n                            .get("mean_pairwise_lexical_jaccard_distance")\n                            .and_then(Value::as_f64)\n                            .unwrap_or(0.0);\n                        self.append(&format!(\n                            "*** {phase}: H_exact={exact:.3} bits | lexical_div={lexical:.3}"\n                        ));\n                    }\n                }\n            }\n            self.append(\n                "*** Entropy/diversity are not truth, confidence, quality, evidence status, or vote weight."\n            );\n        }\n        Ok(())\n''',
)

# Focused telemetry tests.
test_telemetry = r'''from __future__ import annotations

from math import log2
import unittest

from nexus_runtime.api import NexusAPI
from nexus_runtime.council import CouncilCoordinator
from nexus_runtime.mock import DeterministicMockActor
from nexus_runtime.telemetry import (
    TELEMETRY_SCHEMA_VERSION,
    build_council_telemetry,
    mean_pairwise_lexical_jaccard_distance,
    shannon_entropy_bits_from_counts,
)
from nexus_runtime.types import CouncilMember
from nexus_runtime.world import WorldStore


def actor(member_id: str, profile: str = "balanced") -> DeterministicMockActor:
    return DeterministicMockActor(
        CouncilMember(member_id=member_id, model_id=f"mock-{member_id.lower()}"),
        profile=profile,
    )


class TelemetryMathTests(unittest.TestCase):
    def test_unanimous_ballot_entropy_is_zero(self) -> None:
        self.assertEqual(shannon_entropy_bits_from_counts({"TEST_FURTHER": 3}), 0.0)

    def test_three_equal_ballot_categories_are_log2_three(self) -> None:
        self.assertAlmostEqual(
            shannon_entropy_bits_from_counts({"ACCEPT": 1, "REJECT": 1, "TEST_FURTHER": 1}),
            log2(3),
            places=11,
        )

    def test_lexical_distance_distinguishes_overlap_without_claiming_entropy(self) -> None:
        same = mean_pairwise_lexical_jaccard_distance(["same words", "same words", "same words"])
        different = mean_pairwise_lexical_jaccard_distance(["alpha beta", "gamma delta", "epsilon zeta"])
        self.assertEqual(same, 0.0)
        self.assertEqual(different, 1.0)

    def test_exact_response_entropy_is_explicitly_not_semantic_entropy(self) -> None:
        entries = {
            phase: [
                {"member_id": "A", "content": "Alpha hypothesis"},
                {"member_id": "B", "content": "Beta hypothesis"},
                {"member_id": "C", "content": "Gamma hypothesis"},
            ]
            for phase in ("WHITE", "RED", "BLACK", "YELLOW", "GREEN", "BLUE")
        }
        ballots = [
            {"member_id": "A", "choice": "ACCEPT"},
            {"member_id": "B", "choice": "REJECT"},
            {"member_id": "C", "choice": "TEST_FURTHER"},
        ]
        telemetry = build_council_telemetry(entries, ballots, {"minority_reports": []})
        self.assertEqual(telemetry["schema_version"], TELEMETRY_SCHEMA_VERSION)
        self.assertFalse(telemetry["claim_boundaries"]["exact_response_entropy_is_semantic_entropy"])
        self.assertAlmostEqual(telemetry["phase_metrics"]["WHITE"]["exact_response_entropy_bits"], log2(3), places=11)


class TelemetryIntegrationTests(unittest.TestCase):
    def test_council_session_captures_observational_telemetry(self) -> None:
        world = WorldStore()
        result = CouncilCoordinator(world).run(
            "question",
            [actor("A"), actor("B", "skeptical"), actor("C", "supportive")],
        )
        session = world.inspect(result["session_ref"])
        telemetry = session.payload["telemetry"]
        self.assertEqual(telemetry["role"], "observational_only")
        self.assertFalse(telemetry["authority_effects"]["changes_vote_weight"])
        self.assertEqual(result["telemetry"], telemetry)
        self.assertIn("WHITE", telemetry["phase_metrics"])
        self.assertIn("shannon_entropy_bits", telemetry["ballot_metrics"])

    def test_api_recomputes_and_verifies_captured_telemetry(self) -> None:
        api = NexusAPI()
        run = api.handle(
            {
                "operation": "council.run",
                "question": "q",
                "members": [
                    {"member_id": "A", "model_id": "a"},
                    {"member_id": "B", "model_id": "b", "profile": "skeptical"},
                    {"member_id": "C", "model_id": "c", "profile": "supportive"},
                ],
            }
        )
        verified = api.handle({"operation": "telemetry.verify", "session_ref": run["session_ref"]})
        self.assertEqual(verified["status"], "verified")
        self.assertTrue(verified["matches"])
        self.assertEqual(verified["schema_version"], TELEMETRY_SCHEMA_VERSION)

    def test_telemetry_never_changes_vote_mechanics(self) -> None:
        world = WorldStore()
        result = CouncilCoordinator(world).run(
            "question",
            [actor("A"), actor("B"), actor("C", "supportive")],
        )
        self.assertEqual(result["result"]["tally"]["TEST_FURTHER"], 2)
        self.assertEqual(result["result"]["consensus_label"], "CONSENSUS")
        self.assertFalse(result["telemetry"]["authority_effects"]["changes_consensus_threshold"])


if __name__ == "__main__":
    unittest.main()
'''
Path('tests/test_telemetry.py').write_text(test_telemetry)

# Documentation.
telemetry_doc = r'''# Council Information Telemetry

NEXUS 2.0-alpha6 adds deterministic observation channels for how a Council converges or diverges.

> **Telemetry observes the Council. It does not govern the Council.**

Telemetry never changes vote weight, consensus thresholds, evidence state, verification state, or the Equality Guard.

## Implemented metrics

### Ballot Shannon entropy

For sealed ballot categories with probabilities `p_i`:

```text
H = -sum(p_i * log2(p_i))
```

A unanimous ballot has `H = 0` bits. Three equally represented ballot categories have `H = log2(3) ~= 1.585` bits.

This is Shannon entropy because the random variable is explicit: the categorical distribution of sealed ballot choices.

### Per-hat exact-response entropy

For each White/Red/Black/Yellow/Green/Blue phase, responses are normalized by Unicode NFKC, case-folding, and whitespace collapse, then grouped by exact SHA-256 fingerprint. Shannon entropy is computed over those exact categories.

This is **not semantic entropy**. Paraphrases may fall into different exact categories even when they mean nearly the same thing.

### Per-hat lexical divergence

NEXUS also records mean pairwise Jaccard distance over normalized token sets. This gives a deterministic near-overlap signal in `[0, 1]` without mislabelling it Shannon entropy.

It is not a truth score, quality score, confidence score, or authority score.

### Minority snapshot

The ballot telemetry records the number and fraction of current minority reports. Longitudinal *minority-branch persistence* across sessions remains deferred until persistent-world lineage semantics are mature enough to define it precisely.

## Reproducibility

Telemetry is stored inside the content-addressed `council_session` payload and is derived entirely from captured phase submissions, revealed ballots, and the Council result.

The additive JSONL operation:

```text
telemetry.verify
```

recomputes the telemetry from the stored Council artifact and checks that it matches the captured telemetry block.

## Claim boundaries

High entropy is not automatically good. Low entropy is not automatically truth. Diversity can reflect useful independent hypotheses, noise, ambiguity, prompt sensitivity, or model failure. Convergence can reflect genuine constraint, shared priors, common training data, anchoring, or a trivial question.

No telemetry field is permitted to affect `vote_weight = 1` or any other Council authority mechanism.

## Deferred metrics

Alpha6 deliberately defers metrics that need stronger measurement rules:

- semantic response entropy;
- hypothesis branching multiplicity;
- controlled perturbation recovery;
- loop/repeated-motif indicators;
- mode-transition cost;
- minority-branch persistence across sessions;
- geometric labels such as `bottlenecked` or `shattered`.

Those names will not enter runtime state until NEXUS has an explicit operational definition for them.
'''
Path('docs/TELEMETRY.md').write_text(telemetry_doc)

# README: turn the planned section into an implemented alpha6 section.
readme = Path('README.md').read_text()
start = readme.index('## Next: Council information telemetry')
end = readme.index('\n## What is deliberately not here yet', start)
new_section = r'''## Council information telemetry

Alpha6 adds deterministic, replay-friendly observation of Council convergence and divergence.

```text
WHITE   H_exact + lexical divergence
RED     H_exact + lexical divergence
BLACK   H_exact + lexical divergence
YELLOW  H_exact + lexical divergence
GREEN   H_exact + lexical divergence
BLUE    H_exact + lexical divergence
BALLOT  Shannon entropy over sealed choices
```

The hard boundary is:

> **Information diversity is telemetry, not truth.**

`ballot_metrics.shannon_entropy_bits` is genuine Shannon entropy over an explicit categorical distribution. Per-hat `exact_response_entropy_bits` is Shannon entropy over exact normalized response categories and is explicitly **not semantic entropy**. Near-similarity is reported separately as mean pairwise lexical Jaccard distance.

Every captured Council session stores its telemetry, and `telemetry.verify` can recompute it from the session artifact.

No telemetry value changes vote weight, consensus thresholds, evidence status, verification, or the Equality Guard.

See [`docs/TELEMETRY.md`](docs/TELEMETRY.md).
'''
Path('README.md').write_text(readme[:start] + new_section + readme[end:])

# Roadmap alpha6 status.
roadmap = Path('ROADMAP.md').read_text()
start = roadmap.index('## 2.0-alpha6 — Council information telemetry')
end = roadmap.index('\n## 2.0-alpha7 — Instruments', start)
alpha6 = r'''## 2.0-alpha6 — Council information telemetry

Implemented / targeted in PR #6.

- [x] deterministic telemetry module with no external runtime dependency;
- [x] ballot Shannon entropy over explicit sealed ballot categories;
- [x] per-hat exact-response category entropy;
- [x] per-hat lexical Jaccard divergence for near-overlap observation;
- [x] current minority-report count/fraction snapshot;
- [x] telemetry stored inside the content-addressed Council session artifact;
- [x] `telemetry.verify` recomputation path;
- [x] copy-friendly Rust TUI telemetry summary;
- [x] explicit machine-readable authority/claim boundaries;
- [x] reproducibility tests.

Deferred until explicit operational rules exist:

- [ ] semantic response entropy;
- [ ] hypothesis branching multiplicity;
- [ ] controlled-perturbation recovery;
- [ ] loop / repeated-motif indicators;
- [ ] mode-transition cost;
- [ ] minority-branch persistence across sessions;
- [ ] geometric labels such as `bottlenecked` or `shattered`.

Core invariant:

> **Telemetry observes the Council. It does not govern the Council.**

High entropy is not automatically good. Low entropy is not automatically truth.
'''
Path('ROADMAP.md').write_text(roadmap[:start] + alpha6 + roadmap[end:])

# API docs: additive operation and version strings where present.
api_doc = Path('docs/API.md').read_text()
api_doc = api_doc.replace('nexus/0.4', 'nexus/0.5')
if 'telemetry.verify' not in api_doc:
    api_doc += r'''

## `telemetry.verify`

Recompute deterministic Council telemetry from a captured `council_session` object.

```json
{"request_id":"t1","operation":"telemetry.verify","session_ref":"object:<sha256>"}
```

A successful verification returns `status: "verified"`, `matches: true`, the telemetry schema version, and the recomputed telemetry block. Telemetry is observational only and cannot alter Council authority or evidence status.
'''
Path('docs/API.md').write_text(api_doc)

# Changelog.
changelog = Path('CHANGELOG.md').read_text()
marker = '# Changelog\n'
entry = r'''

## 2.0.0-alpha6 — Council information telemetry

- add deterministic ballot Shannon entropy;
- add per-hat exact-response entropy and lexical Jaccard divergence;
- persist telemetry in Council session artifacts;
- add `telemetry.verify` recomputation;
- render observational telemetry in the Rust IRC-style TUI;
- explicitly prohibit telemetry from affecting votes, consensus, evidence, or verification;
- defer semantic entropy and geometry-flavoured labels until they have explicit measurement rules.
'''
if marker not in changelog:
    raise SystemExit('CHANGELOG heading not found')
Path('CHANGELOG.md').write_text(changelog.replace(marker, marker + entry, 1))

print('Applied alpha6 Council information telemetry changes.')
