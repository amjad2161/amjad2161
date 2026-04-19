"""Tests for community hazard reporting (Waze DNA) and POI database (Google Maps DNA)."""
import time
import pytest
from brainiac.core.orbital_nav import OrbitalNav, Coordinate, TransportMode, Route


@pytest.fixture
def nav():
    return OrbitalNav()


# ── Hazard Reporting ──────────────────────────────────────────────────────────

class TestHazardReporting:

    def test_report_hazard(self, nav):
        h = nav.report_hazard(32.08, 34.78, "pothole", "Big pothole on road", severity=7)
        assert h["hazard_id"]
        assert h["type"] == "pothole"
        assert h["severity"] == 7
        assert h["active"] is True
        assert h["upvotes"] == 0

    def test_get_hazards_empty(self, nav):
        assert nav.get_hazards() == []

    def test_get_hazards_proximity(self, nav):
        nav.report_hazard(32.08, 34.78, "accident")
        nav.report_hazard(40.0, -74.0, "police")
        nearby = nav.get_hazards(lat=32.08, lon=34.78, radius_m=1000)
        assert len(nearby) == 1
        assert nearby[0]["type"] == "accident"

    def test_get_all_hazards(self, nav):
        nav.report_hazard(32.08, 34.78, "accident")
        nav.report_hazard(40.0, -74.0, "police")
        all_h = nav.get_hazards()
        assert len(all_h) == 2

    def test_upvote_hazard(self, nav):
        h = nav.report_hazard(32.08, 34.78, "construction")
        result = nav.upvote_hazard(h["hazard_id"])
        assert result["upvotes"] == 1
        result = nav.upvote_hazard(h["hazard_id"])
        assert result["upvotes"] == 2

    def test_upvote_nonexistent(self, nav):
        assert nav.upvote_hazard("fake-id") is None

    def test_dismiss_hazard(self, nav):
        h = nav.report_hazard(32.08, 34.78, "flood")
        assert nav.dismiss_hazard(h["hazard_id"]) is True
        active = nav.get_hazards(active_only=True)
        assert len(active) == 0

    def test_dismiss_nonexistent(self, nav):
        assert nav.dismiss_hazard("fake-id") is False

    def test_severity_clamping(self, nav):
        h1 = nav.report_hazard(32.0, 34.0, "pothole", severity=15)
        h2 = nav.report_hazard(32.0, 34.0, "pothole", severity=-5)
        assert h1["severity"] == 10
        assert h2["severity"] == 1

    def test_hazards_on_route(self, nav):
        nav.report_hazard(32.05, 34.05, "accident")
        nav.report_hazard(50.0, 10.0, "police")
        route = Route(
            origin=Coordinate(lat=32.0, lon=34.0),
            destination=Coordinate(lat=32.1, lon=34.1),
            waypoints=[],
            total_distance_m=15000,
            total_duration_s=600,
            mode=TransportMode.DRIVE,
            precision=nav.precision,
            geometry=[Coordinate(lat=32.05, lon=34.05)],
        )
        on_route = nav.hazards_on_route(route, buffer_m=500)
        assert len(on_route) == 1
        assert on_route[0]["type"] == "accident"

    def test_expired_hazards_excluded(self, nav):
        h = nav.report_hazard(32.0, 34.0, "object_on_road")
        h["timestamp"] = time.time() - 5 * 3600  # 5 hours ago
        assert len(nav.get_hazards()) == 0


# ── POI Database ──────────────────────────────────────────────────────────────

