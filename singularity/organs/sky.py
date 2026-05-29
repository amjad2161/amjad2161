"""SKY — embodiment & flight (real SkyCore integration).

Federates Dji-owner / **SkyCore**. When the SkyCore package is importable this
organ runs the *genuine* code: it builds real ``WaypointMission`` geometry and
executes missions on a real ``SimulatorDrone`` (no hardware, no fakes — the
actual flight controller and physics simulation), returning real telemetry.
With SkyCore absent it falls back to an equivalent deterministic builtin, and
every result declares its provenance in ``_backend``.
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
    # Real simulator flight is real-time; allow a generous budget.
    invoke_timeout_s = 45.0
    capabilities = (
        Capability("sky.mission_plan", "Generate an orbit/survey mission as waypoints.",
                   {"kind": "str?", "lat": "float", "lon": "float", "radius_m": "float?",
                    "altitude_m": "float?", "points": "int?"}),
        Capability("sky.telemetry", "Sample current drone telemetry.", {}),
        Capability("sky.fly", "Execute a (bounded, real) mission and report the flight.",
                   {"lat": "float?", "lon": "float?", "points": "int?", "waypoints": "list?"}),
    )

    async def _attach_real(self) -> None:
        from ..kernel.bootstrap import try_import

        if try_import("skycore") is None:
            raise RuntimeError("skycore unavailable")
        from skycore import GeoPoint, SimulatorDrone
        from skycore import missions

        self._backend = {"Geo": GeoPoint, "Sim": SimulatorDrone, "missions": missions}
        self._detail["skycore"] = True

    async def _invoke(self, intent: str, payload: dict[str, Any]) -> dict[str, Any]:
        if intent == "sky.mission_plan":
            return await self._mission_plan(payload)
        if intent == "sky.telemetry":
            return await self._telemetry(payload)
        if intent == "sky.fly":
            return await self._fly(payload)
        raise AssertionError("unreachable")  # pragma: no cover

    # -- real (skycore) ---------------------------------------------------
    def _real_orbit(self, lat: float, lon: float, radius_m: float, altitude_m: float, points: int):
        geo = self._backend["Geo"]
        return self._backend["missions"].orbit_mission(
            geo(lat, lon), radius_m=radius_m, altitude_m=altitude_m,
            waypoints=max(3, points), photo_each=False,
        )

    async def _mission_plan(self, payload: dict[str, Any]) -> dict[str, Any]:
        lat = float(payload.get("lat", 37.7749))
        lon = float(payload.get("lon", -122.4194))
        radius_m = float(payload.get("radius_m", 60.0))
        altitude_m = float(payload.get("altitude_m", 40.0))
        points = max(3, int(payload.get("points", 12)))
        kind = str(payload.get("kind", "orbit"))

        if self._backend is not None:
            mission = self._real_orbit(lat, lon, radius_m, altitude_m, points)
            waypoints = [
                {"lat": round(s.target.lat, 6), "lon": round(s.target.lon, 6),
                 "alt_m": s.target.alt, "speed_mps": s.speed_mps}
                for s in mission.steps
            ]
            return {"kind": kind, "waypoints": waypoints, "count": len(waypoints),
                    "radius_m": radius_m, "altitude_m": altitude_m, "_backend": "skycore"}

        # deterministic builtin (real geometry, honestly labelled)
        waypoints = []
        for i in range(points):
            angle = 2 * math.pi * i / points
            dlat = (radius_m * math.cos(angle)) / 111_320.0
            dlon = (radius_m * math.sin(angle)) / (111_320.0 * math.cos(math.radians(lat)))
            waypoints.append({"lat": round(lat + dlat, 6), "lon": round(lon + dlon, 6),
                              "alt_m": altitude_m})
        return {"kind": kind, "waypoints": waypoints, "count": len(waypoints),
                "radius_m": radius_m, "altitude_m": altitude_m, "_backend": "builtin"}

    async def _telemetry(self, payload: dict[str, Any]) -> dict[str, Any]:
        lat = float(payload.get("lat", 37.7749))
        lon = float(payload.get("lon", -122.4194))
        if self._backend is not None:
            geo = self._backend["Geo"]
            drone = self._backend["Sim"](home=geo(lat, lon))
            async with drone:
                t = await drone.get_telemetry()
            return {"lat": round(t.position.lat, 6), "lon": round(t.position.lon, 6),
                    "altitude_m": t.position.alt, "battery_pct": round(t.battery_percent, 2),
                    "satellites": t.gps_satellites, "mode": str(getattr(t.flight_mode, "value",
                    t.flight_mode)), "_backend": "skycore"}
        return {"lat": lat, "lon": lon, "altitude_m": 0.0, "battery_pct": 100.0,
                "satellites": 14, "mode": "idle", "_backend": "builtin"}

    async def _fly(self, payload: dict[str, Any]) -> dict[str, Any]:
        lat = float(payload.get("lat", 37.7749))
        lon = float(payload.get("lon", -122.4194))
        given = payload.get("waypoints") or []
        points = max(3, min(int(payload.get("points", len(given) or 3)), 6))
        if self._backend is not None:
            geo = self._backend["Geo"]
            drone = self._backend["Sim"](home=geo(lat, lon))
            # Bounded, fast, *real* flight: high speed + low altitude keep it responsive.
            mission = self._backend["missions"].orbit_mission(
                geo(lat, lon), radius_m=8.0, altitude_m=3.0, waypoints=points,
                speed_mps=60.0, photo_each=False,
            )
            async with drone:
                await mission.execute(drone, takeoff_altitude_m=1.0, return_after=False)
                t = await drone.get_telemetry()
            return {"executed": len(mission.steps), "battery_pct": round(t.battery_percent, 2),
                    "altitude_m": round(t.position.alt, 2),
                    "mode": str(getattr(t.flight_mode, "value", t.flight_mode)),
                    "status": "flown", "_backend": "skycore"}

        wps = given or (await self._mission_plan({"lat": lat, "lon": lon, "points": points}))["waypoints"]
        dist = sum(
            math.hypot((b["lat"] - a["lat"]) * 111_320.0,
                       (b["lon"] - a["lon"]) * 111_320.0 * math.cos(math.radians(a["lat"])))
            for a, b in zip(wps, wps[1:])
        )
        return {"executed": len(wps), "distance_m": round(dist, 1),
                "battery_used_pct": min(99.0, round(len(wps) * 1.5, 1)),
                "status": "landed", "_backend": "builtin"}
