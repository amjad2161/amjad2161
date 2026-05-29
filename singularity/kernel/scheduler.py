"""Scheduler — periodic, autonomous execution (cron-like).

Mirrors the trading engine's ``scheduler`` edge function and BRAINIAC's
background loops: register intents (or callables) to fire on an interval, and a
single async loop dispatches them through the kernel. This is what lets the
organism *act over time* without a human in the loop.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from .event_bus import EventBus

if TYPE_CHECKING:  # pragma: no cover
    from .kernel import Singularity


@dataclass
class Job:
    name: str
    interval_s: float
    intent: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    action: Callable[[], Awaitable[Any]] | None = None
    last_run: float = 0.0
    runs: int = 0

    def due(self, now: float) -> bool:
        return now - self.last_run >= self.interval_s


@dataclass
class Scheduler:
    """A lightweight async cron over kernel intents."""

    kernel: "Singularity"
    bus: EventBus
    tick_s: float = 1.0
    _jobs: dict[str, Job] = field(default_factory=dict)
    _task: asyncio.Task | None = field(default=None, repr=False)
    _stopped: asyncio.Event = field(default_factory=asyncio.Event, repr=False)

    def every(
        self,
        name: str,
        interval_s: float,
        intent: str | None = None,
        payload: dict[str, Any] | None = None,
        *,
        action: Callable[[], Awaitable[Any]] | None = None,
    ) -> "Scheduler":
        if intent is None and action is None:
            raise ValueError("job needs an intent or an action")
        self._jobs[name] = Job(
            name=name, interval_s=interval_s, intent=intent, payload=payload or {}, action=action
        )
        return self

    def cancel(self, name: str) -> bool:
        return self._jobs.pop(name, None) is not None

    def jobs(self) -> list[dict[str, Any]]:
        return [
            {"name": j.name, "interval_s": j.interval_s, "intent": j.intent, "runs": j.runs}
            for j in self._jobs.values()
        ]

    async def run_due(self, now: float | None = None) -> list[str]:
        now = time.monotonic() if now is None else now
        fired: list[str] = []
        for job in list(self._jobs.values()):
            if not job.due(now):
                continue
            job.last_run = now
            job.runs += 1
            fired.append(job.name)
            try:
                if job.action is not None:
                    await job.action()
                elif job.intent is not None:
                    await self.kernel.route(job.intent, job.payload)
                await self.bus.emit("scheduler.fired", {"job": job.name, "runs": job.runs})
            except Exception as exc:  # noqa: BLE001 - one bad job must not kill the loop
                await self.bus.emit("scheduler.error", {"job": job.name, "error": repr(exc)})
        return fired

    async def start(self) -> None:
        self._stopped.clear()
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop(), name="singularity-scheduler")

    async def stop(self) -> None:
        self._stopped.set()
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _loop(self) -> None:
        try:
            while not self._stopped.is_set():
                await self.run_due()
                await asyncio.sleep(self.tick_s)
        except asyncio.CancelledError:  # pragma: no cover - shutdown path
            raise
