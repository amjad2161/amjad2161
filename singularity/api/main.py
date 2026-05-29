"""FastAPI gateway — one HTTP surface over the whole federation.

Mirrors the BRAINIAC/SkyCore pattern: a lifespan that boots all organs on
startup and shuts them down gracefully, plus thin routes that expose status,
the manifest and intent routing. Import is lazy so the core package never
depends on FastAPI.
"""

from __future__ import annotations

import contextlib
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel

from ..kernel.contracts import OrganError
from ..kernel.governor import GovernorError
from ..kernel.kernel import build_default_kernel


class RouteRequest(BaseModel):
    intent: str
    payload: dict[str, Any] = {}


class PulseRequest(BaseModel):
    goal: str


def create_app(*, force_mock: bool = False) -> FastAPI:
    kernel = build_default_kernel(force_mock=force_mock, supervise=True)

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        await kernel.boot()
        try:
            yield
        finally:
            await kernel.shutdown()

    app = FastAPI(
        title="SINGULARITY",
        version="1.0.0",
        description="Hermetic kernel federating the BRAINIAC/JARVIS ecosystem.",
        lifespan=lifespan,
    )

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {"ok": kernel.booted, "status": kernel.status()}

    @app.get("/manifest")
    async def manifest() -> dict[str, Any]:
        return kernel.manifest()

    @app.get("/organs")
    async def organs() -> list[dict[str, Any]]:
        return [info.as_dict() for info in kernel.registry.describe_all()]

    @app.get("/intents")
    async def intents() -> dict[str, str]:
        return kernel.registry.intents()

    @app.post("/route")
    async def route(req: RouteRequest) -> dict[str, Any]:
        try:
            return await kernel.route(req.intent, req.payload)
        except GovernorError as exc:
            raise HTTPException(status_code=429, detail=str(exc)) from exc
        except OrganError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/pulse")
    async def pulse(req: PulseRequest) -> dict[str, Any]:
        return await kernel.pulse(req.goal)

    @app.get("/metrics")
    async def metrics() -> Response:
        return Response(content=kernel.metrics.render_prometheus(), media_type="text/plain")

    @app.get("/blackboard")
    async def blackboard() -> dict[str, Any]:
        return {"keys": kernel.blackboard.keys(), "snapshot": kernel.blackboard.snapshot()}

    @app.post("/mcp")
    async def mcp(request: Request) -> dict[str, Any]:
        """MCP JSON-RPC 2.0 endpoint: tools/list and tools/call."""

        payload = await request.json()
        return await kernel.mcp_bridge().handle(payload)

    return app
