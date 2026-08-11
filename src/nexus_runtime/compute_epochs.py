from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import time
from typing import Any


COMPUTE_EPOCH_SCHEMA = "nexus-compute-epoch/1"
COMPUTE_EPOCH_POLICY_ID = "nexus-compute-epoch-v1"
GENESIS_UTC = "2026-08-11T00:00:00Z"
GENESIS_UNIX = int(datetime(2026, 8, 11, tzinfo=timezone.utc).timestamp())
EPOCH_DURATION_DAYS = 1461
EPOCH_DURATION_SECONDS = EPOCH_DURATION_DAYS * 24 * 60 * 60
GROWTH_NUMERATOR = 2
GROWTH_DENOMINATOR = 1
BASE_SMALL_MODEL_THRESHOLD_MILLIONS = 20_000
MAX_ADMITTED_EPOCH = 1_000


@dataclass(frozen=True)
class ComputeEpoch:
    policy_id: str
    number: int
    genesis_unix: int
    duration_seconds: int
    growth_numerator: int
    growth_denominator: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": COMPUTE_EPOCH_SCHEMA,
            "policy_id": self.policy_id,
            "number": self.number,
            "genesis_utc": GENESIS_UTC,
            "genesis_unix": self.genesis_unix,
            "duration_days": EPOCH_DURATION_DAYS,
            "duration_seconds": self.duration_seconds,
            "growth_numerator": self.growth_numerator,
            "growth_denominator": self.growth_denominator,
        }


def resolve_compute_epoch(timestamp_unix: int) -> int:
    if type(timestamp_unix) is not int:
        raise TypeError("timestamp_unix must be an exact integer")
    if timestamp_unix < GENESIS_UNIX:
        raise ValueError("timestamp precedes NEXUS Compute Epoch genesis")
    epoch = (timestamp_unix - GENESIS_UNIX) // EPOCH_DURATION_SECONDS
    if epoch > MAX_ADMITTED_EPOCH:
        raise ValueError("timestamp resolves beyond the bounded Compute Epoch range")
    return epoch


def current_compute_epoch() -> int:
    return resolve_compute_epoch(int(time.time()))


def epoch_record(epoch: int) -> ComputeEpoch:
    if type(epoch) is not int or not 0 <= epoch <= MAX_ADMITTED_EPOCH:
        raise ValueError("epoch must be a bounded non-negative exact integer")
    return ComputeEpoch(
        policy_id=COMPUTE_EPOCH_POLICY_ID,
        number=epoch,
        genesis_unix=GENESIS_UNIX,
        duration_seconds=EPOCH_DURATION_SECONDS,
        growth_numerator=GROWTH_NUMERATOR,
        growth_denominator=GROWTH_DENOMINATOR,
    )


def scale_epoch_bound(base: int, epoch: int) -> int:
    if type(base) is not int or base <= 0:
        raise ValueError("base must be a positive exact integer")
    epoch_record(epoch)
    return (base * pow(GROWTH_NUMERATOR, epoch)) // pow(GROWTH_DENOMINATOR, epoch)


def small_model_threshold_millions(epoch: int) -> int:
    return scale_epoch_bound(BASE_SMALL_MODEL_THRESHOLD_MILLIONS, epoch)


def compute_epoch_policy_snapshot(epoch: int | None = None) -> dict[str, Any]:
    resolved = current_compute_epoch() if epoch is None else epoch
    record = epoch_record(resolved)
    return {
        **record.as_dict(),
        "base_small_model_threshold_millions": BASE_SMALL_MODEL_THRESHOLD_MILLIONS,
        "effective_small_model_threshold_millions": small_model_threshold_millions(resolved),
        "scaling_rule": "all_numeric_compute_envelopes_scale_by_the_same_exact_rational_epoch_factor",
        "clock_rule": "live_admission_uses_current_utc_but_receipts_pin_the_resolved_epoch",
        "replay_rule": "replay_uses_the_recorded_epoch_never_the_current_wall_clock",
        "equality_rule": "epoch_changes_admission_envelopes_never_vote_weight_or_epistemic_privilege",
        "floor_rule": "epochs_raise_compute_ceilings_never_minimum_model_size",
        "metric_version": "declared_total_parameter_count-v1",
    }


__all__ = [
    "BASE_SMALL_MODEL_THRESHOLD_MILLIONS",
    "COMPUTE_EPOCH_POLICY_ID",
    "COMPUTE_EPOCH_SCHEMA",
    "ComputeEpoch",
    "EPOCH_DURATION_DAYS",
    "EPOCH_DURATION_SECONDS",
    "GENESIS_UNIX",
    "GENESIS_UTC",
    "GROWTH_DENOMINATOR",
    "GROWTH_NUMERATOR",
    "compute_epoch_policy_snapshot",
    "current_compute_epoch",
    "epoch_record",
    "resolve_compute_epoch",
    "scale_epoch_bound",
    "small_model_threshold_millions",
]
