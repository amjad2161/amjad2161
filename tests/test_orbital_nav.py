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


# ── Advanced Navigation Features ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_two_opt_refinement_does_not_worsen():
    nav = OrbitalNav()
    origin = Coordinate(lat=32.0, lon=34.0)
    stops = [
        Coordinate(lat=32.5, lon=34.5),
        Coordinate(lat=32.1, lon=34.1),
        Coordinate(lat=32.9, lon=34.9),
        Coordinate(lat=32.3, lon=34.3),
    ]
    nn_order  = OrbitalNav._nearest_neighbour_order(origin, stops)
    nn_dist   = OrbitalNav._route_total_distance(origin, nn_order)
    opt_order = OrbitalNav._two_opt_refine(origin, nn_order)
    opt_dist  = OrbitalNav._route_total_distance(origin, opt_order)
    assert opt_dist <= nn_dist + 1e-6


def test_route_clear_returns_no_conflicts_when_outside_zones():
    nav = OrbitalNav()
    route = Route(
        origin=Coordinate(lat=32.0, lon=34.0),
        destination=Coordinate(lat=33.0, lon=35.0),
        waypoints=[],
        total_distance_m=1000,
        total_duration_s=60,
        mode=TransportMode.DRIVE,
        precision=PrecisionMode.RTK,
        geometry=[Coordinate(lat=32.0, lon=34.0), Coordinate(lat=33.0, lon=35.0)],
    )
    no_fly = [(Coordinate(lat=10.0, lon=10.0), 1000.0)]
    is_clear, conflicts = nav.is_route_clear(route, no_fly)
    assert is_clear is True
    assert conflicts == []


def test_route_blocked_by_no_fly_zone():
    nav = OrbitalNav()
    route = Route(
        origin=Coordinate(lat=32.0, lon=34.0),
        destination=Coordinate(lat=33.0, lon=35.0),
        waypoints=[],
        total_distance_m=1000,
        total_duration_s=60,
        mode=TransportMode.DRONE,
        precision=PrecisionMode.RTK,
        geometry=[
            Coordinate(lat=32.0, lon=34.0),
            Coordinate(lat=32.5, lon=34.5),
            Coordinate(lat=33.0, lon=35.0),
        ],
    )
    no_fly = [(Coordinate(lat=32.5, lon=34.5), 5000.0)]
    is_clear, conflicts = nav.is_route_clear(route, no_fly)
    assert is_clear is False
    assert conflicts == [0]


def test_eta_adjustment_traffic_only():
    nav = OrbitalNav()
    base = 600.0   # 10 minutes
    assert nav.adjust_eta_for_conditions(base, traffic_factor=1.5) == pytest.approx(900.0)


def test_eta_adjustment_combined():
    nav = OrbitalNav()
    base = 600.0
    adjusted = nav.adjust_eta_for_conditions(base, traffic_factor=1.3, weather_factor=1.4)
    assert adjusted == pytest.approx(600.0 * 1.3 * 1.4)


def test_eta_adjustment_clamps_negative_factors():
    nav = OrbitalNav()
    base = 600.0
    adjusted = nav.adjust_eta_for_conditions(base, traffic_factor=0.0, weather_factor=-1.0)
    assert adjusted > 0


# ── Polygon No-Fly Zones ────────────────────────────────────────────────────

def test_route_clear_poly_outside():
    nav = OrbitalNav()
    route = Route(
        origin=Coordinate(lat=32.0, lon=34.0),
        destination=Coordinate(lat=33.0, lon=35.0),
        waypoints=[],
        total_distance_m=1000,
        total_duration_s=60,
        mode=TransportMode.DRIVE,
        precision=PrecisionMode.RTK,
        geometry=[Coordinate(lat=32.0, lon=34.0), Coordinate(lat=33.0, lon=35.0)],
    )
    polygon = [
        Coordinate(lat=10.0, lon=10.0),
        Coordinate(lat=10.0, lon=11.0),
        Coordinate(lat=11.0, lon=11.0),
        Coordinate(lat=11.0, lon=10.0),
    ]
    is_clear, conflicts = nav.is_route_clear_poly(route, [polygon])
    assert is_clear is True
    assert conflicts == []


