"""Resilience — fault-tolerance decorators for organ invocations.

A compact, async, dependency-free adaptation of the resilience4j pattern set
(Retry · CircuitBreaker · Bulkhead · TimeLimiter). Composed in resilience4j's
default order — **Retry(CircuitBreaker(Bulkhead(TimeLimiter(call))))** — so each
attempt passes the circuit, concurrency is capped, and slow calls time out.

The whole singularity is built mock-first, so in normal operation organs never
fail and these guards are invisible; they exist to keep the organism alive when
real backends (LLMs, drones, exchanges, image servers) misbehave.
"""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")
Factory = Callable[[], Awaitable[T]]


class ResilienceError(RuntimeError):
    """Base class for resilience-layer rejections."""


class CircuitOpenError(ResilienceError):
    """Raised when a call is rejected because the circuit is OPEN."""


class BulkheadFullError(ResilienceError):
    """Raised when the concurrency bulkhead is saturated."""


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """A failure-rate state machine: CLOSED → OPEN → HALF_OPEN → CLOSED."""

    def __init__(
        self,
        *,
        failure_threshold: int = 5,
        reset_timeout_s: float = 30.0,
        half_open_max_calls: int = 1,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.reset_timeout_s = reset_timeout_s
        self.half_open_max_calls = half_open_max_calls
        self._state = CircuitState.CLOSED
        self._failures = 0
        self._opened_at = 0.0
        self._half_open_calls = 0

    @property
    def state(self) -> CircuitState:
        self._maybe_half_open()
        return self._state

    def allow(self) -> bool:
        self._maybe_half_open()
        if self._state is CircuitState.OPEN:
            return False
        if self._state is CircuitState.HALF_OPEN:
            if self._half_open_calls >= self.half_open_max_calls:
                return False
            self._half_open_calls += 1
        return True

    def record_success(self) -> None:
        self._failures = 0
        self._half_open_calls = 0
        self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        self._failures += 1
        if self._state is CircuitState.HALF_OPEN or self._failures >= self.failure_threshold:
            self._state = CircuitState.OPEN
            self._opened_at = time.monotonic()
            self._half_open_calls = 0

    def _maybe_half_open(self) -> None:
        if (
            self._state is CircuitState.OPEN
            and time.monotonic() - self._opened_at >= self.reset_timeout_s
        ):
            self._state = CircuitState.HALF_OPEN
            self._half_open_calls = 0

    def stats(self) -> dict[str, object]:
        return {"state": self.state.value, "failures": self._failures}


@dataclass
class RetryPolicy:
    max_attempts: int = 2
    base_delay_s: float = 0.0
    max_delay_s: float = 2.0
    jitter: float = 0.1

    def backoff(self, attempt: int) -> float:
        if self.base_delay_s <= 0:
            return 0.0
        delay = min(self.base_delay_s * (2**attempt), self.max_delay_s)
        return delay + random.uniform(0, self.jitter * delay)


@dataclass
class ResiliencePolicy:
    """Composes retry + circuit-breaker + bulkhead + timeout for one organ."""

    name: str = "default"
    retry: RetryPolicy = field(default_factory=RetryPolicy)
    timeout_s: float | None = 10.0
    max_concurrent: int = 32
    breaker: CircuitBreaker = field(default_factory=CircuitBreaker)
    _semaphore: asyncio.Semaphore | None = field(default=None, repr=False)

    def _sem(self) -> asyncio.Semaphore:
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.max_concurrent)
        return self._semaphore

    async def execute(self, factory: Factory[T]) -> T:
        last_exc: Exception | None = None
        for attempt in range(self.retry.max_attempts):
            if not self.breaker.allow():
                raise CircuitOpenError(f"circuit '{self.name}' is open")
            try:
                result = await self._guarded(factory)
                self.breaker.record_success()
                return result
            except (CircuitOpenError, BulkheadFullError):
                raise
            except Exception as exc:  # noqa: BLE001 - retry/record then maybe re-raise
                self.breaker.record_failure()
                last_exc = exc
                if attempt + 1 >= self.retry.max_attempts:
                    break
                delay = self.retry.backoff(attempt)
                if delay:
                    await asyncio.sleep(delay)
        assert last_exc is not None
        raise last_exc

    async def _guarded(self, factory: Factory[T]) -> T:
        sem = self._sem()
        if sem.locked():  # no permits available → fast-fail (public API)
            raise BulkheadFullError(f"bulkhead '{self.name}' full")
        async with sem:
            if self.timeout_s is not None:
                return await asyncio.wait_for(factory(), timeout=self.timeout_s)
            return await factory()

    def stats(self) -> dict[str, object]:
        return {"name": self.name, "circuit": self.breaker.stats(),
                "max_concurrent": self.max_concurrent, "timeout_s": self.timeout_s}


def default_policies(organ_ids: list[str] | set[str]) -> dict[str, ResiliencePolicy]:
    """Build a lenient default policy per organ (transparent for healthy mocks)."""

    return {oid: ResiliencePolicy(name=oid) for oid in organ_ids}
