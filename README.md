# G.A.N.E — Global Autonomous Navigation Engine

**G.A.N.E (Global Autonomous Navigation Engine)** is a production-ready, modular autonomy platform that combines AI reasoning, satellite-enabled navigation, medical decision support, telemetry analysis, and multi-agent orchestration into one unified system with API, CLI, SDK, and map UI.

## Core Modules (12)

1. **NEURO-CORE** — reasoning and planning engine for high-level decisions.
2. **ORBITAL-NAV** — GNSS-based routing, positioning, ETA, and nav security checks.
3. **SONIC-MATRIX** — language detection, translation, and TTS utilities.
4. **SATLINK** — resilient SOS signaling and channel failover abstraction.
5. **NEXUS-SYNC** — device registry, pub/sub, and integration messaging hub.
6. **TELEMETRY-HUB** — sensor ingestion, anomaly detection, and metrics export.
7. **CYBER-SHIELD** — input scanning, rate limiting, and security controls.
8. **CREATIVE-ENGINE** — prompt/badge generation and creative helper outputs.
9. **OMNI-VISION** — image analysis and vision module endpoints.
10. **LOCALIZATION** — RTL-aware turn-by-turn localization (EN/HE/AR).
11. **MEDICAL-PROTOCOLS** — protocol lookup, triage scoring, and dose calculations.
12. **INS** — inertial navigation and GNSS/INS fusion for degraded environments.

## Agent Layer

G.A.N.E includes a multi-agent layer with:
- **Telemetry Agent** for sensor/anomaly workflows
- **Medical Agent** for protocol-oriented medical content/actions
- **Navigation Agent** for routing and mission-style planning
- **Agent Router** to dispatch tasks to the right specialist

## Quick Start

```bash
pip install -r requirements.txt
python -m brainiac.cli status
python -m brainiac.cli serve
```

- API docs: `http://localhost:8000/docs`
- Map viewer: `http://localhost:8000/nav`

## API Overview

### Health
```bash
curl -s http://localhost:8000/health
```

### Turn-by-turn navigation
```bash
curl -s -X POST 'http://localhost:8000/api/v1/nav/turn-by-turn?lang=en' \
  -H 'Content-Type: application/json' \
  -d '{
    "origin_lat": 32.0853,
    "origin_lon": 34.7818,
    "dest_lat": 31.7683,
    "dest_lon": 35.2137,
    "mode": "driving"
  }'
```

### Medical triage
```bash
curl -s -X POST 'http://localhost:8000/api/v1/medical/triage?heart_rate=122&respiratory_rate=30&systolic_bp=88&gcs=13&spo2=91'
```

### Agent run
```bash
curl -s -X POST 'http://localhost:8000/api/v1/agent/run' \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Analyze telemetry anomalies and suggest next action"}'
```

## SDK Usage

```python
import asyncio
from brainiac.sdk import BrainiacClient

async def main() -> None:
    async with BrainiacClient("http://localhost:8000") as client:
        health = await client.health()
        route = await client.route(32.0853, 34.7818, 31.7683, 35.2137, mode="driving")
        print(health["status"], route["distance_km"])

asyncio.run(main())
```

## Architecture (ASCII)

```text
                 +----------------------+
                 |      G.A.N.E API     |
                 |  FastAPI + WebSocket |
                 +----------+-----------+
                            |
        +-------------------+-------------------+
        |                                       |
+-------v--------+                     +--------v--------+
|   Core Modules |                     |   Agent Layer   |
| 12 subsystems  |                     | telemetry/med/nav|
+-------+--------+                     +--------+--------+
        |                                       |
        +-------------------+-------------------+
                            |
                    +-------v--------+
                    |  Orchestrator  |
                    | Brainiac class |
                    +-------+--------+
                            |
                  +---------v---------+
                  | CLI / SDK / /nav  |
                  +-------------------+
```

## Testing

```bash
pytest -q
```

## Benchmarks

```bash
python scripts/benchmark.py
```

## License

MIT
