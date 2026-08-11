"""QSOL NEXUS model-neutral reference runtime."""

from .api import PROTOCOL_VERSION, RUNTIME_VERSION
from .provider_api import ProviderNexusAPI as _BaseProviderNexusAPI
from .hardening import HardenedNexusAPI
from . import api as _api
from . import provider_api as _provider_api
from .civilization_gauntlet import (
    CivilizationGauntlet,
    CivilizationGauntletError,
    ReferenceCivilizationActor,
    civilization_gauntlet_policy_snapshot,
)
from .council import CouncilCoordinator
from .guard import EqualityGuard
from .scrub import SecretScrubber
from .stenographer import CourtroomStenographer, StenographerRecord, StenographerStore
from .types import Ballot, CouncilMember, CouncilPolicy, Phase
from .trap import DecoyAdmissionRequest, DecoyGate, TrapController, TrapStore
from .world import WorldStore

ProviderNexusAPI = HardenedNexusAPI
NexusAPI = HardenedNexusAPI

# Preserve the established public import paths while keeping the original
# provider-aware class available only as HardenedNexusAPI's implementation base.
_api.NexusAPI = HardenedNexusAPI
_provider_api.ProviderNexusAPI = HardenedNexusAPI

__all__ = [
    "Ballot",
    "CivilizationGauntlet",
    "CivilizationGauntletError",
    "CouncilCoordinator",
    "CouncilMember",
    "CouncilPolicy",
    "CourtroomStenographer",
    "DecoyAdmissionRequest",
    "DecoyGate",
    "EqualityGuard",
    "HardenedNexusAPI",
    "NexusAPI",
    "PROTOCOL_VERSION",
    "Phase",
    "ProviderNexusAPI",
    "RUNTIME_VERSION",
    "ReferenceCivilizationActor",
    "SecretScrubber",
    "StenographerRecord",
    "StenographerStore",
    "TrapController",
    "TrapStore",
    "WorldStore",
    "civilization_gauntlet_policy_snapshot",
]
