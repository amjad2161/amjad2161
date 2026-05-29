"""The SINGULARITY kernel — the one organism that binds the organs.

Responsibilities:

* **Lifecycle** — boot/shutdown every organ concurrently, gracefully.
* **Routing** — turn an ``intent`` into an organ invocation, emitting signals.
* **Supervision** — run the watchdog so dead organs are resurrected.
* **Governance** — guard expensive intents through the governor.
* **Coherence** — a ``pulse`` that orchestrates organs *together* in one cycle.

It is the realisation of "work together and apart": each organ is independently
usable, yet the kernel composes them into a single continuous intelligence.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import TYPE_CHECKING, Any, Mapping

from .blackboard import Blackboard
from .config import SingularityConfig
from .contracts import OrganError, Signal
from .event_bus import EventBus
from .governor import Governor, GovernorError
from .memory import SessionStore
from .observability import Metrics
from .persistence import Checkpointer, MemoryCheckpointer
from .policy import PolicyError, PolicyGate
from .registry import OrganRegistry, build_default_registry
from .resilience import ResiliencePolicy
from .watchdog import Watchdog

if TYPE_CHECKING:  # pragma: no cover
    from .autopilot import AutopilotRun
    from .mcp import MCPBridge
    from .scheduler import Scheduler
    from .workflow import Workflow, WorkflowResult

# Intents considered "expensive" and therefore guarded by the governor.
_GUARDED_PREFIXES = ("neuro.", "agents.run", "vision.generate")


class Singularity:
    """The federated kernel over the whole ecosystem."""

    def __init__(
        self,
        registry: OrganRegistry | None = None,
        *,
        bus: EventBus | None = None,
        governor: Governor | None = None,
        resilience: dict[str, ResiliencePolicy] | None = None,
        metrics: Metrics | None = None,
        blackboard: Blackboard | None = None,
        policy: PolicyGate | None = None,
        checkpointer: Checkpointer | None = None,
        config: SingularityConfig | None = None,
        supervise: bool = False,
        watchdog_interval_s: float = 5.0,
    ) -> None:
        self.config = config or SingularityConfig()
        self.registry = registry or build_default_registry()
        self.bus = bus or EventBus()
        self.governor = governor or Governor()
        self.metrics = metrics or Metrics()
        self.blackboard = blackboard or Blackboard()
        self.policy = policy or PolicyGate()
        self.checkpointer = checkpointer or MemoryCheckpointer()
        self.memory = SessionStore(self.checkpointer)
        self.resilience = resilience or {
            o.id: ResiliencePolicy(
                name=o.id,
                timeout_s=getattr(o, "invoke_timeout_s", None) or self.config.request_timeout_s,
            )
            for o in self.registry
        }
        self._supervise = supervise or self.config.supervise
        self._booted = False
        self._booted_at = 0.0
        self.scheduler = self._build_scheduler()
        self.watchdog = Watchdog(
            organs={o.id: o for o in self.registry},
            bus=self.bus,
            interval_s=watchdog_interval_s or self.config.watchdog_interval_s,
        )

    def _build_scheduler(self) -> "Scheduler":
        from .scheduler import Scheduler

        return Scheduler(kernel=self, bus=self.bus)

    # -- lifecycle --------------------------------------------------------
    async def boot(self) -> dict[str, str]:
        """Boot every organ concurrently. Returns id -> liveness."""

        await self.bus.emit("kernel.booting", {"organs": len(self.registry)})
        await asyncio.gather(*(self._boot_one(o) for o in self.registry))
        if self._supervise:
            await self.watchdog.start()
            await self.scheduler.start()
        self._booted = True
        self._booted_at = time.time()
        report = {o.id: o.health().liveness.value for o in self.registry}
        await self.bus.emit("kernel.alive", {"report": report})
        return report

    async def shutdown(self) -> None:
        await self.bus.emit("kernel.shutting_down", {})
        if self._supervise:
            await self.scheduler.stop()
            await self.watchdog.stop()
        await asyncio.gather(
            *(self._shutdown_one(o) for o in self.registry), return_exceptions=True
        )
        self._booted = False
        await self.bus.emit("kernel.dormant", {})

    async def __aenter__(self) -> "Singularity":
        await self.boot()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.shutdown()

    async def _boot_one(self, organ: Any) -> None:
        try:
            await organ.boot()
        except Exception as exc:  # noqa: BLE001 - isolate organ failures
            await self.bus.emit("organ.boot_failed", {"organ": organ.id, "error": repr(exc)})

    async def _shutdown_one(self, organ: Any) -> None:
        try:
            await organ.shutdown()
        except Exception as exc:  # noqa: BLE001
            await self.bus.emit("organ.shutdown_failed", {"organ": organ.id, "error": repr(exc)})

    # -- routing ----------------------------------------------------------
    async def route(
        self,
        intent: str,
        payload: Mapping[str, Any] | None = None,
        *,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        """Route a single intent to its owning organ and return the result."""

        if not self._booted:
            raise OrganError("singularity is not booted")
        payload = dict(payload or {})
        trace_id = trace_id or uuid.uuid4().hex[:12]
        organ = self.registry.organ_for_intent(intent)

        decision = self.policy.check(intent, payload)
        if not decision.allowed:
            self.metrics.inc("singularity_route_denied_total", {"intent": intent})
            await self.bus.emit("kernel.denied", {"intent": intent, "reason": decision.reason})
            raise PolicyError(decision.reason)

        if intent.startswith(_GUARDED_PREFIXES):
            try:
                self.governor.check(est_usd=float(payload.get("_est_usd", 0.0)))
            except GovernorError as exc:
                await self.bus.emit("kernel.throttled", {"intent": intent, "error": str(exc)})
                raise

        await self.bus.emit(
            "organ.invoke", {"organ": organ.id, "intent": intent, "trace": trace_id}, source="kernel"
        )
        self.metrics.inc("singularity_route_total", {"organ": organ.id, "intent": intent})
        started = time.perf_counter()
        policy = self.resilience.get(organ.id)
        try:
            if policy is not None:
                result = await policy.execute(lambda: organ.invoke(intent, payload))
            else:
                result = await organ.invoke(intent, payload)
        except Exception as exc:  # noqa: BLE001 - record then re-raise
            self.metrics.inc("singularity_route_errors_total", {"organ": organ.id})
            await self.bus.emit(
                "organ.error", {"organ": organ.id, "intent": intent, "error": repr(exc)},
                source=organ.id,
            )
            raise
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        self.metrics.observe("singularity_route_latency_ms", elapsed_ms, {"organ": organ.id})

        if intent.startswith(_GUARDED_PREFIXES):
            self.governor.record(usd=float(result.get("_usd", 0.0)))

        result.setdefault("_trace", trace_id)
        await self.bus.publish(
            Signal(
                topic=f"organ.{organ.id}.result",
                payload={"intent": intent, "elapsed_ms": round(elapsed_ms, 2), "trace": trace_id},
                source=organ.id,
            )
        )
        return result

    async def fanout(
        self, calls: list[tuple[str, Mapping[str, Any] | None]]
    ) -> list[dict[str, Any]]:
        """Route many intents concurrently — organs working in parallel."""

        return list(await asyncio.gather(*(self.route(i, p) for i, p in calls)))

    # -- coherence --------------------------------------------------------
    async def pulse(self, goal: str) -> dict[str, Any]:
        """One coherent heartbeat across the organism.

        Demonstrates the organs cooperating: the reasoning core decomposes a
        goal into a plan, the agency picks an executor persona, the knowledge
        organ grounds it, and the data plane records telemetry — a single
        continuous thought spanning the whole federation.
        """

        if not self._booted:
            raise OrganError("singularity is not booted")
        await self.bus.emit("kernel.pulse", {"goal": goal})

        thought = await self.route("neuro.think", {"prompt": goal})
        plan = await self.route("neuro.plan", {"goal": goal})
        routing = await self.route("agents.route", {"request": goal})
        grounding = await self.route("knowledge.search", {"query": goal, "limit": 3})
        await self.route(
            "nexus.telemetry",
            {"sensor": "kernel.pulse", "value": float(len(plan.get("tasks", [])))},
        )

        return {
            "goal": goal,
            "thought": thought,
            "plan": plan,
            "chosen_agent": routing,
            "grounding": grounding,
            "organs_engaged": ["neuro", "agents", "knowledge", "nexus"],
        }

    # -- higher-order orchestration --------------------------------------
    async def run_workflow(
        self, workflow: "Workflow", context: dict[str, Any] | None = None
    ) -> "WorkflowResult":
        """Execute a declarative DAG of intents over the shared blackboard."""

        if not self._booted:
            raise OrganError("singularity is not booted")
        await self.bus.emit("kernel.workflow", {"name": workflow.name})
        return await workflow.run(self, context, blackboard=self.blackboard)

    def mcp_bridge(self) -> "MCPBridge":
        """Expose the federation as MCP tools (tools/list + tools/call)."""

        from .mcp import MCPBridge

        return MCPBridge(self)

    async def mount_mcp(self, name: str, transport: Any, *, domain: Any = None) -> Any:
        """Federate an external MCP server: mount its tools as live intents.

        ``transport`` is any object with ``async request(payload)`` (e.g.
        ``HTTPTransport(url)`` or ``InProcessTransport(other_kernel.mcp_bridge().handle)``).
        Its tools become routable as ``ext.<name>.<tool>``.
        """

        from .mcp_client import ExternalMCPOrgan

        organ = ExternalMCPOrgan(name, transport, domain=domain)
        await organ.boot()
        self.registry.register(organ)
        self.resilience[organ.id] = ResiliencePolicy(
            name=organ.id, timeout_s=self.config.request_timeout_s
        )
        self.watchdog.organs[organ.id] = organ
        await self.bus.emit(
            "kernel.mounted_mcp",
            {"server": name, "intents": len(organ.describe().capabilities)},
        )
        return organ

    async def autopilot(
        self, goal: str, *, max_iterations: int | None = None, context: dict[str, Any] | None = None
    ) -> "AutopilotRun":
        """Run a bounded autonomous plan → act → observe loop toward ``goal``."""

        from .autopilot import Autopilot

        if not self._booted:
            raise OrganError("singularity is not booted")
        iterations = max_iterations or self.config.autopilot_max_iterations
        return await Autopilot(self, max_iterations=iterations).run(goal, context)

    # -- durability -------------------------------------------------------
    def checkpoint(self, name: str = "default") -> str:
        """Persist the blackboard + status snapshot to the checkpointer."""

        self.checkpointer.save(
            name,
            {
                "saved_at": time.time(),
                "blackboard": self.blackboard.snapshot(),
                "status": self.status(),
            },
        )
        return name

    def restore(self, name: str = "default") -> bool:
        """Restore a previously checkpointed blackboard. Returns success."""

        state = self.checkpointer.load(name)
        if not state:
            return False
        for key, value in (state.get("blackboard") or {}).items():
            self.blackboard._data[key] = value  # noqa: SLF001 - intentional bulk restore
        return True

    # -- introspection ----------------------------------------------------
    def status(self) -> dict[str, Any]:
        health = [o.health().as_dict() for o in self.registry]
        alive = sum(1 for h in health if h["ok"])
        real = sum(1 for h in health if h["mode"] == "real")
        return {
            "booted": self._booted,
            "uptime_s": round(time.time() - self._booted_at, 1) if self._booted else 0.0,
            "organs": len(self.registry),
            "alive": alive,
            "real_mode": real,
            "mock_mode": len(self.registry) - real,
            "intents": len(self.registry.intents()),
            "events_published": self.bus.total_published,
            "events_delivered": self.bus.total_delivered,
            "governor": self.governor.stats(),
            "blackboard_keys": len(self.blackboard),
            "circuits": {oid: p.breaker.stats()["state"] for oid, p in self.resilience.items()},
            "scheduler_jobs": len(self.scheduler.jobs()),
            "checkpoints": len(self.checkpointer.list()),
            "memory_sessions": len(self.memory),
            "metrics": self.metrics.snapshot(),
            "health": health,
        }

    def manifest(self) -> dict[str, Any]:
        from .ecosystem import ECOSYSTEM

        return {
            "version": "1.6.0",
            "organs": [info.as_dict() for info in self.registry.describe_all()],
            "repos": [spec.as_dict() for spec in ECOSYSTEM],
            "intents": self.registry.intents(),
        }

    @property
    def booted(self) -> bool:
        return self._booted


def build_default_kernel(
    *,
    force_mock: bool = False,
    supervise: bool = False,
    plugins: bool = False,
    config: SingularityConfig | None = None,
) -> Singularity:
    """Build a kernel with the canonical 8-organ federation (+ optional plugins)."""

    config = config or SingularityConfig(force_mock=force_mock, supervise=supervise)
    governor = Governor(
        max_usd_per_hour=config.max_usd_per_hour,
        max_calls_per_minute=config.max_calls_per_minute,
    )
    return Singularity(
        build_default_registry(force_mock=config.force_mock or force_mock, include_plugins=plugins),
        governor=governor,
        config=config,
        supervise=supervise or config.supervise,
    )
