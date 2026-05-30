"""The nervous system: an async pub/sub bus connecting every organ.

Modelled on the wildcard pub/sub of BRAINIAC's ``NexusSync`` and SkyCore's
``EventBus``. Topics are dotted strings (``organ.neuro.invoked``); subscribers
may use ``fnmatch`` globs or an MQTT-style ``#`` suffix wildcard, and ``#`` /
``*`` alone subscribe to everything.
"""

from __future__ import annotations

import asyncio
import fnmatch
from collections import deque
from typing import Awaitable, Callable

from .contracts import Signal

Handler = Callable[[Signal], "Awaitable[None] | None"]


class EventBus:
    """Lightweight, dependency-free async event bus with bounded history."""

    def __init__(self, history: int = 512) -> None:
        self._subs: dict[str, list[Handler]] = {}
        self._history: deque[Signal] = deque(maxlen=history)
        self._delivered = 0
        self._published = 0
        self._handler_errors = 0

    # -- subscription -----------------------------------------------------
    def subscribe(self, pattern: str, handler: Handler) -> Callable[[], None]:
        """Register ``handler`` for ``pattern``. Returns an unsubscribe callable."""

        self._subs.setdefault(pattern, []).append(handler)

        def _unsubscribe() -> None:
            handlers = self._subs.get(pattern)
            if handlers and handler in handlers:
                handlers.remove(handler)
                if not handlers:
                    self._subs.pop(pattern, None)

        return _unsubscribe

    # -- publishing -------------------------------------------------------
    async def publish(self, signal: Signal) -> int:
        """Deliver ``signal`` to all matching subscribers; returns delivery count."""

        self._history.append(signal)
        self._published += 1
        delivered = 0
        for pattern, handlers in list(self._subs.items()):
            if self._match(pattern, signal.topic):
                for handler in list(handlers):
                    try:
                        await self._dispatch(handler, signal)
                        delivered += 1
                    except Exception:  # noqa: BLE001
                        # A subscriber (logger / metrics / another organ) must
                        # never break the publisher — kernel.route() publishes on
                        # its hot path, so a raising observer would fail routing
                        # *after* the organ already ran. Isolate and tally it.
                        self._handler_errors += 1
        self._delivered += delivered
        return delivered

    async def emit(self, topic: str, payload: dict | None = None, source: str = "kernel") -> int:
        return await self.publish(Signal(topic=topic, payload=payload or {}, source=source))

    # -- inspection -------------------------------------------------------
    def history(self, pattern: str = "#") -> list[Signal]:
        return [s for s in self._history if self._match(pattern, s.topic)]

    @property
    def total_delivered(self) -> int:
        return self._delivered

    @property
    def total_published(self) -> int:
        return self._published

    # -- internals --------------------------------------------------------
    @staticmethod
    def _match(pattern: str, topic: str) -> bool:
        if pattern in ("#", "*", "**"):
            return True
        if pattern.endswith("#"):
            return topic.startswith(pattern[:-1])
        return fnmatch.fnmatch(topic, pattern)

    @staticmethod
    async def _dispatch(handler: Handler, signal: Signal) -> None:
        result = handler(signal)
        if asyncio.iscoroutine(result):
            await result
