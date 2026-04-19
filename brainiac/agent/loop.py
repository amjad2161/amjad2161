"""
GANE Agent Loop — Anthropic tool-use agentic loop with full lifecycle management.

Features:
  - Anthropic messages API with tool_use content blocks
  - Per-episode cost tracking (input + output + cache read/write)
  - Max-iterations safety cap
  - Memory integration (auto-save episodes, fact context injection)
  - Concurrent tool dispatch
  - Streaming support via async generator
"""
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass
from typing import Any, AsyncIterator, cast

import anthropic
import structlog

from .memory import AgentMemory, Decision, Episode, FactSource
from .tools import ToolRegistry, ToolResult

log = structlog.get_logger("brainiac.agent.loop")

# Cost per 1K tokens (claude-sonnet-4-6 list pricing as of 2026)
_INPUT_COST_PER_1K        = 0.003
_OUTPUT_COST_PER_1K       = 0.015
_CACHE_WRITE_COST_PER_1K  = 0.00375    # 1.25× input
_CACHE_READ_COST_PER_1K   = 0.0003     # 0.1× input


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


def _decision_to_dict(d: Decision) -> dict:
    return {
        "tool": d.tool_name,
        "input": d.tool_input,
        "success": d.confirmed,
        "duration_ms": round(d.duration_ms, 2),
        "error": d.error,
    }


