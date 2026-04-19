"""Tests for the RTL-aware Localization module."""
import pytest

from brainiac.core.localization import (
    Localization, Language, Direction, _classify_bearing_change,
)


# ── Bearing classification ───────────────────────────────────────────────────

def test_straight_on_zero_delta():
    assert _classify_bearing_change(0) == Direction.STRAIGHT
    assert _classify_bearing_change(10) == Direction.STRAIGHT
    assert _classify_bearing_change(-10) == Direction.STRAIGHT


def test_right_classifications():
    assert _classify_bearing_change(30) == Direction.SLIGHT_RIGHT
    assert _classify_bearing_change(90) == Direction.RIGHT
    assert _classify_bearing_change(160) == Direction.SHARP_RIGHT


def test_left_classifications():
    assert _classify_bearing_change(-30) == Direction.SLIGHT_LEFT
    assert _classify_bearing_change(-90) == Direction.LEFT
    assert _classify_bearing_change(-160) == Direction.SHARP_LEFT


def test_u_turn_classification():
    assert _classify_bearing_change(180) == Direction.U_TURN
    assert _classify_bearing_change(-180) == Direction.U_TURN


def test_bearing_wraps_around():
    # 350° is functionally -10°
    assert _classify_bearing_change(350) == Direction.STRAIGHT
    # 370° is functionally 10°
    assert _classify_bearing_change(370) == Direction.STRAIGHT


# ── Language basics ──────────────────────────────────────────────────────────

def test_default_is_english_ltr():
    loc = Localization()
    assert loc.lang == Language.EN
    assert loc.is_rtl is False


def test_hebrew_is_rtl():
    loc = Localization(lang="he")
    assert loc.lang == Language.HE
    assert loc.is_rtl is True


def test_arabic_is_rtl():
    loc = Localization(lang="ar")
    assert loc.lang == Language.AR
    assert loc.is_rtl is True


def test_lang_accepts_string_or_enum():
    a = Localization(lang="he")
    b = Localization(lang=Language.HE)
    assert a.lang == b.lang


# ── Distance formatting ──────────────────────────────────────────────────────

def test_distance_meters_en():
    loc = Localization(lang="en")
    assert loc.format_distance(50) == "50 m"
    assert loc.format_distance(999) == "999 m"


def test_distance_km_en():
    loc = Localization(lang="en")
    assert loc.format_distance(1500) == "1.5 km"


def test_distance_meters_he():
    loc = Localization(lang="he")
    assert "מטר" in loc.format_distance(500)


def test_distance_km_ar():
    loc = Localization(lang="ar")
    assert "كم" in loc.format_distance(2500)


# ── Duration formatting ──────────────────────────────────────────────────────

def test_duration_minutes_en():
    loc = Localization(lang="en")
    assert loc.format_duration(300) == "5 min"


def test_duration_hours_en():
    loc = Localization(lang="en")
    assert "h" in loc.format_duration(4500)  # 75 min → "1h 15min"


def test_duration_non_zero_min():
    loc = Localization(lang="en")
    # 30s should still render as at least 1 min
    assert loc.format_duration(30) == "1 min"


# ── Turn instructions ────────────────────────────────────────────────────────

def test_turn_instruction_en_right():
    loc = Localization(lang="en")
    phrase = loc.turn_instruction(bearing_change=90, distance_m=200, road="Main St")
    assert "200 m" in phrase
    assert "turn right" in phrase
    assert "Main St" in phrase


def test_turn_instruction_he_left():
    loc = Localization(lang="he")
    phrase = loc.turn_instruction(bearing_change=-90, distance_m=500)
    assert "500 מטר" in phrase
    assert "פנה שמאלה" in phrase


def test_turn_instruction_ar_straight():
    loc = Localization(lang="ar")
    phrase = loc.turn_instruction(bearing_change=0, distance_m=1200)
    assert "1.2 كم" in phrase
    assert "مستقيماً" in phrase


def test_arrival_with_place():
    loc = Localization(lang="en")
    assert "café" in loc.arrival("café")


def test_arrival_without_place():
    loc_en = Localization(lang="en")
    loc_he = Localization(lang="he")
    loc_ar = Localization(lang="ar")
    assert "arrived" in loc_en.arrival()
    assert "הגעת" in loc_he.arrival()
    assert "وصلت" in loc_ar.arrival()


# ── Diagnostics ──────────────────────────────────────────────────────────────

def test_diagnostics_contains_expected_keys():
    loc = Localization(lang="he")
    d = loc.diagnostics()
    assert d["lang"] == "he"
    assert d["is_rtl"] is True
    assert "en" in d["supported_languages"]
    assert "he" in d["supported_languages"]
    assert "ar" in d["supported_languages"]
