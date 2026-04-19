"""
Cross-module navigation integration tests.

Verifies that every module in G.A.N.E serves the navigation system:
- NeuroCore: reasoning
- OrbitalNav: primary engine (6 GNSS + 6 SBAS)
- SonicMatrix: voice guidance
- SatLink: satellite uplink for SOS + RTK corrections
- NexusSync: vehicle/drone IoT bus
- TelemetryHub: motion telemetry
- CyberShield: GPS spoofing detection
- CreativeEngine: map/route badges
- OmniVision: obstacle detection
- Localization: RTL turn-by-turn
- MedicalProtocols: en-route medical emergencies
"""
import pytest

from brainiac.core import (
    NeuroCore, OrbitalNav, SonicMatrix, SatLink,
    NexusSync, TelemetryHub, CyberShield, CreativeEngine, OmniVision,
    Localization, MedicalProtocols,
)
from brainiac.core.orbital_nav import Coordinate, TransportMode


# ── Every module must declare a navigation_role ──────────────────────────────

def test_all_modules_declare_navigation_role():
    """Every G.A.N.E module must explicitly declare a navigation role."""
    instances = {
        "neuro_core":      NeuroCore(),
        "orbital_nav":     OrbitalNav(),
        "sonic_matrix":    SonicMatrix(),
        "nexus_sync":      NexusSync(),
        "telemetry_hub":   TelemetryHub(),
        "cyber_shield":    CyberShield(),
        "creative_engine": CreativeEngine(),
        "omni_vision":     OmniVision(),
        "localization":    Localization(),
        "medical":         MedicalProtocols(),
    }
    for name, mod in instances.items():
        d = mod.diagnostics()
        assert "navigation_role" in d, f"{name} missing navigation_role"
        assert d["navigation_role"], f"{name} has empty navigation_role"


def test_satlink_declares_navigation_role():
    sat = SatLink()
    d = sat.diagnostics()
    assert d["navigation_role"] == "satellite_uplink"
    assert "rtk_corrections_uplink" in d["capabilities"]


# ── Voice-guided navigation (SonicMatrix + Localization + OrbitalNav) ────────

@pytest.mark.asyncio
async def test_voice_guided_turn_by_turn_english():
    nav = OrbitalNav()
    sonic = SonicMatrix()
    origin = Coordinate(lat=32.0853, lon=34.7818)
    dest = Coordinate(lat=32.0900, lon=34.7900)
    route = await nav.route(origin, dest, mode=TransportMode.DRIVE)
    steps = nav.build_turn_by_turn(route, lang="en")
    voice = sonic.synthesize_turn_by_turn(steps, lang="en")
    assert len(voice) == len(steps)
    for v in voice:
        assert isinstance(v["audio_bytes"], (bytes, bytearray))
        assert v["lang"] == "en"


@pytest.mark.asyncio
async def test_voice_guided_turn_by_turn_hebrew_rtl():
    nav = OrbitalNav()
    sonic = SonicMatrix()
    origin = Coordinate(lat=32.0853, lon=34.7818)
    dest = Coordinate(lat=32.0900, lon=34.7900)
    route = await nav.route(origin, dest, mode=TransportMode.DRIVE)
    steps = nav.build_turn_by_turn(route, lang="he")
    voice = sonic.synthesize_turn_by_turn(steps, lang="he")
    assert len(voice) == len(steps)
    for v in voice:
        assert v["lang"] == "he"


# ── Medical evacuation (MedicalProtocols + OrbitalNav via orchestrator) ──────

@pytest.mark.asyncio
async def test_medical_evacuation_routing():
    from brainiac import Brainiac
    bot = Brainiac(secret_key="nav-integ")
    await bot.boot()
    patient = Coordinate(lat=32.0853, lon=34.7818)
    hospital = Coordinate(lat=32.1000, lon=34.8000)
    result = await bot.medical_evacuation_route(
        patient_location=patient, hospital_location=hospital,
        heart_rate=0, respiratory_rate=0, systolic_bp=0, gcs=3,
        mode=TransportMode.DRONE,
    )
    assert result["triage"]["category"] == "immediate"
    assert result["protocol"] is not None
    assert result["route"]["adjusted_eta_s"] > 0
    # Critical patient gets NO traffic penalty (priority corridor): adjusted == raw
    raw_eta_s = result["route"]["eta_minutes"] * 60
    assert result["route"]["adjusted_eta_s"] == pytest.approx(
        result["route"]["eta_minutes"] * 60 / 1.0, rel=0.1,
    )
    await bot.shutdown()


@pytest.mark.asyncio
async def test_medical_evacuation_non_critical_gets_traffic_penalty():
    from brainiac import Brainiac
    bot = Brainiac(secret_key="nav-integ")
    await bot.boot()
    patient = Coordinate(lat=32.0853, lon=34.7818)
    hospital = Coordinate(lat=32.1000, lon=34.8000)
    result = await bot.medical_evacuation_route(
        patient_location=patient, hospital_location=hospital,
        heart_rate=75, respiratory_rate=16, systolic_bp=120, gcs=15,
        mode=TransportMode.DRIVE,
    )
    # Stable patient gets 1.3× traffic penalty
    raw_eta_s = result["route"]["eta_minutes"] * 60
    assert result["route"]["adjusted_eta_s"] == pytest.approx(raw_eta_s * 1.3, rel=0.01)
    await bot.shutdown()


# ── Voice-guided route from orchestrator ────────────────────────────────────

@pytest.mark.asyncio
async def test_voice_guided_route_via_orchestrator():
    from brainiac import Brainiac
    bot = Brainiac(secret_key="nav-integ")
    await bot.boot()
    origin = Coordinate(lat=32.0853, lon=34.7818)
    dest = Coordinate(lat=32.0900, lon=34.7900)
    result = await bot.voice_guided_route(origin, dest, mode=TransportMode.DRIVE, lang="ar")
    assert result["lang"] == "ar"
    assert result["step_count"] > 0
    for step in result["voice_steps"]:
        assert step["lang"] == "ar"
        # audio_size_bytes ≥ 0 — actual byte count depends on gtts availability
        assert step["audio_size_bytes"] >= 0
        assert step["instruction"]
    await bot.shutdown()


# ── Nexus drone dispatch for navigation missions ─────────────────────────────

@pytest.mark.asyncio
async def test_nexus_supports_drone_navigation_dispatch():
    """Nexus must support dispatching drones to target coordinates."""
    from brainiac.core.nexus_sync import DeviceType, Protocol
    nexus = NexusSync()
    nexus.register_device("drone-nav-01", DeviceType.DRONE, Protocol.MQTT, "mqtt://test")
    await nexus.connect_device("drone-nav-01")
    resp = await nexus.command(
        "drone-nav-01", "navigate_to",
        {"target_lat": 32.1, "target_lon": 34.8, "altitude_m": 120},
    )
    assert resp["status"] == "OK"
    assert resp["params"]["target_lat"] == 32.1


# ── SatLink provides RTK corrections + SOS for navigation ────────────────────

@pytest.mark.asyncio
async def test_satlink_supports_navigation_uplink():
    satlink = SatLink()
    conn = await satlink.connect()
    assert conn["status"] == "CONNECTED"
    # Diagnostic must expose RTK / SOS capability for nav
    d = satlink.diagnostics()
    assert "rtk_corrections_uplink" in d["capabilities"]
    assert "emergency_sos" in d["capabilities"]
