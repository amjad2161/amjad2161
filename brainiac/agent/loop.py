"""Agent execution loop with retry handling."""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

import anthropic

from .memory import AgentMemory
from .router import AgentRouter


Runner = Callable[[str, str], Awaitable[str]]


@dataclass
class AgentResult:
    status: str
    route: str
    output: str | None = None
    error: str | None = None
    attempts: int = 0
    started_at: float = field(default_factory=time.time)


class AgentLoop:
    def __init__(
        self,
        router: AgentRouter | None = None,
        memory: AgentMemory | None = None,
        runner: Runner | None = None,
        max_retries: int = 2,
    ) -> None:
        self.router = router or AgentRouter()
        self.memory = memory or AgentMemory()
        self.runner = runner or self._default_runner
        self.max_retries = max_retries

    async def _default_runner(self, prompt: str, _route: str) -> str:
        return prompt

    async def run(self, prompt: str) -> dict[str, Any]:
        route = self.router.route(prompt)
        self.memory.store_fact("last_prompt", prompt, {"route": route})
        last_error: Exception | None = None
        max_attempts = self.max_retries + 1

        for attempt in range(1, max_attempts + 1):
            try:
                output = await self.runner(prompt, route)
                self.memory.store_fact("last_output", output, {"route": route})
                return AgentResult(
                    status="ok",
                    route=route,
                    output=output,
                    attempts=attempt,
                ).__dict__
            except anthropic.APIError as exc:
                last_error = exc
                if attempt <= self.max_retries:
                    await asyncio.sleep(min(0.2 * attempt, 1.0))
                    continue
                break
            except Exception as exc:  # pragma: no cover - defensive catch
                last_error = exc
                break

        return AgentResult(
            status="error",
            route=route,
            error=str(last_error) if last_error else "unknown error",
            attempts=max_attempts,
        ).__dict__


__all__ = ["AgentLoop", "AgentResult"]
