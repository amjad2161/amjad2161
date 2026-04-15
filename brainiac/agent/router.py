"""
GANE Agent Router — Multi-agent orchestrator that routes tasks to specialist agents.

The router:
  1. Analyzes the incoming prompt to determine the best agent
  2. Dispatches to the appropriate specialist
  3. Handles fallback and error recovery
  4. Maintains shared memory across all agents
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import structlog

from .memory import AgentMemory, Episode
from .agents import TelemetryAnalystAgent, MedicalContentAgent

if TYPE_CHECKING:
    from brainiac.core.telemetry_hub import TelemetryHub
    from brainiac.core.creative_engine import CreativeEngine

log = structlog.get_logger("brainiac.agent.router")

# Keyword routing rules: (pattern, agent_name)
_ROUTING_RULES = [
    (r"\b(sensor|telemetry|anomaly|temperature|pressure|voltage|reading|threshold)\b", "telemetry"),
    (r"\b(medical|drug|dose|protocol|acls|bls|cpr|epinephrine|resuscit|clinical|patient)\b", "medical"),
]


@dataclass
class RouterResult:
    """Result of a router dispatch."""
    agent_used: str
    episode: Episode
    routing_reason: str
    total_ms: float


class AgentRouter:
    """
    Multi-agent router that dispatches tasks to specialist agents.

    Shared memory means facts learned by one agent are available to all others.

    Example:
        router = AgentRouter(api_key="sk-...", telem=hub, creative=engine)
        result = await router.run("Check if sensor T-42 is anomalous")
    """

    def __init__(
        self,
        api_key: str | None = None,
        telem: "TelemetryHub | None" = None,
        creative: "CreativeEngine | None" = None,
        auto_approve: bool = True,
    ) -> None:
        self.memory = AgentMemory()
        self._agents: dict[str, Any] = {
            "telemetry": TelemetryAnalystAgent(
                memory=self.memory, telem=telem, api_key=api_key, auto_approve=auto_approve,
            ),
            "medical": MedicalContentAgent(
                memory=self.memory, creative=creative, api_key=api_key, auto_approve=auto_approve,
            ),
        }
        log.info("agent_router.init", agents=list(self._agents.keys()))

    async def run(self, prompt: str) -> RouterResult:
        """Route the prompt to the best agent and return the result."""
        t0 = time.perf_counter()
        agent_name, reason = self._route(prompt)
        agent = self._agents[agent_name]

        log.info("agent_router.dispatch", agent=agent_name, reason=reason)
        episode: Episode = await agent.analyze(prompt) if hasattr(agent, "analyze") else await agent.generate(prompt)

        return RouterResult(
            agent_used=agent_name,
            episode=episode,
            routing_reason=reason,
            total_ms=(time.perf_counter() - t0) * 1000,
        )

    def _route(self, prompt: str) -> tuple[str, str]:
        """Keyword-based routing; returns (agent_name, reason)."""
        prompt_lower = prompt.lower()
        for pattern, agent_name in _ROUTING_RULES:
            if re.search(pattern, prompt_lower, re.IGNORECASE):
                return agent_name, f"keyword match: {pattern[:30]}"
        return "telemetry", "default agent"

    def diagnostics(self) -> dict:
        return {
            "agents": list(self._agents.keys()),
            "memory": self.memory.diagnostics(),
        }
