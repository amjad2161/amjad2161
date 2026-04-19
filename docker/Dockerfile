# ═══════════════════════════════════════════════════════════════════════════════
# G.A.N.E — Production Dockerfile
# Multi-stage build for minimal, secure runtime image
# ═══════════════════════════════════════════════════════════════════════════════

FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# ─── Runtime ──────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/home/brainiac/.local/bin:$PATH

RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash brainiac

WORKDIR /app
COPY --from=builder /root/.local /home/brainiac/.local
COPY --chown=brainiac:brainiac brainiac/ ./brainiac/
COPY --chown=brainiac:brainiac config/ ./config/
COPY --chown=brainiac:brainiac pyproject.toml README.md ./

USER brainiac

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "brainiac.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
