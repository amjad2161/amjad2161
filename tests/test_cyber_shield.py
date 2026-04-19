"""Tests for CYBER-SHIELD module."""

import pytest

from brainiac.core.cyber_shield import CyberShield, ThreatLevel, ThreatType


@pytest.fixture
def shield():
    return CyberShield(secret_key="test-secret-key-32-bytes-long!!!")


# ── Input Scanning ────────────────────────────────────────────────────────────


def test_scan_clean_input(shield):
    assert shield.scan_input("Hello, world! How are you?") is None


def test_scan_sql_injection(shield):
    event = shield.scan_input("SELECT * FROM users WHERE 1=1; DROP TABLE users;")
    assert event is not None
    assert event.threat_type == ThreatType.SQL_INJECTION
    assert event.threat_level.value >= ThreatLevel.HIGH.value


def test_scan_xss(shield):
    event = shield.scan_input("<script>alert('xss')</script>")
    assert event is not None
    assert event.threat_level.value >= ThreatLevel.HIGH.value


def test_sanitize(shield):
    dirty = '<script>alert("xss")</script> & "quoted"'
    clean = shield.sanitize(dirty)
    assert "<script>" not in clean
    assert "&amp;" in clean or "&lt;" in clean


# ── Rate Limiting ─────────────────────────────────────────────────────────────


def test_rate_limit_within_bounds(shield):
    ip = "10.0.0.1"
    for _ in range(50):
        assert shield.check_rate_limit(ip, max_requests=100) is True


def test_rate_limit_exceeded(shield):
    ip = "10.0.0.2"
    # Flood the IP
    for _ in range(1001):
        shield.check_rate_limit(ip, max_requests=1, window_s=60)
    # Should now be blocked
    assert shield.check_rate_limit(ip, max_requests=1) is False


def test_unblock_ip(shield):
    ip = "10.0.0.3"
    for _ in range(1001):
        shield.check_rate_limit(ip, max_requests=1, window_s=60)
    shield.unblock_ip(ip)
    # After unblock, counter is gone too
    shield._rate_counters.pop(ip, None)
    assert shield.check_rate_limit(ip, max_requests=100) is True


# ── File Integrity ────────────────────────────────────────────────────────────


def test_verify_clean_file(shield):
    result = shield.verify_file(b"hello world this is a legitimate file")
    assert result["malware_detected"] is False
    assert len(result["md5"]) == 32
    assert len(result["sha256"]) == 64


def test_verify_empty_file_hash(shield):
    result = shield.verify_file(b"")
    # Empty file hash IS in the known-bad list
    assert result["malware_detected"] is True


# ── HMAC ──────────────────────────────────────────────────────────────────────


def test_sign_and_verify(shield):
    payload = {"action": "launch", "target": "moon", "ts": 1234567890}
    sig = shield.sign(payload)
    assert shield.verify_signature(payload, sig) is True


def test_verify_tampered_payload(shield):
    payload = {"action": "safe"}
    sig = shield.sign(payload)
    tampered = {"action": "dangerous"}
    assert shield.verify_signature(tampered, sig) is False


# ── Config Audit ──────────────────────────────────────────────────────────────


def test_audit_insecure_config(shield):
    bad_config = {
        "debug": True,
        "secret_key": "changeme",
        "https_only": False,
        "cors_origins": ["*"],
    }
    result = shield.audit_config(bad_config)
    assert result.risk_score > 0
    assert len(result.vulnerabilities) >= 3
    assert len(result.hardening_recommendations) >= 3


def test_audit_secure_config(shield):
    good_config = {
        "debug": False,
        "secret_key": "a-very-long-random-secret-key-that-is-safe",
        "https_only": True,
        "cors_origins": ["https://brainiac.ai"],
        "rate_limiting": True,
    }
    result = shield.audit_config(good_config)
    assert result.risk_score == 0
    assert result.vulnerabilities == []


def test_diagnostics(shield):
    d = shield.diagnostics()
    assert d["status"] == "ONLINE"
    assert "total_events" in d
