"""
GANE Agent Loop — Anthropic tool-use agentic loop with full lifecycle management.

Features:
  - Anthropic messages API with tool_use content blocks
  - Per-episode cost tracking
  - Max-iterations safety cap
  - Memory integration (auto-save episodes and facts)
  - Streaming support via async generator
"""
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

import anthropic
import structlog

from .memory import AgentMemory, Episode, Fact, FactSource, Decision
from .tools import ToolRegistry, ToolResult

log = structlog.get_logger("brainiac.agent.loop")

# Cost per 1K tokens (claude-sonnet-4-6 pricing as of 2025)
_INPUT_COST_PER_1K  = 0.003
_OUTPUT_COST_PER_1K = 0.015


@dataclass
class AgentConfig:
    """Configuration for an agent instance."""
    name: str
    system_prompt: str
    model: str = "claude-sonnet-4-6"
    max_iterations: int = 20
    max_tokens: int = 4096
    temperature: float = 0.7
    fact_source: FactSource = FactSource.GENERAL
    auto_approve_tools: bool = False
    budget_usd_per_day: float = 5.0


class AgentLoop:
    """
    Core agentic loop that drives a single agent using BRAINIAC + Anthropic.

    Usage:
        config = AgentConfig(name="analyst", system_prompt="You are a telemetry analyst.")
        loop = AgentLoop(config, tools=registry, memory=memory, api_key="sk-...")
        episode = await loop.run("Analyze anomalies in the last hour")
    """

    def __init__(
        self,
        config: AgentConfig,
        tools: ToolRegistry,
        memory: AgentMemory,
        api_key: str | None = None,
    ) -> None:
        self.config = config
        self.tools = tools
        self.memory = memory
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        log.info("agent_loop.init", agent=config.name, model=config.model)

    async def run(self, prompt: str, context: dict | None = None) -> Episode:
        """
        Run the full agentic loop for a single prompt.
        Returns a completed Episode with full tool call history.
        """
        episode_id = str(uuid.uuid4())[:12]
        started_at = time.time()
        t0 = time.perf_counter()

        # Retrieve relevant facts for context injection
        facts = await self.memory.search_facts(prompt, source=self.config.fact_source, top_k=5)
        fact_context = ""
        if facts:
            fact_context = "\n\n[MEMORY]\n" + "\n".join(
                f"- [{f.source.value}] {f.content}" for f in facts
            )

        messages: list[dict] = [{"role": "user", "content": prompt + fact_context}]
        tool_schemas = self.tools.get_schema()
        decisions: list[Decision] = []
        total_input_tokens = 0
        total_output_tokens = 0
        response_text = ""

        for iteration in range(self.config.max_iterations):
            try:
                resp = await self._client.messages.create(
                    model=self.config.model,
                    max_tokens=self.config.max_tokens,
                    system=[
                        {
                            "type": "text",
                            "text": self.config.system_prompt,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    tools=tool_schemas if tool_schemas else anthropic.NOT_GIVEN,
                    messages=messages,
                )
            except anthropic.APIError as exc:
                log.error("agent_loop.api_error", agent=self.config.name, error=str(exc))
                episode = Episode(
                    episode_id=episode_id,
                    agent_name=self.config.name,
                    prompt=prompt,
                    response=response_text,
                    tool_calls=[d.__dict__ for d in decisions],
                    tokens_used=total_input_tokens + total_output_tokens,
                    cost_usd=self._compute_cost(total_input_tokens, total_output_tokens),
                    duration_ms=(time.perf_counter() - t0) * 1000,
                    started_at=started_at,
                    success=False,
                    error=str(exc),
                )
                await self.memory.save_episode(episode)
                return episode

            total_input_tokens += resp.usage.input_tokens
            total_output_tokens += resp.usage.output_tokens

            # Collect text content
            text_parts = [b.text for b in resp.content if b.type == "text"]
            if text_parts:
                response_text = "\n".join(text_parts)

            # Check stop reason
            if resp.stop_reason == "end_turn" or not tool_schemas:
                break

            # Process tool calls
            tool_use_blocks = [b for b in resp.content if b.type == "tool_use"]
            if not tool_use_blocks:
                break

            messages.append({"role": "assistant", "content": resp.content})
            tool_results = []

            for tu in tool_use_blocks:
                decision = Decision(
                    episode_id=episode_id,
                    agent_name=self.config.name,
                    tool_name=tu.name,
                    tool_input=tu.input,
                    reversible=self._is_reversible(tu.name),
                    executed_at=time.time(),
                )
                call_t0 = time.perf_counter()
                result: ToolResult = await self.tools.call(
                    tu.name,
                    tu.input,
                    skip_confirm=self.config.auto_approve_tools,
                )
                decision.duration_ms = (time.perf_counter() - call_t0) * 1000
                decision.tool_output = result.output
                decision.error = result.error
                decision.confirmed = result.success
                decisions.append(decision)
                await self.memory.record_decision(decision)

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "content": str(result.output) if result.success else f"ERROR: {result.error}",
                })

                log.info(
                    "agent_loop.tool_call",
                    agent=self.config.name,
                    tool=tu.name,
                    success=result.success,
                    ms=round(decision.duration_ms, 1),
                )

            messages.append({"role": "user", "content": tool_results})

        cost_usd = self._compute_cost(total_input_tokens, total_output_tokens)
        episode = Episode(
            episode_id=episode_id,
            agent_name=self.config.name,
            prompt=prompt,
            response=response_text,
            tool_calls=[
                {
                    "tool": d.tool_name,
                    "input": d.tool_input,
                    "success": d.confirmed,
                    "duration_ms": d.duration_ms,
                }
                for d in decisions
            ],
            tokens_used=total_input_tokens + total_output_tokens,
            cost_usd=cost_usd,
            duration_ms=(time.perf_counter() - t0) * 1000,
            started_at=started_at,
            success=True,
        )
        await self.memory.save_episode(episode)

        log.info(
            "agent_loop.episode_complete",
            agent=self.config.name,
            episode_id=episode_id,
            tools_called=len(decisions),
            tokens=episode.tokens_used,
            cost_usd=round(cost_usd, 6),
            ms=round(episode.duration_ms, 1),
        )
        return episode

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        """Stream token output from the agent (no tool calls in streaming mode)."""
        async with self._client.messages.stream(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            system=self.config.system_prompt,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            async for text in stream.text_stream:
                yield text

    def _is_reversible(self, tool_name: str) -> bool:
        tool = self.tools._tools.get(tool_name)
        return tool.reversible if tool else True

    @staticmethod
    def _compute_cost(input_tokens: int, output_tokens: int) -> float:
        return (input_tokens / 1000) * _INPUT_COST_PER_1K + (output_tokens / 1000) * _OUTPUT_COST_PER_1K
