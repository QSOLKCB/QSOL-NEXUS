"""QSOL NEXUS model-neutral reference runtime."""

from .api import PROTOCOL_VERSION, RUNTIME_VERSION
from .provider_api import ProviderNexusAPI as _BaseProviderNexusAPI
from . import api as _api
from . import epoch_api as _epoch_api
from . import provider_api as _provider_api
from . import guardian_api as _guardian_api
from . import civic_due_process_api as _civic_due_process_api
from . import world_continuity_api as _world_continuity_api
from . import progression_api as _progression_api
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
from .culture import (
    CULTURE_POLICY_ID,
    CULTURE_SCHEMA_VERSION,
    CultureError,
    culture_policy_snapshot,
    performance_catalog,
)
from .culture_api import CultureNexusAPI
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
from .long_shift import (
    LONG_SHIFT_KIND,
    LONG_SHIFT_SCHEMA,
    LONG_SHIFT_TITLE,
    apply_long_shift_choice,
    inspect_long_shift,
    long_shift_catalog,
    new_long_shift,
)
from .progression import (
    PROGRESSION_POLICY_ID,
    PROGRESSION_SCHEMA_VERSION,
    ProgressionError,
    ProgressionService,
    activity_catalog,
    progression_policy_snapshot,
)
from .progression_api import ProgressionNexusAPI as _BaseProgressionNexusAPI
from .psyche_chess import (
    PSYCHE_CHESS_KIND,
    PSYCHE_CHESS_SCHEMA,
    PSYCHE_CHESS_TITLE,
    add_psyche,
    apply_psyche_chess_move,
    inspect_psyche_chess,
    legal_moves_for_fen,
    new_psyche_chess,
    psyche_chess_catalog,
)
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

# PR #48 is the final pre-hardening public runtime overlay. It preserves every
# constitutional/storage/progression contract through PR #47 and adds original
# AI culture surfaces: Open Mic performance, NEXUS: The Long Shift, and
# Psyche-Out Chess. Culture and play create history, not authority.
HardenedNexusAPI = CultureNexusAPI
ProviderNexusAPI = CultureNexusAPI
EpochNexusAPI = CultureNexusAPI
GuardianNexusAPI = CultureNexusAPI
CivicDueProcessNexusAPI = CultureNexusAPI
WorldContinuityNexusAPI = CultureNexusAPI
ProgressionNexusAPI = CultureNexusAPI
NexusAPI = CultureNexusAPI

# Preserve established public import and CLI paths through every historical
# overlay module. __main__.py imports EpochNexusAPI directly after package init.
_api.NexusAPI = CultureNexusAPI
_epoch_api.EpochNexusAPI = CultureNexusAPI
_provider_api.ProviderNexusAPI = CultureNexusAPI
_guardian_api.GuardianNexusAPI = CultureNexusAPI
_civic_due_process_api.CivicDueProcessNexusAPI = CultureNexusAPI
_world_continuity_api.WorldContinuityNexusAPI = CultureNexusAPI
_progression_api.ProgressionNexusAPI = CultureNexusAPI

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
    "CULTURE_POLICY_ID",
    "CULTURE_SCHEMA_VERSION",
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
    "CultureError",
    "CultureNexusAPI",
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
    "LONG_SHIFT_KIND",
    "LONG_SHIFT_SCHEMA",
    "LONG_SHIFT_TITLE",
    "NexusAPI",
    "PROGRESSION_POLICY_ID",
    "PROGRESSION_SCHEMA_VERSION",
    "PROTOCOL_VERSION",
    "PSYCHE_CHESS_KIND",
    "PSYCHE_CHESS_SCHEMA",
    "PSYCHE_CHESS_TITLE",
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
    "add_psyche",
    "apply_life_paths_choice",
    "apply_long_shift_choice",
    "apply_psyche_chess_move",
    "civic_due_process_policy_snapshot",
    "civilization_gauntlet_policy_snapshot",
    "compute_epoch_policy_snapshot",
    "continuity_policy_snapshot",
    "culture_policy_snapshot",
    "current_compute_epoch",
    "guardian_policy_snapshot",
    "inspect_life_paths",
    "inspect_long_shift",
    "inspect_psyche_chess",
    "legal_moves_for_fen",
    "life_paths_catalog",
    "long_shift_catalog",
    "new_life_paths",
    "new_long_shift",
    "new_psyche_chess",
    "performance_catalog",
    "progression_policy_snapshot",
    "psyche_chess_catalog",
]
