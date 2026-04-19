"""BRAINIAC module watchdog supervisor."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import Any

import structlog

log = structlog.get_logger("brainiac.watchdog")

ModuleFactory = Callable[[], Any]


class Watchdog:
    """Periodically checks module diagnostics and restarts failed modules."""

    def __init__(
        self,
        modules: dict[str, Any],
        factories: dict[str, ModuleFactory],
        module_health: dict[str, str],
        health_key_map: dict[str, str] | None = None,
        interval_s: float = 30.0,
        max_restarts: int = 3,
    ) -> None:
        self._modules = modules
        self._factories = factories
        self._module_health = module_health
        self._health_key_map = health_key_map or {}
        self._interval_s = interval_s
        self._max_restarts = max_restarts
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._restart_counts: dict[str, int] = dict.fromkeys(modules, 0)
        self._failure_counts: dict[str, int] = dict.fromkeys(modules, 0)

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_loop(), name="brainiac-watchdog")

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task

    async def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            await self.run_once()
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self._interval_s)
            except asyncio.TimeoutError:
                continue

    async def run_once(self) -> None:
        for name, module in list(self._modules.items()):
            try:
                module.diagnostics()
                health_name = self._health_key(name)
                if self._module_health.get(health_name) != "DEGRADED":
                    self._module_health[health_name] = "ONLINE"
            except Exception as exc:
                self._failure_counts[name] = self._failure_counts.get(name, 0) + 1
                log.warning("watchdog.module_failure", module=name, error=str(exc))
                restarted = await self._restart_module(name)
                if not restarted:
                    self._module_health[self._health_key(name)] = "DEGRADED"

    async def _restart_module(self, name: str) -> bool:
        factory = self._factories.get(name)
        if not factory:
            return False

        for attempt in range(1, self._max_restarts + 1):
            try:
                if attempt > 1:
                    await asyncio.sleep(2 ** (attempt - 2))
                module = factory()
                maybe_connect = getattr(module, "connect", None)
                connect_result: Awaitable[Any] | Any = None
                if callable(maybe_connect):
                    connect_result = maybe_connect()
                if isinstance(connect_result, Awaitable):
                    await connect_result
                self._modules[name] = module
                self._module_health[self._health_key(name)] = "ONLINE"
                self._restart_counts[name] = self._restart_counts.get(name, 0) + 1
                log.info("watchdog.module_restarted", module=name, attempt=attempt)
                return True
            except Exception as exc:
                log.warning("watchdog.restart_failed", module=name, attempt=attempt, error=str(exc))
        return False

    def _health_key(self, module_name: str) -> str:
        return self._health_key_map.get(module_name, module_name)

    def diagnostics(self) -> dict[str, Any]:
        return {
            "status": "ONLINE",
            "interval_s": self._interval_s,
            "max_restarts": self._max_restarts,
            "restarts": self._restart_counts,
            "failures": self._failure_counts,
            "module_health": dict(self._module_health),
            "running": bool(self._task and not self._task.done()),
        }
