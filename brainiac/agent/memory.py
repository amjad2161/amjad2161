"""
GANE Agent Memory — Persistent episode and fact store.

Provides a thread-safe in-memory store for:
  - Episodes   : completed reasoning sessions with full context
  - Facts      : distilled knowledge fragments (with vector-ready embeddings)
  - Decisions  : audit trail of every tool call and confirmation
"""
from __future__ import annotations

import asyncio
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class FactSource(str, Enum):
    TELEMETRY = "telemetry"
    NAVIGATION = "navigation"
    MEDICAL = "medical"
    SECURITY = "security"
    CREATIVE = "creative"
    GENERAL = "general"


@dataclass
class Fact:
    """A distilled knowledge fragment stored in agent long-term memory."""
    fact_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    content: str = ""
    source: FactSource = FactSource.GENERAL
    confidence: float = 1.0
    tags: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    accessed_at: float = field(default_factory=time.time)
    access_count: int = 0


@dataclass
class Episode:
    """A completed agent reasoning session."""
    episode_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    agent_name: str = ""
    prompt: str = ""
    response: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    facts_learned: list[str] = field(default_factory=list)
    tokens_used: int = 0
    cost_usd: float = 0.0
    duration_ms: float = 0.0
    started_at: float = field(default_factory=time.time)
    success: bool = True
    error: str | None = None


@dataclass
class Decision:
    """Audit record of a single tool call decision."""
    decision_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    episode_id: str = ""
    agent_name: str = ""
    tool_name: str = ""
    tool_input: dict = field(default_factory=dict)
    tool_output: Any = None
    reversible: bool = True
    confirmed: bool = False
    executed_at: float = field(default_factory=time.time)
    duration_ms: float = 0.0
    error: str | None = None


class AgentMemory:
    """
    Thread-safe in-memory agent memory store with bounded capacity.

    Provides:
    - Episode store (bounded ring buffer)
    - Fact store (LRU-evicted at max_facts)
    - Decision audit log (bounded ring buffer)
    - Inverted-index keyword fact retrieval
    - Tag→fact_id index for O(1) tag lookup
    """

    def __init__(
        self,
        max_episodes: int = 500,
        max_decisions: int = 5000,
        max_facts: int = 10_000,
    ) -> None:
        self._lock = asyncio.Lock()
        self._episodes: deque[Episode] = deque(maxlen=max_episodes)
        self._facts: dict[str, Fact] = {}
        self._fact_tags: dict[str, set[str]] = {}     # fact_id → frozen tag set
        self._tag_index: dict[str, set[str]] = {}     # tag → set of fact_ids
        self._decisions: deque[Decision] = deque(maxlen=max_decisions)
        self._max_facts = max_facts
        self._cost_today: float = 0.0

    # ── Episodes ──────────────────────────────────────────────────────────────

    async def save_episode(self, episode: Episode) -> None:
        async with self._lock:
            self._episodes.append(episode)
            self._cost_today += episode.cost_usd

    async def get_recent_episodes(self, agent_name: str | None = None, n: int = 10) -> list[Episode]:
        async with self._lock:
            episodes = list(self._episodes)
        if agent_name:
            episodes = [e for e in episodes if e.agent_name == agent_name]
        return episodes[-n:]

    # ── Facts ─────────────────────────────────────────────────────────────────

    async def store_fact(self, fact: Fact) -> str:
        async with self._lock:
            if len(self._facts) >= self._max_facts and fact.fact_id not in self._facts:
                self._evict_oldest_fact_locked()
            self._facts[fact.fact_id] = fact
            tag_set = set(fact.tags)
            self._fact_tags[fact.fact_id] = tag_set
            for tag in tag_set:
                self._tag_index.setdefault(tag, set()).add(fact.fact_id)
            return fact.fact_id

    def _evict_oldest_fact_locked(self) -> None:
        """Evict the least-recently-accessed fact. Caller must hold the lock."""
        if not self._facts:
            return
        victim_id = min(self._facts, key=lambda fid: self._facts[fid].accessed_at)
        for tag in self._fact_tags.pop(victim_id, set()):
            ids = self._tag_index.get(tag)
            if ids:
                ids.discard(victim_id)
                if not ids:
                    self._tag_index.pop(tag, None)
        self._facts.pop(victim_id, None)

    async def search_facts(
        self,
        query: str,
        source: FactSource | None = None,
        top_k: int = 5,
    ) -> list[Fact]:
        """Keyword-overlap fact retrieval (production: pgvector similarity)."""
        # Snapshot under lock, then score outside the lock to minimize contention.
        async with self._lock:
            facts_snapshot = list(self._facts.values())

        query_words = set(query.lower().split())
        scored: list[tuple[int, Fact]] = []
        for fact in facts_snapshot:
            if source and fact.source != source:
                continue
            overlap = len(query_words & set(fact.content.lower().split()))
            if overlap > 0:
                scored.append((overlap, fact))
        scored.sort(key=lambda x: x[0], reverse=True)
        top = [f for _, f in scored[:top_k]]

        if top:
            now = time.time()
            async with self._lock:
                for f in top:
                    f.accessed_at = now
                    f.access_count += 1
        return top

    async def get_facts_by_tags(self, tags: list[str]) -> list[Fact]:
        """O(matching_facts) retrieval via inverted tag index."""
        async with self._lock:
            fact_ids: set[str] = set()
            for tag in tags:
                fact_ids |= self._tag_index.get(tag, set())
            return [self._facts[fid] for fid in fact_ids if fid in self._facts]

    # ── Decisions ─────────────────────────────────────────────────────────────

    async def record_decision(self, decision: Decision) -> None:
        async with self._lock:
            self._decisions.append(decision)

    async def get_decisions(self, episode_id: str) -> list[Decision]:
        async with self._lock:
            decisions_snapshot = list(self._decisions)
        return [d for d in decisions_snapshot if d.episode_id == episode_id]

    # ── Cost Tracking ─────────────────────────────────────────────────────────

    async def daily_cost(self) -> float:
        async with self._lock:
            return self._cost_today

    async def reset_daily_cost(self) -> None:
        async with self._lock:
            self._cost_today = 0.0

    # ── Diagnostics ───────────────────────────────────────────────────────────

    async def diagnostics(self) -> dict[str, Any]:
        async with self._lock:
            return {
                "episodes": len(self._episodes),
                "facts": len(self._facts),
                "tags_indexed": len(self._tag_index),
                "decisions": len(self._decisions),
                "cost_today_usd": round(self._cost_today, 6),
                "max_facts": self._max_facts,
            }
