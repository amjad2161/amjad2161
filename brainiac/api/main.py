"""
BRAINIAC API — FastAPI Application Entry Point.
"""

from __future__ import annotations

import asyncio
import os
import signal
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sse_starlette.sse import EventSourceResponse
from structlog.contextvars import bind_contextvars, clear_contextvars

from brainiac.api.auth import is_admin, parse_keys, require_api_key
from brainiac.api.models import (
    DetectLanguageRequest,
    HealthResponse,
    ImagePromptRequest,
    PublishRequest,
    RegisterDeviceRequest,
    RouteRequest,
    RouteResponse,
    SensorReadingRequest,
    SOSRequest,
    SOSResponse,
    TelemetryIngestResponse,
    ThinkRequest,
    ThinkResponse,
    TranslateRequest,
    TTSRequest,
)
from brainiac.core import (
    CreativeEngine,
    CyberShield,
    NeuroCore,
    NexusSync,
    OmniVision,
    OrbitalNav,
    SatLink,
    SonicMatrix,
    TelemetryHub,
)
from brainiac.core.neuro_core import CostLimitExceededError, ReasoningDepth
from brainiac.core.orbital_nav import Coordinate, TransportMode
from brainiac.core.satlink import SOSPriority
from brainiac.core.telemetry_hub import SensorReading
from brainiac.watchdog import Watchdog

log = structlog.get_logger("brainiac.api")
_BOOT_TIME = time.time()
_MAX_REQUEST_BODY_BYTES = 10 * 1024 * 1024
_PROTECTED_PREFIXES = ("/api/v1/system/", "/api/v1/security/")
_ADMIN_ONLY_PATHS = {"/api/v1/system/shutdown-test", "/api/v1/security/audit-config"}
_DEFAULT_SECRETS = {"", "default", "changeme", "CHANGE-IN-PRODUCTION", "BRAINIAC-DEFAULT-CHANGE-ME"}


def _build_modules() -> dict[str, Any]:
    return {
        "neuro": NeuroCore(api_key=os.getenv("ANTHROPIC_API_KEY")),
        "nav": OrbitalNav(),
        "sonic": SonicMatrix(),
        "satlink": SatLink(),
        "nexus": NexusSync(),
        "telem": TelemetryHub(),
        "shield": CyberShield(secret_key=os.getenv("BRAINIAC_SECRET", "CHANGE-IN-PRODUCTION")),
        "creative": CreativeEngine(),
        "vision": OmniVision(),
    }


def _module_factories() -> dict[str, Any]:
    return {
        "neuro": lambda: NeuroCore(api_key=os.getenv("ANTHROPIC_API_KEY")),
        "nav": OrbitalNav,
        "sonic": SonicMatrix,
        "satlink": SatLink,
        "nexus": NexusSync,
        "telem": TelemetryHub,
        "shield": lambda: CyberShield(
            secret_key=os.getenv("BRAINIAC_SECRET", "CHANGE-IN-PRODUCTION"),
        ),
        "creative": CreativeEngine,
        "vision": OmniVision,
    }


def _module_health() -> dict[str, str]:
    return {
        "neuro_core": "ONLINE",
        "orbital_nav": "ONLINE",
        "satlink": "ONLINE",
        "sonic_matrix": "ONLINE",
        "nexus_sync": "ONLINE",
        "telemetry_hub": "ONLINE",
        "cyber_shield": "ONLINE",
        "creative_engine": "ONLINE",
        "omni_vision": "ONLINE",
    }


