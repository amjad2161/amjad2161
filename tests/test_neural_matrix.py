"""Tests for NEURAL-MATRIX module."""

from __future__ import annotations

import pytest

from brainiac.core.neural_matrix import (
    AgentRole,
    AgentStatus,
    NeuralMatrix,
    TaskStatus,
    VoteMethod,
)


@pytest.fixture
def nm() -> NeuralMatrix:
    return NeuralMatrix()


# ── Agent Spawning ────────────────────────────────────────────────────────────


def test_spawn_agent_creates_agent(nm: NeuralMatrix) -> None:
    agent = nm.spawn_agent(AgentRole.ANALYST)
    assert agent.agent_id
    assert agent.role == AgentRole.ANALYST
    assert agent.status == AgentStatus.IDLE
    assert len(agent.capabilities) > 0


def test_spawn_agent_custom_name(nm: NeuralMatrix) -> None:
    agent = nm.spawn_agent(AgentRole.STRATEGIST, name="Strategic-1")
    assert agent.name == "Strategic-1"


def test_spawn_agent_custom_capabilities(nm: NeuralMatrix) -> None:
    caps = ["quantum_analysis", "deep_reasoning"]
    agent = nm.spawn_agent(AgentRole.ORACLE, capabilities=caps)
    assert agent.capabilities == caps


def test_spawn_all_roles(nm: NeuralMatrix) -> None:
    for role in AgentRole:
        agent = nm.spawn_agent(role)
        assert agent.role == role


def test_terminate_agent(nm: NeuralMatrix) -> None:
    agent = nm.spawn_agent(AgentRole.EXECUTOR)
    assert nm.terminate_agent(agent.agent_id) is True
    assert nm.get_agent(agent.agent_id) is None


def test_terminate_nonexistent_agent(nm: NeuralMatrix) -> None:
    assert nm.terminate_agent("does-not-exist") is False


def test_find_agents_by_capability(nm: NeuralMatrix) -> None:
    nm.spawn_agent(AgentRole.ANALYST)  # has data_analysis
    nm.spawn_agent(AgentRole.RESEARCHER)  # has information_retrieval
    found = nm.find_agents_by_capability("data_analysis")
    assert any(a.role == AgentRole.ANALYST for a in found)


def test_find_agents_by_capability_no_match(nm: NeuralMatrix) -> None:
    nm.spawn_agent(AgentRole.ANALYST)
    found = nm.find_agents_by_capability("telekinesis")
    assert found == []


# ── Task Decomposition ────────────────────────────────────────────────────────


def test_decompose_task_creates_graph(nm: NeuralMatrix) -> None:
    graph = nm.decompose_task(
        "Build a recommendation engine",
        [
            {"description": "Collect training data", "domain": "data"},
            {"description": "Train model", "domain": "ml", "dependencies": [0]},
            {"description": "Deploy API", "domain": "infra", "dependencies": [1]},
        ],
    )
    assert graph.graph_id
    assert graph.root_task == "Build a recommendation engine"
    assert len(graph.subtasks) == 3


def test_decompose_task_dependencies(nm: NeuralMatrix) -> None:
    graph = nm.decompose_task(
        "Multi-step task",
        [
            {"description": "Step 1", "domain": "A"},
            {"description": "Step 2", "domain": "B", "dependencies": [0]},
        ],
    )
    task_ids = list(graph.subtasks.keys())
    step2 = graph.subtasks[task_ids[1]]
    assert step2.dependencies == [task_ids[0]]


def test_assign_tasks_blocks_on_unmet_dependency(nm: NeuralMatrix) -> None:
    nm.spawn_agent(AgentRole.ANALYST)
    graph = nm.decompose_task(
        "Dependent tasks",
        [
            {"description": "Step 1", "domain": "A"},
            {"description": "Step 2", "domain": "B", "dependencies": [0]},
        ],
    )
    assignments = nm.assign_tasks(graph.graph_id)
    task_ids = list(graph.subtasks.keys())
    # Step 2 depends on Step 1 which is not complete yet → BLOCKED
    assert graph.subtasks[task_ids[1]].status == TaskStatus.BLOCKED
    assert assignments[task_ids[1]] is None


# ── Swarm Execution ───────────────────────────────────────────────────────────


async def test_execute_swarm_completes(nm: NeuralMatrix) -> None:
    nm.spawn_agent(AgentRole.ANALYST)
    nm.spawn_agent(AgentRole.EXECUTOR)
    graph = nm.decompose_task(
        "Parallel work",
        [
            {
                "description": "Analyse data",
                "domain": "analytics",
                "required_capabilities": ["data_analysis"],
            },
            {
                "description": "Execute workflow",
                "domain": "ops",
                "required_capabilities": ["task_execution"],
            },
        ],
    )
    result = await nm.execute_swarm(graph.graph_id)
    assert result.swarm_id
    assert result.task_graph_id == graph.graph_id
    assert result.elapsed_ms >= 0
    assert 0.0 <= result.confidence <= 1.0


async def test_execute_swarm_unknown_graph(nm: NeuralMatrix) -> None:
    with pytest.raises(KeyError):
        await nm.execute_swarm("nonexistent-graph-id")


