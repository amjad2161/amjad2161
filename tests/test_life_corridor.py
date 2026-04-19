"""Tests for OrbitalNav Life Corridors — emergency priority routing."""
import pytest

from brainiac.core.orbital_nav import OrbitalNav, Coordinate, TransportMode


@pytest.fixture
def nav():
    return OrbitalNav()


@pytest.mark.asyncio
async def test_life_corridor_emergency(nav):
    origin = Coordinate(lat=32.0853, lon=34.7818)
    dest = Coordinate(lat=32.1000, lon=34.8000)
    result = await nav.life_corridor(origin, dest, priority="emergency")

    assert result["corridor_type"] == "emergency"
    assert result["base_eta_s"] > 0
    assert result["corridor_eta_s"] < result["base_eta_s"]
    assert result["time_saved_s"] > 0
    assert result["v2x_broadcast_required"] is True


@pytest.mark.asyncio
async def test_life_corridor_preemption(nav):
    origin = Coordinate(lat=32.0853, lon=34.7818)
    dest = Coordinate(lat=32.1000, lon=34.8000)
    result = await nav.life_corridor(origin, dest, priority="preemption")

    assert result["corridor_type"] == "preemption"
    assert result["v2x_broadcast_required"] is True


@pytest.mark.asyncio
async def test_life_corridor_normal(nav):
    origin = Coordinate(lat=32.0853, lon=34.7818)
    dest = Coordinate(lat=32.1000, lon=34.8000)
    result = await nav.life_corridor(origin, dest, priority="normal")

    assert result["corridor_type"] == "normal"
    assert result["v2x_broadcast_required"] is False


@pytest.mark.asyncio
async def test_life_corridor_has_geometry(nav):
    origin = Coordinate(lat=32.0853, lon=34.7818)
    dest = Coordinate(lat=32.1000, lon=34.8000)
    result = await nav.life_corridor(origin, dest)
    assert "geometry" in result
    assert len(result["geometry"]) > 0
    for pt in result["geometry"]:
        assert "lat" in pt and "lon" in pt


@pytest.mark.asyncio
async def test_life_corridor_drone_mode(nav):
    origin = Coordinate(lat=32.0853, lon=34.7818)
    dest = Coordinate(lat=32.1000, lon=34.8000)
    result = await nav.life_corridor(origin, dest, priority="emergency", mode=TransportMode.DRONE)
    assert result["route"]["mode"] == "drone"
