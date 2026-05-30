from __future__ import annotations

import asyncio

from singularity.kernel.event_bus import EventBus
from singularity.kernel.contracts import Signal


def test_exact_and_wildcard_delivery():
    async def run():
        bus = EventBus()
        seen: list[str] = []
        bus.subscribe("organ.neuro.#", lambda s: seen.append(s.topic))
        catch_all: list[str] = []
        bus.subscribe("#", lambda s: catch_all.append(s.topic))

        await bus.publish(Signal("organ.neuro.result"))
        await bus.publish(Signal("organ.sky.result"))
        return seen, catch_all, bus.total_delivered

    seen, catch_all, delivered = asyncio.run(run())
    assert seen == ["organ.neuro.result"]
    assert catch_all == ["organ.neuro.result", "organ.sky.result"]
    assert delivered == 3


def test_async_handler_and_unsubscribe():
    async def run():
        bus = EventBus()
        hits: list[str] = []

        async def handler(sig: Signal) -> None:
            hits.append(sig.topic)

        unsub = bus.subscribe("a.*", handler)
        await bus.emit("a.one")
        unsub()
        await bus.emit("a.two")
        return hits, bus.history("a.*")

    hits, history = asyncio.run(run())
    assert hits == ["a.one"]
    assert [s.topic for s in history] == ["a.one", "a.two"]
