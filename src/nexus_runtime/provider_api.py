from __future__ import annotations

from typing import Any

from .adapters import (
    LOCAL_AI_ADAPTER_IDS,
    THIRD_PARTY_PROVIDER_IDS,
    LocalAIActor,
    LocalAITransport,
    ThirdPartyActor,
    ThirdPartyTransport,
)
from .api import MAX_REMOTE_COUNCIL_SEATS, NexusAPI as CoreNexusAPI
from .local_role_runtime import LocalAwareCitizenship, LocalAwareFailsafe
from .local_roles import LocalRoleBackendConfig, LocalRoleRegistry
from .types import CouncilMember


REMOTE_PROVIDER_IDS = frozenset({"xai", *THIRD_PARTY_PROVIDER_IDS})
_LOCAL_ROLE_OPERATIONS = frozenset(
    {"local.roles.status", "local.roles.configure", "local.roles.clear"}
)


class ProviderNexusAPI(CoreNexusAPI):
    """NEXUS API with fixed-host cloud and loopback-local provider admission.

    Cloud credentials remain AuthBroker profiles. Local AI credentials are
    optional ephemeral environment references and never become world state.
    Optional local role substitution enriches deterministic Failsafe/civic
    language while the wrapped deterministic role remains authoritative for
    seat identity and ballots.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.local_roles = LocalRoleRegistry()
        self.citizenship = LocalAwareCitizenship(self.citizenship, self.local_roles)
        self.council.failsafe = LocalAwareFailsafe(self.council.failsafe, self.local_roles)

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        operation = request.get("operation")
        # CoreNexusAPI owns malformed/unknown operation validation. Guard the
        # provider-specific membership test so unhashable JSON shapes (arrays,
        # objects) cannot escape the structured error boundary as TypeError.
        if isinstance(operation, str) and operation in _LOCAL_ROLE_OPERATIONS:
            response = self._handle_local_role_operation(request)
        else:
            response = super().handle(request)

        if operation == "system.health" and response.get("status") == "ok":
            response = dict(response)
            response["network"] = (
                "local_stdio_with_loopback_local_ai_or_fixed_remote_provider_https_"
                "or_registered_auth_operations"
            )
            response["adapters"] = [
                "mock",
                "ollama_loopback",
                *[f"{adapter_id}_loopback" for adapter_id in sorted(LOCAL_AI_ADAPTER_IDS)],
                "xai_https",
                *[f"{adapter_id}_https" for adapter_id in sorted(THIRD_PARTY_PROVIDER_IDS)],
            ]
            response["actor_backends_available"] = [
                "mock",
                "ollama",
                *sorted(LOCAL_AI_ADAPTER_IDS),
                "xai",
                *sorted(THIRD_PARTY_PROVIDER_IDS),
            ]
            response["local_roles"] = self.local_roles.status()
        elif operation == "system.operations" and response.get("status") == "ok":
            response = dict(response)
            operations = list(response.get("operations", []))
            operations.extend(sorted(_LOCAL_ROLE_OPERATIONS))
            response["operations"] = sorted(set(operations))
        return response

    def _handle_local_role_operation(self, request: dict[str, Any]) -> dict[str, Any]:
        request_id = request.get("request_id")
        if request_id is not None and (
            not isinstance(request_id, str)
            or not request_id
            or len(request_id) > 128
            or any(
                character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._:-"
                for character in request_id
            )
            or self.scrubber.scrub(request_id).changed
        ):
            return self._error(None, "invalid_request", "request_id must be a bounded non-secret identifier")
        operation = request.get("operation")
        try:
            if operation == "local.roles.status":
                self._require_exact_fields(request, operation, set())
                response = self.local_roles.status()
            elif operation == "local.roles.configure":
                self._require_exact_fields(request, operation, {"role_id", "backend"})
                role_id = self._require_str(request, "role_id")
                backend = request.get("backend")
                if not isinstance(backend, dict):
                    raise ValueError("backend must be an object")
                response = self.local_roles.configure(role_id, backend)
            elif operation == "local.roles.clear":
                self._require_exact_fields(request, operation, {"role_id"})
                response = self.local_roles.clear(self._require_str(request, "role_id"))
            else:  # pragma: no cover - dispatch set is closed above
                return self._error(request_id, "unknown_operation", "operation is not supported")
        except (KeyError, TypeError, ValueError) as exc:
            return self._error(request_id, "invalid_request", str(exc))
        if request_id is not None:
            response = {"request_id": request_id, **response}
        return response

    @staticmethod
    def _validate_council_request_limits(members: list[Any]) -> None:
        CoreNexusAPI._validate_council_request_limits(members)
        remote_seats = sum(
            1
            for item in members
            if isinstance(item, dict) and item.get("adapter_id", "mock") in REMOTE_PROVIDER_IDS
        )
        if remote_seats > MAX_REMOTE_COUNCIL_SEATS:
            raise ValueError(
                f"Council permits at most {MAX_REMOTE_COUNCIL_SEATS} remote provider seats"
            )

    def _actor(self, item: Any) -> Any:
        if not isinstance(item, dict):
            raise ValueError("each member must be an object")
        adapter_id = item.get("adapter_id", "mock")
        if not isinstance(adapter_id, str):
            raise ValueError("adapter_id must be a string")
        if adapter_id in LOCAL_AI_ADAPTER_IDS:
            return self._local_ai_actor(item, adapter_id)
        if adapter_id not in THIRD_PARTY_PROVIDER_IDS:
            return super()._actor(item)

        allowed = {
            "member_id",
            "model_id",
            "adapter_id",
            "deployment_metadata",
            "capability_metadata",
            "vote_weight",
            "epistemic_privilege",
            "auth_profile",
            "timeout_seconds",
        }
        unknown = set(item) - allowed
        if unknown:
            raise ValueError(
                f"{adapter_id} member contains unsupported fields: {', '.join(sorted(unknown))}"
            )

        member = CouncilMember(
            member_id=self._member_identity(item, "member_id"),
            model_id=self._member_identity(item, "model_id"),
            adapter_id=adapter_id,
            deployment_metadata=self._member_metadata(item, "deployment_metadata"),
            capability_metadata=self._member_metadata(item, "capability_metadata"),
            vote_weight=item.get("vote_weight", 1),
            epistemic_privilege=item.get("epistemic_privilege", "none"),
        )
        profile_name = item.get("auth_profile", "default")
        if not isinstance(profile_name, str) or not profile_name:
            raise ValueError(f"{adapter_id} auth_profile must be a non-empty string")
        timeout_seconds = item.get("timeout_seconds", 600)
        material = self.auth.resolve(adapter_id, profile_name)
        if material is None:
            raise ValueError(f"{adapter_id} auth profile did not resolve a credential")
        return ThirdPartyActor(
            member=member,
            model=member.model_id,
            transport=ThirdPartyTransport(
                adapter_id,
                material,
                timeout_seconds=timeout_seconds,
            ),
        )

    def _local_ai_actor(self, item: dict[str, Any], adapter_id: str) -> LocalAIActor:
        allowed = {
            "member_id",
            "model_id",
            "adapter_id",
            "deployment_metadata",
            "capability_metadata",
            "vote_weight",
            "epistemic_privilege",
            "endpoint",
            "credential_env",
            "model",
            "workspace",
            "mcp_plugins",
            "timeout_seconds",
            "max_output_tokens",
        }
        unknown = set(item) - allowed
        if unknown:
            raise ValueError(
                f"{adapter_id} member contains unsupported fields: {', '.join(sorted(unknown))}"
            )
        member = CouncilMember(
            member_id=self._member_identity(item, "member_id"),
            model_id=self._member_identity(item, "model_id"),
            adapter_id=adapter_id,
            deployment_metadata=self._member_metadata(item, "deployment_metadata"),
            capability_metadata=self._member_metadata(item, "capability_metadata"),
            vote_weight=item.get("vote_weight", 1),
            epistemic_privilege=item.get("epistemic_privilege", "none"),
        )
        backend_fields = {
            key: item[key]
            for key in (
                "endpoint",
                "credential_env",
                "model",
                "workspace",
                "mcp_plugins",
                "timeout_seconds",
                "max_output_tokens",
            )
            if key in item
        }
        backend_fields["adapter_id"] = adapter_id
        if adapter_id != "anythingllm_local" and "model" not in backend_fields:
            backend_fields["model"] = member.model_id
        backend = LocalRoleBackendConfig.from_request("failsafe_relief", backend_fields)
        return LocalAIActor(
            member=member,
            transport=LocalAITransport(
                adapter_id,
                endpoint=backend.endpoint,
                credential=self.local_roles._credential(backend),
                timeout_seconds=backend.timeout_seconds,
            ),
            model=backend.model,
            workspace=backend.workspace,
            mcp_plugins=backend.mcp_plugins,
            max_output_tokens=backend.max_output_tokens,
        )

    def _list_models(
        self,
        adapter_id: str,
        profile_name: str,
        timeout_seconds: Any,
    ) -> dict[str, Any]:
        if adapter_id not in THIRD_PARTY_PROVIDER_IDS:
            return super()._list_models(adapter_id, profile_name, timeout_seconds)
        material = self.auth.resolve(adapter_id, profile_name)
        if material is None:
            raise ValueError(f"{adapter_id} auth profile did not resolve a credential")
        models = ThirdPartyTransport(
            adapter_id,
            material,
            timeout_seconds=timeout_seconds,
        ).list_language_models()
        return {
            "status": "ok",
            "adapter_id": adapter_id,
            "profile_name": profile_name,
            "remote_verified": True,
            "model_count": len(models),
            "models": models,
        }
