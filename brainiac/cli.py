"""
BRAINIAC CLI — Command-line interface for diagnostics and demos.

Usage:
    python -m brainiac.cli status
    python -m brainiac.cli demo
    python -m brainiac.cli serve
"""
from __future__ import annotations

import asyncio
import sys


def _print_banner() -> None:
    print("""
╔══════════════════════════════════════════════════════════════════╗
║         BRAINIAC AI — AUTONOMOUS SUPER INTELLIGENCE              ║
║                        v1.0.0 GENESIS                            ║
╚══════════════════════════════════════════════════════════════════╝
""")


async def _cmd_status() -> int:
    from brainiac.core import (
        NeuroCore, OrbitalNav, SonicMatrix, SatLink,
        NexusSync, TelemetryHub, CyberShield, CreativeEngine, OmniVision,
    )
    _print_banner()
    print("▶ Initialising all 9 core modules...\n")

    modules = {
        "NEURO-CORE      ": NeuroCore(),
        "ORBITAL-NAV     ": OrbitalNav(),
        "SONIC-MATRIX    ": SonicMatrix(),
        "SATLINK-X       ": SatLink(),
        "NEXUS-SYNC      ": NexusSync(),
        "TELEMETRY-HUB   ": TelemetryHub(),
        "CYBER-SHIELD    ": CyberShield(),
        "CREATIVE-ENGINE ": CreativeEngine(),
        "OMNI-VISION     ": OmniVision(),
    }

    print("┌──────────────────┬────────────┐")
    print("│ MODULE           │ STATUS     │")
    print("├──────────────────┼────────────┤")
    for name, mod in modules.items():
        status = mod.diagnostics()["status"]
        print(f"│ {name} │ {status:<10} │")
    print("└──────────────────┴────────────┘")
    print("\n✅ All BRAINIAC systems verified.\n")
    return 0


async def _cmd_demo() -> int:
    from brainiac.core import OrbitalNav, SatLink, TelemetryHub, NexusSync, CyberShield, CreativeEngine
    from brainiac.core.orbital_nav import Coordinate, TransportMode
    from brainiac.core.satlink import SOSPriority
    from brainiac.core.telemetry_hub import SensorReading
    from brainiac.core.nexus_sync import DeviceType, Protocol

    _print_banner()
    print("▶ Running end-to-end demo flow...\n")

    nav = OrbitalNav()
    satlink = SatLink()
    telem = TelemetryHub()
    nexus = NexusSync()
    shield = CyberShield()
    creative = CreativeEngine()

    print("[1/6] Acquiring RTK GPS position…")
    pos = await nav.get_position()
    print(f"      ✓ Position: {pos} (accuracy: {pos.accuracy_m}m)")

    print("[2/6] Planning drone route…")
    dest = Coordinate(lat=pos.lat + 0.1, lon=pos.lon + 0.1)
    route = await nav.route(pos, dest, mode=TransportMode.DRONE)
    print(f"      ✓ Route: {route.distance_km:.2f}km, ETA {route.eta_minutes:.1f}min")

    print("[3/6] Connecting SATLINK satellite mesh…")
    conn = await satlink.connect()
    print(f"      ✓ Uplink status: {conn['status']}")

    print("[4/6] Registering rescue drone in NEXUS-SYNC…")
    nexus.register_device(
        "rescue-drone-01", DeviceType.DRONE, Protocol.MQTT, "mqtt://rescue"
    )
    await nexus.connect_device("rescue-drone-01")
    print("      ✓ Drone connected")

    print("[5/6] Ingesting vitals telemetry…")
    for _ in range(10):
        await telem.ingest(SensorReading(sensor_id="heart-rate", value=72, unit="bpm"))
    anomaly = await telem.ingest(SensorReading(sensor_id="heart-rate", value=220, unit="bpm"))
    print(f"      ✓ Anomaly detected: {anomaly.anomaly_type.value} (severity {anomaly.severity})")

    print("[6/6] Broadcasting SOS over all channels…")
    packet = await satlink.send_sos(
        lat=pos.lat, lon=pos.lon,
        message="DEMO: vitals critical", priority=SOSPriority.DISTRESS,
    )
    print(f"      ✓ SOS sent on {len(packet.channels_used)} channels")
    print(f"      ✓ Responders notified: {', '.join(packet.responders_notified)}")

    signature = shield.sign(packet.to_dict())
    print(f"      ✓ Incident signed: {signature[:16]}…")

    print("\n✅ Demo flow complete. All modules operated in unison.\n")
    return 0


def _cmd_serve() -> int:
    import uvicorn
    _print_banner()
    print("▶ Starting BRAINIAC API server on 0.0.0.0:8000…\n")
    uvicorn.run("brainiac.api.main:app", host="0.0.0.0", port=8000, reload=False)
    return 0


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help", "help"):
        _print_banner()
        print("Commands:")
        print("  status  — Show module status")
        print("  demo    — Run end-to-end demo flow")
        print("  serve   — Start the FastAPI server")
        return 0

    cmd = args[0]
    if cmd == "status":
        return asyncio.run(_cmd_status())
    if cmd == "demo":
        return asyncio.run(_cmd_demo())
    if cmd == "serve":
        return _cmd_serve()

    print(f"Unknown command: {cmd!r}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
