# BRAINIAC AI (v1.0.0)

BRAINIAC is a FastAPI-based platform exposing **9 real core modules**:

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
- `POST /api/v1/system/shutdown-test` (admin header required)
- `GET /api/v1/nav/cache-stats`

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
