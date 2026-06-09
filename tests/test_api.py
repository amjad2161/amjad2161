"""Integration tests for BRAINIAC REST API."""

from __future__ import annotations

import io
import logging
from unittest.mock import patch

import pytest
import structlog
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client with mocked AI calls."""
    with patch("brainiac.core.neuro_core.anthropic.AsyncAnthropic"):
        from brainiac.api.main import app

        with TestClient(app, raise_server_exceptions=False) as test_client:
            yield test_client


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
    assert len(data["modules"]) == 10
    assert data["uptime_s"] >= 0


def test_diagnostics(client):
    r = client.get("/diagnostics")
    assert r.status_code == 200
    data = r.json()
    expected_modules = [
        "neuro_core",
        "orbital_nav",
        "satlink",
        "sonic_matrix",
        "nexus_sync",
        "telemetry_hub",
        "cyber_shield",
        "creative_engine",
        "omni_vision",
        "reel_maker",
    ]
    for mod in expected_modules:
        assert mod in data


def test_reel_trends(client):
    r = client.get("/api/v1/reel/trends?niche=tech")
    assert r.status_code == 200
    data = r.json()
    assert "viral_hooks" in data
    assert "trending_hashtags" in data


def test_reel_social_status(client):
    r = client.get("/api/v1/reel/social/status")
    assert r.status_code == 200
    data = r.json()
    assert "platforms" in data
    assert "instagram" in data["platforms"]
    assert "oauth_hint" in data["platforms"]["instagram"]
    assert "webhook_configured" in data
    assert "accounts" in data
    assert "oauth_providers" in data
    assert "connect_all" in data


def test_reel_social_accounts_crud(client):
    r = client.get("/api/v1/reel/social/accounts")
    assert r.status_code == 200
    assert r.json()["accounts"] == []

    r = client.delete("/api/v1/reel/social/accounts/does-not-exist")
    assert r.status_code == 404

    r = client.post("/api/v1/reel/social/accounts/does-not-exist/default")
    assert r.status_code == 404


def test_reel_oauth_start_unknown_provider(client):
    r = client.get("/api/v1/reel/social/oauth/start/unknown?redirect=false")
    assert r.status_code == 400


def test_reel_oauth_start_all(client):
    r = client.get("/api/v1/reel/social/oauth/start-all?label=test-bundle")
    assert r.status_code == 200
    data = r.json()
    assert data["label"] == "test-bundle"
    assert len(data["connections"]) == 3


def test_reel_dashboard_has_social_connect(client):
    r = client.get("/reel")
    assert r.status_code == 200
    assert "Connect all" in r.text
    assert "Social accounts" in r.text


def test_reel_dashboard(client):
    r = client.get("/reel")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "BRAINIAC REEL-MAKER" in r.text


def test_reel_compose_and_publish(client):
    r = client.post(
        "/api/v1/reel/compose",
        json={
            "topic": "test viral reel",
            "style": "viral_hook",
            "platforms": ["tiktok"],
            "voiceover": False,
        },
    )
    assert r.status_code == 200
    job = r.json()
    assert job["status"] == "ready"
    assert job["job_id"]
    assert job["algorithm_score"] > 0

    r2 = client.post(f"/api/v1/reel/jobs/{job['job_id']}/publish", json={"dry_run": True})
    assert r2.status_code == 200
    assert r2.json()["dry_run"] is True

    r3 = client.get(f"/api/v1/reel/jobs/{job['job_id']}/video")
    assert r3.status_code == 200
    assert r3.headers["content-type"].startswith("video/")

    r4 = client.get(f"/api/v1/reel/jobs/{job['job_id']}/thumbnail")
    assert r4.status_code == 200
    assert r4.headers["content-type"].startswith("image/")


def test_metrics(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "brainiac_telemetry" in r.text


def test_cost_stats_endpoint(client):
    r = client.get("/api/v1/system/cost-stats")
    assert r.status_code == 200
    data = r.json()
    assert "hourly_cost_usd" in data
    assert "max_usd_per_hour" in data


def test_watchdog_endpoint(client):
    r = client.get("/api/v1/system/watchdog")
    assert r.status_code == 200
    assert "module_health" in r.json()


def test_shutdown_test_requires_admin(client):
    r = client.post("/api/v1/system/shutdown-test")
    assert r.status_code == 403


def test_shutdown_test_admin(client):
    r = client.post("/api/v1/system/shutdown-test", headers={"X-BRAINIAC-Admin": "brainiac-admin"})
    assert r.status_code == 200
    assert r.json()["marker"] == "shutdown_test_triggered"


def test_get_position(client):
    r = client.get("/api/v1/nav/position")
    assert r.status_code == 200
    data = r.json()
    assert "lat" in data
    assert "lon" in data
    assert "satellites" in data


def test_route_drone(client):
    payload = {
        "origin_lat": 32.0,
        "origin_lon": 34.0,
        "dest_lat": 33.0,
        "dest_lon": 35.0,
        "mode": "drone",
    }
    r = client.post("/api/v1/nav/route", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["distance_km"] > 0
    assert data["eta_minutes"] > 0
    assert data["mode"] == "drone"


def test_route_submarine(client):
    payload = {
        "origin_lat": 32.0,
        "origin_lon": 34.0,
        "dest_lat": 32.1,
        "dest_lon": 34.1,
        "mode": "submarine",
    }
    r = client.post("/api/v1/nav/route", json=payload)
    assert r.status_code == 200
    assert r.json()["mode"] == "submarine"


def test_nav_cache_stats(client):
    payload = {
        "origin_lat": 32.0,
        "origin_lon": 34.0,
        "dest_lat": 32.1,
        "dest_lon": 34.1,
        "mode": "driving",
    }
    client.post("/api/v1/nav/route", json=payload)
    r = client.get("/api/v1/nav/cache-stats")
    assert r.status_code == 200
    data = r.json()
    assert data["maxsize"] == 256


def test_sos_distress(client):
    payload = {
        "lat": 32.0853,
        "lon": 34.7818,
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


def test_scan_clean_input(client):
    r = client.post("/api/v1/security/scan-input", params={"text": "Hello safe world"})
    assert r.status_code == 200
    assert r.json()["clean"] is True


def test_scan_sql_injection(client):
    r = client.post(
        "/api/v1/security/scan-input",
        params={"text": "SELECT * FROM users WHERE 1=1; DROP TABLE users;"},
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


def test_image_prompt(client):
    payload = {"subject": "futuristic AI robot in space", "style": "cinematic"}
    r = client.post("/api/v1/creative/image-prompt", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert "prompt" in data


def test_generate_badge(client):
    r = client.get("/api/v1/creative/badge", params={"text": "ONLINE", "color": "#00f5ff"})
    assert r.status_code == 200
    assert b"svg" in r.content.lower()
    assert b"ONLINE" in r.content


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

    r2 = client.get("/api/v1/nexus/devices")
    assert r2.status_code == 200
    ids = [d["device_id"] for d in r2.json()]
    assert "test-drone-001" in ids


def test_security_headers(client):
    r = client.get("/")
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert "GENESIS" in r.headers.get("X-BRAINIAC-Node", "")
    assert r.headers.get("X-Request-Id")


def test_request_id_passthrough(client):
    req_id = "req-test-123"
    r = client.get("/", headers={"X-Request-Id": req_id})
    assert r.status_code == 200
    assert r.headers.get("X-Request-Id") == req_id


def test_request_id_in_structlog(client):
    previous_config = structlog.get_config()
    log_output = io.StringIO()
    handler = logging.StreamHandler(log_output)
    logger = logging.getLogger("brainiac.api")
    old_handlers = list(logger.handlers)

    try:
        logger.handlers = [handler]
        logger.setLevel(logging.INFO)

        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.processors.KeyValueRenderer(key_order=["event", "request_id"]),
            ],
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
        )

        req_id = "trace-abc-123"
        r = client.get("/", headers={"X-Request-Id": req_id})
        assert r.status_code == 200
        assert r.headers["X-Request-Id"] == req_id

        handler.flush()
        logs = log_output.getvalue()
        assert req_id in logs
    finally:
        logger.handlers = old_handlers
        structlog.configure(**previous_config)


def test_request_body_too_large(client):
    headers = {"Content-Length": str((10 * 1024 * 1024) + 1)}
    r = client.post("/api/v1/vision/info", content=b"x", headers=headers)
    assert r.status_code == 413
