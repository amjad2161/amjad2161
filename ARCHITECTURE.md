# SINGULARITY — Architecture

This document explains *why* SINGULARITY is shaped the way it is, and how it
turns 17 heterogeneous repositories into one hermetic, continuous organism.

## 1. The thesis: one organism wearing many repos

Reading `amjad2161`'s repositories file-by-file reveals a single recurring
intent under rotating codenames — **BRAINIAC**, **JARVIS**, **GENESIS**,
**Nexus**, **Supreme**, **Autonomous**. The same engineering DNA repeats across
all of them:

* async modules with `diagnostics()` / `health()`,
* watchdog supervision with backoff,
* planner → executor → critic loops,
* mock-first design (everything runs offline, dependencies optional),
* a FastAPI/CLI surface per project.

They are not separate products; they are **organs of one body** that were never
connected. SINGULARITY is the **nervous system** that connects them.

## 2. The hermetic seam: the `Organ` contract

The central design decision is to collapse every subsystem — regardless of
language, runtime or transport — onto one tiny structural contract
([`kernel/contracts.py`](singularity/kernel/contracts.py)):

```python
class Organ(Protocol):
    id: str
    domain: Domain
    async def boot(self) -> None: ...
    async def shutdown(self) -> None: ...
    def health(self) -> Health: ...
    def describe(self) -> OrganInfo: ...
    async def invoke(self, intent: str, payload: Mapping) -> dict: ...
```

Everything else in the system depends only on this seam. A Python library
(SkyCore), an HTTP service (ComfyUI, Supabase edge functions), an on-disk asset
corpus (skills, prompts) and a Node subprocess (cors-anywhere) all look
identical to the kernel. This is what makes the federation *singular*: one verb
(`invoke`) over one address space (dotted `intent`s).

## 3. Mock-first duality: "together and apart"

Every organ extends [`BaseOrgan`](singularity/organs/base.py), which encodes a
strict rule: **the whole singularity must boot with zero third-party
dependencies, no credentials and no hardware.**

```
boot():
    try   _attach_real()   → Mode.REAL    (backend present)
    except                 → Mode.MOCK    (deterministic simulation)
```

* **Apart** — each organ is independently importable and usable; its mock is a
  real, deterministic implementation (the trade organ runs an actual
  SMA-crossover backtest; nexus does real z-score anomaly detection; knowledge
  parses real frontmatter; sky computes real orbit geometry).
* **Together** — the kernel composes them; `_attach_real()` transparently
  upgrades an organ when its repo/service is available. The **knowledge** organ
  is the clearest proof: with the sibling repos checked out it indexes 600+ real
  `SKILL.md` / `agents/*.md` / prompt files straight off disk and reports
  `Mode.REAL`, with no configuration.

This duality means the kernel is a faithful, runnable model of the full system
on a laptop, and the same code lights up to the real backends in production.

## 4. The kernel: lifecycle, routing, coherence

[`Singularity`](singularity/kernel/kernel.py) owns five responsibilities:

| Concern | Mechanism |
|---|---|
| **Lifecycle** | `boot()` / `shutdown()` start and stop every organ *concurrently* (`asyncio.gather`); `async with` context manager support. |
| **Routing** | `route(intent, payload)` resolves the owning organ via the registry's intent index, invokes it, and emits signals. `fanout()` runs many intents in parallel. |
| **Coherence** | `pulse(goal)` is one heartbeat that threads a goal through *several* organs (neuro → agents → knowledge → nexus), demonstrating cooperation, not just isolation. |
| **Supervision** | An optional [`Watchdog`](singularity/kernel/watchdog.py) polls health and resurrects `DOWN` organs with exponential backoff, marking them `DEGRADED` after exhausting retries. |
| **Governance** | A [`Governor`](singularity/kernel/governor.py) circuit-breaks expensive intents (`neuro.*`, `agents.run`, `vision.generate`) on rolling cost/rate budgets. |

### Routing table

The [`OrganRegistry`](singularity/kernel/registry.py) builds an
`intent → organ` index at registration time and **rejects collisions**, so the
24 intents form a clean, conflict-free namespace. Adding a repo is: declare it
in `ecosystem.py`, implement (or extend) an organ, register it.

## 5. The nervous system: the event bus

[`EventBus`](singularity/kernel/event_bus.py) is a dependency-free async pub/sub
with wildcard topics (`organ.neuro.#`, `watchdog.#`, `#`). The kernel narrates
itself on it — `kernel.booting`, `organ.invoke`, `organ.<id>.result`,
`watchdog.reboot`, `kernel.throttled` — so observers (dashboards, loggers, other
organs) can subscribe without coupling to the kernel internals. It is modelled
on BRAINIAC's `NexusSync` wildcard mesh and SkyCore's `EventBus`.

## 6. The manifest: a single source of truth

