"""Bearer-token auth for the gateway — fixes finding #3 (missing authn/authz).

The FastAPI app exposed /route, /pulse, /autopilot, /mcp, /checkpoint,
/restore, /memory/* with no auth and a default PolicyGate() that allows
every intent. This adds a constant-time bearer-token dependency and
sane non-zero default rate/cost limits.

Integration (singularity/api/main.py)::

    from singularity.security.api_auth import require_token, install_security

    app = FastAPI(...)
    install_security(app)               # CSP + security headers + CORS lockdown

    @app.post("/route", dependencies=[Depends(require_token)])
    async def route(req: RouteRequest) -> dict[str, Any]:
        ...

Set the token via env: SINGULARITY_API_TOKEN=...  (no token set => the
mutating routes return 503 "auth not configured" rather than running open,
so you can never accidentally ship an unauthenticated control plane).
"""

from __future__ import annotations

import hmac
import os
from typing import TYPE_CHECKING, Any

# `Request` must be importable at RUNTIME: FastAPI resolves the require_token
# annotation via get_type_hints when registering the route, and a string/
# forward-ref it can't resolve would be misread as a required query param
# (making every guarded route return 422). api_auth is only ever imported by the
# FastAPI gateway, so this does not pull FastAPI into the stdlib-only core.
from fastapi import Request

if TYPE_CHECKING:
    from fastapi import FastAPI

_TOKEN_ENV = "SINGULARITY_API_TOKEN"
# State-changing / expensive routes that MUST carry auth.
GUARDED_PATHS = (
    "/route", "/pulse", "/autopilot", "/mcp",
    "/checkpoint", "/restore", "/memory/remember",
)


def _configured_token() -> str | None:
    tok = os.environ.get(_TOKEN_ENV, "").strip()
    return tok or None


async def require_token(request: Request) -> None:
    """FastAPI dependency: enforce a bearer token, constant-time compared."""
    from fastapi import HTTPException

    expected = _configured_token()
    if expected is None:
        # Fail closed: never run guarded routes without a configured secret.
        raise HTTPException(
            status_code=503,
            detail=f"auth not configured: set {_TOKEN_ENV} to enable this route",
        )
    header = request.headers.get("authorization", "")
    scheme, _, presented = header.partition(" ")
    if scheme.lower() != "bearer" or not presented:
        raise HTTPException(status_code=401, detail="missing bearer token")
    if not hmac.compare_digest(presented.strip(), expected):
        raise HTTPException(status_code=403, detail="invalid token")


def install_security(app: "FastAPI", *, allow_origins: list[str] | None = None) -> None:
    """Add a strict CSP + security headers and lock CORS down to an allowlist."""
    from starlette.middleware.cors import CORSMiddleware

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins or [],   # default: no cross-origin writes
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["authorization", "content-type"],
    )

    @app.middleware("http")
    async def _headers(request: "Request", call_next: "Any") -> "Any":
        response = await call_next(request)
        # Defense-in-depth CSP. The dashboard's own script/style are inline, and
        # the primary XSS fix is source-level (dashboard.py now renders every
        # feed value via textContent, never innerHTML), so 'unsafe-inline' here
        # keeps the dashboard working while object-src/base-uri/frame-ancestors
        # still shut down plugin, base-tag and clickjacking vectors.
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; object-src 'none'; "
            "base-uri 'none'; frame-ancestors 'none'",
        )
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response


# Non-zero default governor limits (governor.py defaulted both to 0 = disabled).
SAFE_GOVERNOR_DEFAULTS = {
    "max_usd_per_hour": 5.0,
    "max_calls_per_minute": 120,
}
