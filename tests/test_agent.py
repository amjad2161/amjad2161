"""
Tests for the GANE Agent Layer — mocked Anthropic client, no network.
"""
from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from brainiac.agent.memory import AgentMemory, Episode, Fact, FactSource, Decision
from brainiac.agent.tools import ToolDef, ToolRegistry, ToolResult
from brainiac.agent.loop import AgentLoop, AgentConfig
from brainiac.agent.agents import TelemetryAnalystAgent, MedicalContentAgent
from brainiac.agent.router import AgentRouter


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fake_message(text: str = "Analysis complete.", in_tok: int = 10, out_tok: int = 20):
    """Minimal Anthropic messages.create() response (end_turn, no tool calls)."""
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        stop_reason="end_turn",
        usage=SimpleNamespace(input_tokens=in_tok, output_tokens=out_tok),
    )


# ── Memory Tests ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_memory_save_and_retrieve_episode():
    mem = AgentMemory()
    ep = Episode(agent_name="test", prompt="hello", response="world")
    await mem.save_episode(ep)
    episodes = await mem.get_recent_episodes("test", n=5)
    assert len(episodes) == 1
    assert episodes[0].prompt == "hello"


@pytest.mark.asyncio
async def test_memory_store_and_search_facts():
    mem = AgentMemory()
    f = Fact(content="Sensor T-42 frequently spikes above threshold", source=FactSource.TELEMETRY, tags=["sensor", "T-42"])
    await mem.store_fact(f)
    results = await mem.search_facts("sensor T-42")
    assert len(results) >= 1
    assert results[0].fact_id == f.fact_id


@pytest.mark.asyncio
async def test_memory_search_facts_source_filter():
    mem = AgentMemory()
    await mem.store_fact(Fact(content="sensor data from T-42", source=FactSource.TELEMETRY))
    await mem.store_fact(Fact(content="sensor dosage info", source=FactSource.MEDICAL))
    results = await mem.search_facts("sensor", source=FactSource.MEDICAL)
    assert all(f.source == FactSource.MEDICAL for f in results)


@pytest.mark.asyncio
async def test_memory_decision_audit():
    mem = AgentMemory()
    dec = Decision(episode_id="ep-001", agent_name="analyst", tool_name="query_telemetry")
    await mem.record_decision(dec)
    decisions = await mem.get_decisions("ep-001")
    assert len(decisions) == 1
    assert decisions[0].tool_name == "query_telemetry"


@pytest.mark.asyncio
async def test_memory_cost_tracking():
    mem = AgentMemory()
    ep1 = Episode(cost_usd=0.01)
    ep2 = Episode(cost_usd=0.02)
    await mem.save_episode(ep1)
    await mem.save_episode(ep2)
    cost = await mem.daily_cost()
    assert abs(cost - 0.03) < 1e-9


@pytest.mark.asyncio
async def test_memory_diagnostics():
    mem = AgentMemory()
    await mem.save_episode(Episode())
    await mem.store_fact(Fact(content="test"))
    diag = mem.diagnostics()
    assert diag["episodes"] == 1
    assert diag["facts"] == 1


# ── Tool Registry Tests ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tool_call_success():
    registry = ToolRegistry(auto_approve=True)

    async def my_tool(x: int) -> int:
        return x * 2

    registry.register(ToolDef(
        name="double", description="doubles x",
        parameters={"type": "object", "properties": {"x": {"type": "integer"}}, "required": ["x"]},
        handler=my_tool,
        reversible=True,
    ))

    result = await registry.call("double", {"x": 5})
    assert result.success is True
    assert result.output == 10


@pytest.mark.asyncio
async def test_tool_call_unknown():
    registry = ToolRegistry()
    result = await registry.call("nonexistent", {})
    assert result.success is False
    assert "Unknown tool" in result.error


@pytest.mark.asyncio
async def test_tool_non_reversible_denied_without_auto_approve():
    registry = ToolRegistry(auto_approve=False)

    async def dangerous() -> str:
        return "EXECUTED"

    registry.register(ToolDef(
        name="danger", description="dangerous",
        parameters={"type": "object", "properties": {}},
        handler=dangerous,
        reversible=False,
    ))

    result = await registry.call("danger", {})
    assert result.success is False
    assert "denied" in result.error.lower()


@pytest.mark.asyncio
async def test_tool_non_reversible_approved_with_auto_approve():
    registry = ToolRegistry(auto_approve=True)

    async def safe_action() -> str:
        return "DONE"

    registry.register(ToolDef(
        name="action", description="action",
        parameters={"type": "object", "properties": {}},
        handler=safe_action,
        reversible=False,
    ))

    result = await registry.call("action", {})
    assert result.success is True


@pytest.mark.asyncio
async def test_tool_budget_exceeded():
    registry = ToolRegistry(auto_approve=True, budget_usd_per_day=0.001)

    async def noop() -> str:
        return "ok"

    registry.register(ToolDef(
        name="noop", description="noop",
        parameters={"type": "object", "properties": {}},
        handler=noop,
    ))

    result = await registry.call("noop", {}, cost_hint=1.0)
    assert result.success is False
    assert "budget" in result.error.lower()


@pytest.mark.asyncio
async def test_tool_timeout():
    registry = ToolRegistry(auto_approve=True)

    async def slow_tool() -> str:
        await asyncio.sleep(10)
        return "done"

    registry.register(ToolDef(
        name="slow", description="slow",
        parameters={"type": "object", "properties": {}},
        handler=slow_tool,
        timeout_s=0.01,
    ))

    result = await registry.call("slow", {})
    assert result.success is False
    assert "timed out" in result.error.lower()


