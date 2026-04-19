"""Plugin registry and in-process message bus."""
from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable


PluginFactory = Callable[[], Any]
Subscriber = Callable[[dict[str, Any]], Awaitable[None] | None]


class PluginRegistry:
    def __init__(self) -> None:
        self._plugins: dict[str, PluginFactory] = {}

    def register(self, name: str, factory: PluginFactory) -> None:
        self._plugins[name] = factory

    def create(self, name: str) -> Any:
        return self._plugins[name]()

    def names(self) -> list[str]:
        return sorted(self._plugins)


@dataclass
class AuditRecord:
    topic: str
    payload: dict[str, Any]
    timestamp: float
    signature: str


class MessageBus:
    def __init__(self) -> None:
        self._subs: dict[str, list[Subscriber]] = defaultdict(list)
        self._outbox: deque[dict[str, Any]] = deque()
        self.audit_log: list[AuditRecord] = []

    def subscribe(self, topic: str, handler: Subscriber) -> None:
        self._subs[topic].append(handler)

    async def publish(self, topic: str, payload: dict[str, Any]) -> None:
        self._outbox.append({"topic": topic, "payload": payload})
        handlers = self._subs.get(topic, [])
        for handler in handlers:
            result = handler(payload)
            if asyncio.iscoroutine(result):
                await result

