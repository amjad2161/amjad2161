"""
BRAINIAC AI — Autonomous Super Intelligence System
===================================================
The most advanced autonomous AI platform ever built.

Quick start:
    >>> from brainiac import Brainiac, MissionType, Coordinate
    >>> bot = Brainiac()
    >>> await bot.boot()
    >>> await bot.ask("Plan me a drone route from A to B")
"""
from brainiac.orchestrator import (
    Brainiac, Mission, MissionType, SystemState, HealthReport,
)
from brainiac.core.orbital_nav import Coordinate, TransportMode, PrecisionMode
from brainiac.core.satlink import SOSPriority
from brainiac.core.telemetry_hub import SensorReading
from brainiac.core.nexus_sync import DeviceType, Protocol
from brainiac.core.neuro_core import ReasoningDepth
from brainiac.agent import AgentRouter, TelemetryAnalystAgent, MedicalContentAgent

__version__ = "1.0.1"
__codename__ = "GENESIS"
__author__ = "amjad2161"

__all__ = [
    "Brainiac",
    "Mission",
    "MissionType",
    "SystemState",
    "HealthReport",
    "Coordinate",
    "TransportMode",
    "PrecisionMode",
    "SOSPriority",
    "SensorReading",
    "DeviceType",
    "Protocol",
    "ReasoningDepth",
    "AgentRouter",
    "TelemetryAnalystAgent",
    "MedicalContentAgent",
]
