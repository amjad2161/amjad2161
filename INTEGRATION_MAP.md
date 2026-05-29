# INTEGRATION MAP

> Auto-derived from [`singularity/kernel/ecosystem.py`](singularity/kernel/ecosystem.py) —
> the single source of truth. **17 repositories → 8 organs.**

Every repository is declared exactly once and projected onto the universal
`Organ` contract. `integration` says how the kernel reaches the backend;
`mock_ready` means the organ can stand in for it offline with no deps.

## Full federation table

| Repository | Organ | Domain | Language | Integration | Entrypoint | Mock |
|---|---|---|---|---|---|:--:|
| `amjad2161 (brainiac)` | **neuro** | reasoning | python | in-process | `brainiac.core.neuro_core:NeuroCore` | ✅ |
| `Mythos` | **neuro** | reasoning | python | in-process | `mythos:MythosAgent.run` | ✅ |
| `SuperAGI` | **neuro** | reasoning | python | http | `POST /v1/agent/{id}/run` | — |
| `anthropic-sdk-typescript` | **neuro** | reasoning | typescript | subprocess | `@anthropic-ai/sdk:Anthropic` | ✅ |
| `anthropic-quickstarts` | **neuro** | reasoning | python/typescript | http | `computer_use_demo.loop:sampling_loop` | ✅ |
| `agency-agents` | **agents** | agency | python | in-process | `agency.jarvis_brain:SupremeJarvisBrain` | ✅ |
| `everything-claude-code` | **agents** | agency | markdown/node | asset | `agents/*.md` | ✅ |
| `skills` | **knowledge** | knowledge | markdown | asset | `skills/**/SKILL.md` | ✅ |
| `claude-code` | **knowledge** | knowledge | markdown/typescript | asset | `plugins/*/.claude-plugin/plugin.json` | ✅ |
| `claude-code-abc` | **knowledge** | knowledge | typescript | asset | `src/` | ✅ |
| `system-prompts-and-models-of-ai-tools` | **knowledge** | knowledge | text/json | asset | `<Vendor>/*.{txt,json}` | ✅ |
| `Dji-owner (SkyCore)` | **sky** | embodiment | python | in-process | `skycore:SimulatorDrone / WaypointMission.execute` | ✅ |
| `autonomous-trading-engine` | **trade** | economics | typescript/deno | http | `supabase/functions/autonomous-orchestrator` | ✅ |
| `tradingboy` | **trade** | economics | python | subprocess | `bot` | ✅ |
| `ComfyUI` | **vision** | perception | python | http | `http://127.0.0.1:8188/prompt (+ /ws)` | ✅ |
| `auto-save-sync (GMIN Nexus)` | **nexus** | dataplane | typescript/deno | http | `supabase/functions/calc-entry` | ✅ |
| `cors-anywhere` | **net** | network | node | subprocess | `node server.js (:8080)` | ✅ |

## By organ

### NEURO — reasoning & autonomy  (`neuro`)

- **amjad2161 (brainiac)** — Anthropic-backed reasoning core: think / stream / parallel-think with a cost breaker.
- **Mythos** — Minimal self-directed Reason→Act→Observe autonomous loop with self-monitoring.
- **SuperAGI** — Production agent framework (Celery + Postgres) for concurrent autonomous workflows.
- **anthropic-sdk-typescript** — Canonical typed Claude client used by every TypeScript organ.
- **anthropic-quickstarts** — Reference Claude apps: computer-use loop, support RAG, financial analyst.

### AGENCY — persona routing & orchestration  (`agents`)

- **agency-agents** — JARVIS brain + 340 persona skills, deterministic routing, planner→executor loop.
- **everything-claude-code** — 47 production subagents with model/tool routing frontmatter.

### KNOWLEDGE — skills, agents & prompts  (`knowledge`)

- **skills** — Anthropic Agent Skills reference packages (docx/pdf/pptx/design/mcp).
- **claude-code** — Reference Claude Code plugins: agents, skills, commands, hooks.
- **claude-code-abc** — Annotated Claude Code internals: tool loop, buddy/dream subsystems, prompts.
- **system-prompts-and-models-of-ai-tools** — Corpus of ~31 vendors' system prompts and tool schemas for grounding.

### SKY — embodiment & flight  (`sky`)

- **Dji-owner (SkyCore)** — Unified async drone API over simulator/Tello/MAVLink/DJI with safety + missions.

### TRADE — autonomous economics  (`trade`)

- **autonomous-trading-engine** — Gate.io multi-strategy autonomous trading control center (24 edge functions).
- **tradingboy** — Lightweight trading bot companion to the trading engine.

### VISION — perception & creative media  (`vision`)

- **ComfyUI** — Node-graph generative media engine (image/video/3D) with stable HTTP/WS API.

### NEXUS — data plane (sync/telemetry/shield)  (`nexus`)

- **auto-save-sync (GMIN Nexus)** — Offline-first mobility/timesheet data plane with anonymous auth + sync queue.

### NET — egress / CORS proxy  (`net`)

- **cors-anywhere** — CORS bypass / egress proxy shim for browser-bound organs.

## Intent catalogue (live)

| Intent | Organ | Summary |
|---|---|---|
| `neuro.think` | neuro | Reason about a prompt and return a structured thought. |
| `neuro.plan` | neuro | Decompose a goal into an ordered task list. |
| `neuro.autonomous_run` | neuro | Run a bounded Reason→Act→Observe loop. |
| `agents.list` | agents | List the available specialist personas. |
| `agents.route` | agents | Pick the best persona for a request. |
| `agents.run` | agents | Run a persona against a request. |
| `knowledge.skills` | knowledge | List indexed skills. |
| `knowledge.search` | knowledge | Search skills/agents/prompts by keyword. |
| `knowledge.stats` | knowledge | Report what is indexed and from where. |
| `sky.mission_plan` | sky | Generate an orbit/survey mission as waypoints. |
| `sky.telemetry` | sky | Sample current drone telemetry. |
| `sky.fly` | sky | Execute a mission (simulated) and report the flight. |
| `trade.signal` | trade | Compute a BUY/SELL/HOLD signal via SMA crossover. |
| `trade.backtest` | trade | Backtest the SMA-crossover strategy over a series. |
| `trade.status` | trade | Report engine/treasury status. |
| `vision.generate` | vision | Build a ComfyUI workflow for a text-to-image job. |
| `vision.analyze` | vision | Summarise metadata for an image (size/colors). |
| `vision.creative` | vision | Produce a deterministic SVG badge for a label. |
| `nexus.publish` | nexus | Publish a message to a device-mesh topic. |
| `nexus.telemetry` | nexus | Ingest a sensor reading; flag z-score anomalies. |
| `nexus.sync` | nexus | Enqueue an offline-first record for eventual sync. |
| `nexus.guard` | nexus | Scan text for injection / unsafe content. |
| `net.proxy_url` | net | Wrap a target URL for the CORS proxy. |
| `net.describe_fetch` | net | Describe a guarded fetch without performing it. |

