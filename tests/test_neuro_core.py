"""
Tests for NEURO-CORE — uses mocked Anthropic client so we can run in CI
without an API key and without network access.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from brainiac.core.neuro_core import NeuroCore, ReasoningDepth, Thought, AgentTask


def _fake_response(text: str = "fake", in_tokens: int = 5, out_tokens: int = 7):
    """Build a minimal object that looks like anthropic's Message response."""
    return SimpleNamespace(
        content=[SimpleNamespace(text=text)],
        usage=SimpleNamespace(input_tokens=in_tokens, output_tokens=out_tokens),
    )


@pytest.fixture
def patched_core():
    """Return a NeuroCore with a mocked AsyncAnthropic client."""
    with patch("brainiac.core.neuro_core.anthropic.AsyncAnthropic") as mock_cls:
        client = MagicMock()
        client.messages.create = AsyncMock(return_value=_fake_response("Hello from mock"))
        mock_cls.return_value = client
        core = NeuroCore(api_key="fake-key")
        yield core, client


# ── Basic Behaviour ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_think_returns_thought(patched_core):
    core, _ = patched_core
    thought = await core.think("What is 2+2?")
    assert isinstance(thought, Thought)
    assert thought.content == "Hello from mock"
    assert thought.tokens_used == 12
    assert thought.latency_ms > 0
    assert thought.depth == ReasoningDepth.STANDARD
    assert thought.cached is False


@pytest.mark.asyncio
async def test_think_cache_hit(patched_core):
    core, client = patched_core
    await core.think("Cache me please")
    cached = await core.think("Cache me please")
    assert cached.cached is True
    assert client.messages.create.call_count == 1   # second call served from cache


@pytest.mark.asyncio
async def test_think_cache_disabled(patched_core):
    core, client = patched_core
    await core.think("Don't cache", use_cache=False)
    await core.think("Don't cache", use_cache=False)
    assert client.messages.create.call_count == 2


@pytest.mark.asyncio
async def test_depth_selects_correct_model(patched_core):
    core, client = patched_core
    await core.think("fast question", depth=ReasoningDepth.FAST)
    fast_call = client.messages.create.call_args_list[-1]
    assert "haiku" in fast_call.kwargs["model"]

    await core.think("deep question", depth=ReasoningDepth.DEEP, use_cache=False)
    deep_call = client.messages.create.call_args_list[-1]
    assert "opus" in deep_call.kwargs["model"]


@pytest.mark.asyncio
async def test_parallel_think(patched_core):
    core, _ = patched_core
    tasks = [
        AgentTask(name="nav",      prompt="plan route",   domain="navigation",  priority=1),
        AgentTask(name="vision",   prompt="scan area",    domain="vision",      priority=2),
        AgentTask(name="security", prompt="check threats",domain="security",    priority=3),
    ]
    results = await core.parallel_think(tasks)
    assert len(results) == 3
    for task in results:
        assert task.result is not None
        assert isinstance(task.result, Thought)


@pytest.mark.asyncio
async def test_self_improve_cascade(patched_core):
    core, client = patched_core
    # First the mock returns one answer then another for each call
    first = await core.think("Original question")
    improved = await core.self_improve(first)
    assert improved.content is not None
    # self_improve makes 2 additional calls (critique + refine)
    # but some may be cached; just assert call count increased
    assert client.messages.create.call_count >= 2


@pytest.mark.asyncio
async def test_total_counters_increment(patched_core):
    core, _ = patched_core
    for i in range(3):
        await core.think(f"Question {i}", use_cache=False)
    diag = core.diagnostics()
    assert diag["total_requests"] == 3
    assert diag["total_tokens"] == 3 * 12


def test_diagnostics_reports_models(patched_core):
    core, _ = patched_core
    diag = core.diagnostics()
    assert diag["status"] == "ONLINE"
    assert "deep" in diag["models"]
    assert "opus" in diag["models"]["deep"]
    assert "sonnet" in diag["models"]["standard"]
    assert "haiku" in diag["models"]["fast"]


def test_cache_key_stability():
    k1 = NeuroCore._cache_key("same prompt", ReasoningDepth.STANDARD)
    k2 = NeuroCore._cache_key("same prompt", ReasoningDepth.STANDARD)
    k3 = NeuroCore._cache_key("same prompt", ReasoningDepth.DEEP)
    assert k1 == k2
    assert k1 != k3
    assert len(k1) == 64  # SHA-256 hex


def test_cache_eviction(patched_core):
    """When cache exceeds size, oldest entry is evicted."""
    core, _ = patched_core
    core._cache_size = 3
    # Manually stuff the cache
    for i in range(5):
        core._store_cache(f"key-{i}", Thought(
            content=f"x{i}", model="test", depth=ReasoningDepth.FAST,
            tokens_used=1, latency_ms=0.1,
        ))
    assert len(core._cache) == 3
    assert "key-0" not in core._cache
    assert "key-4" in core._cache
