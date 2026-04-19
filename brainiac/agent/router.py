from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RoutingRule:
    agent: str
    keywords: tuple[str, ...]
    priority: int


class AgentRouter:
    _ROUTING_RULES = (
        RoutingRule("medical", ("triage", "dose", "cardiac", "reading"), priority=100),
        RoutingRule("telemetry", ("sensor", "telemetry", "reading", "metric"), priority=80),
        RoutingRule("navigation", ("route", "gps", "nav", "eta"), priority=70),
    )

    def route(self, prompt: str) -> str:
        text = prompt.lower()
        for rule in sorted(self._ROUTING_RULES, key=lambda r: r.priority, reverse=True):
            if any(k in text for k in rule.keywords):
                return rule.agent
        return "telemetry"
