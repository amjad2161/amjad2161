"""Integration tests — verify all BRAINIAC modules work together."""

import pytest

from brainiac.core import (
    CreativeEngine,
    CyberShield,
    NexusSync,
    OmniVision,
    OrbitalNav,
    SatLink,
    SonicMatrix,
    TelemetryHub,
)
from brainiac.core.nexus_sync import DeviceType, Protocol
from brainiac.core.satlink import SOSPriority
from brainiac.core.telemetry_hub import SensorReading


@pytest.mark.asyncio
async def test_full_system_online():
    """Every module must come up in ONLINE status."""
    nav = OrbitalNav()
    sonic = SonicMatrix()
    satlink = SatLink()
    nexus = NexusSync()
    telem = TelemetryHub()
    shield = CyberShield(secret_key="integration-test")
    creative = CreativeEngine()
    vision = OmniVision()

    await satlink.connect()

    statuses = {
        "orbital_nav": nav.diagnostics()["status"],
        "sonic_matrix": sonic.diagnostics()["status"],
        "satlink": satlink.diagnostics()["status"],
        "nexus_sync": nexus.diagnostics()["status"],
        "telemetry_hub": telem.diagnostics()["status"],
        "cyber_shield": shield.diagnostics()["status"],
        "creative_engine": creative.diagnostics()["status"],
        "omni_vision": vision.diagnostics()["status"],
    }
    for name, status in statuses.items():
        assert status == "ONLINE", f"{name} is {status}"


@pytest.mark.asyncio
async def test_emergency_flow_end_to_end():
    """
    Realistic emergency flow:
    1. ORBITAL-NAV gets position
    2. TELEMETRY-HUB detects a vitals anomaly
    3. SATLINK-X broadcasts SOS
    4. NEXUS-SYNC notifies connected drone
    5. CYBER-SHIELD signs the incident report
    """
    nav = OrbitalNav()
    telem = TelemetryHub(window_size=10)
    satlink = SatLink()
    nexus = NexusSync()
    shield = CyberShield(secret_key="emergency-test")

    # Step 1
    pos = await nav.get_position()
    assert pos.accuracy_m < 1.0  # RTK precision

    # Step 2 — baseline + anomaly (realistic noisy HR readings)
    for i in range(20):
        # Heart rate oscillates slightly around 72 bpm (realistic noise)
        hr = 72.0 + (0.3 if i % 2 == 0 else -0.3)
        await telem.ingest(SensorReading(sensor_id="heart-rate", value=hr, unit="bpm"))
    # Cardiac event — massive spike
    anomaly = await telem.ingest(SensorReading(sensor_id="heart-rate", value=220.0, unit="bpm"))
    assert anomaly is not None, "Cardiac spike must be detected"

    # Step 3 — broadcast SOS
    await satlink.connect()
    packet = await satlink.send_sos(
        lat=pos.lat,
        lon=pos.lon,
        message="VITALS ANOMALY — heart rate 220 bpm",
        priority=SOSPriority.DISTRESS,
        sender_id="wearable-001",
    )
    assert packet.acknowledged
    assert len(packet.channels_used) > 0

    # Step 4 — notify rescue drone via NEXUS
    nexus.register_device(
        device_id="rescue-drone-01",
        device_type=DeviceType.DRONE,
        protocol=Protocol.MQTT,
        endpoint="mqtt://rescue",
    )
    await nexus.connect_device("rescue-drone-01")
    resp = await nexus.command(
        "rescue-drone-01",
        "dispatch",
        {"target_lat": pos.lat, "target_lon": pos.lon, "incident_id": packet.incident_id},
    )
    assert resp["status"] == "OK"

    # Step 5 — sign incident for audit trail
    incident_report = {
        "incident_id": packet.incident_id,
        "location": {"lat": pos.lat, "lon": pos.lon},
        "anomaly_severity": anomaly.severity,
        "responders": packet.responders_notified,
    }
    signature = shield.sign(incident_report)
    assert shield.verify_signature(incident_report, signature)


@pytest.mark.asyncio
async def test_navigation_integrated_with_shield():
    """Routing requests must pass input sanitisation."""
    shield = CyberShield()
    malicious = "'; DROP TABLE routes;--"
    threat = shield.scan_input(malicious)
    assert threat is not None
    assert threat.threat_level.value >= 3


@pytest.mark.asyncio
async def test_sonic_translates_nav_instructions():
    """Navigation instructions can be translated via SONIC-MATRIX."""
    sonic = SonicMatrix()
    detected = sonic.detect_language("Turn left in 200 meters")
    assert detected["language"] == "en"


def test_creative_generates_badge_for_status():
    """CREATIVE-ENGINE can render status badges used in dashboards."""
    engine = CreativeEngine()
    online = engine.generate_svg_badge("ONLINE", color="#00ff88")
    offline = engine.generate_svg_badge("OFFLINE", color="#ff4444")
    assert "ONLINE" in online
    assert "OFFLINE" in offline


@pytest.mark.asyncio
async def test_telemetry_feeds_nexus_devices():
    """Sensor readings from NEXUS-SYNC devices flow into TELEMETRY-HUB."""
    nexus = NexusSync()
    telem = TelemetryHub(window_size=5)

    nexus.register_device("temp-01", DeviceType.IOT_SENSOR, Protocol.MQTT, "mqtt://temp")
    await nexus.connect_device("temp-01")

    async def ingest_handler(msg):
        reading = SensorReading(
            sensor_id=msg.device_id,
            value=msg.payload.get("value", 0.0),
            unit=msg.payload.get("unit", ""),
        )
        await telem.ingest(reading)

    nexus.subscribe("sensors/temp", ingest_handler)

    for v in [20.0, 20.5, 21.0, 20.8, 20.3]:
        await nexus.publish("temp-01", "sensors/temp", {"value": v, "unit": "°C"})

    summary = telem.stream_summary()
    assert any(s["sensor_id"] == "temp-01" for s in summary)
    temp_stream = next(s for s in summary if s["sensor_id"] == "temp-01")
    assert temp_stream["readings_count"] == 5
