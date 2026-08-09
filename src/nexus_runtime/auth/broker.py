from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import subprocess
import threading
import time
from typing import Any, Callable, Mapping, Sequence
import uuid

from ..scrub import SecretScrubber
from .oauth import BrowserPKCEFlow, DeviceAuthorizationPrompt, DeviceCodeFlow, OAuthTokenClient, parse_token_response
from .storage import (
    FileSecretStore,
    ProfileStore,
    SecretStore,
    available_secret_stores,
    default_auth_root,
    ensure_private_auth_root,
)
from .types import (
    AUTH_SCHEMA_VERSION,
    AdapterAuthDescriptor,
    AuthError,
    AuthFlow,
    AuthMethod,
    AuthProfile,
    AuthTimeoutError,
    AuthUnavailableError,
    SecretMaterial,
    validate_environment_name,
    validate_identifier,
)


EXTERNAL_COMMAND_TIMEOUT_SECONDS = 30.0
MAX_EXTERNAL_COMMAND_OUTPUT_BYTES = 65_536
_SECRET_BEARING_HELPER_OPTION = re.compile(
    r"^(?:--?|/)(?:api[-_]?key|(?:access|auth|oauth|refresh|id|identity|session)[-_]?token"
    r"|client[-_]?secret|private[-_]?key|password|passwd|secret|token|credential"
    r"|authorization|bearer|cookie)(?:=|:|$)",
    re.I,
)


@dataclass(frozen=True)
class ConnectionCheck:
    status: str
    code: str

    def __post_init__(self) -> None:
        if self.status not in {"healthy", "unavailable"}:
            raise ValueError("connection check status must be healthy or unavailable")
        validate_identifier(self.code, "connection check code")

    def public_dict(self) -> dict[str, str]:
        return {"status": self.status, "code": self.code}


ConnectionTester = Callable[[SecretMaterial | None], ConnectionCheck]


class AdapterAuthRegistry:
    def __init__(self, descriptors: Sequence[AdapterAuthDescriptor] = ()) -> None:
        self._descriptors: dict[str, AdapterAuthDescriptor] = {}
        for descriptor in (*builtin_auth_descriptors(), *descriptors):
            self.register(descriptor)

    def register(self, descriptor: AdapterAuthDescriptor) -> None:
        if descriptor.adapter_id in self._descriptors:
            raise AuthError(f"duplicate auth descriptor for adapter {descriptor.adapter_id}")
        self._descriptors[descriptor.adapter_id] = descriptor

    def get(self, adapter_id: str) -> AdapterAuthDescriptor:
        validate_identifier(adapter_id, "adapter_id")
        try:
            return self._descriptors[adapter_id]
        except KeyError as exc:
            raise AuthError(f"unknown auth adapter {adapter_id}") from exc

    def public_list(self) -> list[dict[str, Any]]:
        return [self._descriptors[key].public_dict() for key in sorted(self._descriptors)]


def builtin_auth_descriptors() -> tuple[AdapterAuthDescriptor, ...]:
    from ..adapters.xai import xai_auth_descriptor

    return (
        AdapterAuthDescriptor(
            adapter_id="mock",
            provider_name="NEXUS deterministic mock",
            local_or_remote="local",
            auth_methods=(AuthMethod.NO_AUTH_REQUIRED,),
            auth_flows=(AuthFlow.NONE,),
        ),
        AdapterAuthDescriptor(
            adapter_id="ollama",
            provider_name="Ollama loopback",
            local_or_remote="local",
            auth_methods=(AuthMethod.LOCAL_ENDPOINT, AuthMethod.NO_AUTH_REQUIRED),
            auth_flows=(AuthFlow.LOCAL_ENDPOINT, AuthFlow.NONE),
        ),
        xai_auth_descriptor(),
    )


