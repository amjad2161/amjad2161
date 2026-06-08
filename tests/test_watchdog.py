"""Tests for watchdog supervisor."""

from __future__ import annotations

import pytest

from brainiac.watchdog import Watchdog


class HealthyModule:
    def diagnostics(self):
        return {"status": "ONLINE"}


class FailingModule:
    def diagnostics(self):
        raise RuntimeError("boom")


@pytest.mark.asyncio
async def test_watchdog_restarts_failed_module():
    modules = {"nav": FailingModule()}
    health = {"nav": "ONLINE"}

    def factory():
        return HealthyModule()

    watchdog = Watchdog(
        modules=modules, factories={"nav": factory}, module_health=health, interval_s=0.01
    )

    await watchdog.run_once()

    assert isinstance(modules["nav"], HealthyModule)
    assert health["nav"] == "ONLINE"
    assert watchdog.diagnostics()["restarts"]["nav"] == 1


@pytest.mark.asyncio
async def test_watchdog_marks_degraded_after_restart_failures():
    modules = {"nav": FailingModule()}
    health = {"nav": "ONLINE"}

    def bad_factory():
        raise RuntimeError("restart failed")

    watchdog = Watchdog(
        modules=modules,
        factories={"nav": bad_factory},
        module_health=health,
        interval_s=0.01,
        max_restarts=2,
    )

    await watchdog.run_once()

    assert health["nav"] == "DEGRADED"
