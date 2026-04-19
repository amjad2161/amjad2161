"""
BRAINIAC LOCALIZATION — RTL-aware turn-by-turn phrasing.

Provides localized navigation phrases in English, Hebrew (RTL), and Arabic (RTL),
with distance/direction formatting appropriate to each locale.

Usage:
    loc = Localization(lang="he")
    phrase = loc.turn_instruction(bearing_change=90, distance_m=250, road="רחוב דיזנגוף")
    # → "בעוד 250 מטר, פנה ימינה אל רחוב דיזנגוף"
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class Language(str, Enum):
    EN = "en"
    HE = "he"   # Hebrew (RTL)
    AR = "ar"   # Arabic (RTL)


class Direction(str, Enum):
    STRAIGHT = "straight"
    SLIGHT_LEFT = "slight_left"
    LEFT = "left"
    SHARP_LEFT = "sharp_left"
    SLIGHT_RIGHT = "slight_right"
    RIGHT = "right"
    SHARP_RIGHT = "sharp_right"
    U_TURN = "u_turn"
    ARRIVE = "arrive"


_RTL_LANGS = frozenset({Language.HE, Language.AR})


# ── Phrase Tables ────────────────────────────────────────────────────────────

_PHRASES: dict[Language, dict[Direction, str]] = {
    Language.EN: {
        Direction.STRAIGHT:     "continue straight",
        Direction.SLIGHT_LEFT:  "bear slightly left",
        Direction.LEFT:         "turn left",
        Direction.SHARP_LEFT:   "take a sharp left",
        Direction.SLIGHT_RIGHT: "bear slightly right",
        Direction.RIGHT:        "turn right",
        Direction.SHARP_RIGHT:  "take a sharp right",
        Direction.U_TURN:       "make a U-turn",
        Direction.ARRIVE:       "you have arrived",
    },
    Language.HE: {
        Direction.STRAIGHT:     "המשך ישר",
        Direction.SLIGHT_LEFT:  "סטה מעט שמאלה",
        Direction.LEFT:         "פנה שמאלה",
        Direction.SHARP_LEFT:   "פנה בחדות שמאלה",
        Direction.SLIGHT_RIGHT: "סטה מעט ימינה",
        Direction.RIGHT:        "פנה ימינה",
        Direction.SHARP_RIGHT:  "פנה בחדות ימינה",
        Direction.U_TURN:       "בצע פניית פרסה",
        Direction.ARRIVE:       "הגעת ליעד",
    },
    Language.AR: {
        Direction.STRAIGHT:     "تابع مستقيماً",
        Direction.SLIGHT_LEFT:  "انحرف قليلاً يساراً",
        Direction.LEFT:         "انعطف يساراً",
        Direction.SHARP_LEFT:   "انعطف بحدة يساراً",
        Direction.SLIGHT_RIGHT: "انحرف قليلاً يميناً",
        Direction.RIGHT:        "انعطف يميناً",
        Direction.SHARP_RIGHT:  "انعطف بحدة يميناً",
        Direction.U_TURN:       "قم بدوران كامل",
        Direction.ARRIVE:       "لقد وصلت إلى وجهتك",
    },
}

_IN_DIST: dict[Language, str] = {
    Language.EN: "in {dist}",
    Language.HE: "בעוד {dist}",
    Language.AR: "بعد {dist}",
}

_TO_ROAD: dict[Language, str] = {
    Language.EN: "onto {road}",
    Language.HE: "אל {road}",
    Language.AR: "إلى {road}",
}

_ARRIVE_AT: dict[Language, str] = {
    Language.EN: "you have arrived at {place}",
    Language.HE: "הגעת ל{place}",
    Language.AR: "لقد وصلت إلى {place}",
}


def _classify_bearing_change(delta_deg: float) -> Direction:
    """Convert a bearing change (degrees) to a direction token."""
    # Normalize to (-180, 180]
    d = ((delta_deg + 180) % 360) - 180
    if d > 170 or d < -170:
        return Direction.U_TURN
    if -15 <= d <= 15:
        return Direction.STRAIGHT
    if 15 < d <= 45:
        return Direction.SLIGHT_RIGHT
    if 45 < d <= 135:
        return Direction.RIGHT
    if 135 < d <= 170:
        return Direction.SHARP_RIGHT
    if -45 <= d < -15:
        return Direction.SLIGHT_LEFT
    if -135 <= d < -45:
        return Direction.LEFT
    return Direction.SHARP_LEFT


@dataclass
class Localization:
    """RTL-aware turn-by-turn phrasing for navigation instructions."""

    lang: Language = Language.EN

    def __post_init__(self) -> None:
        if isinstance(self.lang, str):
            self.lang = Language(self.lang)

    @property
    def is_rtl(self) -> bool:
        return self.lang in _RTL_LANGS

    def format_distance(self, meters: float) -> str:
        """Locale-aware distance rendering."""
        if meters < 1000:
            value = f"{int(round(meters))}"
            unit = {Language.EN: "m", Language.HE: "מטר", Language.AR: "متر"}[self.lang]
            return f"{value} {unit}"
        value = f"{meters / 1000:.1f}"
        unit = {Language.EN: "km", Language.HE: 'ק"מ', Language.AR: "كم"}[self.lang]
        return f"{value} {unit}"

    def format_duration(self, seconds: float) -> str:
        """Locale-aware duration rendering (h/min)."""
        minutes = int(seconds // 60)
        hours = minutes // 60
        rem_min = minutes % 60
        if hours > 0:
            if self.lang == Language.EN:
                return f"{hours}h {rem_min}min"
            if self.lang == Language.HE:
                return f"{hours} שעות {rem_min} דקות"
            return f"{hours} ساعات {rem_min} دقائق"
        if self.lang == Language.EN:
            return f"{max(1, minutes)} min"
        if self.lang == Language.HE:
            return f"{max(1, minutes)} דקות"
        return f"{max(1, minutes)} دقائق"

    def direction_phrase(self, direction: Direction) -> str:
        return _PHRASES[self.lang][direction]

    def turn_instruction(
        self,
        bearing_change: float,
        distance_m: float,
        road: str | None = None,
    ) -> str:
        """Build a single turn instruction."""
        direction = _classify_bearing_change(bearing_change)
        dist_str = self.format_distance(distance_m)
        in_prefix = _IN_DIST[self.lang].format(dist=dist_str)
        phrase = self.direction_phrase(direction)
        if road and direction not in (Direction.STRAIGHT, Direction.ARRIVE):
            road_part = _TO_ROAD[self.lang].format(road=road)
            phrase = f"{phrase} {road_part}"
        sep = ", " if self.lang == Language.EN else ", "
        return f"{in_prefix}{sep}{phrase}"

    def arrival(self, place: str | None = None) -> str:
        if place:
            return _ARRIVE_AT[self.lang].format(place=place)
        return _PHRASES[self.lang][Direction.ARRIVE]

    def diagnostics(self) -> dict[str, Any]:
        return {
            "status": "ONLINE",
            "navigation_role": "rtl_turn_by_turn_localizer",
            "capabilities": ["turn_by_turn_i18n", "rtl_he_ar", "distance_unit_rendering"],
            "lang": self.lang.value,
            "is_rtl": self.is_rtl,
            "supported_languages": [language.value for language in Language],
        }


__all__ = ["Language", "Direction", "Localization"]
