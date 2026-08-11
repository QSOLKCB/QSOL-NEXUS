from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
import copy
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import threading
from typing import Any, Iterator, Sequence

from .canonical import canonical_json, sha256_ref
from .world import WorldObject, WorldStore


CONTINUITY_SCHEMA_VERSION = "nexus-world-continuity/1"
CONTINUITY_HEAD_SCHEMA = "nexus-world-continuity-head/1"
ARK_SCHEMA_VERSION = "nexus-world-ark/1"
MIGRATION_SCHEMA_VERSION = "nexus-world-format-migration/1"
CONTINUITY_POLICY_ID = "nexus-worldstore-continuity-ark-v1"
MIGRATION_OBJECT_TYPE = "world_format_migration_receipt"
CONTINUITY_RESERVED_OBJECT_TYPES = frozenset({MIGRATION_OBJECT_TYPE})

_MANIFEST_REF = re.compile(r"^world-manifest:[0-9a-f]{64}$")
_OBJECT_REF = re.compile(r"^object:[0-9a-f]{64}$")
_ARK_REF = re.compile(r"^world-ark:[0-9a-f]{64}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class WorldContinuityError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ReplicaState:
    replica_id: str
    root: Path
    failure_domain: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "replica_id": self.replica_id,
            "path": str(self.root),
            "failure_domain": self.failure_domain,
        }


@dataclass(frozen=True)
class _Replica:
    state: ReplicaState
    store: WorldStore


def continuity_policy_snapshot() -> dict[str, Any]:
    return {
        "schema_version": CONTINUITY_SCHEMA_VERSION,
        "policy_id": CONTINUITY_POLICY_ID,
        "object_identity": "existing object:<sha256> references remain unchanged",
        "recognized_history_rule": "verified majority quorum selects the continuity head; recency alone has no authority",
        "repair_rule": "repair only from a content-address-verified source already bound by recognized history",
        "ambiguity_rule": "existing continuity metadata without one recognized HEAD quorum fails closed and is never re-baselined",
        "index_rule": "mutable HEAD files are reconstructible pointers, never historical authority by themselves",
        "ark_rule": "Arks are cold self-describing snapshots, path-confined, chain-inventory exact, and restore only into a new target",
        "migration_rule": "source bytes and object refs remain preserved; alternate digests are additive receipts",
        "guardian_rule": "continuity may emit verified repair receipts for Guardian scars; Guardian has no storage authority",
        "degraded_rule": "a degraded store may become read-only rather than invent history",
        "publication_rule": "failed HEAD publication rolls back to the previously recognized quorum",
        "authority_effect": "none",
    }


