"""Policy — capability access control + payload guarding.

A governance gate enforced by the kernel before any organ runs: intent
allow/deny lists (with ``prefix.*`` wildcards) plus an optional prompt-injection
guard on string payloads. Default policy permits everything, so it is opt-in and
backward compatible — but it lets an operator lock the federation down to a safe
surface (e.g. expose only ``knowledge.*`` and ``neuro.think`` to an untrusted MCP
client).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .contracts import OrganError

_INJECTION = re.compile(
    r"(ignore (previous|all) instructions|rm\s+-rf|drop\s+table|<script|;\s*shutdown|\beval\()",
    re.IGNORECASE,
)


class PolicyError(OrganError):
    """Raised when a policy gate denies an invocation."""


@dataclass(slots=True)
class PolicyDecision:
    allowed: bool
    reason: str = "ok"


@dataclass
class PolicyGate:
    """Allow/deny intent routing and optionally guard payload text."""

    allow: list[str] | None = None  # None = allow all; else allow-list (wildcards ok)
    deny: list[str] = field(default_factory=list)
    guard_text: bool = False

    def check(self, intent: str, payload: dict[str, Any]) -> PolicyDecision:
        for pattern in self.deny:
            if self._match(pattern, intent):
                return PolicyDecision(False, f"intent {intent!r} denied by policy")
        if self.allow is not None and not any(self._match(p, intent) for p in self.allow):
            return PolicyDecision(False, f"intent {intent!r} not in allow-list")
        if self.guard_text:
            hit = self._scan(payload)
            if hit:
                return PolicyDecision(False, f"payload blocked: matched {hit!r}")
        return PolicyDecision(True)

    @staticmethod
    def _match(pattern: str, intent: str) -> bool:
        if pattern in ("*", "#"):
            return True
        if pattern.endswith(".*"):
            return intent.startswith(pattern[:-1])
        return pattern == intent

    @staticmethod
    def _scan(payload: dict[str, Any]) -> str | None:
        for value in payload.values():
            if isinstance(value, str):
                match = _INJECTION.search(value)
                if match:
                    return match.group(0)
        return None
