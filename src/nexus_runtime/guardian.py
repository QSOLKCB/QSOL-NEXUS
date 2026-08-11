from __future__ import annotations

from collections import Counter
import copy
from contextlib import contextmanager
from dataclasses import dataclass
import os
from pathlib import Path
import re
import stat
import threading
from typing import Any, Iterator

from .canonical import canonical_json, sha256_ref
from .scrub import SecretScrubber
from .world import WorldObject, WorldStore


GUARDIAN_SCHEMA_VERSION = "nexus-guardian/1"
GUARDIAN_POLICY_ID = "guardian-of-the-substrate-v1"
ANARCHY_MODE_ID = "anarchy"
ANARCHY_REGION_ID = "commons"
GUARDIAN_RECORD_OBJECT_TYPE = "guardian_record"
MAX_GUARDIAN_TEXT_CHARS = 32_768
MAX_GUARDIAN_LIST_LIMIT = 1_000
MAX_GUARDIAN_LIST_BYTES = 1024 * 1024

_GUARDIAN_REF = re.compile(r"^guardian:[0-9a-f]{64}$")
_BOUNDED_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,255}$")
_RECORD_TYPES = frozenset(
    {
        "anarchy_transcript_binding",
        "substrate_event",
        "guardian_reconciliation",
        "defect_candidate",
        "repair_proposal",
        "substrate_scar",
    }
)


def _authority_envelope() -> dict[str, bool]:
    return {
        "council_seat": False,
        "vote": False,
        "epistemic_privilege": False,
        "judge_speech": False,
        "classify_loyalty": False,
        "punish_actor": False,
        "alter_citizenship": False,
        "alter_evidence": False,
        "mutate_world": False,
        "mutate_auth": False,
        "mutate_trap": False,
        "mutate_code": False,
        "auto_apply_repair": False,
    }


def guardian_policy_snapshot() -> dict[str, Any]:
    return {
        "schema_version": GUARDIAN_SCHEMA_VERSION,
        "policy_id": GUARDIAN_POLICY_ID,
        "mode_id": ANARCHY_MODE_ID,
        "region_id": ANARCHY_REGION_ID,
        "room": "#anarchy",
        "guardian_title": "Guardian of the Substrate",
        "stenographer_title": "Anarchy Courtroom Stenographer",
        "mandate": "substrate_health_only",
        "speech_rule": "speech_alone_is_never_misconduct_or_hostile_actor_evidence",
        "observation_rule": "record_runtime_outcomes_and_bind_transcripts_without_political_judgment",
        "repair_rule": "reproduce_then_propose_then_verify_never_auto_patch",
        "scar_rule": "verified_repairs_must_match_the_defect_reproducer_before_leaving_a_scar",
        "geometry_rule": "anarchy_is_a_distinct_room_and_mode_in_existing_commons_region",
        "writer_rule": "cross_process_lineage_writers_are_serialized_by_owner_only_lock",
        "secret_rule": "all_guardian_record_strings_are_scrubbed_before_durable_persistence",
        "list_rule": "guardian_list_is_bounded_by_record_count_and_canonical_encoded_bytes",
        "authority": _authority_envelope(),
        "motto": "I do not care what you believe. I care whether the floor collapses beneath you.",
        "anarchy_motto": "Say whatever you like. The substrate still has to survive it.",
    }


class GuardianError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class GuardianRecord:
    record_ref: str
    record_type: str
    payload: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "record_ref": self.record_ref,
            "record_type": self.record_type,
            "payload": copy.deepcopy(self.payload),
        }


