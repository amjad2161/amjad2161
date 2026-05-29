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
