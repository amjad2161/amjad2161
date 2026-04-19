"""Tests for the GANE Agent Layer — mocked Anthropic client, no network."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from brainiac.agent.agents import (
    MedicalContentAgent,
    NavigationAgent,
    TelemetryAnalystAgent,
)
from brainiac.agent.base import BaseAgent
from brainiac.agent.loop import AgentConfig, AgentLoop
from brainiac.agent.memory import (
    AgentMemory,
    Decision,
    Episode,
    Fact,
    FactSource,
)
from brainiac.agent.router import AgentRouter
from brainiac.agent.tools import ToolDef, ToolRegistry


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fake_message(text: str = "Done.", in_tok: int = 10, out_tok: int = 20):
    """Anthropic messages.create() response (end_turn, no tool calls)."""
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        stop_reason="end_turn",
        usage=SimpleNamespace(
            input_tokens=in_tok, output_tokens=out_tok,
            cache_read_input_tokens=0, cache_creation_input_tokens=0,
        ),
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
    f = Fact(
        content="Sensor T-42 frequently spikes above threshold",
        source=FactSource.TELEMETRY,
        tags=["sensor", "T-42"],
    )
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
    await mem.save_episode(Episode(cost_usd=0.01))
    await mem.save_episode(Episode(cost_usd=0.02))
    assert abs(await mem.daily_cost() - 0.03) < 1e-9


@pytest.mark.asyncio
async def test_memory_diagnostics_is_async_and_locked():
    mem = AgentMemory()
    await mem.save_episode(Episode())
    await mem.store_fact(Fact(content="test"))
    diag = await mem.diagnostics()
    assert diag["episodes"] == 1
    assert diag["facts"] == 1
    assert "max_facts" in diag


@pytest.mark.asyncio
async def test_memory_facts_by_tag_uses_inverted_index():
    mem = AgentMemory()
    f1 = Fact(content="A", tags=["alpha", "shared"])
    f2 = Fact(content="B", tags=["beta", "shared"])
    f3 = Fact(content="C", tags=["gamma"])
    await mem.store_fact(f1)
    await mem.store_fact(f2)
    await mem.store_fact(f3)
    results = await mem.get_facts_by_tags(["shared"])
    assert {f.fact_id for f in results} == {f1.fact_id, f2.fact_id}


@pytest.mark.asyncio
async def test_memory_max_facts_evicts_lru():
    mem = AgentMemory(max_facts=2)
    f1 = Fact(content="oldest", tags=["a"])
    f2 = Fact(content="middle", tags=["b"])
    f3 = Fact(content="newest", tags=["c"])
    await mem.store_fact(f1)
    f1.accessed_at = 1.0
    await mem.store_fact(f2)
    f2.accessed_at = 2.0
    await mem.store_fact(f3)
    diag = await mem.diagnostics()
    assert diag["facts"] == 2
    by_tag = await mem.get_facts_by_tags(["a"])
    assert len(by_tag) == 0   # oldest evicted


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
        handler=dangerous, reversible=False,
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
        handler=safe_action, reversible=False,
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
        handler=slow_tool, timeout_s=0.01,
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


def test_tool_is_reversible_public_method():
    registry = ToolRegistry()
    registry.register(ToolDef(
        name="r", description="r",
        parameters={"type": "object", "properties": {}},
        handler=lambda: None, reversible=True,
    ))
    registry.register(ToolDef(
        name="nr", description="nr",
        parameters={"type": "object", "properties": {}},
        handler=lambda: None, reversible=False,
    ))
    assert registry.is_reversible("r") is True
    assert registry.is_reversible("nr") is False
    assert registry.is_reversible("missing") is True   # unknown defaults to reversible
    assert registry.has("r")
    assert not registry.has("missing")


# ── AgentLoop Tests ───────────────────────────────────────────────────────────

@pytest.fixture
def mock_loop():
    with patch("brainiac.agent.loop.anthropic.AsyncAnthropic") as mock_cls:
        client = MagicMock()
        client.messages.create = AsyncMock(return_value=_fake_message("Telemetry healthy."))
        mock_cls.return_value = client
        mem = AgentMemory()
        config = AgentConfig(
            name="test-agent",
            system_prompt="You are a test agent.",
            auto_approve_tools=True,
        )
        loop = AgentLoop(config, ToolRegistry(auto_approve=True), mem, api_key="fake-key")
        yield loop, client, mem


@pytest.mark.asyncio
async def test_agent_loop_run_returns_episode(mock_loop):
    loop, _, _ = mock_loop
    episode = await loop.run("Is everything OK?")
    assert episode.agent_name == "test-agent"
    assert episode.response == "Telemetry healthy."
    assert episode.success is True
    assert episode.tokens_used == 30


@pytest.mark.asyncio
async def test_agent_loop_episode_saved_in_memory(mock_loop):
    loop, _, mem = mock_loop
    await loop.run("Test prompt")
    episodes = await mem.get_recent_episodes("test-agent", n=1)
    assert len(episodes) == 1


@pytest.mark.asyncio
async def test_agent_loop_cost_includes_cache_factors(mock_loop):
    loop, _, _ = mock_loop
    episode = await loop.run("Cost test")
    assert episode.cost_usd > 0


@pytest.mark.asyncio
async def test_agent_loop_handles_api_error_gracefully():
    import anthropic
    with patch("brainiac.agent.loop.anthropic.AsyncAnthropic") as mock_cls:
        client = MagicMock()
        client.messages.create = AsyncMock(
            side_effect=anthropic.APIError("boom", request=MagicMock(), body=None),
        )
        mock_cls.return_value = client
        mem = AgentMemory()
        loop = AgentLoop(
            AgentConfig(name="err", system_prompt="x", auto_approve_tools=True),
            ToolRegistry(auto_approve=True), mem, api_key="fake-key",
        )
        episode = await loop.run("trigger error")
    assert episode.success is False
    assert episode.error and "boom" in episode.error


# ── TelemetryAnalystAgent Tests ───────────────────────────────────────────────

@pytest.fixture
def mock_telemetry_agent():
    with patch("brainiac.agent.loop.anthropic.AsyncAnthropic") as mock_cls:
        client = MagicMock()
        client.messages.create = AsyncMock(return_value=_fake_message("No anomalies."))
        mock_cls.return_value = client
        agent = TelemetryAnalystAgent(auto_approve=True, api_key="fake")
        yield agent


@pytest.mark.asyncio
async def test_telemetry_analyst_run(mock_telemetry_agent):
    episode = await mock_telemetry_agent.run("Check all sensors")
    assert episode.agent_name == "telemetry-analyst"


@pytest.mark.asyncio
async def test_telemetry_analyst_analyze_alias_works(mock_telemetry_agent):
    episode = await mock_telemetry_agent.analyze("Check all sensors")
    assert episode.agent_name == "telemetry-analyst"


def test_telemetry_analyst_extends_base_agent(mock_telemetry_agent):
    assert isinstance(mock_telemetry_agent, BaseAgent)


def test_telemetry_analyst_tools_registered(mock_telemetry_agent):
    tools = mock_telemetry_agent._loop.tools.list_tools()
    tool_names = {t["name"] for t in tools}
    assert {"query_telemetry", "create_anomaly_report", "acknowledge_anomaly"} <= tool_names


# ── MedicalContentAgent Tests ─────────────────────────────────────────────────

@pytest.fixture
def mock_medical_agent():
    with patch("brainiac.agent.loop.anthropic.AsyncAnthropic") as mock_cls:
        client = MagicMock()
        client.messages.create = AsyncMock(return_value=_fake_message("ACLS protocol."))
        mock_cls.return_value = client
        agent = MedicalContentAgent(auto_approve=True, api_key="fake")
        yield agent


@pytest.mark.asyncio
async def test_medical_agent_generate_alias(mock_medical_agent):
    episode = await mock_medical_agent.generate("ACLS for VFib")
    assert episode.agent_name == "medical-content"


def test_medical_agent_extends_base_agent(mock_medical_agent):
    assert isinstance(mock_medical_agent, BaseAgent)


def test_medical_agent_tools_registered(mock_medical_agent):
    tools = mock_medical_agent._loop.tools.list_tools()
    tool_names = {t["name"] for t in tools}
    assert {"generate_content", "calculate_drug_dose", "generate_badge_label"} <= tool_names


# ── NavigationAgent Tests ─────────────────────────────────────────────────────

@pytest.fixture
def mock_navigation_agent():
    with patch("brainiac.agent.loop.anthropic.AsyncAnthropic") as mock_cls:
        client = MagicMock()
        client.messages.create = AsyncMock(return_value=_fake_message("Route computed."))
        mock_cls.return_value = client
        agent = NavigationAgent(auto_approve=True, api_key="fake")
        yield agent


@pytest.mark.asyncio
async def test_navigation_agent_run(mock_navigation_agent):
    episode = await mock_navigation_agent.run("Route from Tel Aviv to Jerusalem")
    assert episode.agent_name == "navigation"


def test_navigation_agent_tools_registered(mock_navigation_agent):
    tools = mock_navigation_agent._loop.tools.list_tools()
    tool_names = {t["name"] for t in tools}
    assert {"estimate_eta", "compute_route", "multi_stop_route", "evaluate_geofence", "get_position"} <= tool_names


def test_navigation_agent_extends_base_agent(mock_navigation_agent):
    assert isinstance(mock_navigation_agent, BaseAgent)


# ── AgentRouter Tests ─────────────────────────────────────────────────────────

def test_router_route_telemetry_keyword():
    agent_name, reason = AgentRouter.route("sensor T-42 shows anomaly")
    assert agent_name == "telemetry"
    assert "matched" in reason


def test_router_route_medical_keyword():
    agent_name, reason = AgentRouter.route("generate ACLS protocol for epinephrine dosage")
    assert agent_name == "medical"


def test_router_route_navigation_keyword():
    agent_name, reason = AgentRouter.route("Compute the optimal drone route to destination")
    assert agent_name == "navigation"


def test_router_route_default():
    agent_name, reason = AgentRouter.route("hello world")
    assert agent_name == "telemetry"
    assert reason == "default"


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
async def test_router_force_agent_override():
    with patch("brainiac.agent.loop.anthropic.AsyncAnthropic") as mock_cls:
        client = MagicMock()
        client.messages.create = AsyncMock(return_value=_fake_message("Forced."))
        mock_cls.return_value = client
        router = AgentRouter(api_key="fake", auto_approve=True)
        result = await router.run("anything", force_agent="navigation")
    assert result.agent_used == "navigation"
    assert result.routing_reason == "forced"


@pytest.mark.asyncio
async def test_router_diagnostics_includes_all_agents():
    with patch("brainiac.agent.loop.anthropic.AsyncAnthropic") as mock_cls:
        mock_cls.return_value = MagicMock()
        router = AgentRouter(api_key="fake", auto_approve=True)
    diag = router.diagnostics()
    assert set(diag["agents"].keys()) == {"telemetry", "medical", "navigation"}
    assert "memory" in diag
