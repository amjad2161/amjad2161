"""The dynamic, time-and-state-aware context engine."""
from __future__ import annotations

import asyncio

from singularity.context import Context
from singularity.kernel.kernel import build_default_kernel


def test_context_snapshot_is_time_and_state_aware() -> None:
    async def run() -> tuple[dict, str]:
        async with build_default_kernel(force_mock=True) as kernel:
            snap = await Context.snapshot(kernel)
            return snap, Context.render(snap)

    snap, rendered = asyncio.run(run())
    # TIME awareness
    assert snap["phase"] in ("night", "morning", "afternoon", "evening")
    assert isinstance(snap["hour"], int)
    # STATE awareness
    assert "real_mode" in snap and "real_organs" in snap and "down_organs" in snap
    # the rendered conditioning instructs adaptation
    assert "Time:" in rendered and "State:" in rendered
    assert "Adapt the plan to the current time, state and context." in rendered
