"""Tests for CyberShield hardware attack detection and federated learning privacy."""
import pytest

from brainiac.core.cyber_shield import CyberShield


@pytest.fixture
def shield():
    return CyberShield(secret_key="hw-test")


# ── Hardware Attack Detection ────────────────────────────────────────────────

def test_detect_emp_interference(shield):
    result = shield.detect_hardware_attack(sensor_readings={"emf_gauss": 150.0})
    assert "EMP_INTERFERENCE_DETECTED" in result["indicators"]
    assert result["attack_likelihood"] >= 0.7
    assert result["action"] == "BLOCK"


def test_detect_high_emf_warning(shield):
    result = shield.detect_hardware_attack(sensor_readings={"emf_gauss": 75.0})
    assert "HIGH_EMF_WARNING" in result["indicators"]
    assert result["action"] in ("ALERT", "OK")


def test_detect_voltage_anomaly(shield):
    result = shield.detect_hardware_attack(sensor_readings={"voltage_v": 5.5})
    assert "VOLTAGE_ANOMALY" in result["indicators"]


def test_detect_clock_drift(shield):
    result = shield.detect_hardware_attack(sensor_readings={"clock_drift_ppm": 100.0})
    assert "CLOCK_DRIFT_ANOMALY" in result["indicators"]


def test_detect_rf_injection(shield):
    """Flipper Zero-style high-power RF injection is detected."""
    result = shield.detect_hardware_attack(
        sensor_readings={},
        rf_spectrum=[-5.0, -80.0, -70.0, -85.0, -90.0],   # one very strong peak
    )
    assert "RF_INJECTION_DETECTED" in result["indicators"]


def test_clean_hardware_state_passes(shield):
    result = shield.detect_hardware_attack(
        sensor_readings={"emf_gauss": 5.0, "voltage_v": 3.3, "clock_drift_ppm": 2.0},
        rf_spectrum=[-80.0, -85.0, -78.0, -82.0, -90.0],
    )
    assert result["attack_likelihood"] < 0.3
    assert result["action"] == "OK"


# ── Federated Learning Privacy ──────────────────────────────────────────────

def test_enforce_data_locality_redacts_pii(shield):
    data = {
        "name": "John Doe",
        "email": "john@example.com",
        "speed_kmh": 60,
        "heading_deg": 90,
    }
    sanitised = shield.enforce_data_locality(data)
    assert sanitised["name"] == "[REDACTED]"
    assert sanitised["email"] == "[REDACTED]"
    assert sanitised["speed_kmh"] == 60
    assert sanitised["heading_deg"] == 90


def test_enforce_data_locality_nested(shield):
    data = {
        "user": {"name": "Alice", "face_encoding": "abcd"},
        "route": {"distance_km": 10},
    }
    sanitised = shield.enforce_data_locality(data)
    assert sanitised["user"]["name"] == "[REDACTED]"
    assert sanitised["user"]["face_encoding"] == "[REDACTED]"
    assert sanitised["route"]["distance_km"] == 10


def test_enforce_data_locality_allowlist(shield):
    """Explicitly allowed fields bypass redaction."""
    data = {"name": "Alice", "email": "a@b.com"}
    sanitised = shield.enforce_data_locality(data, allowed_fields=["name"])
    assert sanitised["name"] == "Alice"
    assert sanitised["email"] == "[REDACTED]"


def test_privacy_audit_finds_email(shield):
    data = {"message": "Contact me at alice@example.com for details"}
    result = shield.privacy_audit(data)
    assert result["pii_risk_score"] > 0
    assert any(f["pii_type"] == "email" for f in result["exposed_fields"])
    assert result["federated_compliant"] is False


def test_privacy_audit_finds_ip(shield):
    data = {"log_line": "Request from 192.168.1.42"}
    result = shield.privacy_audit(data)
    assert any(f["pii_type"] == "ip_address" for f in result["exposed_fields"])


def test_privacy_audit_clean_data(shield):
    data = {"distance_km": 12, "speed_kmh": 60, "mode": "driving"}
    result = shield.privacy_audit(data)
    assert result["pii_risk_score"] == 0
    assert result["federated_compliant"] is True
    assert result["recommendation"] == "CLEAR"


# ── Diagnostics ──────────────────────────────────────────────────────────────

def test_cyber_shield_capabilities_include_hardware_and_privacy(shield):
    caps = shield.diagnostics()["capabilities"]
    assert "hardware_attack_detection" in caps
    assert "federated_privacy" in caps
    assert "pii_audit" in caps
