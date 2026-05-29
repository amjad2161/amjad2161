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
# GET /health  /manifest  /organs  /intents     POST /route  /pulse
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
│   └── kernel.py        # Singularity: boot/route/fanout/pulse/status
├── organs/              # 8 mock-first adapters onto the universal contract
│   ├── base.py  neuro.py  agents.py  knowledge.py
│   └── sky.py   trade.py  vision.py  nexus.py  net.py
├── api/main.py          # optional FastAPI gateway
└── cli.py               # `singularity` command line
tests/                   # 40 tests, stdlib-only (no async plugin required)
```

## Testing

```bash
pip install -e '.[dev]'
pytest -q
```

## License

MIT.
