"""
GANE Agent Base Interface — common contract for all specialist agents.

All concrete agents (TelemetryAnalystAgent, MedicalContentAgent, NavigationAgent, …)
extend BaseAgent and implement run(prompt). The router dispatches via this
single interface.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator

from .loop import AgentLoop
from .memory import AgentMemory, Episode


class BaseAgent(ABC):
    """Abstract base for all GANE specialist agents."""

    name: str
    memory: AgentMemory
    _loop: AgentLoop

    @abstractmethod
    async def run(self, prompt: str) -> Episode:
        """Execute the agent and return a completed Episode."""

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        """Default streaming impl — token-only, no tool calls."""
        async for token in self._loop.stream(prompt):
            yield token

    def diagnostics(self) -> dict:
        return {
            "name": self.name,
            "model": self._loop.config.model,
            "tools": self._loop.tools.diagnostics(),
        }
