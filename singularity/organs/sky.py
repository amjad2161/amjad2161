"""SKY — embodiment & flight.

Federates: Dji-owner/SkyCore (unified drone API) and the agency robotics stack.
In ``REAL`` mode it drives ``skycore.SimulatorDrone`` and ``WaypointMission``;
in ``MOCK`` mode it generates equivalent mission geometry and telemetry so the
organism can plan and "fly" missions with no hardware.
"""

from __future__ import annotations

import math
from typing import Any

from ..kernel.contracts import Capability, Domain
from .base import BaseOrgan


class SkyOrgan(BaseOrgan):
    id = "sky"
    domain = Domain.EMBODIMENT
    title = "SkyCore — drones & embodiment"
    vision = "Plan and fly safe autonomous missions across simulator, Tello, MAVLink and DJI."
    capabilities = (
        Capability("sky.mission_plan", "Generate an orbit/survey mission as waypoints.",
                   {"kind": "str?", "lat": "float", "lon": "float", "radius_m": "float?",
                    "altitude_m": "float?", "points": "int?"}),
        Capability("sky.telemetry", "Sample current drone telemetry.", {}),
        Capability("sky.fly", "Execute a mission (simulated) and report the flight.",
                   {"waypoints": "list?", "lat": "float?", "lon": "float?"}),
    )

    async def _attach_real(self) -> None:
        from skycore import GeoPoint, SimulatorDrone  # type: ignore

        self._backend = {"drone_cls": SimulatorDrone, "geo": GeoPoint}
        self._detail["backend"] = "skycore"

    async def _invoke(self, intent: str, payload: dict[str, Any]) -> dict[str, Any]:
        if intent == "sky.mission_plan":
            return self._mission_plan(payload)
        if intent == "sky.telemetry":
            return {
                "lat": float(payload.get("lat", 37.7749)),
                "lon": float(payload.get("lon", -122.4194)),
                "altitude_m": 0.0,
                "battery_pct": 100.0,
                "mode": "idle",
                "satellites": 14,
            }
        if intent == "sky.fly":
            waypoints = payload.get("waypoints")
            if not waypoints:
                waypoints = self._mission_plan(payload)["waypoints"]
            return {
                "executed": len(waypoints),
                "distance_m": round(_path_length(waypoints), 1),
                "battery_used_pct": min(99.0, round(len(waypoints) * 1.5, 1)),
                "status": "landed",
            }
        raise AssertionError("unreachable")  # pragma: no cover

    def _mission_plan(self, payload: dict[str, Any]) -> dict[str, Any]:
        kind = str(payload.get("kind", "orbit"))
        lat = float(payload.get("lat", 37.7749))
        lon = float(payload.get("lon", -122.4194))
        radius_m = float(payload.get("radius_m", 60.0))
        altitude_m = float(payload.get("altitude_m", 40.0))
        points = max(3, int(payload.get("points", 12)))
        waypoints = []
        for i in range(points):
            angle = 2 * math.pi * i / points
            dlat = (radius_m * math.cos(angle)) / 111_320.0
            dlon = (radius_m * math.sin(angle)) / (111_320.0 * math.cos(math.radians(lat)))
            waypoints.append(
                {"lat": round(lat + dlat, 6), "lon": round(lon + dlon, 6), "alt_m": altitude_m}
            )
        return {
            "kind": kind,
            "waypoints": waypoints,
            "count": len(waypoints),
            "radius_m": radius_m,
            "altitude_m": altitude_m,
        }


def _path_length(waypoints: list[dict[str, Any]]) -> float:
    total = 0.0
    for a, b in zip(waypoints, waypoints[1:]):
        dlat = (b["lat"] - a["lat"]) * 111_320.0
        dlon = (b["lon"] - a["lon"]) * 111_320.0 * math.cos(math.radians(a["lat"]))
        total += math.hypot(dlat, dlon)
    return total
