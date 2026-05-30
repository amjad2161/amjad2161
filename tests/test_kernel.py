from __future__ import annotations

import asyncio

import pytest

from singularity import build_default_kernel
from singularity.kernel.contracts import OrganError
from singularity.kernel.governor import Governor, GovernorError


def test_boot_status_and_shutdown():
    async def run():
        kernel = build_default_kernel(force_mock=True)
        report = await kernel.boot()
        status = kernel.status()
        await kernel.shutdown()
        return report, status

    report, status = asyncio.run(run())
    assert len(report) == 9
    assert status["organs"] == 9
    assert status["alive"] == 9
    assert status["intents"] >= 30
    assert status["mock_mode"] == 9


def test_route_requires_boot():
    kernel = build_default_kernel(force_mock=True)
    with pytest.raises(OrganError):
        asyncio.run(kernel.route("neuro.think", {"prompt": "hi"}))


def test_route_and_events():
    async def run():
        kernel = build_default_kernel(force_mock=True)
        await kernel.boot()
        result = await kernel.route("neuro.think", {"prompt": "hello world"})
        events = kernel.bus.history("organ.*")
        await kernel.shutdown()
        return result, events

    result, events = asyncio.run(run())
    assert result["_organ"] == "neuro"
    assert any(e.topic == "organ.neuro.result" for e in events)


def test_fanout_runs_concurrently():
    async def run():
        kernel = build_default_kernel(force_mock=True)
        await kernel.boot()
        results = await kernel.fanout(
            [
                ("neuro.plan", {"goal": "ship it"}),
                ("trade.status", {}),
                ("sky.telemetry", {}),
            ]
        )
        await kernel.shutdown()
        return results

    results = asyncio.run(run())
    assert {r["_organ"] for r in results} == {"neuro", "trade", "sky"}


def test_pulse_engages_multiple_organs():
    async def run():
        kernel = build_default_kernel(force_mock=True)
        await kernel.boot()
        pulse = await kernel.pulse("become coherent")
        await kernel.shutdown()
        return pulse

    pulse = asyncio.run(run())
    assert pulse["organs_engaged"] == ["neuro", "agents", "knowledge", "nexus"]
    assert pulse["plan"]["tasks"]


def test_governor_breaks_on_rate():
    async def run():
        kernel = build_default_kernel(force_mock=True)
        kernel.governor = Governor(max_calls_per_minute=2)
        await kernel.boot()
        await kernel.route("neuro.think", {"prompt": "1"})
        await kernel.route("neuro.think", {"prompt": "2"})
        with pytest.raises(GovernorError):
            await kernel.route("neuro.think", {"prompt": "3"})
        await kernel.shutdown()

    asyncio.run(run())


def test_async_context_manager():
    async def run():
        async with build_default_kernel(force_mock=True) as kernel:
            assert kernel.booted
            out = await kernel.route("agents.list", {})
        return out

    out = asyncio.run(run())
    assert out["count"] >= 1
