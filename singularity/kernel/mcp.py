"""MCP bridge — expose the whole SINGULARITY as Model Context Protocol tools.

This is the keystone of interoperability: it projects every organ capability as
an MCP tool so *any* MCP client (Claude, Cursor, Claude Code, the agency's own
agents) can drive the entire federation through the standard ``tools/list`` /
``tools/call`` JSON-RPC 2.0 surface. The singularity does not just *use* agents —
it *is* a tool any agent can use.

Schemas follow the MCP tool spec: ``name``, ``title``, ``description`` and a
JSON-Schema (2020-12) ``inputSchema`` derived from each capability's declared
payload.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from .kernel import Singularity

_TYPE_MAP = {
    "str": "string",
    "int": "integer",
    "float": "number",
    "bool": "boolean",
    "list": "array",
    "dict": "object",
}


def _json_type(hint: str) -> str:
    base = hint.rstrip("?").split("[")[0].strip().lower()
    return _TYPE_MAP.get(base, "string")


def intent_to_tool(intent: str) -> str:
    return intent.replace(".", "-")


def tool_to_intent(tool: str) -> str:
    return tool.replace("-", ".")


class MCPBridge:
    """Adapts a :class:`Singularity` kernel to the MCP tool protocol."""

    def __init__(self, kernel: "Singularity") -> None:
        self.kernel = kernel
        self._tool_index = {
            intent_to_tool(intent): intent for intent in kernel.registry.intents()
        }

    # -- tool catalogue ---------------------------------------------------
    def list_tools(self) -> list[dict[str, Any]]:
        tools: list[dict[str, Any]] = []
        for info in self.kernel.registry.describe_all():
            for cap in info.capabilities:
                tools.append(
                    {
                        "name": intent_to_tool(cap.intent),
                        "title": f"{info.title.split('—')[0].strip()}: {cap.intent}",
                        "description": cap.summary,
                        "inputSchema": self._input_schema(cap.payload),
                    }
                )
        return tools

    @staticmethod
    def _input_schema(payload: dict[str, str]) -> dict[str, Any]:
        properties: dict[str, Any] = {}
        required: list[str] = []
        for field, hint in payload.items():
            properties[field] = {"type": _json_type(hint), "description": hint}
            if not hint.endswith("?"):
                required.append(field)
        schema: dict[str, Any] = {
            "type": "object",
            "properties": properties,
            "additionalProperties": False,
        }
        if required:
            schema["required"] = required
        return schema

    # -- tool invocation --------------------------------------------------
    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        intent = self._tool_index.get(name) or tool_to_intent(name)
        try:
            result = await self.kernel.route(intent, arguments or {})
        except Exception as exc:  # noqa: BLE001 - surface as MCP tool error
            return {
                "content": [{"type": "text", "text": f"{type(exc).__name__}: {exc}"}],
                "isError": True,
            }
        return {
            "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, default=str)}],
            "structuredContent": result,
            "isError": False,
        }

    # -- JSON-RPC 2.0 dispatch -------------------------------------------
    async def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        rpc_id = request.get("id")
        method = request.get("method")
        params = request.get("params") or {}

        if method == "tools/list":
            return self._ok(rpc_id, {"tools": self.list_tools()})
        if method == "tools/call":
            name = params.get("name", "")
            result = await self.call_tool(name, params.get("arguments") or {})
            return self._ok(rpc_id, result)
        if method == "ping":
            return self._ok(rpc_id, {})
        return self._err(rpc_id, -32601, f"method not found: {method!r}")

    @staticmethod
    def _ok(rpc_id: Any, result: dict[str, Any]) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": rpc_id, "result": result}

    @staticmethod
    def _err(rpc_id: Any, code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": rpc_id, "error": {"code": code, "message": message}}
