## [1.3.0] – REELMAKER webhooks, social status, dashboard

- HTTP webhook callbacks on `compose.ready`, `compose.failed`, `publish.scheduled`, and `publish.completed` (`BRAINIAC_REEL_WEBHOOK_URL`, optional HMAC secret).
- `GET /api/v1/reel/social/status` reports per-platform env readiness and OAuth setup hints (no secrets exposed).
- Browser dashboard at `GET /reel` for compose, job list, dry-run publish, and delete.

## [1.2.0] – REELMAKER NeuroCore, scheduler, publishers

- NeuroCore-powered reel scripts via `use_ai_script` on compose (falls back to templates when API key missing or parse fails).
- Background scheduler processes due `scheduled_publish_at` jobs and TTL cleanup (`BRAINIAC_REEL_JOB_TTL_DAYS`).
- `DELETE /api/v1/reel/jobs/{job_id}` removes persisted jobs and optional media files.
- YouTube resumable upload, TikTok init+upload, Facebook `file_url` or resumable upload.
- `render.yaml` Blueprint for Render web service deployment.
- ReelMaker wired with NeuroCore in API lifespan, Watchdog factory, and CLI.

## [1.1.1] – REELMAKER persistence

- Reel jobs persist as JSON under `{BRAINIAC_REEL_OUTPUT_DIR}/jobs/` and reload on `ReelMaker` init (survives restarts and watchdog module rebuilds).
- Optional `BRAINIAC_REEL_PUBLIC_BASE_URL` supplies `video_url` in Instagram publish payloads for Graph API uploads.

## [1.1.0] – REELMAKER

- Added **REEL-MAKER** module: viral short-form video compose, algorithm scoring, platform specs, dry-run social publish, REST API, and CLI (`brainiac reel`).
- H.264 transcode via ffmpeg after render for browser and social compatibility (`yuv420p`, `faststart`).
- CreativeEngine-driven visual palette selection per reel style.
- Watchdog reel factory preserves SonicMatrix / CreativeEngine / NexusSync dependencies on restart.
- Added `GET /api/v1/reel/jobs/{job_id}/thumbnail` download endpoint.
- Extended `verify.sh` and CLI demo with REEL-MAKER smoke flow.
- Standalone project docs and packaging for `brainiac-reel-maker` repository.

## [1.0.1] – Unreleased

- Added FastAPI lifespan graceful shutdown handling for SIGINT/SIGTERM, in-flight WS/SSE cancellation, and NeuroCore client close.
- Added NeuroCore hourly cost circuit breaker (`BRAINIAC_MAX_USD_PER_HOUR`) and `/api/v1/system/cost-stats`.
- Added request correlation-ID middleware behavior (`X-Request-Id`) with structlog contextvars propagation.
- Added OrbitalNav LRU+TTL route cache with `/api/v1/nav/cache-stats`.
- Added TelemetryHub anomaly callback event bus default warning callback.
- Added watchdog supervisor (`brainiac/watchdog.py`) and `/api/v1/system/watchdog` endpoint.
- Added `.env.example` placeholders and aligned Docker Compose env wiring.
- Hardened CI workflow to install editable package and run `ruff check .`, `ruff format --check .`, `mypy .`, and `pytest -q` on Python 3.10/3.11.
- Updated documentation (README + ARCHITECTURE) to reflect the real 9-module BRAINIAC v1.0.0 baseline.

## [2.1.1] – Unreleased

- Fixed dependency resolution in `requirements.txt` by aligning `anthropic` with `langchain-anthropic`, removing `asyncio` (stdlib), and de-duplicating `httpx`.
- Hardened API request handling with a strict 10MB request-body cap validated from both `Content-Length` and actual read bytes.
- Added correlation IDs to API responses via `X-Request-Id` middleware header.
- Improved orbital navigation offline ETA fallbacks by covering all transport modes, including submarine and spacecraft.
- Exported a stable top-level `brainiac.__all__` surface for import-smoke validation.
