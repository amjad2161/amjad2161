"""The universal contracts every organ of the SINGULARITY obeys.

These types are the *hermetic seam*: every repository in the ecosystem, no
matter its language or runtime, is projected onto the same small interface so
the kernel can treat reasoning, drones, trading and image generation
identically.

Design rules (drawn from the recurring patterns across the ecosystem — the
``diagnostics()`` of BRAINIAC, the ``connect/disconnect`` of SkyCore, the
``run()`` of Mythos, the watchdog supervision of GENESIS):

* Every organ has a stable ``id`` and a ``domain``.
* Every organ has an async lifecycle: ``boot`` / ``shutdown``.
* Every organ reports ``health`` synchronously and cheaply.
* Every organ ``describe``s itself (capabilities + backing repos).
* Every organ does work through a single ``invoke(intent, payload)`` verb.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Protocol, runtime_checkable


class Domain(str, Enum):
    """The eight functional lobes of the organism."""

    REASONING = "reasoning"
    AGENCY = "agency"
    KNOWLEDGE = "knowledge"
    EMBODIMENT = "embodiment"
    ECONOMICS = "economics"
    PERCEPTION = "perception"
    DATAPLANE = "dataplane"
    NETWORK = "network"


class Liveness(str, Enum):
    """Lifecycle state of an organ, mirroring the kernel watchdog states."""

    DORMANT = "dormant"  # constructed but not booted
    BOOTING = "booting"
    ALIVE = "alive"
    DEGRADED = "degraded"  # responding, but with reduced fidelity
    DOWN = "down"  # failed health checks


class Mode(str, Enum):
    """Whether an organ is wired to a real backend or a deterministic mock.

    Every organ MUST run in ``MOCK`` mode with no network, no credentials and
    no hardware so the whole singularity boots offline. When the backing
    repository / service / hardware is present it transparently upgrades to
    ``REAL``.
    """

    REAL = "real"
    MOCK = "mock"


class OrganError(RuntimeError):
    """Raised for invalid intents, payloads or lifecycle misuse."""


@dataclass(slots=True)
class Health:
    """A cheap, synchronous health snapshot for one organ."""

    organ: str
    liveness: Liveness
    mode: Mode
    detail: dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)

    @property
    def ok(self) -> bool:
        return self.liveness in (Liveness.ALIVE, Liveness.DEGRADED)

    def as_dict(self) -> dict[str, Any]:
        return {
            "organ": self.organ,
            "liveness": self.liveness.value,
            "mode": self.mode.value,
            "ok": self.ok,
            "detail": self.detail,
            "ts": self.ts,
        }


@dataclass(slots=True)
class Capability:
    """One thing an organ can do, addressed by a dotted ``intent``."""

    intent: str  # e.g. "neuro.think"
    summary: str
    payload: dict[str, str] = field(default_factory=dict)  # field -> human type hint

    def as_dict(self) -> dict[str, Any]:
        return {"intent": self.intent, "summary": self.summary, "payload": self.payload}


@dataclass(slots=True)
class OrganInfo:
    """Self-description of an organ for discovery and documentation."""

    id: str
    domain: Domain
    title: str
    vision: str
    repos: list[str]
    capabilities: list[Capability]
    mode: Mode

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "domain": self.domain.value,
            "title": self.title,
            "vision": self.vision,
            "repos": list(self.repos),
            "mode": self.mode.value,
            "capabilities": [c.as_dict() for c in self.capabilities],
        }


@dataclass(slots=True)
class Signal:
    """A message travelling on the nervous system (event bus)."""

    topic: str
    payload: dict[str, Any] = field(default_factory=dict)
    source: str = "kernel"
    ts: float = field(default_factory=time.time)

    def as_dict(self) -> dict[str, Any]:
        return {"topic": self.topic, "payload": self.payload, "source": self.source, "ts": self.ts}


@runtime_checkable
class Organ(Protocol):
    """The structural contract every federated subsystem implements."""

    id: str
    domain: Domain

    async def boot(self) -> None: ...

    async def shutdown(self) -> None: ...

    def health(self) -> Health: ...

    def describe(self) -> OrganInfo: ...

    async def invoke(self, intent: str, payload: Mapping[str, Any]) -> dict[str, Any]: ...
