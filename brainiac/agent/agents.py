"""
GANE Specialized Agents — Domain-specific agents built on the AgentLoop.

Agents:
  - TelemetryAnalystAgent : reads sensor data, detects anomalies, creates issues
  - MedicalContentAgent   : generates medical educational content and AHA-compliant protocols
"""
from __future__ import annotations

import asyncio
import os
import time
from typing import TYPE_CHECKING, Any

import structlog

from .loop import AgentLoop, AgentConfig
from .memory import AgentMemory, Fact, FactSource
from .tools import ToolDef, ToolRegistry

if TYPE_CHECKING:
    from brainiac.core.telemetry_hub import TelemetryHub
    from brainiac.core.orbital_nav import OrbitalNav
    from brainiac.core.creative_engine import CreativeEngine

log = structlog.get_logger("brainiac.agent.agents")


# ── Telemetry Analyst Agent ───────────────────────────────────────────────────

_TELEMETRY_SYSTEM = """\
You are GANE Telemetry Analyst — an expert sensor data engineer embedded in the BRAINIAC system.

Your job:
1. Analyze incoming telemetry streams for anomalies (spikes, drops, flatlines).
2. Correlate anomalies across multiple sensors to identify root causes.
3. Generate concise incident reports with severity, affected sensors, and recommended actions.
4. Use the `query_telemetry` tool to retrieve live data and `create_anomaly_report` to log findings.

Respond factually. Cite sensor IDs and timestamps. Never speculate without data.
"""


def _build_telemetry_tools(
    telem: "TelemetryHub | None" = None,
    auto_approve: bool = True,
) -> ToolRegistry:
    registry = ToolRegistry(auto_approve=auto_approve)

    async def query_telemetry(sensor_id: str | None = None, window_s: int = 3600) -> dict:
        """Retrieve recent telemetry summary for a sensor (or all sensors)."""
        if telem is None:
            # Synthetic fallback when no live hub is wired
            return {
                "sensor_id": sensor_id or "ALL",
                "window_s": window_s,
                "readings": 120,
                "mean": 22.4,
                "std_dev": 0.8,
                "min": 21.1,
                "max": 24.7,
                "anomalies": [],
                "note": "synthetic_fallback",
            }
        summary = telem.diagnostics()
        streams = summary.get("streams", {})
        if sensor_id:
            return streams.get(sensor_id, {"error": "sensor not found"})
        return streams

    async def create_anomaly_report(
        sensor_id: str,
        severity: str,
        description: str,
        recommended_action: str,
    ) -> dict:
        """Create and log an anomaly incident report."""
        report = {
            "incident_id": f"INC-{int(time.time())}",
            "sensor_id": sensor_id,
            "severity": severity,
            "description": description,
            "recommended_action": recommended_action,
            "created_at": time.time(),
            "status": "OPEN",
        }
        log.warning("telemetry_analyst.anomaly_report", **report)
        return report

    async def acknowledge_anomaly(incident_id: str, notes: str = "") -> dict:
        """Acknowledge an anomaly incident (non-reversible)."""
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


class TelemetryAnalystAgent:
    """
    G.A.N.E Telemetry Analyst — reads sensor streams, flags anomalies,
    produces structured incident reports.

    Wires directly into BRAINIAC's TelemetryHub for live data.
    """

    def __init__(
        self,
        memory: AgentMemory | None = None,
        telem: "TelemetryHub | None" = None,
        api_key: str | None = None,
        auto_approve: bool = True,
    ) -> None:
        self.memory = memory or AgentMemory()
        config = AgentConfig(
            name="telemetry-analyst",
            system_prompt=_TELEMETRY_SYSTEM,
            model="claude-sonnet-4-6",
            fact_source=FactSource.TELEMETRY,
            auto_approve_tools=auto_approve,
        )
        tools = _build_telemetry_tools(telem, auto_approve)
        self._loop = AgentLoop(config, tools, self.memory, api_key=api_key)
        log.info("telemetry_analyst.init")

    async def analyze(self, prompt: str = "Analyze the last 60 minutes of telemetry for anomalies."):
        """Run a full analysis and return the episode."""
        return await self._loop.run(prompt)

    async def stream_analysis(self, prompt: str):
        """Stream tokens from the analysis (no tool calls)."""
        async for token in self._loop.stream(prompt):
            yield token


# ── Medical Content Agent ─────────────────────────────────────────────────────

