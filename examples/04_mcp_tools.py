"""Show the singularity as an MCP tool server (tools/list + tools/call).

    python examples/04_mcp_tools.py
"""

from __future__ import annotations

import asyncio
import json

from singularity import build_default_kernel


async def main() -> None:
    async with build_default_kernel() as kernel:
        bridge = kernel.mcp_bridge()

        listed = await bridge.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        print(f"exposed {len(listed['result']['tools'])} MCP tools")
        print("first tool:", json.dumps(listed["result"]["tools"][0], indent=2))

        called = await bridge.handle({
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "trade-backtest", "arguments": {"symbol": "ETH_USDT"}},
        })
        print("tools/call isError:", called["result"]["isError"])
        print("structured:", called["result"]["structuredContent"])


if __name__ == "__main__":
    asyncio.run(main())
