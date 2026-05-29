"""The eight organs of the SINGULARITY.

Each organ is a thin adapter that projects one or more real repositories onto
the universal :class:`~singularity.kernel.contracts.Organ` contract. Every
organ boots in deterministic ``MOCK`` mode with zero dependencies and upgrades
to ``REAL`` when its backing repo / service / hardware is present.
"""

from __future__ import annotations

from .agents import AgentsOrgan
from .base import BaseOrgan
from .knowledge import KnowledgeOrgan
from .net import NetOrgan
from .neuro import NeuroOrgan
from .nexus import NexusOrgan
from .sky import SkyOrgan
from .trade import TradeOrgan
from .vision import VisionOrgan

__all__ = [
    "BaseOrgan",
    "NeuroOrgan",
    "AgentsOrgan",
    "KnowledgeOrgan",
    "SkyOrgan",
    "TradeOrgan",
    "VisionOrgan",
    "NexusOrgan",
    "NetOrgan",
]
