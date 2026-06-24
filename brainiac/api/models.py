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
    mode: str = Field("driving", pattern="^(driving|walking|cycling|drone|submarine|spacecraft)$")
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


# ── QUANTUM-MIND ──────────────────────────────────────────────────────────────


class ScenarioInput(BaseModel):
    description: str
    probability: float = Field(0.5, ge=0.0, le=1.0)
    utility: float = Field(0.5)
    risk: float = Field(0.0, ge=0.0, le=1.0)
    tags: list[str] = []


class SuperposeRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    scenarios: list[ScenarioInput] = Field(..., min_length=2)
    strategy: str = Field(
        "max_expected_value",
        pattern="^(max_probability|weighted_random|min_risk|max_expected_value)$",
    )


class CollapseRequest(BaseModel):
    superposition_id: str


class DecisionMatrixRequest(BaseModel):
    options: list[str] = Field(..., min_length=2)
    criteria: list[str] = Field(..., min_length=1)
    scores: dict[str, dict[str, float]]
    weights: list[float] | None = None


class PredictRequest(BaseModel):
    variable: str = Field(..., min_length=1, max_length=200)
    history: list[float] = Field(..., min_length=2)
    horizon: int = Field(10, ge=1, le=100)
    alpha: float = Field(0.3, ge=0.01, le=0.99)
    confidence: float = Field(0.95, ge=0.5, le=0.99)


# ── EMOTION-ENGINE ────────────────────────────────────────────────────────────


class SentimentRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000)


class EmpathizeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000)


class AdaptMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000)
    tone: str = Field(
        "formal",
        pattern="^(formal|empathetic|encouraging|analytical|urgent|playful|reassuring)$",
    )


class PersonalityRequest(BaseModel):
    text_samples: list[str] = Field(..., min_length=1)


# ── NEURAL-MATRIX ──────────────────────────────────────────────────────────────


class SpawnAgentRequest(BaseModel):
    role: str = Field(
        ...,
        pattern="^(analyst|strategist|executor|critic|coordinator|researcher|sentinel|oracle)$",
    )
    name: str | None = None
    capabilities: list[str] = []
    expertise: float = Field(0.8, ge=0.0, le=1.0)


class DecomposeTaskRequest(BaseModel):
    root_task: str = Field(..., min_length=1, max_length=2000)
    subtasks: list[dict[str, Any]]


class VoteRequest(BaseModel):
    proposal: str = Field(..., min_length=1, max_length=1000)
    options: list[str] = Field(..., min_length=2)
    method: str = Field(
        "majority",
        pattern="^(majority|supermajority|weighted|unanimous|borda)$",
    )


class BallotRequest(BaseModel):
    vote_id: str
    agent_id: str
    choice: Any  # str or list[str] depending on method


# ── Generic ───────────────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    status: str
    version: str
    modules: dict[str, str]
    uptime_s: float
