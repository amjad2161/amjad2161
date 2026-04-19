"""High-level system orchestrator for BRAINIAC/G.A.N.E."""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from brainiac.agent import AgentLoop, AgentMemory, AgentRouter
from brainiac.core import (
    CreativeEngine,
    CyberShield,
    Localization,
    MedicalProtocols,
    NexusSync,
    NeuroCore,
    OmniVision,
    OrbitalNav,
    SatLink,
    SonicMatrix,
    TelemetryHub,
)


class MissionType(str, Enum):
    NAVIGATION = "navigation"
    RESCUE = "rescue"
    MEDICAL = "medical"
    SECURITY = "security"
    GENERAL = "general"


class SystemState(str, Enum):
    INITIALIZING = "INITIALIZING"
    ONLINE = "ONLINE"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"


@dataclass
class Mission:
    mission_id: str
    mission_type: MissionType
    objective: str
    created_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthReport:
    status: SystemState
    timestamp: float
    modules: dict[str, Any]


class Brainiac:
    """Top-level orchestrator combining core and agent modules."""

    def __init__(self) -> None:
        self.state = SystemState.INITIALIZING
        self.neuro = NeuroCore()
        self.nav = OrbitalNav()
        self.localization = Localization(self.nav)
        self.sonic = SonicMatrix()
        self.satlink = SatLink()
        self.nexus = NexusSync()
        self.telem = TelemetryHub()
        self.shield = CyberShield()
        self.creative = CreativeEngine()
        self.vision = OmniVision()
        self.medical = MedicalProtocols()

        self.router = AgentRouter()
        self.memory = AgentMemory()
        self.agent = AgentLoop(router=self.router, memory=self.memory)
        self._configure_auto_wiring()
        self.state = SystemState.ONLINE

    def _configure_auto_wiring(self) -> None:
        """Wire module callbacks with safe defaults."""

        async def _publish_anomaly(anomaly: Any) -> None:
            await self.nexus.publish(
                device_id="brainiac-telem",
                topic="telemetry/anomaly",
                payload={
                    "sensor_id": getattr(anomaly, "sensor_id", "unknown"),
                    "type": getattr(getattr(anomaly, "anomaly_type", None), "value", "unknown"),
                    "value": getattr(anomaly, "value", None),
                },
            )

        self.telem.on_anomaly(_publish_anomaly)
        self.nexus.subscribe("#", lambda _msg: None)

    async def boot(self) -> SystemState:
        await self.satlink.connect()
        self.state = SystemState.ONLINE
        return self.state

    async def run_mission(self, mission: Mission) -> dict[str, Any]:
        result = await self.agent.run(mission.objective)
        return {"mission_id": mission.mission_id, "mission_type": mission.mission_type.value, "result": result}

    def diagnostics(self) -> HealthReport:
        modules = {
            "neuro_core": self.neuro.diagnostics(),
            "orbital_nav": self.nav.diagnostics(),
            "satlink": self.satlink.diagnostics(),
            "sonic_matrix": self.sonic.diagnostics(),
            "nexus_sync": self.nexus.diagnostics(),
            "telemetry_hub": self.telem.diagnostics(),
            "cyber_shield": self.shield.diagnostics(),
            "creative_engine": self.creative.diagnostics(),
            "omni_vision": self.vision.diagnostics(),
            "agent_router": self.router.diagnostics(),
            "agent_memory": self.memory.diagnostics(),
        }
        return HealthReport(status=self.state, timestamp=time.time(), modules=modules)

    def emergency(self, reason: str) -> dict[str, Any]:
        self.state = SystemState.DEGRADED
        return {"status": self.state.value, "reason": reason, "timestamp": time.time()}


__all__ = ["Brainiac", "Mission", "MissionType", "SystemState", "HealthReport"]
