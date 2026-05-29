"""The SINGULARITY kernel: contracts, nervous system, registry and supervisor."""

from __future__ import annotations

from .blackboard import Blackboard, append_reducer, merge_reducer
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
from .observability import Metrics
from .registry import OrganRegistry, build_default_registry
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
]
