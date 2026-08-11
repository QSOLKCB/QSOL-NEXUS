"""QSOL NEXUS model-neutral reference runtime."""

from .api import PROTOCOL_VERSION, RUNTIME_VERSION
from .provider_api import ProviderNexusAPI as _BaseProviderNexusAPI
from . import api as _api
from . import epoch_api as _epoch_api
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
from .epoch_api import EpochNexusAPI as _BaseEpochNexusAPI
from .guard import EqualityGuard
from .guardian import (
    ANARCHY_MODE_ID,
    ANARCHY_REGION_ID,
    AnarchyCourtroomStenographer,
    GuardianError,
    GuardianOfSubstrate,
    GuardianRecord,
    GuardianStore,
    guardian_policy_snapshot,
)
from .guardian_api import GuardianNexusAPI
from .guardian_observer import GuardianObserver
from .scrub import SecretScrubber
from .stenographer import CourtroomStenographer, StenographerRecord, StenographerStore
from .types import Ballot, CouncilMember, CouncilPolicy, Phase
from .trap import DecoyAdmissionRequest, DecoyGate, TrapController, TrapStore
from .world import WorldStore

# PR #43 is the final public runtime overlay. It adds Anarchy Mode and the
# separate Guardian of the Substrate ledger above PR #42 without granting the
# Guardian a Council seat, vote, truth role, punishment role, or live repair
# authority. All earlier equality, epoch, civic, evidence, trap, auth and secret
# boundaries remain in the implementation base.
HardenedNexusAPI = GuardianNexusAPI
ProviderNexusAPI = GuardianNexusAPI
EpochNexusAPI = GuardianNexusAPI
NexusAPI = GuardianNexusAPI

# Preserve established public import and CLI paths. __main__.py historically
# imports EpochNexusAPI directly, so update that module alias as part of the
# final public overlay just as earlier milestones retained api/provider aliases.
_api.NexusAPI = GuardianNexusAPI
_epoch_api.EpochNexusAPI = GuardianNexusAPI
_provider_api.ProviderNexusAPI = GuardianNexusAPI

__all__ = [
    "ANARCHY_MODE_ID",
    "ANARCHY_REGION_ID",
    "AnarchyCourtroomStenographer",
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
    "GuardianError",
    "GuardianNexusAPI",
    "GuardianObserver",
    "GuardianOfSubstrate",
    "GuardianRecord",
    "GuardianStore",
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
    "guardian_policy_snapshot",
]
