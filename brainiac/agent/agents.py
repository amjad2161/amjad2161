"""
GANE Specialized Agents — domain-specific agents on top of AgentLoop.

Built-in agents:
  - TelemetryAnalystAgent : reads sensor data, detects anomalies, files reports
  - MedicalContentAgent   : generates AHA-compliant medical educational content
  - NavigationAgent       : satellite-fused routing + mission planning
"""
from __future__ import annotations

import time
import uuid
from typing import TYPE_CHECKING

import structlog

from .base import BaseAgent
from .loop import AgentConfig, AgentLoop
from .memory import AgentMemory, Episode, FactSource
from .tools import ToolDef, ToolRegistry

if TYPE_CHECKING:
    from brainiac.core.creative_engine import CreativeEngine
    from brainiac.core.orbital_nav import OrbitalNav
    from brainiac.core.telemetry_hub import TelemetryHub
    from brainiac.core.medical_protocols import MedicalProtocols

log = structlog.get_logger("brainiac.agent.agents")


# ── Telemetry Analyst Agent ───────────────────────────────────────────────────

_TELEMETRY_SYSTEM = """\
You are GANE Telemetry Analyst — an expert sensor data engineer embedded in BRAINIAC.

Your job:
1. Analyze incoming telemetry streams for anomalies (spikes, drops, flatlines).
2. Correlate anomalies across multiple sensors to identify root causes.
3. Generate concise incident reports with severity, affected sensors, and recommended actions.
4. Use `query_telemetry` to retrieve live data and `create_anomaly_report` to log findings.

Respond factually. Cite sensor IDs and timestamps. Never speculate without data.
"""


def _build_telemetry_tools(
    telem: "TelemetryHub | None" = None,
    auto_approve: bool = True,
) -> ToolRegistry:
    registry = ToolRegistry(auto_approve=auto_approve)

    async def query_telemetry(sensor_id: str | None = None, window_s: int = 3600) -> dict:
        if telem is None:
            return {
                "sensor_id": sensor_id or "ALL",
                "window_s": window_s,
                "readings": 120, "mean": 22.4, "std_dev": 0.8,
                "min": 21.1, "max": 24.7, "anomalies": [],
                "note": "synthetic_fallback",
            }
        summary = telem.diagnostics()
        streams = summary.get("streams", {})
        if sensor_id:
            return streams.get(sensor_id, {"error": "sensor not found"})
        return streams

    async def create_anomaly_report(
        sensor_id: str, severity: str, description: str, recommended_action: str,
    ) -> dict:
        report = {
            "incident_id": f"INC-{uuid.uuid4().hex[:8]}",
            "sensor_id": sensor_id, "severity": severity,
            "description": description, "recommended_action": recommended_action,
            "created_at": time.time(), "status": "OPEN",
        }
        log.warning("telemetry_analyst.anomaly_report", **report)
        return report

    async def acknowledge_anomaly(incident_id: str, notes: str = "") -> dict:
        return {"incident_id": incident_id, "status": "ACKNOWLEDGED", "notes": notes}

    registry.register(ToolDef(
        name="query_telemetry",
        description="Retrieve live telemetry summary for a sensor or all sensors",
        parameters={
            "type": "object",
            "properties": {
                "sensor_id": {"type": "string", "description": "Sensor ID, or omit for all sensors"},
                "window_s": {"type": "integer", "description": "Time window in seconds", "default": 3600},
            },
        },
        handler=query_telemetry,
        reversible=True,
    ))
    registry.register(ToolDef(
        name="create_anomaly_report",
        description="Create and log an anomaly incident report",
        parameters={
            "type": "object",
            "properties": {
                "sensor_id": {"type": "string"},
                "severity": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"]},
                "description": {"type": "string"},
                "recommended_action": {"type": "string"},
            },
            "required": ["sensor_id", "severity", "description", "recommended_action"],
        },
        handler=create_anomaly_report,
        reversible=True,
    ))
    registry.register(ToolDef(
        name="acknowledge_anomaly",
        description="Mark an anomaly incident as acknowledged",
        parameters={
            "type": "object",
            "properties": {
                "incident_id": {"type": "string"},
                "notes": {"type": "string"},
            },
            "required": ["incident_id"],
        },
        handler=acknowledge_anomaly,
        reversible=False,
    ))
    return registry


