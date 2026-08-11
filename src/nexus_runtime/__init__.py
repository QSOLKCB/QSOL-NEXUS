"""QSOL NEXUS model-neutral reference runtime."""

from .api import PROTOCOL_VERSION, RUNTIME_VERSION
from .provider_api import ProviderNexusAPI as _BaseProviderNexusAPI
from . import api as _api
from . import provider_api as _provider_api
from .civilization_api import CivilizationNexusAPI
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

# PR #41 is the final public runtime overlay. It subclasses the existing
# hardened provider-aware API and adds only the Civilization Gauntlet surface;
# all prior control-plane, civic, auth, trap, and secret boundaries remain in
# the implementation base.
HardenedNexusAPI = CivilizationNexusAPI
ProviderNexusAPI = CivilizationNexusAPI
NexusAPI = CivilizationNexusAPI

# Preserve the established public import paths while keeping lower-level base
# classes as implementation details beneath the final public runtime overlay.
_api.NexusAPI = CivilizationNexusAPI
_provider_api.ProviderNexusAPI = CivilizationNexusAPI

__all__ = [
    "Ballot",
    "CivilizationGauntlet",
    "CivilizationGauntletError",
    "CivilizationNexusAPI",
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