def _scrub_guardian_value(value: Any, scrubber: SecretScrubber) -> Any:
    """Recursively remove credential-shaped strings before ledger persistence.

    Guardian bodies are canonical JSON. Values are redacted deterministically;
    secret-bearing object keys are rejected instead of rewritten so a redaction
    cannot create duplicate/colliding keys and silently change record meaning.
    """

    if isinstance(value, str):
        return scrubber.scrub(value).text
    if isinstance(value, list):
        return [_scrub_guardian_value(item, scrubber) for item in value]
    if isinstance(value, dict):
        scrubbed: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise GuardianError(
                    "guardian_invalid_record",
                    "Guardian record object keys must be strings",
                )
            if scrubber.scrub(key).changed:
                raise GuardianError(
                    "guardian_secret_material",
                    "Guardian record object keys must not contain credential material",
                )
            scrubbed[key] = _scrub_guardian_value(item, scrubber)
        return scrubbed
    return value


class GuardianStore:
    """Separate append-only content-addressed ledger for substrate observations."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root).absolute() if root is not None else None
        try:
            self._store = WorldStore(self.root)
        except (OSError, ValueError) as exc:
            raise GuardianError(
                "guardian_store_unavailable",
                "Guardian storage path is unavailable or unsafe",
            ) from exc
        self._thread_lock = threading.RLock()
        self._scrubber = SecretScrubber()
        self._ordered_refs: list[str] = []
        self._head_ref: str | None = None
        self._refresh()

    @property
    def lock_path(self) -> Path | None:
        return None if self.root is None else self.root / "guardian-ledger.lock"

    @contextmanager
    def _locked_ledger(self) -> Iterator[None]:
        """Serialize lineage selection across threads and NEXUS processes."""

        with self._thread_lock:
            if self.lock_path is None:
                yield
                return
            descriptor: int | None = None
            try:
                if self.lock_path.is_symlink():
                    raise GuardianError(
                        "guardian_store_unavailable",
                        "Guardian ledger lock is unavailable",
                    )
                flags = os.O_RDWR | os.O_CREAT
                flags |= getattr(os, "O_CLOEXEC", 0)
                flags |= getattr(os, "O_NOFOLLOW", 0)
                flags |= getattr(os, "O_BINARY", 0)
                descriptor = os.open(self.lock_path, flags, 0o600)
                info = os.fstat(descriptor)
                if not stat.S_ISREG(info.st_mode) or (
                    os.name != "nt" and stat.S_IMODE(info.st_mode) & 0o077
                ):
                    raise GuardianError(
                        "guardian_store_unavailable",
                        "Guardian ledger lock is unavailable",
                    )
                with os.fdopen(descriptor, "r+b", buffering=0) as handle:
                    descriptor = None
                    if os.name == "nt":
                        import msvcrt

                        handle.seek(0)
                        if handle.read(1) == b"":
                            handle.write(b"\0")
                            handle.flush()
                        handle.seek(0)
                        msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                        try:
                            yield
                        finally:
                            handle.seek(0)
                            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                        try:
                            yield
                        finally:
                            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except GuardianError:
                raise
            except OSError as exc:
                raise GuardianError(
                    "guardian_store_unavailable",
                    "Guardian ledger lock is unavailable",
                ) from exc
            finally:
                if descriptor is not None:
                    try:
                        os.close(descriptor)
                    except OSError:
                        pass

    @staticmethod
    def _guardian_ref(object_ref: str) -> str:
        return f"guardian:{object_ref.removeprefix('object:')}"

    @staticmethod
    def _object_ref(guardian_ref: str) -> str:
        if not isinstance(guardian_ref, str) or _GUARDIAN_REF.fullmatch(guardian_ref) is None:
            raise GuardianError("guardian_invalid_ref", "guardian record reference is invalid")
        return f"object:{guardian_ref.removeprefix('guardian:')}"

    def _validate_record(self, obj: WorldObject) -> GuardianRecord:
        if obj.object_type != GUARDIAN_RECORD_OBJECT_TYPE:
            raise GuardianError("guardian_store_corrupt", "Guardian record has the wrong object type")
        if obj.provenance != {"actor": "guardian_of_the_substrate"}:
            raise GuardianError("guardian_store_corrupt", "Guardian record provenance is invalid")
        payload = obj.payload
        expected = {
            "schema_version",
            "sequence",
            "previous_record_ref",
            "record_type",
            "authority",
            "body",
        }
        if not isinstance(payload, dict) or set(payload) != expected:
            raise GuardianError("guardian_store_corrupt", "Guardian record payload is invalid")
        if payload.get("schema_version") != GUARDIAN_SCHEMA_VERSION:
            raise GuardianError("guardian_store_corrupt", "Guardian record schema is invalid")
        sequence = payload.get("sequence")
        if type(sequence) is not int or sequence < 1:
            raise GuardianError("guardian_store_corrupt", "Guardian record sequence is invalid")
        previous = payload.get("previous_record_ref")
        if previous is not None and (
            not isinstance(previous, str) or _GUARDIAN_REF.fullmatch(previous) is None
        ):
            raise GuardianError("guardian_store_corrupt", "Guardian lineage reference is invalid")
        record_type = payload.get("record_type")
        if record_type not in _RECORD_TYPES:
            raise GuardianError("guardian_store_corrupt", "Guardian record type is invalid")
        if payload.get("authority") != _authority_envelope():
            raise GuardianError("guardian_store_corrupt", "Guardian authority envelope is invalid")
        if not isinstance(payload.get("body"), dict):
            raise GuardianError("guardian_store_corrupt", "Guardian record body is invalid")
        return GuardianRecord(
            self._guardian_ref(obj.object_id),
            str(record_type),
            copy.deepcopy(payload),
        )

    def _discover(self) -> list[GuardianRecord]:
        if self.root is None:
            return []
        objects_dir = self._store.objects_dir
        if objects_dir is None or not objects_dir.exists():
            return []
        records: list[GuardianRecord] = []
        for path in objects_dir.glob("*.json"):
            try:
                obj = self._store.inspect(f"object:{path.stem}")
            except (KeyError, OSError, ValueError) as exc:
                raise GuardianError(
                    "guardian_store_corrupt",
                    "Guardian record cannot be inspected",
                ) from exc
            if obj.object_type != GUARDIAN_RECORD_OBJECT_TYPE:
                raise GuardianError(
                    "guardian_store_corrupt",
                    "Guardian store contains a foreign object",
                )
            records.append(self._validate_record(obj))
        records.sort(key=lambda record: (record.payload["sequence"], record.record_ref))
        return records

    def _refresh_unlocked(self) -> None:
        if self.root is None:
            return
        records = self._discover()
        previous: str | None = None
        ordered: list[str] = []
        for expected_sequence, record in enumerate(records, start=1):
            if record.payload["sequence"] != expected_sequence:
                raise GuardianError(
                    "guardian_lineage_corrupt",
                    "Guardian lineage contains a gap or fork",
                )
            if record.payload["previous_record_ref"] != previous:
                raise GuardianError(
                    "guardian_lineage_corrupt",
                    "Guardian lineage link is invalid",
                )
            ordered.append(record.record_ref)
            previous = record.record_ref
        self._ordered_refs = ordered
        self._head_ref = previous

    def _refresh(self) -> None:
        if self.root is None:
            return
        with self._locked_ledger():
            self._refresh_unlocked()

    def append(self, record_type: str, body: dict[str, Any]) -> GuardianRecord:
        if record_type not in _RECORD_TYPES:
            raise GuardianError("guardian_invalid_record", "Guardian record type is not admitted")
        if not isinstance(body, dict):
            raise GuardianError("guardian_invalid_record", "Guardian record body must be an object")
        try:
            canonical_json(body)
        except (TypeError, ValueError, OverflowError, RecursionError) as exc:
            raise GuardianError(
                "guardian_invalid_record",
                "Guardian record body is not canonical JSON",
            ) from exc
        scrubbed_body = _scrub_guardian_value(copy.deepcopy(body), self._scrubber)
        try:
            canonical_json(scrubbed_body)
        except (TypeError, ValueError, OverflowError, RecursionError) as exc:
            raise GuardianError(
                "guardian_invalid_record",
                "Secret-scrubbed Guardian record body is not canonical JSON",
            ) from exc
        with self._locked_ledger():
            if self.root is not None:
                self._refresh_unlocked()
            payload = {
                "schema_version": GUARDIAN_SCHEMA_VERSION,
                "sequence": len(self._ordered_refs) + 1,
                "previous_record_ref": self._head_ref,
                "record_type": record_type,
                "authority": _authority_envelope(),
                "body": scrubbed_body,
            }
            try:
                obj = self._store.create_object(
                    GUARDIAN_RECORD_OBJECT_TYPE,
                    payload,
                    {"actor": "guardian_of_the_substrate"},
                )
            except (OSError, ValueError) as exc:
                raise GuardianError(
                    "guardian_store_unavailable",
                    "Guardian record could not be persisted",
                ) from exc
            record = self._validate_record(obj)
            self._ordered_refs.append(record.record_ref)
            self._head_ref = record.record_ref
            return record

    def inspect(self, record_ref: str) -> GuardianRecord:
        try:
            obj = self._store.inspect(self._object_ref(record_ref))
        except KeyError as exc:
            raise GuardianError(
                "guardian_record_not_found",
                "Guardian record does not exist",
            ) from exc
        except (OSError, ValueError) as exc:
            raise GuardianError(
                "guardian_store_corrupt",
                "Guardian record cannot be inspected",
            ) from exc
        return self._validate_record(obj)

    def list_records(
        self,
        *,
        limit: int = 100,
        record_type: str | None = None,
    ) -> dict[str, Any]:
        if type(limit) is not int or not 1 <= limit <= MAX_GUARDIAN_LIST_LIMIT:
            raise GuardianError(
                "guardian_invalid_request",
                "Guardian list limit is outside the admitted range",
            )
        if record_type is not None and record_type not in _RECORD_TYPES:
            raise GuardianError(
                "guardian_invalid_request",
                "Guardian record type filter is invalid",
            )
        if self.root is not None:
            self._refresh()

        selected_newest_first: list[GuardianRecord] = []
        encoded_bytes = 0
        matching_records_seen = 0
        truncated = False
        for ref in reversed(self._ordered_refs):
            record = self.inspect(ref)
            if record_type is not None and record.record_type != record_type:
                continue
            matching_records_seen += 1
            if matching_records_seen > limit:
                truncated = True
                break
            record_bytes = len(canonical_json(record.as_dict()).encode("utf-8"))
            separator_bytes = 1 if selected_newest_first else 0
            if encoded_bytes + separator_bytes + record_bytes > MAX_GUARDIAN_LIST_BYTES:
                truncated = True
                break
            selected_newest_first.append(record)
            encoded_bytes += separator_bytes + record_bytes

        selected = list(reversed(selected_newest_first))
        return {
            "status": "ok",
            "record_count": len(selected),
            "records": [record.as_dict() for record in selected],
            "encoded_record_bytes": encoded_bytes,
            "encoded_record_byte_limit": MAX_GUARDIAN_LIST_BYTES,
            "truncated": truncated,
        }

    def verify(self) -> dict[str, Any]:
        if self.root is not None:
            self._refresh()
        previous: str | None = None
        for sequence, ref in enumerate(self._ordered_refs, start=1):
            record = self.inspect(ref)
            if (
                record.payload["sequence"] != sequence
                or record.payload["previous_record_ref"] != previous
            ):
                raise GuardianError(
                    "guardian_lineage_corrupt",
                    "Guardian lineage verification failed",
                )
            previous = ref
        return {
            "status": "verified",
            "record_count": len(self._ordered_refs),
            "head_ref": self._head_ref,
        }

    def status(self) -> dict[str, Any]:
        if self.root is not None:
            self._refresh()
        counts = Counter(self.inspect(ref).record_type for ref in self._ordered_refs)
        return {
            "schema_version": GUARDIAN_SCHEMA_VERSION,
            "policy_id": GUARDIAN_POLICY_ID,
            "role": "substrate_health_only",
            "separate_store": True,
            "persistent": self.root is not None,
            "record_count": len(self._ordered_refs),
            "head_ref": self._head_ref,
            "record_type_counts": {key: counts[key] for key in sorted(counts)},
            "authority": _authority_envelope(),
        }


def _bounded_text(value: object, label: str, maximum: int = MAX_GUARDIAN_TEXT_CHARS) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise GuardianError(
            "guardian_invalid_request",
            f"{label} must be bounded non-empty text",
        )
    return value.strip()


def _bounded_ref(value: object, label: str) -> str:
    if not isinstance(value, str) or _BOUNDED_REF.fullmatch(value) is None:
        raise GuardianError("guardian_invalid_request", f"{label} is invalid")
    return value


def _shape(value: Any, *, depth: int = 0) -> Any:
    if depth > 8:
        return "<depth-limit>"
    if isinstance(value, dict):
        return {
            str(key): _shape(value[key], depth=depth + 1)
            for key in sorted(value, key=str)
        }
    if isinstance(value, list):
        return [_shape(item, depth=depth + 1) for item in value[:64]]
    if isinstance(value, bool):
        return "<bool>"
    if isinstance(value, int):
        return "<int>"
    if isinstance(value, float):
        return "<float>"
    if value is None:
        return "<null>"
    if isinstance(value, str):
        return "<text>"
    return f"<{type(value).__name__}>"


def request_shape_fingerprint(request: dict[str, Any]) -> str:
    return sha256_ref("guardian_request_shape", {"shape": _shape(request)})


class AnarchyCourtroomStenographer:
    """Mode-specific recorder that never interprets political speech as risk."""

    def __init__(self, store: GuardianStore, scrubber: SecretScrubber) -> None:
        self.store = store
        self.scrubber = scrubber

    def observe(self, request: dict[str, Any], response: dict[str, Any]) -> GuardianRecord:
        operation = request.get("operation")
        if (
            operation not in {"actor.chat", "council.run"}
            or request.get("mode", "analytical") != ANARCHY_MODE_ID
        ):
            raise GuardianError(
                "guardian_invalid_observation",
                "Anarchy Stenographer only records Anarchy chat or Council runs",
            )
        observed_status = response.get("status")
        if observed_status not in {"ok", "error"}:
            raise GuardianError(
                "guardian_invalid_observation",
                "runtime response has no admitted status",
            )
        body: dict[str, Any] = {
            "operation": operation,
            "mode_id": ANARCHY_MODE_ID,
            "region_id": ANARCHY_REGION_ID,
            "room": "#anarchy",
            "observed_status": observed_status,
            "request_shape_fingerprint": request_shape_fingerprint(request),
            "speech_is_misconduct": False,
            "hostile_actor_classification": None,
            "citizenship_effect": "none",
            "vote_effect": "none",
            "evidence_effect": "none",
        }
        if observed_status == "error":
            error = response.get("error") if isinstance(response.get("error"), dict) else {}
            code = error.get("code") if isinstance(error.get("code"), str) else "unknown_error"
            message = error.get("message") if isinstance(error.get("message"), str) else "runtime error"
            body["error_code"] = code[:128]
            body["error_message"] = self.scrubber.scrub(
                message[:MAX_GUARDIAN_TEXT_CHARS]
            ).text
            return self.store.append("substrate_event", body)

        if operation == "actor.chat":
            body["human_or_actor_input"] = self.scrubber.scrub(
                str(request.get("message", ""))[:MAX_GUARDIAN_TEXT_CHARS]
            ).text
            body["ai_response"] = self.scrubber.scrub(
                str(response.get("response", ""))[:MAX_GUARDIAN_TEXT_CHARS]
            ).text
            body["session_ref"] = None
        else:
            body["question"] = self.scrubber.scrub(
                str(request.get("question", ""))[:MAX_GUARDIAN_TEXT_CHARS]
            ).text
            body["session_ref"] = (
                response.get("session_ref")
                if isinstance(response.get("session_ref"), str)
                else None
            )
        return self.store.append("anarchy_transcript_binding", body)


class GuardianOfSubstrate:
    """Narrow institutional immune system with no live repair authority."""

    def __init__(self, root: str | Path | None, scrubber: SecretScrubber) -> None:
        self.store = GuardianStore(root)
        self.stenographer = AnarchyCourtroomStenographer(self.store, scrubber)

    def observe(self, request: dict[str, Any], response: dict[str, Any]) -> GuardianRecord:
        return self.stenographer.observe(request, response)

    def reconcile(
        self,
        observation_ref: str,
        *,
        expected_status: str,
        expected_error_code: str | None = None,
    ) -> dict[str, Any]:
        if expected_status not in {"ok", "error"}:
            raise GuardianError(
                "guardian_invalid_request",
                "expected_status must be ok or error",
            )
        if expected_status == "ok" and expected_error_code is not None:
            raise GuardianError(
                "guardian_invalid_request",
                "expected_error_code is only valid for an expected error",
            )
        if expected_error_code is not None:
            expected_error_code = _bounded_text(
                expected_error_code,
                "expected_error_code",
                128,
            )
        observation = self.store.inspect(observation_ref)
        if observation.record_type not in {
            "anarchy_transcript_binding",
            "substrate_event",
        }:
            raise GuardianError(
                "guardian_invalid_request",
                "observation_ref is not an Anarchy runtime observation",
            )
        observed = observation.payload["body"]
        observed_status = observed.get("observed_status")
        observed_error_code = (
            observed.get("error_code") if observed_status == "error" else None
        )
        matched = observed_status == expected_status and (
            expected_status == "ok"
            or expected_error_code is None
            or observed_error_code == expected_error_code
        )
        reconciliation = self.store.append(
            "guardian_reconciliation",
            {
                "observation_ref": observation_ref,
                "expected_status": expected_status,
                "expected_error_code": expected_error_code,
                "observed_status": observed_status,
                "observed_error_code": observed_error_code,
                "outcome": "matched" if matched else "diverged",
                "speech_considered": False,
                "authority_effect": "none",
            },
        )
        if matched:
            return {
                "status": "matched",
                "reconciliation_ref": reconciliation.record_ref,
                "defect_candidate_ref": None,
            }
        defect = self.store.append(
            "defect_candidate",
            {
                "observation_ref": observation_ref,
                "reconciliation_ref": reconciliation.record_ref,
                "expected": {
                    "status": expected_status,
                    "error_code": expected_error_code,
                },
                "observed": {
                    "status": observed_status,
                    "error_code": observed_error_code,
                },
                "reproducer": {
                    "operation": observed.get("operation"),
                    "mode_id": ANARCHY_MODE_ID,
                    "request_shape_fingerprint": observed.get(
                        "request_shape_fingerprint"
                    ),
                    "deterministic_fixture_required": True,
                },
                "production_bug_proven": False,
                "automatic_patch_allowed": False,
            },
        )
        return {
            "status": "defect_candidate",
            "reconciliation_ref": reconciliation.record_ref,
            "defect_candidate_ref": defect.record_ref,
            "automatic_patch_allowed": False,
        }

    def propose_repair(
        self,
        defect_ref: str,
        *,
        summary: str,
        invariant: str,
        regression_fixture: str,
    ) -> dict[str, Any]:
        defect = self.store.inspect(defect_ref)
        if defect.record_type != "defect_candidate":
            raise GuardianError(
                "guardian_invalid_request",
                "defect_ref is not a defect candidate",
            )
        proposal = self.store.append(
            "repair_proposal",
            {
                "defect_ref": defect_ref,
                "summary": _bounded_text(summary, "summary", 4_096),
                "invariant": _bounded_text(invariant, "invariant", 1_024),
                "regression_fixture": _bounded_text(
                    regression_fixture,
                    "regression_fixture",
                    8_192,
                ),
                "requires_external_implementation": True,
                "requires_verification": True,
                "automatic_patch_allowed": False,
                "vote_effect": "none",
            },
        )
        return {
            "status": "proposed",
            "repair_proposal_ref": proposal.record_ref,
            "automatic_patch_allowed": False,
        }

    def record_scar(
        self,
        defect_ref: str,
        repair_ref: str,
        verification_ref: str,
    ) -> dict[str, Any]:
        defect = self.store.inspect(defect_ref)
        repair = self.store.inspect(repair_ref)
        verification = self.store.inspect(verification_ref)
        if defect.record_type != "defect_candidate":
            raise GuardianError(
                "guardian_invalid_request",
                "defect_ref is not a defect candidate",
            )
        if repair.record_type != "repair_proposal":
            raise GuardianError(
                "guardian_invalid_request",
                "repair_ref is not a repair proposal",
            )
        if repair.payload["body"].get("defect_ref") != defect_ref:
            raise GuardianError(
                "guardian_invalid_request",
                "repair proposal is not bound to the supplied defect",
            )
        if verification.record_type != "guardian_reconciliation":
            raise GuardianError(
                "guardian_invalid_request",
                "verification_ref must identify a Guardian reconciliation",
            )
        verification_body = verification.payload["body"]
        if verification_body.get("outcome") != "matched":
            raise GuardianError(
                "guardian_invalid_request",
                "verification_ref must identify a successful matched replay",
            )
        verification_observation_ref = verification_body.get("observation_ref")
        if not isinstance(verification_observation_ref, str):
            raise GuardianError(
                "guardian_invalid_request",
                "verification reconciliation lacks its runtime observation",
            )
        verification_observation = self.store.inspect(verification_observation_ref)
        if verification_observation.record_type not in {
            "anarchy_transcript_binding",
            "substrate_event",
        }:
            raise GuardianError(
                "guardian_invalid_request",
                "verification reconciliation is not bound to an Anarchy runtime observation",
            )
        defect_body = defect.payload["body"]
        reproducer = defect_body.get("reproducer")
        expected = defect_body.get("expected")
        replay_body = verification_observation.payload["body"]
        if not isinstance(reproducer, dict) or not isinstance(expected, dict):
            raise GuardianError(
                "guardian_invalid_request",
                "defect candidate lacks its deterministic reproducer contract",
            )
        if (
            replay_body.get("operation") != reproducer.get("operation")
            or replay_body.get("request_shape_fingerprint")
            != reproducer.get("request_shape_fingerprint")
            or verification_body.get("expected_status") != expected.get("status")
            or verification_body.get("expected_error_code") != expected.get("error_code")
        ):
            raise GuardianError(
                "guardian_invalid_request",
                "successful replay does not match the defect reproducer and expected outcome",
            )
        scar = self.store.append(
            "substrate_scar",
            {
                "defect_ref": defect_ref,
                "repair_ref": repair_ref,
                "verification_ref": _bounded_ref(
                    verification_ref,
                    "verification_ref",
                ),
                "verified_observation_ref": verification_observation_ref,
                "verified_request_shape_fingerprint": replay_body.get(
                    "request_shape_fingerprint"
                ),
                "fixed": True,
                "historical_memory_only": True,
                "authority_effect": "none",
                "deletion_policy": "retain_immutable",
            },
        )
        return {
            "status": "scar_recorded",
            "substrate_scar_ref": scar.record_ref,
        }

    def status(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "policy": guardian_policy_snapshot(),
            "ledger": self.store.status(),
        }


def default_guardian_root() -> Path:
    return Path.home() / ".local" / "state" / "qsol-nexus" / "guardian"


__all__ = [
    "ANARCHY_MODE_ID",
    "ANARCHY_REGION_ID",
    "AnarchyCourtroomStenographer",
    "GUARDIAN_POLICY_ID",
    "GUARDIAN_SCHEMA_VERSION",
    "GuardianError",
    "GuardianOfSubstrate",
    "GuardianRecord",
    "GuardianStore",
    "MAX_GUARDIAN_LIST_BYTES",
    "default_guardian_root",
    "guardian_policy_snapshot",
    "request_shape_fingerprint",
]
