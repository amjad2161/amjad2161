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

    async def _invoke(self, intent: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = str(payload.get("url", ""))
        parsed = urlparse(url)
        valid = parsed.scheme in ("http", "https") and bool(parsed.netloc)
        if intent == "net.proxy_url":
            return {
                "target": url,
                "valid": valid,
                "proxied": f"{self._proxy}/{url}" if valid else None,
                "host": parsed.netloc,
            }
        if intent == "net.describe_fetch":
            method = str(payload.get("method", "GET")).upper()
            return {
                "target": url,
                "valid": valid,
                "method": method,
                "via": self._proxy,
                "headers": {"origin": "https://singularity.local", "x-requested-with": "fetch"},
                "note": "cookies stripped by proxy; CORS headers injected",
            }
        raise AssertionError("unreachable")  # pragma: no cover
