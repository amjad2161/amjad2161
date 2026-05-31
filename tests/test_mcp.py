from __future__ import annotations

import asyncio

from singularity import build_default_kernel
from singularity.kernel.mcp import intent_to_tool, tool_to_intent


def test_tool_name_roundtrip():
    assert intent_to_tool("neuro.think") == "neuro-think"
    assert tool_to_intent("neuro-think") == "neuro.think"


def test_list_tools_matches_intents():
    kernel = build_default_kernel(force_mock=True)
    bridge = kernel.mcp_bridge()
    tools = bridge.list_tools()
    assert len(tools) == len(kernel.registry.intents()) == 42
    sample = next(t for t in tools if t["name"] == "neuro-think")
    schema = sample["inputSchema"]
    assert schema["type"] == "object"
    assert "prompt" in schema["properties"]
    assert schema["properties"]["prompt"]["type"] == "string"
    assert "prompt" in schema["required"]
    # 'depth' is optional (trailing ? in the hint) → not required
    assert "depth" not in schema.get("required", [])


def test_tools_list_jsonrpc():
    async def run():
        kernel = build_default_kernel(force_mock=True)
        await kernel.boot()
        resp = await kernel.mcp_bridge().handle(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        )
        await kernel.shutdown()
        return resp

    resp = asyncio.run(run())
    assert resp["jsonrpc"] == "2.0" and resp["id"] == 1
    assert len(resp["result"]["tools"]) == 42


def test_tools_call_executes_intent():
    async def run():
        kernel = build_default_kernel(force_mock=True)
        await kernel.boot()
        resp = await kernel.mcp_bridge().handle(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "trade-signal", "arguments": {"symbol": "ETH_USDT"}},
            }
        )
        await kernel.shutdown()
        return resp

    resp = asyncio.run(run())
    result = resp["result"]
    assert result["isError"] is False
    assert result["structuredContent"]["_organ"] == "trade"
    assert result["content"][0]["type"] == "text"


def test_unknown_method_is_jsonrpc_error():
    async def run():
        kernel = build_default_kernel(force_mock=True)
        await kernel.boot()
        resp = await kernel.mcp_bridge().handle({"jsonrpc": "2.0", "id": 9, "method": "nope"})
        await kernel.shutdown()
        return resp

    resp = asyncio.run(run())
    assert resp["error"]["code"] == -32601
