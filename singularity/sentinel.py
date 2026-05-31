"""SENTINEL — proactive, environment-reactive behaviour.

Until now JARVIS only *responds* to commands. The Sentinel makes it *act on its
own*: it continuously senses the environment (the camera's presence/motion, the
time of day, organ state) and reacts proactively — greeting you when you appear,
flagging motion when no one should be there, adapting to the hour. This is the
"notices you walk in and says good evening" behaviour — interactive and dynamic,
not waiting to be asked.

    from singularity import build_default_kernel, Sentinel
    async with build_default_kernel() as k:
        s = Sentinel(k, voice=v)
        await s.watch_forever(interval_s=20)
"""
from __future__ import annotations

from typing import Any


class Sentinel:
    """A proactive monitor that senses the environment and reacts on its own."""

    def __init__(self, kernel: Any, voice: Any = None, evolver: Any = None) -> None:
        self.kernel = kernel
        self.voice = voice
        self.evolver = evolver
        self._present = False
        self._greeted = False

    async def tick(self) -> dict[str, Any]:
        """One sense->react cycle. Returns what was sensed and any action taken."""
        import contextlib

        events: list[str] = []
        try:
            watch = await self.kernel.route("vision.watch", {"frames": 4})
        except Exception:
            watch = {}
        present = bool(watch.get("present"))
        motion = bool(watch.get("motion"))

        phase = "day"
        with contextlib.suppress(Exception):
            from .context import Context

            snap = await Context.snapshot(self.kernel, self.evolver)
            phase = str(snap.get("phase", "day"))

        if present and not self._present:
            # PROACTIVE: someone appeared -> greet (in JARVIS's voice), log, broadcast.
            greeting = f"Good {phase}. I see you — JARVIS is at your service."
            if self.voice is not None:
                with contextlib.suppress(Exception):
                    speak_as = getattr(self.voice, "speak_as", None)
                    if speak_as:
                        speak_as("jarvis", greeting)
                    else:
                        self.voice.speak(greeting)
            with contextlib.suppress(Exception):
                await self.kernel.bus.emit("sentinel.presence", {"phase": phase, "greeting": greeting})
            if self.evolver is not None:
                with contextlib.suppress(Exception):
                    self.evolver.store.memory_append("human", f"present in the {phase}")
            events.append("greeted_on_presence")
        elif motion and not present:
            with contextlib.suppress(Exception):
                await self.kernel.bus.emit(
                    "sentinel.motion", {"level": watch.get("motion_level"), "phase": phase})
            events.append("motion_alert")

        self._present = present
        return {"present": present, "motion": motion, "phase": phase, "events": events,
                "summary": watch.get("summary")}

    async def watch_forever(self, *, interval_s: float = 20.0,
                            max_ticks: int | None = None) -> None:
        import asyncio

        i = 0
        while max_ticks is None or i < max_ticks:
            i += 1
            r = await self.tick()
            if r["events"]:
                print(f"[sentinel] {r['summary']} -> {', '.join(r['events'])}")
            if max_ticks is not None and i >= max_ticks:
                break
            await asyncio.sleep(interval_s)
