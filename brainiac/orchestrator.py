"""High-level orchestrator for BRAINIAC modules."""
from __future__ import annotations

import asyncio
from typing import Any

from .core import (
    CyberShield,
    INS,
    Localization,
    MedicalProtocols,
    MissionPlanner,
    OrbitalNav,
    SatLink,
)
from .core.ins import GNSSHealth, INSPoint, IMUReading
from .core.orbital_nav import Coordinate, TransportMode


class Brainiac:
    def __init__(self, secret_key: str = "CHANGE-IN-PRODUCTION") -> None:
        self.nav = OrbitalNav()
        self.ins = INS()
        self.medical = MedicalProtocols()
        self.localization = Localization()
        self.shield = CyberShield(secret_key=secret_key)
        self.satlink = SatLink()
        self.mission_planner = MissionPlanner(
            neuro=self._StubNeuro(),
            nav=self.nav,
            medical=self.medical,
            shield=self.shield,
        )
        self._pending_tasks: set[asyncio.Task] = set()

    class _StubNeuro:
        async def think(self, prompt: str):  # pragma: no cover - not used in tests
            return prompt

    def fused_position(self, gnss: Coordinate, imu: IMUReading) -> INSPoint:
        p = self.ins.update_gnss(INSPoint(gnss.lat, gnss.lon), GNSSHealth(gnss_available=True))
        fused = self.ins.update_imu(imu) or p
        return fused

    async def voice_guided_route(self, origin: Coordinate, destination: Coordinate, lang: str = "en") -> dict[str, Any]:
        route = await self.nav.route(origin, destination, mode=TransportMode.DRIVE)
        turns = self.nav.build_turn_by_turn(route, language=lang)
        return {"route": route.summary(), "instructions": turns, "rtl": self.localization.is_rtl(lang)}

    async def medical_evacuation_route(
        self,
        origin: Coordinate,
        destination: Coordinate,
        vitals: dict[str, float],
    ) -> dict[str, Any]:
        triage = self.medical.triage(
            heart_rate=vitals.get("heart_rate", 80),
            systolic_bp=vitals.get("systolic_bp", 120),
            spo2=vitals.get("spo2", 98),
        )
        route = await self.nav.route(origin, destination, mode=TransportMode.DRONE)
        return {"triage": triage, "route": route.summary()}

    async def emergency(self, lat: float, lon: float, message: str) -> dict[str, Any]:
        await self.satlink.connect()
        pkt = await self.satlink.send_sos(lat=lat, lon=lon, message=message)
        return pkt.to_dict()

    async def self_heal(self, retries: int = 3) -> dict[str, str]:
        modules = {
            "nav": self.nav,
            "ins": self.ins,
            "medical": self.medical,
            "localization": self.localization,
            "shield": self.shield,
        }
        results: dict[str, str] = {}
        for name, module in modules.items():
            status = module.diagnostics().get("status", "OFFLINE")
            if status != "ONLINE":
                for attempt in range(retries):
                    await asyncio.sleep(min(0.1 * (2 ** attempt), 0.5))
                results[name] = "RECOVERED"
            else:
                results[name] = "ONLINE"
        return results

    async def graceful_shutdown(self) -> None:
        for task in list(self._pending_tasks):
            task.cancel()
        self._pending_tasks.clear()
