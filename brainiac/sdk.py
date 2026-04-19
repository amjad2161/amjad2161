"""
BRAINIAC Python SDK Client
===========================
A clean, async-friendly client for talking to a running BRAINIAC API server.

Example
-------
    from brainiac.sdk import BrainiacClient

    async with BrainiacClient("http://localhost:8000") as client:
        health = await client.health()
        route  = await client.route(32.0, 34.0, 33.0, 35.0, mode="drone")
        sos    = await client.sos(32.0, 34.8, "Help!", priority="MAYDAY")
"""
from __future__ import annotations

import asyncio
from typing import Any

import httpx


class BrainiacClient:
    """Async client for the BRAINIAC REST API."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        timeout: float = 30.0,
        api_key: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        headers = {"User-Agent": "brainiac-sdk/1.0.0"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            headers=headers,
        )

    async def __aenter__(self) -> "BrainiacClient":
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    # ── System ────────────────────────────────────────────────────────────────

    async def health(self) -> dict:
        r = await self._client.get("/health")
        r.raise_for_status()
        return r.json()

    async def diagnostics(self) -> dict:
        r = await self._client.get("/diagnostics")
        r.raise_for_status()
        return r.json()

    async def metrics(self) -> str:
        r = await self._client.get("/metrics")
        r.raise_for_status()
        return r.text

    # ── NEURO-CORE ────────────────────────────────────────────────────────────

    async def think(
        self,
        prompt: str,
        depth: str = "standard",
        use_cache: bool = True,
    ) -> dict:
        r = await self._client.post("/api/v1/think", json={
            "prompt": prompt, "depth": depth, "use_cache": use_cache,
        })
        r.raise_for_status()
        return r.json()

    async def think_stream(self, prompt: str, depth: str = "standard"):
        """Async generator yielding tokens as they arrive."""
        async with self._client.stream(
            "POST", "/api/v1/think/stream",
            json={"prompt": prompt, "depth": depth},
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    yield line[5:].strip()

    # ── ORBITAL-NAV ───────────────────────────────────────────────────────────

    async def route(
        self,
        origin_lat: float,
        origin_lon: float,
        dest_lat: float,
        dest_lon: float,
        mode: str = "driving",
        alternatives: int = 3,
    ) -> dict:
        r = await self._client.post("/api/v1/nav/route", json={
            "origin_lat": origin_lat, "origin_lon": origin_lon,
            "dest_lat": dest_lat, "dest_lon": dest_lon,
            "mode": mode, "alternatives": alternatives,
        })
        r.raise_for_status()
        return r.json()

    async def position(self) -> dict:
        r = await self._client.get("/api/v1/nav/position")
        r.raise_for_status()
        return r.json()

    # ── SATLINK SOS ───────────────────────────────────────────────────────────

    async def sos(
        self,
        lat: float,
        lon: float,
        message: str,
        priority: str = "DISTRESS",
        sender_id: str = "sdk-client",
    ) -> dict:
        r = await self._client.post("/api/v1/sos", json={
            "lat": lat, "lon": lon, "message": message,
            "priority": priority, "sender_id": sender_id,
        })
        r.raise_for_status()
        return r.json()

    async def satellite_passes(self, lat: float, lon: float, hours: int = 24) -> list[dict]:
        r = await self._client.get("/api/v1/sos/passes", params={
            "lat": lat, "lon": lon, "hours": hours,
        })
        r.raise_for_status()
        return r.json()

    # ── SONIC-MATRIX ──────────────────────────────────────────────────────────

    async def detect_language(self, text: str) -> dict:
        r = await self._client.post("/api/v1/sonic/detect", json={"text": text})
        r.raise_for_status()
        return r.json()

    async def translate(self, text: str, target_lang: str, source_lang: str = "auto") -> dict:
        r = await self._client.post("/api/v1/sonic/translate", json={
            "text": text, "target_lang": target_lang, "source_lang": source_lang,
        })
        r.raise_for_status()
        return r.json()

    async def tts(self, text: str, lang: str | None = None) -> bytes:
        r = await self._client.post("/api/v1/sonic/tts", json={
            "text": text, "lang": lang,
        })
        r.raise_for_status()
        return r.content

    # ── TELEMETRY ─────────────────────────────────────────────────────────────

    async def ingest(self, sensor_id: str, value: float, unit: str = "") -> dict:
        r = await self._client.post("/api/v1/telemetry/ingest", json={
            "sensor_id": sensor_id, "value": value, "unit": unit,
        })
        r.raise_for_status()
        return r.json()

    async def telemetry_summary(self) -> dict:
        r = await self._client.get("/api/v1/telemetry/summary")
        r.raise_for_status()
        return r.json()

    # ── NEXUS-SYNC ────────────────────────────────────────────────────────────

    async def register_device(
        self,
        device_id: str,
        device_type: str,
        protocol: str,
        endpoint: str,
        name: str = "",
        capabilities: list[str] | None = None,
    ) -> dict:
        r = await self._client.post("/api/v1/nexus/devices", json={
            "device_id": device_id, "device_type": device_type,
            "protocol": protocol, "endpoint": endpoint,
            "name": name, "capabilities": capabilities or [],
        })
        r.raise_for_status()
        return r.json()

    async def list_devices(self, connected_only: bool = False) -> list[dict]:
        r = await self._client.get("/api/v1/nexus/devices", params={
            "connected_only": connected_only,
        })
        r.raise_for_status()
        return r.json()

    async def publish(self, device_id: str, topic: str, payload: dict) -> dict:
        r = await self._client.post("/api/v1/nexus/publish", json={
            "device_id": device_id, "topic": topic, "payload": payload,
        })
        r.raise_for_status()
        return r.json()

    # ── SECURITY ──────────────────────────────────────────────────────────────

    async def scan_input(self, text: str, source_ip: str = "0.0.0.0") -> dict:
        r = await self._client.post(
            "/api/v1/security/scan-input",
            params={"text": text, "source_ip": source_ip},
        )
        r.raise_for_status()
        return r.json()

    async def audit_config(self, config: dict) -> dict:
        r = await self._client.post("/api/v1/security/audit-config", json=config)
        r.raise_for_status()
        return r.json()

    # ── CREATIVE ──────────────────────────────────────────────────────────────

    async def image_prompt(
        self,
        subject: str,
        style: str = "photorealistic",
        width: int = 1024,
        height: int = 1024,
    ) -> dict:
        r = await self._client.post("/api/v1/creative/image-prompt", json={
            "subject": subject, "style": style, "width": width, "height": height,
        })
        r.raise_for_status()
        return r.json()

    async def badge(self, text: str, color: str = "#00f5ff") -> str:
        r = await self._client.get("/api/v1/creative/badge", params={
            "text": text, "color": color,
        })
        r.raise_for_status()
        return r.text

    # ── Navigation Enhancements ──────────────────────────────────────────────

    async def turn_by_turn(
        self,
        origin_lat: float, origin_lon: float,
        dest_lat: float, dest_lon: float,
        mode: str = "driving", lang: str = "en",
    ) -> dict:
        r = await self._client.post(
            "/api/v1/nav/turn-by-turn",
            params={"lang": lang},
            json={
                "origin_lat": origin_lat, "origin_lon": origin_lon,
                "dest_lat": dest_lat, "dest_lon": dest_lon,
                "mode": mode, "alternatives": 1,
            },
        )
        r.raise_for_status()
        return r.json()

    async def eta_with_conditions(
        self,
        origin_lat: float, origin_lon: float,
        dest_lat: float, dest_lon: float,
        mode: str = "driving",
        hour: int | None = None, weekday: int = 0,
        weather_factor: float = 1.0,
    ) -> dict:
        params = {
            "origin_lat": origin_lat, "origin_lon": origin_lon,
            "dest_lat": dest_lat, "dest_lon": dest_lon,
            "mode": mode, "weekday": weekday, "weather_factor": weather_factor,
        }
        if hour is not None:
            params["hour"] = hour
        r = await self._client.post("/api/v1/nav/eta-with-conditions", params=params)
        r.raise_for_status()
        return r.json()

    async def battery_check(
        self,
        origin_lat: float, origin_lon: float,
        dest_lat: float, dest_lon: float,
        battery_wh: float,
        mode: str = "drone",
        wind_factor: float = 1.0,
        reserve_percent: float = 20.0,
    ) -> dict:
        r = await self._client.post(
            "/api/v1/nav/battery-check",
            params={"battery_wh": battery_wh, "wind_factor": wind_factor,
                    "reserve_percent": reserve_percent},
            json={
                "origin_lat": origin_lat, "origin_lon": origin_lon,
                "dest_lat": dest_lat, "dest_lon": dest_lon,
                "mode": mode, "alternatives": 0,
            },
        )
        r.raise_for_status()
        return r.json()

    # ── Medical ──────────────────────────────────────────────────────────────

    async def medical_protocols(self, category: str | None = None) -> dict:
        params = {"category": category} if category else {}
        r = await self._client.get("/api/v1/medical/protocols", params=params)
        r.raise_for_status()
        return r.json()

    async def medical_protocol(self, name: str) -> dict:
        r = await self._client.get(f"/api/v1/medical/protocol/{name}")
        r.raise_for_status()
        return r.json()

    async def medical_dose(self, drug: str, weight_kg: float, route: str | None = None) -> dict:
        params = {"drug": drug, "weight_kg": weight_kg}
        if route:
            params["route"] = route
        r = await self._client.post("/api/v1/medical/dose", params=params)
        r.raise_for_status()
        return r.json()

    async def medical_triage(
        self, heart_rate: int, respiratory_rate: int, systolic_bp: int, gcs: int,
        spo2: int = 98, temperature_c: float = 37.0,
    ) -> dict:
        r = await self._client.post(
            "/api/v1/medical/triage",
            params={
                "heart_rate": heart_rate, "respiratory_rate": respiratory_rate,
                "systolic_bp": systolic_bp, "gcs": gcs,
                "spo2": spo2, "temperature_c": temperature_c,
            },
        )
        r.raise_for_status()
        return r.json()

    async def medical_drugs(self) -> dict:
        r = await self._client.get("/api/v1/medical/drugs")
        r.raise_for_status()
        return r.json()

    async def medical_drug(self, name: str) -> dict:
        r = await self._client.get(f"/api/v1/medical/drug/{name}")
        r.raise_for_status()
        return r.json()

    # ── INS (Inertial Navigation) ──────────────────────────────────────────

    async def ins_position(self) -> dict:
        r = await self._client.get("/api/v1/ins/position")
        r.raise_for_status()
        return r.json()

    async def ins_health(self) -> dict:
        r = await self._client.get("/api/v1/ins/health")
        r.raise_for_status()
        return r.json()

    async def corridor_check(
        self, route_coords: list[list[float]], threshold_m: float = 50.0,
    ) -> dict:
        r = await self._client.post(
            "/api/v1/ins/corridor-check",
            params={"threshold_m": threshold_m},
            json={"route_coords": route_coords},
        )
        r.raise_for_status()
        return r.json()

    # ── GPS Spoofing Detection ──────────────────────────────────────────────

    async def detect_gps_spoofing(
        self, reported_lat: float, reported_lon: float, hdop: float = 1.0,
        previous_lat: float | None = None, previous_lon: float | None = None,
        previous_ts: float | None = None, current_ts: float | None = None,
    ) -> dict:
        params: dict = {
            "reported_lat": reported_lat, "reported_lon": reported_lon,
            "hdop": hdop,
        }
        if previous_lat is not None:
            params["previous_lat"] = previous_lat
        if previous_lon is not None:
            params["previous_lon"] = previous_lon
        if previous_ts is not None:
            params["previous_ts"] = previous_ts
        if current_ts is not None:
            params["current_ts"] = current_ts
        r = await self._client.post("/api/v1/security/detect-gps-spoofing", params=params)
        r.raise_for_status()
        return r.json()

    # ── Mesh Networking & V2X ────────────────────────────────────────────────

    async def mesh_broadcast(
        self, payload: dict, protocol: str = "LoRaWAN", ttl: int = 3,
    ) -> dict:
        r = await self._client.post("/api/v1/nexus/mesh/broadcast", json={
            "payload": payload, "protocol": protocol, "ttl": ttl,
        })
        r.raise_for_status()
        return r.json()

    async def mesh_topology(self) -> dict:
        r = await self._client.get("/api/v1/nexus/mesh/topology")
        r.raise_for_status()
        return r.json()

    async def v2x_signal(self, signal_type: str, data: dict, source_id: str = "gane") -> dict:
        r = await self._client.post("/api/v1/nexus/v2x/signal", json={
            "signal_type": signal_type, "data": data, "source_id": source_id,
        })
        r.raise_for_status()
        return r.json()

    async def v2x_traffic_light(
        self, intersection_id: str, priority: str = "normal", reason: str = "",
    ) -> dict:
        r = await self._client.post("/api/v1/nexus/v2x/traffic-light", json={
            "intersection_id": intersection_id, "priority": priority, "reason": reason,
        })
        r.raise_for_status()
        return r.json()

    # ── Life Corridors ───────────────────────────────────────────────────────

    async def life_corridor(
        self,
        origin_lat: float, origin_lon: float,
        dest_lat: float, dest_lon: float,
        priority: str = "emergency", mode: str = "driving",
    ) -> dict:
        r = await self._client.post("/api/v1/nav/life-corridor", params={
            "origin_lat": origin_lat, "origin_lon": origin_lon,
            "dest_lat": dest_lat, "dest_lon": dest_lon,
            "priority": priority, "mode": mode,
        })
        r.raise_for_status()
        return r.json()

    # ── SLAM / LiDAR ─────────────────────────────────────────────────────────

    async def lidar_scan(self, points: list, intensity: list | None = None) -> dict:
        body = {"points": points}
        if intensity is not None:
            body["intensity"] = intensity
        r = await self._client.post("/api/v1/vision/lidar-scan", json=body)
        r.raise_for_status()
        return r.json()

    async def slam_update(
        self, points: list, imu_heading_deg: float = 0.0,
        odometry_dx: float = 0.0, odometry_dy: float = 0.0,
    ) -> dict:
        r = await self._client.post("/api/v1/vision/slam-update", json={
            "points": points, "imu_heading_deg": imu_heading_deg,
            "odometry_dx": odometry_dx, "odometry_dy": odometry_dy,
        })
        r.raise_for_status()
        return r.json()

    async def obstacles_3d(
        self, points: list, min_height_m: float = 0.3, max_range_m: float = 50.0,
    ) -> dict:
        r = await self._client.post("/api/v1/vision/obstacles-3d", json={
            "points": points, "min_height_m": min_height_m, "max_range_m": max_range_m,
        })
        r.raise_for_status()
        return r.json()

    # ── Hardware Attack / Federated Privacy ─────────────────────────────────

    async def detect_hardware_attack(
        self, sensor_readings: dict, rf_spectrum: list | None = None,
    ) -> dict:
        body = {"sensor_readings": sensor_readings}
        if rf_spectrum is not None:
            body["rf_spectrum"] = rf_spectrum
        r = await self._client.post("/api/v1/security/detect-hardware-attack", json=body)
        r.raise_for_status()
        return r.json()

    async def privacy_audit(self, data: dict) -> dict:
        r = await self._client.post("/api/v1/security/privacy-audit", json={"data": data})
        r.raise_for_status()
        return r.json()

    async def enforce_data_locality(
        self, data: dict, allowed_fields: list | None = None,
    ) -> dict:
        body = {"data": data}
        if allowed_fields is not None:
            body["allowed_fields"] = allowed_fields
        r = await self._client.post("/api/v1/security/enforce-data-locality", json=body)
        r.raise_for_status()
        return r.json()

    # ── Community Hazards (Waze DNA) ──────────────────────────────────────

    async def report_hazard(
        self, lat: float, lon: float, hazard_type: str,
        description: str = "", severity: int = 5,
    ) -> dict:
        r = await self._client.post("/api/v1/nav/hazards", json={
            "lat": lat, "lon": lon, "type": hazard_type,
            "description": description, "severity": severity,
        })
        r.raise_for_status()
        return r.json()

    async def get_hazards(
        self, lat: float | None = None, lon: float | None = None,
        radius_m: float = 5000.0,
    ) -> dict:
        params: dict = {"radius_m": radius_m}
        if lat is not None:
            params["lat"] = lat
        if lon is not None:
            params["lon"] = lon
        r = await self._client.get("/api/v1/nav/hazards", params=params)
        r.raise_for_status()
        return r.json()

    async def upvote_hazard(self, hazard_id: str) -> dict:
        r = await self._client.post(f"/api/v1/nav/hazards/{hazard_id}/upvote")
        r.raise_for_status()
        return r.json()

    async def dismiss_hazard(self, hazard_id: str) -> dict:
        r = await self._client.delete(f"/api/v1/nav/hazards/{hazard_id}")
        r.raise_for_status()
        return r.json()

    # ── POI Database (Google Maps DNA) ──────────────────────────────────────

    async def add_poi(
        self, lat: float, lon: float, name: str, category: str,
        rating: float = 0.0,
    ) -> dict:
        r = await self._client.post("/api/v1/nav/pois", json={
            "lat": lat, "lon": lon, "name": name,
            "category": category, "rating": rating,
        })
        r.raise_for_status()
        return r.json()

    async def search_pois(
        self, query: str = "", category: str | None = None,
        lat: float | None = None, lon: float | None = None,
        radius_m: float = 5000.0, limit: int = 20,
    ) -> dict:
        params: dict = {"query": query, "radius_m": radius_m, "limit": limit}
        if category:
            params["category"] = category
        if lat is not None:
            params["lat"] = lat
        if lon is not None:
            params["lon"] = lon
        r = await self._client.get("/api/v1/nav/pois", params=params)
        r.raise_for_status()
        return r.json()

    async def nearest_poi(self, lat: float, lon: float, category: str) -> dict:
        r = await self._client.get("/api/v1/nav/pois/nearest", params={
            "lat": lat, "lon": lon, "category": category,
        })
        r.raise_for_status()
        return r.json()

    async def poi_categories(self) -> dict:
        r = await self._client.get("/api/v1/nav/pois/categories")
        r.raise_for_status()
        return r.json()

    # ── Predictive Routing ──────────────────────────────────────────────────

    async def predict_route_intent(
        self, current_lat: float, current_lon: float,
        heading_deg: float = 0.0, speed_ms: float = 0.0,
        time_of_day: int = 12, weekday: int = 0,
        history: list | None = None,
    ) -> dict:
        body: dict = {
            "current_lat": current_lat, "current_lon": current_lon,
            "heading_deg": heading_deg, "speed_ms": speed_ms,
            "time_of_day": time_of_day, "weekday": weekday,
        }
        if history:
            body["history"] = history
        r = await self._client.post("/api/v1/nav/predict-intent", json=body)
        r.raise_for_status()
        return r.json()

    # ── Agent ────────────────────────────────────────────────────────────────

    async def agent_run(self, prompt: str, force_agent: str | None = None) -> dict:
        body = {"prompt": prompt}
        if force_agent:
            body["force_agent"] = force_agent
        r = await self._client.post("/api/v1/agent/run", json=body)
        r.raise_for_status()
        return r.json()

    async def agent_route_preview(self, prompt: str) -> dict:
        r = await self._client.post("/api/v1/agent/route-preview", json={"prompt": prompt})
        r.raise_for_status()
        return r.json()


# ── Convenience sync wrapper ──────────────────────────────────────────────────

class BrainiacSync:
    """Blocking wrapper around BrainiacClient for simple scripts."""

    def __init__(self, base_url: str = "http://localhost:8000", **kwargs) -> None:
        self._client = BrainiacClient(base_url, **kwargs)
        self._loop = asyncio.new_event_loop()

    def __enter__(self) -> "BrainiacSync":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _run(self, coro):
        return self._loop.run_until_complete(coro)

    def health(self) -> dict:
        return self._run(self._client.health())

    def think(self, prompt: str, depth: str = "standard") -> dict:
        return self._run(self._client.think(prompt, depth))

    def route(self, olat: float, olon: float, dlat: float, dlon: float, mode: str = "driving") -> dict:
        return self._run(self._client.route(olat, olon, dlat, dlon, mode=mode))

    def sos(self, lat: float, lon: float, message: str, priority: str = "DISTRESS") -> dict:
        return self._run(self._client.sos(lat, lon, message, priority))

    def close(self) -> None:
        self._run(self._client.close())
        self._loop.close()

    def __del__(self) -> None:
        try:
            if not self._loop.is_closed():
                self._run(self._client.close())
                self._loop.close()
        except Exception:
            pass
