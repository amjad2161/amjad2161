# BRAINIAC Architecture

## Core modules (10)

BRAINIAC ships ten concrete runtime modules under `brainiac/core/`:

1. `neuro_core.py`
2. `orbital_nav.py`
3. `sonic_matrix.py`
4. `satlink.py`
5. `nexus_sync.py`
6. `telemetry_hub.py`
7. `cyber_shield.py`
8. `creative_engine.py`
9. `omni_vision.py`
10. `reel_maker.py` — short-form reel scripts, 9:16 render, trends, social publish

## FastAPI surface

`brainiac/api/main.py` wires all module singletons into REST + WS/SSE routes under:

- system/health/diagnostics/metrics
- neuro (`/api/v1/think*`)
- nav (`/api/v1/nav/*`)
- satlink (`/api/v1/sos*`)
- sonic (`/api/v1/sonic/*`)
- telemetry (`/api/v1/telemetry/*`)
- creative (`/api/v1/creative/*`)
- nexus (`/api/v1/nexus/*`)
- security (`/api/v1/security/*`)
- vision (`/api/v1/vision/*`)
- reel (`/api/v1/reel/*`) — compose, jobs, publish, trends, platform specs

## Operational controls in this release

- **Graceful shutdown**: lifespan handles SIGINT/SIGTERM, cancels in-flight WS/SSE tasks, stops watchdog, closes NeuroCore client.
- **Cost circuit breaker**: NeuroCore tracks hourly token spend and blocks new think calls after `BRAINIAC_MAX_USD_PER_HOUR`.
- **Correlation IDs**: request middleware propagates/echoes `X-Request-Id` and binds it into structlog contextvars.
- **OrbitalNav route cache**: in-memory LRU+TTL route cache with `/api/v1/nav/cache-stats`.
- **Telemetry anomaly event bus**: anomaly callbacks registered via `on_anomaly`, with default structured warning logger.
- **Watchdog**: background supervisor that checks module `diagnostics()`, restarts failed modules with exponential backoff, and marks health as `DEGRADED` after max retries.
