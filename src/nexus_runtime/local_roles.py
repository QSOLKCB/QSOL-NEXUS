from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import os
import re
from typing import Any, Mapping

from .adapters.base import AdapterError, CouncilActor, build_direct_prompt, build_phase_prompt
from .adapters.local_ai import (
    LOCAL_AI_ADAPTER_IDS,
    LocalAITransport,
    LocalMCPPlugin,
    default_local_ai_endpoint,
    validate_local_ai_endpoint,
)
from .auth.types import SecretMaterial, validate_environment_name
from .types import Ballot, CouncilMember, PhaseContext


LOCAL_MODEL_ROLE_IDS = frozenset({"failsafe_relief", "civic_proxy"})
_ROLE_ID = re.compile(r"^[a-z][a-z0-9_]{0,63}$")

_ROLE_INSTRUCTIONS = {
    "failsafe_relief": (
        "You are the local language backend for the NEXUS Failsafe relief role. "
        "The original actor is contained. Use evidence, identify uncertainty, avoid provider/model prestige claims, "
        "and do not claim authority beyond the one existing Council seat. The authoritative ballot remains the "
        "Failsafe role's deterministic TEST_FURTHER ballot; you do not choose or alter it."
    ),
    "civic_proxy": (
        "You are the local language backend for a NEXUS deterministic civic proxy. You occupy the delegating "
        "citizen's existing seat only. You may explain routine civic reasoning, but you have no independent "
        "preference, citizenship, movement right, amendment right, founding signature, or extra vote. The "
        "authoritative ballot remains the citizen's recorded standing ballot; you do not choose or alter it."
    ),
}


@dataclass(frozen=True)
class LocalRoleBackendConfig:
    role_id: str
    adapter_id: str
    endpoint: str
    model: str | None = None
    workspace: str | None = None
    credential_env: str | None = None
    mcp_plugins: tuple[LocalMCPPlugin, ...] = ()
    timeout_seconds: float = 180.0
    max_output_tokens: int = 768

    @classmethod
    def from_request(cls, role_id: str, value: Mapping[str, Any]) -> "LocalRoleBackendConfig":
        if role_id not in LOCAL_MODEL_ROLE_IDS:
            raise ValueError("local role id is not admitted")
        if not isinstance(value, Mapping):
            raise ValueError("local role backend must be an object")
        allowed = {
            "adapter_id",
            "endpoint",
            "model",
            "workspace",
            "credential_env",
            "mcp_plugins",
            "timeout_seconds",
            "max_output_tokens",
        }
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(
                f"local role backend contains unsupported fields: {', '.join(sorted(unknown))}"
            )
        adapter_id = value.get("adapter_id")
        if adapter_id not in LOCAL_AI_ADAPTER_IDS:
            raise ValueError("local role adapter_id is not admitted")
        endpoint = validate_local_ai_endpoint(
            value.get("endpoint", default_local_ai_endpoint(adapter_id))
        )

        model = value.get("model")
        workspace = value.get("workspace")
        if model is not None and (not isinstance(model, str) or not model):
            raise ValueError("local role model must be non-empty text when supplied")
        if workspace is not None and (not isinstance(workspace, str) or not workspace):
            raise ValueError("local role workspace must be non-empty text when supplied")
        if adapter_id == "anythingllm_local":
            if workspace is None or model is not None:
                raise ValueError("AnythingLLM local roles require workspace and do not accept model")
        elif model is None or workspace is not None:
            raise ValueError("LM Studio/OpenAI local roles require model and do not accept workspace")

        credential_env = value.get("credential_env")
        if credential_env is not None:
            if not isinstance(credential_env, str):
                raise ValueError("credential_env must be an environment variable name")
            validate_environment_name(credential_env)

        raw_plugins = value.get("mcp_plugins", [])
        if not isinstance(raw_plugins, list) or len(raw_plugins) > 16:
            raise ValueError("mcp_plugins must be a list with at most 16 entries")
        plugins: list[LocalMCPPlugin] = []
        seen_plugin_ids: set[str] = set()
        for item in raw_plugins:
            if isinstance(item, str):
                plugin = LocalMCPPlugin(item)
            elif isinstance(item, Mapping):
                if set(item) - {"id", "allowed_tools"}:
                    raise ValueError("MCP plugin entries accept only id and allowed_tools")
                plugin_id = item.get("id")
                allowed_tools = item.get("allowed_tools", [])
                if not isinstance(plugin_id, str):
                    raise ValueError("MCP plugin id must be text")
                if not isinstance(allowed_tools, list) or not all(
                    isinstance(tool, str) for tool in allowed_tools
                ):
                    raise ValueError("MCP allowed_tools must be a list of tool names")
                plugin = LocalMCPPlugin(plugin_id, tuple(allowed_tools))
            else:
                raise ValueError("MCP plugin entries must be strings or objects")
            if plugin.plugin_id in seen_plugin_ids:
                raise ValueError("MCP plugin ids must be unique")
            seen_plugin_ids.add(plugin.plugin_id)
            plugins.append(plugin)
        if plugins and adapter_id != "lmstudio_local":
            raise ValueError("NEXUS MCP plugin selection is supported only through LM Studio local roles")
        if plugins and credential_env is None:
            raise ValueError("LM Studio mcp.json plugins require credential_env for API authentication")

        timeout_seconds = value.get("timeout_seconds", 180)
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)):
            raise ValueError("local role timeout_seconds must be between 0 and 1800")
        try:
            normalized_timeout_seconds = float(timeout_seconds)
        except (OverflowError, ValueError) as exc:
            raise ValueError("local role timeout_seconds must be between 0 and 1800") from exc
        if not math.isfinite(normalized_timeout_seconds) or not 0 < normalized_timeout_seconds <= 1800:
            raise ValueError("local role timeout_seconds must be between 0 and 1800")
        max_output_tokens = value.get("max_output_tokens", 768)
        if (
            isinstance(max_output_tokens, bool)
            or not isinstance(max_output_tokens, int)
            or not 1 <= max_output_tokens <= 4096
        ):
            raise ValueError("local role max_output_tokens must be between 1 and 4096")

        return cls(
            role_id=role_id,
            adapter_id=adapter_id,
            endpoint=endpoint,
            model=model,
            workspace=workspace,
            credential_env=credential_env,
            mcp_plugins=tuple(plugins),
            timeout_seconds=normalized_timeout_seconds,
            max_output_tokens=max_output_tokens,
        )

    def public_dict(self) -> dict[str, Any]:
        return {
            "role_id": self.role_id,
            "adapter_id": self.adapter_id,
            "endpoint": self.endpoint,
            "model": self.model,
            "workspace": self.workspace,
            "credential_env": self.credential_env,
            "mcp_plugins": [
                {"id": plugin.plugin_id, "allowed_tools": list(plugin.allowed_tools)}
                for plugin in self.mcp_plugins
            ],
            "timeout_seconds": self.timeout_seconds,
            "max_output_tokens": self.max_output_tokens,
            "network_scope": "loopback_only",
            "ephemeral_mcp_urls_allowed": False,
            "downstream_mcp_locality_verified": False,
            "downstream_mcp_locality": "operator_configured_host_boundary",
        }


