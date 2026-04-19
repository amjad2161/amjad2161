"""Tests for SATLINK-X module."""
import pytest
from brainiac.core.satlink import SatLink, SOSPriority, BroadcastChannel


@pytest.fixture
def satlink():
    return SatLink(node_id="TEST-NODE")


@pytest.mark.asyncio
async def test_connect(satlink):
    result = await satlink.connect()
    assert result["status"] in ("CONNECTED", "DEGRADED")
    for ch in BroadcastChannel:
        assert ch.value in result["channels"]


@pytest.mark.asyncio
async def test_sos_mayday(satlink):
    await satlink.connect()
    packet = await satlink.send_sos(
        lat=32.0853,
        lon=34.7818,
        message="TEST MAYDAY — simulation only",
        priority=SOSPriority.MAYDAY,
        sender_id="unit_test",
    )
    assert packet.incident_id
    assert packet.acknowledged
    assert len(packet.channels_used) > 0
    assert packet.ack_timestamp is not None
    assert len(packet.responders_notified) > 0


@pytest.mark.asyncio
async def test_sos_routine(satlink):
    await satlink.connect()
    packet = await satlink.send_sos(
        lat=31.7683, lon=35.2137,
        message="Routine check",
        priority=SOSPriority.ROUTINE,
    )
    assert packet.incident_id
    assert packet.acknowledged


@pytest.mark.asyncio
async def test_satellite_passes(satlink):
    passes = await satlink.predict_passes(lat=32.0, lon=34.8, hours_ahead=24)
    assert len(passes) > 0
    for p in passes:
        assert p.sat_id
        assert 0 <= p.link_quality <= 1
        assert p.aos_time < p.los_time


@pytest.mark.asyncio
async def test_telemetry_uplink(satlink):
    await satlink.connect()
    ok = await satlink.uplink_telemetry({"temperature": 22.5, "pressure": 1013.0})
    assert ok is True


def test_pqc_encrypt_deterministic(satlink):
    plain = "test payload"
    enc1 = satlink._pqc_encrypt(plain)
    enc2 = satlink._pqc_encrypt(plain)
    assert enc1 == enc2
    assert plain in enc1   # passthrough in stub


def test_diagnostics(satlink):
    d = satlink.diagnostics()
    assert d["node_id"] == "TEST-NODE"
    assert "active_incidents" in d
