"""Tests for ORBITAL-NAV module."""
import math
import pytest
import pytest_asyncio
from brainiac.core.orbital_nav import (
    Coordinate, OrbitalNav, TransportMode, PrecisionMode, Route
)


# ── Coordinate ────────────────────────────────────────────────────────────────

def test_coordinate_str():
    c = Coordinate(lat=32.0853, lon=34.7818)
    assert "32.085300" in str(c)
    assert "34.781800" in str(c)


def test_distance_same_point():
    c = Coordinate(lat=32.0, lon=34.0)
    assert c.distance_to(c) == pytest.approx(0.0, abs=1e-6)


def test_distance_known_pair():
    # Tel Aviv to Jerusalem ~55km
    tel_aviv   = Coordinate(lat=32.0853, lon=34.7818)
    jerusalem  = Coordinate(lat=31.7683, lon=35.2137)
    dist = tel_aviv.distance_to(jerusalem)
    assert 50_000 < dist < 60_000, f"Expected ~55km, got {dist:.0f}m"


def test_bearing_east():
    origin = Coordinate(lat=0.0, lon=0.0)
    east   = Coordinate(lat=0.0, lon=1.0)
    bearing = origin.bearing_to(east)
    assert bearing == pytest.approx(90.0, abs=1.0)


def test_bearing_north():
    origin = Coordinate(lat=0.0, lon=0.0)
    north  = Coordinate(lat=1.0, lon=0.0)
    bearing = origin.bearing_to(north)
    assert bearing == pytest.approx(0.0, abs=1.0)


# ── OrbitalNav ────────────────────────────────────────────────────────────────

@pytest.fixture
def nav():
    return OrbitalNav(precision=PrecisionMode.RTK)


@pytest.mark.asyncio
async def test_get_position(nav):
    pos = await nav.get_position()
    assert -90 <= pos.lat <= 90
    assert -180 <= pos.lon <= 180
    assert pos.accuracy_m == pytest.approx(0.02)     # RTK precision


@pytest.mark.asyncio
async def test_satellite_status(nav):
    statuses = await nav.get_satellite_status()
    assert len(statuses) == 5   # GPS, GLONASS, Galileo, BeiDou, QZSS
    for s in statuses:
        assert s.satellites_used > 0
        assert s.fix_type == "RTK_FIXED"


@pytest.mark.asyncio
async def test_drone_route(nav):
    origin = Coordinate(lat=32.0, lon=34.0)
    dest   = Coordinate(lat=33.0, lon=35.0)
    route  = await nav.route(origin, dest, mode=TransportMode.DRONE)
    assert route.total_distance_m > 0
    assert route.mode == TransportMode.DRONE
    assert route.total_duration_s > 0
    assert len(route.geometry) == 2


@pytest.mark.asyncio
async def test_fallback_route(nav, monkeypatch):
    """Offline fallback should always return a valid route."""
    async def bad_get(*args, **kwargs):
        raise Exception("network down")

    monkeypatch.setattr("httpx.AsyncClient.get", bad_get)
    origin = Coordinate(lat=32.0, lon=34.0)
    dest   = Coordinate(lat=33.0, lon=35.0)
    route  = await nav.route(origin, dest, mode=TransportMode.DRIVE)
    assert route.total_distance_m > 0
    assert "OFFLINE_MODE" in (route.hazards[0] if route.hazards else "")


def test_diagnostics(nav):
    d = nav.diagnostics()
    assert d["status"] == "ONLINE"
    assert d["precision_mode"] == "rtk"
    assert len(d["gnss_systems"]) == 5
