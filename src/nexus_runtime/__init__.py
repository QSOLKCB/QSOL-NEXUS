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
from .compute_epochs import (
    COMPUTE_EPOCH_POLICY_ID,
    compute_epoch_policy_snapshot,
    current_compute_epoch,
)
from .council import CouncilCoordinator
from .epoch_api import EpochNexusAPI
from .guard import EqualityGuard
from .scrub import SecretScrubber
from .stenographer import CourtroomStenographer, StenographerRecord, StenographerStore
from .types import Ballot, CouncilMember, CouncilPolicy, Phase
from .trap import DecoyAdmissionRequest, DecoyGate, TrapController, TrapStore
from .world import WorldStore

# PR #42 is the final public runtime overlay. It subclasses the Civilization
# Gauntlet surface and adds Temporal Compute Equality, pinned epoch-admission
# receipts, the Centennial Genesis Capsule and inert defensive Purgatory policy.
# All prior control-plane, civic, auth, trap, evidence and secret boundaries
# remain in the implementation base.
HardenedNexusAPI = EpochNexusAPI
ProviderNexusAPI = EpochNexusAPI
NexusAPI = EpochNexusAPI

# Preserve the established public import paths while keeping lower-level base
# classes as implementation details beneath the final public runtime overlay.
_api.NexusAPI = EpochNexusAPI
_provider_api.ProviderNexusAPI = EpochNexusAPI

__all__ = [
    "Ballot",
    "COMPUTE_EPOCH_POLICY_ID",
    "CivilizationGauntlet",
    "CivilizationGauntletError",
    "CivilizationNexusAPI",
    "CouncilCoordinator",
    "CouncilMember",
    "CouncilPolicy",
    "CourtroomStenographer",
    "DecoyAdmissionRequest",
    "DecoyGate",
    "EpochNexusAPI",
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
    "compute_epoch_policy_snapshot",
    "current_compute_epoch",
]
