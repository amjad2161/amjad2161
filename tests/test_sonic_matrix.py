"""Tests for SONIC-MATRIX module."""
import pytest

from brainiac.core.sonic_matrix import SonicMatrix

langdetect = pytest.importorskip("langdetect", reason="langdetect not installed in env")


@pytest.fixture
def sonic():
    return SonicMatrix(default_lang="en")


def test_detect_english(sonic):
    result = sonic.detect_language("Hello, this is a test in English.")
    assert result["language"] == "en"
    assert result["confidence"] > 0.5


def test_detect_unknown_graceful(sonic):
    # Very short text — may fail detection but should not raise
    result = sonic.detect_language("X")
    assert "language" in result


def test_supported_languages(sonic):
    langs = sonic.supported_languages()
    assert isinstance(langs, list)
    assert len(langs) >= 20
    codes = [lang_entry["code"] for lang_entry in langs]
    assert "en" in codes
    assert "he" in codes
    assert "ar" in codes


def test_voice_profile_registration(sonic):
    features = {"pitch": 220.0, "timbre": "warm", "rate_wpm": 140}
    fp = sonic.register_voice("user-001", features)
    assert len(fp) == 16


def test_voice_identity(sonic):
    features = {"pitch": 180.0, "timbre": "deep"}
    sonic.register_voice("user-002", features)
    found = sonic.identify_voice({"pitch": 180.0, "timbre": "deep"})
    assert found == "user-002"


def test_voice_identity_no_match(sonic):
    result = sonic.identify_voice({"pitch": 9999.0})
    assert result is None


def test_diagnostics(sonic):
    d = sonic.diagnostics()
    assert d["status"] == "ONLINE"
    assert d["supported_languages"] >= 20