def _watchdog_health_map() -> dict[str, str]:
    return {
        "neuro": "neuro_core",
        "nav": "orbital_nav",
        "satlink": "satlink",
        "sonic": "sonic_matrix",
        "nexus": "nexus_sync",
        "telem": "telemetry_hub",
        "shield": "cyber_shield",
        "creative": "creative_engine",
        "vision": "omni_vision",
    }


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    secret = os.getenv("BRAINIAC_SECRET", "CHANGE-IN-PRODUCTION")
    if secret in _DEFAULT_SECRETS:
        log.warning("brainiac.security.default_secret")

    api_keys = parse_keys(os.getenv("BRAINIAC_API_KEYS"))
    admin_keys = parse_keys(os.getenv("BRAINIAC_ADMIN_API_KEYS"))
    if not api_keys and not admin_keys:
        log.warning("brainiac.security.api_keys_missing")

    app.state.modules = _build_modules()
    app.state.module_health = _module_health()
    app.state.active_stream_tasks = set()
    app.state.shutdown_event = asyncio.Event()
    app.state.watchdog = Watchdog(
        modules=app.state.modules,
        factories=_module_factories(),
        module_health=app.state.module_health,
        health_key_map=_watchdog_health_map(),
    )

    loop = asyncio.get_running_loop()
    registered_signals: list[signal.Signals] = []

    def _signal_handler(sig_num: int) -> None:
        log.warning("brainiac.signal", signal=sig_num)
        app.state.shutdown_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler, sig)
            registered_signals.append(sig)
        except (NotImplementedError, RuntimeError, ValueError):
            pass

    log.info("brainiac.startup")
    satlink: SatLink = app.state.modules["satlink"]
    await satlink.connect()
    await app.state.watchdog.start()

    try:
        yield
    finally:
        log.info("brainiac.shutdown")
        app.state.shutdown_event.set()

        tasks = list(app.state.active_stream_tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        await app.state.watchdog.stop()

        neuro: NeuroCore = app.state.modules["neuro"]
        await neuro.close()

        for sig in registered_signals:
            loop.remove_signal_handler(sig)


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


def _validate_request_size(content_length: str | None, body_len: int | None = None) -> None:
    if content_length:
        try:
            if int(content_length) > _MAX_REQUEST_BODY_BYTES:
                raise HTTPException(status_code=413, detail="Request body too large")
        except ValueError:
            pass
    if body_len is not None and body_len > _MAX_REQUEST_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Request body too large")


def _modules() -> dict[str, Any]:
    return app.state.modules


def _shield() -> CyberShield:
    return _modules()["shield"]


def _is_protected_endpoint(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in _PROTECTED_PREFIXES)


def _is_admin_endpoint(path: str) -> bool:
    return path in _ADMIN_ONLY_PATHS


async def _track_stream_task_start() -> asyncio.Task[Any] | None:
    task = asyncio.current_task()
    if task is not None:
        app.state.active_stream_tasks.add(task)
    return task


def _track_stream_task_end(task: asyncio.Task[Any] | None) -> None:
    if task is not None:
        app.state.active_stream_tasks.discard(task)


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
    client_ip = request.client.host if request.client else "0.0.0.0"
    request_path = request.url.path
    shield = _shield()
    protected = _is_protected_endpoint(request_path)

    clear_contextvars()
    bind_contextvars(request_id=request_id)
    log.info("http.request", method=request.method, path=request_path)

    if protected:
        try:
            require_api_key(request, admin=_is_admin_endpoint(request_path))
        except HTTPException as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
                headers={"X-Request-Id": request_id},
            )

    rate_limit_key = request.headers.get("X-API-Key") if protected else None
    rate_limit_identity = rate_limit_key or client_ip
    if not shield.check_rate_limit(rate_limit_identity):
        return JSONResponse(
            status_code=429,
            content={"error": "Rate limit exceeded"},
            headers={"X-Request-Id": request_id},
        )

    if request.method in ("POST", "PUT", "PATCH"):
        try:
            _validate_request_size(request.headers.get("content-length"))
            body_bytes = await request.body()
            _validate_request_size(None, len(body_bytes))
            body_str = body_bytes.decode("utf-8", errors="ignore")
            threat = shield.scan_input(body_str, source_ip=client_ip)
            if threat and threat.threat_level.value >= 3:
                return JSONResponse(
                    status_code=400,
                    content={"error": "Malicious input detected"},
                    headers={"X-Request-Id": request_id},
                )

            async def receive() -> dict[str, Any]:
                return {"type": "http.request", "body": body_bytes, "more_body": False}

            request = Request(request.scope, receive)
        except HTTPException as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
                headers={"X-Request-Id": request_id},
            )
        except Exception:
            pass

    response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    response.headers["X-BRAINIAC-Node"] = "GENESIS-1"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    log.info(
        "http.response", method=request.method, path=request.url.path, status=response.status_code
    )
    return response


@app.get("/", tags=["System"])
async def root():
    return {"system": "BRAINIAC AI", "status": "ONLINE", "version": "1.0.0"}


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health():
    return HealthResponse(
        status="ONLINE",
        version="1.0.0",
        modules=dict(app.state.module_health),
        uptime_s=round(time.time() - _BOOT_TIME, 1),
    )


@app.get("/diagnostics", tags=["System"])
async def diagnostics():
    modules = _modules()
    return {
        "neuro_core": modules["neuro"].diagnostics(),
        "orbital_nav": modules["nav"].diagnostics(),
        "satlink": modules["satlink"].diagnostics(),
        "sonic_matrix": modules["sonic"].diagnostics(),
        "nexus_sync": modules["nexus"].diagnostics(),
        "telemetry_hub": modules["telem"].diagnostics(),
        "cyber_shield": modules["shield"].diagnostics(),
        "creative_engine": modules["creative"].diagnostics(),
        "omni_vision": modules["vision"].diagnostics(),
    }


