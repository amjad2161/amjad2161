"""
GANE Agent Router — Multi-agent orchestrator routing tasks to specialist agents.

The router:
  1. Classifies prompts via keyword routing
  2. Dispatches to the matching specialist via the BaseAgent.run() interface
  3. Maintains shared memory across all agents
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

from .agents import MedicalContentAgent, NavigationAgent, TelemetryAnalystAgent
from .base import BaseAgent
from .memory import AgentMemory, Episode

if TYPE_CHECKING:
    from brainiac.core.creative_engine import CreativeEngine
    from brainiac.core.orbital_nav import OrbitalNav
    from brainiac.core.telemetry_hub import TelemetryHub

log = structlog.get_logger("brainiac.agent.router")

# Routing rules: (compiled pattern, agent_name, label)
_ROUTING_RULES: list[tuple[re.Pattern, str, str]] = [
    (re.compile(r"\b(route|navigate|drive|drone|spacecraft|geofence|eta|coordinate|destination|origin|waypoint)\b", re.I), "navigation", "navigation"),
    (re.compile(r"\b(medical|drug|dose|protocol|acls|bls|cpr|epinephrine|resuscit|clinical|patient|aha)\b", re.I), "medical", "medical"),
    (re.compile(r"\b(sensor|telemetry|anomaly|temperature|pressure|voltage|reading|threshold|spike|drop|flatline)\b", re.I), "telemetry", "telemetry"),
]
_DEFAULT_AGENT = "telemetry"


@dataclass
class RouterResult:
    """Result of a router dispatch."""
    agent_used: str
    episode: Episode
    routing_reason: str
    total_ms: float


class AgentRouter:
    """Multi-agent router with shared memory across all specialist agents."""

    def __init__(
        self,
        api_key: str | None = None,
        telem: "TelemetryHub | None" = None,
        creative: "CreativeEngine | None" = None,
        nav: "OrbitalNav | None" = None,
        auto_approve: bool = True,
    ) -> None:
        self.memory = AgentMemory()
        self._agents: dict[str, BaseAgent] = {
            "telemetry": TelemetryAnalystAgent(
                memory=self.memory, telem=telem,
                api_key=api_key, auto_approve=auto_approve,
            ),
            "medical": MedicalContentAgent(
                memory=self.memory, creative=creative,
                api_key=api_key, auto_approve=auto_approve,
            ),
            "navigation": NavigationAgent(
                memory=self.memory, nav=nav,
                api_key=api_key, auto_approve=auto_approve,
            ),
        }
        log.info("agent_router.init", agents=list(self._agents.keys()))

    async def run(self, prompt: str, force_agent: str | None = None) -> RouterResult:
        """Route the prompt to the best agent (or a forced one) and return the result."""
        t0 = time.perf_counter()
        if force_agent and force_agent in self._agents:
            agent_name, reason = force_agent, "forced"
        else:
            agent_name, reason = self.route(prompt)
        agent = self._agents[agent_name]
        log.info("agent_router.dispatch", agent=agent_name, reason=reason)
        episode = await agent.run(prompt)
        return RouterResult(
            agent_used=agent_name,
            episode=episode,
            routing_reason=reason,
            total_ms=(time.perf_counter() - t0) * 1000,
        )

    @staticmethod
    def route(prompt: str) -> tuple[str, str]:
        """Keyword-based routing; returns (agent_name, reason)."""
        for pattern, agent_name, label in _ROUTING_RULES:
            if pattern.search(prompt):
                return agent_name, f"matched:{label}"
        return _DEFAULT_AGENT, "default"

    @property
    def agents(self) -> dict[str, BaseAgent]:
        return dict(self._agents)

    def diagnostics(self) -> dict:
        return {
            "agents": {name: agent.diagnostics() for name, agent in self._agents.items()},
            "memory": {
                "episodes_kept": self.memory._episodes.maxlen,
                "decisions_kept": self.memory._decisions.maxlen,
            },
        }
