from __future__ import annotations

import asyncio

from singularity.kernel.contracts import (
    Domain,
    Health,
    Liveness,
    Mode,
    OrganInfo,
)
from singularity.kernel.event_bus import EventBus
from singularity.kernel.watchdog import Watchdog


class FlakyOrgan:
    id = "flaky"
    domain = Domain.REASONING

    def __init__(self) -> None:
        self._alive = False
        self.boots = 0

    async def boot(self) -> None:
        self.boots += 1
        self._alive = True

    async def shutdown(self) -> None:
        self._alive = False

    def health(self) -> Health:
        live = Liveness.ALIVE if self._alive else Liveness.DOWN
        return Health(self.id, live, Mode.MOCK)

    def describe(self) -> OrganInfo:
        return OrganInfo(self.id, self.domain, "Flaky", "", [], [], Mode.MOCK)

    async def invoke(self, intent, payload):  # pragma: no cover - unused
        return {}


def test_watchdog_resurrects_down_organ():
    async def run():
        organ = FlakyOrgan()  # starts DOWN
        bus = EventBus()
        reboots: list[str] = []
        bus.subscribe("watchdog.#", lambda s: reboots.append(s.topic))
        dog = Watchdog(organs={organ.id: organ}, bus=bus, base_backoff_s=0.0)
        report = await dog.run_once()
        return report, organ.boots, reboots

    report, boots, reboots = asyncio.run(run())
    assert boots == 1  # watchdog booted the dead organ
    assert "watchdog.reboot" in reboots
    assert report["flaky"] == "alive"


def test_watchdog_marks_degraded_after_max_reboots():
    async def run():
        class AlwaysDown(FlakyOrgan):
            async def boot(self) -> None:
                self.boots += 1
                self._alive = False  # never recovers

        organ = AlwaysDown()
        bus = EventBus()
        topics: list[str] = []
        bus.subscribe("watchdog.#", lambda s: topics.append(s.topic))
        dog = Watchdog(organs={organ.id: organ}, bus=bus, base_backoff_s=0.0, max_reboots=2)
        for _ in range(5):
            await dog.run_once()
        return topics

    topics = asyncio.run(run())
    assert "watchdog.degraded" in topics
