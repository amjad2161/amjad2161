"""
GANE Agent Memory — Persistent episode and fact store.

Provides a thread-safe in-memory store for:
  - Episodes   : completed reasoning sessions with full context
  - Facts      : distilled knowledge fragments (with vector-ready embeddings)
  - Decisions  : audit trail of every tool call and confirmation
"""
from __future__ import annotations

import asyncio
import hashlib
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
    facts_learned: list[str] = field(default_factory=list)   # fact_ids
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
    Thread-safe in-memory agent memory store.

    Provides:
    - Episode store (bounded ring buffer)
    - Fact store (dict keyed by fact_id)
    - Decision audit log (bounded ring buffer)
    - Simple keyword-based fact retrieval
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
        self._decisions: deque[Decision] = deque(maxlen=max_decisions)
        self._cost_today: float = 0.0
        self._cost_day: str = ""

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
        """Store a fact; returns fact_id."""
        async with self._lock:
            self._facts[fact.fact_id] = fact
            return fact.fact_id

    async def search_facts(self, query: str, source: FactSource | None = None, top_k: int = 5) -> list[Fact]:
        """Simple keyword-based fact retrieval (production: pgvector similarity)."""
        async with self._lock:
            query_lower = query.lower()
            query_words = set(query_lower.split())
            results = []
            for fact in self._facts.values():
                if source and fact.source != source:
                    continue
                fact_words = set(fact.content.lower().split())
                overlap = len(query_words & fact_words)
                if overlap > 0:
                    results.append((overlap, fact))
            results.sort(key=lambda x: x[0], reverse=True)
            top = [f for _, f in results[:top_k]]
            # Update access metadata
            now = time.time()
            for f in top:
                f.accessed_at = now
                f.access_count += 1
            return top

    async def get_facts_by_tags(self, tags: list[str]) -> list[Fact]:
        async with self._lock:
            tag_set = set(tags)
            return [f for f in self._facts.values() if tag_set & set(f.tags)]

    # ── Decisions ─────────────────────────────────────────────────────────────

    async def record_decision(self, decision: Decision) -> None:
        async with self._lock:
            self._decisions.append(decision)

    async def get_decisions(self, episode_id: str) -> list[Decision]:
        async with self._lock:
            return [d for d in self._decisions if d.episode_id == episode_id]

    # ── Cost Tracking ─────────────────────────────────────────────────────────

    async def daily_cost(self) -> float:
        async with self._lock:
            return self._cost_today

    async def reset_daily_cost(self) -> None:
        async with self._lock:
            self._cost_today = 0.0

    # ── Diagnostics ───────────────────────────────────────────────────────────

    def diagnostics(self) -> dict[str, Any]:
        return {
            "episodes": len(self._episodes),
            "facts": len(self._facts),
            "decisions": len(self._decisions),
            "cost_today_usd": round(self._cost_today, 6),
        }
