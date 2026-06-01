"""REFLEXES — the autonomic nervous system: events trigger actions on their own.

The event bus already carries signals (``sentinel.motion``, ``organ.*`` health,
``trade`` anomalies …) and the Sentinel *emits* them — but until now nothing
*acted* on them automatically. Reflexes close the loop: each reflex subscribes to
a topic and, when it fires, routes a real organ intent **with no human in the
loop**. This is the spinal reflex arc — sense → react → act — that makes the whole
federation autonomic, not just responsive.

    from singularity import build_default_kernel, Sentinel, Reflexes
    async with build_default_kernel() as k:
        Reflexes(k, voice=v).arm()        # now the kernel reacts on its own
        await Sentinel(k, voice=v).watch_forever()

Reflexes are dynamic: add/remove them at runtime, gate them on a live condition,
and they react to whatever the bus carries — the "applies to everything, changes
with state" principle wired into the nervous system itself.
"""
from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Reflex:
    """One reflex arc: when ``on`` fires (and ``when`` holds), route ``intent``."""

    name: str
    on: str                                              # topic glob to listen for
    intent: str                                          # organ intent to fire
    payload: Callable[[Any], dict[str, Any]] = field(    # build payload from the Signal
        default=lambda sig: {})
    when: Callable[[Any], bool] = field(                 # extra live guard
        default=lambda sig: True)
    say: Callable[[Any, Any], str] | None = None         # optional spoken line (sig, result)


def default_reflexes() -> list[Reflex]:
    """The built-in autonomic behaviours — real intents, no GPU/keys needed."""
    return [
        # Motion while no one is present -> LOOK on your own and report what you see.
        Reflex(
            name="investigate-motion",
            on="sentinel.motion",
            intent="vision.analyze",
            payload=lambda sig: {},
            say=lambda sig, res: "Movement detected while no one is here. "
            + (str(res.get("description", "investigating"))[:160]
               if isinstance(res, dict) else "Investigating."),
        ),
    ]


class Reflexes:
    """An autonomic layer: subscribe reflexes to the bus; they act on their own."""

    def __init__(self, kernel: Any, voice: Any = None, evolver: Any = None) -> None:
        self.kernel = kernel
        self.voice = voice
        self.evolver = evolver
        self.reflexes: list[Reflex] = default_reflexes()
        self.fired: list[dict[str, Any]] = []            # audit trail
        self._unsubs: list[Callable[[], None]] = []
        self._tasks: set[asyncio.Task[Any]] = set()

    def add(self, reflex: Reflex) -> "Reflexes":
        self.reflexes.append(reflex)
        return self

    def arm(self) -> "Reflexes":
        """Subscribe every reflex to the bus. The kernel now reacts on its own."""
        for rx in self.reflexes:
            self._unsubs.append(self.kernel.bus.subscribe(rx.on, self._handler(rx)))
        return self

    def disarm(self) -> None:
        for unsub in self._unsubs:
            with contextlib.suppress(Exception):
                unsub()
        self._unsubs.clear()

    def _handler(self, rx: Reflex) -> Callable[[Any], None]:
        # Run the reflex OFF the publisher's hot path so a slow action (a camera
        # capture, an LLM call) never stalls whoever emitted the event.
        def handler(signal: Any) -> None:
            task = asyncio.create_task(self._fire(rx, signal))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

        return handler

    async def _fire(self, rx: Reflex, signal: Any) -> Any:
        # Never let a reflex react to a reflex -> no autonomic storm / infinite arc.
        if str(getattr(signal, "topic", "")).startswith("reflex."):
            return None
        if not _safe_bool(rx.when, signal):
            return None
        try:
            result = await self.kernel.route(rx.intent, rx.payload(signal) or {})
        except Exception:  # noqa: BLE001 - a reflex misfire must stay contained
            result = {"error": True}

        record = {"reflex": rx.name, "on": getattr(signal, "topic", ""), "intent": rx.intent}
        self.fired.append(record)
        with contextlib.suppress(Exception):
            await self.kernel.bus.emit("reflex.fired", record, source="reflexes")
        if rx.say is not None and self.voice is not None:
            with contextlib.suppress(Exception):
                line = rx.say(signal, result)
                speak_as = getattr(self.voice, "speak_as", None)
                speak_as("jarvis", line) if speak_as else self.voice.speak(line)
        if self.evolver is not None:
            with contextlib.suppress(Exception):
                self.evolver.store.memory_append(
                    "reflex", f"{rx.name} fired on {getattr(signal, 'topic', '')}")
        return result

    async def drain(self) -> None:
        """Await any in-flight reflex actions (useful for tests / shutdown)."""
        if self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)


def _safe_bool(fn: Callable[[Any], bool], signal: Any) -> bool:
    try:
        return bool(fn(signal))
    except Exception:  # noqa: BLE001
        return False