class AuthBroker:
    """Provider-neutral authentication boundary.

    Only this object returns ``SecretMaterial`` and only to adapter transport
    code. Public methods emit profile metadata and health states without raw
    tokens, refresh tokens, authorization codes, or credential handles.
    """

    def __init__(
        self,
        root: str | Path | None = None,
        *,
        descriptors: Sequence[AdapterAuthDescriptor] = (),
        profile_store: ProfileStore | None = None,
        secret_stores: Mapping[str, SecretStore] | None = None,
        default_secret_backend: str | None = None,
        browser_flow: BrowserPKCEFlow | None = None,
        device_flow: DeviceCodeFlow | None = None,
        token_client: OAuthTokenClient | None = None,
        connection_testers: Mapping[str, ConnectionTester] | None = None,
        remote_adapters_admitted: bool = True,
        clock: Callable[[], float] = time.time,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        selected_root = Path(root).expanduser() if root is not None else default_auth_root().expanduser()
        if not selected_root.is_absolute():
            raise AuthError("authentication storage root must be an absolute path")
        self.root = selected_root
        self.registry = AdapterAuthRegistry(descriptors)
        self.profile_store = profile_store or ProfileStore(self.root)
        if self.profile_store.root.expanduser().resolve() != self.root.resolve():
            raise AuthError("auth profile store root must match the broker auth root")
        if secret_stores is None:
            selected_stores, selected_default = available_secret_stores(self.root)
            self.secret_stores = selected_stores
            self.default_secret_backend = selected_default
        else:
            self.secret_stores = dict(secret_stores)
            if not self.secret_stores:
                raise AuthError("at least one credential store is required")
            self.default_secret_backend = default_secret_backend or next(iter(self.secret_stores))
        if self.default_secret_backend not in self.secret_stores:
            raise AuthError("default credential backend is unavailable")
        for backend_id, store in self.secret_stores.items():
            validate_identifier(backend_id, "credential backend id")
            if getattr(store, "backend_id", None) != backend_id:
                raise AuthError("credential store key does not match its backend id")
            if isinstance(store, FileSecretStore) and store.root.parent.expanduser().resolve() != self.root.resolve():
                raise AuthError("private-file credential store root must match the broker auth root")
        if type(remote_adapters_admitted) is not bool:
            raise AuthError("remote_adapters_admitted must be a boolean")
        self.clock = clock
        self.token_client = token_client or OAuthTokenClient(clock=clock)
        self.browser_flow = browser_flow or BrowserPKCEFlow(token_client=self.token_client)
        self.device_flow = device_flow or DeviceCodeFlow(clock=clock)
        if connection_testers is None:
            from ..adapters.xai import xai_connection_test

            self.connection_testers = {"xai": xai_connection_test}
        else:
            self.connection_testers = dict(connection_testers)
        for adapter_id in self.connection_testers:
            self.registry.get(adapter_id)
        self.remote_adapters_admitted = remote_adapters_admitted
        self.environment = environment if environment is not None else os.environ

    def status(self) -> dict[str, Any]:
        profiles = self.profile_store.load()
        remote_descriptors = [
            row
            for row in self.registry.public_list()
            if row["local_or_remote"] == "remote" and row["implementation_status"] == "available"
        ]
        return {
            "schema_version": AUTH_SCHEMA_VERSION,
            "credential_backends": sorted(self.secret_stores),
            "default_credential_backend": self.default_secret_backend,
            "configured_profile_count": len(profiles),
            "browser_pkce": True,
            "device_code": True,
            "headless_sources": [AuthFlow.ENVIRONMENT.value, AuthFlow.EXTERNAL_COMMAND.value],
            "remote_auth_descriptor_count": len(remote_descriptors),
            "remote_adapters_admitted": self.remote_adapters_admitted,
        }

    def adapters(self) -> dict[str, Any]:
        return {"status": "ok", "schema_version": AUTH_SCHEMA_VERSION, "adapters": self.registry.public_list()}

    def setup_url(self, adapter_id: str) -> str:
        descriptor = self.registry.get(adapter_id)
        if descriptor.setup_url is None:
            raise AuthUnavailableError(f"adapter {adapter_id} does not publish a browser setup URL")
        return descriptor.setup_url

    def list_profiles(self) -> dict[str, Any]:
        profiles = self.profile_store.load()
        return {
            "status": "ok",
            "schema_version": AUTH_SCHEMA_VERSION,
            "profiles": [profiles[key].public_dict() for key in sorted(profiles)],
        }

    def add_api_key(
        self,
        adapter_id: str,
        profile_name: str,
        api_key: str,
        *,
        replace: bool = False,
    ) -> dict[str, Any]:
        self._require_flow(adapter_id, AuthFlow.API_KEY, AuthMethod.API_CREDENTIAL)
        material = SecretMaterial(access_token=api_key)
        return self._add_stored(
            adapter_id,
            profile_name,
            AuthMethod.API_CREDENTIAL,
            AuthFlow.API_KEY,
            material,
            replace=replace,
        )

    def add_environment(
        self,
        adapter_id: str,
        profile_name: str,
        env_var: str,
        *,
        replace: bool = False,
    ) -> dict[str, Any]:
        self._require_flow(adapter_id, AuthFlow.ENVIRONMENT, AuthMethod.API_CREDENTIAL)
        validate_environment_name(env_var)
        return self._add_profile(
            adapter_id,
            profile_name,
            AuthMethod.API_CREDENTIAL,
            AuthFlow.ENVIRONMENT,
            secret_source="environment",
            source_metadata={"env_var": env_var},
            replace=replace,
        )

    def add_external_command(
        self,
        adapter_id: str,
        profile_name: str,
        argv: Sequence[str],
        *,
        replace: bool = False,
    ) -> dict[str, Any]:
        self._require_flow(adapter_id, AuthFlow.EXTERNAL_COMMAND, AuthMethod.EXTERNAL_SECRET)
        command = self._validated_external_command(argv)
        return self._add_profile(
            adapter_id,
            profile_name,
            AuthMethod.EXTERNAL_SECRET,
            AuthFlow.EXTERNAL_COMMAND,
            secret_source="external_command",
            source_metadata={"argv": command},
            replace=replace,
        )

    def add_browser(
        self,
        adapter_id: str,
        profile_name: str,
        *,
        open_browser: bool = True,
        on_authorization_url: Callable[[str], None] | None = None,
        replace: bool = False,
    ) -> dict[str, Any]:
        descriptor = self._require_flow(
            adapter_id,
            AuthFlow.BROWSER_PKCE,
            AuthMethod.PROVIDER_SUPPORTED_INTERACTIVE,
        )
        if descriptor.browser_oauth is None:
            raise AuthError("adapter has no admitted browser OAuth configuration")
        if type(open_browser) is not bool:
            raise AuthError("open_browser must be a boolean")
        self._assert_profile_available(adapter_id, profile_name, replace=replace)
        ensure_private_auth_root(self.root)
        material = self.browser_flow.authorize(
            descriptor.browser_oauth,
            open_browser=open_browser,
            on_authorization_url=on_authorization_url,
        )
        return self._add_stored(
            adapter_id,
            profile_name,
            AuthMethod.PROVIDER_SUPPORTED_INTERACTIVE,
            AuthFlow.BROWSER_PKCE,
            material,
            replace=replace,
        )

    def add_device(
        self,
        adapter_id: str,
        profile_name: str,
        *,
        on_prompt: Callable[[DeviceAuthorizationPrompt], None],
        replace: bool = False,
    ) -> dict[str, Any]:
        descriptor = self._require_flow(
            adapter_id,
            AuthFlow.DEVICE_CODE,
            AuthMethod.PROVIDER_SUPPORTED_INTERACTIVE,
        )
        if descriptor.device_oauth is None:
            raise AuthError("adapter has no admitted device OAuth configuration")
        self._assert_profile_available(adapter_id, profile_name, replace=replace)
        ensure_private_auth_root(self.root)
        material = self.device_flow.authorize(descriptor.device_oauth, on_prompt=on_prompt)
        return self._add_stored(
            adapter_id,
            profile_name,
            AuthMethod.PROVIDER_SUPPORTED_INTERACTIVE,
            AuthFlow.DEVICE_CODE,
            material,
            replace=replace,
        )

    def test_profile(self, adapter_id: str, profile_name: str = "default") -> dict[str, Any]:
        descriptor = self.registry.get(adapter_id)
        try:
            validate_identifier(profile_name, "profile_name")
            profiles = self.profile_store.load()
        except AuthError as exc:
            return {
                "status": "unavailable",
                "adapter_id": adapter_id,
                "profile_name": profile_name,
                "credential": "unavailable",
                "remote_verified": False,
                "code": self._public_error_code(exc),
            }
        profile = profiles.get(f"{adapter_id}:{profile_name}")
        if profile is None:
            if AuthMethod.NO_AUTH_REQUIRED in descriptor.auth_methods:
                profile = None
            else:
                return {
                    "status": "unavailable",
                    "adapter_id": adapter_id,
                    "profile_name": profile_name,
                    "credential": "profile_missing",
                    "remote_verified": False,
                    "code": "profile_missing",
                }
        try:
            material = self.resolve(adapter_id, profile_name) if profile is not None else None
        except (AuthError, OSError) as exc:
            return {
                "status": "unavailable",
                "adapter_id": adapter_id,
                "profile_name": profile_name,
                "credential": "unavailable",
                "remote_verified": False,
                "code": self._public_error_code(exc),
            }
        tester = self.connection_testers.get(adapter_id)
        if tester is None:
            return {
                "status": "ready",
                "adapter_id": adapter_id,
                "profile_name": profile_name,
                "credential": "available" if material is not None else "not_required",
                "remote_verified": False,
                "code": "provider_test_not_registered",
            }
        try:
            check = tester(material)
            if not isinstance(check, ConnectionCheck):
                raise TypeError("connection tester returned an invalid result")
        except Exception:
            check = ConnectionCheck("unavailable", "provider_test_failed")
        return {
            "status": "ready" if check.status == "healthy" else "unavailable",
            "adapter_id": adapter_id,
            "profile_name": profile_name,
            "credential": "available" if material is not None else "not_required",
            "remote_verified": check.status == "healthy",
            "code": check.code,
        }

    def logout(self, adapter_id: str, profile_name: str = "default") -> dict[str, Any]:
        validate_identifier(adapter_id, "adapter_id")
        validate_identifier(profile_name, "profile_name")
        with self.profile_store.lock:
            profile = self._get_profile(adapter_id, profile_name)
            if profile.secret_source == "stored":
                store = self._secret_store(profile.secret_backend)
                store.delete(profile.credential_handle or "")
            self.profile_store.delete(adapter_id, profile_name)
        return {
            "status": "ok",
            "adapter_id": adapter_id,
            "profile_name": profile_name,
            "credential_removed": profile.secret_source == "stored",
        }

    def resolve(self, adapter_id: str, profile_name: str = "default") -> SecretMaterial | None:
        descriptor = self.registry.get(adapter_id)
        profile = self._get_profile(adapter_id, profile_name)
        if (
            descriptor.implementation_status != "available"
            or profile.auth_method not in descriptor.auth_methods
            or profile.auth_flow not in descriptor.auth_flows
        ):
            raise AuthUnavailableError("auth profile is no longer admitted by its adapter descriptor")
        if profile.secret_source == "none":
            return None
        if profile.secret_source == "environment":
            env_var = profile.source_metadata["env_var"]
            token = self.environment.get(env_var)
            if not token:
                raise AuthUnavailableError("configured credential environment variable is unavailable")
            return SecretMaterial(access_token=token)
        if profile.secret_source == "external_command":
            return self._resolve_external_command(profile)
        if profile.secret_source != "stored":
            raise AuthError("auth profile uses an unsupported secret source")
        store = self._secret_store(profile.secret_backend)
        material = store.get(profile.credential_handle or "")
        if not material.is_expired(self.clock()):
            return material
        with self.profile_store.lock:
            profile = self._get_profile(adapter_id, profile_name)
            if (
                descriptor.implementation_status != "available"
                or profile.auth_method not in descriptor.auth_methods
                or profile.auth_flow not in descriptor.auth_flows
                or profile.secret_source != "stored"
            ):
                raise AuthUnavailableError("auth profile changed while its credential was refreshing")
            store = self._secret_store(profile.secret_backend)
            material = store.get(profile.credential_handle or "")
            if not material.is_expired(self.clock()):
                return material
            if profile.auth_flow is AuthFlow.BROWSER_PKCE:
                config = descriptor.browser_oauth
            elif profile.auth_flow is AuthFlow.DEVICE_CODE:
                config = descriptor.device_oauth
            else:
                config = None
            if config is None:
                raise AuthUnavailableError("stored credential is expired and cannot be refreshed")
            refreshed = self.token_client.refresh(config, material)
            store.put(profile.credential_handle or "", refreshed)
            return refreshed

    def _resolve_external_command(self, profile: AuthProfile) -> SecretMaterial:
        argv = self._validated_external_command(profile.source_metadata["argv"])
        command_environment = dict(self.environment)
        command_environment.update(
            {
                "NEXUS_AUTH_ADAPTER": profile.adapter_id,
                "NEXUS_AUTH_PROFILE": profile.profile_name,
            }
        )
        try:
            process = subprocess.Popen(
                argv,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env=command_environment,
            )
        except OSError as exc:
            raise AuthUnavailableError("external credential helper could not be started") from exc
        output = bytearray()
        overflow = threading.Event()

        def read_bounded_stdout() -> None:
            assert process.stdout is not None
            try:
                while chunk := process.stdout.read(8192):
                    remaining = MAX_EXTERNAL_COMMAND_OUTPUT_BYTES - len(output)
                    if len(chunk) > remaining:
                        output.extend(chunk[: max(0, remaining)])
                        overflow.set()
                        try:
                            process.kill()
                        except ProcessLookupError:
                            pass
                        return
                    output.extend(chunk)
            finally:
                process.stdout.close()

        reader = threading.Thread(target=read_bounded_stdout, daemon=True)
        reader.start()
        try:
            return_code = process.wait(timeout=EXTERNAL_COMMAND_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired as exc:
            process.kill()
            process.wait()
            reader.join(timeout=2)
            raise AuthTimeoutError("external credential helper timed out") from exc
        reader.join(timeout=2)
        if reader.is_alive():
            process.kill()
            process.wait()
            raise AuthUnavailableError("external credential helper output could not be collected")
        if overflow.is_set():
            raise AuthError("external credential helper output exceeded the size limit")
        if return_code != 0:
            raise AuthUnavailableError("external credential helper failed")
        try:
            value = json.loads(bytes(output).decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise AuthError("external credential helper must return a JSON object") from exc
        if not isinstance(value, dict):
            raise AuthError("external credential helper must return a JSON object")
        allowed = {"access_token", "refresh_token", "token_type", "expires_in", "scope"}
        if not set(value).issubset(allowed):
            raise AuthError("external credential helper returned unsupported fields")
        return parse_token_response(value, now=self.clock())

    def _add_stored(
        self,
        adapter_id: str,
        profile_name: str,
        auth_method: AuthMethod,
        auth_flow: AuthFlow,
        material: SecretMaterial,
        *,
        replace: bool,
    ) -> dict[str, Any]:
        validate_identifier(profile_name, "profile_name")
        ensure_private_auth_root(self.root)
        attempted_backend = self.default_secret_backend
        backend = attempted_backend
        store = self._secret_store(attempted_backend)
        handle = f"cred-{uuid.uuid4().hex}"
        backend_fallback = False
        fallback_cleanup_pending = False
        try:
            store.put(handle, material)
        except AuthUnavailableError:
            fallback = self.secret_stores.get(FileSecretStore.backend_id)
            if fallback is None or attempted_backend == FileSecretStore.backend_id:
                raise
            try:
                store.delete(handle)
            except (AuthError, OSError):
                fallback_cleanup_pending = True
            backend = FileSecretStore.backend_id
            store = fallback
            store.put(handle, material)
            backend_fallback = True
        try:
            result = self._add_profile(
                adapter_id,
                profile_name,
                auth_method,
                auth_flow,
                secret_source="stored",
                source_metadata={},
                credential_handle=handle,
                secret_backend=backend,
                replace=replace,
            )
        except Exception:
            try:
                store.delete(handle)
            except (AuthError, OSError):
                pass
            raise
        result["credential_backend_fallback"] = backend_fallback
        if fallback_cleanup_pending:
            result["credential_cleanup_pending"] = True
        return result

    def _add_profile(
        self,
        adapter_id: str,
        profile_name: str,
        auth_method: AuthMethod,
        auth_flow: AuthFlow,
        *,
        secret_source: str,
        source_metadata: Mapping[str, Any],
        credential_handle: str | None = None,
        secret_backend: str | None = None,
        replace: bool,
    ) -> dict[str, Any]:
        validate_identifier(adapter_id, "adapter_id")
        validate_identifier(profile_name, "profile_name")
        if type(replace) is not bool:
            raise AuthError("replace must be a boolean")
        ensure_private_auth_root(self.root)
        with self.profile_store.lock:
            profiles = self.profile_store.load()
            profile_id = f"{adapter_id}:{profile_name}"
            previous = profiles.get(profile_id)
            if previous is not None and not replace:
                raise AuthError(f"auth profile {profile_id} already exists")
            now = self.clock()
            profile = AuthProfile(
                adapter_id=adapter_id,
                profile_name=profile_name,
                auth_method=auth_method,
                auth_flow=auth_flow,
                secret_source=secret_source,
                source_metadata=dict(source_metadata),
                credential_handle=credential_handle,
                secret_backend=secret_backend,
                created_at=previous.created_at if previous is not None else now,
                updated_at=now,
            )
            previous = self.profile_store.upsert(profile, replace=replace)
        cleanup_warning = False
        if previous is not None and previous.secret_source == "stored":
            if previous.credential_handle != credential_handle or previous.secret_backend != secret_backend:
                try:
                    old_store = self._secret_store(previous.secret_backend)
                    old_store.delete(previous.credential_handle or "")
                except (AuthError, OSError):
                    # The new profile is already committed and usable. Do not
                    # roll it back to a deleted credential; report only a
                    # non-secret cleanup condition for the operator.
                    cleanup_warning = True
        return {
            "status": "ok",
            "profile": profile.public_dict(),
            "replaced": previous is not None,
            "credential_cleanup_pending": cleanup_warning,
        }

    def _require_flow(
        self,
        adapter_id: str,
        flow: AuthFlow,
        method: AuthMethod,
    ) -> AdapterAuthDescriptor:
        descriptor = self.registry.get(adapter_id)
        if flow not in descriptor.auth_flows or method not in descriptor.auth_methods:
            raise AuthError(f"adapter {adapter_id} does not support auth flow {flow.value}")
        if descriptor.implementation_status != "available":
            raise AuthUnavailableError(f"adapter {adapter_id} authentication is not admitted")
        return descriptor

    def _get_profile(self, adapter_id: str, profile_name: str) -> AuthProfile:
        validate_identifier(adapter_id, "adapter_id")
        validate_identifier(profile_name, "profile_name")
        profile_id = f"{adapter_id}:{profile_name}"
        try:
            return self.profile_store.load()[profile_id]
        except KeyError as exc:
            raise AuthError(f"auth profile {profile_id} does not exist") from exc

    def _assert_profile_available(self, adapter_id: str, profile_name: str, *, replace: bool) -> None:
        validate_identifier(adapter_id, "adapter_id")
        validate_identifier(profile_name, "profile_name")
        if type(replace) is not bool:
            raise AuthError("replace must be a boolean")
        if not replace and f"{adapter_id}:{profile_name}" in self.profile_store.load():
            raise AuthError(f"auth profile {adapter_id}:{profile_name} already exists")

    def _secret_store(self, backend: str | None) -> SecretStore:
        if backend is None:
            raise AuthError("auth profile does not name a credential backend")
        try:
            return self.secret_stores[backend]
        except KeyError as exc:
            raise AuthUnavailableError("configured credential backend is unavailable") from exc

    @staticmethod
    def _public_error_code(exc: BaseException) -> str:
        if isinstance(exc, AuthTimeoutError):
            return "auth_timeout"
        if isinstance(exc, AuthUnavailableError):
            return "credential_unavailable"
        return "auth_invalid"

    @staticmethod
    def _validated_external_command(argv: Sequence[str]) -> list[str]:
        command = list(argv)
        if (
            not command
            or len(command) > 64
            or not all(
                isinstance(item, str)
                and item
                and len(item) <= 4096
                and "\x00" not in item
                and "\r" not in item
                and "\n" not in item
                for item in command
            )
            or sum(len(item) for item in command) > 32_768
        ):
            raise AuthError("external command must be a bounded non-empty argv list")
        if not Path(command[0]).is_absolute():
            raise AuthError("external credential helper executable must use an absolute path")
        if any(_SECRET_BEARING_HELPER_OPTION.match(item) for item in command[1:]):
            raise AuthError("external credential helper argv must not contain credential-bearing options")
        scrubber = SecretScrubber()
        if any(scrubber.scrub(item).changed for item in command):
            raise AuthError("external credential helper argv must not contain credential-shaped text")
        return command