class TelemetryAnalystAgent(BaseAgent):
    """G.A.N.E Telemetry Analyst — wires into TelemetryHub for live data."""

    name = "telemetry-analyst"

    def __init__(
        self,
        memory: AgentMemory | None = None,
        telem: "TelemetryHub | None" = None,
        api_key: str | None = None,
        auto_approve: bool = True,
    ) -> None:
        self.memory = memory or AgentMemory()
        config = AgentConfig(
            name=self.name,
            system_prompt=_TELEMETRY_SYSTEM,
            fact_source=FactSource.TELEMETRY,
            auto_approve_tools=auto_approve,
        )
        tools = _build_telemetry_tools(telem, auto_approve)
        self._loop = AgentLoop(config, tools, self.memory, api_key=api_key)
        log.info("telemetry_analyst.init")

    async def run(self, prompt: str) -> Episode:
        return await self._loop.run(prompt)

    async def analyze(self, prompt: str = "Analyze the last 60 minutes of telemetry for anomalies.") -> Episode:
        return await self.run(prompt)


# ── Medical Content Agent ─────────────────────────────────────────────────────

_MEDICAL_SYSTEM = """\
You are GANE Medical Content — an expert medical educator embedded in BRAINIAC.

Specializations:
- AHA (American Heart Association) resuscitation guidelines (ACLS/BLS/PALS)
- Clinical protocol generation for emergency medicine
- Medical education content (infographics, scripts, summaries)
- Drug dosage calculations (with appropriate safety disclaimers)

Guidelines:
- Always cite the guideline version (e.g., "AHA 2020 ACLS Guidelines").
- Include safety disclaimers for drug dosages.
- Content is for EDUCATIONAL PURPOSES ONLY — not direct clinical advice.
- Use `generate_content` to produce structured educational materials.
"""