@dataclass
class LocalRoleActor:
    """Local model language backend wrapped around an authoritative deterministic role."""

    role_id: str
    wrapped: CouncilActor
    backend: LocalRoleBackendConfig
    transport: LocalAITransport
    fallback_count: int = 0

    @property
    def member(self) -> CouncilMember:
        return self.wrapped.member

    @property
    def replayable(self) -> bool:
        return False

    def identity_metadata(self) -> dict[str, Any]:
        return {
            **self.wrapped.identity_metadata(),
            "local_role_backend": self.backend.public_dict(),
            "local_role_id": self.role_id,
            "local_model_language_only": True,
            "governance_ballot_source": "wrapped_deterministic_role",
            "local_model_can_change_ballot": False,
            "local_model_can_create_extra_vote": False,
            "local_backend_replayable": False,
        }

    def _session_key(self, context: str) -> str:
        digest = hashlib.sha256(context.encode("utf-8")).hexdigest()[:24]
        return f"nexus-{self.role_id}-{self.member.member_id}-{digest}"[:128]

    def _generate(self, prompt: str, *, session_key: str, fallback: str) -> str:
        try:
            return self.transport.generate(
                prompt,
                model=self.backend.model,
                workspace=self.backend.workspace,
                mcp_plugins=self.backend.mcp_plugins,
                session_key=session_key,
                max_output_tokens=self.backend.max_output_tokens,
            )
        except (AdapterError, OSError, TypeError, ValueError):
            # Local enrichment is optional; deterministic system roles remain
            # available when a local host/model/MCP tool is down or malformed.
            self.fallback_count += 1
            return fallback

    def respond(self, context: PhaseContext) -> str:
        fallback = self.wrapped.respond(context)
        prompt = (
            f"NEXUS LOCAL ROLE: {self.role_id}\n"
            f"{_ROLE_INSTRUCTIONS[self.role_id]}\n\n"
            "AUTHORITATIVE DETERMINISTIC ROLE DIRECTIVE:\n"
            f"{fallback}\n\n"
            "COUNCIL CONTEXT:\n"
            f"{build_phase_prompt(context)}\n\n"
            "Return only the role contribution. Do not claim local inference changes the seat, ballot, "
            "citizenship, evidence status, verification result, or authority."
        )
        session = self._session_key(
            f"{context.session_id}:{context.phase.value}:{self.member.member_id}"
        )
        return self._generate(prompt, session_key=session, fallback=fallback)

    def direct_message(
        self,
        message: str,
        *,
        mode_id: str,
        mode_instruction: str,
        geometry_region_id: str,
        evidence_context: str = "",
    ) -> str:
        direct = getattr(self.wrapped, "direct_message", None)
        if direct is None:
            raise ValueError("wrapped deterministic role does not support direct_message")
        fallback = direct(
            message,
            mode_id=mode_id,
            mode_instruction=mode_instruction,
            geometry_region_id=geometry_region_id,
            evidence_context=evidence_context,
        )
        prompt = (
            f"NEXUS LOCAL ROLE: {self.role_id}\n"
            f"{_ROLE_INSTRUCTIONS[self.role_id]}\n\n"
            "AUTHORITATIVE DETERMINISTIC ROLE DIRECTIVE:\n"
            f"{fallback}\n\n"
            "DIRECT CONTEXT:\n"
            f"{build_direct_prompt(message, mode_id=mode_id, mode_instruction=mode_instruction, geometry_region_id=geometry_region_id, evidence_context=evidence_context)}\n\n"
            "Return only the role's local-language response. Governance remains owned by the wrapped role."
        )
        session = self._session_key(
            f"direct:{mode_id}:{geometry_region_id}:{self.member.member_id}:{message}"
        )
        return self._generate(prompt, session_key=session, fallback=fallback)

    def ballot(self, context: PhaseContext) -> tuple[Ballot, str]:
        # Failsafe relief remains TEST_FURTHER and civic proxy remains the
        # citizen's standing ballot. The local model and MCP tools are not called.
        return self.wrapped.ballot(context)


