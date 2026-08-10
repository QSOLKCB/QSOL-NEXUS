#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
HUMAN_README = ROOT / "README.md"
AI_README = ROOT / "README4AI.md"
EXPECTED_DOCUMENT_TYPE = "qsol-nexus-ai-manifest"
EXPECTED_SCHEMA_VERSION = 1
EXPECTED_SYNC_POLICY = "README.md_change_requires_README4AI.md_change_same_pull_request"
ZERO_SHA = "0" * 40


class ContractError(RuntimeError):
    pass


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise ContractError(f"README4AI.md contains duplicate JSON key: {key}")
        output[key] = value
    return output


def _reject_constant(value: str) -> Any:
    raise ContractError(f"README4AI.md contains non-finite JSON number: {value}")


def load_manifest() -> dict[str, Any]:
    try:
        text = AI_README.read_text(encoding="utf-8")
    except OSError as exc:
        raise ContractError(f"cannot read README4AI.md: {exc}") from exc
    try:
        decoded = json.loads(
            text,
            object_pairs_hook=_strict_object,
            parse_constant=_reject_constant,
        )
    except (json.JSONDecodeError, ContractError) as exc:
        raise ContractError(f"README4AI.md must be strict JSON: {exc}") from exc
    if not isinstance(decoded, dict):
        raise ContractError("README4AI.md top level must be a JSON object")
    return decoded


def _require(mapping: dict[str, Any], key: str, expected_type: type[Any]) -> Any:
    value = mapping.get(key)
    if not isinstance(value, expected_type):
        raise ContractError(
            f"README4AI.md field {key!r} must be {expected_type.__name__}"
        )
    return value


def validate_manifest() -> dict[str, Any]:
    manifest = load_manifest()
    if manifest.get("document_type") != EXPECTED_DOCUMENT_TYPE:
        raise ContractError(
            f"README4AI.md document_type must be {EXPECTED_DOCUMENT_TYPE!r}"
        )
    if manifest.get("schema_version") != EXPECTED_SCHEMA_VERSION:
        raise ContractError(
            f"README4AI.md schema_version must be {EXPECTED_SCHEMA_VERSION}"
        )

    audience = _require(manifest, "audience", dict)
    if audience.get("primary") != "ai":
        raise ContractError("README4AI.md audience.primary must be 'ai'")
    if audience.get("human_document") != "README.md":
        raise ContractError("README4AI.md audience.human_document must be 'README.md'")

    sync = _require(manifest, "synchronization", dict)
    if sync.get("policy") != EXPECTED_SYNC_POLICY:
        raise ContractError(
            "README4AI.md synchronization.policy does not match the repository contract"
        )
    if sync.get("human_surface") != "README.md" or sync.get("machine_surface") != "README4AI.md":
        raise ContractError("README4AI.md synchronization surfaces are invalid")

    serialization = _require(manifest, "serialization", dict)
    expected_serialization = {
        "format": "json",
        "encoding": "utf-8",
        "duplicate_keys": "forbidden",
        "non_finite_numbers": "forbidden",
    }
    for key, expected in expected_serialization.items():
        if serialization.get(key) != expected:
            raise ContractError(
                f"README4AI.md serialization.{key} must be {expected!r}"
            )

    release = _require(manifest, "release_identity", dict)
    for key in ("protocol", "runtime", "python_package", "rust_tui", "stable_2_0"):
        if key not in release:
            raise ContractError(f"README4AI.md release_identity missing {key!r}")
    if type(release["stable_2_0"]) is not bool:
        raise ContractError("README4AI.md release_identity.stable_2_0 must be boolean")

    for key in (
        "normative_precedence",
        "authority_invariants",
        "runtime",
        "adapters",
        "world",
        "council",
        "security_boundaries",
        "epistemic_labels",
        "prohibited_inferences",
        "modification_contract",
        "read_next",
    ):
        if key not in manifest:
            raise ContractError(f"README4AI.md missing required top-level field {key!r}")

    readme = HUMAN_README.read_text(encoding="utf-8")
    if "[README4AI.md](README4AI.md)" not in readme and "[`README4AI.md`](README4AI.md)" not in readme:
        raise ContractError("README.md must link to README4AI.md")
    for key in ("protocol", "runtime", "python_package", "rust_tui"):
        value = release[key]
        if not isinstance(value, str) or not value:
            raise ContractError(f"README4AI.md release_identity.{key} must be non-empty text")
        if value not in readme:
            raise ContractError(
                f"README.md does not contain README4AI release_identity.{key} value {value!r}"
            )
    return manifest


def changed_files(base: str, head: str) -> set[str]:
    if not base or not head:
        raise ContractError("both --base and --head are required for diff validation")
    if base == ZERO_SHA:
        return set()
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=ACMRD", base, head],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ContractError(f"cannot inspect README diff contract: {exc}") from exc
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def validate_sync(base: str, head: str) -> None:
    files = changed_files(base, head)
    if "README.md" in files and "README4AI.md" not in files:
        raise ContractError(
            "README.md changed without README4AI.md; both documentation surfaces must be updated in the same change"
        )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate the NEXUS human/machine README contract."
    )
    parser.add_argument("--base", help="base commit for paired-change validation")
    parser.add_argument("--head", help="head commit for paired-change validation")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        manifest = validate_manifest()
        if (args.base is None) != (args.head is None):
            raise ContractError("--base and --head must be supplied together")
        if args.base is not None and args.head is not None:
            validate_sync(args.base, args.head)
        print(
            "README contract OK: "
            f"schema={manifest['schema_version']} policy={manifest['synchronization']['policy']}"
        )
        return 0
    except (ContractError, OSError) as exc:
        print(f"README CONTRACT ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
