"""Mission planning with contingencies and optional persistence."""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .cyber_shield import CyberShield
from .medical_protocols import MedicalProtocols
from .neuro_core import NeuroCore
from .orbital_nav import Coordinate, OrbitalNav, TransportMode


@dataclass
class MissionPlan:
    mission_id: str
    primary: dict[str, Any]
    plan_b: dict[str, Any]
    plan_c: dict[str, Any]
    abort_criteria: list[str]
    created_at: float = field(default_factory=time.time)


class MissionStore:
    def __init__(self, sqlite_path: str | None = None) -> None:
        self._mem: dict[str, MissionPlan] = {}
        self._sqlite_path = sqlite_path
        if sqlite_path:
            conn = sqlite3.connect(sqlite_path)
            conn.execute(
                "CREATE TABLE IF NOT EXISTS missions (mission_id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
            )
            conn.commit()
            conn.close()

    def save(self, plan: MissionPlan) -> None:
        self._mem[plan.mission_id] = plan
        if self._sqlite_path:
            conn = sqlite3.connect(self._sqlite_path)
            conn.execute(
                "REPLACE INTO missions(mission_id, payload) VALUES(?, ?)",
                (plan.mission_id, json.dumps(plan.__dict__)),
            )
            conn.commit()
            conn.close()

    def load(self, mission_id: str) -> MissionPlan | None:
        if mission_id in self._mem:
            return self._mem[mission_id]
        if not self._sqlite_path:
            return None
        conn = sqlite3.connect(self._sqlite_path)
        row = conn.execute("SELECT payload FROM missions WHERE mission_id = ?", (mission_id,)).fetchone()
        conn.close()
        if not row:
            return None
        payload = json.loads(row[0])
        return MissionPlan(**payload)


class MissionPlanner:
    def __init__(
        self,
        neuro: NeuroCore,
        nav: OrbitalNav,
        medical: MedicalProtocols,
        shield: CyberShield,
        store: MissionStore | None = None,
    ) -> None:
        self.neuro = neuro
        self.nav = nav
        self.medical = medical
        self.shield = shield
        self.store = store or MissionStore()

    async def create_plan(
        self,
        *,
        origin: Coordinate,
        destination: Coordinate,
        mode: TransportMode = TransportMode.DRIVE,
        vitals: dict[str, float] | None = None,
    ) -> MissionPlan:
        route = await self.nav.route(origin, destination, mode=mode)
        triage = self.medical.triage(
            heart_rate=(vitals or {}).get("heart_rate", 80),
            systolic_bp=(vitals or {}).get("systolic_bp", 120),
            spo2=(vitals or {}).get("spo2", 98),
        )
        spoof = self.shield.detect_gps_spoofing()
        mission_id = str(uuid.uuid4())
        plan = MissionPlan(
            mission_id=mission_id,
            primary={"route": route.summary(), "triage": triage},
            plan_b={"action": "switch_to_offline_route"},
            plan_c={"action": "abort_and_rtb"},
            abort_criteria=[
                "battery_below_reserve",
                "gps_spoofing_high" if spoof["risk_score"] >= 0.8 else "operator_abort",
            ],
        )
        self.store.save(plan)
        return plan

    def allocate_tasks(self, vehicles: list[str], tasks: list[str]) -> dict[str, list[str]]:
        allocation = {v: [] for v in vehicles}
        for i, task in enumerate(tasks):
            allocation[vehicles[i % len(vehicles)]].append(task)
        return allocation

    def resume(self, mission_id: str) -> MissionPlan | None:
        return self.store.load(mission_id)
