"""Simple thread-safe in-memory fact store for agents."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MemoryFact:
    key: str
    value: Any
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentMemory:
    def __init__(self, max_facts: int = 1000) -> None:
        self.max_facts = max_facts
        self._facts: dict[str, MemoryFact] = {}
        self._order: list[str] = []
        self._lock = threading.RLock()

    def store_fact(self, key: str, value: Any, metadata: dict[str, Any] | None = None) -> MemoryFact:
        with self._lock:
            fact = MemoryFact(key=key, value=value, metadata=metadata or {})
            if key not in self._facts:
                self._order.append(key)
            self._facts[key] = fact
            while len(self._facts) > self.max_facts:
                self._evict_oldest_fact_locked()
            return fact

    def _evict_oldest_fact_locked(self) -> None:
        if not self._order:
            return
        oldest_key = self._order.pop(0)
        self._facts.pop(oldest_key, None)

    def get_fact(self, key: str) -> MemoryFact | None:
        with self._lock:
            return self._facts.get(key)

    def list_facts(self) -> list[MemoryFact]:
        with self._lock:
            return [self._facts[k] for k in self._order if k in self._facts]

    def diagnostics(self) -> dict[str, Any]:
        with self._lock:
            return {"status": "ONLINE", "facts": len(self._facts), "max_facts": self.max_facts}


__all__ = ["AgentMemory", "MemoryFact"]
