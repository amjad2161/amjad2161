"""
BRAINIAC API — FastAPI Application Entry Point
===============================================
All 9 core modules exposed via REST + WebSocket endpoints.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from sse_starlette.sse import EventSourceResponse

from brainiac.core import (
    NeuroCore, OrbitalNav, SonicMatrix, SatLink,
    NexusSync, TelemetryHub, CyberShield, CreativeEngine, OmniVision,
)
from brainiac.core.neuro_core import ReasoningDepth
from brainiac.core.orbital_nav import Coordinate, TransportMode
from brainiac.core.satlink import SOSPriority
from brainiac.core.telemetry_hub import SensorReading
from brainiac.core.medical_protocols import MedicalProtocols, ProtocolCategory, DrugRoute
from brainiac.api.models import (
    ThinkRequest, ThinkResponse,
    RouteRequest, RouteResponse,
    SOSRequest, SOSResponse,
    SensorReadingRequest, TelemetryIngestResponse,
    TranslateRequest, DetectLanguageRequest, TTSRequest,
    ImagePromptRequest,
    RegisterDeviceRequest, PublishRequest,
    HealthResponse,
)
from brainiac.agent import AgentRouter

log = structlog.get_logger("brainiac.api")
_BOOT_TIME = time.time()

# ── Constants ─────────────────────────────────────────────────────────────────
_SCAN_FIELDS = frozenset({"prompt", "text", "message", "subject", "description", "query"})
_MAX_BODY_BYTES        = 10 * 1024 * 1024   # 10 MB hard cap on request body
_MAX_VISION_BYTES      = 5 * 1024 * 1024    # 5 MB max image upload
_MAX_SCAN_BYTES        = 256 * 1024         # only scan first 256 KB of JSON

# ── Module singletons ─────────────────────────────────────────────────────────
neuro   = NeuroCore(api_key=os.getenv("ANTHROPIC_API_KEY"))
nav     = OrbitalNav()
sonic   = SonicMatrix()
satlink = SatLink()
nexus   = NexusSync()
telem   = TelemetryHub()
shield  = CyberShield(secret_key=os.getenv("BRAINIAC_SECRET", "CHANGE-IN-PRODUCTION"))
creative= CreativeEngine()
vision  = OmniVision()
medical = MedicalProtocols()

_agent_router = AgentRouter(
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    telem=telem, creative=creative, nav=nav, medical=medical,
    auto_approve=True,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    log.info("brainiac.startup")
    await satlink.connect()
    yield
    log.info("brainiac.shutdown")


app = FastAPI(
    title="BRAINIAC AI",
    description="Autonomous Super Intelligence System — REST + WebSocket API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Static frontend (map viewer) ──────────────────────────────────────────────
_STATIC_DIR = Path(__file__).parent / "static"
if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.get("/nav", include_in_schema=False)
async def nav_viewer():
    """Serve the interactive map viewer."""
    index = _STATIC_DIR / "nav.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail="Map viewer not installed")
    return FileResponse(str(index), media_type="text/html")


# ── Security middleware ───────────────────────────────────────────────────────

@app.middleware("http")
async def security_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "0.0.0.0"

    if not shield.check_rate_limit(client_ip):
        return JSONResponse(status_code=429, content={"error": "Rate limit exceeded"})

    # Hard cap on total request body size declared via Content-Length
    cl = request.headers.get("content-length")
    if cl and cl.isdigit() and int(cl) > _MAX_BODY_BYTES:
        return JSONResponse(status_code=413, content={"error": "Request body too large"})

    # Scan parsed JSON field values for injection — never the raw body, never binary uploads
    if request.method in ("POST", "PUT", "PATCH"):
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            try:
                body_bytes = await request.body()
                if len(body_bytes) > _MAX_BODY_BYTES:
                    return JSONResponse(status_code=413, content={"error": "Request body too large"})
                # json.loads accepts bytes directly (Python 3.6+), no decode needed
                scan_window = body_bytes if len(body_bytes) <= _MAX_SCAN_BYTES else body_bytes[:_MAX_SCAN_BYTES]
                try:
                    body_json = json.loads(scan_window)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    body_json = None
                if isinstance(body_json, dict):
                    for key, val in body_json.items():
                        if key in _SCAN_FIELDS and isinstance(val, str):
                            threat = shield.scan_input(val, source_ip=client_ip)
                            if threat and threat.threat_level.value >= 3:
                                return JSONResponse(status_code=400, content={"error": "Malicious input detected"})
            except Exception:
                pass

    response = await call_next(request)
    response.headers["X-BRAINIAC-Node"] = "GENESIS-1"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(self)"
    response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
    return response


# ── Health / Status ───────────────────────────────────────────────────────────

@app.get("/", tags=["System"])
async def root():
    return {"system": "BRAINIAC AI", "status": "ONLINE", "version": "1.0.0"}


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health():
    return HealthResponse(
        status="ONLINE",
        version="2.0.0",
        modules={
            "neuro_core":        "ONLINE",
            "orbital_nav":       "ONLINE",
            "satlink":           "ONLINE",
            "sonic_matrix":      "ONLINE",
            "nexus_sync":        "ONLINE",
            "telemetry_hub":     "ONLINE",
            "cyber_shield":      "ONLINE",
            "creative_engine":   "ONLINE",
            "omni_vision":       "ONLINE",
            "localization":      "ONLINE",
            "medical_protocols": "ONLINE",
        },
        uptime_s=round(time.time() - _BOOT_TIME, 1),
    )


@app.get("/diagnostics", tags=["System"])
async def diagnostics():
    return {
        "neuro_core":      neuro.diagnostics(),
        "orbital_nav":     nav.diagnostics(),
        "satlink":         satlink.diagnostics(),
        "sonic_matrix":    sonic.diagnostics(),
        "nexus_sync":      nexus.diagnostics(),
        "telemetry_hub":   telem.diagnostics(),
        "cyber_shield":    shield.diagnostics(),
        "creative_engine": creative.diagnostics(),
        "omni_vision":     vision.diagnostics(),
    }


@app.get("/metrics", tags=["System"], response_class=Response)
async def prometheus_metrics():
    return Response(content=telem.prometheus_metrics(), media_type="text/plain")


# ── NEURO-CORE ────────────────────────────────────────────────────────────────

@app.post("/api/v1/think", response_model=ThinkResponse, tags=["NEURO-CORE"])
async def think(req: ThinkRequest):
    try:
        depth = ReasoningDepth(req.depth)
        thought = await neuro.think(req.prompt, depth=depth, use_cache=req.use_cache)
        return ThinkResponse(
            content=thought.content,
            model=thought.model,
            depth=thought.depth.value,
            tokens_used=thought.tokens_used,
            latency_ms=thought.latency_ms,
            cached=thought.cached,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Internal processing error")


@app.post("/api/v1/think/stream", tags=["NEURO-CORE"])
async def think_stream(req: ThinkRequest):
    """Stream tokens as Server-Sent Events."""
    async def generator():
        async for token in neuro.think_stream(req.prompt):
            yield {"data": token}
    return EventSourceResponse(generator())


@app.post("/api/v1/think/improve", response_model=ThinkResponse, tags=["NEURO-CORE"])
async def think_improve(req: ThinkRequest):
    """Two-pass: generate then self-improve."""
    try:
        first = await neuro.think(req.prompt)
        improved = await neuro.self_improve(first)
        return ThinkResponse(
            content=improved.content,
            model=improved.model,
            depth=improved.depth.value,
            tokens_used=improved.tokens_used,
            latency_ms=improved.latency_ms,
            cached=improved.cached,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Internal processing error")


# ── WebSocket streaming chat ──────────────────────────────────────────────────

@app.websocket("/ws/chat")
async def websocket_chat(ws: WebSocket):
    await ws.accept()
    log.info("ws.chat.connected", client=ws.client)
    try:
        while True:
            prompt = await ws.receive_text()
            async for token in neuro.think_stream(prompt):
                await ws.send_text(token)
            await ws.send_text("[END]")
    except WebSocketDisconnect:
        log.info("ws.chat.disconnected")


# ── ORBITAL-NAV ───────────────────────────────────────────────────────────────

@app.post("/api/v1/nav/route", response_model=RouteResponse, tags=["ORBITAL-NAV"])
async def route(req: RouteRequest):
    origin = Coordinate(lat=req.origin_lat, lon=req.origin_lon)
    dest   = Coordinate(lat=req.dest_lat,   lon=req.dest_lon)
    mode   = TransportMode(req.mode)
    route  = await nav.route(origin, dest, mode=mode, alternatives=req.alternatives)
    s = route.summary()
    return RouteResponse(
        origin=s["origin"],
        destination=s["destination"],
        distance_km=s["distance_km"],
        eta_minutes=s["eta_minutes"],
        mode=s["mode"],
        precision=s["precision"],
        satellite_corrected=s["satellite_corrected"],
        waypoints=s["waypoints"],
        hazards=s["hazards"],
        alternatives=s["alternatives"],
    )


@app.get("/api/v1/nav/position", tags=["ORBITAL-NAV"])
async def get_position():
    pos = await nav.get_position()
    sats = await nav.get_satellite_status()
    return {
        "lat": pos.lat, "lon": pos.lon, "alt_m": pos.alt_m,
        "accuracy_m": pos.accuracy_m, "timestamp": pos.timestamp,
        "satellites": [{"system": s.system, "fix": s.fix_type, "hdop": s.hdop} for s in sats],
    }


@app.post("/api/v1/nav/turn-by-turn", tags=["ORBITAL-NAV"])
async def turn_by_turn(req: RouteRequest, lang: str = "en"):
    """Generate localized turn-by-turn directions. Supports en/he/ar (RTL)."""
    if lang not in ("en", "he", "ar"):
        raise HTTPException(status_code=400, detail="lang must be one of: en, he, ar")
    origin = Coordinate(lat=req.origin_lat, lon=req.origin_lon)
    dest   = Coordinate(lat=req.dest_lat,   lon=req.dest_lon)
    mode   = TransportMode(req.mode)
    route  = await nav.route(origin, dest, mode=mode, alternatives=req.alternatives)
    instructions = nav.build_turn_by_turn(route, lang=lang)
    return {
        "lang": lang,
        "is_rtl": lang in ("he", "ar"),
        "total_distance_m": route.total_distance_m,
        "total_duration_s": route.total_duration_s,
        "instructions": instructions,
    }


@app.post("/api/v1/nav/eta-with-conditions", tags=["ORBITAL-NAV"])
async def eta_with_conditions(
    origin_lat: float, origin_lon: float,
    dest_lat: float, dest_lon: float,
    mode: str = "driving",
    hour: int | None = None, weekday: int = 0,
    weather_factor: float = 1.0,
):
    """Fast ETA with time-of-day traffic prediction + weather adjustment."""
    origin = Coordinate(lat=origin_lat, lon=origin_lon)
    dest   = Coordinate(lat=dest_lat,   lon=dest_lon)
    tmode  = TransportMode(mode)
    est = nav.estimate_eta(origin, dest, mode=tmode)
    traffic_factor = 1.0
    if hour is not None:
        traffic_factor = nav.predict_traffic_factor(hour, weekday)
    adjusted = nav.adjust_eta_for_conditions(
        est["duration_s"], traffic_factor=traffic_factor, weather_factor=weather_factor,
    )
    return {
        **est,
        "traffic_factor": traffic_factor,
        "weather_factor": weather_factor,
        "adjusted_duration_s": round(adjusted, 1),
        "adjusted_eta_minutes": round(adjusted / 60, 1),
    }


@app.post("/api/v1/nav/battery-check", tags=["ORBITAL-NAV"])
async def battery_check(
    req: RouteRequest,
    battery_wh: float,
    wind_factor: float = 1.0,
    reserve_percent: float = 20.0,
):
    """Check whether a planned route is feasible with available battery."""
    origin = Coordinate(lat=req.origin_lat, lon=req.origin_lon)
    dest   = Coordinate(lat=req.dest_lat,   lon=req.dest_lon)
    tmode  = TransportMode(req.mode)
    route_obj = await nav.route(origin, dest, mode=tmode, alternatives=0)
    return nav.is_within_range(
        route_obj, battery_wh_available=battery_wh,
        wind_factor=wind_factor, reserve_percent=reserve_percent,
    )


@app.websocket("/api/v1/nav/ws/position")
async def ws_position(websocket: WebSocket, interval_s: float = 1.0):
    """Live GPS position stream over WebSocket. Closes cleanly on disconnect."""
    interval = max(0.1, min(10.0, interval_s))
    await websocket.accept()
    try:
        while True:
            pos = await nav.get_position()
            await websocket.send_json({
                "lat": pos.lat, "lon": pos.lon, "alt_m": pos.alt_m,
                "accuracy_m": pos.accuracy_m, "timestamp": pos.timestamp,
            })
            await asyncio.sleep(interval)
    except WebSocketDisconnect:
        log.info("ws.position.disconnect")
    except Exception as exc:
        log.warning("ws.position.error", error=str(exc))
        try:
            await websocket.close()
        except Exception:
            pass


# ── SATLINK SOS ───────────────────────────────────────────────────────────────

@app.post("/api/v1/sos", response_model=SOSResponse, tags=["SATLINK-X"])
async def send_sos(req: SOSRequest):
    priority = SOSPriority[req.priority]
    packet = await satlink.send_sos(
        lat=req.lat, lon=req.lon,
        message=req.message,
        priority=priority,
        alt_m=req.alt_m,
        sender_id=req.sender_id,
    )
    return SOSResponse(
        incident_id=packet.incident_id,
        acknowledged=packet.acknowledged,
        channels_used=packet.channels_used,
        responders_notified=packet.responders_notified,
        ack_timestamp=packet.ack_timestamp,
    )


@app.get("/api/v1/sos/passes", tags=["SATLINK-X"])
async def satellite_passes(lat: float = 32.0, lon: float = 34.8, hours: int = 24):
    passes = await satlink.predict_passes(lat, lon, hours)
    return [
        {
            "sat_id": p.sat_id,
            "sat_name": p.sat_name,
            "aos_time": p.aos_time,
            "los_time": p.los_time,
            "max_elevation_deg": p.max_elevation_deg,
            "link_quality": p.link_quality,
        }
        for p in passes
    ]


# ── SONIC-MATRIX ──────────────────────────────────────────────────────────────

@app.post("/api/v1/sonic/detect", tags=["SONIC-MATRIX"])
async def detect_language(req: DetectLanguageRequest):
    return sonic.detect_language(req.text)


@app.post("/api/v1/sonic/translate", tags=["SONIC-MATRIX"])
async def translate(req: TranslateRequest):
    result = sonic.translate(req.text, req.target_lang, req.source_lang)
    return {
        "source_text": result.source_text,
        "translated_text": result.translated_text,
        "source_lang": result.source_lang,
        "target_lang": result.target_lang,
        "confidence": result.confidence,
    }


@app.post("/api/v1/sonic/tts", tags=["SONIC-MATRIX"])
async def tts(req: TTSRequest):
    result = sonic.synthesize(req.text, lang=req.lang)
    if not result.audio_bytes:
        raise HTTPException(status_code=500, detail="TTS synthesis failed")
    return Response(
        content=result.audio_bytes,
        media_type="audio/mpeg",
        headers={"X-Language": result.language, "X-Duration-MS": str(result.duration_ms)},
    )


@app.get("/api/v1/sonic/languages", tags=["SONIC-MATRIX"])
async def supported_languages():
    return {"languages": sonic.supported_languages()}


# ── TELEMETRY-HUB ─────────────────────────────────────────────────────────────

@app.post("/api/v1/telemetry/ingest", response_model=TelemetryIngestResponse, tags=["TELEMETRY-HUB"])
async def ingest_telemetry(req: SensorReadingRequest):
    reading = SensorReading(
        sensor_id=req.sensor_id, value=req.value, unit=req.unit, quality=req.quality
    )
    anomaly = await telem.ingest(reading)
    return TelemetryIngestResponse(
        sensor_id=req.sensor_id,
        anomaly_detected=anomaly is not None,
        anomaly_type=anomaly.anomaly_type.value if anomaly else None,
        anomaly_severity=anomaly.severity if anomaly else None,
    )


@app.get("/api/v1/telemetry/stream/{sensor_id}", tags=["TELEMETRY-HUB"])
async def stream_sensor(sensor_id: str, interval: float = 1.0):
    """Server-Sent Events stream of live sensor readings."""
    async def generator():
        async for reading in telem.stream_sensor(sensor_id, interval_s=interval):
            yield {"data": str(reading)}
    return EventSourceResponse(generator())


@app.get("/api/v1/telemetry/summary", tags=["TELEMETRY-HUB"])
async def telemetry_summary():
    return {"streams": telem.stream_summary()}


# ── CREATIVE-ENGINE ───────────────────────────────────────────────────────────

@app.post("/api/v1/creative/image-prompt", tags=["CREATIVE-ENGINE"])
async def image_prompt(req: ImagePromptRequest):
    from brainiac.core.creative_engine import Style
    style = Style(req.style)
    return creative.generate_image_prompt(req.subject, style, req.width, req.height)


@app.get("/api/v1/creative/badge", tags=["CREATIVE-ENGINE"])
async def generate_badge(text: str, color: str = "#00f5ff"):
    svg = creative.generate_svg_badge(text, color)
    return Response(content=svg, media_type="image/svg+xml")


@app.post("/api/v1/creative/3d-scene", tags=["CREATIVE-ENGINE"])
async def generate_3d(description: str):
    return creative.generate_3d_scene(description)


# ── NEXUS-SYNC ────────────────────────────────────────────────────────────────

@app.post("/api/v1/nexus/devices", tags=["NEXUS-SYNC"])
async def register_device(req: RegisterDeviceRequest):
    from brainiac.core.nexus_sync import DeviceType, Protocol
    try:
        device = nexus.register_device(
            device_id=req.device_id,
            device_type=DeviceType(req.device_type),
            protocol=Protocol(req.protocol),
            endpoint=req.endpoint,
            name=req.name,
            capabilities=req.capabilities,
        )
        await nexus.connect_device(req.device_id)
        return device.to_dict()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid device registration parameters")


@app.get("/api/v1/nexus/devices", tags=["NEXUS-SYNC"])
async def list_devices(connected_only: bool = False):
    return [d.to_dict() for d in nexus.list_devices(connected_only=connected_only)]


@app.post("/api/v1/nexus/publish", tags=["NEXUS-SYNC"])
async def publish_message(req: PublishRequest):
    msg = await nexus.publish(req.device_id, req.topic, req.payload, req.qos)
    return {"msg_id": msg.msg_id, "topic": msg.topic, "timestamp": msg.timestamp}


# ── MEDICAL PROTOCOLS ─────────────────────────────────────────────────────────

@app.get("/api/v1/medical/protocols", tags=["MEDICAL"])
async def list_protocols(category: str | None = None):
    """List available clinical protocols, optionally filtered by category."""
    cat = ProtocolCategory(category) if category else None
    return {"protocols": medical.list_protocols(cat)}


@app.get("/api/v1/medical/protocol/{name}", tags=["MEDICAL"])
async def get_protocol(name: str):
    """Retrieve a specific clinical protocol with steps and drug references."""
    proto = medical.get_protocol(name)
    if not proto:
        raise HTTPException(status_code=404, detail="Protocol not found")
    return {
        "name": proto.name,
        "category": proto.category.value,
        "urgency": proto.urgency.value,
        "reference": proto.reference,
        "steps": [
            {"step": s.step_number, "action": s.action, "critical": s.critical,
             "duration_s": s.duration_s, "notes": s.notes}
            for s in proto.steps
        ],
        "drugs": [
            {"drug": d.drug, "dose_mg_per_kg": d.dose_mg_per_kg,
             "max_mg": d.max_dose_mg, "routes": [r.value for r in d.routes]}
            for d in proto.drugs
        ],
        "contraindications": proto.contraindications,
        "disclaimer": "EDUCATIONAL REFERENCE ONLY — NOT CLINICAL ADVICE",
    }


@app.post("/api/v1/medical/dose", tags=["MEDICAL"])
async def calculate_dose(drug: str, weight_kg: float, route: str | None = None):
    """Calculate weight-based drug dosage with safety clamping."""
    dr = DrugRoute(route) if route else None
    return medical.calculate_dose(drug, weight_kg, route=dr)


@app.post("/api/v1/medical/triage", tags=["MEDICAL"])
async def triage(
    heart_rate: int, respiratory_rate: int, systolic_bp: int, gcs: int,
    spo2: int = 98, temperature_c: float = 37.0,
):
    """Field triage scoring based on vital signs. Returns urgency category and recommended protocol."""
    result = medical.triage(
        heart_rate=heart_rate, respiratory_rate=respiratory_rate,
        systolic_bp=systolic_bp, gcs=gcs, spo2=spo2, temperature_c=temperature_c,
    )
    return {
        "category": result.category.value,
        "score": result.score,
        "rationale": result.rationale,
        "recommended_protocol": result.recommended_protocol,
    }


@app.get("/api/v1/medical/drugs", tags=["MEDICAL"])
async def list_drugs():
    """List all drugs in the reference database."""
    return {"drugs": medical.list_drugs()}


@app.get("/api/v1/medical/drug/{name}", tags=["MEDICAL"])
async def get_drug(name: str):
    """Get detailed drug information."""
    info = medical.get_drug_info(name)
    if not info:
        raise HTTPException(status_code=404, detail="Drug not found")
    return info


# ── CYBER-SHIELD ──────────────────────────────────────────────────────────────

@app.post("/api/v1/security/scan-input", tags=["CYBER-SHIELD"])
async def scan_input(text: str, source_ip: str = "0.0.0.0"):
    threat = shield.scan_input(text, source_ip)
    return {
        "clean": threat is None,
        "threat": {
            "type": threat.threat_type.value,
            "level": threat.threat_level.name,
            "description": threat.description,
        } if threat else None,
    }


@app.post("/api/v1/security/audit-config", tags=["CYBER-SHIELD"])
async def audit_config(config: dict):
    result = shield.audit_config(config)
    return {
        "risk_score": result.risk_score,
        "vulnerabilities": result.vulnerabilities,
        "recommendations": result.hardening_recommendations,
    }


# ── OMNI-VISION ───────────────────────────────────────────────────────────────

def _validate_image_request(request: Request, image_bytes: bytes) -> None:
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Image bytes required in request body")
    if len(image_bytes) > _MAX_VISION_BYTES:
        raise HTTPException(status_code=413, detail=f"Image exceeds {_MAX_VISION_BYTES} byte limit")
    ct = request.headers.get("content-type", "")
    if ct and not ct.startswith("image/") and "octet-stream" not in ct:
        raise HTTPException(status_code=415, detail="Content-Type must be image/* or application/octet-stream")


@app.post("/api/v1/vision/analyze", tags=["OMNI-VISION"])
async def analyze_image(request: Request):
    """Accepts raw image bytes in request body."""
    image_bytes = await request.body()
    _validate_image_request(request, image_bytes)
    analysis = vision.analyze_scene(image_bytes)
    return {
        "description": analysis.description,
        "dominant_colors": analysis.dominant_colors,
        "processing_ms": analysis.processing_ms,
        "objects_detected": len(analysis.objects),
    }


@app.post("/api/v1/vision/info", tags=["OMNI-VISION"])
async def image_info(request: Request):
    image_bytes = await request.body()
    _validate_image_request(request, image_bytes)
    return vision.image_info(image_bytes)


# ── GANE AGENT LAYER ─────────────────────────────────────────────────────────

@app.post("/api/v1/agent/run", tags=["GANE-AGENT"])
async def agent_run(request: Request):
    """
    Dispatch a prompt to the GANE multi-agent system.
    Routes to the best specialist agent (telemetry, medical, navigation).

    Body: {"prompt": "...", "force_agent": "telemetry|medical|navigation"}
    """
    body = await request.json()
    prompt = body.get("prompt", "")
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt is required")
    force_agent = body.get("force_agent")
    result = await _agent_router.run(prompt, force_agent=force_agent)
    return {
        "agent_used": result.agent_used,
        "routing_reason": result.routing_reason,
        "response": result.episode.response,
        "episode_id": result.episode.episode_id,
        "tool_calls": result.episode.tool_calls,
        "tokens_used": result.episode.tokens_used,
        "cost_usd": result.episode.cost_usd,
        "success": result.episode.success,
        "duration_ms": round(result.total_ms, 1),
    }


@app.get("/api/v1/agent/diagnostics", tags=["GANE-AGENT"])
async def agent_diagnostics():
    """Return diagnostics for all GANE agents and shared memory."""
    return _agent_router.diagnostics()


@app.get("/api/v1/agent/memory", tags=["GANE-AGENT"])
async def agent_memory():
    """Return a summary of the agent memory store."""
    return await _agent_router.memory.diagnostics()


@app.post("/api/v1/agent/route-preview", tags=["GANE-AGENT"])
async def agent_route_preview(request: Request):
    """Preview which agent would be selected for a given prompt without executing."""
    body = await request.json()
    prompt = body.get("prompt", "")
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt is required")
    agent_name, reason = AgentRouter.route(prompt)
    return {"agent": agent_name, "reason": reason}