@app.get("/metrics", tags=["System"], response_class=Response)
async def prometheus_metrics():
    return Response(content=_modules()["telem"].prometheus_metrics(), media_type="text/plain")


@app.get("/api/v1/system/cost-stats", tags=["System"])
async def cost_stats():
    return _modules()["neuro"].cost_stats()


@app.get("/api/v1/system/watchdog", tags=["System"])
async def watchdog_status():
    return app.state.watchdog.diagnostics()


@app.post("/api/v1/system/shutdown-test", tags=["System"])
async def shutdown_test(request: Request):
    require_api_key(request, admin=True)
    app.state.shutdown_event.set()
    return {
        "marker": "shutdown_test_triggered",
        "request_id": request.headers.get("X-Request-Id"),
        "admin": is_admin(request),
    }


@app.post("/api/v1/think", response_model=ThinkResponse, tags=["NEURO-CORE"])
async def think(req: ThinkRequest):
    neuro: NeuroCore = _modules()["neuro"]
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
    except CostLimitExceededError as exc:
        return JSONResponse(
            status_code=429, content={"error": "cost_limit_exceeded", "stats": exc.stats}
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/v1/think/stream", tags=["NEURO-CORE"])
async def think_stream(req: ThinkRequest):
    neuro: NeuroCore = _modules()["neuro"]

    async def generator() -> AsyncIterator[dict[str, str]]:
        task = await _track_stream_task_start()
        try:
            async for token in neuro.think_stream(req.prompt):
                yield {"data": token}
        finally:
            _track_stream_task_end(task)

    return EventSourceResponse(generator())


@app.post("/api/v1/think/improve", response_model=ThinkResponse, tags=["NEURO-CORE"])
async def think_improve(req: ThinkRequest):
    neuro: NeuroCore = _modules()["neuro"]
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
    except CostLimitExceededError as exc:
        return JSONResponse(
            status_code=429, content={"error": "cost_limit_exceeded", "stats": exc.stats}
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.websocket("/ws/chat")
async def websocket_chat(ws: WebSocket):
    neuro: NeuroCore = _modules()["neuro"]
    await ws.accept()
    task = asyncio.current_task()
    if task is not None:
        app.state.active_stream_tasks.add(task)
    log.info("ws.chat.connected", client=ws.client)
    try:
        while True:
            prompt = await ws.receive_text()
            async for token in neuro.think_stream(prompt):
                await ws.send_text(token)
            await ws.send_text("[END]")
    except WebSocketDisconnect:
        log.info("ws.chat.disconnected")
    finally:
        if task is not None:
            app.state.active_stream_tasks.discard(task)


@app.post("/api/v1/nav/route", response_model=RouteResponse, tags=["ORBITAL-NAV"])
async def route(req: RouteRequest):
    nav: OrbitalNav = _modules()["nav"]
    origin = Coordinate(lat=req.origin_lat, lon=req.origin_lon)
    dest = Coordinate(lat=req.dest_lat, lon=req.dest_lon)
    mode = TransportMode(req.mode)
    nav_route = await nav.route(origin, dest, mode=mode, alternatives=req.alternatives)
    s = nav_route.summary()
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
    nav: OrbitalNav = _modules()["nav"]
    pos = await nav.get_position()
    sats = await nav.get_satellite_status()
    return {
        "lat": pos.lat,
        "lon": pos.lon,
        "alt_m": pos.alt_m,
        "accuracy_m": pos.accuracy_m,
        "timestamp": pos.timestamp,
        "satellites": [{"system": s.system, "fix": s.fix_type, "hdop": s.hdop} for s in sats],
    }


@app.get("/api/v1/nav/cache-stats", tags=["ORBITAL-NAV"])
async def nav_cache_stats():
    nav: OrbitalNav = _modules()["nav"]
    return nav.get_cache_stats()


@app.post("/api/v1/sos", response_model=SOSResponse, tags=["SATLINK-X"])
async def send_sos(req: SOSRequest):
    satlink: SatLink = _modules()["satlink"]
    priority = SOSPriority[req.priority]
    packet = await satlink.send_sos(
        lat=req.lat,
        lon=req.lon,
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
    satlink: SatLink = _modules()["satlink"]
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


@app.post("/api/v1/sonic/detect", tags=["SONIC-MATRIX"])
async def detect_language(req: DetectLanguageRequest):
    return _modules()["sonic"].detect_language(req.text)


@app.post("/api/v1/sonic/translate", tags=["SONIC-MATRIX"])
async def translate(req: TranslateRequest):
    sonic: SonicMatrix = _modules()["sonic"]
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
    sonic: SonicMatrix = _modules()["sonic"]
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
    return {"languages": _modules()["sonic"].supported_languages()}


@app.post(
    "/api/v1/telemetry/ingest",
    response_model=TelemetryIngestResponse,
    tags=["TELEMETRY-HUB"],
)
async def ingest_telemetry(req: SensorReadingRequest):
    telem: TelemetryHub = _modules()["telem"]
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
    telem: TelemetryHub = _modules()["telem"]

    async def generator() -> AsyncIterator[dict[str, str]]:
        task = await _track_stream_task_start()
        try:
            async for reading in telem.stream_sensor(sensor_id, interval_s=interval):
                yield {"data": str(reading)}
        finally:
            _track_stream_task_end(task)

    return EventSourceResponse(generator())


@app.get("/api/v1/telemetry/summary", tags=["TELEMETRY-HUB"])
async def telemetry_summary():
    return {"streams": _modules()["telem"].stream_summary()}


@app.post("/api/v1/creative/image-prompt", tags=["CREATIVE-ENGINE"])
async def image_prompt(req: ImagePromptRequest):
    from brainiac.core.creative_engine import Style

    creative: CreativeEngine = _modules()["creative"]
    style = Style(req.style)
    return creative.generate_image_prompt(req.subject, style, req.width, req.height)


@app.get("/api/v1/creative/badge", tags=["CREATIVE-ENGINE"])
async def generate_badge(text: str, color: str = "#00f5ff"):
    creative: CreativeEngine = _modules()["creative"]
    svg = creative.generate_svg_badge(text, color)
    return Response(content=svg, media_type="image/svg+xml")


@app.post("/api/v1/creative/3d-scene", tags=["CREATIVE-ENGINE"])
async def generate_3d(description: str):
    creative: CreativeEngine = _modules()["creative"]
    return creative.generate_3d_scene(description)


@app.post("/api/v1/nexus/devices", tags=["NEXUS-SYNC"])
async def register_device(req: RegisterDeviceRequest):
    from brainiac.core.nexus_sync import DeviceType, Protocol

    nexus: NexusSync = _modules()["nexus"]
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
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/v1/nexus/devices", tags=["NEXUS-SYNC"])
async def list_devices(connected_only: bool = False):
    nexus: NexusSync = _modules()["nexus"]
    return [d.to_dict() for d in nexus.list_devices(connected_only=connected_only)]


@app.post("/api/v1/nexus/publish", tags=["NEXUS-SYNC"])
async def publish_message(req: PublishRequest):
    nexus: NexusSync = _modules()["nexus"]
    msg = await nexus.publish(req.device_id, req.topic, req.payload, req.qos)
    return {"msg_id": msg.msg_id, "topic": msg.topic, "timestamp": msg.timestamp}


@app.post("/api/v1/security/scan-input", tags=["CYBER-SHIELD"])
async def scan_input(text: str, source_ip: str = "0.0.0.0"):
    shield = _shield()
    threat = shield.scan_input(text, source_ip)
    return {
        "clean": threat is None,
        "threat": {
            "type": threat.threat_type.value,
            "level": threat.threat_level.name,
            "description": threat.description,
        }
        if threat
        else None,
    }


@app.post("/api/v1/security/audit-config", tags=["CYBER-SHIELD"])
async def audit_config(config: dict):
    shield = _shield()
    result = shield.audit_config(config)
    return {
        "risk_score": result.risk_score,
        "vulnerabilities": result.vulnerabilities,
        "recommendations": result.hardening_recommendations,
    }


@app.post("/api/v1/vision/analyze", tags=["OMNI-VISION"])
async def analyze_image(request: Request):
    vision: OmniVision = _modules()["vision"]
    _validate_request_size(request.headers.get("content-length"))
    image_bytes = await request.body()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Image bytes required in request body")
    _validate_request_size(None, len(image_bytes))
    analysis = vision.analyze_scene(image_bytes)
    return {
        "description": analysis.description,
        "dominant_colors": analysis.dominant_colors,
        "processing_ms": analysis.processing_ms,
        "objects_detected": len(analysis.objects),
    }


@app.post("/api/v1/vision/info", tags=["OMNI-VISION"])
async def image_info(request: Request):
    vision: OmniVision = _modules()["vision"]
    _validate_request_size(request.headers.get("content-length"))
    image_bytes = await request.body()
    _validate_request_size(None, len(image_bytes))
    return vision.image_info(image_bytes)
