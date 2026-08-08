from __future__ import annotations

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
