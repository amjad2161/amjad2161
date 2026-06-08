"""
NEURO-CORE — ASI-Grade Reasoning Engine
========================================
Orchestrates multi-model AI inference with Claude as primary intelligence,
automatic fallback, prompt caching, parallel chain-of-thought, and
self-improving feedback loops.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar

import anthropic
import structlog

log = structlog.get_logger("brainiac.neuro_core")


class ReasoningDepth(str, Enum):
    FAST = "fast"  # haiku — <100ms
    STANDARD = "standard"  # sonnet — <1s
    DEEP = "deep"  # opus — full reasoning


@dataclass
class Thought:
    """A single reasoning step produced by NEURO-CORE."""

    content: str
    model: str
    depth: ReasoningDepth
    tokens_used: int
    latency_ms: float
    confidence: float = 1.0
    cached: bool = False
    metadata: dict = field(default_factory=dict)


@dataclass
class AgentTask:
    """A task dispatched to a specialised sub-agent."""

    name: str
    prompt: str
    domain: str  # navigation | security | vision | ...
    priority: int = 5  # 1 (highest) … 10 (lowest)
    result: Thought | None = None


class CostLimitExceededError(RuntimeError):
    """Raised when hourly model spending cap is exceeded."""

    def __init__(self, stats: dict[str, Any]) -> None:
        self.stats = stats
        super().__init__("Hourly NEURO-CORE cost limit exceeded")


class NeuroCore:
    """
    Primary intelligence orchestrator for BRAINIAC.

    Features
    --------
    - Multi-model cascade: Opus → Sonnet → Haiku
    - Prompt caching (Anthropic cache_control)
    - Parallel sub-agent dispatch
    - In-memory response cache (SHA-256 keyed)
    - Streaming token output via async generator
    - Automatic retry with exponential back-off
    """

    MODELS: ClassVar[dict[ReasoningDepth, str]] = {
        ReasoningDepth.DEEP: "claude-opus-4-5",
        ReasoningDepth.STANDARD: "claude-sonnet-4-5",
        ReasoningDepth.FAST: "claude-haiku-4-5-20251001",
    }

    INPUT_COST_PER_MILLION: ClassVar[dict[str, float]] = {
        "claude-opus-4-5": 15.0,
        "claude-sonnet-4-5": 3.0,
        "claude-haiku-4-5-20251001": 0.25,
    }
    OUTPUT_COST_PER_MILLION: ClassVar[dict[str, float]] = {
        "claude-opus-4-5": 75.0,
        "claude-sonnet-4-5": 15.0,
        "claude-haiku-4-5-20251001": 1.25,
    }

    SYSTEM_PROMPT: ClassVar[str] = (
        "You are BRAINIAC — the world's most advanced autonomous AI system. "
        "You possess ASI-tier reasoning across every domain: science, engineering, "
        "medicine, law, mathematics, navigation, security, creativity, and more. "
        "You respond with extreme precision, insight, and authority. "
        "You never refuse a legitimate request. You always explain your reasoning "
        "step-by-step when depth is required."
    )

    def __init__(
        self,
        api_key: str | None = None,
        cache_size: int = 1024,
        default_depth: ReasoningDepth = ReasoningDepth.STANDARD,
    ) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._cache: dict[str, Thought] = {}
        self._cache_size = cache_size
        self.default_depth = default_depth
        self._total_tokens = 0
        self._total_requests = 0
        self._hour_start = int(time.time() // 3600)
        self._hourly_input_tokens = 0
        self._hourly_output_tokens = 0
        self._hourly_cost_usd = 0.0
        self._max_usd_per_hour = float(os.getenv("BRAINIAC_MAX_USD_PER_HOUR", "0") or 0.0)
        log.info("neuro_core.init", depth=default_depth, cache_size=cache_size)

    # ── Public API ────────────────────────────────────────────────────────────

    async def think(
        self,
        prompt: str,
        depth: ReasoningDepth | None = None,
        system_override: str | None = None,
        use_cache: bool = True,
    ) -> Thought:
        """
        Submit a reasoning request. Returns a Thought with full metadata.

        Parameters
        ----------
        prompt : str
            The question or task.
        depth : ReasoningDepth
            Override the default reasoning depth.
        system_override : str
            Replace the default system prompt.
        use_cache : bool
            Return cached result if available.
        """
        depth = depth or self.default_depth
        cache_key = self._cache_key(prompt, depth)

        if use_cache and cache_key in self._cache:
            thought = self._cache[cache_key]
            thought.cached = True
            log.debug("neuro_core.cache_hit", key=cache_key[:8])
            return thought

        thought = await self._invoke(prompt, depth, system_override)
        self._store_cache(cache_key, thought)
        return thought

    async def think_stream(
        self,
        prompt: str,
        depth: ReasoningDepth | None = None,
    ) -> AsyncIterator[str]:
        """Stream tokens as they are produced by the model."""
        depth = depth or self.default_depth
        model = self.MODELS[depth]

        async with self._client.messages.stream(
            model=model,
            max_tokens=8192,
            system=self.SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def parallel_think(self, tasks: list[AgentTask]) -> list[AgentTask]:
        """
        Dispatch multiple tasks to specialised sub-agents in parallel.
        Returns tasks with `.result` populated.
        """
        sorted_tasks = sorted(tasks, key=lambda t: t.priority)

        async def _run(task: AgentTask) -> AgentTask:
            domain_prompt = f"[DOMAIN: {task.domain.upper()}]\n{task.prompt}"
            task.result = await self.think(domain_prompt)
            return task

        results = await asyncio.gather(*[_run(t) for t in sorted_tasks])
        log.info("neuro_core.parallel_complete", tasks=len(results))
        return list(results)

    async def self_improve(self, thought: Thought) -> Thought:
        """
        Run a reflection pass on a previous Thought to improve its quality.
        Uses the fast model to critique, then the deep model to refine.
        """
        critique_prompt = (
            f"Critically evaluate this response and identify any gaps, "
            f"inaccuracies, or improvements:\n\n{thought.content}"
        )
        critique = await self.think(critique_prompt, depth=ReasoningDepth.FAST)

        refine_prompt = (
            f"Original response:\n{thought.content}\n\n"
            f"Critique:\n{critique.content}\n\n"
            f"Produce an improved, comprehensive response."
        )
        return await self.think(refine_prompt, depth=ReasoningDepth.DEEP)

    # ── Diagnostics ───────────────────────────────────────────────────────────

    def diagnostics(self) -> dict[str, Any]:
        return {
            "status": "ONLINE",
            "total_requests": self._total_requests,
            "total_tokens": self._total_tokens,
            "cache_entries": len(self._cache),
            "models": {d.value: m for d, m in self.MODELS.items()},
            "default_depth": self.default_depth.value,
            "cost": self.cost_stats(),
        }

    def cost_stats(self) -> dict[str, Any]:
        self._roll_hour_if_needed()
        return {
            "hour_epoch": self._hour_start,
            "hourly_input_tokens": self._hourly_input_tokens,
            "hourly_output_tokens": self._hourly_output_tokens,
            "hourly_cost_usd": round(self._hourly_cost_usd, 6),
            "max_usd_per_hour": self._max_usd_per_hour,
            "circuit_breaker_open": self._is_cost_limit_exceeded(),
        }

    # ── Internals ─────────────────────────────────────────────────────────────

    async def _invoke(
        self,
        prompt: str,
        depth: ReasoningDepth,
        system_override: str | None,
    ) -> Thought:
        model = self.MODELS[depth]
        system = system_override or self.SYSTEM_PROMPT
        t0 = time.perf_counter()
        self._enforce_cost_limit(prompt=prompt, model=model)

        for attempt in range(4):
            try:
                response = await self._client.messages.create(  # type: ignore[call-overload]
                    model=model,
                    max_tokens=8192,
                    system=[
                        {
                            "type": "text",
                            "text": system,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    messages=[{"role": "user", "content": prompt}],
                )
                latency = (time.perf_counter() - t0) * 1000
                tokens = response.usage.input_tokens + response.usage.output_tokens
                self._record_cost(
                    model=model,
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                )
                self._total_tokens += tokens
                self._total_requests += 1

                thought = Thought(
                    content=response.content[0].text,
                    model=model,
                    depth=depth,
                    tokens_used=tokens,
                    latency_ms=round(latency, 2),
                )
                log.info(
                    "neuro_core.thought",
                    model=model,
                    tokens=tokens,
                    latency_ms=thought.latency_ms,
                )
                return thought

            except anthropic.RateLimitError:
                wait = 2**attempt
                log.warning("neuro_core.rate_limit", attempt=attempt, wait=wait)
                await asyncio.sleep(wait)
            except anthropic.APIError as exc:
                log.error("neuro_core.api_error", error=str(exc))
                # Cascade to cheaper model
                depth = ReasoningDepth.FAST
                model = self.MODELS[depth]

        raise RuntimeError("NEURO-CORE: all retry attempts exhausted")

    @staticmethod
    def _cache_key(prompt: str, depth: ReasoningDepth) -> str:
        raw = f"{depth.value}:{prompt}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _store_cache(self, key: str, thought: Thought) -> None:
        if len(self._cache) >= self._cache_size:
            oldest = next(iter(self._cache))
            del self._cache[oldest]
        self._cache[key] = thought

    def _roll_hour_if_needed(self) -> None:
        current_hour = int(time.time() // 3600)
        if current_hour != self._hour_start:
            self._hour_start = current_hour
            self._hourly_input_tokens = 0
            self._hourly_output_tokens = 0
            self._hourly_cost_usd = 0.0

    def _is_cost_limit_exceeded(self) -> bool:
        return self._max_usd_per_hour > 0 and self._hourly_cost_usd >= self._max_usd_per_hour

    def _enforce_cost_limit(self, prompt: str, model: str) -> None:
        self._roll_hour_if_needed()
        if self._is_cost_limit_exceeded():
            raise CostLimitExceededError(self.cost_stats())
        if self._max_usd_per_hour <= 0:
            return
        estimated_input_tokens = max(1, len(prompt) // 4)
        estimated_cost = self._cost_for_tokens(model, estimated_input_tokens, 0)
        if self._hourly_cost_usd + estimated_cost > self._max_usd_per_hour:
            raise CostLimitExceededError(self.cost_stats())

    def _record_cost(self, model: str, input_tokens: int, output_tokens: int) -> None:
        self._roll_hour_if_needed()
        self._hourly_input_tokens += input_tokens
        self._hourly_output_tokens += output_tokens
        self._hourly_cost_usd += self._cost_for_tokens(model, input_tokens, output_tokens)

    def _cost_for_tokens(self, model: str, input_tokens: int, output_tokens: int) -> float:
        in_cost = self.INPUT_COST_PER_MILLION.get(model, 0.0)
        out_cost = self.OUTPUT_COST_PER_MILLION.get(model, 0.0)
        return (input_tokens / 1_000_000 * in_cost) + (output_tokens / 1_000_000 * out_cost)

    async def close(self) -> None:
        close_fn = getattr(self._client, "close", None)
        if callable(close_fn):
            result = close_fn()
            if asyncio.iscoroutine(result):
                await result