async def test_execute_swarm_all_tasks_complete(nm: NeuralMatrix) -> None:
    nm.spawn_agent(AgentRole.RESEARCHER)
    graph = nm.decompose_task(
        "Research task",
        [
            {"description": "Search literature", "domain": "research"},
            {"description": "Synthesise findings", "domain": "research"},
        ],
    )
    result = await nm.execute_swarm(graph.graph_id)
    assert result.confidence == pytest.approx(1.0)


# ── Consensus Voting ──────────────────────────────────────────────────────────


def test_open_vote_creates_vote(nm: NeuralMatrix) -> None:
    vote = nm.open_vote("Best deployment strategy?", ["Blue-Green", "Canary", "Rolling"])
    assert vote.vote_id
    assert not vote.resolved
    assert vote.options == ["Blue-Green", "Canary", "Rolling"]


def test_cast_ballot_records_choice(nm: NeuralMatrix) -> None:
    agent = nm.spawn_agent(AgentRole.STRATEGIST)
    vote = nm.open_vote("Choose option", ["A", "B"])
    ok = nm.cast_ballot(vote.vote_id, agent.agent_id, "A")
    assert ok is True
    assert vote.ballots[agent.agent_id] == "A"


def test_resolve_majority_vote(nm: NeuralMatrix) -> None:
    a1 = nm.spawn_agent(AgentRole.ANALYST)
    a2 = nm.spawn_agent(AgentRole.ANALYST)
    a3 = nm.spawn_agent(AgentRole.CRITIC)
    vote = nm.open_vote("Best option", ["X", "Y"], VoteMethod.MAJORITY)
    nm.cast_ballot(vote.vote_id, a1.agent_id, "X")
    nm.cast_ballot(vote.vote_id, a2.agent_id, "X")
    nm.cast_ballot(vote.vote_id, a3.agent_id, "Y")
    resolved = nm.resolve_vote(vote.vote_id, quorum=0.0)
    assert resolved.result == "X"
    assert resolved.resolved is True


def test_resolve_weighted_vote(nm: NeuralMatrix) -> None:
    expert = nm.spawn_agent(AgentRole.ORACLE, expertise=0.95)
    novice = nm.spawn_agent(AgentRole.EXECUTOR, expertise=0.40)
    vote = nm.open_vote("Weighted vote", ["A", "B"], VoteMethod.WEIGHTED)
    nm.cast_ballot(vote.vote_id, expert.agent_id, "A")
    nm.cast_ballot(vote.vote_id, novice.agent_id, "B")
    resolved = nm.resolve_vote(vote.vote_id, quorum=0.0)
    assert resolved.result == "A"  # expert's weight dominates


def test_resolve_borda_vote(nm: NeuralMatrix) -> None:
    a1 = nm.spawn_agent(AgentRole.ANALYST)
    a2 = nm.spawn_agent(AgentRole.CRITIC)
    vote = nm.open_vote("Borda test", ["X", "Y", "Z"], VoteMethod.BORDA)
    nm.cast_ballot(vote.vote_id, a1.agent_id, ["X", "Y", "Z"])
    nm.cast_ballot(vote.vote_id, a2.agent_id, ["X", "Z", "Y"])
    resolved = nm.resolve_vote(vote.vote_id, quorum=0.0)
    assert resolved.result == "X"


def test_cast_ballot_on_resolved_vote_fails(nm: NeuralMatrix) -> None:
    agent = nm.spawn_agent(AgentRole.ANALYST)
    vote = nm.open_vote("Closed vote", ["A", "B"])
    nm.cast_ballot(vote.vote_id, agent.agent_id, "A")
    nm.resolve_vote(vote.vote_id, quorum=0.0)
    ok = nm.cast_ballot(vote.vote_id, agent.agent_id, "B")
    assert ok is False


def test_resolve_unknown_vote_raises(nm: NeuralMatrix) -> None:
    with pytest.raises(KeyError):
        nm.resolve_vote("no-such-vote")


# ── Knowledge Base ────────────────────────────────────────────────────────────


def test_contribute_and_retrieve_knowledge(nm: NeuralMatrix) -> None:
    nm.contribute_knowledge("physics", "speed_of_light", 299_792_458)
    kb = nm.retrieve_knowledge("physics")
    assert kb["speed_of_light"] == 299_792_458


def test_retrieve_unknown_domain_returns_empty(nm: NeuralMatrix) -> None:
    assert nm.retrieve_knowledge("alchemy") == {}


# ── Agent success_rate ────────────────────────────────────────────────────────


def test_agent_success_rate_initial(nm: NeuralMatrix) -> None:
    agent = nm.spawn_agent(AgentRole.EXECUTOR)
    assert agent.success_rate == pytest.approx(1.0)


# ── Diagnostics ───────────────────────────────────────────────────────────────


def test_diagnostics(nm: NeuralMatrix) -> None:
    nm.spawn_agent(AgentRole.ANALYST)
    nm.spawn_agent(AgentRole.SENTINEL)
    d = nm.diagnostics()
    assert d["status"] == "ONLINE"
    assert d["agents"] == 2
    assert "agents_by_role" in d
    assert "task_graphs" in d
    assert "votes" in d
