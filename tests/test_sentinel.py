"""The proactive Sentinel: sense the environment and react on its own."""
from __future__ import annotations

import asyncio
from typing import Any

from singularity.sentinel import Sentinel


class _FakeBus:
    def __init__(self) -> None:
        self.emitted: list[str] = []

    async def emit(self, topic: str, payload: Any = None, source: str = "") -> int:
        self.emitted.append(topic)
        return 1

    def history(self, pattern: str = "#") -> list[Any]:
        return []


class _FakeKernel:
    """Minimal kernel stub returning a canned vision.watch — no camera needed."""

    def __init__(self, watch: dict[str, Any]) -> None:
        self._watch = watch
        self.bus = _FakeBus()

    def status(self) -> dict[str, Any]:
        return {"health": [], "real_mode": 9, "alive": 9}

    async def route(self, intent: str, payload: Any) -> dict[str, Any]:
        if intent == "vision.watch":
            return self._watch
        if intent == "neuro.think":
            return {"thought": ""}
        return {}


class _VoiceSpy:
    def __init__(self) -> None:
        self.said: list[str] = []

    def speak_as(self, organ: str, text: str) -> None:
        self.said.append(f"{organ}:{text}")


def test_sentinel_greets_proactively_on_presence() -> None:
    voice = _VoiceSpy()
    k = _FakeKernel({"present": True, "motion": False, "summary": "person present"})
    s = Sentinel(k, voice=voice)

    r1 = asyncio.run(s.tick())                       # first sight -> greet
    assert "greeted_on_presence" in r1["events"]
    assert any("jarvis:" in m for m in voice.said)   # greeted in JARVIS's voice
    assert "sentinel.presence" in k.bus.emitted      # broadcast on the nervous system

    r2 = asyncio.run(s.tick())                       # still present -> no re-greet
    assert r2["events"] == []


def test_sentinel_alerts_on_motion_when_empty() -> None:
    k = _FakeKernel({"present": False, "motion": True, "motion_level": 0.3,
                     "summary": "motion detected"})
    s = Sentinel(k)
    r = asyncio.run(s.tick())
    assert "motion_alert" in r["events"]
    assert "sentinel.motion" in k.bus.emitted
