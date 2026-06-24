# BRAINIAC AI (v1.1.0 "MATRIX")

BRAINIAC is a FastAPI-based platform exposing **12 real core modules**:

| Module | Purpose |
|---|---|
| NeuroCore | Anthropic-backed reasoning, streaming, retries, hourly cost breaker |
| OrbitalNav | Routing, ETA estimation, OSRM fallback, route cache |
| SonicMatrix | Language detection/translation/TTS with optional dependency guards |
| SatLink | SOS broadcast, channel fanout, satellite pass prediction |
| NexusSync | Device registry + pub/sub with wildcard (`#`) sync/async handlers |
| TelemetryHub | Sliding-window telemetry with z-score anomaly detection + event callbacks |
| CyberShield | Input scanning, rate limiting, HMAC signing, file hash checks |
| CreativeEngine | Prompt generation, SVG badges, 3D scene specs |
| OmniVision | Image metadata, dominant colors, thermal simulation with guarded imports |
| QuantumMind | Quantum-inspired probability trees, multi-scenario superposition/collapse, MCDM decision matrix, exponential-smoothing prediction |
| EmotionEngine | VAD-model emotional intelligence, lexical sentiment, Big Five personality profiling, empathy mapping, adaptive communication tone |
| NeuralMatrix | Multi-agent swarm intelligence, role-based agent spawning, parallel task graphs, consensus voting (majority/weighted/Borda), federated knowledge base |

## Install

```bash
pip install -e .
pip install ruff mypy pytest pytest-asyncio pytest-cov
```

## Run quality checks

```bash
ruff check .
ruff format --check .
mypy .
pytest -q
python -m compileall -q brainiac tests
python -c "import brainiac; from brainiac.api.main import app; print(brainiac.__version__)"
```

## CLI

```bash
python -m brainiac.cli status
python -m brainiac.cli demo
python -m brainiac.cli serve
```

## API quickstart

```bash
uvicorn brainiac.api.main:app --host 0.0.0.0 --port 8000
```

Notable system endpoints:

- `GET /health`
- `GET /diagnostics`
- `GET /api/v1/system/cost-stats`
- `GET /api/v1/system/watchdog`
- `POST /api/v1/system/shutdown-test` (admin API key required)
- `GET /api/v1/nav/cache-stats`

JARVIS-tier module endpoints:

| Module | Endpoints |
|---|---|
| QuantumMind | `POST /api/v1/quantum/superpose`, `POST /api/v1/quantum/collapse`, `POST /api/v1/quantum/decision-matrix`, `POST /api/v1/quantum/predict` |
| EmotionEngine | `POST /api/v1/emotion/sentiment`, `POST /api/v1/emotion/empathize`, `POST /api/v1/emotion/adapt-message`, `POST /api/v1/emotion/personality`, `GET /api/v1/emotion/state` |
| NeuralMatrix | `POST /api/v1/matrix/agents`, `GET /api/v1/matrix/agents`, `DELETE /api/v1/matrix/agents/{id}`, `POST /api/v1/matrix/tasks/decompose`, `POST /api/v1/matrix/tasks/{id}/execute`, `POST /api/v1/matrix/votes`, `POST /api/v1/matrix/votes/ballot`, `POST /api/v1/matrix/votes/{id}/resolve` |

## Security

Set API keys in your environment:

```bash
export BRAINIAC_API_KEYS="ops-key-1,ops-key-2"
export BRAINIAC_ADMIN_API_KEYS="admin-key-1"
```

- Public endpoints (no API key required): `/`, `/health`, `/diagnostics`, `/metrics`
- Protected endpoints: `/api/v1/system/*`, `/api/v1/security/*`
- Admin-only endpoints: `POST /api/v1/system/shutdown-test`, `POST /api/v1/security/audit-config`

Example calls:

```bash
# Public
curl http://localhost:8000/health

# Protected
curl -H "X-API-Key: ops-key-1" http://localhost:8000/api/v1/system/cost-stats

# Admin-only
curl -X POST -H "X-API-Key: admin-key-1" http://localhost:8000/api/v1/system/shutdown-test
```

## Docker

Build and run:

```bash
docker build -f docker/Dockerfile .
docker-compose config
```

Environment template:

```bash
cp .env.example .env
```
