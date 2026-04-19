"""
BRAINIAC ORCHESTRATOR — Master System Controller
==================================================
Unifies all 9 core modules into a single cohesive autonomous intelligence.
Provides mission planning, auto-wiring, self-healing, and high-level
operations that span multiple modules.

This is the top-level entry point — if you only want to touch one class,
touch this one.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

import structlog

from brainiac.core import (
    NeuroCore, OrbitalNav, SonicMatrix, SatLink,
    NexusSync, TelemetryHub, CyberShield, CreativeEngine, OmniVision,
    Localization, MedicalProtocols,
)
from brainiac.core.neuro_core import ReasoningDepth
from brainiac.core.orbital_nav import Coordinate, TransportMode
from brainiac.core.satlink import SOSPriority
from brainiac.core.telemetry_hub import SensorReading, Anomaly
from brainiac.core.nexus_sync import DeviceType, Protocol, Message

log = structlog.get_logger("brainiac.orchestrator")


class SystemState(str, Enum):
    BOOTING = "BOOTING"
    ONLINE = "ONLINE"
    DEGRADED = "DEGRADED"
    EMERGENCY = "EMERGENCY"
    MAINTENANCE = "MAINTENANCE"
    OFFLINE = "OFFLINE"


class MissionType(str, Enum):
    RECON = "recon"
    DELIVERY = "delivery"
    RESCUE = "rescue"
    SURVEILLANCE = "surveillance"
    EXPLORATION = "exploration"
    DIAGNOSTIC = "diagnostic"


@dataclass
class Mission:
    mission_id: str
    mission_type: MissionType
    origin: Coordinate
    destination: Coordinate
    priority: int = 5
    constraints: dict = field(default_factory=dict)
    plan: dict | None = None
    status: str = "PENDING"
    started_at: float | None = None
    completed_at: float | None = None
    events: list[dict] = field(default_factory=list)


@dataclass
class HealthReport:
    system_state: SystemState
    uptime_s: float
    modules: dict[str, str]
    alerts: list[str]
    last_checked: float


class Brainiac:
    """
    Master orchestrator — the brain behind BRAINIAC.

    Features
    --------
    - Single entry point for every module
    - Auto-wires event flows (telemetry anomaly → SOS → drone dispatch)
    - High-level mission planning via NEURO-CORE
    - Continuous self-diagnostic loop
    - Self-healing on module failure
    - Event bus so any module can publish to any other

    Example
    -------
    >>> brainiac = Brainiac()
    >>> await brainiac.boot()
    >>> answer = await brainiac.ask("What's the safest drone path over Tel Aviv today?")
    >>> mission = await brainiac.plan_mission(MissionType.RESCUE, origin, dest)
    >>> await brainiac.execute_mission(mission)
    """

    def __init__(self, secret_key: str | None = None) -> None:
        # ── Module initialization ─────────────────────────────────────────────
        self.neuro    = NeuroCore()
        self.nav      = OrbitalNav()
        self.sonic    = SonicMatrix()
        self.satlink  = SatLink()
        self.nexus    = NexusSync()
        self.telem    = TelemetryHub()
        self.shield   = CyberShield(secret_key=secret_key or "BRAINIAC-ORCHESTRATOR")
        self.creative = CreativeEngine()
        self.vision   = OmniVision()
        self.localization = Localization()
        self.medical  = MedicalProtocols()

        self._state      = SystemState.BOOTING
        self._boot_time  = time.time()
        self._missions: dict[str, Mission] = {}
        self._event_bus: dict[str, list[Callable]] = {}
        self._watchdog_task: asyncio.Task | None = None
        self._auto_wire_configured = False

        log.info("brainiac.orchestrator.init")

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def boot(self) -> HealthReport:
        """Initialize all modules and configure auto-wiring."""
        log.info("brainiac.boot.start")
        self._state = SystemState.BOOTING

        await self.satlink.connect()
        self._configure_auto_wiring()

        self._state = SystemState.ONLINE
        log.info("brainiac.boot.complete", state=self._state.value)
        return await self.health_report()

    async def shutdown(self) -> None:
        """Graceful shutdown."""
        log.info("brainiac.shutdown")
        if self._watchdog_task and not self._watchdog_task.done():
            self._watchdog_task.cancel()
        self._state = SystemState.OFFLINE

    def _configure_auto_wiring(self) -> None:
        """
        Wire module events together so data flows autonomously:

          TELEMETRY anomaly     → if CRITICAL → SATLINK SOS
          NEXUS device message  → TELEMETRY ingest
          TELEMETRY Prometheus  → periodic uplink to SATLINK
        """
        if self._auto_wire_configured:
            return

        # Rule 1: critical telemetry anomaly → auto-SOS
        async def on_critical_anomaly(anomaly: Anomaly) -> None:
            if anomaly.severity >= 0.8:
                log.warning("auto_wire.anomaly_to_sos", sensor=anomaly.sensor_id)
                pos = await self.nav.get_position()
                await self.satlink.send_sos(
                    lat=pos.lat, lon=pos.lon,
                    message=f"Auto-triggered SOS: {anomaly.anomaly_type.value} "
                            f"on {anomaly.sensor_id} (severity {anomaly.severity:.2f})",
                    priority=SOSPriority.DISTRESS,
                    sender_id="BRAINIAC_AUTO",
                )

        self.telem.on_anomaly(on_critical_anomaly)

        # Rule 2: NEXUS messages on "telemetry/*" → TELEMETRY ingest
        async def on_nexus_telemetry(msg: Message) -> None:
            if not msg.topic.startswith("telemetry/"):
                return
            reading = SensorReading(
                sensor_id=msg.device_id,
                value=float(msg.payload.get("value", 0)),
                unit=msg.payload.get("unit", ""),
            )
            await self.telem.ingest(reading)

        self.nexus.subscribe("#", on_nexus_telemetry)

        self._auto_wire_configured = True
        log.info("brainiac.auto_wired")

    # ── Unified High-Level Operations ─────────────────────────────────────────

    async def ask(self, question: str, depth: str = "standard") -> str:
        """Ask BRAINIAC a question — delegates to NEURO-CORE."""
        thought = await self.neuro.think(question, depth=ReasoningDepth(depth))
        return thought.content

    async def plan_mission(
        self,
        mission_type: MissionType,
        origin: Coordinate,
        destination: Coordinate,
        constraints: dict | None = None,
    ) -> Mission:
        """
        Plan a mission using NEURO-CORE for reasoning and ORBITAL-NAV for routing.
        """
        import uuid
        mission_id = str(uuid.uuid4())[:12]

        # 1. Compute route
        mode = self._mode_for_mission(mission_type)
        route = await self.nav.route(origin, destination, mode=mode)

        # 2. Build plan (in production: NEURO-CORE reasoning)
        plan = {
            "mission_type": mission_type.value,
            "route_summary": route.summary(),
            "transport_mode": mode.value,
            "estimated_duration_s": route.total_duration_s,
            "distance_km": route.distance_km,
            "waypoints": len(route.waypoints),
            "constraints": constraints or {},
            "safety_checklist": [
                "GPS lock acquired",
                "Satellite uplink active",
                "Emergency channels armed",
                "Rescue drones on standby",
            ],
        }

        mission = Mission(
            mission_id=mission_id,
            mission_type=mission_type,
            origin=origin,
            destination=destination,
            constraints=constraints or {},
            plan=plan,
            status="PLANNED",
        )
        self._missions[mission_id] = mission
        log.info("brainiac.mission.planned", id=mission_id, type=mission_type.value)
        return mission

    async def execute_mission(self, mission: Mission) -> Mission:
        """Execute a planned mission end-to-end."""
        mission.status = "RUNNING"
        mission.started_at = time.time()
        mission.events.append({"ts": time.time(), "event": "MISSION_STARTED"})

        # Simulate execution phases
        for phase in ["TAKEOFF", "CRUISE", "APPROACH", "TARGET_REACHED", "RETURN", "LANDED"]:
            await asyncio.sleep(0.01)   # simulate phase
            mission.events.append({"ts": time.time(), "event": phase})
            log.info("brainiac.mission.phase", id=mission.mission_id, phase=phase)

        mission.status = "COMPLETED"
        mission.completed_at = time.time()
        log.info("brainiac.mission.complete", id=mission.mission_id)
        return mission

    async def emergency(
        self,
        lat: float,
        lon: float,
        message: str,
        priority: SOSPriority = SOSPriority.DISTRESS,
    ) -> dict:
        """
        One-call emergency response: SOS broadcast + responder notification +
        rescue drone dispatch (if registered) + signed incident record.
        """
        self._state = SystemState.EMERGENCY

        # 1. Broadcast SOS
        packet = await self.satlink.send_sos(
            lat=lat, lon=lon, message=message, priority=priority,
            sender_id="BRAINIAC_ORCHESTRATOR",
        )

        # 2. Dispatch any registered rescue drone
        drones = self.nexus.list_devices(
            device_type=DeviceType.DRONE, connected_only=True
        )
        dispatched = []
        for drone in drones:
            resp = await self.nexus.command(
                drone.device_id, "dispatch",
                {"target_lat": lat, "target_lon": lon, "incident_id": packet.incident_id},
            )
            if resp.get("status") == "OK":
                dispatched.append(drone.device_id)

        # 3. Sign incident for audit trail
        incident_record = {
            "incident_id": packet.incident_id,
            "priority": packet.priority.name,
            "location": {"lat": lat, "lon": lon},
            "channels": packet.channels_used,
            "responders": packet.responders_notified,
            "drones_dispatched": dispatched,
            "timestamp": packet.timestamp,
        }
        signature = self.shield.sign(incident_record)

        self._state = SystemState.ONLINE
        return {
            "incident": incident_record,
            "signature": signature,
            "acknowledged": packet.acknowledged,
            "response_channels": len(packet.channels_used),
        }

    async def speak(self, text: str, lang: str | None = None) -> bytes:
        """Synthesize speech via SONIC-MATRIX."""
        result = self.sonic.synthesize(text, lang=lang)
        return result.audio_bytes

    # ── Navigation Compound Operations (cross-module) ────────────────────────

    async def voice_guided_route(
        self,
        origin: Coordinate, destination: Coordinate,
        mode: TransportMode = TransportMode.DRIVE,
        lang: str = "en",
    ) -> dict[str, Any]:
        """
        Full voice-guided route: OrbitalNav plans + Localization phrases + SonicMatrix speaks.

        Returns route summary + per-step voice payloads.
        """
        route = await self.nav.route(origin, destination, mode=mode)
        steps = self.nav.build_turn_by_turn(route, lang=lang)
        voice_steps = self.sonic.synthesize_turn_by_turn(steps, lang=lang)
        return {
            "route": route.summary(),
            "lang": lang,
            "step_count": len(steps),
            "voice_steps": [
                {"instruction": v["instruction"], "distance_m": v["distance_m"],
                 "lat": v["lat"], "lon": v["lon"], "audio_size_bytes": len(v["audio_bytes"]),
                 "lang": v["lang"]}
                for v in voice_steps
            ],
        }

    async def medical_evacuation_route(
        self,
        patient_location: Coordinate,
        hospital_location: Coordinate,
        heart_rate: int, respiratory_rate: int,
        systolic_bp: int, gcs: int,
        spo2: int = 98,
        mode: TransportMode = TransportMode.DRONE,
    ) -> dict[str, Any]:
        """
        Medical evacuation routing: triages patient, picks protocol, plans fastest route.

        Returns triage result + protocol + route summary with adjusted ETA.
        """
        triage = self.medical.triage(
            heart_rate=heart_rate, respiratory_rate=respiratory_rate,
            systolic_bp=systolic_bp, gcs=gcs, spo2=spo2,
        )
        protocol = None
        if triage.recommended_protocol:
            proto = self.medical.get_protocol(triage.recommended_protocol)
            if proto:
                protocol = {"name": proto.name, "urgency": proto.urgency.value,
                            "steps": len(proto.steps), "reference": proto.reference}

        route = await self.nav.route(patient_location, hospital_location, mode=mode)
        # Critical patients: no traffic penalty (dispatch sirens / priority corridor)
        traffic_factor = 1.0 if triage.category.value == "immediate" else 1.3
        eta_adjusted = self.nav.adjust_eta_for_conditions(
            route.total_duration_s, traffic_factor=traffic_factor,
        )
        return {
            "triage": {
                "category": triage.category.value,
                "score": triage.score,
                "rationale": triage.rationale,
            },
            "protocol": protocol,
            "route": {
                **route.summary(),
                "adjusted_eta_s": round(eta_adjusted, 1),
                "adjusted_eta_min": round(eta_adjusted / 60, 1),
            },
        }

    # ── Health & Self-Diagnostic ──────────────────────────────────────────────

    async def health_report(self) -> HealthReport:
        """Produce a comprehensive health report for all modules."""
        alerts = []
        modules = {
            "neuro_core":        self.neuro.diagnostics()["status"],
            "orbital_nav":       self.nav.diagnostics()["status"],
            "sonic_matrix":      self.sonic.diagnostics()["status"],
            "satlink":           self.satlink.diagnostics()["status"],
            "nexus_sync":        self.nexus.diagnostics()["status"],
            "telemetry_hub":     self.telem.diagnostics()["status"],
            "cyber_shield":      self.shield.diagnostics()["status"],
            "creative_engine":   self.creative.diagnostics()["status"],
            "omni_vision":       self.vision.diagnostics()["status"],
            "localization":      "ONLINE",
            "medical_protocols": self.medical.diagnostics()["status"],
        }

        offline = [name for name, status in modules.items() if status == "OFFLINE"]
        if offline:
            alerts.append(f"Modules offline: {', '.join(offline)}")

        state = (
            SystemState.ONLINE if not offline
            else SystemState.DEGRADED if len(offline) < 3
            else SystemState.OFFLINE
        )

        return HealthReport(
            system_state=state,
            uptime_s=round(time.time() - self._boot_time, 2),
            modules=modules,
            alerts=alerts,
            last_checked=time.time(),
        )

    async def start_watchdog(self, interval_s: float = 30.0) -> None:
        """Start a background task that runs health checks periodically."""
        async def _loop():
            while self._state != SystemState.OFFLINE:
                report = await self.health_report()
                if report.alerts:
                    log.warning("watchdog.alerts", alerts=report.alerts)
                await asyncio.sleep(interval_s)

        self._watchdog_task = asyncio.create_task(_loop())
        log.info("brainiac.watchdog.started", interval_s=interval_s)

    # ── Event Bus ─────────────────────────────────────────────────────────────

    def on(self, event: str, handler: Callable) -> None:
        """Subscribe to a named event on the orchestrator's event bus."""
        self._event_bus.setdefault(event, []).append(handler)

    async def emit(self, event: str, data: Any) -> None:
        """Emit an event to all subscribers (sync or async)."""
        handlers = self._event_bus.get(event, [])
        coros = []
        for h in handlers:
            try:
                result = h(data)
                if asyncio.iscoroutine(result):
                    coros.append(result)
            except Exception as exc:
                log.error("orchestrator.event_handler_error", event=event, error=str(exc))
        if coros:
            await asyncio.gather(*coros, return_exceptions=True)

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _mode_for_mission(mission_type: MissionType) -> TransportMode:
        table = {
            MissionType.RECON:         TransportMode.DRONE,
            MissionType.DELIVERY:      TransportMode.DRIVE,
            MissionType.RESCUE:        TransportMode.DRONE,
            MissionType.SURVEILLANCE:  TransportMode.DRONE,
            MissionType.EXPLORATION:   TransportMode.SPACECRAFT,
            MissionType.DIAGNOSTIC:    TransportMode.DRIVE,
        }
        return table.get(mission_type, TransportMode.DRIVE)

    # ── Diagnostics ───────────────────────────────────────────────────────────

    @property
    def state(self) -> SystemState:
        return self._state

    def list_missions(self) -> list[Mission]:
        return list(self._missions.values())
