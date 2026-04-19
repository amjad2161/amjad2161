"""Inertial Navigation System (INS) with GNSS fusion."""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class INSState(str, Enum):
    UNINITIALISED = "UNINITIALISED"
    NAVIGATING = "NAVIGATING"


@dataclass
class INSPoint:
    lat: float
    lon: float
    ts: float = field(default_factory=time.time)


@dataclass
class GNSSHealth:
    gnss_available: bool = True


@dataclass
class IMUReading:
    accel_x_mps2: float
    accel_y_mps2: float
    timestamp: float = field(default_factory=time.time)


class INS:
    def __init__(self) -> None:
        self._state = INSState.UNINITIALISED
        self._point: INSPoint | None = None
        self._vx = 0.0
        self._vy = 0.0
        self._last_imu_ts: float | None = None

    def update_gnss(self, point: INSPoint, gnss_health: GNSSHealth) -> INSPoint:
        if not gnss_health.gnss_available:
            return self._point or point
        if self._state == INSState.UNINITIALISED or self._point is None:
            self._point = point
            self._state = INSState.NAVIGATING
            return point
        # Complementary blend only in navigating state
        alpha = 0.7
        self._point = INSPoint(
            lat=(alpha * point.lat) + ((1 - alpha) * self._point.lat),
            lon=(alpha * point.lon) + ((1 - alpha) * self._point.lon),
            ts=point.ts,
        )
        return self._point

    def update_imu(self, reading: IMUReading) -> INSPoint | None:
        if self._point is None:
            self._last_imu_ts = reading.timestamp
            return None
        if self._last_imu_ts is None:
            self._last_imu_ts = reading.timestamp
            return self._point
        dt = max(0.0, reading.timestamp - self._last_imu_ts)
        self._last_imu_ts = reading.timestamp
        self._vx += reading.accel_x_mps2 * dt
        self._vy += reading.accel_y_mps2 * dt
        # very small-angle local tangent approximation
        dlat = (self._vy * dt) / 111_320.0
        dlon = (self._vx * dt) / max(1e-9, 111_320.0 * math.cos(math.radians(self._point.lat)))
        self._point = INSPoint(lat=self._point.lat + dlat, lon=self._point.lon + dlon, ts=reading.timestamp)
        return self._point

    @staticmethod
    def _haversine_m(a: INSPoint, b: INSPoint) -> float:
        phi1, phi2 = math.radians(a.lat), math.radians(b.lat)
        dphi = math.radians(b.lat - a.lat)
        dlambda = math.radians(b.lon - a.lon)
        s = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        return 6_371_000 * (2 * math.atan2(math.sqrt(s), math.sqrt(1 - s)))

    @staticmethod
    def _point_to_segment_distance_m(p: INSPoint, a: INSPoint, b: INSPoint) -> float:
        """
        Approximate local planar distance in meters (valid for short corridor segments).
        """
        ax, ay = a.lon, a.lat
        bx, by = b.lon, b.lat
        px, py = p.lon, p.lat
        abx, aby = bx - ax, by - ay
        ab2 = abx * abx + aby * aby
        if ab2 == 0:
            return INS._haversine_m(p, a)
        t = ((px - ax) * abx + (py - ay) * aby) / ab2
        t = max(0.0, min(1.0, t))
        cx, cy = ax + t * abx, ay + t * aby
        return INS._haversine_m(p, INSPoint(lat=cy, lon=cx))

    def corridor_check(self, point: INSPoint, corridor: list[INSPoint], width_m: float) -> bool:
        if len(corridor) < 2:
            return True
        min_dist = min(
            self._point_to_segment_distance_m(point, corridor[i], corridor[i + 1])
            for i in range(len(corridor) - 1)
        )
        return min_dist <= max(0.0, width_m)

    def diagnostics(self) -> dict[str, Any]:
        return {
            "status": "ONLINE",
            "navigation_role": "inertial_navigation",
            "capabilities": ["gnss_fusion", "dead_reckoning", "corridor_check"],
            "metrics": {"state": self._state.value},
            "version": "2.1.0",
        }
