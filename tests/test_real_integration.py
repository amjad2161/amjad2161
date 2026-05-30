"""Authenticity tests — exercise the *real* sibling-repo backends.

These run the genuine code of SkyCore / agency / Mythos and the on-disk skill
corpus when those repos are checked out. Each test skips cleanly if its backend
is unavailable, so the suite stays green anywhere while *proving* the integration
is real (not a mock) wherever the repos exist.
"""

from __future__ import annotations

import asyncio

import pytest

from singularity import build_default_kernel
from singularity.kernel.bootstrap import available


def _real_kernel():
    # force_mock=False → organs attach real backends when importable.
    return build_default_kernel(force_mock=False)


def test_sky_uses_real_skycore_when_present():
    if not available()["skycore"]:
        pytest.skip("skycore not checked out")

    async def run():
        kernel = _real_kernel()
        await kernel.boot()
        assert kernel.registry.get("sky").health().mode.value == "real"
        plan = await kernel.route("sky.mission_plan",
                                  {"lat": 38.5, "lon": -122.4, "points": 4, "radius_m": 30})
        flight = await kernel.route("sky.fly", {"lat": 38.5, "lon": -122.4, "points": 3})
        await kernel.shutdown()
        return plan, flight

    plan, flight = asyncio.run(run())
    assert plan["_backend"] == "skycore" and plan["count"] == 4
    # speed comes from SkyCore's real TrajectoryGenerator (circular_trajectory)
    assert plan.get("trajectory_engine") == "skycore.TrajectoryGenerator"
    assert "speed_mps" in plan["waypoints"][0]
    # fly drives the genuine SkyCoreSystem and reports honestly — it must NOT
    # claim "flown" unless the real controller actually armed and took off.
    assert flight["_backend"] == "skycore"
    assert flight["status"] in ("flown", "planned-only")
    assert flight["planned_waypoints"] == 3


def test_agents_uses_real_agency_when_present():
    if not available()["agency"]:
        pytest.skip("agency not checked out")

    async def run():
        kernel = _real_kernel()
        await kernel.boot()
        listed = await kernel.route("agents.list", {})
        routed = await kernel.route("agents.route", {"request": "build a react frontend component"})
        await kernel.shutdown()
        return listed, routed

    listed, routed = asyncio.run(run())
    assert listed["_backend"] == "agency"
    assert listed["count"] > 100  # the real persona library (300+)
    assert routed["_backend"] == "agency"
    assert "frontend" in routed["persona"].lower()


def test_neuro_uses_real_mythos_when_present():
    if not available()["mythos"]:
        pytest.skip("mythos not checked out")

    async def run():
        kernel = _real_kernel()
        await kernel.boot()
        out = await kernel.route("neuro.autonomous_run", {"goal": "compute 2**8", "max_iterations": 2})
        await kernel.shutdown()
        return out

    out = asyncio.run(run())
    assert out["_backend"].startswith("mythos:")
    assert isinstance(out["conclusion"], str) and out["conclusion"]


def test_knowledge_indexes_real_files_when_present():
    async def run():
        kernel = _real_kernel()
        await kernel.boot()
        stats = await kernel.route("knowledge.stats", {})
        await kernel.shutdown()
        return stats, kernel.registry.get("knowledge").health().mode.value

    stats, mode = asyncio.run(run())
    if mode != "real":
        pytest.skip("no sibling repos to index")
    assert stats["_backend"] == "filesystem-scan"
    assert stats["total"] > 50  # hundreds of real skills/agents/prompts
