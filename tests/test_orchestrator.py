"""Tests for the BRAINIAC master orchestrator."""
import pytest
from brainiac import (
    Brainiac, Mission, MissionType, SystemState,
    Coordinate, DeviceType, Protocol, SensorReading,
)
from brainiac.core.satlink import SOSPriority


@pytest.fixture
async def brainiac():
    bot = Brainiac(secret_key="orchestrator-test")
    await bot.boot()
    yield bot
    await bot.shutdown()


@pytest.mark.asyncio
async def test_boot_brings_all_modules_online(brainiac):
    report = await brainiac.health_report()
    assert report.system_state == SystemState.ONLINE
    assert len(report.modules) == 9
    assert not report.alerts


@pytest.mark.asyncio
async def test_plan_rescue_mission(brainiac):
    origin = Coordinate(lat=32.0853, lon=34.7818)
    dest   = Coordinate(lat=31.7683, lon=35.2137)
    mission = await brainiac.plan_mission(MissionType.RESCUE, origin, dest)

    assert mission.status == "PLANNED"
    assert mission.plan["transport_mode"] == "drone"
    assert mission.plan["distance_km"] > 0
    assert len(mission.plan["safety_checklist"]) >= 4


@pytest.mark.asyncio
async def test_execute_mission_lifecycle(brainiac):
    origin = Coordinate(lat=32.0, lon=34.0)
    dest   = Coordinate(lat=33.0, lon=35.0)
    mission = await brainiac.plan_mission(MissionType.DELIVERY, origin, dest)
    executed = await brainiac.execute_mission(mission)

    assert executed.status == "COMPLETED"
    assert executed.started_at is not None
    assert executed.completed_at is not None
    assert len(executed.events) >= 6   # TAKEOFF → LANDED


@pytest.mark.asyncio
async def test_emergency_response_integrated(brainiac):
    # Pre-register a rescue drone
    brainiac.nexus.register_device(
        "rescue-01", DeviceType.DRONE, Protocol.MQTT, "mqtt://rescue"
    )
    await brainiac.nexus.connect_device("rescue-01")

    result = await brainiac.emergency(
        lat=32.0, lon=34.8,
        message="TEST EMERGENCY via orchestrator",
        priority=SOSPriority.MAYDAY,
    )

    assert result["acknowledged"] is True
    assert result["response_channels"] >= 5
    assert "rescue-01" in result["incident"]["drones_dispatched"]
    assert result["signature"]


@pytest.mark.asyncio
async def test_auto_wiring_anomaly_triggers_sos(brainiac):
    """
    Critical telemetry anomaly should auto-trigger SOS via the auto-wiring
    configured during boot().
    """
    # Feed a stable baseline
    for _ in range(15):
        await brainiac.telem.ingest(SensorReading(sensor_id="critical-pressure", value=100.0, unit="Pa"))

    # Inject massive spike — severity will be 1.0 → auto-SOS fires
    initial_incidents = brainiac.satlink.diagnostics()["active_incidents"]
    await brainiac.telem.ingest(SensorReading(sensor_id="critical-pressure", value=1_000_000.0, unit="Pa"))
    after_incidents = brainiac.satlink.diagnostics()["active_incidents"]

    assert after_incidents > initial_incidents, "Auto-wired SOS should have fired"


@pytest.mark.asyncio
async def test_nexus_telemetry_auto_ingest(brainiac):
    """NEXUS messages on 'telemetry/*' topics should auto-flow into TELEMETRY-HUB."""
    brainiac.nexus.register_device(
        "sensor-xyz", DeviceType.IOT_SENSOR, Protocol.MQTT, "mqtt://sensor"
    )
    await brainiac.nexus.connect_device("sensor-xyz")

    initial_readings = brainiac.telem.diagnostics()["total_readings"]
    await brainiac.nexus.publish(
        "sensor-xyz", "telemetry/temperature", {"value": 22.5, "unit": "C"}
    )
    after_readings = brainiac.telem.diagnostics()["total_readings"]

    assert after_readings > initial_readings


@pytest.mark.asyncio
async def test_event_bus(brainiac):
    received = []
    brainiac.on("test_event", lambda data: received.append(data))
    await brainiac.emit("test_event", {"value": 42})
    assert len(received) == 1
    assert received[0]["value"] == 42


def test_mission_mode_mapping(brainiac):
    from brainiac.core.orbital_nav import TransportMode
    assert Brainiac._mode_for_mission(MissionType.RESCUE) == TransportMode.DRONE
    assert Brainiac._mode_for_mission(MissionType.DELIVERY) == TransportMode.DRIVE
    assert Brainiac._mode_for_mission(MissionType.EXPLORATION) == TransportMode.SPACECRAFT
