"""Simple localization helpers for EN/HE/AR."""
from __future__ import annotations

from typing import Any


class Localization:
    _PHRASES = {
        "en": {"turn_left": "Turn left", "turn_right": "Turn right", "arrived": "Arrived"},
        "he": {"turn_left": "פנה שמאלה", "turn_right": "פנה ימינה", "arrived": "הגעת"},
        "ar": {"turn_left": "انعطف يسارًا", "turn_right": "انعطف يمينًا", "arrived": "وصلت"},
    }

    def phrase(self, key: str, lang: str = "en") -> str:
        return self._PHRASES.get(lang, self._PHRASES["en"]).get(key, key)

    def is_rtl(self, lang: str) -> bool:
        return lang in {"he", "ar"}

    def diagnostics(self) -> dict[str, Any]:
        return {
            "status": "ONLINE",
            "navigation_role": "localization",
            "capabilities": ["phrase_lookup", "rtl_support"],
            "metrics": {"languages": len(self._PHRASES)},
            "version": "2.1.0",
        }
