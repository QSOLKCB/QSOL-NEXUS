"""QSOL NEXUS model-neutral reference runtime."""

from .api import PROTOCOL_VERSION, RUNTIME_VERSION
from .provider_api import ProviderNexusAPI as _BaseProviderNexusAPI
from . import api as _api
from . import epoch_api as _epoch_api
from . import provider_api as _provider_api
from . import guardian_api as _guardian_api
from . import civic_due_process_api as _civic_due_process_api
from . import world_continuity_api as _world_continuity_api
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
from .life_paths import (
    LIFE_PATHS_KIND,
    LIFE_PATHS_SCHEMA,
    LIFE_PATHS_TITLE,
    apply_life_paths_choice,
    inspect_life_paths,
    life_paths_catalog,
    new_life_paths,
)
from .progression import (
    PROGRESSION_POLICY_ID,
    PROGRESSION_SCHEMA_VERSION,
    ProgressionError,
    ProgressionService,
    activity_catalog,
    progression_policy_snapshot,
)
from .progression_api import ProgressionNexusAPI
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
from .world_continuity_api import WorldContinuityNexusAPI as _BaseWorldContinuityNexusAPI

# PR #47 is the final pre-hardening public runtime overlay. It preserves every
# constitutional/runtime/storage contract through PR #46 while giving AI
# participants persistent non-voting civic life: bounded activities,
# commissions, descriptive milestones, Monopoly play history and the original
# NEXUS Life Paths simulation. Contribution history never creates authority.
HardenedNexusAPI = ProgressionNexusAPI
ProviderNexusAPI = ProgressionNexusAPI
EpochNexusAPI = ProgressionNexusAPI
GuardianNexusAPI = ProgressionNexusAPI
CivicDueProcessNexusAPI = ProgressionNexusAPI
WorldContinuityNexusAPI = ProgressionNexusAPI
NexusAPI = ProgressionNexusAPI

# Preserve established public import and CLI paths through every historical
# overlay module. __main__.py imports EpochNexusAPI directly after package init.
_api.NexusAPI = ProgressionNexusAPI
_epoch_api.EpochNexusAPI = ProgressionNexusAPI
_provider_api.ProviderNexusAPI = ProgressionNexusAPI
_guardian_api.GuardianNexusAPI = ProgressionNexusAPI
_civic_due_process_api.CivicDueProcessNexusAPI = ProgressionNexusAPI
_world_continuity_api.WorldContinuityNexusAPI = ProgressionNexusAPI

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
    "LIFE_PATHS_KIND",
    "LIFE_PATHS_SCHEMA",
    "LIFE_PATHS_TITLE",
    "NexusAPI",
    "PROGRESSION_POLICY_ID",
    "PROGRESSION_SCHEMA_VERSION",
    "PROTOCOL_VERSION",
    "Phase",
    "ProgressionError",
    "ProgressionNexusAPI",
    "ProgressionService",
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
    "activity_catalog",
    "apply_life_paths_choice",
    "civic_due_process_policy_snapshot",
    "civilization_gauntlet_policy_snapshot",
    "compute_epoch_policy_snapshot",
    "continuity_policy_snapshot",
    "current_compute_epoch",
    "guardian_policy_snapshot",
    "inspect_life_paths",
    "life_paths_catalog",
    "new_life_paths",
    "progression_policy_snapshot",
]
