# SINGULARITY

> One hermetic kernel that fuses an entire constellation of repositories into a
> single autonomous superintelligence — every repo an **organ**, able to work
> **together** (one kernel, one nervous system, one API/CLI) and **apart** (each
> organ boots, self-heals and degrades to a deterministic mock).

`amjad2161`'s repositories were never separate projects. Read together they are
one recurring dream under many codenames — **BRAINIAC**, **JARVIS**, **GENESIS**,
**Nexus**, **Supreme**, **Autonomous**. SINGULARITY is the connective tissue that
makes that one organism real: a 2030-grade orchestration kernel that federates
**17 repositories** into **8 organs** behind a single, typed, async contract.

```
                                ┌───────────────────────────┐
                                │        SINGULARITY         │
                                │   kernel · bus · watchdog  │
                                │     governor · registry    │
                                └─────────────┬─────────────┘
        ┌──────────┬──────────┬──────────┬────┴─────┬──────────┬──────────┬──────────┐
      NEURO     AGENCY    KNOWLEDGE     SKY       TRADE     VISION     NEXUS       NET
   reasoning   personas    skills/    drones &   markets   media &   data plane  egress
    & loops   & routing    prompts   embodiment  & risk   creation  & telemetry  proxy
```

## Authenticity — real, not "as if"

Every organ runs **genuine code with honest provenance**, never a fake. When the
sibling repositories are checked out, four organs attach to and execute the
*actual* upstream code (verified by `singularity doctor` and
`tests/test_real_integration.py`):

| Organ | Real backend | Proof it is genuine |
|-------|--------------|---------------------|
| **sky** | `skycore` (Dji-owner) | Flies a real `SimulatorDrone` — real `WaypointMission`, real physics, battery actually drains; `_backend: "skycore"` |
| **agents** | `agency` (agency-agents) | Loads the **324 real personas** via `SkillRegistry`, routes through `SupremeJarvisBrain`; `_backend: "agency"` |
| **neuro** | `mythos` (Mythos) | Runs the genuine `MythosAgent` Reason→Act→Observe loop; `_backend: "mythos:stub"` (or `:anthropic` with a key) |
| **knowledge** | filesystem | Indexes **600+ real** `SKILL.md`/`agents`/prompt files off disk; `_backend: "filesystem-scan"` |

The remaining organs (**trade, vision, nexus, net**) are deterministic builtins —
real algorithms (SMA backtester, z-score anomaly detection, valid ComfyUI graphs,
correct proxy URLs), **honestly labelled** `_backend: "builtin"` — because their
upstreams require a running server / network / key (ComfyUI `:8188`, Supabase edge
functions, a node proxy, an exchange API). They upgrade to REAL the instant those
backends are reachable. **Every result carries a `_backend` field** declaring
exactly what produced it, and `_mode` (`real`/`mock`) — nothing pretends.

```bash
python -m singularity doctor   # real_backends: {skycore, agency, mythos, brainiac}; per-organ real/mock
```

## The federation at a glance

| Organ | Domain | Federates | Marquee intents |
|-------|--------|-----------|-----------------|
| **neuro** | reasoning | brainiac NeuroCore · Mythos · SuperAGI · anthropic SDK/quickstarts | `neuro.think`, `neuro.plan`, `neuro.autonomous_run` |
| **agents** | agency | agency-agents (JARVIS, 340 personas) · everything-claude-code | `agents.route`, `agents.run`, `agents.list` |
| **knowledge** | knowledge | skills · claude-code · claude-code-abc · system-prompts | `knowledge.search`, `knowledge.skills`, `knowledge.stats` |
| **sky** | embodiment | Dji-owner / SkyCore · agency robotics | `sky.mission_plan`, `sky.fly`, `sky.telemetry` |
| **trade** | economics | autonomous-trading-engine · tradingboy | `trade.signal`, `trade.backtest`, `trade.status` |
| **vision** | perception | ComfyUI · brainiac OmniVision/CreativeEngine | `vision.generate`, `vision.analyze`, `vision.creative` |
| **nexus** | dataplane | auto-save-sync (GMIN) · brainiac NexusSync/Telemetry/Shield | `nexus.publish`, `nexus.telemetry`, `nexus.sync`, `nexus.guard` |
| **net** | network | cors-anywhere | `net.proxy_url`, `net.describe_fetch` |

