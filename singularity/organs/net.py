"""NET — the egress / network shim.

Federates: cors-anywhere. Provides the federation a single, auditable egress
surface: build proxied URLs and describe guarded fetches. In ``MOCK`` mode it
never touches the network; it returns the exact request shape that the real
``cors-anywhere`` proxy would issue.
"""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlparse

from ..kernel.contracts import Capability, Domain
from .base import BaseOrgan


class NetOrgan(BaseOrgan):
    id = "net"
    domain = Domain.NETWORK
    title = "Net — CORS / egress proxy"
    vision = "One governed egress for browser-bound organs: build and audit proxied requests."
    capabilities = (
        Capability("net.proxy_url", "Wrap a target URL for the CORS proxy.", {"url": "str"}),
        Capability("net.describe_fetch", "Describe a guarded fetch without performing it.",
                   {"url": "str", "method": "str?"}),
    )

    def __init__(self, *, force_mock: bool = False) -> None:
        super().__init__(force_mock=force_mock)
        self._proxy = os.environ.get("CORS_PROXY_URL", "http://127.0.0.1:8080")
        self._server: Any = None  # real running CORS proxy in REAL mode

    async def _attach_real(self) -> None:
        # Start a REAL local CORS proxy (stdlib) that actually fetches targets —
        # SSRF-guarded via security.netguard, with CORS headers injected, the
        # same job cors-anywhere does. Bound to an ephemeral localhost port.
        import http.server
        import json
        import socketserver
        import threading
        import urllib.parse

        from ..security.netguard import SSRFError, safe_fetch

        class _Proxy(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_a: Any) -> None:  # silence default logging
                return

            def _send(self, code: int, obj: dict[str, Any]) -> None:
                body = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Headers", "*")
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self) -> None:
                target = urllib.parse.unquote(self.path[1:])
                for sc in ("https", "http"):
                    if target.startswith(sc + ":/") and not target.startswith(sc + "://"):
                        target = target.replace(sc + ":/", sc + "://", 1)
                if not target:
                    self._send(400, {"ok": False, "error": "no target"})
                    return
                try:
                    self._send(200, dict(safe_fetch(target, max_bytes=200_000, timeout=8)))
                except SSRFError as exc:
                    self._send(400, {"ok": False, "error": f"blocked: {exc}"})
                except Exception as exc:  # noqa: BLE001
                    self._send(502, {"ok": False, "error": type(exc).__name__})

        server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), _Proxy)
        server.daemon_threads = True
        port = server.server_address[1]
        threading.Thread(target=server.serve_forever, daemon=True, name="net-cors-proxy").start()
        self._server = server
        self._proxy = f"http://127.0.0.1:{port}"
        self._detail["cors_proxy"] = self._proxy

    async def _on_shutdown(self) -> None:
        if self._server is not None:
            try:
                self._server.shutdown()
                self._server.server_close()
            finally:
                self._server = None

    async def _invoke(self, intent: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = str(payload.get("url", ""))
        parsed = urlparse(url)
        valid = parsed.scheme in ("http", "https") and bool(parsed.netloc)
        live = self._server is not None
        backend = "cors-proxy" if live else "builtin"
        if intent == "net.proxy_url":
            return {
                "target": url,
                "valid": valid,
                "proxied": f"{self._proxy}/{url}" if valid else None,
                "host": parsed.netloc,
                "proxy_live": live,
                "_backend": backend,
            }
        if intent == "net.describe_fetch":
            method = str(payload.get("method", "GET")).upper()
            return {
                "target": url,
                "valid": valid,
                "method": method,
                "via": self._proxy,
                "proxy_live": live,
                "headers": {"origin": "https://singularity.local", "x-requested-with": "fetch"},
                "note": ("live local CORS proxy is serving; GET the proxied URL to fetch"
                         if live else "cookies stripped by proxy; CORS headers injected"),
                "_backend": backend,
            }
        raise AssertionError("unreachable")  # pragma: no cover
