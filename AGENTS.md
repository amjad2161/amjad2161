# AGENTS.md

## Cursor Cloud specific instructions

### Product scope

This repository is **BRAINIAC AI v1.1.1** — a standalone Python FastAPI monolith. It is **not** tied to any other GitHub repository or legacy monorepo. All ten core modules and the Watchdog supervisor run in-process inside a single uvicorn server.

### Dependency refresh

The VM update script installs the editable package and dev tools. After pulling changes, if imports fail, re-run from the repo root:

```bash
pip install -e .
pip install ruff mypy pytest pytest-asyncio pytest-cov
```

Dev CLIs (`ruff`, `pytest`, `mypy`) may not be on `PATH`; prefer `python3 -m ruff`, `python3 -m pytest`, and `python3 -m mypy` (matches CI).

### Required environment variables

For local serve and tests without a real Anthropic key:

```bash
export ANTHROPIC_API_KEY=dummy-key-for-ci
export BRAINIAC_SECRET=ci-test-secret
```

Copy `.env.example` to `.env` when you need real NeuroCore `/api/v1/think*` calls or social publish tokens.

### Lint, typecheck, and tests

From the repository root:

| Task | Command |
|------|---------|
| Lint | `python3 -m ruff check .` |
| Format check | `python3 -m ruff format --check .` |
| Typecheck | `python3 -m mypy .` |
| Tests | `python3 -m pytest -q` |

Full verifier (imports + CLI status/demo + subset of tests): `./scripts/verify.sh`

See `.github/workflows/ci.yml` for the canonical CI sequence.

### Running the API (dev)

Start the server (blocks; use tmux for background):

```bash
python3 -m brainiac.cli serve
# or: uvicorn brainiac.api.main:app --host 0.0.0.0 --port 8000
```

Quick smoke without HTTP: `python3 -m brainiac.cli demo` (nav → satlink → telemetry → SOS flow).

Reel smoke: `python3 -m brainiac.cli reel "AI productivity hacks"`

Hello-world HTTP checks once serve is up:

- `GET http://127.0.0.1:8000/health`
- `POST http://127.0.0.1:8000/api/v1/nav/route` with JSON body (`origin_lat`, `origin_lon`, `dest_lat`, `dest_lon`, `mode`: `drone`)
- `POST http://127.0.0.1:8000/api/v1/reel/compose` with JSON body (`topic`, `platforms`)
- OpenAPI UI: `http://127.0.0.1:8000/docs`

### Optional Docker stack

`docker compose up` adds Redis, Prometheus, and Grafana. Only the `brainiac` service is required for functional E2E; observability containers are optional and not used by the test suite.

### Gotchas

- **No separate frontend** — verification is CLI + HTTP API + pytest.
- **OSRM** is used opportunistically by OrbitalNav; routing falls back to haversine if the public OSRM endpoint is unreachable.
- **Redis/Kafka** appear in `docker-compose.yml` and config but are not wired in application code for core flows.
- **Reel publish** dry-runs without `INSTAGRAM_*`, `TIKTOK_*`, `YOUTUBE_*`, or `FACEBOOK_*` tokens in `.env`.