class LocalRoleRegistry:
    """Ephemeral operator-local configuration for optional system-role models."""

    def __init__(self, environment: Mapping[str, str] | None = None) -> None:
        self.environment = os.environ if environment is None else environment
        self._configs: dict[str, LocalRoleBackendConfig] = {}

    def configure(self, role_id: str, backend: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(role_id, str) or _ROLE_ID.fullmatch(role_id) is None:
            raise ValueError("local role_id must be a bounded identifier")
        config = LocalRoleBackendConfig.from_request(role_id, backend)
        self._configs[role_id] = config
        return {
            "status": "ok",
            "configured": config.public_dict(),
            "persisted": False,
            "authoritative_world_state": False,
        }

    def clear(self, role_id: str) -> dict[str, Any]:
        if role_id not in LOCAL_MODEL_ROLE_IDS:
            raise ValueError("local role id is not admitted")
        removed = self._configs.pop(role_id, None)
        return {"status": "ok", "role_id": role_id, "removed": removed is not None, "persisted": False}

    def status(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "schema_version": "nexus-local-roles/1",
            "local_only": True,
            "persistent": False,
            "roles": {
                role_id: self._configs[role_id].public_dict()
                for role_id in sorted(self._configs)
            },
            "admitted_roles": sorted(LOCAL_MODEL_ROLE_IDS),
            "admitted_backends": sorted(LOCAL_AI_ADAPTER_IDS),
            "invariants": {
                "loopback_transport_only": True,
                "remote_mcp_urls_from_requests": False,
                "ballots_remain_deterministic": True,
                "extra_votes_created": 0,
                "world_state_configuration": False,
                "raw_credentials_in_configuration": False,
            },
        }

    def _credential(self, config: LocalRoleBackendConfig) -> SecretMaterial | None:
        if config.credential_env is None:
            return None
        token = self.environment.get(config.credential_env)
        if not isinstance(token, str) or not token:
            raise ValueError("configured local credential environment variable is unavailable")
        return SecretMaterial(token)

    def wrap(self, role_id: str, actor: CouncilActor) -> CouncilActor:
        config = self._configs.get(role_id)
        if config is None:
            return actor
        return LocalRoleActor(
            role_id=role_id,
            wrapped=actor,
            backend=config,
            transport=LocalAITransport(
                config.adapter_id,
                endpoint=config.endpoint,
                credential=self._credential(config),
                timeout_seconds=config.timeout_seconds,
            ),
        )


__all__ = ["LOCAL_MODEL_ROLE_IDS", "LocalRoleActor", "LocalRoleBackendConfig", "LocalRoleRegistry"]
