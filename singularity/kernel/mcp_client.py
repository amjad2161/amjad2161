"""MCP client — federate *external* MCP servers as organs.

The other direction of the MCP bridge: instead of only exposing the federation
as tools, the kernel can *consume* any Model Context Protocol server and mount
its tools as first-class intents (``ext.<server>.<tool>``). This extends the
"federation" beyond local repos to the entire MCP ecosystem.

Transport-agnostic: an in-process transport (loopback to another kernel's
``MCPBridge``) and an HTTP/JSON-RPC transport ship here; both speak the same
``tools/list`` / ``tools/call`` protocol.
"""

from __future__ import annotations

import json
from typing import Any, Awaitable, Callable, Protocol, runtime_checkable

from .contracts import Capability, Domain
from ..organs.base import BaseOrgan


@runtime_checkable
class Transport(Protocol):
    async def request(self, payload: dict[str, Any]) -> dict[str, Any]: ...


class InProcessTransport:
    """Loopback transport: call a handler (e.g. another kernel's MCPBridge.handle)."""

    def __init__(self, handler: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]) -> None:
        self._handler = handler

    async def request(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._handler(payload)


class HTTPTransport:
    """JSON-RPC over HTTP transport (POST), using stdlib urllib in a thread."""

    def __init__(self, url: str, *, timeout_s: float = 10.0) -> None:
        self.url = url
        self.timeout_s = timeout_s

    async def request(self, payload: dict[str, Any]) -> dict[str, Any]:
        import asyncio

        def _post() -> dict[str, Any]:
            import urllib.request

            data = json.dumps(payload).encode()
            req = urllib.request.Request(
                self.url, data=data, headers={"content-type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:  # noqa: S310
                return json.loads(resp.read().decode())

        return await asyncio.to_thread(_post)


class MCPClient:
    """Minimal MCP client over a transport."""

    def __init__(self, transport: Transport) -> None:
        self.transport = transport
        self._id = 0

    def _next_id(self) -> int:
        self._id += 1
        return self._id

    async def list_tools(self) -> list[dict[str, Any]]:
        resp = await self.transport.request(
            {"jsonrpc": "2.0", "id": self._next_id(), "method": "tools/list"}
        )
        return (resp.get("result") or {}).get("tools", [])

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        resp = await self.transport.request(
            {"jsonrpc": "2.0", "id": self._next_id(), "method": "tools/call",
             "params": {"name": name, "arguments": arguments}}
        )
        return resp.get("result") or {}


class ExternalMCPOrgan(BaseOrgan):
    """An organ whose capabilities are the tools of a remote MCP server."""

    domain = Domain.KNOWLEDGE  # external tools default to the knowledge lobe

    def __init__(self, name: str, transport: Transport, *, domain: Domain | None = None) -> None:
        self.id = f"ext-{name}"
        self.title = f"External MCP: {name}"
        self.vision = f"Federated tools from the external MCP server '{name}'."
        if domain is not None:
            self.domain = domain
        super().__init__(force_mock=False)
        self._server = name
        self._client = MCPClient(transport)
        self._tool_map: dict[str, str] = {}  # intent -> remote tool name

    async def _attach_real(self) -> None:
        tools = await self._client.list_tools()
        if not tools:
            raise RuntimeError(f"external MCP '{self._server}' exposed no tools")
        caps: list[Capability] = []
        for tool in tools:
            remote = tool["name"]
            intent = f"ext.{self._server}.{remote}"
            self._tool_map[intent] = remote
            schema = tool.get("inputSchema", {}) or {}
            payload = {k: v.get("type", "any") for k, v in (schema.get("properties") or {}).items()}
            caps.append(Capability(intent, tool.get("description", remote), payload))
        # Instance-level capabilities (shadow the empty class attr) + intent set.
        self.capabilities = tuple(caps)  # type: ignore[assignment]
        self._intents = {c.intent for c in caps}
        self._detail["server"] = self._server
        self._detail["tools"] = len(caps)

    async def _invoke(self, intent: str, payload: dict[str, Any]) -> dict[str, Any]:
        remote = self._tool_map.get(intent)
        if remote is None:
            from .contracts import OrganError

            raise OrganError(f"unknown external intent {intent!r}")
        result = await self._client.call_tool(remote, payload)
        return {"server": self._server, "tool": remote, "result": result,
                "is_error": bool(result.get("isError")), "_backend": f"mcp:{self._server}"}
