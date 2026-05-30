"""FastAPI gateway — one HTTP surface over the whole federation.

Mirrors the BRAINIAC/SkyCore pattern: a lifespan that boots all organs on
startup and shuts them down gracefully, plus thin routes that expose status,
the manifest and intent routing. Import is lazy so the core package never
depends on FastAPI.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from typing import Any

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from ..kernel.contracts import OrganError, Signal
from ..kernel.governor import GovernorError
from ..kernel.kernel import build_default_kernel
from ..security.api_auth import install_security, require_token
from .dashboard import DASHBOARD_HTML


class RouteRequest(BaseModel):
    intent: str
    payload: dict[str, Any] = {}


class PulseRequest(BaseModel):
    goal: str


class AutopilotRequest(BaseModel):
    goal: str
    max_iterations: int | None = None


class RememberRequest(BaseModel):
    content: str
    role: str = "user"
    sid: str = "default"
    intent: str | None = None


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

    # Fail-closed auth + security headers. Mutating/expensive routes below carry
    # Depends(require_token); with no SINGULARITY_API_TOKEN set they return 503
    # rather than running an open control plane.
    install_security(app)

    @app.get("/", response_class=HTMLResponse)
    async def dashboard() -> str:
        return DASHBOARD_HTML

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

    @app.post("/route", dependencies=[Depends(require_token)])
    async def route(req: RouteRequest) -> dict[str, Any]:
        try:
            return await kernel.route(req.intent, req.payload)
        except GovernorError as exc:
            raise HTTPException(status_code=429, detail=str(exc)) from exc
        except OrganError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/pulse", dependencies=[Depends(require_token)])
    async def pulse(req: PulseRequest) -> dict[str, Any]:
        return await kernel.pulse(req.goal)

    @app.get("/metrics")
    async def metrics() -> Response:
        return Response(content=kernel.metrics.render_prometheus(), media_type="text/plain")

    @app.get("/blackboard")
    async def blackboard() -> dict[str, Any]:
        return {"keys": kernel.blackboard.keys(), "snapshot": kernel.blackboard.snapshot()}

    @app.post("/mcp", dependencies=[Depends(require_token)])
    async def mcp(request: Request) -> dict[str, Any]:
        """MCP JSON-RPC 2.0 endpoint: tools/list and tools/call."""

        payload = await request.json()
        return await kernel.mcp_bridge().handle(payload)

    @app.post("/autopilot", dependencies=[Depends(require_token)])
    async def autopilot(req: AutopilotRequest) -> dict[str, Any]:
        run = await kernel.autopilot(req.goal, max_iterations=req.max_iterations)
        return run.as_dict()

    @app.post("/checkpoint", dependencies=[Depends(require_token)])
    async def checkpoint(name: str = "default") -> dict[str, Any]:
        return {"saved": kernel.checkpoint(name), "checkpoints": kernel.checkpointer.list()}

    @app.post("/restore", dependencies=[Depends(require_token)])
    async def restore(name: str = "default") -> dict[str, Any]:
        return {"restored": kernel.restore(name), "blackboard_keys": len(kernel.blackboard)}

    @app.post("/memory/remember", dependencies=[Depends(require_token)])
    async def remember(req: RememberRequest) -> dict[str, Any]:
        turn = kernel.memory.remember(req.content, role=req.role, sid=req.sid, intent=req.intent)
        return {"stored": turn.as_dict(), "session": kernel.memory.summary(req.sid)}

    @app.get("/memory/recall")
    async def recall(query: str, sid: str | None = None, limit: int = 5) -> dict[str, Any]:
        hits = kernel.memory.recall(query, sid=sid, limit=limit)
        return {"query": query, "hits": [t.as_dict() for t in hits], "count": len(hits)}

    @app.get("/memory/sessions")
    async def memory_sessions() -> dict[str, Any]:
        return {"sessions": [kernel.memory.summary(sid) for sid in kernel.memory.sessions()]}

    @app.get("/stream")
    async def stream(request: Request) -> StreamingResponse:
        """Server-Sent Events: live feed of the nervous system."""

        queue: asyncio.Queue[Signal] = asyncio.Queue(maxsize=256)

        def _on_signal(signal: Signal) -> None:
            with contextlib.suppress(asyncio.QueueFull):
                queue.put_nowait(signal)

        unsubscribe = kernel.bus.subscribe("#", _on_signal)

        async def _events():
            try:
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        signal = await asyncio.wait_for(queue.get(), timeout=15.0)
                    except asyncio.TimeoutError:
                        yield ": keep-alive\n\n"
                        continue
                    yield f"data: {json.dumps(signal.as_dict(), default=str)}\n\n"
            finally:
                unsubscribe()

        return StreamingResponse(_events(), media_type="text/event-stream")

    @app.websocket("/ws")
    async def ws(websocket: WebSocket) -> None:
        """WebSocket mirror of the nervous-system feed (agency parity)."""

        await websocket.accept()
        queue: asyncio.Queue[Signal] = asyncio.Queue(maxsize=256)

        def _on_signal(signal: Signal) -> None:
            with contextlib.suppress(asyncio.QueueFull):
                queue.put_nowait(signal)

        unsubscribe = kernel.bus.subscribe("#", _on_signal)
        try:
            while True:
                signal = await queue.get()
                await websocket.send_json(signal.as_dict())
        except WebSocketDisconnect:
            pass
        finally:
            unsubscribe()

    return app
