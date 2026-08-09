from typing import Any, Mapping, Sequence

from .broker import AdapterAuthRegistry, AuthBroker as _BaseAuthBroker, ConnectionCheck
from .oauth import BrowserPKCEFlow, DeviceAuthorizationPrompt, DeviceCodeFlow, OAuthTokenClient
from .storage import ensure_disjoint_auth_world_roots
from .types import (
    AUTH_SCHEMA_VERSION,
    AdapterAuthDescriptor,
    AuthError,
    AuthFlow,
    AuthMethod,
    AuthProfile,
    AuthProtocolError,
    AuthTimeoutError,
    AuthUnavailableError,
    BrowserOAuthConfig,
    DeviceOAuthConfig,
    SecretMaterial,
)


class AuthBroker(_BaseAuthBroker):
    """Public broker with the built-in fixed-host cloud provider registry."""

    def __init__(
        self,
        root: Any = None,
        *,
        descriptors: Sequence[AdapterAuthDescriptor] = (),
        connection_testers: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        # Import lazily so adapters can depend on auth.types without creating a
        # package-import cycle through nexus_runtime.auth.__init__.
        from ..adapters.third_party import third_party_auth_descriptors, third_party_connection_testers

        merged_descriptors = (*third_party_auth_descriptors(), *descriptors)
        if connection_testers is None:
            from ..adapters.xai import xai_connection_test

            connection_testers = {
                "xai": xai_connection_test,
                **third_party_connection_testers(),
            }
        super().__init__(
            root,
            descriptors=merged_descriptors,
            connection_testers=connection_testers,
            **kwargs,
        )


__all__ = [
    "AUTH_SCHEMA_VERSION",
    "AdapterAuthDescriptor",
    "AdapterAuthRegistry",
    "AuthBroker",
    "AuthError",
    "AuthFlow",
    "AuthMethod",
    "AuthProfile",
    "AuthProtocolError",
    "AuthTimeoutError",
    "AuthUnavailableError",
    "BrowserOAuthConfig",
    "BrowserPKCEFlow",
    "ConnectionCheck",
    "DeviceAuthorizationPrompt",
    "DeviceCodeFlow",
    "DeviceOAuthConfig",
    "ensure_disjoint_auth_world_roots",
    "OAuthTokenClient",
    "SecretMaterial",
]
