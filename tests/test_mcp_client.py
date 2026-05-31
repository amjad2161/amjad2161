from __future__ import annotations

import asyncio

from singularity import build_default_kernel
from singularity.kernel.mcp_client import HTTPTransport, InProcessTransport, MCPClient


def test_mount_external_mcp_loopback():
    """Federate kernel A's MCP bridge into kernel B as live ext.* intents."""

    async def run():
        a = build_default_kernel(force_mock=True)
        b = build_default_kernel(force_mock=True)
        await a.boot()
        await b.boot()

        bridge_a = a.mcp_bridge()
        organ = await b.mount_mcp("alpha", InProcessTransport(bridge_a.handle))

        ext = [i for i in b.registry.intents() if i.startswith("ext.alpha.")]
        # Route an external tool through B → executes on A.
        result = await b.route("ext.alpha.trade-signal", {"symbol": "ETH_USDT"})

        await a.shutdown()
        await b.shutdown()
        return organ, ext, result

    organ, ext, result = asyncio.run(run())
    assert organ.id == "ext-alpha"
    assert len(ext) == 44  # all of A's intents are now federated into B
    assert result["server"] == "alpha"
    assert result["tool"] == "trade-signal"
    assert result["result"]["structuredContent"]["signal"] in ("BUY", "SELL", "HOLD")
    assert result["_backend"] == "mcp:alpha"


def test_mcp_client_list_and_call_via_inprocess():
    async def run():
        k = build_default_kernel(force_mock=True)
        await k.boot()
        client = MCPClient(InProcessTransport(k.mcp_bridge().handle))
        tools = await client.list_tools()
        called = await client.call_tool("sky-mission_plan", {"lat": 37.0, "lon": -122.0, "points": 4})
        await k.shutdown()
        return tools, called

    tools, called = asyncio.run(run())
    assert len(tools) == 44
    assert called["isError"] is False
    assert called["structuredContent"]["count"] == 4


def test_http_transport_constructs():
    # No network call — just verify the transport is well-formed.
    t = HTTPTransport("http://127.0.0.1:9/mcp", timeout_s=0.5)
    assert t.url.endswith("/mcp")