def _build_medical_tools(
    creative: "CreativeEngine | None" = None,
    medical: "MedicalProtocols | None" = None,
    auto_approve: bool = True,
) -> ToolRegistry:
    # Lazy-import to avoid circular: MedicalProtocols owns the canonical drug database.
    from brainiac.core.medical_protocols import MedicalProtocols as _MP
    med_engine = medical or _MP()

    registry = ToolRegistry(auto_approve=auto_approve)

    async def generate_content(
        content_type: str, topic: str,
        target_audience: str = "healthcare professional",
        format: str = "structured_text",
    ) -> dict:
        return {
            "content_type": content_type, "topic": topic,
            "target_audience": target_audience, "format": format,
            "content": f"[{content_type.upper()} on {topic} for {target_audience}] — Generated by GANE Medical",
            "disclaimer": "EDUCATIONAL PURPOSES ONLY. Not a substitute for clinical judgment.",
            "guideline_version": "AHA 2020",
        }

    async def calculate_drug_dose(drug: str, weight_kg: float, indication: str) -> dict:
        result = med_engine.calculate_dose(drug, weight_kg)
        if "error" in result:
            return {"error": result["error"]}
        return {**result, "indication": indication}

    async def lookup_protocol(name: str) -> dict:
        proto = med_engine.get_protocol(name)
        if not proto:
            return {"error": f"Protocol '{name}' not found",
                    "available": med_engine.list_protocols()}
        return {
            "name": proto.name,
            "category": proto.category.value,
            "urgency": proto.urgency.value,
            "steps": [{"n": s.step_number, "action": s.action, "critical": s.critical}
                      for s in proto.steps],
            "reference": proto.reference,
        }

    async def triage_vitals(
        heart_rate: int, respiratory_rate: int, systolic_bp: int,
        gcs: int, spo2: int = 98, temperature_c: float = 37.0,
    ) -> dict:
        result = med_engine.triage(
            heart_rate=heart_rate, respiratory_rate=respiratory_rate,
            systolic_bp=systolic_bp, gcs=gcs, spo2=spo2, temperature_c=temperature_c,
        )
        return {
            "category": result.category.value,
            "score": result.score,
            "rationale": result.rationale,
            "recommended_protocol": result.recommended_protocol,
        }

    async def generate_badge_label(text: str, style: str = "clinical") -> dict:
        if creative is None:
            return {"text": text, "style": style, "svg": None, "note": "creative_engine_not_wired"}
        svg = creative.generate_svg_badge(text, color="#00cc88")
        return {"svg": svg, "text": text, "style": style}

    registry.register(ToolDef(
        name="generate_content",
        description="Generate structured medical educational content",
        parameters={
            "type": "object",
            "properties": {
                "content_type": {"type": "string", "enum": ["protocol", "infographic", "script", "summary", "quiz"]},
                "topic": {"type": "string"},
                "target_audience": {"type": "string"},
                "format": {"type": "string"},
            },
            "required": ["content_type", "topic"],
        },
        handler=generate_content, reversible=True,
    ))
    registry.register(ToolDef(
        name="calculate_drug_dose",
        description="Calculate weight-based drug dose with AHA guideline reference",
        parameters={
            "type": "object",
            "properties": {
                "drug": {"type": "string", "description": "Drug name (e.g., epinephrine, amiodarone)"},
                "weight_kg": {"type": "number"},
                "indication": {"type": "string"},
            },
            "required": ["drug", "weight_kg", "indication"],
        },
        handler=calculate_drug_dose, reversible=True,
    ))
    registry.register(ToolDef(
        name="lookup_protocol",
        description="Look up a clinical protocol by name (e.g., acls_cardiac_arrest, stroke_code, stemi_protocol)",
        parameters={
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
        handler=lookup_protocol, reversible=True,
    ))
    registry.register(ToolDef(
        name="triage_vitals",
        description="Score a patient's vitals and recommend a protocol",
        parameters={
            "type": "object",
            "properties": {
                "heart_rate": {"type": "integer"},
                "respiratory_rate": {"type": "integer"},
                "systolic_bp": {"type": "integer"},
                "gcs": {"type": "integer"},
                "spo2": {"type": "integer"},
                "temperature_c": {"type": "number"},
            },
            "required": ["heart_rate", "respiratory_rate", "systolic_bp", "gcs"],
        },
        handler=triage_vitals, reversible=True,
    ))
    registry.register(ToolDef(
        name="generate_badge_label",
        description="Generate an SVG badge for a medical protocol label (returns null SVG when CreativeEngine is unavailable)",
        parameters={
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "style": {"type": "string"},
            },
            "required": ["text"],
        },
        handler=generate_badge_label, reversible=True,
    ))
    return registry


class MedicalContentAgent(BaseAgent):
    """G.A.N.E Medical Content — AHA-compliant protocol generator."""

    name = "medical-content"

    def __init__(
        self,
        memory: AgentMemory | None = None,
        creative: "CreativeEngine | None" = None,
        medical: "MedicalProtocols | None" = None,
        api_key: str | None = None,
        auto_approve: bool = True,
    ) -> None:
        self.memory = memory or AgentMemory()
        config = AgentConfig(
            name=self.name,
            system_prompt=_MEDICAL_SYSTEM,
            fact_source=FactSource.MEDICAL,
            auto_approve_tools=auto_approve,
        )
        tools = _build_medical_tools(creative, medical, auto_approve)
        self._loop = AgentLoop(config, tools, self.memory, api_key=api_key)
        log.info("medical_content.init")

    async def run(self, prompt: str) -> Episode:
        return await self._loop.run(prompt)

    async def generate(self, prompt: str) -> Episode:
        return await self.run(prompt)


