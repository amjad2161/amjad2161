"""The supervisor: health polling + exponential-backoff resurrection.

Direct descendant of BRAINIAC's ``Watchdog``. It periodically inspects each
organ's :meth:`health`, reboots organs that have gone ``DOWN`` with exponential
backoff, and marks an organ ``DEGRADED`` once it exhausts its retries so the
rest of the singularity keeps running.
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field

from .contracts import Liveness, Organ, Signal
from .event_bus import EventBus


@dataclass
class _OrganState:
    failures: int = 0
    reboots: int = 0
    backoff: float = 0.0


@dataclass
class Watchdog:
    """Background supervisor over a set of organs."""

    organs: dict[str, Organ]
    bus: EventBus
    interval_s: float = 5.0
    max_reboots: int = 3
    base_backoff_s: float = 0.5
    _states: dict[str, _OrganState] = field(default_factory=dict)
    _task: asyncio.Task | None = field(default=None, repr=False)
    _stopped: asyncio.Event = field(default_factory=asyncio.Event, repr=False)

    async def start(self) -> None:
        self._stopped.clear()
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop(), name="singularity-watchdog")

    async def stop(self) -> None:
        self._stopped.set()
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def run_once(self) -> dict[str, str]:
        """Inspect every organ once; reboot the dead. Returns id -> liveness."""

        report: dict[str, str] = {}
        for organ_id, organ in self.organs.items():
            state = self._states.setdefault(organ_id, _OrganState())
            health = organ.health()
            if health.liveness is Liveness.DOWN:
                await self._resurrect(organ_id, organ, state)
            else:
                if state.failures or state.reboots:
                    await self.bus.publish(
                        Signal("watchdog.recovered", {"organ": organ_id}, source="watchdog")
                    )
                # Reset the FULL backoff state on recovery — previously `reboots`
                # was never cleared, so after one exhaustion the next blip went
                # straight to the degraded branch without retrying (#7).
                state.failures = 0
                state.reboots = 0
                state.backoff = 0.0
            report[organ_id] = organ.health().liveness.value
        return report

    async def _resurrect(self, organ_id: str, organ: Organ, state: _OrganState) -> None:
        state.failures += 1
        if state.reboots >= self.max_reboots:
            # Exhausted retries: mark the organ DEGRADED (usable, reduced
            # fidelity) instead of leaving it DOWN and only emitting an event —
            # otherwise run_once() keeps reporting "down" and invoke() keeps
            # rejecting calls for an organ the system could still use (#7).
            degrade = getattr(organ, "degrade", None)
            if callable(degrade):
                degrade("watchdog: max reboots exhausted")
            await self.bus.publish(
                Signal(
                    "watchdog.degraded",
                    {"organ": organ_id, "reboots": state.reboots},
                    source="watchdog",
                )
            )
            return
        state.backoff = self.base_backoff_s * (2**state.reboots)
        state.reboots += 1
        await self.bus.publish(
            Signal(
                "watchdog.reboot",
                {"organ": organ_id, "attempt": state.reboots, "backoff_s": state.backoff},
                source="watchdog",
            )
        )
        await asyncio.sleep(min(state.backoff, self.interval_s))
        with contextlib.suppress(Exception):
            await organ.shutdown()
            await organ.boot()

    async def _loop(self) -> None:
        try:
            while not self._stopped.is_set():
                await self.run_once()
                await asyncio.sleep(self.interval_s)
        except asyncio.CancelledError:  # pragma: no cover - shutdown path
            raise

    def diagnostics(self) -> dict[str, dict[str, float]]:
        return {
            organ_id: {
                "failures": float(state.failures),
                "reboots": float(state.reboots),
                "backoff_s": state.backoff,
            }
            for organ_id, state in self._states.items()
        }
