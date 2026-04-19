"""Tests for NEXUS-SYNC module."""

import pytest

from brainiac.core.nexus_sync import DeviceType, Message, NexusSync, Protocol


@pytest.fixture
def nexus():
    return NexusSync()


def test_register_device(nexus):
    device = nexus.register_device(
        device_id="drone-001",
        device_type=DeviceType.DRONE,
        protocol=Protocol.MQTT,
        endpoint="mqtt://192.168.1.10:1883",
        name="Recon Drone Alpha",
        capabilities=["camera", "gps", "sos"],
    )
    assert device.device_id == "drone-001"
    assert device.device_type == DeviceType.DRONE
    assert "camera" in device.capabilities


@pytest.mark.asyncio
async def test_connect_device(nexus):
    nexus.register_device("sensor-001", DeviceType.IOT_SENSOR, Protocol.MQTT, "mqtt://localhost")
    ok = await nexus.connect_device("sensor-001")
    assert ok is True
    device = nexus.get_device("sensor-001")
    assert device.connected is True
    assert device.last_seen > 0


@pytest.mark.asyncio
async def test_disconnect_device(nexus):
    nexus.register_device("plc-001", DeviceType.INDUSTRIAL_PLC, Protocol.MODBUS, "tcp://10.0.0.5")
    await nexus.connect_device("plc-001")
    ok = await nexus.disconnect_device("plc-001")
    assert ok is True
    assert nexus.get_device("plc-001").connected is False


@pytest.mark.asyncio
async def test_publish_and_subscribe(nexus):
    nexus.register_device("cam-001", DeviceType.IOT_SENSOR, Protocol.MQTT, "mqtt://cam")
    await nexus.connect_device("cam-001")

    received: list[Message] = []

    async def handler(msg: Message):
        received.append(msg)

    nexus.subscribe("sensors/temperature", handler)
    msg = await nexus.publish("cam-001", "sensors/temperature", {"value": 22.5, "unit": "C"})

    assert msg.topic == "sensors/temperature"
    assert len(received) == 1
    assert received[0].payload["value"] == 22.5


@pytest.mark.asyncio
async def test_wildcard_subscription(nexus):
    nexus.register_device("dev-x", DeviceType.WEARABLE, Protocol.WEBSOCKET, "ws://localhost")
    await nexus.connect_device("dev-x")

    all_messages = []
    nexus.subscribe("#", lambda msg: all_messages.append(msg))

    await nexus.publish("dev-x", "any/topic/here", {"data": 1})
    await nexus.publish("dev-x", "other/topic", {"data": 2})
    assert len(all_messages) == 2


@pytest.mark.asyncio
async def test_command_dispatch(nexus):
    nexus.register_device("robot-01", DeviceType.ROBOT, Protocol.GRPC, "grpc://robot:50051")
    await nexus.connect_device("robot-01")

    resp = await nexus.command("robot-01", "move_forward", {"speed": 1.5, "duration_s": 3})
    assert resp["status"] == "OK"
    assert resp["command"] == "move_forward"


@pytest.mark.asyncio
async def test_command_disconnected_device(nexus):
    nexus.register_device("offline-01", DeviceType.IOT_SENSOR, Protocol.REST, "http://offline")
    # Do NOT connect
    resp = await nexus.command("offline-01", "ping")
    assert "error" in resp


def test_list_devices_filter(nexus):
    nexus.register_device("d1", DeviceType.DRONE, Protocol.MQTT, "mqtt://d1")
    nexus.register_device("d2", DeviceType.VEHICLE, Protocol.REST, "http://d2")
    nexus.register_device("d3", DeviceType.DRONE, Protocol.MQTT, "mqtt://d3")

    drones = nexus.list_devices(device_type=DeviceType.DRONE)
    assert len(drones) == 2
    assert all(d.device_type == DeviceType.DRONE for d in drones)


def test_diagnostics(nexus):
    d = nexus.diagnostics()
    assert d["status"] == "ONLINE"
    assert d["max_connections"] == 100_000
