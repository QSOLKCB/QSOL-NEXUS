from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
from pathlib import Path
import re
from typing import Any, Mapping
from urllib.parse import urlsplit


AUTH_SCHEMA_VERSION = "nexus-auth/1"
PROFILE_STORE_SCHEMA_VERSION = "nexus-auth-profiles/1"
SECRET_STORE_SCHEMA_VERSION = "nexus-auth-secret/1"
MAX_SECRET_TOKEN_LENGTH = 65_536

_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_ENVIRONMENT_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
_CREDENTIAL_HANDLE = re.compile(r"^[a-z0-9][a-z0-9-]{15,127}$")
_TOKEN_TYPE = re.compile(r"^[A-Za-z][A-Za-z0-9._~+/-]{0,31}$")
_OAUTH_PARAMETER_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9._~-]{0,63}$")


class AuthError(ValueError):
    """Base class for sanitized authentication failures."""


class AuthUnavailableError(AuthError):
    """The configured credential source or provider cannot be reached."""


class AuthProtocolError(AuthError):
    """A provider returned a response outside the admitted auth contract."""


class AuthTimeoutError(AuthError):
    """An interactive or external authentication operation timed out."""


class AuthMethod(str, Enum):
    API_CREDENTIAL = "api_credential"
    PROVIDER_SUPPORTED_INTERACTIVE = "provider_supported_interactive"
    EXTERNAL_SECRET = "external_secret"
    LOCAL_ENDPOINT = "local_endpoint"
    NO_AUTH_REQUIRED = "no_auth_required"


class AuthFlow(str, Enum):
    API_KEY = "api_key"
    BROWSER_PKCE = "browser_pkce"
    DEVICE_CODE = "device_code"
    ENVIRONMENT = "environment"
    EXTERNAL_COMMAND = "external_command"
    LOCAL_ENDPOINT = "local_endpoint"
    NONE = "none"


