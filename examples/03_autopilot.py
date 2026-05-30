"""Hand the organism a goal and let it act autonomously.

    python examples/03_autopilot.py
"""

from __future__ import annotations

import asyncio

from singularity import build_default_kernel


async def main() -> None:
    async with build_default_kernel() as kernel:
        run = await kernel.autopilot(
            "survey a vineyard, hedge the harvest futures, and brief the team", max_iterations=6
        )
        print("goal:", run.goal)
        for step in run.steps:
            print(f"  {step.iteration}. {step.intent:<20} {step.observation}")
        print("organs engaged:", run.organs_engaged)
        print("conclusion:", run.conclusion[:100])


if __name__ == "__main__":
    asyncio.run(main())
