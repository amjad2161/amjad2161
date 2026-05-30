"""Boot the whole singularity and route a few intents across organs.

    python examples/01_quickstart.py
"""

from __future__ import annotations

import asyncio

from singularity import build_default_kernel


async def main() -> None:
    async with build_default_kernel() as kernel:  # boots all 8 organs
        print("status:", {k: kernel.status()[k] for k in ("organs", "alive", "real_mode")})

        thought = await kernel.route("neuro.think", {"prompt": "unify the fleet"})
        print("neuro.think confidence:", thought["confidence"])

        signal = await kernel.route("trade.signal", {"symbol": "BTC_USDT"})
        print("trade.signal:", signal["signal"])

        mission = await kernel.route("sky.mission_plan", {"lat": 37.0, "lon": -122.0, "points": 6})
        print("sky waypoints:", mission["count"])


if __name__ == "__main__":
    asyncio.run(main())
