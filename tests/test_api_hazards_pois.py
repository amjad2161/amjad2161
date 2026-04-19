"""API integration tests for hazards, POIs, and predictive routing endpoints."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch


@pytest.fixture
def client():
    with patch("brainiac.core.neuro_core.anthropic.AsyncAnthropic"):
        from brainiac.api.main import app
        return TestClient(app, raise_server_exceptions=False)


# ── Hazards API ──────────────────────────────────────────────────────────────

def test_report_hazard(client):
    r = client.post("/api/v1/nav/hazards", json={
        "lat": 32.08, "lon": 34.78, "type": "pothole",
        "description": "Large pothole", "severity": 7,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["hazard_id"]
    assert data["type"] == "pothole"
    assert data["severity"] == 7


def test_get_hazards(client):
    client.post("/api/v1/nav/hazards", json={
        "lat": 32.08, "lon": 34.78, "type": "accident",
    })
    r = client.get("/api/v1/nav/hazards")
    assert r.status_code == 200
    assert "hazards" in r.json()


def test_upvote_hazard(client):
    h = client.post("/api/v1/nav/hazards", json={
        "lat": 32.08, "lon": 34.78, "type": "police",
    }).json()
    r = client.post(f"/api/v1/nav/hazards/{h['hazard_id']}/upvote")
    assert r.status_code == 200
    assert r.json()["upvotes"] == 1


def test_upvote_nonexistent_404(client):
    r = client.post("/api/v1/nav/hazards/fake-id/upvote")
    assert r.status_code == 404


def test_dismiss_hazard(client):
    h = client.post("/api/v1/nav/hazards", json={
        "lat": 32.08, "lon": 34.78, "type": "flood",
    }).json()
    r = client.delete(f"/api/v1/nav/hazards/{h['hazard_id']}")
    assert r.status_code == 200
    assert r.json()["dismissed"] is True


def test_dismiss_nonexistent_404(client):
    r = client.delete("/api/v1/nav/hazards/fake-id")
    assert r.status_code == 404


# ── POI API ──────────────────────────────────────────────────────────────────

def test_add_poi(client):
    r = client.post("/api/v1/nav/pois", json={
        "lat": 32.08, "lon": 34.78,
        "name": "Test Hospital", "category": "hospital",
        "rating": 4.5,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "Test Hospital"
    assert data["category"] == "hospital"


def test_search_pois(client):
    client.post("/api/v1/nav/pois", json={
        "lat": 32.08, "lon": 34.78,
        "name": "Café Test", "category": "restaurant",
    })
    r = client.get("/api/v1/nav/pois", params={"query": "café"})
    assert r.status_code == 200
    assert "pois" in r.json()


def test_nearest_poi(client):
    client.post("/api/v1/nav/pois", json={
        "lat": 32.08, "lon": 34.78,
        "name": "Nearby Gas", "category": "gas_station",
    })
    r = client.get("/api/v1/nav/pois/nearest", params={
        "lat": 32.079, "lon": 34.779, "category": "gas_station",
    })
    assert r.status_code == 200
    assert r.json()["name"] == "Nearby Gas"


def test_nearest_poi_no_match(client):
    r = client.get("/api/v1/nav/pois/nearest", params={
        "lat": 32.0, "lon": 34.0, "category": "nonexistent",
    })
    assert r.status_code == 404


def test_poi_categories(client):
    r = client.get("/api/v1/nav/pois/categories")
    assert r.status_code == 200
    assert "categories" in r.json()
    assert len(r.json()["categories"]) > 0


# ── Predictive Routing API ───────────────────────────────────────────────────

def test_predict_intent_with_history(client):
    r = client.post("/api/v1/nav/predict-intent", json={
        "current_lat": 32.05, "current_lon": 34.75,
        "heading_deg": 45.0, "speed_ms": 15.0,
        "time_of_day": 8, "weekday": 1,
        "history": [
            {"dest_lat": 32.1, "dest_lon": 34.8, "name": "Office", "hour": 8, "weekday": 1},
        ],
    })
    assert r.status_code == 200
    data = r.json()
    assert data["edge_computed"] is True
    assert len(data["predictions"]) >= 1


def test_predict_intent_no_history(client):
    r = client.post("/api/v1/nav/predict-intent", json={
        "current_lat": 32.05, "current_lon": 34.75,
        "heading_deg": 0.0, "speed_ms": 10.0,
        "time_of_day": 8, "weekday": 1,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["edge_computed"] is True
