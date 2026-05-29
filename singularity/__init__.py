"""SINGULARITY — the hermetic kernel that federates a whole ecosystem of repos.

The vision behind ``amjad2161``'s repositories is a single autonomous
superintelligence (the recurring codenames are *BRAINIAC*, *JARVIS*, *GENESIS*,
*Nexus*).  Each repository is one **organ** of that organism: reasoning,
agency, knowledge, embodiment, economics, perception, the data plane and the
network.

This package is the *nervous system* that lets those organs work **together**
(routed through one kernel, one event bus, one API/CLI) and **apart** (each
organ boots, self-reports health and degrades to a deterministic mock when its
backing repo or credentials are absent).

Public surface::

    from singularity import Singularity, build_default_kernel
    kernel = build_default_kernel()
    await kernel.boot()
    result = await kernel.route("neuro.think", {"prompt": "hello"})
    await kernel.shutdown()
"""

from __future__ import annotations

from .kernel.autopilot import Autopilot, AutopilotRun
from .kernel.blackboard import Blackboard
from .kernel.config import SingularityConfig
from .kernel.contracts import (
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
from .kernel.event_bus import EventBus
from .kernel.kernel import Singularity, build_default_kernel
from .kernel.mcp import MCPBridge
from .kernel.policy import PolicyGate
from .kernel.registry import OrganRegistry, build_default_registry
from .kernel.scheduler import Scheduler
from .kernel.workflow import Workflow, WorkflowResult

__version__ = "1.2.0"
__all__ = [
    "__version__",
    "Singularity",
    "build_default_kernel",
    "SingularityConfig",
    "OrganRegistry",
    "build_default_registry",
    "EventBus",
    "Workflow",
    "WorkflowResult",
    "Autopilot",
    "AutopilotRun",
    "Scheduler",
    "PolicyGate",
    "MCPBridge",
    "Blackboard",
    "Organ",
    "OrganInfo",
    "OrganError",
    "Capability",
    "Health",
    "Signal",
    "Domain",
    "Liveness",
    "Mode",
]