def validate_identifier(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise AuthError(f"{field_name} must match {_IDENTIFIER.pattern}")
    return value


def validate_environment_name(value: str) -> str:
    if not isinstance(value, str) or not _ENVIRONMENT_NAME.fullmatch(value):
        raise AuthError("environment variable name is invalid")
    return value


def validate_credential_handle(value: str) -> str:
    if not isinstance(value, str) or not _CREDENTIAL_HANDLE.fullmatch(value):
        raise AuthError("credential handle is invalid")
    return value


def _validated_endpoint(
    value: str,
    *,
    allowed_hosts: tuple[str, ...],
    allow_insecure_loopback: bool,
    field_name: str,
) -> str:
    if not isinstance(value, str):
        raise AuthError(f"{field_name} must be a URL")
    parsed = urlsplit(value)
    if parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment:
        raise AuthError(f"{field_name} must not contain user-info, a query, or a fragment")
    host = (parsed.hostname or "").lower()
    normalized_hosts = {item.lower() for item in allowed_hosts}
    if not host or host not in normalized_hosts:
        raise AuthError(f"{field_name} host is not admitted by the adapter descriptor")
    if parsed.scheme == "https":
        return value
    if allow_insecure_loopback and parsed.scheme == "http" and host in {"127.0.0.1", "::1"}:
        return value
    raise AuthError(f"{field_name} must use HTTPS")


def _valid_oauth_string(value: str, *, maximum: int) -> bool:
    return (
        isinstance(value, str)
        and 0 < len(value) <= maximum
        and all(0x21 <= ord(character) <= 0x7E for character in value)
    )


@dataclass(frozen=True)
class BrowserOAuthConfig:
    authorization_endpoint: str
    token_endpoint: str
    client_id: str
    scopes: tuple[str, ...]
    allowed_endpoint_hosts: tuple[str, ...]
    extra_authorization_params: tuple[tuple[str, str], ...] = ()
    callback_timeout_seconds: float = 180.0
    allow_insecure_loopback_provider: bool = False

    def __post_init__(self) -> None:
        if type(self.allow_insecure_loopback_provider) is not bool:
            raise AuthError("allow_insecure_loopback_provider must be a boolean")
        if not _valid_oauth_string(self.client_id, maximum=512):
            raise AuthError("OAuth client_id must be non-empty")
        if (
            not isinstance(self.scopes, tuple)
            or not self.scopes
            or len(self.scopes) > 128
            or not all(_valid_oauth_string(scope, maximum=128) for scope in self.scopes)
            or len(set(self.scopes)) != len(self.scopes)
        ):
            raise AuthError("OAuth scopes must be non-empty strings")
        if (
            not isinstance(self.allowed_endpoint_hosts, tuple)
            or not self.allowed_endpoint_hosts
            or not all(
                isinstance(host, str) and host and host == host.lower() for host in self.allowed_endpoint_hosts
            )
            or len(set(self.allowed_endpoint_hosts)) != len(self.allowed_endpoint_hosts)
        ):
            raise AuthError("OAuth endpoint allowlist must not be empty")
        if (
            isinstance(self.callback_timeout_seconds, bool)
            or not isinstance(self.callback_timeout_seconds, (int, float))
            or not math.isfinite(self.callback_timeout_seconds)
            or self.callback_timeout_seconds <= 0
        ):
            raise AuthError("OAuth callback timeout must be positive and finite")
        _validated_endpoint(
            self.authorization_endpoint,
            allowed_hosts=self.allowed_endpoint_hosts,
            allow_insecure_loopback=self.allow_insecure_loopback_provider,
            field_name="authorization_endpoint",
        )
        _validated_endpoint(
            self.token_endpoint,
            allowed_hosts=self.allowed_endpoint_hosts,
            allow_insecure_loopback=self.allow_insecure_loopback_provider,
            field_name="token_endpoint",
        )
        reserved = {
            "client_id",
            "code_challenge",
            "code_challenge_method",
            "redirect_uri",
            "response_type",
            "scope",
            "state",
        }
        if not isinstance(self.extra_authorization_params, tuple) or not all(
            isinstance(item, tuple) and len(item) == 2 for item in self.extra_authorization_params
        ):
            raise AuthError("extra OAuth authorization parameters must be key/value pairs")
        keys: set[str] = set()
        for key, value in self.extra_authorization_params:
            if not isinstance(key, str) or not _OAUTH_PARAMETER_NAME.fullmatch(key) or key in reserved or key in keys:
                raise AuthError("extra OAuth authorization parameters contain an invalid or reserved key")
            if (
                not isinstance(value, str)
                or len(value) > 2048
                or any(ord(character) < 0x20 or ord(character) > 0x7E for character in value)
            ):
                raise AuthError("extra OAuth authorization parameter values must be strings")
            keys.add(key)


@dataclass(frozen=True)
class DeviceOAuthConfig:
    device_authorization_endpoint: str
    token_endpoint: str
    client_id: str
    scopes: tuple[str, ...]
    allowed_endpoint_hosts: tuple[str, ...]
    allowed_verification_hosts: tuple[str, ...]
    allow_insecure_loopback_provider: bool = False

    def __post_init__(self) -> None:
        if type(self.allow_insecure_loopback_provider) is not bool:
            raise AuthError("allow_insecure_loopback_provider must be a boolean")
        if not _valid_oauth_string(self.client_id, maximum=512):
            raise AuthError("OAuth client_id must be non-empty")
        if (
            not isinstance(self.scopes, tuple)
            or not self.scopes
            or len(self.scopes) > 128
            or not all(_valid_oauth_string(scope, maximum=128) for scope in self.scopes)
            or len(set(self.scopes)) != len(self.scopes)
        ):
            raise AuthError("OAuth scopes must be non-empty strings")
        if (
            not isinstance(self.allowed_endpoint_hosts, tuple)
            or not self.allowed_endpoint_hosts
            or not all(
                isinstance(host, str) and host and host == host.lower() for host in self.allowed_endpoint_hosts
            )
            or len(set(self.allowed_endpoint_hosts)) != len(self.allowed_endpoint_hosts)
        ):
            raise AuthError("OAuth endpoint allowlist must not be empty")
        if (
            not isinstance(self.allowed_verification_hosts, tuple)
            or not self.allowed_verification_hosts
            or not all(
                isinstance(host, str) and host and host == host.lower()
                for host in self.allowed_verification_hosts
            )
            or len(set(self.allowed_verification_hosts)) != len(self.allowed_verification_hosts)
        ):
            raise AuthError("OAuth verification-URL allowlist must not be empty")
        _validated_endpoint(
            self.device_authorization_endpoint,
            allowed_hosts=self.allowed_endpoint_hosts,
            allow_insecure_loopback=self.allow_insecure_loopback_provider,
            field_name="device_authorization_endpoint",
        )
        _validated_endpoint(
            self.token_endpoint,
            allowed_hosts=self.allowed_endpoint_hosts,
            allow_insecure_loopback=self.allow_insecure_loopback_provider,
            field_name="token_endpoint",
        )


@dataclass(frozen=True)
class AdapterAuthDescriptor:
    adapter_id: str
    provider_name: str
    local_or_remote: str
    auth_methods: tuple[AuthMethod, ...]
    auth_flows: tuple[AuthFlow, ...]
    browser_oauth: BrowserOAuthConfig | None = None
    device_oauth: DeviceOAuthConfig | None = None
    implementation_status: str = "available"

    def __post_init__(self) -> None:
        validate_identifier(self.adapter_id, "adapter_id")
        if (
            not isinstance(self.provider_name, str)
            or not self.provider_name.strip()
            or len(self.provider_name) > 128
            or any(ord(character) < 0x20 for character in self.provider_name)
        ):
            raise AuthError("provider_name must be non-empty")
        if self.local_or_remote not in {"local", "remote"}:
            raise AuthError("local_or_remote must be local or remote")
        if (
            not self.auth_methods
            or not all(isinstance(method, AuthMethod) for method in self.auth_methods)
            or len(set(self.auth_methods)) != len(self.auth_methods)
        ):
            raise AuthError("auth_methods must be non-empty and unique")
        if (
            not self.auth_flows
            or not all(isinstance(flow, AuthFlow) for flow in self.auth_flows)
            or len(set(self.auth_flows)) != len(self.auth_flows)
        ):
            raise AuthError("auth_flows must be non-empty and unique")
        if AuthFlow.BROWSER_PKCE in self.auth_flows and self.browser_oauth is None:
            raise AuthError("browser_pkce requires provider-owned OAuth configuration")
        if AuthFlow.BROWSER_PKCE not in self.auth_flows and self.browser_oauth is not None:
            raise AuthError("browser OAuth configuration requires the browser_pkce flow")
        if AuthFlow.DEVICE_CODE in self.auth_flows and self.device_oauth is None:
            raise AuthError("device_code requires provider-owned OAuth configuration")
        if AuthFlow.DEVICE_CODE not in self.auth_flows and self.device_oauth is not None:
            raise AuthError("device OAuth configuration requires the device_code flow")
        required_methods = {
            AuthFlow.API_KEY: AuthMethod.API_CREDENTIAL,
            AuthFlow.BROWSER_PKCE: AuthMethod.PROVIDER_SUPPORTED_INTERACTIVE,
            AuthFlow.DEVICE_CODE: AuthMethod.PROVIDER_SUPPORTED_INTERACTIVE,
            AuthFlow.ENVIRONMENT: AuthMethod.API_CREDENTIAL,
            AuthFlow.EXTERNAL_COMMAND: AuthMethod.EXTERNAL_SECRET,
            AuthFlow.LOCAL_ENDPOINT: AuthMethod.LOCAL_ENDPOINT,
            AuthFlow.NONE: AuthMethod.NO_AUTH_REQUIRED,
        }
        if any(required_methods[flow] not in self.auth_methods for flow in self.auth_flows):
            raise AuthError("auth flow is missing its required authentication method")
        if self.implementation_status not in {"available", "planned", "disabled"}:
            raise AuthError("implementation_status must be available, planned, or disabled")

    def public_dict(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "provider_name": self.provider_name,
            "local_or_remote": self.local_or_remote,
            "auth_methods": [method.value for method in self.auth_methods],
            "auth_flows": [flow.value for flow in self.auth_flows],
            "implementation_status": self.implementation_status,
        }


@dataclass(frozen=True, repr=False)
class SecretMaterial:
    access_token: str = field(repr=False)
    refresh_token: str | None = field(default=None, repr=False)
    token_type: str = "Bearer"
    expires_at: float | None = None
    scopes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not _valid_oauth_string(self.access_token, maximum=MAX_SECRET_TOKEN_LENGTH):
            raise AuthProtocolError("credential source did not return an access token")
        if self.refresh_token is not None and not _valid_oauth_string(
            self.refresh_token,
            maximum=MAX_SECRET_TOKEN_LENGTH,
        ):
            raise AuthProtocolError("refresh token must be non-empty when supplied")
        if not isinstance(self.token_type, str) or not _TOKEN_TYPE.fullmatch(self.token_type):
            raise AuthProtocolError("token type is invalid")
        if self.expires_at is not None and (
            isinstance(self.expires_at, bool)
            or not isinstance(self.expires_at, (int, float))
            or not math.isfinite(float(self.expires_at))
        ):
            raise AuthProtocolError("credential expiry is invalid")
        if (
            not isinstance(self.scopes, tuple)
            or len(self.scopes) > 128
            or not all(_valid_oauth_string(scope, maximum=128) for scope in self.scopes)
        ):
            raise AuthProtocolError("credential scopes are invalid")

    def __repr__(self) -> str:
        return (
            "SecretMaterial(access_token=<redacted>, refresh_token="
            f"{'<redacted>' if self.refresh_token else 'None'}, token_type={self.token_type!r}, "
            f"expires_at={self.expires_at!r}, scopes={self.scopes!r})"
        )

    def is_expired(self, now: float, *, skew_seconds: float = 30.0) -> bool:
        return self.expires_at is not None and self.expires_at <= now + skew_seconds

    def storage_dict(self) -> dict[str, Any]:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_type": self.token_type,
            "expires_at": self.expires_at,
            "scopes": list(self.scopes),
        }

    @classmethod
    def from_storage_dict(cls, value: Mapping[str, Any]) -> "SecretMaterial":
        expected = {"access_token", "refresh_token", "token_type", "expires_at", "scopes"}
        if set(value) != expected:
            raise AuthProtocolError("stored credential schema is invalid")
        scopes = value["scopes"]
        if not isinstance(scopes, list):
            raise AuthProtocolError("stored credential scopes are invalid")
        return cls(
            access_token=value["access_token"],
            refresh_token=value["refresh_token"],
            token_type=value["token_type"],
            expires_at=value["expires_at"],
            scopes=tuple(scopes),
        )


