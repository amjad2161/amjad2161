import pytest

from brainiac.core.orbital_nav import Coordinate, OrbitalNav, PrecisionMode, Route, TransportMode, Waypoint


@pytest.fixture
def nav():
    return OrbitalNav(precision=PrecisionMode.RTK)


def _sample_route():
    origin = Coordinate(lat=32.0, lon=34.0)
    mid = Coordinate(lat=32.1, lon=34.1)
    dest = Coordinate(lat=32.2, lon=34.2)
    return Route(
        origin=origin,
        destination=dest,
        waypoints=[Waypoint(origin), Waypoint(mid), Waypoint(dest)],
        total_distance_m=10_000,
        total_duration_s=600,
        mode=TransportMode.DRIVE,
        precision=PrecisionMode.RTK,
        geometry=[origin, mid, dest],
    )


def test_build_turn_by_turn_languages(nav):
    route = _sample_route()
    en = nav.build_turn_by_turn(route, "en")
    he = nav.build_turn_by_turn(route, "he")
    ar = nav.build_turn_by_turn(route, "ar")
    assert any("Head" in x for x in en)
    assert any("התחל" in x for x in he)
    assert any("ابدأ" in x for x in ar)


def test_geofence_polygon_circle(nav):
    square = [
        Coordinate(0, 0),
        Coordinate(0, 1),
        Coordinate(1, 1),
        Coordinate(1, 0),
    ]
    assert nav.geofence_polygon(Coordinate(0.5, 0.5), square)
    assert not nav.geofence_polygon(Coordinate(2, 2), square)
    center = Coordinate(0, 0)
    assert nav.geofence_circle(Coordinate(0, 0), center, radius_m=1)
    assert not nav.geofence_circle(Coordinate(1, 1), center, radius_m=10)


@pytest.mark.asyncio
async def test_route_multi_stop_two_opt(nav):
    origin = Coordinate(32.0, 34.0)
    stops = [Coordinate(32.2, 34.2), Coordinate(32.1, 34.1), Coordinate(32.3, 34.3)]
    route = await nav.route_multi_stop(origin, stops)
    assert route.total_distance_m > 0
    assert len(route.geometry) == 4


def test_route_clear_checks(nav):
    route = _sample_route()
    blocked = [Coordinate(35.0, 35.0)]
    assert nav.is_route_clear(route, blocked)
    assert not nav.is_route_clear(route, [Coordinate(32.1, 34.1)], radius_m=500)
    polygon = [[Coordinate(31.9, 33.9), Coordinate(31.9, 34.2), Coordinate(32.2, 34.2), Coordinate(32.2, 33.9)]]
    assert not nav.is_route_clear_poly(route, polygon)
