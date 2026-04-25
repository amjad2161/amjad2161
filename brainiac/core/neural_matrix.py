"""
NEURAL-MATRIX — Distributed Multi-Agent Swarm Intelligence
===========================================================
Role-based agent spawning, collective consensus voting,
task graph decomposition, swarm coordination, and
federated knowledge aggregation.

Provides BRAINIAC with a self-organising layer of specialised sub-agents
that can be spawned, assigned tasks, vote on decisions, and merge results —
modelling the emergent intelligence of a neural swarm.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import structlog

log = structlog.get_logger("brainiac.neural_matrix")


# ── Enumerations ──────────────────────────────────────────────────────────────


class AgentRole(str, Enum):
    ANALYST = "analyst"
    STRATEGIST = "strategist"
    EXECUTOR = "executor"
    CRITIC = "critic"
    COORDINATOR = "coordinator"
    RESEARCHER = "researcher"
    SENTINEL = "sentinel"  # security watchdog
    ORACLE = "oracle"  # prediction / forecasting


class AgentStatus(str, Enum):
    IDLE = "idle"
    ACTIVE = "active"
    PROCESSING = "processing"
    COMPLETE = "complete"
    FAILED = "failed"
    DORMANT = "dormant"


class TaskStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    FAILED = "failed"
    BLOCKED = "blocked"


class VoteMethod(str, Enum):
    MAJORITY = "majority"  # simple majority
    SUPERMAJORITY = "supermajority"  # ≥ 2/3
    WEIGHTED = "weighted"  # weight by agent expertise
    UNANIMOUS = "unanimous"  # all must agree
    BORDA = "borda"  # Borda count ranked voting


# ── Data Structures ───────────────────────────────────────────────────────────


@dataclass
class Agent:
    agent_id: str
    name: str
    role: AgentRole
    capabilities: list[str]
    expertise: float  # 0..1 — affects weighted voting
    status: AgentStatus = AgentStatus.IDLE
    tasks_completed: int = 0
    tasks_failed: int = 0
    spawned_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        total = self.tasks_completed + self.tasks_failed
        return self.tasks_completed / total if total > 0 else 1.0


@dataclass
class SubTask:
    task_id: str
    description: str
    domain: str
    required_capabilities: list[str]
    priority: int  # 1 (highest) … 10 (lowest)
    status: TaskStatus = TaskStatus.PENDING
    assigned_to: str | None = None  # agent_id
    result: Any = None
    created_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    dependencies: list[str] = field(default_factory=list)  # task_ids


@dataclass
class TaskGraph:
    graph_id: str
    root_task: str
    subtasks: dict[str, SubTask]  # task_id → SubTask
    created_at: float = field(default_factory=time.time)
    completed: bool = False

    @property
    def completion_rate(self) -> float:
        if not self.subtasks:
            return 0.0
        done = sum(1 for t in self.subtasks.values() if t.status == TaskStatus.COMPLETE)
        return done / len(self.subtasks)


@dataclass
class Vote:
    vote_id: str
    proposal: str
    options: list[str]
    method: VoteMethod
    ballots: dict[str, Any]  # agent_id → choice or ranking
    result: str | None = None
    tally: dict[str, float] = field(default_factory=dict)
    quorum_met: bool = False
    resolved: bool = False
    created_at: float = field(default_factory=time.time)


@dataclass
class SwarmResult:
    """Aggregated output from a parallel swarm execution."""

    swarm_id: str
    task_graph_id: str
    outputs: dict[str, Any]  # task_id → result
    consensus: str | None
    confidence: float
    total_agents: int
    elapsed_ms: float
    created_at: float = field(default_factory=time.time)


# ── Role capability table ──────────────────────────────────────────────────────

_ROLE_DEFAULT_CAPABILITIES: dict[AgentRole, list[str]] = {
    AgentRole.ANALYST: ["data_analysis", "pattern_recognition", "statistics", "reporting"],
    AgentRole.STRATEGIST: ["planning", "risk_assessment", "decision_making", "scenario_modelling"],
    AgentRole.EXECUTOR: ["task_execution", "api_calls", "automation", "workflow"],
    AgentRole.CRITIC: ["evaluation", "quality_assurance", "fact_checking", "red_teaming"],
    AgentRole.COORDINATOR: ["delegation", "scheduling", "communication", "monitoring"],
    AgentRole.RESEARCHER: [
        "information_retrieval",
        "synthesis",
        "hypothesis_generation",
        "citation",
    ],
    AgentRole.SENTINEL: ["threat_detection", "anomaly_detection", "access_control", "audit"],
    AgentRole.ORACLE: ["forecasting", "trend_analysis", "probability_estimation", "simulation"],
}

_ROLE_DEFAULT_EXPERTISE: dict[AgentRole, float] = {
    AgentRole.ANALYST: 0.85,
    AgentRole.STRATEGIST: 0.90,
    AgentRole.EXECUTOR: 0.75,
    AgentRole.CRITIC: 0.80,
    AgentRole.COORDINATOR: 0.70,
    AgentRole.RESEARCHER: 0.88,
    AgentRole.SENTINEL: 0.92,
    AgentRole.ORACLE: 0.87,
}


class NeuralMatrix:
    """
    NEURAL-MATRIX — multi-agent swarm intelligence for BRAINIAC.

    Features
    --------
    - Spawn role-based agents with capability profiles
    - Distribute task graphs across agents by capability matching
    - Parallel async swarm execution
    - Consensus voting (majority, supermajority, weighted, Borda)
    - Task graph decomposition with dependency resolution
    - Federated knowledge aggregation
    """

    def __init__(self) -> None:
        self._agents: dict[str, Agent] = {}
        self._task_graphs: dict[str, TaskGraph] = {}
        self._votes: dict[str, Vote] = {}
        self._swarm_results: list[SwarmResult] = []
        self._knowledge_base: dict[str, Any] = {}  # domain → knowledge chunks
        log.info("neural_matrix.init")

    # ── Agent Management ──────────────────────────────────────────────────────

    def spawn_agent(
        self,
        role: AgentRole,
        name: str | None = None,
        capabilities: list[str] | None = None,
        expertise: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Agent:
        """Spawn a new sub-agent with the given role."""
        agent_id = uuid.uuid4().hex[:12]
        agent = Agent(
            agent_id=agent_id,
            name=name or f"{role.value}-{agent_id[:6]}",
            role=role,
            capabilities=capabilities or list(_ROLE_DEFAULT_CAPABILITIES.get(role, [])),
            expertise=expertise
            if expertise is not None
            else _ROLE_DEFAULT_EXPERTISE.get(role, 0.7),
            metadata=metadata or {},
        )
        self._agents[agent_id] = agent
        log.info(
            "neural_matrix.agent_spawned",
            id=agent_id,
            role=role.value,
            name=agent.name,
        )
        return agent

    def terminate_agent(self, agent_id: str) -> bool:
        """Terminate and remove an agent."""
        agent = self._agents.pop(agent_id, None)
        if agent:
            log.info("neural_matrix.agent_terminated", id=agent_id, role=agent.role.value)
            return True
        return False

    def get_agent(self, agent_id: str) -> Agent | None:
        return self._agents.get(agent_id)

    def find_agents_by_capability(self, capability: str) -> list[Agent]:
        """Return all IDLE agents with the specified capability."""
        return [
            a
            for a in self._agents.values()
            if capability in a.capabilities and a.status == AgentStatus.IDLE
        ]

    # ── Task Decomposition ────────────────────────────────────────────────────

    def decompose_task(
        self,
        root_task: str,
        subtask_specs: list[dict[str, Any]],
    ) -> TaskGraph:
        """
        Decompose a complex task into a dependency graph of subtasks.

        Each item in ``subtask_specs`` should contain:
            - ``description`` (str)
            - ``domain`` (str)
        Optional keys:
            - ``required_capabilities`` (list[str])
            - ``priority`` (int, 1-10)
            - ``dependencies`` (list[task indices, 0-based])
        """
        subtasks: dict[str, SubTask] = {}
        task_ids: list[str] = []

        for spec in subtask_specs:
            tid = uuid.uuid4().hex[:12]
            task_ids.append(tid)
            subtasks[tid] = SubTask(
                task_id=tid,
                description=spec["description"],
                domain=spec.get("domain", "general"),
                required_capabilities=spec.get("required_capabilities", []),
                priority=spec.get("priority", 5),
            )

        # Resolve dependency indices to task IDs
        for i, spec in enumerate(subtask_specs):
            dep_indices: list[int] = spec.get("dependencies", [])
            subtasks[task_ids[i]].dependencies = [
                task_ids[j] for j in dep_indices if 0 <= j < len(task_ids)
            ]

        graph = TaskGraph(
            graph_id=uuid.uuid4().hex[:12],
            root_task=root_task,
            subtasks=subtasks,
        )
        self._task_graphs[graph.graph_id] = graph
        log.info(
            "neural_matrix.task_graph",
            id=graph.graph_id,
            subtasks=len(subtasks),
            root=root_task,
        )
        return graph

    def assign_tasks(self, graph_id: str) -> dict[str, str | None]:
        """
        Assign each PENDING subtask to the best available agent (by capability match).
        Returns {task_id: agent_id | None}.
        """
        graph = self._task_graphs.get(graph_id)
        if graph is None:
            raise KeyError(f"TaskGraph {graph_id!r} not found")

        assignment: dict[str, str | None] = {}
        for task in sorted(graph.subtasks.values(), key=lambda t: t.priority):
            if task.status != TaskStatus.PENDING:
                assignment[task.task_id] = task.assigned_to
                continue
            if not self._dependencies_met(task, graph):
                task.status = TaskStatus.BLOCKED
                assignment[task.task_id] = None
                continue

            agent = self._best_agent_for(task)
            if agent:
                task.assigned_to = agent.agent_id
                task.status = TaskStatus.ASSIGNED
                agent.status = AgentStatus.ACTIVE
                assignment[task.task_id] = agent.agent_id
                log.debug(
                    "neural_matrix.task_assigned",
                    task=task.task_id,
                    agent=agent.agent_id,
                )
            else:
                assignment[task.task_id] = None

        return assignment

    # ── Swarm Execution ───────────────────────────────────────────────────────

    async def execute_swarm(
        self,
        graph_id: str,
        handler: Any | None = None,
    ) -> SwarmResult:
        """
        Execute all assigned tasks in the graph concurrently.

        ``handler`` is an optional coroutine function
        ``async def handler(task: SubTask, agent: Agent) -> Any``
        that performs the actual work. If not provided, a no-op stub is used.
        """
        graph = self._task_graphs.get(graph_id)
        if graph is None:
            raise KeyError(f"TaskGraph {graph_id!r} not found")

        t0 = time.perf_counter()
        self.assign_tasks(graph_id)

        async def _run(task: SubTask) -> tuple[str, Any]:
            if task.status not in (TaskStatus.ASSIGNED, TaskStatus.PENDING):
                return task.task_id, None
            agent = self._agents.get(task.assigned_to or "")
            if agent:
                agent.status = AgentStatus.PROCESSING
                task.status = TaskStatus.IN_PROGRESS
            try:
                if handler:
                    result = await handler(task, agent)
                else:
                    await asyncio.sleep(0)  # yield to event loop
                    result = {
                        "task": task.description,
                        "domain": task.domain,
                        "agent": agent.name if agent else "unassigned",
                        "status": "stub_complete",
                    }
                task.status = TaskStatus.COMPLETE
                task.completed_at = time.time()
                task.result = result
                if agent:
                    agent.status = AgentStatus.IDLE
                    agent.tasks_completed += 1
                return task.task_id, result
            except Exception as exc:
                task.status = TaskStatus.FAILED
                if agent:
                    agent.status = AgentStatus.IDLE
                    agent.tasks_failed += 1
                log.error("neural_matrix.task_failed", task=task.task_id, error=str(exc))
                return task.task_id, None

        assigned = [
            t
            for t in graph.subtasks.values()
            if t.status in (TaskStatus.ASSIGNED, TaskStatus.PENDING)
        ]
        results_raw = await asyncio.gather(*[_run(t) for t in assigned])
        outputs: dict[str, Any] = dict(results_raw)

        elapsed = (time.perf_counter() - t0) * 1000
        graph.completed = all(t.status == TaskStatus.COMPLETE for t in graph.subtasks.values())

        # Build consensus from text results
        consensus = self._aggregate_consensus(outputs)

        swarm = SwarmResult(
            swarm_id=uuid.uuid4().hex[:12],
            task_graph_id=graph_id,
            outputs=outputs,
            consensus=consensus,
            confidence=graph.completion_rate,
            total_agents=len(self._agents),
            elapsed_ms=round(elapsed, 2),
        )
        self._swarm_results.append(swarm)
        log.info(
            "neural_matrix.swarm_complete",
            id=swarm.swarm_id,
            tasks=len(outputs),
            elapsed_ms=elapsed,
        )
        return swarm

    # ── Consensus Voting ──────────────────────────────────────────────────────

    def open_vote(
        self,
        proposal: str,
        options: list[str],
        method: VoteMethod = VoteMethod.MAJORITY,
    ) -> Vote:
        """Open a new vote on a proposal among the active agent swarm."""
        vote = Vote(
            vote_id=uuid.uuid4().hex[:12],
            proposal=proposal,
            options=options,
            method=method,
            ballots={},
        )
        self._votes[vote.vote_id] = vote
        log.info(
            "neural_matrix.vote_opened",
            id=vote.vote_id,
            method=method.value,
            options=options,
        )
        return vote

    def cast_ballot(self, vote_id: str, agent_id: str, choice: Any) -> bool:
        """
        Record a ballot for an agent.

        For MAJORITY / SUPERMAJORITY / WEIGHTED: ``choice`` is one of the option strings.
        For BORDA: ``choice`` is a list of options ranked from best (index 0) to worst.
        For UNANIMOUS: ``choice`` is an option string.
        """
        vote = self._votes.get(vote_id)
        if vote is None or vote.resolved:
            return False
        agent = self._agents.get(agent_id)
        if agent is None:
            return False
        vote.ballots[agent_id] = choice
        return True

    def resolve_vote(self, vote_id: str, quorum: float = 0.51) -> Vote:
        """Tally votes and determine the winning option."""
        vote = self._votes.get(vote_id)
        if vote is None:
            raise KeyError(f"Vote {vote_id!r} not found")
        if vote.resolved:
            return vote

        participating = len(vote.ballots)
        total_agents = max(len(self._agents), participating)
        vote.quorum_met = participating / max(total_agents, 1) >= quorum

        tally = self._tally(vote)
        vote.tally = tally
        vote.result = max(tally, key=lambda k: tally[k]) if tally else None
        vote.resolved = True
        log.info(
            "neural_matrix.vote_resolved",
            id=vote_id,
            result=vote.result,
            quorum=vote.quorum_met,
        )
        return vote

    # ── Knowledge Aggregation ─────────────────────────────────────────────────

    def contribute_knowledge(self, domain: str, key: str, value: Any) -> None:
        """Add a knowledge fragment to the shared base."""
        if domain not in self._knowledge_base:
            self._knowledge_base[domain] = {}
        self._knowledge_base[domain][key] = value

    def retrieve_knowledge(self, domain: str) -> dict[str, Any]:
        """Retrieve all knowledge for a domain."""
        return dict(self._knowledge_base.get(domain, {}))

    # ── Diagnostics ───────────────────────────────────────────────────────────

    def diagnostics(self) -> dict[str, Any]:
        role_counts: dict[str, int] = defaultdict(int)
        status_counts: dict[str, int] = defaultdict(int)
        for a in self._agents.values():
            role_counts[a.role.value] += 1
            status_counts[a.status.value] += 1

        return {
            "status": "ONLINE",
            "agents": len(self._agents),
            "agents_by_role": dict(role_counts),
            "agents_by_status": dict(status_counts),
            "task_graphs": len(self._task_graphs),
            "votes": len(self._votes),
            "swarms_executed": len(self._swarm_results),
            "knowledge_domains": list(self._knowledge_base.keys()),
        }

    # ── Internals ─────────────────────────────────────────────────────────────

    def _best_agent_for(self, task: SubTask) -> Agent | None:
        """Return the most capable idle agent for the task."""
        required = set(task.required_capabilities)
        candidates: list[Agent] = []

        for agent in self._agents.values():
            if agent.status != AgentStatus.IDLE:
                continue
            agent_caps = set(agent.capabilities)
            if not required or required & agent_caps:
                overlap = len(required & agent_caps) if required else 1
                candidates.append(agent)
                # annotate overlap for sorting (don't mutate Agent)
                agent.metadata["_match_score"] = overlap * agent.expertise * agent.success_rate

        if not candidates:
            return None
        return max(candidates, key=lambda a: a.metadata.get("_match_score", 0.0))

    @staticmethod
    def _dependencies_met(task: SubTask, graph: TaskGraph) -> bool:
        for dep_id in task.dependencies:
            dep = graph.subtasks.get(dep_id)
            if dep is None or dep.status != TaskStatus.COMPLETE:
                return False
        return True

    def _tally(self, vote: Vote) -> dict[str, float]:
        if vote.method == VoteMethod.BORDA:
            return self._borda_tally(vote)
        if vote.method == VoteMethod.WEIGHTED:
            return self._weighted_tally(vote)

        # Majority / Supermajority / Unanimous — simple count
        counts: dict[str, float] = dict.fromkeys(vote.options, 0.0)
        for ballot in vote.ballots.values():
            if ballot in counts:
                counts[ballot] += 1.0
        return counts

    def _weighted_tally(self, vote: Vote) -> dict[str, float]:
        totals: dict[str, float] = dict.fromkeys(vote.options, 0.0)
        for agent_id, ballot in vote.ballots.items():
            agent = self._agents.get(agent_id)
            weight = agent.expertise if agent else 1.0
            if ballot in totals:
                totals[ballot] += weight
        return totals

    @staticmethod
    def _borda_tally(vote: Vote) -> dict[str, float]:
        """
        Borda count: each option receives (n-rank) points where n = total options.
        """
        n = len(vote.options)
        scores: dict[str, float] = dict.fromkeys(vote.options, 0.0)
        for ranking in vote.ballots.values():
            if isinstance(ranking, list):
                for rank, option in enumerate(ranking):
                    if option in scores:
                        scores[option] += n - rank
        return scores

    @staticmethod
    def _aggregate_consensus(outputs: dict[str, Any]) -> str | None:
        """Simple consensus: the most common non-None string status in outputs."""
        statuses: list[str] = []
        for v in outputs.values():
            if isinstance(v, dict):
                s = v.get("status") or v.get("result")
                if isinstance(s, str):
                    statuses.append(s)
        if not statuses:
            return None
        return max(set(statuses), key=statuses.count)
