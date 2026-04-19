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
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, cast

import anthropic
import structlog

log = structlog.get_logger("brainiac.neuro_core")


class ReasoningDepth(str, Enum):
    FAST = "fast"          # haiku — <100ms
    STANDARD = "standard"  # sonnet — <1s
    DEEP = "deep"          # opus — full reasoning


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
    domain: str                   # navigation | security | vision | ...
    priority: int = 5             # 1 (highest) … 10 (lowest)
    result: Thought | None = None


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

    MODELS = {
        ReasoningDepth.DEEP:     "claude-opus-4-6",
        ReasoningDepth.STANDARD: "claude-sonnet-4-6",
        ReasoningDepth.FAST:     "claude-haiku-4-5-20251001",
    }

    SYSTEM_PROMPT = (
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
        cache_key = self._cache_key(prompt, depth, system_override)

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
            domain_prompt = (
                f"[DOMAIN: {task.domain.upper()}]\n{task.prompt}"
            )
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
            "navigation_role": "reasoning_engine",
            "capabilities": ["mission_planning", "route_reasoning", "natural_language_intents"],
            "total_requests": self._total_requests,
            "total_tokens": self._total_tokens,
            "cache_entries": len(self._cache),
            "models": {d.value: m for d, m in self.MODELS.items()},
            "default_depth": self.default_depth.value,
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

        for attempt in range(4):
            try:
                response = await self._client.messages.create(
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
                self._total_tokens += tokens
                self._total_requests += 1

                first_text = next(
                    (
                        str(cast(Any, block).text)
                        for block in response.content
                        if hasattr(cast(Any, block), "text")
                    ),
                    "",
                )
                thought = Thought(
                    content=first_text,
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
                wait = 2 ** attempt
                log.warning("neuro_core.rate_limit", attempt=attempt, wait=wait)
                await asyncio.sleep(wait)
            except anthropic.APIError as exc:
                log.error("neuro_core.api_error", error=str(exc))
                # Cascade to cheaper model
                depth = ReasoningDepth.FAST
                model = self.MODELS[depth]

        raise RuntimeError("NEURO-CORE: all retry attempts exhausted")

    @staticmethod
    def _cache_key(prompt: str, depth: ReasoningDepth, system_override: str | None = None) -> str:
        raw = f"{depth.value}:{system_override or ''}:{prompt}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _store_cache(self, key: str, thought: Thought) -> None:
        if len(self._cache) >= self._cache_size:
            oldest = next(iter(self._cache))
            del self._cache[oldest]
        self._cache[key] = thought