def test_route_blocked_by_poly_zone():
    nav = OrbitalNav()
    route = Route(
        origin=Coordinate(lat=32.0, lon=34.0),
        destination=Coordinate(lat=33.0, lon=35.0),
        waypoints=[],
        total_distance_m=1000,
        total_duration_s=60,
        mode=TransportMode.DRONE,
        precision=PrecisionMode.RTK,
        geometry=[
            Coordinate(lat=32.0, lon=34.0),
            Coordinate(lat=32.5, lon=34.5),
            Coordinate(lat=33.0, lon=35.0),
        ],
    )
    polygon = [
        Coordinate(lat=32.3, lon=34.3),
        Coordinate(lat=32.3, lon=34.7),
        Coordinate(lat=32.7, lon=34.7),
        Coordinate(lat=32.7, lon=34.3),
    ]
    is_clear, conflicts = nav.is_route_clear_poly(route, [polygon])
    assert is_clear is False
    assert conflicts == [0]


# ── Geometry Interpolation ───────────────────────────────────────────────────

def test_interpolate_short_segment_unchanged():
    """Segments shorter than max_gap should not gain extra points."""
    a = Coordinate(lat=32.0, lon=34.0)
    b = Coordinate(lat=32.001, lon=34.001)
    result = OrbitalNav.interpolate_geometry([a, b], max_gap_m=50_000)
    assert len(result) == 2


def test_interpolate_long_segment_densified():
    """A ~157km segment with max_gap=50km should produce intermediate points."""
    a = Coordinate(lat=32.0, lon=34.0)
    b = Coordinate(lat=33.0, lon=35.0)
    result = OrbitalNav.interpolate_geometry([a, b], max_gap_m=50_000)
    assert len(result) >= 4
    assert result[0].lat == pytest.approx(a.lat)
    assert result[-1].lat == pytest.approx(b.lat)


def test_interpolate_empty_and_single():
    assert OrbitalNav.interpolate_geometry([]) == []
    pt = Coordinate(lat=32.0, lon=34.0)
    result = OrbitalNav.interpolate_geometry([pt])
    assert len(result) == 1


# ── Geofence Polygon ────────────────────────────────────────────────────────

def test_geofence_polygon_inside():
    nav = OrbitalNav()
    polygon = [
        Coordinate(lat=32.0, lon=34.0),
        Coordinate(lat=32.0, lon=35.0),
        Coordinate(lat=33.0, lon=35.0),
        Coordinate(lat=33.0, lon=34.0),
    ]
    point = Coordinate(lat=32.5, lon=34.5)
    assert nav.geofence_polygon(point, polygon) is True


def test_geofence_polygon_outside():
    nav = OrbitalNav()
    polygon = [
        Coordinate(lat=32.0, lon=34.0),
        Coordinate(lat=32.0, lon=35.0),
        Coordinate(lat=33.0, lon=35.0),
        Coordinate(lat=33.0, lon=34.0),
    ]
    point = Coordinate(lat=31.0, lon=33.0)
    assert nav.geofence_polygon(point, polygon) is False


def test_geofence_polygon_degenerate():
    nav = OrbitalNav()
    assert nav.geofence_polygon(Coordinate(lat=0, lon=0), []) is False
    assert nav.geofence_polygon(
        Coordinate(lat=0, lon=0),
        [Coordinate(lat=1, lon=1), Coordinate(lat=2, lon=2)],
    ) is False


# ── ETA Estimate (fast path) ────────────────────────────────────────────────

def test_estimate_eta_returns_correct_keys():
    nav = OrbitalNav()
    result = nav.estimate_eta(
        Coordinate(lat=32.0, lon=34.0),
        Coordinate(lat=33.0, lon=35.0),
        mode=TransportMode.DRIVE,
    )
    assert "distance_m" in result
    assert "distance_km" in result
    assert "duration_s" in result
    assert "eta_minutes" in result
    assert "speed_kmh" in result
    assert result["distance_m"] > 0
    assert result["duration_s"] > 0
