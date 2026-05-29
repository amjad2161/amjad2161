"""The SINGULARITY kernel: contracts, nervous system, registry and supervisor."""

from __future__ import annotations

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
from .registry import OrganRegistry, build_default_registry
from .watchdog import Watchdog

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
]
