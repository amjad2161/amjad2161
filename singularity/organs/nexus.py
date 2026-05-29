"""NEXUS — the data plane (sync, telemetry, security).

Federates: auto-save-sync (GMIN Nexus offline-first data plane) plus BRAINIAC's
NexusSync / TelemetryHub / CyberShield. Fully functional offline: an in-memory
device pub/sub, sliding-window telemetry with z-score anomaly detection, and a
rule-based input guard — the same primitives the federation needs to stay
coherent and safe.
"""

from __future__ import annotations

import re
import statistics
from collections import defaultdict, deque
from typing import Any

from ..kernel.contracts import Capability, Domain
from .base import BaseOrgan

_INJECTION = re.compile(
    r"(ignore (previous|all) instructions|rm\s+-rf|drop\s+table|<script|;\s*shutdown|\beval\()",
    re.IGNORECASE,
)


class NexusOrgan(BaseOrgan):
    id = "nexus"
    domain = Domain.DATAPLANE
    title = "Nexus — sync, telemetry & shield"
    vision = "Keep the organism coherent: device mesh, anomaly-aware telemetry, input defence."
    capabilities = (
        Capability("nexus.publish", "Publish a message to a device-mesh topic.",
                   {"topic": "str", "payload": "dict"}),
        Capability("nexus.telemetry", "Ingest a sensor reading; flag z-score anomalies.",
                   {"sensor": "str", "value": "float"}),
        Capability("nexus.sync", "Enqueue an offline-first record for eventual sync.",
                   {"record": "dict"}),
        Capability("nexus.guard", "Scan text for injection / unsafe content.",
                   {"text": "str", "source_ip": "str?"}),
    )

    def __init__(self, *, force_mock: bool = False) -> None:
        super().__init__(force_mock=force_mock)
        self._topics: dict[str, int] = defaultdict(int)
        self._windows: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=64))
        self._sync_queue: list[dict[str, Any]] = []

    async def _invoke(self, intent: str, payload: dict[str, Any]) -> dict[str, Any]:
        if intent == "nexus.publish":
            topic = str(payload.get("topic", "default"))
            self._topics[topic] += 1
            return {"topic": topic, "delivered": True, "count": self._topics[topic]}
        if intent == "nexus.telemetry":
            return self._telemetry(str(payload.get("sensor", "default")), float(payload.get("value", 0.0)))
        if intent == "nexus.sync":
            record = dict(payload.get("record", {}))
            record["_seq"] = len(self._sync_queue) + 1
            self._sync_queue.append(record)
            return {"queued": True, "queue_depth": len(self._sync_queue), "seq": record["_seq"]}
        if intent == "nexus.guard":
            return self._guard(str(payload.get("text", "")))
        raise AssertionError("unreachable")  # pragma: no cover

    def _telemetry(self, sensor: str, value: float) -> dict[str, Any]:
        window = self._windows[sensor]
        anomaly = False
        z = 0.0
        if len(window) >= 8:
            mean = statistics.fmean(window)
            stdev = statistics.pstdev(window) or 1e-9
            z = (value - mean) / stdev
            anomaly = abs(z) >= 3.0
        window.append(value)
        return {
            "sensor": sensor,
            "value": value,
            "samples": len(window),
            "z_score": round(z, 3),
            "anomaly": anomaly,
        }

    def _guard(self, text: str) -> dict[str, Any]:
        match = _INJECTION.search(text)
        threat = bool(match)
        return {
            "safe": not threat,
            "threat": threat,
            "category": "prompt-injection" if threat else "clean",
            "matched": match.group(0) if match else None,
        }
