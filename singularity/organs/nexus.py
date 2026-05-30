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
        self._db: Any = None  # real sqlite3 connection in REAL mode

    async def _attach_real(self) -> None:
        # A REAL persistent data plane backed by stdlib sqlite3 (a genuine
        # database — Supabase is just managed Postgres). Topics, telemetry and
        # the offline-sync queue survive restarts instead of living in memory.
        import os
        import sqlite3
        from pathlib import Path

        db_path = os.environ.get("SINGULARITY_NEXUS_DB",
                                 str(Path.home() / ".singularity" / "nexus.db"))
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.executescript(
            "CREATE TABLE IF NOT EXISTS publish_log(topic TEXT, ts REAL DEFAULT (strftime('%s','now')));"
            "CREATE TABLE IF NOT EXISTS telemetry(sensor TEXT, value REAL,"
            " ts REAL DEFAULT (strftime('%s','now')));"
            "CREATE TABLE IF NOT EXISTS sync_queue(seq INTEGER PRIMARY KEY AUTOINCREMENT,"
            " record TEXT, ts REAL DEFAULT (strftime('%s','now')));"
        )
        conn.commit()
        self._db = conn
        self._detail["sqlite"] = db_path

    async def _on_shutdown(self) -> None:
        if self._db is not None:
            try:
                self._db.close()
            finally:
                self._db = None

    async def _invoke(self, intent: str, payload: dict[str, Any]) -> dict[str, Any]:
        if intent == "nexus.publish":
            topic = str(payload.get("topic", "default"))
            if self._db is not None:
                self._db.execute("INSERT INTO publish_log(topic) VALUES (?)", (topic,))
                self._db.commit()
                count = self._db.execute(
                    "SELECT COUNT(*) FROM publish_log WHERE topic=?", (topic,)).fetchone()[0]
                return {"topic": topic, "delivered": True, "count": count,
                        "_backend": "sqlite-dataplane"}
            self._topics[topic] += 1
            return {"topic": topic, "delivered": True, "count": self._topics[topic],
                    "_backend": "builtin"}
        if intent == "nexus.telemetry":
            return self._telemetry(str(payload.get("sensor", "default")), float(payload.get("value", 0.0)))
        if intent == "nexus.sync":
            record = dict(payload.get("record", {}))
            if self._db is not None:
                import json as _json

                cur = self._db.execute("INSERT INTO sync_queue(record) VALUES (?)",
                                       (_json.dumps(record),))
                self._db.commit()
                depth = self._db.execute("SELECT COUNT(*) FROM sync_queue").fetchone()[0]
                return {"queued": True, "queue_depth": depth, "seq": cur.lastrowid,
                        "_backend": "sqlite-dataplane"}
            record["_seq"] = len(self._sync_queue) + 1
            self._sync_queue.append(record)
            return {"queued": True, "queue_depth": len(self._sync_queue), "seq": record["_seq"],
                    "_backend": "builtin"}
        if intent == "nexus.guard":
            return self._guard(str(payload.get("text", "")))
        raise AssertionError("unreachable")  # pragma: no cover

    def _telemetry(self, sensor: str, value: float) -> dict[str, Any]:
        if self._db is not None:
            # Real: persist the reading and compute the z-score over the genuine
            # stored window read back from the database.
            self._db.execute("INSERT INTO telemetry(sensor, value) VALUES (?,?)", (sensor, value))
            self._db.commit()
            rows = self._db.execute(
                "SELECT value FROM telemetry WHERE sensor=? ORDER BY rowid DESC LIMIT 64",
                (sensor,)).fetchall()
            window = [r[0] for r in rows]
            backend = "sqlite-dataplane"
        else:
            window = list(self._windows[sensor])
            window.append(value)
            self._windows[sensor].append(value)
            backend = "builtin"
        anomaly = False
        z = 0.0
        prior = window[1:] if self._db is not None else window[:-1]
        if len(prior) >= 8:
            mean = statistics.fmean(prior)
            stdev = statistics.pstdev(prior) or 1e-9
            z = (value - mean) / stdev
            anomaly = abs(z) >= 3.0
        return {
            "sensor": sensor,
            "value": value,
            "samples": len(window),
            "z_score": round(z, 3),
            "anomaly": anomaly,
            "_backend": backend,
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
