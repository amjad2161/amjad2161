"""Resource governance: cost and rate circuit-breaking.

Ported in spirit from BRAINIAC's hourly USD cost breaker. The governor guards
expensive (typically LLM-backed) intents so an autonomous loop cannot run away
with spend or request volume. It is intentionally simple and synchronous.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field


class GovernorError(RuntimeError):
    """Raised when a guarded action exceeds its budget."""


@dataclass
class Governor:
    """A rolling-window cost + rate breaker."""

    max_usd_per_hour: float = 0.0  # 0 disables the cost breaker
    max_calls_per_minute: int = 0  # 0 disables the rate breaker
    _spend: deque[tuple[float, float]] = field(default_factory=deque, repr=False)
    _calls: deque[float] = field(default_factory=deque, repr=False)
    _reserved_usd: float = field(default=0.0, repr=False)

    def reserve(self, *, est_usd: float = 0.0) -> None:
        """Atomically check the budget **and** claim a call slot.

        This is the correct primitive for the async hot path: it is synchronous
        and contains no ``await``, so in asyncio's cooperative model no two
        coroutines can both pass before either claims its slot. The previous
        split (``check()`` before ``await organ.invoke()``, ``record()`` after)
        let N concurrent guarded calls all pass ``check()`` and then blow the
        budget — finding #5. The estimate is reserved up front and released by
        :meth:`commit` / :meth:`refund`.
        """
        now = time.time()
        self._evict(now)
        if self.max_calls_per_minute and len(self._calls) >= self.max_calls_per_minute:
            raise GovernorError(
                f"rate breaker open: {len(self._calls)} calls/min >= "
                f"{self.max_calls_per_minute}"
            )
        if self.max_usd_per_hour:
            spent = sum(usd for _, usd in self._spend) + self._reserved_usd
            if spent + est_usd > self.max_usd_per_hour:
                raise GovernorError(
                    f"cost breaker open: ${spent + est_usd:.4f}/hr > ${self.max_usd_per_hour:.4f}"
                )
        self._calls.append(now)
        self._reserved_usd += est_usd

    def commit(self, *, est_usd: float = 0.0, usd: float = 0.0) -> None:
        """Release the up-front reservation and record the actual spend."""
        self._reserved_usd = max(0.0, self._reserved_usd - est_usd)
        if usd:
            self._spend.append((time.time(), usd))
        self._evict(time.time())

    def refund(self, *, est_usd: float = 0.0) -> None:
        """The guarded call failed — give its cost reservation back."""
        self._reserved_usd = max(0.0, self._reserved_usd - est_usd)

    # -- legacy split API (kept for compatibility; prefer reserve/commit) -----
    def check(self, *, est_usd: float = 0.0) -> None:
        """Raise :class:`GovernorError` if this action would breach a budget."""

        now = time.time()
        self._evict(now)
        if self.max_calls_per_minute and len(self._calls) >= self.max_calls_per_minute:
            raise GovernorError(
                f"rate breaker open: {len(self._calls)} calls/min >= "
                f"{self.max_calls_per_minute}"
            )
        if self.max_usd_per_hour:
            spent = sum(usd for _, usd in self._spend)
            if spent + est_usd > self.max_usd_per_hour:
                raise GovernorError(
                    f"cost breaker open: ${spent + est_usd:.4f}/hr > ${self.max_usd_per_hour:.4f}"
                )

    def record(self, *, usd: float = 0.0) -> None:
        now = time.time()
        self._calls.append(now)
        if usd:
            self._spend.append((now, usd))
        self._evict(now)

    def stats(self) -> dict[str, float]:
        now = time.time()
        self._evict(now)
        return {
            "calls_last_minute": float(len(self._calls)),
            "usd_last_hour": float(sum(usd for _, usd in self._spend)),
            "max_usd_per_hour": self.max_usd_per_hour,
            "max_calls_per_minute": float(self.max_calls_per_minute),
        }

    def _evict(self, now: float) -> None:
        while self._calls and now - self._calls[0] > 60:
            self._calls.popleft()
        while self._spend and now - self._spend[0][0] > 3600:
            self._spend.popleft()