class ContinuityWorldStore(WorldStore):
    """Content-addressed WorldStore with quorum continuity and cold Arks."""

    def __init__(
        self,
        root: str | Path | None = None,
        *,
        replica_roots: Sequence[str | Path] = (),
        write_quorum: int | None = None,
    ) -> None:
        self._continuity_thread_lock = threading.RLock()
        self._history_cache_head: str | None = None
        self._history_cache_objects: frozenset[str] = frozenset()
        self._history_cache_manifests: tuple[str, ...] = ()

        if root is None:
            if replica_roots:
                raise WorldContinuityError(
                    "world_continuity_requires_primary",
                    "replicas require a persistent primary WorldStore root",
                )
            super().__init__(None)
            self._replicas: list[_Replica] = []
            self.write_quorum = 1
            return

        primary = Path(root).absolute()
        replica_paths = [Path(item).absolute() for item in replica_roots]
        roots = [primary, *replica_paths]
        self._validate_replica_roots(roots)

        continuity_preexisting = any(
            (item / "continuity").exists() or (item / "continuity").is_symlink()
            for item in roots
        )

        super().__init__(primary)
        stores: list[WorldStore] = [self]
        stores.extend(WorldStore(item) for item in replica_paths)
        self._replicas = []
        for index, (replica_root, store) in enumerate(zip(roots, stores, strict=True)):
            try:
                domain = f"device:{replica_root.stat().st_dev}"
            except OSError:
                domain = f"path:{replica_root}"
            state = ReplicaState(
                "primary" if index == 0 else f"replica-{index}",
                replica_root,
                domain,
            )
            self._prepare_continuity_root(replica_root)
            self._replicas.append(_Replica(state, store))

        majority = len(self._replicas) // 2 + 1
        selected_quorum = majority if write_quorum is None else write_quorum
        if type(selected_quorum) is not int or not majority <= selected_quorum <= len(self._replicas):
            raise WorldContinuityError(
                "world_continuity_invalid_quorum",
                f"write_quorum must be a strict majority between {majority} and {len(self._replicas)}",
            )
        self.write_quorum = selected_quorum

        with self._locked_continuity():
            observations = self._head_observations()
            if not any(value is not None for value in observations.values()):
                if continuity_preexisting:
                    raise WorldContinuityError(
                        "world_continuity_no_quorum",
                        "continuity metadata already exists but no verified HEAD quorum remains",
                    )
                self._bootstrap_legacy_world()
            else:
                self._resolve_head(require_chain=True)

    @staticmethod
    def _validate_replica_roots(roots: list[Path]) -> None:
        resolved: list[Path] = []
        for root in roots:
            if root.is_symlink():
                raise WorldContinuityError(
                    "world_continuity_unsafe_replica",
                    "WorldStore replica roots must not be symbolic links",
                )
            try:
                candidate = root.resolve()
            except (OSError, RuntimeError) as exc:
                raise WorldContinuityError(
                    "world_continuity_unsafe_replica",
                    "WorldStore replica roots could not be resolved safely",
                ) from exc
            for previous in resolved:
                if (
                    candidate == previous
                    or candidate.is_relative_to(previous)
                    or previous.is_relative_to(candidate)
                ):
                    raise WorldContinuityError(
                        "world_continuity_overlapping_replicas",
                        "WorldStore replica roots must be disjoint",
                    )
            resolved.append(candidate)

    @staticmethod
    def _prepare_continuity_root(root: Path) -> None:
        continuity = root / "continuity"
        manifests = continuity / "manifests"
        repairs = continuity / "repairs"
        for path in (continuity, manifests, repairs):
            if path.is_symlink() or (path.exists() and not path.is_dir()):
                raise WorldContinuityError(
                    "world_continuity_unsafe_storage",
                    "continuity storage must be private directories",
                )
            path.mkdir(mode=0o700, parents=True, exist_ok=True)
            if os.name != "nt":
                path.chmod(0o700)

    @property
    def continuity_dir(self) -> Path | None:
        return None if self.root is None else self.root / "continuity"

    @property
    def continuity_lock_path(self) -> Path | None:
        return None if self.continuity_dir is None else self.continuity_dir / "continuity.lock"

    @contextmanager
    def _locked_continuity(self) -> Iterator[None]:
        with self._continuity_thread_lock:
            if self.continuity_lock_path is None:
                yield
                return
            descriptor: int | None = None
            try:
                path = self.continuity_lock_path
                if path.is_symlink():
                    raise WorldContinuityError(
                        "world_continuity_lock_unavailable",
                        "continuity lock must not be a symbolic link",
                    )
                flags = os.O_RDWR | os.O_CREAT
                flags |= getattr(os, "O_CLOEXEC", 0)
                flags |= getattr(os, "O_NOFOLLOW", 0)
                flags |= getattr(os, "O_BINARY", 0)
                descriptor = os.open(path, flags, 0o600)
                info = os.fstat(descriptor)
                if not stat.S_ISREG(info.st_mode) or (
                    os.name != "nt" and stat.S_IMODE(info.st_mode) & 0o077
                ):
                    raise WorldContinuityError(
                        "world_continuity_lock_unavailable",
                        "continuity lock must be an owner-only regular file",
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
            except WorldContinuityError:
                raise
            except OSError as exc:
                raise WorldContinuityError(
                    "world_continuity_lock_unavailable",
                    "continuity lock could not be acquired",
                ) from exc
            finally:
                if descriptor is not None:
                    try:
                        os.close(descriptor)
                    except OSError:
                        pass

    @staticmethod
    def _manifest_path(root: Path, manifest_ref: str) -> Path:
        digest = manifest_ref.removeprefix("world-manifest:")
        return root / "continuity" / "manifests" / f"{digest}.json"

    @staticmethod
    def _head_path(root: Path) -> Path:
        return root / "continuity" / "HEAD.json"

    @staticmethod
    def _repair_path(root: Path, repair_ref: str) -> Path:
        digest = repair_ref.removeprefix("world-repair:")
        return root / "continuity" / "repairs" / f"{digest}.json"

    @staticmethod
    def _write_immutable(path: Path, raw: dict[str, Any]) -> None:
        encoded = (canonical_json(raw) + "\n").encode("utf-8")
        if path.is_symlink():
            raise WorldContinuityError(
                "world_continuity_unsafe_storage",
                "immutable continuity records must not be symbolic links",
            )
        if path.exists():
            if not path.is_file() or path.read_bytes() != encoded:
                raise WorldContinuityError(
                    "world_continuity_conflict",
                    "immutable continuity record already exists with different bytes",
                )
            return
        temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}-{threading.get_ident()}")
        descriptor: int | None = None
        try:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            flags |= getattr(os, "O_CLOEXEC", 0)
            flags |= getattr(os, "O_NOFOLLOW", 0)
            flags |= getattr(os, "O_BINARY", 0)
            descriptor = os.open(temporary, flags, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                descriptor = None
                if os.name != "nt":
                    os.fchmod(handle.fileno(), 0o600)
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError:
                if not path.is_file() or path.read_bytes() != encoded:
                    raise WorldContinuityError(
                        "world_continuity_conflict",
                        "immutable continuity record raced with different bytes",
                    )
            if os.name != "nt" and path.exists():
                path.chmod(0o600)
        finally:
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    @staticmethod
    def _write_head(root: Path, manifest_ref: str) -> None:
        raw = {"schema_version": CONTINUITY_HEAD_SCHEMA, "manifest_ref": manifest_ref}
        target = ContinuityWorldStore._head_path(root)
        if target.is_symlink():
            raise WorldContinuityError(
                "world_continuity_unsafe_storage",
                "continuity HEAD must not be a symbolic link",
            )
        temporary = target.with_name(f".HEAD.tmp-{os.getpid()}-{threading.get_ident()}")
        encoded = (canonical_json(raw) + "\n").encode("utf-8")
        descriptor: int | None = None
        try:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            flags |= getattr(os, "O_CLOEXEC", 0)
            flags |= getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(temporary, flags, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                descriptor = None
                if os.name != "nt":
                    os.fchmod(handle.fileno(), 0o600)
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
            if os.name != "nt":
                target.chmod(0o600)
        finally:
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    @staticmethod
    def _remove_head(root: Path) -> None:
        target = ContinuityWorldStore._head_path(root)
        if target.is_symlink():
            raise WorldContinuityError(
                "world_continuity_unsafe_storage",
                "continuity HEAD must not be a symbolic link",
            )
        if target.exists():
            if not target.is_file():
                raise WorldContinuityError(
                    "world_continuity_unsafe_storage",
                    "continuity HEAD must be a regular file",
                )
            target.unlink()

    @staticmethod
    def _read_canonical(path: Path) -> dict[str, Any]:
        if path.is_symlink():
            raise WorldContinuityError(
                "world_continuity_unsafe_storage",
                "continuity record must not be a symbolic link",
            )
        descriptor: int | None = None
        try:
            flags = os.O_RDONLY
            flags |= getattr(os, "O_CLOEXEC", 0)
            flags |= getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(path, flags)
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode):
                raise WorldContinuityError(
                    "world_continuity_corrupt",
                    "continuity record must be a regular file",
                )
            if os.name != "nt" and stat.S_IMODE(info.st_mode) & 0o077:
                raise WorldContinuityError(
                    "world_continuity_corrupt",
                    "continuity record permissions must be owner-only",
                )
            with os.fdopen(descriptor, "rb") as handle:
                descriptor = None
                encoded = handle.read()
            raw = json.loads(encoded.decode("utf-8"))
            if not isinstance(raw, dict):
                raise WorldContinuityError(
                    "world_continuity_corrupt",
                    "continuity record must be a JSON object",
                )
            expected = (canonical_json(raw) + "\n").encode("utf-8")
            if encoded != expected:
                raise WorldContinuityError(
                    "world_continuity_corrupt",
                    "continuity record is not canonical JSON",
                )
            return raw
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
            raise WorldContinuityError(
                "world_continuity_corrupt",
                "continuity record cannot be decoded",
            ) from exc
        finally:
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass

    @classmethod
    def _validate_manifest(cls, raw: dict[str, Any], expected_ref: str) -> dict[str, Any]:
        body_fields = {
            "schema_version",
            "generation",
            "previous_manifest_ref",
            "event_type",
            "inventory_refs",
            "object_ref",
            "write_quorum",
            "replica_ids",
            "digest_policy",
            "authority_effect",
        }
        if set(raw) != body_fields | {"manifest_ref"}:
            raise WorldContinuityError(
                "world_continuity_corrupt",
                "continuity manifest schema is invalid",
            )
        body = {key: raw[key] for key in body_fields}
        manifest_ref = sha256_ref("world-manifest", body)
        if raw.get("manifest_ref") != expected_ref or manifest_ref != expected_ref:
            raise WorldContinuityError(
                "world_continuity_corrupt",
                "continuity manifest failed content-address verification",
            )
        if raw.get("schema_version") != CONTINUITY_SCHEMA_VERSION:
            raise WorldContinuityError(
                "world_continuity_corrupt",
                "continuity manifest schema version is invalid",
            )
        generation = raw.get("generation")
        if type(generation) is not int or generation < 0:
            raise WorldContinuityError(
                "world_continuity_corrupt",
                "continuity manifest generation is invalid",
            )
        previous = raw.get("previous_manifest_ref")
        if previous is not None and (
            not isinstance(previous, str) or _MANIFEST_REF.fullmatch(previous) is None
        ):
            raise WorldContinuityError(
                "world_continuity_corrupt",
                "continuity manifest predecessor is invalid",
            )
        event_type = raw.get("event_type")
        if event_type not in {"legacy_baseline", "object_commit"}:
            raise WorldContinuityError(
                "world_continuity_corrupt",
                "continuity manifest event type is invalid",
            )
        inventory = raw.get("inventory_refs")
        if (
            not isinstance(inventory, list)
            or inventory != sorted(set(inventory))
            or any(
                not isinstance(item, str) or _OBJECT_REF.fullmatch(item) is None
                for item in inventory
            )
        ):
            raise WorldContinuityError(
                "world_continuity_corrupt",
                "continuity manifest inventory is invalid",
            )
        object_ref = raw.get("object_ref")
        if object_ref is not None and (
            not isinstance(object_ref, str) or _OBJECT_REF.fullmatch(object_ref) is None
        ):
            raise WorldContinuityError(
                "world_continuity_corrupt",
                "continuity manifest object ref is invalid",
            )
        replica_ids = raw.get("replica_ids")
        quorum = raw.get("write_quorum")
        if (
            not isinstance(replica_ids, list)
            or not replica_ids
            or any(not isinstance(item, str) or not item for item in replica_ids)
            or len(set(replica_ids)) != len(replica_ids)
            or type(quorum) is not int
            or not (len(replica_ids) // 2 + 1) <= quorum <= len(replica_ids)
        ):
            raise WorldContinuityError(
                "world_continuity_corrupt",
                "continuity manifest quorum metadata is invalid",
            )
        if raw.get("authority_effect") != "none":
            raise WorldContinuityError(
                "world_continuity_corrupt",
                "continuity manifest authority envelope is invalid",
            )
        if event_type == "legacy_baseline":
            if generation != 0 or previous is not None or object_ref is not None:
                raise WorldContinuityError(
                    "world_continuity_corrupt",
                    "legacy baseline manifest is structurally invalid",
                )
        elif (
            generation < 1
            or previous is None
            or inventory != []
            or object_ref is None
        ):
            raise WorldContinuityError(
                "world_continuity_corrupt",
                "object commit manifest is structurally invalid",
            )
        return raw

    @classmethod
    def _read_manifest(cls, root: Path, manifest_ref: str) -> dict[str, Any]:
        if not isinstance(manifest_ref, str) or _MANIFEST_REF.fullmatch(manifest_ref) is None:
            raise WorldContinuityError(
                "world_continuity_corrupt",
                "continuity manifest ref is invalid",
            )
        raw = cls._read_canonical(cls._manifest_path(root, manifest_ref))
        return cls._validate_manifest(raw, manifest_ref)

    @classmethod
    def _read_head(cls, root: Path) -> str | None:
        path = cls._head_path(root)
        if path.is_symlink():
            raise WorldContinuityError(
                "world_continuity_corrupt",
                "continuity HEAD must not be a symbolic link",
            )
        if not path.exists():
            return None
        raw = cls._read_canonical(path)
        if (
            set(raw) != {"schema_version", "manifest_ref"}
            or raw.get("schema_version") != CONTINUITY_HEAD_SCHEMA
        ):
            raise WorldContinuityError(
                "world_continuity_corrupt",
                "continuity HEAD schema is invalid",
            )
        ref = raw.get("manifest_ref")
        if not isinstance(ref, str) or _MANIFEST_REF.fullmatch(ref) is None:
            raise WorldContinuityError(
                "world_continuity_corrupt",
                "continuity HEAD ref is invalid",
            )
        cls._read_manifest(root, ref)
        return ref

    def _head_observations(self) -> dict[str, str | None]:
        observations: dict[str, str | None] = {}
        for replica in self._replicas:
            try:
                observations[replica.state.replica_id] = self._read_head(replica.state.root)
            except (OSError, WorldContinuityError):
                observations[replica.state.replica_id] = None
        return observations

    def _manifest_sources(self, manifest_ref: str) -> list[_Replica]:
        sources: list[_Replica] = []
        for replica in self._replicas:
            try:
                self._read_manifest(replica.state.root, manifest_ref)
            except (OSError, WorldContinuityError):
                continue
            sources.append(replica)
        return sources

    def _resolve_head(
        self,
        *,
        require_chain: bool,
        require_manifest_quorum: bool = False,
    ) -> tuple[str, dict[str, Any]]:
        observations = self._head_observations()
        counts = Counter(value for value in observations.values() if value is not None)
        candidates = [ref for ref, count in counts.items() if count >= self.write_quorum]
        if len(candidates) != 1:
            raise WorldContinuityError(
                "world_continuity_no_quorum",
                "replica HEADs do not contain one verified majority history",
            )
        head_ref = candidates[0]
        sources = self._manifest_sources(head_ref)
        if len(sources) < self.write_quorum:
            raise WorldContinuityError(
                "world_continuity_no_quorum",
                "recognized continuity HEAD lacks a manifest quorum",
            )
        manifest = self._read_manifest(sources[0].state.root, head_ref)
        if require_chain:
            self._history(head_ref, require_manifest_quorum=require_manifest_quorum)
        return head_ref, manifest

    def _history(
        self,
        head_ref: str,
        *,
        require_manifest_quorum: bool = False,
    ) -> tuple[frozenset[str], tuple[str, ...]]:
        # Never trust the cached predecessor chain for a new read or mutation.
        # The cache is only a published snapshot for diagnostics; every call
        # below revalidates all manifest links from disk.
        newest: list[tuple[str, dict[str, Any]]] = []
        seen: set[str] = set()
        cursor: str | None = head_ref
        while cursor is not None:
            if cursor in seen:
                raise WorldContinuityError(
                    "world_continuity_corrupt",
                    "continuity manifest chain contains a cycle",
                )
            seen.add(cursor)
            sources = self._manifest_sources(cursor)
            if not sources:
                raise WorldContinuityError(
                    "world_continuity_corrupt",
                    "continuity manifest chain has no verified source",
                )
            if require_manifest_quorum and len(sources) < self.write_quorum:
                raise WorldContinuityError(
                    "world_continuity_degraded_read_only",
                    "continuity predecessor manifest no longer has a verified quorum",
                )
            raw = self._read_manifest(sources[0].state.root, cursor)
            newest.append((cursor, raw))
            cursor = raw["previous_manifest_ref"]

        ordered = list(reversed(newest))
        if not ordered or ordered[0][1]["event_type"] != "legacy_baseline":
            raise WorldContinuityError(
                "world_continuity_corrupt",
                "continuity history has no baseline",
            )
        objects: set[str] = set(ordered[0][1]["inventory_refs"])
        previous_ref: str | None = None
        for expected_generation, (ref, raw) in enumerate(ordered):
            if (
                raw["generation"] != expected_generation
                or raw["previous_manifest_ref"] != previous_ref
            ):
                raise WorldContinuityError(
                    "world_continuity_corrupt",
                    "continuity history contains a gap or fork",
                )
            if raw["event_type"] == "object_commit":
                objects.add(raw["object_ref"])
            previous_ref = ref

        self._history_cache_head = head_ref
        self._history_cache_objects = frozenset(objects)
        self._history_cache_manifests = tuple(ref for ref, _ in ordered)
        return self._history_cache_objects, self._history_cache_manifests

    def _scan_primary_objects(self) -> list[str]:
        if self.objects_dir is None:
            return []
        refs: list[str] = []
        for path in sorted(self.objects_dir.glob("*.json"), key=lambda item: item.name):
            ref = f"object:{path.stem}"
            WorldStore._read_validated(ref, path)
            refs.append(ref)
        return refs

    @staticmethod
    def _base_create(
        store: WorldStore,
        object_type: str,
        payload: dict[str, Any],
        provenance: dict[str, Any] | None,
    ) -> WorldObject:
        if isinstance(store, ContinuityWorldStore):
            return WorldStore.create_object(store, object_type, payload, provenance)
        return store.create_object(object_type, payload, provenance)

    @staticmethod
    def _base_disk_inspect(store: WorldStore, object_ref: str) -> WorldObject:
        if store.objects_dir is None:
            return WorldStore.inspect(store, object_ref)
        digest = object_ref.removeprefix("object:")
        path = store.objects_dir / f"{digest}.json"
        if not path.exists() or path.is_symlink():
            raise KeyError(object_ref)
        return WorldStore._read_validated(object_ref, path)

    def _copy_object_to_replica(self, source: WorldObject, replica: _Replica) -> WorldObject:
        try:
            return self._base_create(
                replica.store,
                source.object_type,
                source.payload,
                source.provenance,
            )
        except (OSError, ValueError) as exc:
            raise WorldContinuityError(
                "world_continuity_replica_write_failed",
                f"replica {replica.state.replica_id} could not persist an object",
            ) from exc

    def _bootstrap_legacy_world(self) -> None:
        inventory = sorted(self._scan_primary_objects())
        for object_ref in inventory:
            source = self._base_disk_inspect(self, object_ref)
            successes = 0
            for replica in self._replicas:
                try:
                    current = self._base_disk_inspect(replica.store, object_ref)
                    if current.as_dict() == source.as_dict():
                        successes += 1
                        continue
                except (KeyError, OSError, ValueError):
                    pass
                try:
                    self._copy_object_to_replica(source, replica)
                    successes += 1
                except WorldContinuityError:
                    continue
            if successes < self.write_quorum:
                raise WorldContinuityError(
                    "world_continuity_bootstrap_quorum_unavailable",
                    "legacy WorldStore could not be replicated to the configured quorum",
                )

        body = {
            "schema_version": CONTINUITY_SCHEMA_VERSION,
            "generation": 0,
            "previous_manifest_ref": None,
            "event_type": "legacy_baseline",
            "inventory_refs": inventory,
            "object_ref": None,
            "write_quorum": self.write_quorum,
            "replica_ids": [item.state.replica_id for item in self._replicas],
            "digest_policy": {"object_identity": "sha256", "continuity_identity": "sha256"},
            "authority_effect": "none",
        }
        manifest_ref = sha256_ref("world-manifest", body)
        self._commit_manifest(
            {"manifest_ref": manifest_ref, **body},
            previous_head_ref=None,
        )
        self._history_cache_head = None

    def _rollback_head_publication(
        self,
        changed: list[_Replica],
        previous_head_ref: str | None,
    ) -> None:
        rollback_errors = 0
        for replica in changed:
            try:
                if previous_head_ref is None:
                    self._remove_head(replica.state.root)
                else:
                    self._write_head(replica.state.root, previous_head_ref)
            except (OSError, WorldContinuityError):
                rollback_errors += 1

        if previous_head_ref is not None:
            observations = self._head_observations()
            support = sum(value == previous_head_ref for value in observations.values())
            if support < self.write_quorum:
                raise WorldContinuityError(
                    "world_continuity_head_rollback_failed",
                    "failed HEAD publication also failed to restore the previously recognized quorum",
                )
        elif rollback_errors:
            observations = self._head_observations()
            counts = Counter(value for value in observations.values() if value is not None)
            if any(count >= self.write_quorum for count in counts.values()):
                raise WorldContinuityError(
                    "world_continuity_head_rollback_failed",
                    "failed baseline publication left an unexpected recognized HEAD",
                )

    def _commit_manifest(
        self,
        raw: dict[str, Any],
        *,
        previous_head_ref: str | None,
    ) -> str:
        manifest_ref = raw["manifest_ref"]
        manifest_successes: list[_Replica] = []
        for replica in self._replicas:
            try:
                self._write_immutable(
                    self._manifest_path(replica.state.root, manifest_ref),
                    raw,
                )
                manifest_successes.append(replica)
            except (OSError, WorldContinuityError):
                continue
        if len(manifest_successes) < self.write_quorum:
            raise WorldContinuityError(
                "world_continuity_manifest_quorum_unavailable",
                "continuity manifest could not reach the configured quorum",
            )

        changed: list[_Replica] = []
        for replica in manifest_successes:
            try:
                self._write_head(replica.state.root, manifest_ref)
                changed.append(replica)
            except (OSError, WorldContinuityError):
                continue
        if len(changed) < self.write_quorum:
            self._rollback_head_publication(changed, previous_head_ref)
            raise WorldContinuityError(
                "world_continuity_head_quorum_unavailable",
                "continuity HEAD could not reach the configured quorum; previous quorum was restored",
            )
        self._history_cache_head = None
        return manifest_ref

    def _assert_write_ready(self, head_ref: str) -> None:
        objects, _ = self._history(head_ref, require_manifest_quorum=True)
        for object_ref in objects:
            if len(self._valid_object_sources(object_ref)) < self.write_quorum:
                raise WorldContinuityError(
                    "world_continuity_degraded_read_only",
                    "recognized object redundancy is below quorum; repair before writing new history",
                )

    def create_object(
        self,
        object_type: str,
        payload: dict[str, Any],
        provenance: dict[str, Any] | None = None,
    ) -> WorldObject:
        if self.root is None:
            return WorldStore.create_object(self, object_type, payload, provenance)

        with self._locked_continuity():
            head_ref, head = self._resolve_head(require_chain=True)
            self._assert_write_ready(head_ref)
            successes: list[tuple[_Replica, WorldObject]] = []
            for replica in self._replicas:
                try:
                    obj = self._base_create(replica.store, object_type, payload, provenance)
                    successes.append((replica, obj))
                except (OSError, ValueError):
                    continue
            if len(successes) < self.write_quorum:
                raise WorldContinuityError(
                    "world_continuity_write_quorum_unavailable",
                    "object was not committed because the configured replica quorum was unavailable",
                )
            object_ids = {item.object_id for _, item in successes}
            if len(object_ids) != 1:
                raise WorldContinuityError(
                    "world_continuity_replica_divergence",
                    "replicas derived different content-addressed object identities",
                )
            obj = successes[0][1]
            body = {
                "schema_version": CONTINUITY_SCHEMA_VERSION,
                "generation": int(head["generation"]) + 1,
                "previous_manifest_ref": head_ref,
                "event_type": "object_commit",
                "inventory_refs": [],
                "object_ref": obj.object_id,
                "write_quorum": self.write_quorum,
                "replica_ids": [item.state.replica_id for item in self._replicas],
                "digest_policy": {"object_identity": "sha256", "continuity_identity": "sha256"},
                "authority_effect": "none",
            }
            manifest_ref = sha256_ref("world-manifest", body)
            self._commit_manifest(
                {"manifest_ref": manifest_ref, **body},
                previous_head_ref=head_ref,
            )
            self._objects[obj.object_id] = self._clone(obj)
            return self._clone(obj)

    def _valid_object_sources(self, object_ref: str) -> list[tuple[_Replica, WorldObject]]:
        valid: list[tuple[_Replica, WorldObject]] = []
        for replica in self._replicas:
            try:
                valid.append((replica, self._base_disk_inspect(replica.store, object_ref)))
            except (KeyError, OSError, ValueError):
                continue
        return valid

    def inspect(self, object_ref: str) -> WorldObject:
        self._validate_object_ref(object_ref)
        if self.root is None:
            return WorldStore.inspect(self, object_ref)
        with self._locked_continuity():
            head_ref, _ = self._resolve_head(require_chain=True)
            objects, _ = self._history(head_ref)
            if object_ref not in objects:
                raise KeyError(object_ref)
            valid = self._valid_object_sources(object_ref)
            if len(valid) < self.write_quorum:
                raise WorldContinuityError(
                    "world_continuity_read_quorum_unavailable",
                    "recognized object does not currently have a verified read quorum",
                )
            obj = valid[0][1]
            self._objects[object_ref] = self._clone(obj)
            return self._clone(obj)

    def _repair_object_file(self, source: WorldObject, replica: _Replica) -> None:
        assert replica.store.objects_dir is not None
        digest = source.object_id.removeprefix("object:")
        target = replica.store.objects_dir / f"{digest}.json"
        raw = (canonical_json(source.as_dict()) + "\n").encode("utf-8")
        temporary = target.with_name(f".{target.name}.repair-{os.getpid()}-{threading.get_ident()}")
        descriptor: int | None = None
        try:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            flags |= getattr(os, "O_CLOEXEC", 0)
            flags |= getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(temporary, flags, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                descriptor = None
                if os.name != "nt":
                    os.fchmod(handle.fileno(), 0o600)
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
            if target.is_symlink():
                raise WorldContinuityError(
                    "world_continuity_unsafe_storage",
                    "replica object path must not be a symbolic link",
                )
            if target.exists() and not target.is_file():
                raise WorldContinuityError(
                    "world_continuity_unsafe_storage",
                    "replica object path must be a regular file",
                )
            os.replace(temporary, target)
            if os.name != "nt":
                target.chmod(0o600)
            WorldStore._read_validated(source.object_id, target)
        finally:
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def _repair_manifest_file(
        self,
        manifest_ref: str,
        source_raw: dict[str, Any],
        replica: _Replica,
    ) -> None:
        path = self._manifest_path(replica.state.root, manifest_ref)
        if path.is_symlink():
            raise WorldContinuityError(
                "world_continuity_unsafe_storage",
                "replica manifest path must not be a symbolic link",
            )
        if path.exists():
            if not path.is_file():
                raise WorldContinuityError(
                    "world_continuity_unsafe_storage",
                    "replica manifest path must be a regular file",
                )
            path.unlink()
        self._write_immutable(path, source_raw)

    def _persist_repair_receipt(self, body: dict[str, Any]) -> str:
        repair_ref = sha256_ref("world-repair", body)
        raw = {"repair_ref": repair_ref, **body}
        successes = 0
        for replica in self._replicas:
            try:
                self._write_immutable(self._repair_path(replica.state.root, repair_ref), raw)
                successes += 1
            except (OSError, WorldContinuityError):
                continue
        if successes < self.write_quorum:
            raise WorldContinuityError(
                "world_continuity_repair_receipt_unavailable",
                "repair completed but its immutable receipt did not reach quorum",
            )
        return repair_ref

    def scrub(self, *, repair: bool = False) -> dict[str, Any]:
        if self.root is None:
            return {
                "status": "memory_only",
                "persistent": False,
                "repair": False,
                "defect_count": 0,
                "authority_effect": "none",
            }
        with self._locked_continuity():
            head_ref, head = self._resolve_head(require_chain=True)
            object_refs, manifest_refs = self._history(head_ref)
            defects: list[dict[str, str]] = []
            repairs: list[dict[str, str]] = []
            unrecoverable: list[str] = []

            for manifest_ref in manifest_refs:
                sources = self._manifest_sources(manifest_ref)
                if not sources:
                    unrecoverable.append(manifest_ref)
                    continue
                source_raw = self._read_manifest(sources[0].state.root, manifest_ref)
                valid_ids = {item.state.replica_id for item in sources}
                for replica in self._replicas:
                    if replica.state.replica_id in valid_ids:
                        continue
                    defects.append(
                        {"kind": "manifest", "ref": manifest_ref, "replica_id": replica.state.replica_id}
                    )
                    if repair:
                        self._repair_manifest_file(manifest_ref, source_raw, replica)
                        repairs.append(defects[-1])

            for object_ref in sorted(object_refs):
                sources = self._valid_object_sources(object_ref)
                if not sources:
                    unrecoverable.append(object_ref)
                    continue
                source_obj = sources[0][1]
                valid_ids = {item.state.replica_id for item, _ in sources}
                for replica in self._replicas:
                    if replica.state.replica_id in valid_ids:
                        continue
                    defects.append(
                        {"kind": "object", "ref": object_ref, "replica_id": replica.state.replica_id}
                    )
                    if repair:
                        self._repair_object_file(source_obj, replica)
                        repairs.append(defects[-1])

            observations = self._head_observations()
            for replica in self._replicas:
                if observations.get(replica.state.replica_id) == head_ref:
                    continue
                defects.append(
                    {"kind": "head", "ref": head_ref, "replica_id": replica.state.replica_id}
                )
                if repair:
                    self._write_head(replica.state.root, head_ref)
                    repairs.append(defects[-1])

            if unrecoverable:
                return {
                    "status": "unrecoverable",
                    "head_ref": head_ref,
                    "generation": head["generation"],
                    "unrecoverable_refs": sorted(unrecoverable),
                    "defect_count": len(defects),
                    "defects": defects,
                    "repair_count": len(repairs),
                    "repairs": repairs,
                    "repair_receipt_ref": None,
                    "guardian_scar_eligible": False,
                    "authority_effect": "none",
                }

            audit_gap: dict[str, str] | None = None
            repair_ref: str | None = None
            if repair and repairs:
                for manifest_ref in manifest_refs:
                    if len(self._manifest_sources(manifest_ref)) < self.write_quorum:
                        raise WorldContinuityError(
                            "world_continuity_repair_verification_failed",
                            "repair did not restore the configured manifest quorum",
                        )
                for object_ref in object_refs:
                    if len(self._valid_object_sources(object_ref)) < self.write_quorum:
                        raise WorldContinuityError(
                            "world_continuity_repair_verification_failed",
                            "repair did not restore the configured object quorum",
                        )
                observations = self._head_observations()
                if sum(value == head_ref for value in observations.values()) < self.write_quorum:
                    raise WorldContinuityError(
                        "world_continuity_repair_verification_failed",
                        "repair did not restore the configured HEAD quorum",
                    )
                self._resolve_head(require_chain=True, require_manifest_quorum=True)
                receipt_body = {
                    "schema_version": CONTINUITY_SCHEMA_VERSION,
                    "head_ref": head_ref,
                    "generation": head["generation"],
                    "repairs": repairs,
                    "verification": "content_addressed_source_revalidated_after_atomic_replace",
                    "guardian_scar_eligible": True,
                    "authority_effect": "none",
                }
                try:
                    repair_ref = self._persist_repair_receipt(receipt_body)
                except WorldContinuityError as exc:
                    if exc.code != "world_continuity_repair_receipt_unavailable":
                        raise
                    audit_gap = {
                        "code": exc.code,
                        "message": "replica repair committed but its immutable audit receipt did not reach quorum",
                    }

            if repair and repairs:
                status = "repaired_audit_gap" if audit_gap else "repaired"
            elif defects:
                status = "degraded"
            else:
                status = "healthy"
            return {
                "status": status,
                "head_ref": head_ref,
                "generation": head["generation"],
                "object_count": len(object_refs),
                "manifest_count": len(manifest_refs),
                "repair": repair,
                "defect_count": len(defects),
                "defects": defects,
                "repair_count": len(repairs),
                "repairs": repairs,
                "repair_receipt_ref": repair_ref,
                "audit_gap": audit_gap,
                "guardian_scar_eligible": bool(repair_ref),
                "authority_effect": "none",
            }

    def status(self) -> dict[str, Any]:
        if self.root is None:
            return {
                "schema_version": CONTINUITY_SCHEMA_VERSION,
                "policy_id": CONTINUITY_POLICY_ID,
                "status": "memory_only",
                "persistent": False,
                "replica_count": 0,
                "write_quorum": 1,
                "recognized_head_ref": None,
                "read_only": False,
                "authority_effect": "none",
            }
        with self._locked_continuity():
            head_ref, head = self._resolve_head(require_chain=True)
            objects, manifests = self._history(head_ref)
            observations = self._head_observations()
            head_support = sum(value == head_ref for value in observations.values())
            domains = [item.state.failure_domain for item in self._replicas]
            writable = sum(os.access(item.state.root, os.W_OK) for item in self._replicas)

            degraded_refs: list[str] = []
            below_quorum = False
            for manifest_ref in manifests:
                count = len(self._manifest_sources(manifest_ref))
                if count < len(self._replicas):
                    degraded_refs.append(manifest_ref)
                if count < self.write_quorum:
                    below_quorum = True
            for object_ref in objects:
                count = len(self._valid_object_sources(object_ref))
                if count < len(self._replicas):
                    degraded_refs.append(object_ref)
                if count < self.write_quorum:
                    below_quorum = True
            if head_support < len(self._replicas):
                degraded_refs.append(head_ref)

            read_only = writable < self.write_quorum or below_quorum
            return {
                "schema_version": CONTINUITY_SCHEMA_VERSION,
                "policy_id": CONTINUITY_POLICY_ID,
                "status": "degraded" if degraded_refs else "healthy",
                "persistent": True,
                "replica_count": len(self._replicas),
                "write_quorum": self.write_quorum,
                "read_quorum": self.write_quorum,
                "recognized_head_ref": head_ref,
                "generation": head["generation"],
                "recognized_object_count": len(objects),
                "manifest_count": len(manifests),
                "head_quorum_support": head_support,
                "writable_replicas": writable,
                "read_only": read_only,
                "degraded_ref_count": len(set(degraded_refs)),
                "replicas": [item.state.as_dict() for item in self._replicas],
                "independent_failure_domains": len(set(domains)),
                "failure_domain_warning": len(set(domains)) < len(domains),
                "history_selection": "majority_quorum_not_recency",
                "authority_effect": "none",
            }

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _assert_ark_destination_disjoint(self, target: Path) -> None:
        try:
            candidate = target.parent.resolve() / target.name
        except (OSError, RuntimeError) as exc:
            raise WorldContinuityError(
                "world_ark_unsafe_destination",
                "Ark destination could not be resolved safely",
            ) from exc
        for replica in self._replicas:
            root = replica.state.root.resolve()
            if (
                candidate == root
                or candidate.is_relative_to(root)
                or root.is_relative_to(candidate)
            ):
                raise WorldContinuityError(
                    "world_ark_storage_overlap",
                    "Ark destination must be disjoint from every WorldStore replica root",
                )

    @classmethod
    def _safe_ark_member(cls, root: Path, name: str) -> Path:
        if not isinstance(name, str) or not name or "\\" in name:
            raise WorldContinuityError("world_ark_invalid", "Ark file path is invalid")
        pure = PurePosixPath(name)
        if pure.is_absolute() or not pure.parts or any(part in {"", ".", ".."} for part in pure.parts):
            raise WorldContinuityError("world_ark_invalid", "Ark file path escapes the archive root")
        candidate = root.joinpath(*pure.parts)
        cursor = root
        for index, part in enumerate(pure.parts):
            cursor = cursor / part
            try:
                info = cursor.lstat()
            except OSError as exc:
                raise WorldContinuityError("world_ark_invalid", f"Ark file is unavailable: {name}") from exc
            if stat.S_ISLNK(info.st_mode):
                raise WorldContinuityError("world_ark_invalid", "Ark paths must not traverse symbolic links")
            if index < len(pure.parts) - 1 and not stat.S_ISDIR(info.st_mode):
                raise WorldContinuityError("world_ark_invalid", "Ark path parent is not a directory")
        try:
            resolved_root = root.resolve()
            resolved = candidate.resolve()
        except (OSError, RuntimeError) as exc:
            raise WorldContinuityError("world_ark_invalid", "Ark path could not be resolved safely") from exc
        if resolved == resolved_root or not resolved.is_relative_to(resolved_root):
            raise WorldContinuityError("world_ark_invalid", "Ark file path escapes the archive root")
        return candidate

    def create_ark(
        self,
        destination: str | Path,
        *,
        compute_epoch: int | None = None,
    ) -> dict[str, Any]:
        if self.root is None:
            raise WorldContinuityError(
                "world_ark_requires_persistent_world",
                "an Ark requires a persistent WorldStore",
            )
        target = Path(destination).absolute()
        self._assert_ark_destination_disjoint(target)
        if target.exists() or target.is_symlink():
            raise WorldContinuityError(
                "world_ark_target_exists",
                "Ark destination must be a new path",
            )
        staging = target.with_name(f".{target.name}.tmp-{os.getpid()}-{threading.get_ident()}")
        if staging.exists() or staging.is_symlink():
            raise WorldContinuityError(
                "world_ark_target_exists",
                "Ark staging destination already exists",
            )

        with self._locked_continuity():
            head_ref, head = self._resolve_head(
                require_chain=True,
                require_manifest_quorum=True,
            )
            object_refs, manifest_refs = self._history(
                head_ref,
                require_manifest_quorum=True,
            )
            for object_ref in object_refs:
                if len(self._valid_object_sources(object_ref)) < self.write_quorum:
                    raise WorldContinuityError(
                        "world_ark_read_quorum_unavailable",
                        "Ark creation requires a verified read quorum for every recognized object",
                    )

            try:
                staging.mkdir(parents=True, mode=0o700)
                objects_dir = staging / "objects"
                manifests_dir = staging / "manifests"
                objects_dir.mkdir(mode=0o700)
                manifests_dir.mkdir(mode=0o700)

                (staging / "FORMAT.md").write_text(
                    "# NEXUS World Ark Format\n\n"
                    "This Ark stores canonical UTF-8 JSON WorldStore objects named by their SHA-256 "
                    "object references, plus the complete content-addressed continuity manifest chain "
                    "that selected recognized history. ARK_MANIFEST.json binds every payload file by "
                    "SHA-256 and verification requires exact agreement between the chain-derived object "
                    "inventory and the archived object list. No database, daemon, cloud service or model "
                    "is required to inspect it.\n",
                    encoding="utf-8",
                )
                (staging / "RECOVERY.md").write_text(
                    "# Recovery\n\n"
                    "Verify ARK_MANIFEST.json and every listed SHA-256 before recovery. "
                    "Restore only into a new target directory; never overwrite a live WorldStore in place. "
                    "Mutable continuity HEAD state is reconstructed from the Ark's recognized head.\n",
                    encoding="utf-8",
                )

                for object_ref in sorted(object_refs):
                    source = self._valid_object_sources(object_ref)[0][0]
                    digest = object_ref.removeprefix("object:")
                    assert source.store.objects_dir is not None
                    source_path = source.store.objects_dir / f"{digest}.json"
                    destination_path = objects_dir / f"{digest}.json"
                    shutil.copyfile(source_path, destination_path)
                    if os.name != "nt":
                        destination_path.chmod(0o600)

                for manifest_ref in manifest_refs:
                    source = self._manifest_sources(manifest_ref)[0]
                    source_path = self._manifest_path(source.state.root, manifest_ref)
                    destination_path = manifests_dir / f"{manifest_ref.removeprefix('world-manifest:')}.json"
                    shutil.copyfile(source_path, destination_path)
                    if os.name != "nt":
                        destination_path.chmod(0o600)

                payload_files = [
                    path
                    for path in staging.rglob("*")
                    if path.is_file() and path.name not in {"ARK_MANIFEST.json", "SHA256SUMS"}
                ]
                files = {
                    path.relative_to(staging).as_posix(): self._sha256_file(path)
                    for path in sorted(
                        payload_files,
                        key=lambda item: item.relative_to(staging).as_posix(),
                    )
                }
                body = {
                    "schema_version": ARK_SCHEMA_VERSION,
                    "continuity_schema_version": CONTINUITY_SCHEMA_VERSION,
                    "recognized_head_ref": head_ref,
                    "generation": head["generation"],
                    "compute_epoch": compute_epoch,
                    "object_refs": sorted(object_refs),
                    "manifest_refs": list(manifest_refs),
                    "files": files,
                    "serialization": "canonical-json-utf8",
                    "primary_digest_algorithm": "sha256",
                    "restore_policy": "new_target_only",
                    "authority_effect": "none",
                }
                ark_ref = sha256_ref("world-ark", body)
                manifest = {"ark_ref": ark_ref, **body}
                (staging / "ARK_MANIFEST.json").write_text(
                    canonical_json(manifest) + "\n",
                    encoding="utf-8",
                )
                checksum_lines = [f"{digest}  {name}" for name, digest in sorted(files.items())]
                (staging / "SHA256SUMS").write_text(
                    "\n".join(checksum_lines) + "\n",
                    encoding="utf-8",
                )
                if os.name != "nt":
                    for path in (
                        staging / "FORMAT.md",
                        staging / "RECOVERY.md",
                        staging / "ARK_MANIFEST.json",
                        staging / "SHA256SUMS",
                    ):
                        path.chmod(0o600)
                    staging.chmod(0o700)
                    objects_dir.chmod(0o700)
                    manifests_dir.chmod(0o700)

                verified = self.verify_ark(staging)
                if verified.get("status") != "verified":
                    raise WorldContinuityError("world_ark_invalid", "new Ark failed verification")
                os.replace(staging, target)
            except Exception:
                shutil.rmtree(staging, ignore_errors=True)
                raise

        return {
            "status": "created",
            "ark_ref": ark_ref,
            "path": str(target),
            "generation": head["generation"],
            "object_count": len(object_refs),
            "manifest_count": len(manifest_refs),
            "compute_epoch": compute_epoch,
            "verified": True,
            "authority_effect": "none",
        }

    @classmethod
    def _load_ark_manifest(cls, ark_root: Path) -> dict[str, Any]:
        raw = cls._read_canonical(ark_root / "ARK_MANIFEST.json")
        expected_fields = {
            "ark_ref",
            "schema_version",
            "continuity_schema_version",
            "recognized_head_ref",
            "generation",
            "compute_epoch",
            "object_refs",
            "manifest_refs",
            "files",
            "serialization",
            "primary_digest_algorithm",
            "restore_policy",
            "authority_effect",
        }
        if set(raw) != expected_fields:
            raise WorldContinuityError("world_ark_invalid", "Ark manifest schema is invalid")
        body = {key: raw[key] for key in expected_fields if key != "ark_ref"}
        expected_ref = sha256_ref("world-ark", body)
        if raw.get("ark_ref") != expected_ref or _ARK_REF.fullmatch(str(raw.get("ark_ref"))) is None:
            raise WorldContinuityError("world_ark_invalid", "Ark manifest identity is invalid")
        if raw.get("schema_version") != ARK_SCHEMA_VERSION:
            raise WorldContinuityError("world_ark_invalid", "Ark schema version is invalid")
        if raw.get("continuity_schema_version") != CONTINUITY_SCHEMA_VERSION:
            raise WorldContinuityError("world_ark_invalid", "Ark continuity schema version is invalid")
        if raw.get("serialization") != "canonical-json-utf8" or raw.get("primary_digest_algorithm") != "sha256":
            raise WorldContinuityError("world_ark_invalid", "Ark serialization policy is invalid")
        if raw.get("restore_policy") != "new_target_only" or raw.get("authority_effect") != "none":
            raise WorldContinuityError("world_ark_invalid", "Ark recovery or authority policy is invalid")
        return raw

    @classmethod
    def verify_ark(cls, ark_root: str | Path) -> dict[str, Any]:
        root = Path(ark_root).absolute()
        if root.is_symlink() or not root.is_dir():
            raise WorldContinuityError("world_ark_invalid", "Ark root must be a regular directory")
        try:
            if root.resolve() != root:
                raise WorldContinuityError("world_ark_invalid", "Ark root must not traverse symbolic links")
        except (OSError, RuntimeError) as exc:
            raise WorldContinuityError("world_ark_invalid", "Ark root could not be resolved safely") from exc

        raw = cls._load_ark_manifest(root)
        files = raw.get("files")
        if not isinstance(files, dict) or any(
            not isinstance(name, str)
            or not isinstance(digest, str)
            or _HEX64.fullmatch(digest) is None
            for name, digest in files.items()
        ):
            raise WorldContinuityError("world_ark_invalid", "Ark file digest map is invalid")

        object_refs = raw.get("object_refs")
        manifest_refs = raw.get("manifest_refs")
        if (
            not isinstance(object_refs, list)
            or object_refs != sorted(set(object_refs))
            or any(not isinstance(item, str) or _OBJECT_REF.fullmatch(item) is None for item in object_refs)
            or not isinstance(manifest_refs, list)
            or not manifest_refs
            or len(set(manifest_refs)) != len(manifest_refs)
        ):
            raise WorldContinuityError("world_ark_invalid", "Ark history lists are invalid")

        expected_files = {"FORMAT.md", "RECOVERY.md"}
        expected_files.update(
            f"objects/{item.removeprefix('object:')}.json" for item in object_refs
        )
        expected_files.update(
            f"manifests/{item.removeprefix('world-manifest:')}.json" for item in manifest_refs
        )
        if set(files) != expected_files:
            raise WorldContinuityError(
                "world_ark_invalid",
                "Ark file inventory does not exactly match its declared history",
            )

        for name, digest in files.items():
            path = cls._safe_ark_member(root, name)
            if not path.is_file() or cls._sha256_file(path) != digest:
                raise WorldContinuityError("world_ark_invalid", f"Ark file failed verification: {name}")

        for item in root.rglob("*"):
            if item.is_symlink():
                raise WorldContinuityError("world_ark_invalid", "Ark payload must not contain symbolic links")
        actual_payload_files = {
            path.relative_to(root).as_posix()
            for path in root.rglob("*")
            if path.is_file() and path.name not in {"ARK_MANIFEST.json", "SHA256SUMS"}
        }
        if actual_payload_files != expected_files:
            raise WorldContinuityError("world_ark_invalid", "Ark contains undeclared or missing payload files")

        for object_ref in object_refs:
            digest = object_ref.removeprefix("object:")
            path = cls._safe_ark_member(root, f"objects/{digest}.json")
            WorldStore._read_validated(object_ref, path)

        previous: str | None = None
        expected_objects: set[str] = set()
        last_generation = -1
        for generation, manifest_ref in enumerate(manifest_refs):
            if not isinstance(manifest_ref, str) or _MANIFEST_REF.fullmatch(manifest_ref) is None:
                raise WorldContinuityError("world_ark_invalid", "Ark manifest ref is invalid")
            member = f"manifests/{manifest_ref.removeprefix('world-manifest:')}.json"
            manifest_path = cls._safe_ark_member(root, member)
            manifest = cls._validate_manifest(cls._read_canonical(manifest_path), manifest_ref)
            if manifest["generation"] != generation or manifest["previous_manifest_ref"] != previous:
                raise WorldContinuityError("world_ark_invalid", "Ark continuity chain is invalid")
            if generation == 0:
                if manifest["event_type"] != "legacy_baseline":
                    raise WorldContinuityError("world_ark_invalid", "Ark continuity chain lacks a baseline")
                expected_objects.update(manifest["inventory_refs"])
            elif manifest["event_type"] == "object_commit":
                expected_objects.add(manifest["object_ref"])
            previous = manifest_ref
            last_generation = generation

        if previous != raw.get("recognized_head_ref"):
            raise WorldContinuityError("world_ark_invalid", "Ark head does not match its manifest chain")
        if raw.get("generation") != last_generation:
            raise WorldContinuityError("world_ark_invalid", "Ark generation does not match its manifest chain")
        if expected_objects != set(object_refs):
            raise WorldContinuityError(
                "world_ark_invalid",
                "Ark object inventory does not exactly match the continuity chain",
            )

        checksum_path = root / "SHA256SUMS"
        if checksum_path.is_symlink() or not checksum_path.is_file():
            raise WorldContinuityError("world_ark_invalid", "Ark checksum index is invalid")
        checksum_text = checksum_path.read_text(encoding="utf-8")
        expected_checksum_text = "\n".join(
            f"{digest}  {name}" for name, digest in sorted(files.items())
        ) + "\n"
        if checksum_text != expected_checksum_text:
            raise WorldContinuityError("world_ark_invalid", "Ark checksum index is inconsistent")

        return {
            "status": "verified",
            "ark_ref": raw["ark_ref"],
            "recognized_head_ref": raw["recognized_head_ref"],
            "generation": raw["generation"],
            "compute_epoch": raw["compute_epoch"],
            "object_count": len(object_refs),
            "manifest_count": len(manifest_refs),
            "restore_eligible": True,
            "authority_effect": "none",
        }

    @classmethod
    def inspect_recovery(cls, ark_root: str | Path) -> dict[str, Any]:
        verified = cls.verify_ark(ark_root)
        return {
            **verified,
            "status": "restore_eligible",
            "restore_policy": "new_target_only",
            "in_place_overwrite_allowed": False,
        }

    @classmethod
    def restore_ark(cls, ark_root: str | Path, target_root: str | Path) -> dict[str, Any]:
        verified = cls.verify_ark(ark_root)
        source = Path(ark_root).absolute()
        target = Path(target_root).absolute()
        if target.exists() or target.is_symlink():
            raise WorldContinuityError(
                "world_recovery_target_exists",
                "recovery target must be a new path",
            )
        try:
            source_resolved = source.resolve()
            target_candidate = target.parent.resolve() / target.name
        except (OSError, RuntimeError) as exc:
            raise WorldContinuityError(
                "world_recovery_unsafe_target",
                "recovery target could not be resolved safely",
            ) from exc
        if (
            target_candidate == source_resolved
            or target_candidate.is_relative_to(source_resolved)
            or source_resolved.is_relative_to(target_candidate)
        ):
            raise WorldContinuityError(
                "world_recovery_unsafe_target",
                "recovery target must be disjoint from the source Ark",
            )

        staging = target.with_name(f".{target.name}.tmp-{os.getpid()}-{threading.get_ident()}")
        if staging.exists() or staging.is_symlink():
            raise WorldContinuityError(
                "world_recovery_target_exists",
                "recovery staging target already exists",
            )
        raw = cls._load_ark_manifest(source)
        try:
            staging.mkdir(parents=True, mode=0o700)
            (staging / "objects").mkdir(mode=0o700)
            cls._prepare_continuity_root(staging)

            for object_ref in raw["object_refs"]:
                digest = object_ref.removeprefix("object:")
                source_path = cls._safe_ark_member(source, f"objects/{digest}.json")
                destination = staging / "objects" / f"{digest}.json"
                shutil.copyfile(source_path, destination)
                if os.name != "nt":
                    destination.chmod(0o600)
            for manifest_ref in raw["manifest_refs"]:
                digest = manifest_ref.removeprefix("world-manifest:")
                source_path = cls._safe_ark_member(source, f"manifests/{digest}.json")
                destination = staging / "continuity" / "manifests" / f"{digest}.json"
                shutil.copyfile(source_path, destination)
                if os.name != "nt":
                    destination.chmod(0o600)
            cls._write_head(staging, raw["recognized_head_ref"])
            if os.name != "nt":
                staging.chmod(0o700)
                (staging / "objects").chmod(0o700)

            restored = cls(staging)
            restored_status = restored.status()
            for object_ref in raw["object_refs"]:
                restored.inspect(object_ref)
            os.replace(staging, target)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise

        return {
            "status": "restored",
            "source_ark_ref": verified["ark_ref"],
            "target": str(target),
            "recognized_head_ref": restored_status["recognized_head_ref"],
            "object_count": restored_status["recognized_object_count"],
            "in_place_overwrite": False,
            "authority_effect": "none",
        }

    def create_migration_receipt(
        self,
        object_ref: str,
        *,
        target_digest_algorithm: str = "sha512",
    ) -> WorldObject:
        source = self.inspect(object_ref)
        raw = (canonical_json(source.as_dict()) + "\n").encode("utf-8")
        if target_digest_algorithm != "sha512":
            raise WorldContinuityError(
                "world_migration_digest_unsupported",
                "v1 migration receipts currently support the additive sha512 digest only",
            )
        target_digest = hashlib.sha512(raw).hexdigest()
        source_digest = object_ref.removeprefix("object:")
        return self.create_object(
            MIGRATION_OBJECT_TYPE,
            {
                "schema_version": MIGRATION_SCHEMA_VERSION,
                "source_object_ref": object_ref,
                "source_format": "canonical-json-v1",
                "source_digest": {"algorithm": "sha256", "value": source_digest},
                "target_format": "canonical-json-v1",
                "target_digest": {"algorithm": target_digest_algorithm, "value": target_digest},
                "source_bytes_preserved": True,
                "source_ref_preserved": True,
                "semantic_equivalence_claim": "same_canonical_bytes_rehashed",
                "authority_effect": "none",
            },
            {"actor": "nexus_world_continuity"},
        )


__all__ = [
    "ARK_SCHEMA_VERSION",
    "CONTINUITY_POLICY_ID",
    "CONTINUITY_RESERVED_OBJECT_TYPES",
    "CONTINUITY_SCHEMA_VERSION",
    "ContinuityWorldStore",
    "MIGRATION_OBJECT_TYPE",
    "MIGRATION_SCHEMA_VERSION",
    "ReplicaState",
    "WorldContinuityError",
    "continuity_policy_snapshot",
]