@dataclass(frozen=True)
class AuthProfile:
    adapter_id: str
    profile_name: str
    auth_method: AuthMethod
    auth_flow: AuthFlow
    secret_source: str
    source_metadata: Mapping[str, Any]
    credential_handle: str | None
    secret_backend: str | None
    created_at: float
    updated_at: float

    def __post_init__(self) -> None:
        validate_identifier(self.adapter_id, "adapter_id")
        validate_identifier(self.profile_name, "profile_name")
        if not isinstance(self.auth_method, AuthMethod) or not isinstance(self.auth_flow, AuthFlow):
            raise AuthError("profile auth method and flow must use admitted enum values")
        if self.secret_source not in {"stored", "environment", "external_command", "none"}:
            raise AuthError("profile secret_source is invalid")
        if (
            isinstance(self.created_at, bool)
            or not isinstance(self.created_at, (int, float))
            or not math.isfinite(float(self.created_at))
        ):
            raise AuthError("profile created_at is invalid")
        if (
            isinstance(self.updated_at, bool)
            or not isinstance(self.updated_at, (int, float))
            or not math.isfinite(float(self.updated_at))
            or self.updated_at < self.created_at
        ):
            raise AuthError("profile updated_at is invalid")
        if self.secret_source == "stored":
            if self.credential_handle is None or self.secret_backend is None:
                raise AuthError("stored profile requires a credential handle and backend")
            validate_credential_handle(self.credential_handle)
            validate_identifier(self.secret_backend, "secret_backend")
        elif self.credential_handle is not None or self.secret_backend is not None:
            raise AuthError("non-stored profile must not name a credential handle or backend")
        if self.secret_source == "environment":
            if set(self.source_metadata) != {"env_var"}:
                raise AuthError("environment profile metadata is invalid")
            validate_environment_name(self.source_metadata["env_var"])
        elif self.secret_source == "external_command":
            if set(self.source_metadata) != {"argv"}:
                raise AuthError("external-command profile metadata is invalid")
            argv = self.source_metadata["argv"]
            if (
                not isinstance(argv, list)
                or not argv
                or len(argv) > 64
                or not all(
                    isinstance(item, str)
                    and item
                    and len(item) <= 4096
                    and "\x00" not in item
                    and "\r" not in item
                    and "\n" not in item
                    for item in argv
                )
                or sum(len(item) for item in argv) > 32_768
                or not Path(argv[0]).is_absolute()
            ):
                raise AuthError("external command argv must be a non-empty string list")
        elif self.source_metadata:
            raise AuthError("stored and no-auth profiles must not carry source metadata")
        expected_contract = {
            AuthFlow.API_KEY: (AuthMethod.API_CREDENTIAL, "stored"),
            AuthFlow.BROWSER_PKCE: (AuthMethod.PROVIDER_SUPPORTED_INTERACTIVE, "stored"),
            AuthFlow.DEVICE_CODE: (AuthMethod.PROVIDER_SUPPORTED_INTERACTIVE, "stored"),
            AuthFlow.ENVIRONMENT: (AuthMethod.API_CREDENTIAL, "environment"),
            AuthFlow.EXTERNAL_COMMAND: (AuthMethod.EXTERNAL_SECRET, "external_command"),
            AuthFlow.LOCAL_ENDPOINT: (AuthMethod.LOCAL_ENDPOINT, "none"),
            AuthFlow.NONE: (AuthMethod.NO_AUTH_REQUIRED, "none"),
        }[self.auth_flow]
        if (self.auth_method, self.secret_source) != expected_contract:
            raise AuthError("auth profile method, flow, and secret-source contract is inconsistent")

    @property
    def profile_id(self) -> str:
        return f"{self.adapter_id}:{self.profile_name}"

    def storage_dict(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "profile_name": self.profile_name,
            "auth_method": self.auth_method.value,
            "auth_flow": self.auth_flow.value,
            "secret_source": self.secret_source,
            "source_metadata": dict(self.source_metadata),
            "credential_handle": self.credential_handle,
            "secret_backend": self.secret_backend,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_storage_dict(cls, value: Mapping[str, Any]) -> "AuthProfile":
        expected = {
            "adapter_id",
            "profile_name",
            "auth_method",
            "auth_flow",
            "secret_source",
            "source_metadata",
            "credential_handle",
            "secret_backend",
            "created_at",
            "updated_at",
        }
        if set(value) != expected:
            raise AuthError("stored auth profile schema is invalid")
        source_metadata = value["source_metadata"]
        if not isinstance(source_metadata, dict):
            raise AuthError("stored auth source metadata is invalid")
        try:
            method = AuthMethod(value["auth_method"])
            flow = AuthFlow(value["auth_flow"])
        except (TypeError, ValueError) as exc:
            raise AuthError("stored auth method or flow is invalid") from exc
        return cls(
            adapter_id=value["adapter_id"],
            profile_name=value["profile_name"],
            auth_method=method,
            auth_flow=flow,
            secret_source=value["secret_source"],
            source_metadata=source_metadata,
            credential_handle=value["credential_handle"],
            secret_backend=value["secret_backend"],
            created_at=value["created_at"],
            updated_at=value["updated_at"],
        )

    def public_dict(self) -> dict[str, Any]:
        source: dict[str, Any] = {"kind": self.secret_source}
        if self.secret_source == "environment":
            source["env_var"] = self.source_metadata["env_var"]
        elif self.secret_source == "external_command":
            argv = self.source_metadata["argv"]
            source["executable"] = argv[0].rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        elif self.secret_source == "stored":
            source["backend"] = self.secret_backend
        return {
            "profile_id": self.profile_id,
            "adapter_id": self.adapter_id,
            "profile_name": self.profile_name,
            "auth_method": self.auth_method.value,
            "auth_flow": self.auth_flow.value,
            "source": source,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
