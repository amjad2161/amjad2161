"""Tests for OmniVision SLAM / LiDAR processing."""
import pytest

from brainiac.core.omni_vision import OmniVision


@pytest.fixture
def vision():
    return OmniVision()


# ── LiDAR Point Cloud Processing ────────────────────────────────────────────

def test_process_empty_scan(vision):
    result = vision.process_lidar_scan([])
    assert result["point_count"] == 0
    assert result["obstacles"] == []


def test_process_lidar_scan_basic(vision):
    """A basic scan with ground + above-ground points produces obstacles."""
    points = [
        (1.0, 0.0, 0.0),    # ground
        (2.0, 0.0, 1.5),    # obstacle at 2m, 1.5m tall
        (3.0, 1.0, 0.8),    # obstacle diagonally
        (10.0, 5.0, 0.0),   # ground at distance
    ]
    result = vision.process_lidar_scan(points)
    assert result["point_count"] == 4
    assert result["occupancy_cells"] > 0
    assert result["total_obstacles"] == 2


def test_process_lidar_with_intensity(vision):
    points = [(1.0, 0.0, 1.0), (2.0, 0.0, 1.0)]
    intensity = [0.9, 0.5]
    result = vision.process_lidar_scan(points, intensity)
    assert result["obstacles"][0]["intensity"] == 0.9


def test_process_lidar_computes_distance(vision):
    """Distance metric is euclidean XY."""
    points = [(3.0, 4.0, 1.0)]   # sqrt(9+16)=5m
    result = vision.process_lidar_scan(points)
    assert result["obstacles"][0]["distance_m"] == 5.0


# ── SLAM Update ──────────────────────────────────────────────────────────────

def test_slam_update_empty(vision):
    result = vision.slam_update([], imu_heading_deg=45.0)
    assert result["map_updated"] is False
    assert result["position_delta"]["heading_deg"] == 45.0


def test_slam_update_with_points(vision):
    points = [(1.0, 0.0, 1.2), (2.0, 1.0, 1.5)]
    result = vision.slam_update(
        points, imu_heading_deg=90.0, odometry_dx=0.5, odometry_dy=0.3,
    )
    assert result["map_updated"] is True
    assert result["scan_summary"]["points"] == 2
    assert result["position_delta"]["dx"] == 0.5
    assert result["position_delta"]["dy"] == 0.3


# ── 3D Obstacle Detection ───────────────────────────────────────────────────

def test_obstacles_3d_filters_by_height(vision):
    points = [
        (1.0, 0.0, 0.1),    # too low (ground)
        (2.0, 0.0, 1.5),    # obstacle
        (3.0, 0.0, 0.05),   # too low
    ]
    obstacles = vision.detect_obstacles_3d(points, min_height_m=0.3)
    assert len(obstacles) == 1
    assert obstacles[0]["centroid"]["x"] == 2.0


def test_obstacles_3d_filters_by_range(vision):
    points = [
        (5.0, 0.0, 1.0),    # in range
        (100.0, 0.0, 1.0),  # out of 50m range
    ]
    obstacles = vision.detect_obstacles_3d(points, max_range_m=50.0)
    assert len(obstacles) == 1
    assert obstacles[0]["distance_m"] == 5.0


def test_obstacles_3d_risk_classification(vision):
    points = [
        (3.0, 0.0, 1.0),    # HIGH
        (10.0, 0.0, 1.0),   # MEDIUM
        (20.0, 0.0, 1.0),   # LOW
    ]
    obstacles = vision.detect_obstacles_3d(points)
    assert obstacles[0]["risk"] == "HIGH"
    assert obstacles[1]["risk"] == "MEDIUM"
    assert obstacles[2]["risk"] == "LOW"


def test_obstacles_3d_sorted_by_distance(vision):
    points = [(10.0, 0.0, 1.0), (2.0, 0.0, 1.0), (5.0, 0.0, 1.0)]
    obstacles = vision.detect_obstacles_3d(points)
    distances = [o["distance_m"] for o in obstacles]
    assert distances == sorted(distances)


# ── Diagnostics ──────────────────────────────────────────────────────────────

def test_vision_capabilities_include_slam(vision):
    caps = vision.diagnostics()["capabilities"]
    assert "lidar_processing" in caps
    assert "3d_obstacle_detection" in caps
    assert "occupancy_grid" in caps
    assert "slam_fusion" in caps
    assert "visual_slam" in caps