class TestPOIDatabase:

    def test_add_poi(self, nav):
        p = nav.add_poi(32.08, 34.78, "Ichilov Hospital", "hospital", rating=4.5)
        assert p["poi_id"]
        assert p["name"] == "Ichilov Hospital"
        assert p["category"] == "hospital"
        assert p["rating"] == 4.5

    def test_search_by_name(self, nav):
        nav.add_poi(32.08, 34.78, "Café Noir", "restaurant", rating=4.2)
        nav.add_poi(32.09, 34.79, "Pizza Palace", "restaurant", rating=3.8)
        results = nav.search_pois(query="café")
        assert len(results) == 1
        assert results[0]["name"] == "Café Noir"

    def test_search_by_category(self, nav):
        nav.add_poi(32.08, 34.78, "Gas Stop", "gas_station")
        nav.add_poi(32.09, 34.79, "Park Hayarkon", "park")
        results = nav.search_pois(category="park")
        assert len(results) == 1
        assert results[0]["category"] == "park"

    def test_search_by_proximity(self, nav):
        nav.add_poi(32.08, 34.78, "Near Place", "restaurant")
        nav.add_poi(40.0, -74.0, "Far Place", "restaurant")
        results = nav.search_pois(lat=32.08, lon=34.78, radius_m=1000)
        assert len(results) == 1
        assert results[0]["name"] == "Near Place"
        assert "distance_m" in results[0]

    def test_nearest_poi(self, nav):
        nav.add_poi(32.08, 34.78, "Hospital A", "hospital")
        nav.add_poi(32.10, 34.80, "Hospital B", "hospital")
        nearest = nav.nearest_poi(32.079, 34.779, "hospital")
        assert nearest["name"] == "Hospital A"
        assert "distance_m" in nearest

    def test_nearest_poi_no_match(self, nav):
        assert nav.nearest_poi(32.0, 34.0, "airport") is None

    def test_poi_categories_default(self, nav):
        cats = nav.poi_categories()
        assert "hospital" in cats
        assert "restaurant" in cats
        assert "gas_station" in cats

    def test_poi_categories_from_data(self, nav):
        nav.add_poi(32.0, 34.0, "X", "custom_category")
        cats = nav.poi_categories()
        assert "custom_category" in cats

    def test_rating_clamping(self, nav):
        p1 = nav.add_poi(32.0, 34.0, "X", "restaurant", rating=10.0)
        p2 = nav.add_poi(32.0, 34.0, "Y", "restaurant", rating=-2.0)
        assert p1["rating"] == 5.0
        assert p2["rating"] == 0.0

    def test_search_limit(self, nav):
        for i in range(30):
            nav.add_poi(32.0 + i * 0.001, 34.0, f"Place {i}", "restaurant")
        results = nav.search_pois(limit=10)
        assert len(results) == 10

    def test_search_sorted_by_distance(self, nav):
        nav.add_poi(32.10, 34.80, "Far", "restaurant", rating=5.0)
        nav.add_poi(32.08, 34.78, "Near", "restaurant", rating=1.0)
        results = nav.search_pois(lat=32.079, lon=34.779)
        assert results[0]["name"] == "Near"


# ── Predictive Routing ────────────────────────────────────────────────────────

class TestPredictiveRouting:

    def test_predict_with_history(self, nav):
        history = [
            {"dest_lat": 32.1, "dest_lon": 34.8, "name": "Office", "hour": 8, "weekday": 1},
            {"dest_lat": 32.0, "dest_lon": 34.7, "name": "Home", "hour": 18, "weekday": 1},
        ]
        result = nav.predict_route_intent(
            current_lat=32.05, current_lon=34.75,
            heading_deg=45.0, speed_ms=15.0,
            time_of_day=8, weekday=1,
            history=history,
        )
        assert result["edge_computed"] is True
        assert result["model"] == "gane_intent_v1"
        assert len(result["predictions"]) >= 1
        assert result["predictions"][0]["confidence"] > 0

    def test_predict_morning_commute_fallback(self, nav):
        result = nav.predict_route_intent(
            current_lat=32.05, current_lon=34.75,
            heading_deg=0.0, speed_ms=10.0,
            time_of_day=8, weekday=1,
        )
        assert len(result["predictions"]) >= 1
        assert result["predictions"][0]["reason"] == "morning_commute_pattern"

    def test_predict_evening_commute_fallback(self, nav):
        result = nav.predict_route_intent(
            current_lat=32.05, current_lon=34.75,
            heading_deg=180.0, speed_ms=10.0,
            time_of_day=17, weekday=3,
        )
        assert len(result["predictions"]) >= 1
        assert result["predictions"][0]["reason"] == "evening_commute_pattern"

    def test_predict_weekend_no_commute(self, nav):
        result = nav.predict_route_intent(
            current_lat=32.05, current_lon=34.75,
            heading_deg=0.0, speed_ms=5.0,
            time_of_day=10, weekday=6,
        )
        assert result["total_candidates"] == 0

    def test_predict_sorted_by_confidence(self, nav):
        history = [
            {"dest_lat": 32.1, "dest_lon": 34.8, "name": "A", "hour": 8, "weekday": 1},
            {"dest_lat": 32.2, "dest_lon": 34.9, "name": "B", "hour": 8, "weekday": 1},
            {"dest_lat": 32.3, "dest_lon": 35.0, "name": "C", "hour": 14, "weekday": 5},
        ]
        result = nav.predict_route_intent(
            current_lat=32.05, current_lon=34.75,
            heading_deg=45.0, speed_ms=15.0,
            time_of_day=8, weekday=1,
            history=history,
        )
        confs = [p["confidence"] for p in result["predictions"]]
        assert confs == sorted(confs, reverse=True)
