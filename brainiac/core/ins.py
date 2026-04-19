"""
INS — Inertial Navigation System
==================================
Provides dead-reckoning position estimation when GNSS signals are
degraded or unavailable (tunnels, urban canyons, jamming, underwater).

Fuses 9-axis IMU data (accelerometer + gyroscope + magnetometer) with
the last known GNSS fix to maintain a continuous position estimate.

Drift is modelled and compensated using a complementary filter; when
GNSS resumes, the system auto-corrects accumulated error.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import structlog

log = structlog.get_logger("brainiac.ins")

EARTH_RADIUS_M = 6_371_000.0


class PositionSource(str, Enum):
    GNSS = "GNSS"
    INS = "INS"
    FUSED = "FUSED"
    UNKNOWN = "UNKNOWN"


class INSState(str, Enum):
    UNINITIALISED = "UNINITIALISED"
    ALIGNING = "ALIGNING"
    NAVIGATING = "NAVIGATING"
    DEGRADED = "DEGRADED"


@dataclass
class IMUReading:
    accel_x: float  # m/s²
    accel_y: float
    accel_z: float
    gyro_x: float   # rad/s
    gyro_y: float
    gyro_z: float
    mag_x: float    # µT
    mag_y: float
    mag_z: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class INSPosition:
    lat: float
    lon: float
    alt_m: float
    heading_deg: float       # 0=N, 90=E
    speed_ms: float          # ground speed m/s
    source: PositionSource
    accuracy_m: float        # estimated horizontal error
    drift_m: float           # accumulated dead-reckoning drift
    timestamp: float = field(default_factory=time.time)

    def __str__(self) -> str:
        return (
            f"({self.lat:.6f}, {self.lon:.6f}, alt={self.alt_m:.1f}m, "
            f"hdg={self.heading_deg:.1f}°, src={self.source.value})"
        )


@dataclass
class GNSSHealth:
    constellations_available: int
    total_satellites_used: int
    best_hdop: float
    gnss_available: bool
    fix_type: str
    score: float   # 0.0 (no signal) .. 1.0 (perfect)


class INS:
    """
    Inertial Navigation System — dead-reckoning fallback for GNSS-denied nav.

    Capabilities:
    - 9-axis IMU fusion (accelerometer + gyroscope + magnetometer)
    - Dead-reckoning from last known GNSS fix
    - Automatic GNSS ↔ INS transition with fused blending
    - Drift estimation and accuracy degradation model
    - Heading from magnetometer + gyro integration
    - GNSS health scoring for failover decisions
    """

    DRIFT_RATE_M_PER_S = 0.5
    GNSS_HEALTH_THRESHOLD = 0.3
    ALIGNMENT_SAMPLES = 10
    COMPLEMENTARY_ALPHA = 0.98

    def __init__(self) -> None:
        self._state = INSState.UNINITIALISED
        self._last_gnss_lat: float | None = None
        self._last_gnss_lon: float | None = None
        self._last_gnss_alt: float = 0.0
        self._last_gnss_ts: float = 0.0

        self._lat: float = 0.0
        self._lon: float = 0.0
        self._alt: float = 0.0
        self._heading: float = 0.0
        self._speed: float = 0.0
        self._drift: float = 0.0

        self._velocity_north: float = 0.0
        self._velocity_east: float = 0.0
        self._velocity_down: float = 0.0

        self._alignment_buffer: list[IMUReading] = []
        self._gyro_bias_x: float = 0.0
        self._gyro_bias_y: float = 0.0
        self._gyro_bias_z: float = 0.0

        self._last_imu_ts: float = 0.0
        self._source = PositionSource.UNKNOWN
        self._gnss_health = GNSSHealth(
            constellations_available=0, total_satellites_used=0,
            best_hdop=99.0, gnss_available=False, fix_type="NO_FIX", score=0.0,
        )
        self._total_imu_samples: int = 0
        self._gnss_corrections: int = 0

        log.info("ins.init")

    def seed_position(self, lat: float, lon: float, alt_m: float = 0.0,
                      heading_deg: float = 0.0) -> None:
        self._lat = lat
        self._lon = lon
        self._alt = alt_m
        self._heading = heading_deg
        self._last_gnss_lat = lat
        self._last_gnss_lon = lon
        self._last_gnss_alt = alt_m
        self._last_gnss_ts = time.time()
        self._drift = 0.0
        self._source = PositionSource.GNSS
        self._state = INSState.NAVIGATING
        log.info("ins.seed", lat=lat, lon=lon)

    def update_gnss(self, lat: float, lon: float, alt_m: float = 0.0,
                    accuracy_m: float = 3.0) -> INSPosition:
        self._last_gnss_lat = lat
        self._last_gnss_lon = lon
        self._last_gnss_alt = alt_m
        self._last_gnss_ts = time.time()
        self._gnss_corrections += 1

        if self._gnss_health.gnss_available:
            alpha = min(0.9, accuracy_m / 10.0)
            self._lat = self._lat * (1 - alpha) + lat * alpha if self._state == INSState.NAVIGATING else lat
            self._lon = self._lon * (1 - alpha) + lon * alpha if self._state == INSState.NAVIGATING else lon
            self._alt = alt_m
            self._drift = max(0.0, self._drift - accuracy_m)
            self._source = PositionSource.FUSED
        else:
            self._lat = lat
            self._lon = lon
            self._alt = alt_m
            self._drift = 0.0
            self._source = PositionSource.GNSS

        if self._state == INSState.UNINITIALISED:
            self._state = INSState.NAVIGATING

        return self.position()

    def update_imu(self, reading: IMUReading) -> INSPosition:
        self._total_imu_samples += 1

        if self._state == INSState.UNINITIALISED:
            self._alignment_buffer.append(reading)
            if len(self._alignment_buffer) >= self.ALIGNMENT_SAMPLES:
                self._run_alignment()
            return self.position()

        if self._state == INSState.ALIGNING:
            self._alignment_buffer.append(reading)
            if len(self._alignment_buffer) >= self.ALIGNMENT_SAMPLES:
                self._run_alignment()
            return self.position()

        dt = reading.timestamp - self._last_imu_ts if self._last_imu_ts > 0 else 0.01
        dt = max(0.001, min(dt, 1.0))
        self._last_imu_ts = reading.timestamp

        corrected_gx = reading.gyro_x - self._gyro_bias_x
        corrected_gy = reading.gyro_y - self._gyro_bias_y
        corrected_gz = reading.gyro_z - self._gyro_bias_z

        self._heading += math.degrees(corrected_gz * dt)
        self._heading %= 360.0

        mag_heading = math.degrees(math.atan2(reading.mag_y, reading.mag_x))
        mag_heading = (mag_heading + 360) % 360
        a = self.COMPLEMENTARY_ALPHA
        diff = mag_heading - self._heading
        if diff > 180:
            diff -= 360
        elif diff < -180:
            diff += 360
        self._heading = (self._heading + (1 - a) * diff) % 360.0

        heading_rad = math.radians(self._heading)
        ax_body = reading.accel_x
        ay_body = reading.accel_y

        accel_north = ax_body * math.cos(heading_rad) - ay_body * math.sin(heading_rad)
        accel_east = ax_body * math.sin(heading_rad) + ay_body * math.cos(heading_rad)

        self._velocity_north += accel_north * dt
        self._velocity_east += accel_east * dt

        damping = 0.995
        self._velocity_north *= damping
        self._velocity_east *= damping

        self._speed = math.sqrt(self._velocity_north**2 + self._velocity_east**2)

        dn = self._velocity_north * dt
        de = self._velocity_east * dt

        self._lat += math.degrees(dn / EARTH_RADIUS_M)
        self._lon += math.degrees(de / (EARTH_RADIUS_M * math.cos(math.radians(self._lat))))
        self._alt += self._velocity_down * dt

        distance_step = math.sqrt(dn**2 + de**2)
        self._drift += self.DRIFT_RATE_M_PER_S * dt + distance_step * 0.02

        self._source = PositionSource.INS if not self._gnss_health.gnss_available else PositionSource.FUSED

        if self._drift > 500:
            self._state = INSState.DEGRADED
            log.warning("ins.drift_excessive", drift_m=self._drift)

        return self.position()

    def _run_alignment(self) -> None:
        if not self._alignment_buffer:
            return
        n = len(self._alignment_buffer)
        self._gyro_bias_x = sum(r.gyro_x for r in self._alignment_buffer) / n
        self._gyro_bias_y = sum(r.gyro_y for r in self._alignment_buffer) / n
        self._gyro_bias_z = sum(r.gyro_z for r in self._alignment_buffer) / n

        last = self._alignment_buffer[-1]
        self._heading = math.degrees(math.atan2(last.mag_y, last.mag_x))
        self._heading = (self._heading + 360) % 360
        self._last_imu_ts = last.timestamp
        self._alignment_buffer.clear()

        if self._last_gnss_lat is not None:
            self._state = INSState.NAVIGATING
        else:
            self._state = INSState.ALIGNING
        log.info("ins.alignment_complete", heading=self._heading)

    def update_gnss_health(
        self,
        constellations_available: int,
        total_satellites_used: int,
        best_hdop: float,
        fix_type: str = "3D",
    ) -> GNSSHealth:
        score = 0.0
        if fix_type in ("3D", "RTK_FLOAT", "RTK_FIXED"):
            score += 0.3
        if fix_type == "RTK_FIXED":
            score += 0.2
        score += min(0.3, constellations_available / 6 * 0.3)
        if best_hdop < 2.0:
            score += 0.2 * (1 - best_hdop / 2.0)
        score = min(1.0, score)

        self._gnss_health = GNSSHealth(
            constellations_available=constellations_available,
            total_satellites_used=total_satellites_used,
            best_hdop=best_hdop,
            gnss_available=score >= self.GNSS_HEALTH_THRESHOLD,
            fix_type=fix_type,
            score=round(score, 3),
        )
        if not self._gnss_health.gnss_available:
            log.warning("ins.gnss_degraded", score=score)
        return self._gnss_health

    def position(self) -> INSPosition:
        accuracy = 3.0
        if self._source == PositionSource.INS:
            accuracy = max(3.0, self._drift)
        elif self._source == PositionSource.FUSED:
            accuracy = max(1.0, self._drift * 0.3)
        return INSPosition(
            lat=self._lat,
            lon=self._lon,
            alt_m=self._alt,
            heading_deg=round(self._heading, 1),
            speed_ms=round(self._speed, 2),
            source=self._source,
            accuracy_m=round(accuracy, 2),
            drift_m=round(self._drift, 2),
        )

    def get_gnss_health(self) -> GNSSHealth:
        return self._gnss_health

    def reset(self) -> None:
        self._state = INSState.UNINITIALISED
        self._drift = 0.0
        self._velocity_north = 0.0
        self._velocity_east = 0.0
        self._velocity_down = 0.0
        self._speed = 0.0
        self._alignment_buffer.clear()
        self._source = PositionSource.UNKNOWN
        log.info("ins.reset")

    @property
    def state(self) -> INSState:
        return self._state

    def corridor_check(
        self,
        route_coords: list[tuple[float, float]],
        threshold_m: float = 50.0,
    ) -> dict[str, Any]:
        if not route_coords:
            return {"on_route": True, "deviation_m": 0.0, "nearest_segment": 0}

        min_dist = float("inf")
        nearest_seg = 0

        for i in range(len(route_coords) - 1):
            ax, ay = route_coords[i]
            bx, by = route_coords[i + 1]
            dist = self._point_to_segment_distance_m(
                self._lat, self._lon, ax, ay, bx, by,
            )
            if dist < min_dist:
                min_dist = dist
                nearest_seg = i

        if len(route_coords) == 1:
            ax, ay = route_coords[0]
            min_dist = self._haversine_m(self._lat, self._lon, ax, ay)

        return {
            "on_route": min_dist <= threshold_m,
            "deviation_m": round(min_dist, 1),
            "nearest_segment": nearest_seg,
            "threshold_m": threshold_m,
            "alert": "OFF_ROUTE" if min_dist > threshold_m else "OK",
        }

    @staticmethod
    def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
        return EARTH_RADIUS_M * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    @staticmethod
    def _point_to_segment_distance_m(
        px: float, py: float,
        ax: float, ay: float,
        bx: float, by: float,
    ) -> float:
        dx, dy = bx - ax, by - ay
        if dx == 0 and dy == 0:
            return INS._haversine_m(px, py, ax, ay)
        t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
        proj_lat = ax + t * dx
        proj_lon = ay + t * dy
        return INS._haversine_m(px, py, proj_lat, proj_lon)

    def diagnostics(self) -> dict[str, Any]:
        return {
            "status": "ONLINE",
            "navigation_role": "inertial_fallback",
            "capabilities": [
                "dead_reckoning", "imu_fusion", "gnss_ins_blending",
                "corridor_monitoring", "drift_estimation", "heading_computation",
            ],
            "state": self._state.value,
            "position_source": self._source.value,
            "drift_m": round(self._drift, 2),
            "heading_deg": round(self._heading, 1),
            "speed_ms": round(self._speed, 2),
            "gnss_health_score": self._gnss_health.score,
            "gnss_available": self._gnss_health.gnss_available,
            "total_imu_samples": self._total_imu_samples,
            "gnss_corrections": self._gnss_corrections,
        }
