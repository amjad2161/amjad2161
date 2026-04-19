"""Integration tests for BRAINIAC REST API."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def client():
    """Create test client with mocked AI calls."""
    with patch("brainiac.core.neuro_core.anthropic.AsyncAnthropic"):
        from brainiac.api.main import app
        return TestClient(app, raise_server_exceptions=False)


# ── System ────────────────────────────────────────────────────────────────────

def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    data = r.json()
    assert data["system"] == "BRAINIAC AI"
    assert data["status"] == "ONLINE"


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ONLINE"
    assert len(data["modules"]) == 9
    for mod_status in data["modules"].values():
        assert mod_status == "ONLINE"
    assert data["uptime_s"] >= 0


def test_diagnostics(client):
    r = client.get("/diagnostics")
    assert r.status_code == 200
    data = r.json()
    expected_modules = [
        "neuro_core", "orbital_nav", "satlink", "sonic_matrix",
        "nexus_sync", "telemetry_hub", "cyber_shield", "creative_engine", "omni_vision",
    ]
    for mod in expected_modules:
        assert mod in data


def test_metrics(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "brainiac_telemetry" in r.text


# ── Navigation ────────────────────────────────────────────────────────────────

def test_get_position(client):
    r = client.get("/api/v1/nav/position")
    assert r.status_code == 200
    data = r.json()
    assert "lat" in data
    assert "lon" in data
    assert "satellites" in data


def test_route_drone(client):
    payload = {
        "origin_lat": 32.0, "origin_lon": 34.0,
        "dest_lat": 33.0, "dest_lon": 35.0,
        "mode": "drone",
    }
    r = client.post("/api/v1/nav/route", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["distance_km"] > 0
    assert data["eta_minutes"] > 0
    assert data["mode"] == "drone"


# ── SOS ───────────────────────────────────────────────────────────────────────

def test_sos_distress(client):
    payload = {
        "lat": 32.0853, "lon": 34.7818,
        "message": "API integration test SOS",
        "priority": "DISTRESS",
        "sender_id": "test_suite",
    }
    r = client.post("/api/v1/sos", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["incident_id"]
    assert data["acknowledged"] is True
    assert len(data["channels_used"]) > 0


# ── Telemetry ─────────────────────────────────────────────────────────────────

def test_ingest_normal_reading(client):
    payload = {"sensor_id": "temp-api-01", "value": 22.5, "unit": "°C"}
    r = client.post("/api/v1/telemetry/ingest", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["sensor_id"] == "temp-api-01"
    assert "anomaly_detected" in data


def test_telemetry_summary(client):
    r = client.get("/api/v1/telemetry/summary")
    assert r.status_code == 200
    assert "streams" in r.json()


# ── Sonic Matrix ──────────────────────────────────────────────────────────────

def test_detect_language(client):
    r = client.post("/api/v1/sonic/detect", json={"text": "Hello, how are you?"})
    assert r.status_code == 200
    data = r.json()
    assert "language" in data


def test_supported_languages(client):
    r = client.get("/api/v1/sonic/languages")
    assert r.status_code == 200
    data = r.json()
    assert "languages" in data
    assert len(data["languages"]) > 10


# ── Security ──────────────────────────────────────────────────────────────────

def test_scan_clean_input(client):
    r = client.post("/api/v1/security/scan-input", params={"text": "Hello safe world"})
    assert r.status_code == 200
    assert r.json()["clean"] is True


def test_scan_sql_injection(client):
    r = client.post(
        "/api/v1/security/scan-input",
        params={"text": "SELECT * FROM users WHERE 1=1; DROP TABLE users;"}
    )
    assert r.status_code == 200
    data = r.json()
    assert data["clean"] is False
    assert data["threat"]["level"] in ("HIGH", "CRITICAL")


def test_audit_config(client):
    config = {"debug": True, "secret_key": "changeme", "https_only": False}
    r = client.post("/api/v1/security/audit-config", json=config)
    assert r.status_code == 200
    data = r.json()
    assert data["risk_score"] > 0
    assert len(data["vulnerabilities"]) > 0


# ── Creative Engine ───────────────────────────────────────────────────────────

def test_image_prompt(client):
    payload = {"subject": "futuristic AI robot in space", "style": "cinematic"}
    r = client.post("/api/v1/creative/image-prompt", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert "prompt" in data
    assert "cinematic" in data["prompt"].lower() or "cinematic" in data["style"]


def test_generate_badge(client):
    r = client.get("/api/v1/creative/badge", params={"text": "ONLINE", "color": "#00f5ff"})
    assert r.status_code == 200
    assert b"svg" in r.content.lower()
    assert b"ONLINE" in r.content


# ── NEXUS-SYNC ────────────────────────────────────────────────────────────────

def test_register_and_list_device(client):
    payload = {
        "device_id": "test-drone-001",
        "device_type": "drone",
        "protocol": "MQTT",
        "endpoint": "mqtt://localhost:1883",
        "name": "Test Drone",
        "capabilities": ["camera", "gps"],
    }
    r = client.post("/api/v1/nexus/devices", json=payload)
    assert r.status_code == 200
    device = r.json()
    assert device["device_id"] == "test-drone-001"

    r2 = client.get("/api/v1/nexus/devices")
    assert r2.status_code == 200
    ids = [d["device_id"] for d in r2.json()]
    assert "test-drone-001" in ids


# ── Security Middleware ───────────────────────────────────────────────────────

def test_security_headers(client):
    r = client.get("/")
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert "GENESIS" in r.headers.get("X-BRAINIAC-Node", "")


def test_parse_content_length_robust():
    with patch("brainiac.core.neuro_core.anthropic.AsyncAnthropic"):
        from brainiac.api.main import _parse_content_length

    assert _parse_content_length(None) is None
    assert _parse_content_length("abc") is None
    assert _parse_content_length("-1") is None
    assert _parse_content_length("0") == 0
    assert _parse_content_length("1024") == 1024


def test_oversized_payload_rejected(client):
    payload = b"A" * (10 * 1024 * 1024 + 1)
    r = client.post("/api/v1/vision/analyze", content=payload)
    assert r.status_code == 413
