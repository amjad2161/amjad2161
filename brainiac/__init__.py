"""
G.A.N.E — Global Autonomous Navigation Engine
===============================================
Enterprise-grade autonomous AI platform with satellite-fused navigation,
multi-agent intelligence, medical protocols, and RTL-native localization.

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
from brainiac.core.localization import Localization, Language
from brainiac.core.medical_protocols import MedicalProtocols
from brainiac.core.ins import INS, PositionSource
from brainiac.agent import (
    AgentRouter, TelemetryAnalystAgent, MedicalContentAgent, NavigationAgent,
)

__version__ = "2.1.0"
__codename__ = "GANE"
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
    "Localization",
    "Language",
    "MedicalProtocols",
    "INS",
    "PositionSource",
    "AgentRouter",
    "TelemetryAnalystAgent",
    "MedicalContentAgent",
    "NavigationAgent",
]