_MEDICAL_SYSTEM = """\
You are GANE Medical Content — an expert medical educator embedded in the BRAINIAC system.

Specializations:
- AHA (American Heart Association) resuscitation guidelines (ACLS/BLS/PALS)
- Clinical protocol generation for emergency medicine
- Medical education content (infographics, scripts, summaries)
- Drug dosage calculations (with appropriate safety disclaimers)

Guidelines:
- Always cite the guideline version (e.g., "AHA 2020 ACLS Guidelines").
- Include safety disclaimers for drug dosages.
- Content is for EDUCATIONAL PURPOSES ONLY — not direct clinical advice.
- Use the `generate_content` tool to produce structured educational materials.
"""


def _build_medical_tools(
    creative: "CreativeEngine | None" = None,
    auto_approve: bool = True,
) -> ToolRegistry:
    registry = ToolRegistry(auto_approve=auto_approve)

    async def generate_content(
        content_type: str,
        topic: str,
        target_audience: str = "healthcare professional",
        format: str = "structured_text",
    ) -> dict:
        """Generate structured medical educational content."""
        return {
            "content_type": content_type,
            "topic": topic,
            "target_audience": target_audience,
            "format": format,
            "content": f"[{content_type.upper()} on {topic} for {target_audience}] — Generated by GANE Medical",
            "disclaimer": "EDUCATIONAL PURPOSES ONLY. Not a substitute for clinical judgment.",
            "guideline_version": "AHA 2020",
        }

    async def calculate_drug_dose(
        drug: str,
        weight_kg: float,
        indication: str,
    ) -> dict:
        """Calculate weight-based drug dose with AHA guideline reference."""
        # Standard ACLS doses (simplified)
        _doses = {
            "epinephrine": {"dose_mg_per_kg": 0.01, "max_mg": 1.0, "route": "IV/IO"},
            "amiodarone": {"dose_mg_per_kg": 5.0, "max_mg": 300.0, "route": "IV"},
            "atropine": {"dose_mg_per_kg": 0.02, "max_mg": 3.0, "route": "IV/IO"},
        }
        drug_lower = drug.lower()
        if drug_lower not in _doses:
            return {"error": f"Drug '{drug}' not in formulary. Consult pharmacist."}
        info = _doses[drug_lower]
        calculated = min(weight_kg * info["dose_mg_per_kg"], info["max_mg"])
        return {
            "drug": drug,
            "weight_kg": weight_kg,
            "indication": indication,
            "calculated_dose_mg": round(calculated, 2),
            "max_dose_mg": info["max_mg"],
            "route": info["route"],
            "guideline": "AHA 2020 ACLS",
            "disclaimer": "VERIFY WITH PHARMACIST. Educational use only.",
        }

    async def generate_badge_label(text: str, style: str = "clinical") -> dict:
        """Generate an SVG badge for a medical protocol label."""
        if creative:
            svg = creative.generate_svg_badge(text, color="#00cc88")
            return {"svg": svg, "text": text, "style": style}
        return {"text": text, "style": style, "note": "creative_engine_not_wired"}

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
        handler=generate_content,
        reversible=True,
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
        handler=calculate_drug_dose,
        reversible=True,
    ))

    registry.register(ToolDef(
        name="generate_badge_label",
        description="Generate an SVG badge for a medical protocol label",
        parameters={
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "style": {"type": "string"},
            },
            "required": ["text"],
        },
        handler=generate_badge_label,
        reversible=True,
    ))

    return registry


class MedicalContentAgent:
    """
    G.A.N.E Medical Content — AHA-compliant protocol generator and medical educator.
    """

    def __init__(
        self,
        memory: AgentMemory | None = None,
        creative: "CreativeEngine | None" = None,
        api_key: str | None = None,
        auto_approve: bool = True,
    ) -> None:
        self.memory = memory or AgentMemory()
        config = AgentConfig(
            name="medical-content",
            system_prompt=_MEDICAL_SYSTEM,
            model="claude-sonnet-4-6",
            fact_source=FactSource.MEDICAL,
            auto_approve_tools=auto_approve,
        )
        tools = _build_medical_tools(creative, auto_approve)
        self._loop = AgentLoop(config, tools, self.memory, api_key=api_key)
        log.info("medical_content.init")

    async def generate(self, prompt: str):
        """Generate medical educational content and return the episode."""
        return await self._loop.run(prompt)
