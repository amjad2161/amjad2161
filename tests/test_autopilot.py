from __future__ import annotations

import asyncio

from singularity import build_default_kernel
from singularity.kernel.autopilot import Autopilot


def test_autopilot_runs_loop_and_concludes():
    async def run():
        kernel = build_default_kernel(force_mock=True)
        await kernel.boot()
        result = await kernel.autopilot("survey a vineyard then hedge the harvest futures",
                                        max_iterations=5)
        await kernel.shutdown()
        return result

    result = asyncio.run(run())
    assert result.iterations >= 1
    assert result.conclusion  # neuro.think produced a conclusion
    assert result.organs_engaged  # at least one organ acted
    # every step carries a concrete intent + observation
    for step in result.steps:
        assert "." in step.intent
        assert step.observation


def test_dispatch_routes_keywords_to_organs():
    assert Autopilot._dispatch("plan the drone survey mission")[0] == "sky.mission_plan"
    assert Autopilot._dispatch("hedge the market risk")[0] == "trade.signal"
    assert Autopilot._dispatch("render a creative badge")[0] == "vision.creative"
    assert Autopilot._dispatch("search for testing skills")[0] == "knowledge.search"
    assert Autopilot._dispatch("do something generic")[0] == "agents.run"


def test_autopilot_emits_lifecycle_events():
    async def run():
        kernel = build_default_kernel(force_mock=True)
        topics: list[str] = []
        kernel.bus.subscribe("autopilot.#", lambda s: topics.append(s.topic))
        await kernel.boot()
        await kernel.autopilot("build something", max_iterations=2)
        await kernel.shutdown()
        return topics

    topics = asyncio.run(run())
    assert "autopilot.start" in topics
    assert "autopilot.done" in topics
