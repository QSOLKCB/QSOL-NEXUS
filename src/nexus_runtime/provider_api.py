from __future__ import annotations

from typing import Any

from .adapters import THIRD_PARTY_PROVIDER_IDS, ThirdPartyActor, ThirdPartyTransport
from .api import MAX_REMOTE_COUNCIL_SEATS, NexusAPI as CoreNexusAPI
from .types import CouncilMember


REMOTE_PROVIDER_IDS = frozenset({"xai", *THIRD_PARTY_PROVIDER_IDS})


class ProviderNexusAPI(CoreNexusAPI):
    """NEXUS API with fixed-host third-party provider admission.

    The core control protocol remains JSONL/stdio. Remote provider credentials
    are resolved through AuthBroker profiles and never accepted in public API
    requests. All remote provider seats retain one vote and no epistemic
    privilege, and the existing remote-seat cap is shared across providers.
    """

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        response = super().handle(request)
        if request.get("operation") == "system.health" and response.get("status") == "ok":
            response = dict(response)
            response["network"] = (
                "local_stdio_with_explicit_loopback_ollama_or_fixed_remote_provider_https_"
                "or_registered_auth_operations"
            )
            response["adapters"] = [
                "mock",
                "ollama_loopback",
                "xai_https",
                *[f"{adapter_id}_https" for adapter_id in sorted(THIRD_PARTY_PROVIDER_IDS)],
            ]
            response["actor_backends_available"] = [
                "mock",
                "ollama",
                "xai",
                *sorted(THIRD_PARTY_PROVIDER_IDS),
            ]
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

        vote_weight = item.get("vote_weight", 1)
        epistemic_privilege = item.get("epistemic_privilege", "none")
        member = CouncilMember(
            member_id=self._member_identity(item, "member_id"),
            model_id=self._member_identity(item, "model_id"),
            adapter_id=adapter_id,
            deployment_metadata=self._member_metadata(item, "deployment_metadata"),
            capability_metadata=self._member_metadata(item, "capability_metadata"),
            vote_weight=vote_weight,
            epistemic_privilege=epistemic_privilege,
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
