from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class Fact:
    text: str
    created_at: float = field(default_factory=time.time)
    accessed_at: float = field(default_factory=time.time)


class AgentMemory:
    def __init__(self, capacity: int = 256) -> None:
        self._capacity = capacity
        self._facts: list[Fact] = []

    def store_fact(self, text: str) -> None:
        now = time.time()
        self._facts.append(Fact(text=text, created_at=now, accessed_at=now))
        while len(self._facts) > self._capacity:
            self._evict_oldest_fact_locked()

    def search_facts(self, query: str, limit: int = 5) -> list[str]:
        terms = set(query.lower().split())
        ranked: list[tuple[int, float, Fact]] = []
        for fact in self._facts:
            overlap = len(terms.intersection(set(fact.text.lower().split())))
            fact.accessed_at = time.time()
            ranked.append((overlap, fact.accessed_at, fact))
        ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [item[2].text for item in ranked[:limit] if item[0] > 0]

    def _evict_oldest_fact_locked(self) -> None:
        idx = min(
            range(len(self._facts)),
            key=lambda i: (self._facts[i].accessed_at, self._facts[i].created_at),
        )
        self._facts.pop(idx)
