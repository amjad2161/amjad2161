"""Tests for the BRAINIAC SDK client (uses FastAPI TestClient + httpx-mock pattern)."""
import asyncio
import pytest
import httpx

from brainiac.sdk import BrainiacClient, BrainiacSync
from brainiac.api.main import app


@pytest.fixture
async def client():
    """Create an SDK client wired to the FastAPI app via ASGITransport."""
    transport = httpx.ASGITransport(app=app)
    sdk = BrainiacClient(base_url="http://testserver")
    sdk._client = httpx.AsyncClient(transport=transport, base_url="http://testserver")
    yield sdk
    await sdk.close()


@pytest.mark.asyncio
async def test_health(client):
    data = await client.health()
    assert data["status"] == "ONLINE"
    assert len(data["modules"]) == 11


@pytest.mark.asyncio
async def test_position(client):
    pos = await client.position()
    assert "lat" in pos
    assert "lon" in pos
    assert "satellites" in pos


@pytest.mark.asyncio
async def test_drone_route(client):
    route = await client.route(32.0, 34.0, 33.0, 35.0, mode="drone")
    assert route["distance_km"] > 0
    assert route["mode"] == "drone"


@pytest.mark.asyncio
async def test_sos_broadcast(client):
    result = await client.sos(32.0, 34.8, "SDK test SOS", priority="DISTRESS")
    assert result["acknowledged"] is True
    assert len(result["channels_used"]) >= 5


@pytest.mark.asyncio
async def test_satellite_passes(client):
    passes = await client.satellite_passes(32.0, 34.8, hours=24)
    assert len(passes) > 0


@pytest.mark.asyncio
async def test_telemetry_ingest(client):
    result = await client.ingest("sdk-sensor-01", 42.0, unit="V")
    assert result["sensor_id"] == "sdk-sensor-01"


@pytest.mark.asyncio
async def test_register_device(client):
    result = await client.register_device(
        device_id="sdk-drone-01",
        device_type="drone",
        protocol="MQTT",
        endpoint="mqtt://test",
        name="SDK Test Drone",
        capabilities=["camera", "gps"],
    )
    assert result["device_id"] == "sdk-drone-01"
    assert result["connected"] is True


@pytest.mark.asyncio
async def test_scan_input_clean(client):
    result = await client.scan_input("Hello, safe world")
    assert result["clean"] is True


@pytest.mark.asyncio
async def test_scan_sql_injection(client):
    result = await client.scan_input("SELECT * FROM users WHERE 1=1; DROP TABLE users;")
    assert result["clean"] is False


@pytest.mark.asyncio
async def test_image_prompt(client):
    result = await client.image_prompt("a futuristic robot", style="cinematic")
    assert "prompt" in result


@pytest.mark.asyncio
async def test_badge(client):
    svg = await client.badge("ONLINE", color="#00ff88")
    assert "<svg" in svg
    assert "ONLINE" in svg


@pytest.mark.asyncio
async def test_audit_config(client):
    result = await client.audit_config({"debug": True, "https_only": False})
    assert result["risk_score"] > 0


def test_brainiac_sync_context_manager():
    sync = BrainiacSync(base_url="http://localhost:9999")
    assert hasattr(sync, "__enter__")
    assert hasattr(sync, "__exit__")
    sync.close()


# ── New endpoints wired through the SDK ───────────────────────────────────────

@pytest.mark.asyncio
async def test_sdk_turn_by_turn(client):
    result = await client.turn_by_turn(32.0, 34.0, 32.1, 34.1, mode="drone", lang="he")
    assert result["lang"] == "he"
    assert result["is_rtl"] is True
    assert len(result["instructions"]) >= 1


@pytest.mark.asyncio
async def test_sdk_eta_with_traffic(client):
    result = await client.eta_with_conditions(
        32.0, 34.0, 33.0, 35.0, mode="driving", hour=8, weekday=1,
    )
    assert result["traffic_factor"] == 1.7
    assert result["adjusted_duration_s"] > result["duration_s"]


@pytest.mark.asyncio
async def test_sdk_battery_check(client):
    result = await client.battery_check(
        32.0, 34.0, 32.01, 34.01, battery_wh=10000, mode="drone",
    )
    assert result["feasible"] is True


@pytest.mark.asyncio
async def test_sdk_medical_protocols_list(client):
    result = await client.medical_protocols()
    assert "acls_cardiac_arrest" in result["protocols"]


@pytest.mark.asyncio
async def test_sdk_medical_dose(client):
    result = await client.medical_dose("epinephrine", 70.0)
    assert result["drug"] == "Epinephrine"
    assert result["actual_dose_mg"] > 0


@pytest.mark.asyncio
async def test_sdk_medical_triage(client):
    result = await client.medical_triage(
        heart_rate=0, respiratory_rate=0, systolic_bp=0, gcs=3,
    )
    assert result["category"] == "immediate"


@pytest.mark.asyncio
async def test_sdk_medical_drug_info(client):
    result = await client.medical_drug("naloxone")
    assert result["drug"] == "Naloxone"
