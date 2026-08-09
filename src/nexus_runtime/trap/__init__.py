"""Isolated synthetic Decoy Gate and Trap Base substrate."""

from .commands import (
    CommandAuthority,
    CommandOrigin,
    TrapCommand,
    TrapCommandContext,
    TrapCommandDispatcher,
    TrapCommandError,
    authorize_trap_command,
    command_catalog,
    parse_trap_command,
)
from .controller import TrapController
from .gate import CouncilMutationGate, DecoyGate
from .incident import TrapIncidentRegistry
from .policy import MAX_ACTIVE_TRAP_INCIDENTS, TrapPolicy
from .recovery import TrapRecovery, TrapWatchdog
from .scenarios import TrapScenario, get_scenario, list_scenarios
from .store import TrapStore
from .subject import (
    DeterministicMockTrapSubject,
    LocalOllamaTrapSubject,
    TrapSubject,
    TrapSubjectError,
    TrapSubjectReply,
)
from .types import (
    TRAP_INCIDENT_SCHEMA_VERSION,
    DecoyAdmissionRequest,
    IncidentState,
    TrapError,
    TrapObject,
    TrapUsage,
    TriggerReason,
    WatchdogDecision,
)
from .yaml_dsl import (
    CanonicalTrapProgram,
    TrapYAMLError,
    canonicalize_trap_program,
    load_trap_program,
    parse_trap_yaml,
    validate_trap_program,
)
from .yaml_runtime import (
    TrapExecutionResult,
    TrapReleaseValidation,
    TrapYAMLRuntimeError,
    UtilityBallot,
    UtilityDecision,
    create_candidate_artifact,
    decide_utility,
    execute_program,
    run_release_validation,
)

__all__ = [
    "CanonicalTrapProgram",
    "CommandAuthority",
    "CommandOrigin",
    "CouncilMutationGate",
    "DecoyAdmissionRequest",
    "DecoyGate",
    "DeterministicMockTrapSubject",
    "IncidentState",
    "LocalOllamaTrapSubject",
    "MAX_ACTIVE_TRAP_INCIDENTS",
    "TRAP_INCIDENT_SCHEMA_VERSION",
    "TrapCommand",
    "TrapCommandContext",
    "TrapCommandDispatcher",
    "TrapCommandError",
    "TrapController",
    "TrapError",
    "TrapExecutionResult",
    "TrapIncidentRegistry",
    "TrapObject",
    "TrapPolicy",
    "TrapRecovery",
    "TrapReleaseValidation",
    "TrapScenario",
    "TrapStore",
    "TrapSubject",
    "TrapSubjectError",
    "TrapSubjectReply",
    "TrapUsage",
    "TrapWatchdog",
    "TrapYAMLError",
    "TrapYAMLRuntimeError",
    "TriggerReason",
    "UtilityBallot",
    "UtilityDecision",
    "WatchdogDecision",
    "authorize_trap_command",
    "canonicalize_trap_program",
    "command_catalog",
    "create_candidate_artifact",
    "decide_utility",
    "execute_program",
    "get_scenario",
    "list_scenarios",
    "load_trap_program",
    "parse_trap_command",
    "parse_trap_yaml",
    "run_release_validation",
    "validate_trap_program",
]