[`ecosystem.py`](singularity/kernel/ecosystem.py) declares all 17 repositories
once — repo, organ, domain, language, integration mode, entrypoint, mock
readiness, role. [`INTEGRATION_MAP.md`](INTEGRATION_MAP.md) is generated from it,
so documentation cannot drift from code. The registry test asserts every repo
maps to a live organ and that the count stays at 17.

## 7. Surfaces

* **CLI** ([`cli.py`](singularity/cli.py)) — `status`, `organs`, `manifest`,
  `intents`, `route`, `pulse`, `demo`, `serve`. Stdlib-only (`argparse`).
* **HTTP gateway** ([`api/main.py`](singularity/api/main.py)) — optional FastAPI
  app with a lifespan that boots/supervises/stops the kernel; routes for health,
  manifest, organs, intents, route and pulse. Import is lazy so the core never
  requires FastAPI.

## 8. Dependency posture (2030-grade restraint)

* **Core kernel: standard library only.** No runtime third-party imports in
  `kernel/` or `organs/`. This is deliberate — the connective tissue must never
  be the thing that fails to install.
* **Heavy capability = optional extra.** FastAPI/uvicorn live behind the `api`
  extra; each organ's real backend is an optional, lazily-imported upgrade.
* **Typed throughout** (`py.typed`, dataclasses, `Protocol`s), `ruff`/`mypy`
  configured, 40 stdlib-only tests covering contracts, bus, registry, governor,
  watchdog, every organ and the kernel.

## 9. Upgrade layers — adopting the best of the OSS ecosystem

The kernel deliberately mines proven open-source patterns and re-implements them
dependency-free, so the organism is not just connected but *production-grade*.

### 9.1 Resilience ([`resilience.py`](singularity/kernel/resilience.py))

A compact async adaptation of **resilience4j**. Every organ call is wrapped in a
`ResiliencePolicy` composing — in resilience4j's canonical order —
**Retry → CircuitBreaker → Bulkhead → TimeLimiter**:

* **CircuitBreaker** is a CLOSED → OPEN → HALF_OPEN state machine that fails fast
  once an organ's failure threshold is crossed, then probes recovery.
* **Retry** re-attempts transient failures with exponential backoff + jitter.
* **Bulkhead** caps concurrency per organ (semaphore) to prevent resource
  monopolisation.
* **TimeLimiter** bounds slow calls via `asyncio.wait_for`.

Because every organ is mock-first and healthy by default, these guards are
invisible in normal operation — they exist for the day a real LLM, exchange,
drone or image server misbehaves. Circuit state is surfaced in `kernel.status()`.

### 9.2 Workflow DAG ([`workflow.py`](singularity/kernel/workflow.py))

Adapted from **LangGraph**'s state-graph model. A `Workflow` is a set of steps
(nodes) wired by dependencies (edges) over a shared context (state). A Kahn
topological sort yields parallelizable **layers**; independent steps in a layer
run concurrently (`asyncio.gather`), a step's payload may be a function of the
accumulated context, and a step may be gated by a `when` condition (conditional
edges). Cycles and missing dependencies are rejected at plan time. This is the
richest expression of "work together": one declarative graph threads a goal
across many organs with real parallelism.

### 9.3 Blackboard ([`blackboard.py`](singularity/kernel/blackboard.py))

The classic **blackboard architecture** (organs as knowledge sources sharing
state) fused with LangGraph's **reducers** (`Annotated[list, add]`). An
async-safe key-value store with pluggable per-key reducers (`append`, `merge`,
last-write-wins) and full change history. The workflow engine writes every step
result here, giving long-running tasks a coherent shared memory.

### 9.4 MCP surface ([`mcp.py`](singularity/kernel/mcp.py))

The keystone of interoperability. `MCPBridge` projects all 24 intents as
**Model Context Protocol** tools, generating JSON-Schema `inputSchema` from each
capability's declared payload, and speaks JSON-RPC 2.0 `tools/list` / `tools/call`.
This closes the loop with the ecosystem it came from: the singularity does not
merely *use* agents — it *is* a tool that Claude, Cursor, Claude Code or the
agency's own personas can call, over the same protocol the knowledge organ indexes.

### 9.5 Observability ([`observability.py`](singularity/kernel/observability.py))

A Prometheus-client-style `Metrics` registry (counters, gauges, labelled
histograms) rendered in the Prometheus text exposition format — echoing
BRAINIAC's `prometheus_metrics()`. The kernel records per-intent route counts,
per-organ latency histograms and error counts; exposed at `/metrics` and via
`singularity metrics`.

## 10. Extending the organism

1. Add a `RepoSpec` to `ecosystem.py`.
2. Create or extend an organ in `organs/` (subclass `BaseOrgan`, declare
   `capabilities`, implement `_invoke`, optionally `_attach_real`).
3. Register it in `build_default_registry()`.
4. The new intents are immediately routable from the CLI, the API and `pulse`.

The body grows by adding organs — never by editing the kernel.
