"""GANE Agent Layer — Autonomous Multi-Agent System built on BRAINIAC."""
from .memory import AgentMemory, Episode, Fact
from .tools import ToolRegistry, ToolResult
from .loop import AgentLoop, AgentConfig
from .agents import TelemetryAnalystAgent, MedicalContentAgent
from .router import AgentRouter

__all__ = [
    "AgentMemory",
    "Episode",
    "Fact",
    "ToolRegistry",
    "ToolResult",
    "AgentLoop",
    "AgentConfig",
    "TelemetryAnalystAgent",
    "MedicalContentAgent",
    "AgentRouter",
]
