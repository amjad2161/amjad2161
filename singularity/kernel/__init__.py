"""The SINGULARITY kernel: contracts, nervous system, registry and supervisor."""

from __future__ import annotations

from .autopilot import Autopilot, AutopilotRun, AutopilotStep
from .blackboard import Blackboard, append_reducer, merge_reducer
from .bootstrap import available as real_backends_available
from .bootstrap import repos_root
from .config import SingularityConfig
from .contracts import (
    Capability,
    Domain,
    Health,
    Liveness,
    Mode,
    Organ,
    OrganError,
    OrganInfo,
    Signal,
)
from .event_bus import EventBus
from .governor import Governor, GovernorError
from .kernel import Singularity, build_default_kernel
from .mcp import MCPBridge
from .memory import Session, SessionStore, Turn
from .plugins import discover_plugin_organs, load_entrypoint_organs, load_spec_organs
from .observability import Metrics
from .persistence import Checkpointer, JSONCheckpointer, MemoryCheckpointer
from .policy import PolicyDecision, PolicyError, PolicyGate
from .registry import OrganRegistry, build_default_registry
from .scheduler import Job, Scheduler
from .resilience import (
    BulkheadFullError,
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
    ResilienceError,
    ResiliencePolicy,
    RetryPolicy,
)
from .watchdog import Watchdog
from .workflow import Step, Workflow, WorkflowError, WorkflowResult

__all__ = [
    "Capability",
    "Domain",
    "Health",
    "Liveness",
    "Mode",
    "Organ",
    "OrganError",
    "OrganInfo",
    "Signal",
    "EventBus",
    "Governor",
    "GovernorError",
    "Singularity",
    "build_default_kernel",
    "OrganRegistry",
    "build_default_registry",
    "Watchdog",
    "Blackboard",
    "append_reducer",
    "merge_reducer",
    "Metrics",
    "MCPBridge",
    "ResiliencePolicy",
    "RetryPolicy",
    "CircuitBreaker",
    "CircuitState",
    "ResilienceError",
    "CircuitOpenError",
    "BulkheadFullError",
    "Workflow",
    "WorkflowResult",
    "WorkflowError",
    "Step",
    "SingularityConfig",
    "PolicyGate",
    "PolicyDecision",
    "PolicyError",
    "Checkpointer",
    "MemoryCheckpointer",
    "JSONCheckpointer",
    "Autopilot",
    "AutopilotRun",
    "AutopilotStep",
    "Scheduler",
    "Job",
    "SessionStore",
    "Session",
    "Turn",
    "discover_plugin_organs",
    "load_entrypoint_organs",
    "load_spec_organs",
    "real_backends_available",
    "repos_root",
]
