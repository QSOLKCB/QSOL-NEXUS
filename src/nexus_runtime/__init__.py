"""QSOL NEXUS model-neutral reference runtime."""

from .api import PROTOCOL_VERSION, RUNTIME_VERSION
from .provider_api import ProviderNexusAPI as _BaseProviderNexusAPI
from . import api as _api
from . import epoch_api as _epoch_api
from . import provider_api as _provider_api
from . import guardian_api as _guardian_api
from . import civic_due_process_api as _civic_due_process_api
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
from .civic_due_process_api import CivicDueProcessNexusAPI as _BaseCivicDueProcessNexusAPI
from .scrub import SecretScrubber
from .stenographer import CourtroomStenographer, StenographerRecord, StenographerStore
from .types import Ballot, CouncilMember, CouncilPolicy, Phase
from .trap import DecoyAdmissionRequest, DecoyGate, TrapController, TrapStore
from .world import WorldStore
from .world_continuity import (
    ARK_SCHEMA_VERSION,
    CONTINUITY_POLICY_ID,
    CONTINUITY_SCHEMA_VERSION,
    ContinuityWorldStore,
    WorldContinuityError,
    continuity_policy_snapshot,
)
from .world_continuity_api import WorldContinuityNexusAPI

# PR #46 is the final pre-beta public runtime overlay. It preserves every
# constitutional/runtime contract through PR #45 while layering majority-quorum
# WorldStore continuity, deterministic scrub/repair, self-describing cold Arks,
# and non-destructive recovery around the existing content-addressed object
# format. Storage redundancy never creates votes, evidence, or civic authority.
HardenedNexusAPI = WorldContinuityNexusAPI
ProviderNexusAPI = WorldContinuityNexusAPI
EpochNexusAPI = WorldContinuityNexusAPI
GuardianNexusAPI = WorldContinuityNexusAPI
CivicDueProcessNexusAPI = WorldContinuityNexusAPI
NexusAPI = WorldContinuityNexusAPI

# Preserve established public import and CLI paths through every historical
# overlay module. __main__.py imports EpochNexusAPI directly after package init.
_api.NexusAPI = WorldContinuityNexusAPI
_epoch_api.EpochNexusAPI = WorldContinuityNexusAPI
_provider_api.ProviderNexusAPI = WorldContinuityNexusAPI
_guardian_api.GuardianNexusAPI = WorldContinuityNexusAPI
_civic_due_process_api.CivicDueProcessNexusAPI = WorldContinuityNexusAPI

__all__ = [
    "ANARCHY_MODE_ID",
    "ANARCHY_REGION_ID",
    "ARK_SCHEMA_VERSION",
    "AnarchyCourtroomStenographer",
    "Ballot",
    "CIVIC_DUE_PROCESS_POLICY",
    "CIVIC_DUE_PROCESS_SCHEMA",
    "COMPUTE_EPOCH_POLICY_ID",
    "CONTINUITY_POLICY_ID",
    "CONTINUITY_SCHEMA_VERSION",
    "CURSED_XML_EXAM_ID",
    "CivicDueProcessError",
    "CivicDueProcessFailsafe",
    "CivicDueProcessNexusAPI",
    "CivicDueProcessRegistry",
    "CivicDueProcessService",
    "CivilizationGauntlet",
    "CivilizationGauntletError",
    "CivilizationNexusAPI",
    "ContinuityWorldStore",
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
    "WorldContinuityError",
    "WorldContinuityNexusAPI",
    "WorldStore",
    "civic_due_process_policy_snapshot",
    "civilization_gauntlet_policy_snapshot",
    "compute_epoch_policy_snapshot",
    "continuity_policy_snapshot",
    "current_compute_epoch",
    "guardian_policy_snapshot",
]
