from __future__ import annotations

import logging
from typing import Any

import anthropic

log = logging.getLogger(__name__)


class AgentLoop:
    def __init__(self, client: anthropic.AsyncAnthropic, model: str = "claude-sonnet-4-5") -> None:
        self.client = client
        self.model = model

    @staticmethod
    def _accumulate_usage(total: dict[str, int], usage: Any) -> dict[str, int]:
        total["input_tokens"] = total.get("input_tokens", 0) + int(getattr(usage, "input_tokens", 0) or 0)
        total["output_tokens"] = total.get("output_tokens", 0) + int(getattr(usage, "output_tokens", 0) or 0)
        total["cache_read_input_tokens"] = total.get("cache_read_input_tokens", 0) + int(
            getattr(usage, "cache_read_input_tokens", 0) or 0
        )
        total["cache_creation_input_tokens"] = total.get("cache_creation_input_tokens", 0) + int(
            getattr(usage, "cache_creation_input_tokens", 0) or 0
        )
        return total

    async def stream(self, prompt: str, tool_schemas: list[dict[str, Any]] | None = None):
        tools = tool_schemas if tool_schemas else anthropic.NOT_GIVEN
        try:
            async with self.client.messages.stream(
                model=self.model,
                max_tokens=1024,
                system=[{"type": "text", "text": "You are BRAINIAC."}],
                messages=[{"role": "user", "content": prompt}],
                tools=tools,
            ) as stream:
                async for token in stream.text_stream:
                    yield token
        except anthropic.APIError:
            log.exception("agent.loop.api_error")
            raise
