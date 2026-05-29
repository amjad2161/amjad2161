"""Compose a DAG that threads one goal across several organs in parallel layers.

    python examples/02_workflow.py
"""

from __future__ import annotations

import asyncio

from singularity import Workflow, build_default_kernel


async def main() -> None:
    wf = (
        Workflow("survey-and-hedge")
        .add_step("plan", "neuro.plan", {"goal": "survey a vineyard then hedge the harvest"})
        .add_step("mission", "sky.mission_plan",
                  {"kind": "survey", "lat": 38.5, "lon": -122.4, "points": 8}, depends_on=["plan"])
        .add_step("fly", "sky.fly",
                  lambda ctx: {"waypoints": ctx["mission"]["waypoints"]}, depends_on=["mission"])
        .add_step("hedge", "trade.backtest", {"symbol": "BTC_USDT"}, depends_on=["plan"])
    )
    async with build_default_kernel() as kernel:
        result = await kernel.run_workflow(wf)
        print("layers:", result.layers)
        print("organs engaged:", result.organs_engaged)
        print("flight executed waypoints:", result.outputs["fly"]["executed"])


if __name__ == "__main__":
    asyncio.run(main())