The full mapping (all 17 repos, languages, entrypoints, integration modes) is in
**[INTEGRATION_MAP.md](INTEGRATION_MAP.md)**; the design rationale is in
**[ARCHITECTURE.md](ARCHITECTURE.md)**.

## Upgrade layers (v1.1) — best-in-class OSS patterns, re-implemented

Beyond the organ federation, the kernel adopts (and re-implements, dependency-free)
the strongest patterns from across the open-source ecosystem so the organism is
reliable, composable, observable and interoperable:

| Layer | Module | Inspired by | What it adds |
|-------|--------|-------------|--------------|
| **Resilience** | `kernel/resilience.py` | [resilience4j](https://github.com/resilience4j/resilience4j) | Retry · CircuitBreaker (CLOSED/OPEN/HALF_OPEN) · Bulkhead · TimeLimiter wrapping every organ call |
| **Workflow DAG** | `kernel/workflow.py` | [LangGraph](https://github.com/langchain-ai/langgraph) | Declarative graph of intents over shared state — topological layers run in parallel, with conditional steps |
| **Blackboard** | `kernel/blackboard.py` | blackboard architecture + LangGraph reducers | Async-safe shared working memory with `append`/`merge` reducers and change history |
| **MCP surface** | `kernel/mcp.py` | [Model Context Protocol](https://modelcontextprotocol.io) | Exposes all 24 intents as MCP tools (`tools/list` + `tools/call`, JSON-RPC 2.0) — the singularity *is* a tool any agent can call |
| **Observability** | `kernel/observability.py` | Prometheus client model | Counters / gauges / histograms with labels, Prometheus text exposition |

```bash
python -m singularity workflow "survey a vineyard then hedge the harvest"  # run a DAG
python -m singularity mcp        # dump the MCP tools/list catalogue (24 tools)
python -m singularity metrics    # Prometheus exposition after a warm-up pulse
```

## Autonomy layers (v1.2) — the organism acts on its own

| Layer | Module | Inspired by | What it adds |
|-------|--------|-------------|--------------|
| **Autopilot** | `kernel/autopilot.py` | Mythos / agency AutonomousLoop / SuperAGI | Goal → `neuro.plan` → dispatch each task to the best organ → observe → `neuro.think` conclusion, under the governor's budget |
| **Scheduler** | `kernel/scheduler.py` | trading `scheduler` edge fn | Fire intents/workflows on an interval (cron-like) so the organism acts over time |
| **Config** | `kernel/config.py` | BRAINIAC `config.py` | One typed `SingularityConfig` from `SINGULARITY_*` env or TOML |
| **Policy** | `kernel/policy.py` | capability security / RBAC | Intent allow/deny (wildcards) + payload injection guard, enforced in `route()` |
| **Persistence** | `kernel/persistence.py` | LangGraph checkpointers | Memory + JSON checkpointers — snapshot/restore the blackboard for durable, resumable runs |
| **Tracing** | `kernel/kernel.py` | correlation IDs | Every `route()` carries a `trace_id` propagated through events and results |
| **Streaming** | `api/main.py` `/stream` | SSE | Live Server-Sent-Events feed of the nervous system |

```bash
python -m singularity autopilot "survey a vineyard then hedge the harvest"  # autonomous loop
python -m singularity doctor     # environment + health diagnostic
python -m singularity top         # live status table
```

```python
async with build_default_kernel() as kernel:
    run = await kernel.autopilot("survey, hedge, and brief the team", max_iterations=6)
    kernel.checkpoint("mission-1")          # durable snapshot of the blackboard
    print(run.organs_engaged, run.conclusion)
```

## Federation & realism (v1.5)

| Layer | Module | What it adds |
|-------|--------|--------------|
| **MCP client** | `kernel/mcp_client.py` | Consume *external* MCP servers: `kernel.mount_mcp(name, transport)` mounts their tools as live `ext.<name>.<tool>` intents — bidirectional MCP, federating the whole MCP ecosystem (proven by a loopback test) |
| **Real quant** | `organs/trade.py` | Genuine EMA-crossover + RSI signals and an event-driven backtester reporting return, **Sharpe**, **max-drawdown** and **win-rate** |
| **Real raster** | `organs/vision.py` | `vision.creative` emits a genuine, openable **PNG** (stdlib encoder + procedural art), not just an SVG string |
| **Vector recall** | `kernel/memory.py` | `memory.recall` upgraded to **TF-IDF cosine** retrieval (distinctive terms beat common ones) |

```python
# Federate another MCP server (or another SINGULARITY) as organs:
from singularity import build_default_kernel, InProcessTransport
a = build_default_kernel(); b = build_default_kernel()
await a.boot(); await b.boot()
await b.mount_mcp("alpha", InProcessTransport(a.mcp_bridge().handle))
await b.route("ext.alpha.trade-signal", {"symbol": "ETH_USDT"})   # runs on A, through B
```

## Reach & extensibility (v1.3)

| Layer | Module | Inspired by | What it adds |
|-------|--------|-------------|--------------|
| **Memory** | `kernel/memory.py` | agency `MemoryStore` / BRAINIAC sessions | Long-term, session-scoped memory with keyword recall; autopilot records goals + conclusions; persists via the checkpointer |
| **Plugins** | `kernel/plugins.py` | Python entry points | Third-party organs via the `singularity.organs` entry-point group or `SINGULARITY_PLUGINS=mod:Attr` — grow the body without editing the kernel |
| **Live dashboard** | `api/dashboard.py` | BRAINIAC / agency dashboards | Zero-build HTML page at `/` showing organ health, circuits, counters and a live event log (SSE) |
| **WebSocket** | `api/main.py` `/ws` | agency `/ws` | Full-duplex nervous-system feed, mirroring SSE |

```python
# Run with discovered third-party organs:
kernel = build_default_kernel(plugins=True)     # + SINGULARITY_PLUGINS=mypkg:WeatherOrgan
```

Compose an orchestration graph in code:

```python
from singularity import build_default_kernel, Workflow

wf = (Workflow("survey-and-hedge")
      .add_step("plan", "neuro.plan", {"goal": "survey + hedge"})
      .add_step("mission", "sky.mission_plan", {"lat": 38.5, "lon": -122.4, "points": 8},
                depends_on=["plan"])
      .add_step("fly", "sky.fly", lambda ctx: {"waypoints": ctx["mission"]["waypoints"]},
                depends_on=["mission"])
      .add_step("hedge", "trade.backtest", {"symbol": "BTC_USDT"}, depends_on=["plan"]))

async with build_default_kernel() as kernel:
    result = await kernel.run_workflow(wf)   # plan ∥ —, then mission ∥ hedge, then fly
```

## Why this is "singular and continuous"

* **One contract.** Every organ — Python library, HTTP service, on-disk asset
  corpus or Node subprocess — is projected onto the same
  `boot / shutdown / health / describe / invoke(intent, payload)` interface.
* **One source of truth.** [`singularity/kernel/ecosystem.py`](singularity/kernel/ecosystem.py)
  declares every repository exactly once and maps it to an organ.
* **Works apart.** The kernel core depends on **nothing but the standard library**.
  Every organ boots in deterministic **MOCK** mode with no keys, no hardware, no
  network — yet transparently upgrades to **REAL** when its backend is present
  (the knowledge organ, for example, indexes 600+ real skills/agents/prompts the
  moment the sibling repos are on disk).
* **Stays alive.** A watchdog resurrects dead organs with exponential backoff; a
  governor circuit-breaks runaway cost/rate on expensive intents.

## Quick start

```bash
pip install -e .                 # core kernel — zero third-party deps
python -m singularity status     # boot all 8 organs, print aggregated health
python -m singularity demo       # narrated showcase of organs working together
```

Drive a single capability, or one coherent cross-organ "heartbeat":

```bash
python -m singularity route neuro.plan '{"goal":"survey a vineyard then hedge the harvest"}'
python -m singularity route sky.mission_plan '{"kind":"survey","lat":38.5,"lon":-122.4,"points":8}'
python -m singularity route trade.backtest '{"symbol":"BTC_USDT","fast":3,"slow":8}'
python -m singularity pulse "Become a coherent autonomous organism"
```

Programmatic use:

```python
import asyncio
from singularity import build_default_kernel

async def main():
    async with build_default_kernel() as kernel:          # boots every organ
        thought = await kernel.route("neuro.think", {"prompt": "unify the fleet"})
        flight  = await kernel.route("sky.fly", {"lat": 37.0, "lon": -122.0})
        pulse   = await kernel.pulse("coordinate a survey-and-trade mission")
        print(kernel.status())

asyncio.run(main())
```

## HTTP gateway (optional)

```bash
pip install -e '.[api]'
python -m singularity serve --port 8088
# GET  /  (live dashboard)  /health /manifest /organs /intents /metrics
#      /blackboard /stream(SSE) /ws(WebSocket) /memory/recall /memory/sessions
# POST /route /pulse /autopilot /checkpoint /restore /memory/remember /mcp
#      (/mcp speaks MCP JSON-RPC: tools/list, tools/call)
```

## Layout

```
singularity/
├── kernel/
│   ├── contracts.py     # Organ protocol, Health, Capability, Signal, Domain
│   ├── event_bus.py     # async pub/sub nervous system (wildcard topics)
│   ├── ecosystem.py     # the 17-repo → 8-organ manifest (source of truth)
│   ├── registry.py      # intent → organ routing table
│   ├── governor.py      # cost/rate circuit breaker
│   ├── watchdog.py      # health supervision + backoff resurrection
│   ├── resilience.py    # retry · circuit breaker · bulkhead · time limiter
│   ├── workflow.py      # DAG orchestration engine over intents
│   ├── blackboard.py    # shared working memory (reducers + history)
│   ├── observability.py # metrics registry + Prometheus exposition
│   ├── mcp.py           # MCP tools/list + tools/call bridge
│   ├── autopilot.py     # autonomous plan→act→observe loop
│   ├── scheduler.py     # cron-like periodic intents/workflows
│   ├── config.py        # typed SingularityConfig (env / TOML)
│   ├── policy.py        # intent allow/deny + payload guard
│   ├── persistence.py   # memory + JSON checkpointers (durability)
│   ├── memory.py        # long-term session memory + recall
│   ├── plugins.py       # third-party organ discovery (entry points / specs)
│   └── kernel.py        # Singularity: boot/route/fanout/pulse/run_workflow/autopilot/status
├── organs/              # 8 mock-first adapters onto the universal contract
│   ├── base.py  neuro.py  agents.py  knowledge.py
│   └── sky.py   trade.py  vision.py  nexus.py  net.py
├── api/                 # FastAPI gateway + live dashboard
│   ├── main.py          #   /route /pulse /autopilot /mcp /stream /ws /memory/* ...
│   └── dashboard.py     #   zero-build live HTML dashboard at /
└── cli.py               # `singularity` command line (status/demo/workflow/autopilot/doctor/top/...)
examples/                # runnable scripts (quickstart, workflow, autopilot, mcp)
tests/                   # 86 tests, stdlib-only (no async plugin required)
```

## Testing

```bash
pip install -e '.[dev]'
pytest -q
```

## License

MIT.
