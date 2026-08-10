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
from .citizenship import PAROLE_MODE_ID
from .council_chair import (
    chair_policy_snapshot,
    evaluate_council_roster_request,
    validate_council_roster_request,
)
from .local_role_runtime import LocalAwareCitizenship, LocalAwareFailsafe
from .local_roles import LocalRoleBackendConfig, LocalRoleRegistry
from .trap.types import TrapError
from .types import CouncilMember


REMOTE_PROVIDER_IDS = frozenset({"xai", *THIRD_PARTY_PROVIDER_IDS})
_LOCAL_ROLE_OPERATIONS = frozenset(
    {"local.roles.status", "local.roles.configure", "local.roles.clear"}
)
_REQUEST_ID_CHARS = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._:-"
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

        # Civic parole is constitutionally non-Council. Preserve that semantic
        # error ahead of voting-roster admission, but never ahead of Trap Base's
        # real-world mutation quarantine. Invalid request IDs still fall through
        # to the core validator so this preflight cannot weaken the envelope.
        if (
            operation == "council.run"
            and request.get("mode", "analytical") == PAROLE_MODE_ID
            and self._request_id_is_preflight_safe(request.get("request_id"))
        ):
            try:
                self.trap_mutation_gate.assert_mutation_allowed()
            except TrapError as exc:
                return self._error(request.get("request_id"), exc.code, str(exc))
            return self._error(
                request.get("request_id"),
                "citizen_parole_has_no_council",
                "civic parole has no Council ballot; submit the deterministic YAML exam instead",
            )

        # CoreNexusAPI owns malformed/unknown operation validation. Guard the
        # provider-specific membership test so unhashable JSON shapes (arrays,
        # objects) cannot escape the structured error boundary as TypeError.
        try:
            if isinstance(operation, str) and operation in _LOCAL_ROLE_OPERATIONS:
                response = self._handle_local_role_operation(request)
            else:
                response = super().handle(request)
        except OverflowError:
            # A pathological JSON integer must never tear down the JSONL
            # runtime merely because a lower-level numeric conversion missed
            # its local range guard. Known timeout paths validate earlier; this
            # remains a final structured-error boundary for provider overlays.
            return self._error(
                request.get("request_id"),
                "invalid_request",
                "numeric value is outside the admitted range",
            )

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
            # Keep the legacy core-engine council_limits shape stable. The
            # public admission layer is stricter and is exposed separately so
            # operators can distinguish the coordinator's internal ceiling
            # from the Chair's constitutional voting-roster rule.
            response["council_chair"] = chair_policy_snapshot()
        elif operation == "system.operations" and response.get("status") == "ok":
            response = dict(response)
            operations = list(response.get("operations", []))
            operations.extend(sorted(_LOCAL_ROLE_OPERATIONS))
            response["operations"] = sorted(set(operations))
        elif operation == "council.run" and response.get("status") == "ok":
            # The exact public roster was already admitted by
            # _validate_council_request_limits before any actor/auth creation.
            # Return the deterministic admission summary so operators can audit
            # which protected/general slot each requested model occupied.
            response = dict(response)
            response["council_chair"] = evaluate_council_roster_request(
                request.get("members", [])
            )
        return response

    def _handle_local_role_operation(self, request: dict[str, Any]) -> dict[str, Any]:
        request_id = request.get("request_id")
        if request_id is not None and not self._request_id_is_preflight_safe(request_id):
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

    def _request_id_is_preflight_safe(self, value: object) -> bool:
        if value is None:
            return True
        return (
            isinstance(value, str)
            and bool(value)
            and len(value) <= 128
            and all(character in _REQUEST_ID_CHARS for character in value)
            and not self.scrubber.scrub(value).changed
        )

    @staticmethod
    def _validate_council_request_limits(members: list[Any]) -> None:
        # Preserve the existing spend/network caps first so their historical
        # diagnostics remain stable, then apply the stricter Chair composition
        # contract. All of this happens before actor construction, credential
        # resolution, or provider inference.
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
        validate_council_roster_request(members)

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
