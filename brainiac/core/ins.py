"""INS (Inertial Navigation System) support."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class IMUReading:
    accel: tuple[float, float, float]
    gyro: tuple[float, float, float]
    timestamp: float = field(default_factory=time.time)


class INS:
    def __init__(self) -> None:
        self._aligned = False
        self._last_imu_ts: float | None = None

    def align(self) -> None:
        self._aligned = True
        self._last_imu_ts = time.time()

    def update_imu(self, reading: IMUReading) -> None:
        if not self._aligned:
            self.align()
        self._last_imu_ts = reading.timestamp

    def diagnostics(self) -> dict[str, Any]:
        return {"status": "ONLINE", "aligned": self._aligned, "last_imu_ts": self._last_imu_ts}


__all__ = ["INS", "IMUReading"]
