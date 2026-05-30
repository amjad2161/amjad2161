from __future__ import annotations

import asyncio

import pytest

from singularity.kernel.resilience import (
    BulkheadFullError,
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
    ResiliencePolicy,
    RetryPolicy,
)


def test_circuit_opens_after_threshold():
    cb = CircuitBreaker(failure_threshold=3, reset_timeout_s=999, half_open_max_calls=1)
    assert cb.state is CircuitState.CLOSED
    for _ in range(3):
        cb.record_failure()
    assert cb.state is CircuitState.OPEN
    assert cb.allow() is False  # OPEN rejects calls


def test_circuit_half_opens_after_timeout_then_closes():
    cb = CircuitBreaker(failure_threshold=2, reset_timeout_s=0.0, half_open_max_calls=1)
    cb.record_failure()
    cb.record_failure()
    # reset_timeout 0 → immediately transitions to HALF_OPEN on inspection
    assert cb.state is CircuitState.HALF_OPEN
    assert cb.allow() is True
    cb.record_success()
    assert cb.state is CircuitState.CLOSED


def test_policy_retries_then_succeeds():
    attempts = {"n": 0}

    async def flaky():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise ValueError("transient")
        return {"ok": True}

    policy = ResiliencePolicy(name="t", retry=RetryPolicy(max_attempts=3, base_delay_s=0.0))
    result = asyncio.run(policy.execute(flaky))
    assert result == {"ok": True}
    assert attempts["n"] == 3


def test_policy_gives_up_and_opens_circuit():
    async def always_fail():
        raise RuntimeError("down")

    policy = ResiliencePolicy(
        name="t",
        retry=RetryPolicy(max_attempts=2, base_delay_s=0.0),
        breaker=CircuitBreaker(failure_threshold=2, reset_timeout_s=999),
    )
    with pytest.raises(RuntimeError):
        asyncio.run(policy.execute(always_fail))
    # two failures recorded → circuit open → next call short-circuits
    with pytest.raises(CircuitOpenError):
        asyncio.run(policy.execute(always_fail))


def test_timeout_is_enforced():
    async def slow():
        await asyncio.sleep(0.5)
        return {"ok": True}

    policy = ResiliencePolicy(name="t", retry=RetryPolicy(max_attempts=1), timeout_s=0.01)
    with pytest.raises(asyncio.TimeoutError):
        asyncio.run(policy.execute(slow))


def test_bulkhead_rejects_when_saturated():
    async def run():
        policy = ResiliencePolicy(name="t", retry=RetryPolicy(max_attempts=1),
                                  max_concurrent=1, timeout_s=None)
        started = asyncio.Event()

        async def hold():
            started.set()
            await asyncio.sleep(0.2)
            return {"ok": True}

        task = asyncio.create_task(policy.execute(hold))
        await started.wait()
        with pytest.raises(BulkheadFullError):
            await policy.execute(lambda: asyncio.sleep(0))
        await task

    asyncio.run(run())
