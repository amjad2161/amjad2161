"""Tests for ORBITAL-NAV module."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from brainiac.core.orbital_nav import Coordinate, OrbitalNav, PrecisionMode, TransportMode


def test_coordinate_str():
    c = Coordinate(lat=32.0853, lon=34.7818)
    assert "32.085300" in str(c)
    assert "34.781800" in str(c)


def test_distance_same_point():
    c = Coordinate(lat=32.0, lon=34.0)
    assert c.distance_to(c) == pytest.approx(0.0, abs=1e-6)


def test_distance_known_pair():
    tel_aviv = Coordinate(lat=32.0853, lon=34.7818)
    jerusalem = Coordinate(lat=31.7683, lon=35.2137)
    dist = tel_aviv.distance_to(jerusalem)
    assert 50_000 < dist < 60_000


def test_bearing_east():
    origin = Coordinate(lat=0.0, lon=0.0)
    east = Coordinate(lat=0.0, lon=1.0)
    bearing = origin.bearing_to(east)
    assert bearing == pytest.approx(90.0, abs=1.0)


def test_bearing_north():
    origin = Coordinate(lat=0.0, lon=0.0)
    north = Coordinate(lat=1.0, lon=0.0)
    bearing = origin.bearing_to(north)
    assert bearing == pytest.approx(0.0, abs=1.0)


@pytest.fixture
def nav():
    return OrbitalNav(precision=PrecisionMode.RTK)


@pytest.mark.asyncio
async def test_get_position(nav):
    pos = await nav.get_position()
    assert -90 <= pos.lat <= 90
    assert -180 <= pos.lon <= 180
    assert pos.accuracy_m == pytest.approx(0.02)


@pytest.mark.asyncio
async def test_satellite_status(nav):
    statuses = await nav.get_satellite_status()
    assert len(statuses) == 5
    for status in statuses:
        assert status.satellites_used > 0
        assert status.fix_type == "RTK_FIXED"


@pytest.mark.asyncio
async def test_drone_route(nav):
    origin = Coordinate(lat=32.0, lon=34.0)
    dest = Coordinate(lat=33.0, lon=35.0)
    route = await nav.route(origin, dest, mode=TransportMode.DRONE)
    assert route.total_distance_m > 0
    assert route.mode == TransportMode.DRONE
    assert route.total_duration_s > 0
    assert len(route.geometry) == 2


@pytest.mark.asyncio
async def test_fallback_route(nav, monkeypatch):
    async def bad_get(*args, **kwargs):
        raise Exception("network down")

    monkeypatch.setattr("httpx.AsyncClient.get", bad_get)
    origin = Coordinate(lat=32.0, lon=34.0)
    dest = Coordinate(lat=33.0, lon=35.0)
    route = await nav.route(origin, dest, mode=TransportMode.DRIVE)
    assert route.total_distance_m > 0
    assert route.hazards
    assert "OFFLINE_MODE" in route.hazards[0]


@pytest.mark.asyncio
async def test_route_cache(nav, monkeypatch):
    monkeypatch.setattr(nav, "_ground_route", AsyncMock())
    nav._ground_route.return_value = nav._fallback_route(
        Coordinate(lat=32.0, lon=34.0),
        Coordinate(lat=32.2, lon=34.2),
        TransportMode.DRIVE,
    )

    origin = Coordinate(lat=32.0, lon=34.0)
    destination = Coordinate(lat=32.2, lon=34.2)

    await nav.route(origin, destination, mode=TransportMode.DRIVE)
    await nav.route(origin, destination, mode=TransportMode.DRIVE)

    stats = nav.get_cache_stats()
    assert stats["entries"] >= 1
    assert stats["hits"] >= 1


def test_diagnostics(nav):
    d = nav.diagnostics()
    assert d["status"] == "ONLINE"
    assert d["precision_mode"] == "rtk"
    assert len(d["gnss_systems"]) == 5
