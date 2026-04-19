"""Tests for NexusSync mesh networking (LoRaWAN/BLE) and V2X protocols."""
import pytest

from brainiac.core.nexus_sync import NexusSync, DeviceType, Protocol


@pytest.fixture
def nexus():
    return NexusSync()


# ── Mesh Networking ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_lorawan_mesh_broadcast(nexus):
    """Broadcast to LoRaWAN mesh nodes delivers to all connected nodes."""
    nexus.register_device("lora-01", DeviceType.MESH_NODE, Protocol.LORAWAN, "lora://hub")
    nexus.register_device("lora-02", DeviceType.MESH_NODE, Protocol.LORAWAN, "lora://hub")
    await nexus.connect_device("lora-01")
    await nexus.connect_device("lora-02")

    result = await nexus.broadcast_mesh(
        payload={"alert": "emergency_route_cleared"},
        protocol=Protocol.LORAWAN,
        ttl=3,
    )
    assert result["protocol"] == "LoRaWAN"
    assert result["nodes_reached"] == 2
    assert "lora-01" in result["device_ids"]
    assert "lora-02" in result["device_ids"]
    assert result["ttl"] == 3


@pytest.mark.asyncio
async def test_ble_mesh_broadcast(nexus):
    """BLE Mesh broadcast reaches only BLE Mesh nodes."""
    nexus.register_device("ble-01", DeviceType.MESH_NODE, Protocol.BLE_MESH, "ble://local")
    nexus.register_device("mqtt-01", DeviceType.IOT_SENSOR, Protocol.MQTT, "mqtt://cloud")
    await nexus.connect_device("ble-01")
    await nexus.connect_device("mqtt-01")

    result = await nexus.broadcast_mesh({"msg": "proximity_alert"}, protocol=Protocol.BLE_MESH)
    assert result["nodes_reached"] == 1
    assert "ble-01" in result["device_ids"]
    assert "mqtt-01" not in result["device_ids"]


@pytest.mark.asyncio
async def test_mesh_broadcast_no_nodes(nexus):
    """Broadcast with no mesh nodes returns zero delivery."""
    result = await nexus.broadcast_mesh({"payload": "x"})
    assert result["nodes_reached"] == 0


def test_mesh_topology_empty(nexus):
    topo = nexus.mesh_topology()
    assert topo["total_nodes"] == 0
    assert topo["connected_nodes"] == 0


@pytest.mark.asyncio
async def test_mesh_topology_populated(nexus):
    nexus.register_device("lora-01", DeviceType.MESH_NODE, Protocol.LORAWAN, "lora://x")
    nexus.register_device("ble-01", DeviceType.MESH_NODE, Protocol.BLE_MESH, "ble://y")
    await nexus.connect_device("lora-01")

    topo = nexus.mesh_topology()
    assert topo["total_nodes"] == 2
    assert topo["connected_nodes"] == 1
    assert "LoRaWAN" in topo["protocols"]
    assert "BLE_Mesh" in topo["protocols"]


# ── V2X Messaging ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_v2x_signal_to_rsu(nexus):
    """V2I signal reaches connected Roadside Units."""
    nexus.register_device("rsu-001", DeviceType.V2X_RSU, Protocol.V2X, "v2x://intersection/42")
    await nexus.connect_device("rsu-001")

    result = await nexus.v2x_signal(
        signal_type="V2I",
        data={"speed_kmh": 60, "direction": "north"},
        source_id="ambulance-7",
    )
    assert result["signal_type"] == "V2I"
    assert result["targets_reached"] == 1
    assert "rsu-001" in result["device_ids"]


@pytest.mark.asyncio
async def test_v2x_traffic_light_preemption(nexus):
    """Traffic-light preemption request succeeds when RSU is connected."""
    nexus.register_device("rsu-main", DeviceType.V2X_RSU, Protocol.V2X, "v2x://int/main")
    await nexus.connect_device("rsu-main")

    result = await nexus.v2x_traffic_light_request(
        intersection_id="INT-42",
        priority="emergency",
        reason="ambulance_en_route",
    )
    assert result["status"] == "OK"
    assert result["params"]["intersection_id"] == "INT-42"
    assert result["params"]["priority"] == "emergency"


@pytest.mark.asyncio
async def test_v2x_traffic_light_no_rsu(nexus):
    """Preemption request with no RSU returns graceful NO_RSU status."""
    result = await nexus.v2x_traffic_light_request("INT-99", priority="emergency")
    assert result["status"] == "NO_RSU"
    assert result["intersection_id"] == "INT-99"


# ── Diagnostics ──────────────────────────────────────────────────────────────

def test_nexus_capabilities_includes_mesh_and_v2x(nexus):
    caps = nexus.diagnostics()["capabilities"]
    assert "lorawan_mesh" in caps
    assert "ble_mesh" in caps
    assert "v2x_messaging" in caps
    assert "traffic_light_priority" in caps


@pytest.mark.asyncio
async def test_nexus_diagnostics_tracks_mesh_v2x_counts(nexus):
    nexus.register_device("m1", DeviceType.MESH_NODE, Protocol.LORAWAN, "x")
    nexus.register_device("m2", DeviceType.MESH_NODE, Protocol.BLE_MESH, "x")
    nexus.register_device("v1", DeviceType.V2X_RSU, Protocol.V2X, "x")
    d = nexus.diagnostics()
    assert d["mesh_nodes"] == 2
    assert d["v2x_nodes"] == 1
