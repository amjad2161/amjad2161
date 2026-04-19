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
