from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
import stat
import tempfile
import threading
from typing import Any, Mapping, Protocol

from .types import (
    AuthError,
    AuthProfile,
    AuthUnavailableError,
    PROFILE_STORE_SCHEMA_VERSION,
    SECRET_STORE_SCHEMA_VERSION,
    SecretMaterial,
    validate_credential_handle,
)


MAX_AUTH_FILE_BYTES = 1_048_576
KEYRING_SERVICE = "qsol-nexus"


class AuthStorageLock:
    """Re-entrant thread/process lock for one authentication storage root."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.path = self.root / "auth.lock"
        self._thread_lock = threading.RLock()
        self._local = threading.local()

    def __enter__(self) -> "AuthStorageLock":
        self._thread_lock.acquire()
        depth = getattr(self._local, "depth", 0)
        if depth:
            self._local.depth = depth + 1
            return self

        descriptor: int | None = None
        handle: Any | None = None
        try:
            ensure_private_auth_root(self.root)
            if self.path.exists() or self.path.is_symlink():
                _assert_private_regular_file(self.path)
            flags = os.O_RDWR | os.O_CREAT
            flags |= getattr(os, "O_CLOEXEC", 0)
            flags |= getattr(os, "O_NOFOLLOW", 0)
            flags |= getattr(os, "O_BINARY", 0)
            descriptor = os.open(self.path, flags, 0o600)
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode):
                raise AuthError("authentication storage lock is not a regular file")
            if os.name != "nt" and stat.S_IMODE(info.st_mode) & 0o077:
                raise AuthError("authentication storage lock permissions must be owner-only")
            handle = os.fdopen(descriptor, "r+b", buffering=0)
            descriptor = None
            if os.name == "nt":
                import msvcrt

                handle.seek(0, os.SEEK_END)
                if handle.tell() == 0:
                    handle.write(b"\0")
                    handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        except Exception as exc:
            try:
                if handle is not None:
                    handle.close()
                elif descriptor is not None:
                    os.close(descriptor)
            except OSError:
                pass
            self._thread_lock.release()
            if isinstance(exc, AuthError):
                raise
            if isinstance(exc, OSError):
                raise AuthUnavailableError("authentication storage lock is unavailable") from exc
            raise

        self._local.handle = handle
        self._local.depth = 1
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        depth = getattr(self._local, "depth", 0)
        if depth > 1:
            self._local.depth = depth - 1
            self._thread_lock.release()
            return False

        handle = getattr(self._local, "handle", None)
        unlock_error: OSError | None = None
        try:
            if handle is not None:
                try:
                    if os.name == "nt":
                        import msvcrt

                        handle.seek(0)
                        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                except OSError as error:
                    unlock_error = error
                finally:
                    try:
                        handle.close()
                    except OSError as error:
                        if unlock_error is None:
                            unlock_error = error
        finally:
            self._local.depth = 0
            self._local.handle = None
            self._thread_lock.release()
        if unlock_error is not None and exc_type is None:
            raise AuthUnavailableError("authentication storage lock could not be released") from unlock_error
        return False


_AUTH_STORAGE_LOCKS_GUARD = threading.Lock()
_AUTH_STORAGE_LOCKS: dict[str, AuthStorageLock] = {}


def auth_storage_lock(root: str | Path) -> AuthStorageLock:
    try:
        key = str(Path(root).expanduser().resolve())
    except (OSError, RuntimeError) as exc:
        raise AuthError("authentication storage root could not be resolved") from exc
    with _AUTH_STORAGE_LOCKS_GUARD:
        lock = _AUTH_STORAGE_LOCKS.get(key)
        if lock is None:
            lock = AuthStorageLock(Path(key))
            _AUTH_STORAGE_LOCKS[key] = lock
        return lock


class SecretStore(Protocol):
    backend_id: str

    def put(self, handle: str, material: SecretMaterial) -> None: ...

    def get(self, handle: str) -> SecretMaterial: ...

    def delete(self, handle: str) -> None: ...


def default_auth_root() -> Path:
    override = os.environ.get("NEXUS_AUTH_ROOT")
    if override:
        return Path(override).expanduser()
    if os.name == "nt" and os.environ.get("APPDATA"):
        return Path(os.environ["APPDATA"]) / "QSOL NEXUS" / "auth"
    if sys_platform() == "darwin":
        return Path.home() / "Library" / "Application Support" / "QSOL NEXUS" / "auth"
    config_root = os.environ.get("XDG_CONFIG_HOME")
    return (Path(config_root) if config_root else Path.home() / ".config") / "qsol-nexus" / "auth"


def sys_platform() -> str:
    # Kept as a tiny seam for deterministic platform-path tests.
    import sys

    return sys.platform


def _ensure_private_directory(path: Path) -> None:
    try:
        existed = path.exists()
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        if path.is_symlink() or not path.is_dir() or path.resolve() != path.absolute():
            raise AuthError("authentication storage directory is not a private directory")
        if os.name != "nt":
            permissions = stat.S_IMODE(path.stat().st_mode)
            if existed and permissions & 0o077:
                raise AuthError("authentication storage directory permissions must be owner-only")
            if not existed:
                os.chmod(path, 0o700)
    except AuthError:
        raise
    except (OSError, RuntimeError) as exc:
        raise AuthError("authentication storage directory could not be prepared") from exc


def ensure_private_auth_root(path: str | Path) -> None:
    _ensure_private_directory(Path(path))


def ensure_disjoint_auth_world_roots(auth_root: str | Path, world_root: str | Path) -> None:
    try:
        auth_path = Path(auth_root).expanduser().resolve()
        world_path = Path(world_root).expanduser().resolve()
    except (OSError, RuntimeError) as exc:
        raise AuthError("auth or world storage root could not be resolved") from exc
    if auth_path == world_path or auth_path.is_relative_to(world_path) or world_path.is_relative_to(auth_path):
        raise AuthError("auth storage and world storage must be disjoint directories")


def _assert_private_regular_file(path: Path) -> None:
    try:
        if path.parent.resolve() != path.parent.absolute():
            raise AuthError("authentication storage directory must not traverse symbolic links")
        parent_info = path.parent.lstat()
        if not stat.S_ISDIR(parent_info.st_mode):
            raise AuthError("authentication storage parent is not a directory")
        if os.name != "nt" and stat.S_IMODE(parent_info.st_mode) & 0o077:
            raise AuthError("authentication storage directory permissions must be owner-only")
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode):
            raise AuthError("authentication storage file is not a regular file")
        if os.name != "nt" and stat.S_IMODE(info.st_mode) & 0o077:
            raise AuthError("authentication storage file permissions must be owner-only")
    except AuthError:
        raise
    except (OSError, RuntimeError) as exc:
        raise AuthError("authentication storage file could not be inspected") from exc


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        _assert_private_regular_file(path)
        if path.stat().st_size > MAX_AUTH_FILE_BYTES:
            raise AuthError("authentication storage file exceeds the size limit")
        value = json.loads(path.read_text(encoding="utf-8"))
    except AuthError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AuthError("authentication storage file is unreadable or invalid") from exc
    if not isinstance(value, dict):
        raise AuthError("authentication storage root must be an object")
    return value


def _atomic_private_json(path: Path, value: Mapping[str, Any]) -> None:
    _ensure_private_directory(path.parent)
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
    if len(payload.encode("utf-8")) > MAX_AUTH_FILE_BYTES:
        raise AuthError("authentication storage payload exceeds the size limit")
    fd: int | None = None
    temporary: Path | None = None
    try:
        fd, temporary_name = tempfile.mkstemp(prefix=".nexus-auth-", dir=path.parent, text=True)
        temporary = Path(temporary_name)
        if os.name != "nt":
            os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            fd = None
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        if os.name != "nt":
            os.chmod(path, 0o600)
    except Exception as exc:
        try:
            if fd is not None:
                os.close(fd)
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        except OSError:
            pass
        if isinstance(exc, OSError):
            raise AuthUnavailableError("authentication storage file could not be written") from exc
        raise


class ProfileStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.path = self.root / "profiles.json"
        self.lock = auth_storage_lock(self.root)

    def load(self) -> dict[str, AuthProfile]:
        return self._load_unlocked()

    def _load_unlocked(self) -> dict[str, AuthProfile]:
        try:
            if not self.path.exists():
                return {}
        except OSError as exc:
            raise AuthUnavailableError("auth profile store is unavailable") from exc
        value = _read_json(self.path)
        if set(value) != {"schema_version", "profiles"}:
            raise AuthError("auth profile store schema is invalid")
        if value["schema_version"] != PROFILE_STORE_SCHEMA_VERSION:
            raise AuthError("auth profile store schema version is unsupported")
        rows = value["profiles"]
        if not isinstance(rows, list):
            raise AuthError("auth profile store profiles must be a list")
        profiles: dict[str, AuthProfile] = {}
        for row in rows:
            if not isinstance(row, dict):
                raise AuthError("stored auth profile must be an object")
            profile = AuthProfile.from_storage_dict(row)
            if profile.profile_id in profiles:
                raise AuthError("auth profile store contains a duplicate profile")
            profiles[profile.profile_id] = profile
        return profiles

    def save(self, profiles: Mapping[str, AuthProfile]) -> None:
        with self.lock:
            self._save_unlocked(profiles)

    def _save_unlocked(self, profiles: Mapping[str, AuthProfile]) -> None:
        if any(key != profile.profile_id for key, profile in profiles.items()):
            raise AuthError("auth profile store key does not match profile identity")
        ordered = [profiles[key].storage_dict() for key in sorted(profiles)]
        _atomic_private_json(
            self.path,
            {"schema_version": PROFILE_STORE_SCHEMA_VERSION, "profiles": ordered},
        )

    def upsert(self, profile: AuthProfile, *, replace: bool = False) -> AuthProfile | None:
        with self.lock:
            profiles = self._load_unlocked()
            previous = profiles.get(profile.profile_id)
            if previous is not None and not replace:
                raise AuthError(f"auth profile {profile.profile_id} already exists")
            profiles[profile.profile_id] = profile
            self._save_unlocked(profiles)
            return previous

    def delete(self, adapter_id: str, profile_name: str) -> AuthProfile:
        with self.lock:
            profiles = self._load_unlocked()
            profile_id = f"{adapter_id}:{profile_name}"
            try:
                removed = profiles.pop(profile_id)
            except KeyError as exc:
                raise AuthError(f"auth profile {profile_id} does not exist") from exc
            self._save_unlocked(profiles)
            return removed


class FileSecretStore:
    backend_id = "private_file"

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root) / "secrets"

    def _path(self, handle: str) -> Path:
        validate_credential_handle(handle)
        return self.root / f"{handle}.json"

    def put(self, handle: str, material: SecretMaterial) -> None:
        _atomic_private_json(
            self._path(handle),
            {"schema_version": SECRET_STORE_SCHEMA_VERSION, "credential": material.storage_dict()},
        )

    def get(self, handle: str) -> SecretMaterial:
        path = self._path(handle)
        try:
            if not path.exists():
                raise AuthUnavailableError("stored credential is unavailable")
        except OSError as exc:
            raise AuthUnavailableError("stored credential is unavailable") from exc
        value = _read_json(path)
        if set(value) != {"schema_version", "credential"}:
            raise AuthError("stored credential schema is invalid")
        if value["schema_version"] != SECRET_STORE_SCHEMA_VERSION:
            raise AuthError("stored credential schema version is unsupported")
        credential = value["credential"]
        if not isinstance(credential, dict):
            raise AuthError("stored credential payload is invalid")
        return SecretMaterial.from_storage_dict(credential)

    def delete(self, handle: str) -> None:
        path = self._path(handle)
        try:
            if path.parent.exists():
                if path.parent.is_symlink() or path.parent.resolve() != path.parent.absolute():
                    raise AuthError("authentication storage directory must not traverse symbolic links")
                if os.name != "nt" and stat.S_IMODE(path.parent.stat().st_mode) & 0o077:
                    raise AuthError("authentication storage directory permissions must be owner-only")
            path.unlink()
        except FileNotFoundError:
            return
        except OSError as exc:
            raise AuthUnavailableError("stored credential could not be deleted") from exc


class KeyringSecretStore:
    backend_id = "os_keyring"

    def __init__(self, keyring_module: Any) -> None:
        self._keyring = keyring_module

    def put(self, handle: str, material: SecretMaterial) -> None:
        validate_credential_handle(handle)
        payload = json.dumps(
            {"schema_version": SECRET_STORE_SCHEMA_VERSION, "credential": material.storage_dict()},
            sort_keys=True,
            separators=(",", ":"),
        )
        if len(payload.encode("utf-8")) > MAX_AUTH_FILE_BYTES:
            raise AuthError("OS keyring credential payload exceeds the size limit")
        try:
            self._keyring.set_password(KEYRING_SERVICE, handle, payload)
        except Exception as exc:
            raise AuthUnavailableError("OS keyring rejected the credential write") from exc

    def get(self, handle: str) -> SecretMaterial:
        validate_credential_handle(handle)
        try:
            payload = self._keyring.get_password(KEYRING_SERVICE, handle)
        except Exception as exc:
            raise AuthUnavailableError("OS keyring credential lookup failed") from exc
        if payload is None:
            raise AuthUnavailableError("stored credential is unavailable")
        try:
            payload_size = len(payload.encode("utf-8")) if isinstance(payload, str) else MAX_AUTH_FILE_BYTES + 1
        except UnicodeError as exc:
            raise AuthError("OS keyring credential payload is invalid") from exc
        if payload_size > MAX_AUTH_FILE_BYTES:
            raise AuthError("OS keyring credential payload exceeds the size limit")
        try:
            value = json.loads(payload)
        except (TypeError, json.JSONDecodeError) as exc:
            raise AuthError("OS keyring credential payload is invalid") from exc
        if not isinstance(value, dict) or set(value) != {"schema_version", "credential"}:
            raise AuthError("OS keyring credential schema is invalid")
        if value["schema_version"] != SECRET_STORE_SCHEMA_VERSION or not isinstance(value["credential"], dict):
            raise AuthError("OS keyring credential schema version or payload is invalid")
        return SecretMaterial.from_storage_dict(value["credential"])

    def delete(self, handle: str) -> None:
        validate_credential_handle(handle)
        try:
            if self._keyring.get_password(KEYRING_SERVICE, handle) is not None:
                self._keyring.delete_password(KEYRING_SERVICE, handle)
        except Exception as exc:
            raise AuthUnavailableError("OS keyring credential deletion failed") from exc


def available_secret_stores(root: str | Path, keyring_module: Any | None = None) -> tuple[dict[str, SecretStore], str]:
    stores: dict[str, SecretStore] = {}
    file_store = FileSecretStore(root)
    stores[file_store.backend_id] = file_store

    module = keyring_module
    if module is None and os.environ.get("NEXUS_AUTH_FORCE_FILE_STORE") != "1":
        try:
            module = importlib.import_module("keyring")
        except (ImportError, OSError):
            module = None
    if module is not None:
        try:
            backend = module.get_keyring()
            priority = getattr(backend, "priority", 0)
            if isinstance(priority, (int, float)) and priority > 0:
                keyring_store = KeyringSecretStore(module)
                stores[keyring_store.backend_id] = keyring_store
                return stores, keyring_store.backend_id
        except Exception:
            pass
    return stores, file_store.backend_id
