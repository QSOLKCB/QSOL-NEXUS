from __future__ import annotations

from math import isqrt
from typing import Any, Iterable

from .canonical import sha256_ref


INTEGER_PRIMALITY_INSTRUMENT = "nexus.integer-primality/1"
MAX_INTEGER_VALUES = 128
MAX_INTEGER_VALUE = 10_000_000
DEFAULT_INTEGER_VALUES = (2, 3, 5, 7, 11, 13, 17, 19, 23, 25)


def normalize_integer_values(values: Iterable[int]) -> tuple[int, ...]:
    """Validate and freeze the bounded integer fixture for the alpha11 probe."""

    normalized = tuple(values)
    if not normalized:
        raise ValueError("integer fixture must contain at least one value")
    if len(normalized) > MAX_INTEGER_VALUES:
        raise ValueError(f"integer fixture permits at most {MAX_INTEGER_VALUES} values")
    for index, value in enumerate(normalized, start=1):
        if type(value) is not int:
            raise ValueError(
                f"integer fixture value {index} must be an exact integer; "
                f"got {type(value).__name__}"
            )
        if not 2 <= value <= MAX_INTEGER_VALUE:
            raise ValueError(
                f"integer fixture value {index} must be in [2, {MAX_INTEGER_VALUE}]; "
                f"got {value}"
            )
    return normalized


def _smallest_factor(value: int) -> int | None:
    if value == 2:
        return None
    if value % 2 == 0:
        return 2
    limit = isqrt(value)
    candidate = 3
    while candidate <= limit:
        if value % candidate == 0:
            return candidate
        candidate += 2
    return None


def integer_primality_probe(values: Iterable[int]) -> dict[str, Any]:
    """Run the bounded deterministic integer-only alpha11 instrument.

    The result verifies primality only for the supplied finite fixture. It is
    deliberately not a general scientific-validation or truth oracle.
    """

    normalized = normalize_integer_values(values)
    results: list[dict[str, Any]] = []
    composites: list[int] = []
    for value in normalized:
        factor = _smallest_factor(value)
        is_prime = factor is None
        if not is_prime:
            composites.append(value)
        results.append(
            {
                "value": value,
                "is_prime": is_prime,
                "smallest_factor": factor,
            }
        )
    input_ref = sha256_ref("integer_fixture", {"values": list(normalized)})
    return {
        "instrument_id": INTEGER_PRIMALITY_INSTRUMENT,
        "input_ref": input_ref,
        "value_count": len(normalized),
        "values": list(normalized),
        "results": results,
        "all_prime": not composites,
        "composite_values": composites,
        "claim_boundary": "exact integer primality for the supplied bounded fixture only",
    }


def render_integer_primality_evidence(probe: dict[str, Any]) -> str:
    """Render a compact model-readable result that always names the tested values."""

    composites = []
    for result in probe["results"]:
        if not result["is_prime"]:
            composites.append(f"{result['value']} (factor {result['smallest_factor']})")
    rendered_composites = ", ".join(composites) if composites else "none"
    rendered_values = ",".join(str(value) for value in probe["values"])
    return (
        f"{INTEGER_PRIMALITY_INSTRUMENT} checked values=[{rendered_values}]; "
        f"count={probe['value_count']}; all_prime={str(probe['all_prime']).lower()}; "
        f"composites={rendered_composites}."
    )


__all__ = [
    "DEFAULT_INTEGER_VALUES",
    "INTEGER_PRIMALITY_INSTRUMENT",
    "MAX_INTEGER_VALUE",
    "MAX_INTEGER_VALUES",
    "integer_primality_probe",
    "normalize_integer_values",
    "render_integer_primality_evidence",
]
