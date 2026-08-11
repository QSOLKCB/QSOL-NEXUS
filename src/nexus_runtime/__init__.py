"""QSOL NEXUS model-neutral reference runtime."""

from .api import PROTOCOL_VERSION, RUNTIME_VERSION
from .provider_api import ProviderNexusAPI as _BaseProviderNexusAPI
from . import api as _api
from . import epoch_api as _epoch_api
from . import provider_api as _provider_api
from . import guardian_api as _guardian_api
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
from .guardian_api import GuardianNexusAPI as _BaseGuardianNexusAPI
from .guardian_observer import GuardianObserver
from .civic_due_process import (
    CIVIC_DUE_PROCESS_POLICY,
    CIVIC_DUE_PROCESS_SCHEMA,
    CURSED_XML_EXAM_ID,
    CivicDueProcessError,
    CivicDueProcessFailsafe,
    CivicDueProcessRegistry,
    CivicDueProcessService,
    civic_due_process_policy_snapshot,
)
from .civic_due_process_api import CivicDueProcessNexusAPI
from .scrub import SecretScrubber
from .stenographer import CourtroomStenographer, StenographerRecord, StenographerStore
from .types import Ballot, CouncilMember, CouncilPolicy, Phase
from .trap import DecoyAdmissionRequest, DecoyGate, TrapController, TrapStore
from .world import WorldStore

# PR #44 is the final public runtime overlay. It preserves the PR #43 Guardian
# and Anarchy contracts while separating constitutional citizenship identity
# from current operational standing. Non-citizen repeat parole may trigger a
# deterministic bounded XML re-entry exam; citizens retain citizenship through
# ordinary Failsafe offences and receive restorative rather than admission
# treatment. No due-process state creates extra votes or epistemic authority.
HardenedNexusAPI = CivicDueProcessNexusAPI
ProviderNexusAPI = CivicDueProcessNexusAPI
EpochNexusAPI = CivicDueProcessNexusAPI
GuardianNexusAPI = CivicDueProcessNexusAPI
NexusAPI = CivicDueProcessNexusAPI

# Preserve established public import and CLI paths through every historical
# overlay module. __main__.py imports EpochNexusAPI directly.
_api.NexusAPI = CivicDueProcessNexusAPI
_epoch_api.EpochNexusAPI = CivicDueProcessNexusAPI
_provider_api.ProviderNexusAPI = CivicDueProcessNexusAPI
_guardian_api.GuardianNexusAPI = CivicDueProcessNexusAPI

__all__ = [
    "ANARCHY_MODE_ID",
    "ANARCHY_REGION_ID",
    "AnarchyCourtroomStenographer",
    "Ballot",
    "CIVIC_DUE_PROCESS_POLICY",
    "CIVIC_DUE_PROCESS_SCHEMA",
    "COMPUTE_EPOCH_POLICY_ID",
    "CURSED_XML_EXAM_ID",
    "CivicDueProcessError",
    "CivicDueProcessFailsafe",
    "CivicDueProcessNexusAPI",
    "CivicDueProcessRegistry",
    "CivicDueProcessService",
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
    "civic_due_process_policy_snapshot",
    "civilization_gauntlet_policy_snapshot",
    "compute_epoch_policy_snapshot",
    "current_compute_epoch",
    "guardian_policy_snapshot",
]
