"""Tests for NEURO-CORE cost circuit breaker behavior."""

from __future__ import annotations

import pytest

from brainiac.core.neuro_core import CostLimitExceededError, NeuroCore


@pytest.mark.asyncio
async def test_cost_circuit_breaker_blocks_calls(monkeypatch):
    monkeypatch.setenv("BRAINIAC_MAX_USD_PER_HOUR", "0.000001")
    neuro = NeuroCore(api_key="test")

    # Simulate already-spent budget.
    neuro._hourly_cost_usd = 1.0

    with pytest.raises(CostLimitExceededError):
        await neuro.think("hello world", use_cache=False)


def test_cost_stats_shape(monkeypatch):
    monkeypatch.setenv("BRAINIAC_MAX_USD_PER_HOUR", "1.5")
    neuro = NeuroCore(api_key="test")

    stats = neuro.cost_stats()
    assert "hourly_input_tokens" in stats
    assert "hourly_output_tokens" in stats
    assert "hourly_cost_usd" in stats
    assert stats["max_usd_per_hour"] == pytest.approx(1.5)