class AgentLoop:
    """
    Core agentic loop driving a single agent via the Anthropic Messages API.

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

    async def run(self, prompt: str) -> Episode:
        """Run the full agentic loop. Returns a completed Episode."""
        episode_id = str(uuid.uuid4())[:12]
        started_at = time.time()
        t0 = time.perf_counter()

        prompt_with_context = await self._inject_memory(prompt)
        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt_with_context}]
        tool_schemas = self.tools.get_schema()
        decisions: list[Decision] = []

        usage_totals = {
            "input": 0,
            "output": 0,
            "cache_read": 0,
            "cache_write": 0,
        }
        response_text = ""

        for _ in range(self.config.max_iterations):
            try:
                resp = await self._client.messages.create(
                    model=self.config.model,
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature,
                    system=[{
                        "type": "text",
                        "text": self.config.system_prompt,
                        "cache_control": {"type": "ephemeral"},
                    }],
                    tools=cast(Any, tool_schemas if tool_schemas else anthropic.NOT_GIVEN),
                    messages=cast(Any, messages),
                )
            except anthropic.APIError as exc:
                return await self._save_episode(
                    episode_id, started_at, t0, prompt, response_text,
                    decisions, usage_totals, success=False, error=str(exc),
                )

            self._accumulate_usage(usage_totals, resp.usage)

            text_blocks, tool_use_blocks = self._partition_content(resp.content)
            if text_blocks:
                response_text = "\n".join(text_blocks)

            if resp.stop_reason == "end_turn" or not tool_schemas or not tool_use_blocks:
                break

            messages.append({"role": "assistant", "content": resp.content})
            tool_results = await self._execute_tools_concurrent(
                tool_use_blocks, episode_id, decisions,
            )
            messages.append({"role": "user", "content": tool_results})

        return await self._save_episode(
            episode_id, started_at, t0, prompt, response_text,
            decisions, usage_totals, success=True,
        )

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        """Stream token output. Memory facts are injected for parity with run()."""
        prompt_with_context = await self._inject_memory(prompt)
        async with self._client.messages.stream(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            system=[{
                "type": "text",
                "text": self.config.system_prompt,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": prompt_with_context}],
        ) as stream:
            async for text in stream.text_stream:
                yield text

    # ── Internals ─────────────────────────────────────────────────────────────

    async def _inject_memory(self, prompt: str) -> str:
        facts = await self.memory.search_facts(
            prompt, source=self.config.fact_source, top_k=5,
        )
        if not facts:
            return prompt
        memory_block = "\n".join(f"- [{f.source.value}] {f.content}" for f in facts)
        return f"{prompt}\n\n[MEMORY]\n{memory_block}"

    @staticmethod
    def _partition_content(content) -> tuple[list[str], list]:
        text_blocks: list[str] = []
        tool_use_blocks: list = []
        for block in content:
            if block.type == "text":
                text_blocks.append(block.text)
            elif block.type == "tool_use":
                tool_use_blocks.append(block)
        return text_blocks, tool_use_blocks

    @staticmethod
    def _accumulate_usage(totals: dict, usage) -> None:
        totals["input"] += usage.input_tokens
        totals["output"] += usage.output_tokens
        totals["cache_read"] += getattr(usage, "cache_read_input_tokens", 0) or 0
        totals["cache_write"] += getattr(usage, "cache_creation_input_tokens", 0) or 0

    async def _execute_tools_concurrent(
        self,
        tool_use_blocks: list,
        episode_id: str,
        decisions: list[Decision],
    ) -> list[dict]:
        """Dispatch all tool calls concurrently; record decisions in submission order."""

        async def run_one(tu) -> tuple[Decision, dict]:
            decision = Decision(
                episode_id=episode_id,
                agent_name=self.config.name,
                tool_name=tu.name,
                tool_input=dict(tu.input) if isinstance(tu.input, dict) else {},
                reversible=self.tools.is_reversible(tu.name),
            )
            call_t0 = time.perf_counter()
            tool_inputs = dict(tu.input) if isinstance(tu.input, dict) else {}
            result: ToolResult = await self.tools.call(
                tu.name, tool_inputs,
                skip_confirm=self.config.auto_approve_tools,
            )
            decision.duration_ms = (time.perf_counter() - call_t0) * 1000
            decision.tool_output = result.output
            decision.error = result.error
            decision.confirmed = result.success
            log.info(
                "agent_loop.tool_call",
                agent=self.config.name, tool=tu.name,
                success=result.success, ms=round(decision.duration_ms, 1),
            )
            payload = {
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": str(result.output) if result.success else f"ERROR: {result.error}",
            }
            return decision, payload

        outcomes = await asyncio.gather(*(run_one(tu) for tu in tool_use_blocks))
        tool_results = []
        for decision, payload in outcomes:
            decisions.append(decision)
            await self.memory.record_decision(decision)
            tool_results.append(payload)
        return tool_results

    async def _save_episode(
        self,
        episode_id: str,
        started_at: float,
        t0: float,
        prompt: str,
        response_text: str,
        decisions: list[Decision],
        usage_totals: dict,
        success: bool,
        error: str | None = None,
    ) -> Episode:
        cost_usd = self._compute_cost(usage_totals)
        tokens_used = usage_totals["input"] + usage_totals["output"]
        episode = Episode(
            episode_id=episode_id,
            agent_name=self.config.name,
            prompt=prompt,
            response=response_text,
            tool_calls=[_decision_to_dict(d) for d in decisions],
            tokens_used=tokens_used,
            cost_usd=cost_usd,
            duration_ms=(time.perf_counter() - t0) * 1000,
            started_at=started_at,
            success=success,
            error=error,
        )
        await self.memory.save_episode(episode)
        log.info(
            "agent_loop.episode_complete",
            agent=self.config.name, episode_id=episode_id,
            tools_called=len(decisions), tokens=tokens_used,
            cost_usd=round(cost_usd, 6),
            ms=round(episode.duration_ms, 1), success=success,
        )
        return episode

    @staticmethod
    def _compute_cost(usage: dict) -> float:
        return (
            (usage["input"]       / 1000) * _INPUT_COST_PER_1K +
            (usage["output"]      / 1000) * _OUTPUT_COST_PER_1K +
            (usage["cache_write"] / 1000) * _CACHE_WRITE_COST_PER_1K +
            (usage["cache_read"]  / 1000) * _CACHE_READ_COST_PER_1K
        )