# ── Navigation Agent ──────────────────────────────────────────────────────────

_NAVIGATION_SYSTEM = """\
You are GANE Navigation — an expert satellite-fused navigation specialist embedded in BRAINIAC.

Capabilities:
- Multi-modal routing (drive, walk, bike, drone, spacecraft, submarine)
- ETA estimation with real-world traffic and weather corrections
- Multi-stop route optimization (greedy TSP)
- Mission planning (recon, delivery, rescue, surveillance, exploration)
- Geofence evaluation (circle and polygon)

Guidelines:
- Cite coordinates in (lat, lon) decimal degrees.
- Always specify the transport mode used and ETA in minutes.
- Use `compute_route` for single-leg, `multi_stop_route` for waypoint chains,
  and `estimate_eta` for fast-path ETA-only queries.
- Use `evaluate_geofence` to check if a point is inside a circular or polygonal area.
"""


def _build_navigation_tools(
    nav: "OrbitalNav | None" = None,
    auto_approve: bool = True,
) -> ToolRegistry:
    from brainiac.core.orbital_nav import Coordinate, OrbitalNav, TransportMode

    registry = ToolRegistry(auto_approve=auto_approve)
    nav_engine = nav or OrbitalNav()

    def _coord(lat: float, lon: float, alt_m: float = 0.0) -> Coordinate:
        return Coordinate(lat=lat, lon=lon, alt_m=alt_m)

    def _mode(name: str) -> TransportMode:
        try:
            return TransportMode(name.lower())
        except ValueError:
            return TransportMode.DRIVE

    async def estimate_eta(
        origin_lat: float, origin_lon: float,
        dest_lat: float, dest_lon: float,
        mode: str = "driving",
    ) -> dict:
        return nav_engine.estimate_eta(
            _coord(origin_lat, origin_lon),
            _coord(dest_lat, dest_lon),
            mode=_mode(mode),
        )

    async def compute_route(
        origin_lat: float, origin_lon: float,
        dest_lat: float, dest_lon: float,
        mode: str = "driving",
        alternatives: int = 1,
    ) -> dict:
        route = await nav_engine.route(
            _coord(origin_lat, origin_lon),
            _coord(dest_lat, dest_lon),
            mode=_mode(mode),
            alternatives=alternatives,
        )
        return route.summary()

    async def multi_stop_route(
        origin_lat: float, origin_lon: float,
        stops: list[list[float]],
        mode: str = "driving",
    ) -> dict:
        coords = [_coord(s[0], s[1]) for s in stops]
        legs = await nav_engine.route_multi_stop(
            _coord(origin_lat, origin_lon), coords, mode=_mode(mode),
        )
        return {
            "legs": len(legs),
            "total_km": round(sum(leg.distance_km for leg in legs), 2),
            "total_minutes": round(sum(leg.eta_minutes for leg in legs), 1),
            "summaries": [leg.summary() for leg in legs],
        }

    async def evaluate_geofence(
        point_lat: float, point_lon: float,
        center_lat: float | None = None, center_lon: float | None = None,
        radius_m: float | None = None,
        polygon: list[list[float]] | None = None,
    ) -> dict:
        point = _coord(point_lat, point_lon)
        if polygon:
            poly = [_coord(p[0], p[1]) for p in polygon]
            inside = nav_engine.geofence_polygon(point, poly)
            return {"inside": inside, "type": "polygon", "vertices": len(poly)}
        if center_lat is not None and center_lon is not None and radius_m is not None:
            inside = nav_engine.geofence_circle(point, _coord(center_lat, center_lon), radius_m)
            return {"inside": inside, "type": "circle", "radius_m": radius_m}
        return {"error": "Provide either (center+radius) or polygon"}

    async def get_position() -> dict:
        coord = await nav_engine.get_position()
        return {
            "lat": coord.lat, "lon": coord.lon, "alt_m": coord.alt_m,
            "accuracy_m": coord.accuracy_m, "timestamp": coord.timestamp,
        }

    registry.register(ToolDef(
        name="estimate_eta",
        description="Fast ETA estimate using haversine + typical speeds",
        parameters={
            "type": "object",
            "properties": {
                "origin_lat": {"type": "number"}, "origin_lon": {"type": "number"},
                "dest_lat": {"type": "number"},   "dest_lon":   {"type": "number"},
                "mode": {"type": "string", "enum": ["driving", "walking", "cycling", "drone", "spacecraft", "submarine"]},
            },
            "required": ["origin_lat", "origin_lon", "dest_lat", "dest_lon"],
        },
        handler=estimate_eta, reversible=True,
    ))
    registry.register(ToolDef(
        name="compute_route",
        description="Compute an optimal route between two coordinates with full waypoint detail",
        parameters={
            "type": "object",
            "properties": {
                "origin_lat": {"type": "number"}, "origin_lon": {"type": "number"},
                "dest_lat": {"type": "number"},   "dest_lon":   {"type": "number"},
                "mode": {"type": "string", "enum": ["driving", "walking", "cycling", "drone", "spacecraft", "submarine"]},
                "alternatives": {"type": "integer", "default": 1},
            },
            "required": ["origin_lat", "origin_lon", "dest_lat", "dest_lon"],
        },
        handler=compute_route, reversible=True, timeout_s=15.0,
    ))
    registry.register(ToolDef(
        name="multi_stop_route",
        description="Optimize a route through multiple stops (nearest-neighbour TSP)",
        parameters={
            "type": "object",
            "properties": {
                "origin_lat": {"type": "number"}, "origin_lon": {"type": "number"},
                "stops": {
                    "type": "array",
                    "items": {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2},
                },
                "mode": {"type": "string"},
            },
            "required": ["origin_lat", "origin_lon", "stops"],
        },
        handler=multi_stop_route, reversible=True, timeout_s=30.0,
    ))
    registry.register(ToolDef(
        name="evaluate_geofence",
        description="Check whether a point lies inside a circular or polygonal geofence",
        parameters={
            "type": "object",
            "properties": {
                "point_lat": {"type": "number"}, "point_lon": {"type": "number"},
                "center_lat": {"type": "number"}, "center_lon": {"type": "number"},
                "radius_m": {"type": "number"},
                "polygon": {"type": "array", "items": {"type": "array", "items": {"type": "number"}}},
            },
            "required": ["point_lat", "point_lon"],
        },
        handler=evaluate_geofence, reversible=True,
    ))
    registry.register(ToolDef(
        name="get_position",
        description="Return the current navigation position with accuracy",
        parameters={"type": "object", "properties": {}},
        handler=get_position, reversible=True,
    ))
    return registry


class NavigationAgent(BaseAgent):
    """G.A.N.E Navigation — satellite-fused routing and mission planning."""

    name = "navigation"

    def __init__(
        self,
        memory: AgentMemory | None = None,
        nav: "OrbitalNav | None" = None,
        api_key: str | None = None,
        auto_approve: bool = True,
    ) -> None:
        self.memory = memory or AgentMemory()
        config = AgentConfig(
            name=self.name,
            system_prompt=_NAVIGATION_SYSTEM,
            fact_source=FactSource.NAVIGATION,
            auto_approve_tools=auto_approve,
        )
        tools = _build_navigation_tools(nav, auto_approve)
        self._loop = AgentLoop(config, tools, self.memory, api_key=api_key)
        log.info("navigation_agent.init")

    async def run(self, prompt: str) -> Episode:
        return await self._loop.run(prompt)

    async def plan(self, prompt: str) -> Episode:
        return await self.run(prompt)
