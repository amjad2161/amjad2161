"""The autonomic nervous system: events trigger real actions on their own."""
from __future__ import annotations

import asyncio
from typing import Any

from singularity.kernel.event_bus import EventBus
from singularity.reflexes import Reflex, Reflexes


class _FakeKernel:
    """A kernel with a real bus that records the intents reflexes route to."""

    def __init__(self) -> None:
        self.bus = EventBus()
        self.routed: list[tuple[str, dict[str, Any]]] = []

    async def route(self, intent: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.routed.append((intent, payload))
        return {"description": "a person near the desk", "_backend": "fake"}


def test_motion_triggers_an_autonomous_look() -> None:
    async def run() -> None:
        k = _FakeKernel()
        reflexes = Reflexes(k).arm()                       # default: investigate-motion

        await k.bus.emit("sentinel.motion", {"level": 0.4})   # the spinal trigger
        await reflexes.drain()                              # let the reflex finish

        assert any(intent == "vision.analyze" for intent, _ in k.routed)
        assert reflexes.fired and reflexes.fired[0]["reflex"] == "investigate-motion"
        # it broadcast that it acted, on its own
        assert any(s.topic == "reflex.fired" for s in k.bus.history())

    asyncio.run(run())


def test_reflex_never_reacts_to_its_own_events() -> None:
    """A reflex.* event must not arm another reflex -> no autonomic storm."""
    async def run() -> None:
        k = _FakeKernel()
        reflexes = Reflexes(k)
        reflexes.reflexes = [Reflex(name="echo", on="#", intent="neuro.think")]
        reflexes.arm()

        await k.bus.emit("reflex.fired", {"loop": True})
        await reflexes.drain()

        assert k.routed == []                               # storm prevented

    asyncio.run(run())


def test_condition_gates_a_reflex() -> None:
    async def run() -> None:
        k = _FakeKernel()
        reflexes = Reflexes(k)
        reflexes.reflexes = [Reflex(name="guarded", on="x.test", intent="neuro.think",
                                    when=lambda sig: sig.payload.get("go") is True)]
        reflexes.arm()

        await k.bus.emit("x.test", {"go": False})
        await reflexes.drain()
        assert k.routed == []                               # gated off

        await k.bus.emit("x.test", {"go": True})
        await reflexes.drain()
        assert k.routed and k.routed[0][0] == "neuro.think"  # gated on

    asyncio.run(run())
