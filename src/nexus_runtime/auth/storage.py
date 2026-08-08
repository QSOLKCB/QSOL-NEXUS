from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
import stat
import tempfile
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
    existed = path.exists()
    try:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
    except OSError as exc:
        raise AuthError("authentication storage directory could not be prepared") from exc
    if path.is_symlink() or not path.is_dir() or path.resolve() != path.absolute():
        raise AuthError("authentication storage directory is not a private directory")
    if os.name != "nt":
        permissions = stat.S_IMODE(path.stat().st_mode)
        if existed and permissions & 0o077:
            raise AuthError("authentication storage directory permissions must be owner-only")
        if not existed:
            os.chmod(path, 0o700)


def ensure_private_auth_root(path: str | Path) -> None:
    _ensure_private_directory(Path(path))


def _assert_private_regular_file(path: Path) -> None:
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


def _read_json(path: Path) -> Mapping[str, Any]:
    _assert_private_regular_file(path)
    if path.stat().st_size > MAX_AUTH_FILE_BYTES:
        raise AuthError("authentication storage file exceeds the size limit")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
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
    fd, temporary_name = tempfile.mkstemp(prefix=".nexus-auth-", dir=path.parent, text=True)
    temporary = Path(temporary_name)
    try:
        if os.name != "nt":
            os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        if os.name != "nt":
            os.chmod(path, 0o600)
    except Exception:
        try:
            try:
                os.close(fd)
            except OSError:
                pass
            temporary.unlink(missing_ok=True)
        finally:
            raise


class ProfileStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.path = self.root / "profiles.json"

    def load(self) -> dict[str, AuthProfile]:
        if not self.path.exists():
            return {}
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
        if any(key != profile.profile_id for key, profile in profiles.items()):
            raise AuthError("auth profile store key does not match profile identity")
        ordered = [profiles[key].storage_dict() for key in sorted(profiles)]
        _atomic_private_json(
            self.path,
            {"schema_version": PROFILE_STORE_SCHEMA_VERSION, "profiles": ordered},
        )

    def upsert(self, profile: AuthProfile, *, replace: bool = False) -> AuthProfile | None:
        profiles = self.load()
        previous = profiles.get(profile.profile_id)
        if previous is not None and not replace:
            raise AuthError(f"auth profile {profile.profile_id} already exists")
        profiles[profile.profile_id] = profile
        self.save(profiles)
        return previous

    def delete(self, adapter_id: str, profile_name: str) -> AuthProfile:
        profiles = self.load()
        profile_id = f"{adapter_id}:{profile_name}"
        try:
            removed = profiles.pop(profile_id)
        except KeyError as exc:
            raise AuthError(f"auth profile {profile_id} does not exist") from exc
        self.save(profiles)
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
        if not path.exists():
            raise AuthUnavailableError("stored credential is unavailable")
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
        if path.parent.exists():
            if path.parent.is_symlink() or path.parent.resolve() != path.parent.absolute():
                raise AuthError("authentication storage directory must not traverse symbolic links")
            if os.name != "nt" and stat.S_IMODE(path.parent.stat().st_mode) & 0o077:
                raise AuthError("authentication storage directory permissions must be owner-only")
        try:
            path.unlink()
        except FileNotFoundError:
            return


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
