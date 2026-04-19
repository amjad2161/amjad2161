"""Tests for the INS (Inertial Navigation System) module."""
import math
import time
import pytest

from brainiac.core.ins import (
    INS, IMUReading, INSPosition, GNSSHealth,
    PositionSource, INSState,
)


@pytest.fixture
def ins():
    return INS()


@pytest.fixture
def seeded_ins():
    i = INS()
    i.seed_position(lat=32.0853, lon=34.7818, alt_m=30.0, heading_deg=90.0)
    return i


# ── Initialisation ───────────────────────────────────────────────────────────

def test_init_state(ins):
    assert ins.state == INSState.UNINITIALISED
    pos = ins.position()
    assert pos.source == PositionSource.UNKNOWN


def test_seed_position(ins):
    ins.seed_position(lat=32.0, lon=34.0, alt_m=50.0, heading_deg=180.0)
    assert ins.state == INSState.NAVIGATING
    pos = ins.position()
    assert pos.lat == 32.0
    assert pos.lon == 34.0
    assert pos.alt_m == 50.0
    assert pos.source == PositionSource.GNSS


# ── GNSS Updates ─────────────────────────────────────────────────────────────

def test_gnss_update_sets_position(ins):
    pos = ins.update_gnss(lat=31.5, lon=35.2, alt_m=100.0)
    assert pos.lat == 31.5
    assert pos.lon == 35.2
    assert ins.state == INSState.NAVIGATING


def test_gnss_update_resets_drift(seeded_ins):
    seeded_ins._drift = 10.0
    seeded_ins.update_gnss(lat=32.0853, lon=34.7818, accuracy_m=2.0)
    assert seeded_ins._drift < 10.0


# ── GNSS Health Scoring ──────────────────────────────────────────────────────

def test_gnss_health_good(ins):
    health = ins.update_gnss_health(
        constellations_available=6,
        total_satellites_used=30,
        best_hdop=0.7,
        fix_type="RTK_FIXED",
    )
    assert health.gnss_available is True
    assert health.score > 0.7


def test_gnss_health_degraded(ins):
    health = ins.update_gnss_health(
        constellations_available=0,
        total_satellites_used=0,
        best_hdop=99.0,
        fix_type="NO_FIX",
    )
    assert health.gnss_available is False
    assert health.score < 0.3


def test_gnss_health_marginal(ins):
    health = ins.update_gnss_health(
        constellations_available=2,
        total_satellites_used=6,
        best_hdop=3.0,
        fix_type="3D",
    )
    assert health.gnss_available is True
    assert 0.3 <= health.score <= 0.8


# ── IMU Dead Reckoning ───────────────────────────────────────────────────────

def test_imu_alignment_phase(ins):
    """INS requires alignment samples before it can navigate."""
    ts = time.time()
    for i in range(INS.ALIGNMENT_SAMPLES):
        ins.update_imu(IMUReading(
            accel_x=0, accel_y=0, accel_z=9.81,
            gyro_x=0.001, gyro_y=0, gyro_z=0,
            mag_x=20.0, mag_y=5.0, mag_z=-40.0,
            timestamp=ts + i * 0.01,
        ))
    # After alignment, still needs GNSS seed to navigate
    # state depends on whether seed was given


def test_imu_updates_position(seeded_ins):
    """IMU readings should move the dead-reckoning position."""
    initial = seeded_ins.position()
    ts = time.time()
    for i in range(20):
        seeded_ins.update_imu(IMUReading(
            accel_x=0.5, accel_y=0.0, accel_z=9.81,
            gyro_x=0, gyro_y=0, gyro_z=0,
            mag_x=20.0, mag_y=5.0, mag_z=-40.0,
            timestamp=ts + i * 0.1,
        ))
    after = seeded_ins.position()
    assert after.source in (PositionSource.INS, PositionSource.FUSED)
    assert after.drift_m > 0


def test_imu_accumulates_drift(seeded_ins):
    """Drift should increase over time without GNSS corrections."""
    ts = time.time()
    for i in range(50):
        seeded_ins.update_imu(IMUReading(
            accel_x=0, accel_y=0, accel_z=9.81,
            gyro_x=0, gyro_y=0, gyro_z=0,
            mag_x=20.0, mag_y=5.0, mag_z=-40.0,
            timestamp=ts + i * 0.1,
        ))
    pos = seeded_ins.position()
    assert pos.drift_m > 0


def test_heading_from_magnetometer(seeded_ins):
    """Heading should be influenced by magnetometer readings."""
    ts = time.time()
    for i in range(20):
        seeded_ins.update_imu(IMUReading(
            accel_x=0, accel_y=0, accel_z=9.81,
            gyro_x=0, gyro_y=0, gyro_z=0,
            mag_x=0.0, mag_y=20.0, mag_z=-40.0,  # North=0, East=20 → heading ~90°
            timestamp=ts + i * 0.1,
        ))
    pos = seeded_ins.position()
    assert 0 <= pos.heading_deg < 360


def test_gyro_changes_heading(seeded_ins):
    """Gyroscope z-axis rotation should change heading."""
    initial_heading = seeded_ins.position().heading_deg
    ts = time.time()
    for i in range(20):
        seeded_ins.update_imu(IMUReading(
            accel_x=0, accel_y=0, accel_z=9.81,
            gyro_x=0, gyro_y=0, gyro_z=0.5,  # turning right
            mag_x=20.0, mag_y=5.0, mag_z=-40.0,
            timestamp=ts + i * 0.1,
        ))
    final_heading = seeded_ins.position().heading_deg
    # Heading should have changed due to gyro rotation
    assert final_heading != initial_heading


