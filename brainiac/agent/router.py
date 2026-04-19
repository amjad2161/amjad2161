"""Intent router for the agent layer."""
from __future__ import annotations

import re
from typing import Any


class AgentRouter:
    _RULES: list[tuple[str, str]] = [
        (r"(route|navigate|gnss|eta|מסלול|ניווט|ملاحة)", "navigation"),
        (r"(telemetry|sensor|anomaly|טלמטר|مستشعر)", "telemetry"),
        (r"(medical|dose|drug|רפוא|دواء)", "medical"),
        (r"(security|threat|spoof|אבטח|تهديد)", "security"),
    ]

    def route(self, prompt: str) -> str:
        text = prompt or ""
        for pattern, target in self._RULES:
            if re.search(pattern, text, flags=re.IGNORECASE | re.UNICODE):
                return target
        return "general"

    def diagnostics(self) -> dict[str, Any]:
        return {"status": "ONLINE", "rules": len(self._RULES)}


__all__ = ["AgentRouter"]
