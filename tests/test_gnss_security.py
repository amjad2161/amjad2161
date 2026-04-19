"""Tests for GNSS-related CyberShield features (spoofing detection)."""
import pytest
import time

from brainiac.core.cyber_shield import CyberShield


@pytest.fixture
def shield():
    return CyberShield(secret_key="test-gnss")


def test_spoof_detection_clean_position(shield):
    result = shield.detect_gps_spoofing(
        reported_lat=32.0853, reported_lon=34.7818,
        hdop=0.9,
    )
    assert result["spoof_likelihood"] < 0.3
    assert result["action"] == "OK"


def test_spoof_detection_invalid_coordinates(shield):
    result = shield.detect_gps_spoofing(
        reported_lat=200.0, reported_lon=34.7818,
    )
    assert "INVALID_COORDINATE_RANGE" in result["indicators"]
    assert result["action"] == "BLOCK"


def test_spoof_detection_impossible_speed(shield):
    # Teleport from Tel Aviv to Tokyo in 1 second → ~9000 km / 1s
    now = time.time()
    result = shield.detect_gps_spoofing(
        reported_lat=35.6895, reported_lon=139.6917,
        previous_lat=32.0853, previous_lon=34.7818,
        previous_ts=now - 1, current_ts=now,
        hdop=0.9,
    )
    assert any("IMPLAUSIBLE" in i for i in result["indicators"])
    assert result["action"] == "BLOCK"


def test_spoof_detection_hdop_too_perfect(shield):
    result = shield.detect_gps_spoofing(
        reported_lat=32.0, reported_lon=34.0,
        hdop=0.05,
    )
    assert "HDOP_TOO_PERFECT" in result["indicators"]


def test_spoof_detection_uniform_snr(shield):
    """Spoofed signals often have identical SNR values."""
    result = shield.detect_gps_spoofing(
        reported_lat=32.0, reported_lon=34.0,
        hdop=0.9,
        snr_values=[42.0, 42.0, 42.0, 42.0, 42.0],
    )
    assert "SNR_UNIFORMITY_ANOMALY" in result["indicators"]


def test_spoof_detection_real_snr_variation_passes(shield):
    result = shield.detect_gps_spoofing(
        reported_lat=32.0, reported_lon=34.0,
        hdop=0.9,
        snr_values=[38.5, 42.1, 36.8, 44.2, 39.7],
    )
    assert "SNR_UNIFORMITY_ANOMALY" not in result["indicators"]


def test_cyber_shield_diagnostics_exposes_nav_role(shield):
    d = shield.diagnostics()
    assert d["navigation_role"] == "security_layer"
    assert "gps_spoofing_detection" in d["capabilities"]