def test_tool_get_schema():
    registry = ToolRegistry()
    registry.register(ToolDef(
        name="t1", description="desc",
        parameters={"type": "object", "properties": {}},
        handler=lambda: None,
    ))
    schema = registry.get_schema()
    assert len(schema) == 1
    assert schema[0]["name"] == "t1"
    assert "input_schema" in schema[0]


# ── AgentLoop Tests ───────────────────────────────────────────────────────────

@pytest.fixture
def mock_loop():
    """AgentLoop with mocked Anthropic client."""
    with patch("brainiac.agent.loop.anthropic.AsyncAnthropic") as mock_cls:
        client = MagicMock()
        client.messages.create = AsyncMock(return_value=_fake_message("Telemetry looks healthy."))
        mock_cls.return_value = client

        mem = AgentMemory()
        config = AgentConfig(
            name="test-agent",
            system_prompt="You are a test agent.",
            auto_approve_tools=True,
        )
        registry = ToolRegistry(auto_approve=True)
        loop = AgentLoop(config, registry, mem, api_key="fake-key")
        yield loop, client, mem


@pytest.mark.asyncio
async def test_agent_loop_run_returns_episode(mock_loop):
    loop, _, mem = mock_loop
    episode = await loop.run("Is everything OK?")
    assert episode.agent_name == "test-agent"
    assert episode.response == "Telemetry looks healthy."
    assert episode.success is True
    assert episode.tokens_used == 30


@pytest.mark.asyncio
async def test_agent_loop_episode_saved_in_memory(mock_loop):
    loop, _, mem = mock_loop
    await loop.run("Test prompt")
    episodes = await mem.get_recent_episodes("test-agent", n=1)
    assert len(episodes) == 1


@pytest.mark.asyncio
async def test_agent_loop_cost_computed(mock_loop):
    loop, _, _ = mock_loop
    episode = await loop.run("Cost test")
    assert episode.cost_usd > 0


# ── TelemetryAnalystAgent Tests ───────────────────────────────────────────────

@pytest.fixture
def mock_telemetry_agent():
    with patch("brainiac.agent.loop.anthropic.AsyncAnthropic") as mock_cls:
        client = MagicMock()
        client.messages.create = AsyncMock(return_value=_fake_message("No anomalies detected."))
        mock_cls.return_value = client
        agent = TelemetryAnalystAgent(auto_approve=True, api_key="fake")
        yield agent


@pytest.mark.asyncio
async def test_telemetry_analyst_analyze(mock_telemetry_agent):
    episode = await mock_telemetry_agent.analyze("Check all sensors")
    assert episode.agent_name == "telemetry-analyst"
    assert "anomalies" in episode.response.lower() or episode.success


@pytest.mark.asyncio
async def test_telemetry_analyst_tools_registered(mock_telemetry_agent):
    tools = mock_telemetry_agent._loop.tools.list_tools()
    tool_names = {t["name"] for t in tools}
    assert "query_telemetry" in tool_names
    assert "create_anomaly_report" in tool_names
    assert "acknowledge_anomaly" in tool_names


# ── MedicalContentAgent Tests ─────────────────────────────────────────────────

@pytest.fixture
def mock_medical_agent():
    with patch("brainiac.agent.loop.anthropic.AsyncAnthropic") as mock_cls:
        client = MagicMock()
        client.messages.create = AsyncMock(return_value=_fake_message("ACLS protocol generated."))
        mock_cls.return_value = client
        agent = MedicalContentAgent(auto_approve=True, api_key="fake")
        yield agent


@pytest.mark.asyncio
async def test_medical_agent_generate(mock_medical_agent):
    episode = await mock_medical_agent.generate("Generate ACLS protocol for VFib")
    assert episode.agent_name == "medical-content"
    assert episode.success is True


@pytest.mark.asyncio
async def test_medical_agent_tools_registered(mock_medical_agent):
    tools = mock_medical_agent._loop.tools.list_tools()
    tool_names = {t["name"] for t in tools}
    assert "generate_content" in tool_names
    assert "calculate_drug_dose" in tool_names


# ── AgentRouter Tests ─────────────────────────────────────────────────────────

def test_router_routing_telemetry():
    router = AgentRouter.__new__(AgentRouter)
    agent_name, reason = AgentRouter._route(router, "sensor T-42 shows anomaly")
    assert agent_name == "telemetry"


def test_router_routing_medical():
    router = AgentRouter.__new__(AgentRouter)
    agent_name, reason = AgentRouter._route(router, "generate ACLS protocol for epinephrine dosage")
    assert agent_name == "medical"


def test_router_routing_default():
    router = AgentRouter.__new__(AgentRouter)
    agent_name, reason = AgentRouter._route(router, "hello world")
    assert agent_name == "telemetry"   # default


@pytest.mark.asyncio
async def test_router_run_telemetry_prompt():
    with patch("brainiac.agent.loop.anthropic.AsyncAnthropic") as mock_cls:
        client = MagicMock()
        client.messages.create = AsyncMock(return_value=_fake_message("Sensor OK."))
        mock_cls.return_value = client

        router = AgentRouter(api_key="fake", auto_approve=True)
        result = await router.run("Check sensor T-42 anomaly")

    assert result.agent_used == "telemetry"
    assert result.episode.success is True
    assert result.total_ms > 0


@pytest.mark.asyncio
async def test_router_diagnostics():
    router = AgentRouter.__new__(AgentRouter)
    router.memory = AgentMemory()
    router._agents = {"telemetry": None, "medical": None}
    diag = router.diagnostics()
    assert "agents" in diag
    assert "memory" in diag
