"""The unified JARVIS commander: plan -> parallel multi-organ execute -> synthesise."""
from __future__ import annotations

import asyncio

from singularity.jarvis import Jarvis
from singularity.kernel.kernel import build_default_kernel


def test_jarvis_command_plans_executes_synthesises() -> None:
    async def run() -> dict:
        async with build_default_kernel(force_mock=True) as kernel:
            return await Jarvis(kernel).command(
                "check the market and search for a frontend agent", max_tasks=4)

    result = asyncio.run(run())
    assert result["plan"]                                  # the brain produced a plan
    assert result["executed"]                              # steps routed to organs
    assert result["organs_engaged"]                        # >= 1 real organ engaged
    assert result["parallel"] is True                      # executed via fanout
    assert isinstance(result["conclusion"], str) and result["conclusion"]
    # every executed step is a real federation intent
    assert all("." in intent for intent in result["executed"])


def test_jarvis_router_maps_domains() -> None:
    async def run() -> Jarvis:
        async with build_default_kernel(force_mock=True) as kernel:
            return Jarvis(kernel)

    j = asyncio.run(run())
    assert j._intent_for("check the bitcoin price")[0] == "trade.signal"
    assert j._intent_for("look at my screen")[0] == "vision.analyze"
    assert j._intent_for("fly a survey mission")[0] == "sky.telemetry"
    assert j._intent_for("browse https://example.com")[0] == "control.browse"
    assert j._intent_for("do something unusual")[0] == "agents.route"  # default specialist
