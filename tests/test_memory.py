from __future__ import annotations

import asyncio

from singularity import build_default_kernel
from singularity.kernel.memory import SessionStore
from singularity.kernel.persistence import MemoryCheckpointer


def test_remember_and_recall_ranks_by_relevance():
    store = SessionStore()
    store.remember("the drone survey covered the north vineyard", role="assistant")
    store.remember("we hedged the harvest futures on the exchange", role="assistant")
    store.remember("vineyard vineyard vineyard mapping complete", role="assistant")
    hits = store.recall("vineyard", limit=2)
    assert len(hits) == 2
    assert "vineyard" in hits[0].content  # highest term frequency first


def test_sessions_are_isolated():
    store = SessionStore()
    store.remember("alpha", sid="a")
    store.remember("beta", sid="b")
    assert set(store.sessions()) == {"a", "b"}
    assert len(store.recall("alpha", sid="a")) == 1
    assert len(store.recall("alpha", sid="b")) == 0


def test_persistence_roundtrip():
    cp = MemoryCheckpointer()
    store = SessionStore(cp)
    store.remember("remember me", sid="s1", intent="note")
    assert store.save("mem") is True

    restored = SessionStore(cp)
    assert restored.load("mem") is True
    assert restored.summary("s1")["turns"] == 1


def test_autopilot_writes_to_kernel_memory():
    async def run():
        kernel = build_default_kernel(force_mock=True)
        await kernel.boot()
        await kernel.autopilot("survey the vineyard", max_iterations=2)
        sessions = kernel.memory.sessions()
        await kernel.shutdown()
        return sessions, kernel.memory

    sessions, memory = asyncio.run(run())
    assert any(s.startswith("autopilot:") for s in sessions)
    # goal + conclusion recorded
    assert len(memory.recall("vineyard")) >= 1
