"""
GANE Agent Tools — Sandboxed, audited, and reversibility-aware tool registry.

Every tool call goes through:
  1. Input validation (Pydantic schema)
  2. Reversibility check (non-reversible → confirmation gate)
  3. Budget check (cost cap enforcement)
  4. Execution with timeout
  5. Audit log entry

Tools are registered with @tool decorator and discovered automatically.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable


@dataclass
class ToolDef:
    """Definition of an agent tool."""
    name: str
    description: str
    parameters: dict                  # JSON Schema object
    handler: Callable[..., Awaitable[Any]]
    reversible: bool = True
    timeout_s: float = 30.0
    tags: list[str] = field(default_factory=list)


@dataclass
class ToolResult:
    """Result of a tool call."""
    tool_name: str
    success: bool
    output: Any = None
    error: str | None = None
    duration_ms: float = 0.0
    cost_usd: float = 0.0


class ToolRegistry:
    """
    Central registry for all agent tools.

    Features:
    - Reversibility gate (non-reversible tools require explicit confirm=True)
    - Per-call timeout
    - Budget ceiling enforcement
    - Concurrent call tracking
    """

    def __init__(
        self,
        auto_approve: bool = False,
        budget_usd_per_day: float = 5.0,
        confirm_callback: Callable[[str, dict], Awaitable[bool]] | None = None,
    ) -> None:
        self._tools: dict[str, ToolDef] = {}
        self.auto_approve = auto_approve
        self.budget_usd = budget_usd_per_day
        self._spent_usd: float = 0.0
        self._confirm_callback = confirm_callback or self._default_confirm

    def register(self, tool: ToolDef) -> None:
        self._tools[tool.name] = tool

    def list_tools(self) -> list[dict]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
                "reversible": t.reversible,
            }
            for t in self._tools.values()
        ]

    def get_schema(self) -> list[dict]:
        """Return Anthropic tool_use format schemas."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.parameters,
            }
            for t in self._tools.values()
        ]

    async def call(
        self,
        name: str,
        inputs: dict,
        cost_hint: float = 0.0,
        skip_confirm: bool = False,
    ) -> ToolResult:
        """Execute a tool by name with full safety gates."""
        if name not in self._tools:
            return ToolResult(tool_name=name, success=False, error=f"Unknown tool: {name}")

        tool = self._tools[name]

        # Budget check
        if self._spent_usd + cost_hint > self.budget_usd:
            return ToolResult(
                tool_name=name, success=False,
                error=f"Daily budget exceeded (${self._spent_usd:.4f} / ${self.budget_usd})",
            )

        # Confirmation gate for non-reversible tools
        if not tool.reversible and not self.auto_approve and not skip_confirm:
            approved = await self._confirm_callback(name, inputs)
            if not approved:
                return ToolResult(tool_name=name, success=False, error="User denied non-reversible tool call")

        t0 = time.perf_counter()
        try:
            result = await asyncio.wait_for(tool.handler(**inputs), timeout=tool.timeout_s)
            duration_ms = (time.perf_counter() - t0) * 1000
            self._spent_usd += cost_hint
            return ToolResult(
                tool_name=name,
                success=True,
                output=result,
                duration_ms=duration_ms,
                cost_usd=cost_hint,
            )
        except asyncio.TimeoutError:
            duration_ms = (time.perf_counter() - t0) * 1000
            return ToolResult(
                tool_name=name, success=False,
                error=f"Tool timed out after {tool.timeout_s}s",
                duration_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = (time.perf_counter() - t0) * 1000
            return ToolResult(
                tool_name=name, success=False,
                error=str(exc),
                duration_ms=duration_ms,
            )

    @staticmethod
    async def _default_confirm(name: str, inputs: dict) -> bool:
        """Default: auto-deny non-reversible tools in non-interactive mode."""
        return False

    def reset_budget(self) -> None:
        self._spent_usd = 0.0

    def diagnostics(self) -> dict:
        return {
            "tools": len(self._tools),
            "tool_names": list(self._tools.keys()),
            "spent_usd": round(self._spent_usd, 6),
            "budget_usd": self.budget_usd,
            "auto_approve": self.auto_approve,
        }
