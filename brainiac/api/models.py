"""Pydantic request/response models for the BRAINIAC API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# ── NEURO-CORE ────────────────────────────────────────────────────────────────


class ThinkRequest(BaseModel):
    prompt: str = Field(
        ..., min_length=1, max_length=32768, description="Question or task for BRAINIAC"
    )
    depth: str = Field("standard", pattern="^(fast|standard|deep)$")
    use_cache: bool = True


class ThinkResponse(BaseModel):
    content: str
    model: str
    depth: str
    tokens_used: int
    latency_ms: float
    cached: bool


# ── ORBITAL-NAV ───────────────────────────────────────────────────────────────


class RouteRequest(BaseModel):
    origin_lat: float
    origin_lon: float
    dest_lat: float
    dest_lon: float
    mode: str = Field("driving", pattern="^(driving|walking|cycling|drone|spacecraft)$")
    alternatives: int = Field(3, ge=0, le=5)


class RouteResponse(BaseModel):
    origin: str
    destination: str
    distance_km: float
    eta_minutes: float
    mode: str
    precision: str
    satellite_corrected: bool
    waypoints: int
    hazards: list[str]
    alternatives: int


# ── SATLINK SOS ───────────────────────────────────────────────────────────────


class SOSRequest(BaseModel):
    lat: float
    lon: float
    message: str = Field(..., min_length=1, max_length=500)
    priority: str = Field("DISTRESS", pattern="^(ROUTINE|URGENT|DISTRESS|MAYDAY)$")
    alt_m: float = 0.0
    sender_id: str = "UNKNOWN"


class SOSResponse(BaseModel):
    incident_id: str
    acknowledged: bool
    channels_used: list[str]
    responders_notified: list[str]
    ack_timestamp: float | None


# ── TELEMETRY ─────────────────────────────────────────────────────────────────


class SensorReadingRequest(BaseModel):
    sensor_id: str
    value: float
    unit: str = ""
    quality: float = Field(1.0, ge=0.0, le=1.0)


class TelemetryIngestResponse(BaseModel):
    sensor_id: str
    anomaly_detected: bool
    anomaly_type: str | None
    anomaly_severity: float | None


# ── SONIC-MATRIX ──────────────────────────────────────────────────────────────


class TranslateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000)
    target_lang: str = Field(..., min_length=2, max_length=5)
    source_lang: str = "auto"


class DetectLanguageRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000)


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    lang: str | None = None


# ── CREATIVE-ENGINE ───────────────────────────────────────────────────────────


class ImagePromptRequest(BaseModel):
    subject: str = Field(..., min_length=1, max_length=1000)
    style: str = Field(
        "photorealistic",
        pattern="^(photorealistic|cinematic|illustration|technical|abstract|pixel_art|3d_render|blueprint)$",
    )
    width: int = Field(1024, ge=256, le=4096)
    height: int = Field(1024, ge=256, le=4096)


# ── NEXUS-SYNC ────────────────────────────────────────────────────────────────


class RegisterDeviceRequest(BaseModel):
    device_id: str
    device_type: str
    protocol: str
    endpoint: str
    name: str = ""
    capabilities: list[str] = []


class PublishRequest(BaseModel):
    device_id: str
    topic: str
    payload: dict[str, Any]
    qos: int = Field(1, ge=0, le=2)


# ── Generic ───────────────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    status: str
    version: str
    modules: dict[str, str]
    uptime_s: float
