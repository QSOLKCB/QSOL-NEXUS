"""QSOL NEXUS model-neutral reference runtime."""

from .api import PROTOCOL_VERSION, RUNTIME_VERSION
from .provider_api import ProviderNexusAPI, ProviderNexusAPI as NexusAPI
from . import api as _api
from .council import CouncilCoordinator
from .guard import EqualityGuard
from .scrub import SecretScrubber
from .stenographer import CourtroomStenographer, StenographerRecord, StenographerStore
from .types import Ballot, CouncilMember, CouncilPolicy, Phase
from .trap import DecoyAdmissionRequest, DecoyGate, TrapController, TrapStore
from .world import WorldStore

# Preserve the established `from nexus_runtime.api import NexusAPI` import path.
# provider_api captures the original core class during package initialization;
# once the provider-aware subclass exists, expose it through the canonical
# submodule as well as the package root so callers cannot accidentally bypass
# admitted provider/local-role support merely by choosing one public import.
_api.NexusAPI = ProviderNexusAPI

__all__ = [
    "Ballot",
    "CouncilCoordinator",
    "CouncilMember",
    "CouncilPolicy",
    "CourtroomStenographer",
    "DecoyAdmissionRequest",
    "DecoyGate",
    "EqualityGuard",
    "NexusAPI",
    "PROTOCOL_VERSION",
    "Phase",
    "ProviderNexusAPI",
    "RUNTIME_VERSION",
    "SecretScrubber",
    "StenographerRecord",
    "StenographerStore",
    "TrapController",
    "TrapStore",
    "WorldStore",
]
