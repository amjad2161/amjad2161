"""
NEXUS-SYNC — Universal Integration Hub
========================================
Connects BRAINIAC to IoT, industrial SCADA, vehicles, smart cities,
medical devices, drones — via MQTT, WebSocket, REST, gRPC, OPC-UA,
LoRaWAN, BLE Mesh, and V2X (Vehicle-to-Everything).
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Awaitable

import structlog

log = structlog.get_logger("brainiac.nexus_sync")


class Protocol(str, Enum):
    MQTT = "MQTT"
    WEBSOCKET = "WebSocket"
    REST = "REST"
    GRPC = "gRPC"
    OPC_UA = "OPC-UA"
    MODBUS = "Modbus"
    COAP = "CoAP"
    AMQP = "AMQP"
    LORAWAN = "LoRaWAN"
    BLE_MESH = "BLE_Mesh"
    V2X = "V2X"


class DeviceType(str, Enum):
    IOT_SENSOR = "iot_sensor"
    VEHICLE = "vehicle"
    DRONE = "drone"
    INDUSTRIAL_PLC = "industrial_plc"
    SMART_CITY_NODE = "smart_city_node"
    MEDICAL_DEVICE = "medical_device"
    WEATHER_STATION = "weather_station"
    SATELLITE_GROUND = "satellite_ground"
    ROBOT = "robot"
    WEARABLE = "wearable"
    MESH_NODE = "mesh_node"
    V2X_RSU = "v2x_rsu"          # Roadside Unit
    V2X_OBU = "v2x_obu"          # On-Board Unit


@dataclass
class Device:
    device_id: str
    device_type: DeviceType
    protocol: Protocol
    endpoint: str
    name: str = ""
    connected: bool = False
    last_seen: float = 0.0
    metadata: dict = field(default_factory=dict)
    capabilities: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "device_id": self.device_id,
            "type": self.device_type.value,
            "protocol": self.protocol.value,
            "endpoint": self.endpoint,
            "name": self.name,
            "connected": self.connected,
            "last_seen": self.last_seen,
            "capabilities": self.capabilities,
        }


@dataclass
class Message:
    msg_id: str
    device_id: str
    topic: str
    payload: dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    qos: int = 1                  # 0=fire-and-forget, 1=at-least-once, 2=exactly-once


class NexusSync:
    """
    Universal integration hub for BRAINIAC.

    Manages connections to 100,000+ concurrent devices across all protocols.
    Provides unified publish/subscribe, command dispatch, and device registry.
    """

    MAX_CONNECTIONS = 100_000

    def __init__(self) -> None:
        self._devices: dict[str, Device] = {}
        self._subscriptions: dict[str, list[Callable]] = {}   # topic → handlers
        self._message_log: list[Message] = []
        self._message_count = 0
        log.info("nexus_sync.init")

    # ── Device Registry ───────────────────────────────────────────────────────

    def register_device(
        self,
        device_id: str,
        device_type: DeviceType,
        protocol: Protocol,
        endpoint: str,
        name: str = "",
        capabilities: list[str] | None = None,
        metadata: dict | None = None,
    ) -> Device:
        """Register a device with NEXUS-SYNC."""
        if len(self._devices) >= self.MAX_CONNECTIONS:
            raise RuntimeError(f"Max device limit reached: {self.MAX_CONNECTIONS}")

        device = Device(
            device_id=device_id,
            device_type=device_type,
            protocol=protocol,
            endpoint=endpoint,
            name=name or device_id,
            capabilities=capabilities or [],
            metadata=metadata or {},
        )
        self._devices[device_id] = device
        log.info("nexus_sync.device_registered", id=device_id, type=device_type.value)
        return device

    async def connect_device(self, device_id: str) -> bool:
        """Establish connection to a registered device."""
        device = self._devices.get(device_id)
        if not device:
            raise KeyError(f"Device {device_id!r} not registered")

        # In production: open actual MQTT / WebSocket / gRPC connection
        await asyncio.sleep(0.01)          # simulate handshake
        device.connected = True
        device.last_seen = time.time()
        log.info("nexus_sync.device_connected", id=device_id, protocol=device.protocol.value)
        return True

    async def disconnect_device(self, device_id: str) -> bool:
        device = self._devices.get(device_id)
        if device:
            device.connected = False
            log.info("nexus_sync.device_disconnected", id=device_id)
            return True
        return False

    def get_device(self, device_id: str) -> Device | None:
        return self._devices.get(device_id)

    def list_devices(
        self,
        device_type: DeviceType | None = None,
        connected_only: bool = False,
    ) -> list[Device]:
        devices = list(self._devices.values())
        if device_type:
            devices = [d for d in devices if d.device_type == device_type]
        if connected_only:
            devices = [d for d in devices if d.connected]
        return devices

    # ── Pub/Sub ───────────────────────────────────────────────────────────────

    def subscribe(self, topic: str, handler: Callable[[Message], Awaitable[None]]) -> None:
        """Subscribe to a topic with an async handler."""
        self._subscriptions.setdefault(topic, []).append(handler)
        log.debug("nexus_sync.subscribe", topic=topic)

    async def publish(
        self,
        device_id: str,
        topic: str,
        payload: dict[str, Any],
        qos: int = 1,
    ) -> Message:
        """Publish a message and route to subscribers."""
        msg = Message(
            msg_id=str(uuid.uuid4()),
            device_id=device_id,
            topic=topic,
            payload=payload,
            qos=qos,
        )
        self._message_log.append(msg)
        self._message_count += 1

        # Update device last_seen
        if device_id in self._devices:
            self._devices[device_id].last_seen = time.time()

        # Route to subscribers (exact match + wildcard '#')
        handlers = (
            self._subscriptions.get(topic, []) +
            self._subscriptions.get("#", [])
        )
        if handlers:
            # Support both sync and async handlers
            coros = []
            for h in handlers:
                try:
                    result = h(msg)
                    if asyncio.iscoroutine(result):
                        coros.append(result)
                except Exception as exc:
                    log.error("nexus_sync.handler_error", error=str(exc))
            if coros:
                await asyncio.gather(*coros, return_exceptions=True)

        log.debug("nexus_sync.publish", topic=topic, device=device_id, handlers=len(handlers))
        return msg

    # ── Command Dispatch ──────────────────────────────────────────────────────

    async def command(
        self,
        device_id: str,
        command: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send a command to a device and await response."""
        device = self._devices.get(device_id)
        if not device:
            return {"error": f"device {device_id!r} not found"}
        if not device.connected:
            return {"error": f"device {device_id!r} not connected"}

        # In production: send via device's native protocol
        await asyncio.sleep(0.005)         # simulate round-trip
        response = {
            "device_id": device_id,
            "command": command,
            "params": params,
            "status": "OK",
            "timestamp": time.time(),
        }
        log.info("nexus_sync.command", device=device_id, cmd=command)
        return response

    # ── Mesh Networking (LoRaWAN / BLE) ─────────────────────────────────────

    async def broadcast_mesh(
        self,
        payload: dict[str, Any],
        protocol: Protocol = Protocol.LORAWAN,
        ttl: int = 3,
    ) -> dict[str, Any]:
        """
        Broadcast a message to all connected mesh nodes.

        Used for off-grid P2P navigation data sharing when cellular is unavailable.
        TTL controls hop count for multi-hop mesh relay.
        """
        mesh_devices = [
            d for d in self._devices.values()
            if d.connected and d.protocol in (Protocol.LORAWAN, Protocol.BLE_MESH)
        ]
        delivered = []
        for device in mesh_devices:
            msg = await self.publish(
                device.device_id, "mesh/broadcast",
                {**payload, "ttl": ttl, "mesh_protocol": protocol.value},
            )
            delivered.append(device.device_id)

        log.info("nexus_sync.mesh_broadcast", nodes=len(delivered), protocol=protocol.value)
        return {
            "protocol": protocol.value,
            "nodes_reached": len(delivered),
            "device_ids": delivered,
            "ttl": ttl,
        }

    def mesh_topology(self) -> dict[str, Any]:
        """Return the current mesh network topology."""
        mesh_nodes = [
            d for d in self._devices.values()
            if d.protocol in (Protocol.LORAWAN, Protocol.BLE_MESH)
        ]
        return {
            "total_nodes": len(mesh_nodes),
            "connected_nodes": sum(1 for n in mesh_nodes if n.connected),
            "protocols": list({n.protocol.value for n in mesh_nodes}),
            "nodes": [
                {
                    "device_id": n.device_id,
                    "protocol": n.protocol.value,
                    "connected": n.connected,
                    "last_seen": n.last_seen,
                }
                for n in mesh_nodes
            ],
        }

    # ── V2X (Vehicle-to-Everything) ──────────────────────────────────────────

    async def v2x_signal(
        self,
        signal_type: str,
        data: dict[str, Any],
        source_id: str = "gane-node",
    ) -> dict[str, Any]:
        """
        Send a V2X message to roadside units and nearby vehicles.

        signal_type: V2I (vehicle-to-infrastructure), V2V (vehicle-to-vehicle),
                     V2P (vehicle-to-pedestrian), V2N (vehicle-to-network)
        """
        v2x_devices = [
            d for d in self._devices.values()
            if d.connected and d.protocol == Protocol.V2X
        ]
        delivered = []
        for device in v2x_devices:
            msg = await self.publish(
                device.device_id, f"v2x/{signal_type.lower()}",
                {"signal_type": signal_type, "source": source_id, **data},
            )
            delivered.append(device.device_id)

        log.info("nexus_sync.v2x_signal", type=signal_type, targets=len(delivered))
        return {
            "signal_type": signal_type,
            "targets_reached": len(delivered),
            "device_ids": delivered,
            "timestamp": time.time(),
        }

    async def v2x_traffic_light_request(
        self,
        intersection_id: str,
        priority: str = "normal",
        reason: str = "",
    ) -> dict[str, Any]:
        """
        Request traffic light priority at a smart intersection (V2I).

        priority: normal | emergency | preemption
        Used by Life Corridors to clear routes for emergency vehicles.
        """
        rsu_devices = [
            d for d in self._devices.values()
            if d.connected and d.device_type == DeviceType.V2X_RSU
        ]
        result = None
        for rsu in rsu_devices:
            result = await self.command(rsu.device_id, "traffic_light_priority", {
                "intersection_id": intersection_id,
                "priority": priority,
                "reason": reason,
            })
            if result.get("status") == "OK":
                break

        return result or {
            "status": "NO_RSU",
            "intersection_id": intersection_id,
            "message": "No connected V2X RSU found",
        }

    # ── Diagnostics ───────────────────────────────────────────────────────────

    def diagnostics(self) -> dict[str, Any]:
        connected = sum(1 for d in self._devices.values() if d.connected)
        type_counts = {}
        for d in self._devices.values():
            type_counts[d.device_type.value] = type_counts.get(d.device_type.value, 0) + 1
        mesh_nodes = sum(
            1 for d in self._devices.values()
            if d.protocol in (Protocol.LORAWAN, Protocol.BLE_MESH)
        )
        v2x_nodes = sum(
            1 for d in self._devices.values()
            if d.protocol == Protocol.V2X
        )
        return {
            "status": "ONLINE",
            "navigation_role": "vehicle_iot_bus",
            "capabilities": [
                "drone_dispatch", "vehicle_integration", "sensor_ingest",
                "v2x_messaging", "lorawan_mesh", "ble_mesh", "traffic_light_priority",
            ],
            "registered_devices": len(self._devices),
            "connected_devices": connected,
            "device_types": type_counts,
            "mesh_nodes": mesh_nodes,
            "v2x_nodes": v2x_nodes,
            "total_messages": self._message_count,
            "subscriptions": {t: len(h) for t, h in self._subscriptions.items()},
            "max_connections": self.MAX_CONNECTIONS,
        }
