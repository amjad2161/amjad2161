"""Tests for agent/orchestrator compatibility layer."""
from __future__ import annotations

from unittest.mock import MagicMock

import anthropic
import pytest

from brainiac.agent import AgentLoop, AgentMemory, AgentRouter, build_default_tools
from brainiac.orchestrator import Brainiac, Mission, MissionType, SystemState


def test_agent_router_unicode_keywords() -> None:
    router = AgentRouter()
    assert router.route("חשב מסלול חירום") == "navigation"
    assert router.route("تحاليل مستشعر") == "telemetry"


def test_agent_memory_evicts_without_deadlock() -> None:
    memory = AgentMemory(max_facts=2)
    memory.store_fact("k1", 1)
    memory.store_fact("k2", 2)
    memory.store_fact("k3", 3)
    assert memory.get_fact("k1") is None
    assert memory.get_fact("k3") is not None


@pytest.mark.asyncio
async def test_agent_loop_handles_anthropic_api_error() -> None:
    calls = 0

    async def runner(_prompt: str, _route: str) -> str:
        nonlocal calls
        calls += 1
        raise anthropic.APIError("boom", request=MagicMock(), body=None)

    loop = AgentLoop(runner=runner, max_retries=1)
    result = await loop.run("do something")
    assert result["status"] == "error"
    assert calls == 2


def test_agent_tools_use_medical_protocols() -> None:
    tools = build_default_tools()
    assert "medical.list_drugs" in tools
    assert "epinephrine" in tools["medical.list_drugs"]()


@pytest.mark.asyncio
async def test_orchestrator_exports_and_mission_run() -> None:
    brainiac = Brainiac()
    mission = Mission(mission_id="m1", mission_type=MissionType.GENERAL, objective="ping")
    result = await brainiac.run_mission(mission)
    assert result["mission_id"] == "m1"
    assert brainiac.state == SystemState.ONLINE