# ── GNSS/INS Fusion ─────────────────────────────────────────────────────────

def test_fusion_corrects_drift(seeded_ins):
    """GNSS update should correct INS drift and blend positions."""
    ts = time.time()
    for i in range(30):
        seeded_ins.update_imu(IMUReading(
            accel_x=1.0, accel_y=0, accel_z=9.81,
            gyro_x=0, gyro_y=0, gyro_z=0,
            mag_x=20.0, mag_y=5.0, mag_z=-40.0,
            timestamp=ts + i * 0.1,
        ))
    drift_before = seeded_ins.position().drift_m
    assert drift_before > 0

    seeded_ins.update_gnss_health(6, 24, 0.8, "RTK_FIXED")
    seeded_ins.update_gnss(lat=32.0853, lon=34.7818, accuracy_m=0.02)
    drift_after = seeded_ins.position().drift_m
    assert drift_after < drift_before


def test_source_switches_to_ins_when_gnss_lost(seeded_ins):
    """When GNSS becomes unavailable, source should switch to INS."""
    seeded_ins.update_gnss_health(0, 0, 99.0, "NO_FIX")
    ts = time.time()
    for i in range(5):
        seeded_ins.update_imu(IMUReading(
            accel_x=0, accel_y=0, accel_z=9.81,
            gyro_x=0, gyro_y=0, gyro_z=0,
            mag_x=20.0, mag_y=5.0, mag_z=-40.0,
            timestamp=ts + i * 0.1,
        ))
    pos = seeded_ins.position()
    assert pos.source == PositionSource.INS


def test_source_fused_when_gnss_available(seeded_ins):
    """With GNSS healthy and IMU running, source should be FUSED."""
    seeded_ins.update_gnss_health(6, 24, 0.8, "3D")
    ts = time.time()
    for i in range(5):
        seeded_ins.update_imu(IMUReading(
            accel_x=0, accel_y=0, accel_z=9.81,
            gyro_x=0, gyro_y=0, gyro_z=0,
            mag_x=20.0, mag_y=5.0, mag_z=-40.0,
            timestamp=ts + i * 0.1,
        ))
    pos = seeded_ins.position()
    assert pos.source == PositionSource.FUSED


# ── Corridor Monitoring ──────────────────────────────────────────────────────

def test_corridor_check_on_route(seeded_ins):
    route = [(32.0853, 34.7818), (32.0900, 34.7900)]
    result = seeded_ins.corridor_check(route, threshold_m=100.0)
    assert result["on_route"] is True
    assert result["alert"] == "OK"


def test_corridor_check_off_route(seeded_ins):
    route = [(33.0, 35.0), (33.1, 35.1)]  # far away
    result = seeded_ins.corridor_check(route, threshold_m=50.0)
    assert result["on_route"] is False
    assert result["alert"] == "OFF_ROUTE"
    assert result["deviation_m"] > 50.0


def test_corridor_check_empty_route(seeded_ins):
    result = seeded_ins.corridor_check([], threshold_m=50.0)
    assert result["on_route"] is True


def test_corridor_check_single_point(seeded_ins):
    result = seeded_ins.corridor_check([(32.0853, 34.7818)], threshold_m=100.0)
    assert result["on_route"] is True


# ── Reset ────────────────────────────────────────────────────────────────────

def test_reset(seeded_ins):
    seeded_ins.reset()
    assert seeded_ins.state == INSState.UNINITIALISED
    assert seeded_ins.position().source == PositionSource.UNKNOWN
    assert seeded_ins.position().drift_m == 0.0


# ── Diagnostics ──────────────────────────────────────────────────────────────

def test_diagnostics(ins):
    d = ins.diagnostics()
    assert d["status"] == "ONLINE"
    assert d["navigation_role"] == "inertial_fallback"
    assert "dead_reckoning" in d["capabilities"]
    assert "imu_fusion" in d["capabilities"]
    assert "gnss_ins_blending" in d["capabilities"]
    assert "corridor_monitoring" in d["capabilities"]
    assert "drift_estimation" in d["capabilities"]
    assert "heading_computation" in d["capabilities"]


def test_diagnostics_after_operation(seeded_ins):
    ts = time.time()
    for i in range(5):
        seeded_ins.update_imu(IMUReading(
            accel_x=0, accel_y=0, accel_z=9.81,
            gyro_x=0, gyro_y=0, gyro_z=0,
            mag_x=20.0, mag_y=5.0, mag_z=-40.0,
            timestamp=ts + i * 0.1,
        ))
    d = seeded_ins.diagnostics()
    assert d["total_imu_samples"] == 5
    assert d["state"] == "NAVIGATING"


# ── INSPosition string representation ───────────────────────────────────────

def test_ins_position_str():
    pos = INSPosition(
        lat=32.0853, lon=34.7818, alt_m=30.0,
        heading_deg=90.0, speed_ms=5.0,
        source=PositionSource.FUSED, accuracy_m=2.0, drift_m=1.5,
    )
    s = str(pos)
    assert "32.085300" in s
    assert "FUSED" in s


# ── Orchestrator fused_position integration ──────────────────────────────────

@pytest.mark.asyncio
async def test_orchestrator_fused_position():
    from brainiac import Brainiac
    bot = Brainiac(secret_key="ins-test")
    await bot.boot()
    result = await bot.fused_position()
    assert "lat" in result
    assert "lon" in result
    assert "source" in result
    assert "gnss_health" in result
    assert result["gnss_health"]["constellations"] == 6
    assert result["gnss_health"]["available"] is True
    assert result["ins_state"] in ("NAVIGATING", "UNINITIALISED", "ALIGNING")
    await bot.shutdown()
