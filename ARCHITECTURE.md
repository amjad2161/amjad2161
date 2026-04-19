# BRAINIAC Architecture (v2.1.1)

## Runtime topology

- **API Layer (`brainiac/api/main.py`)**: FastAPI app exposing REST/SSE/WebSocket routes.
- **Core Modules (`brainiac/core/*`)**: Nine module singletons initialized at startup:
  - NeuroCore
  - OrbitalNav
  - SonicMatrix
  - SatLink
  - NexusSync
  - TelemetryHub
  - CyberShield
  - CreativeEngine
  - OmniVision
- **CLI Layer (`brainiac/cli.py`)**: operational commands (`status`, `boot`, `demo`, `serve`).

## Wiring model

1. **Startup/Shutdown**
   - FastAPI lifespan connects SatLink uplink on startup.
   - Module diagnostics are surfaced through `/diagnostics` and `/health`.

2. **Security path**
   - HTTP middleware enforces rate limits (CyberShield).
   - Request bodies are capped and scanned (raw + nested JSON fields).
   - Body bytes are re-injected so downstream FastAPI handlers can parse normally.

3. **Navigation + communication path**
   - OrbitalNav provides position and route planning.
   - SatLink sends SOS packets and dispatch notifications.
   - NexusSync manages device registry/pub-sub/commands.

4. **Telemetry path**
   - TelemetryHub ingests readings and performs anomaly detection.
   - Callbacks can be attached with `on_anomaly`.

## Resilience behavior

- NeuroCore gracefully degrades to deterministic offline responses when `ANTHROPIC_API_KEY` is missing.
- Language detection is stabilized for short route phrases to avoid random classifier drift.
- CI validates targeted lint and full pytest execution on push/PR.
