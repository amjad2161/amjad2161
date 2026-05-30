from __future__ import annotations

import asyncio

from singularity import build_default_kernel


def test_scheduler_runs_due_jobs():
    async def run():
        kernel = build_default_kernel(force_mock=True)
        await kernel.boot()
        fired_events: list[str] = []
        kernel.bus.subscribe("scheduler.#", lambda s: fired_events.append(s.topic))
        kernel.scheduler.every("status", interval_s=0.0, intent="trade.status", payload={})
        # interval 0 → due immediately
        fired = await kernel.scheduler.run_due(now=100.0)
        await kernel.shutdown()
        return fired, fired_events, kernel.scheduler.jobs()

    fired, events, jobs = asyncio.run(run())
    assert "status" in fired
    assert "scheduler.fired" in events
    assert jobs[0]["runs"] == 1


def test_scheduler_respects_interval():
    async def run():
        kernel = build_default_kernel(force_mock=True)
        await kernel.boot()
        kernel.scheduler.every("ping", interval_s=100.0, intent="sky.telemetry", payload={})
        first = await kernel.scheduler.run_due(now=1000.0)
        again = await kernel.scheduler.run_due(now=1000.5)  # too soon
        later = await kernel.scheduler.run_due(now=1101.0)  # interval elapsed
        await kernel.shutdown()
        return first, again, later

    first, again, later = asyncio.run(run())
    assert first == ["ping"] and again == [] and later == ["ping"]


def test_scheduler_action_callable():
    async def run():
        kernel = build_default_kernel(force_mock=True)
        await kernel.boot()
        hits = {"n": 0}

        async def tick():
            hits["n"] += 1

        kernel.scheduler.every("tick", interval_s=0.0, action=tick)
        await kernel.scheduler.run_due(now=5.0)
        await kernel.shutdown()
        return hits["n"]

    assert asyncio.run(run()) == 1
