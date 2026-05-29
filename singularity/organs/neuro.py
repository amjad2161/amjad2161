"""NEURO — the reasoning core.

Federates: amjad2161/brainiac ``NeuroCore``, Mythos' autonomous loop, SuperAGI,
the Anthropic SDK + quickstarts. In ``REAL`` mode it delegates to
``brainiac.core.neuro_core.NeuroCore`` (and, given ``ANTHROPIC_API_KEY``, real
Claude calls). In ``MOCK`` mode it produces a deterministic, inspectable
reasoning trace so downstream organs always have something to act on.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from ..kernel.contracts import Capability, Domain
from .base import BaseOrgan

_STOPWORDS = {
    "the", "a", "an", "to", "of", "and", "or", "for", "with", "in", "on", "is",
    "are", "be", "this", "that", "it", "as", "by", "at", "from",
}


class NeuroOrgan(BaseOrgan):
    id = "neuro"
    domain = Domain.REASONING
    title = "NeuroCore — reasoning & autonomy"
    vision = "Decompose any goal into grounded thought, plans and self-directed loops."
    capabilities = (
        Capability("neuro.think", "Reason about a prompt and return a structured thought.",
                   {"prompt": "str", "depth": "str?"}),
        Capability("neuro.plan", "Decompose a goal into an ordered task list.",
                   {"goal": "str", "max_tasks": "int?"}),
        Capability("neuro.autonomous_run", "Run a bounded Reason→Act→Observe loop.",
                   {"goal": "str", "max_iterations": "int?"}),
        Capability("neuro.humanize", "Strip common AI-writing tells from text (humanizer).",
                   {"text": "str"}),
    )

    async def _attach_real(self) -> None:
        # Real reasoning backends: Mythos' autonomous loop (runs offline with a
        # stub LLM) and, when present + keyed, BRAINIAC's NeuroCore.
        from ..kernel.bootstrap import try_import

        mythos = try_import("mythos")
        brainiac = try_import("brainiac")
        if mythos is None and brainiac is None:
            raise RuntimeError("no real reasoning backend available")
        self._backend = {"mythos": mythos, "brainiac": brainiac}
        self._detail["mythos"] = mythos is not None
        self._detail["brainiac"] = brainiac is not None

    async def _invoke(self, intent: str, payload: dict[str, Any]) -> dict[str, Any]:
        if intent == "neuro.think":
            return self._think(str(payload.get("prompt", "")), str(payload.get("depth", "standard")))
        if intent == "neuro.plan":
            return self._plan(str(payload.get("goal", "")), int(payload.get("max_tasks", 5)))
        if intent == "neuro.autonomous_run":
            return await self._autonomous_run(
                str(payload.get("goal", "")), int(payload.get("max_iterations", 3))
            )
        if intent == "neuro.humanize":
            return self._humanize(str(payload.get("text", "")))
        raise AssertionError("unreachable")  # pragma: no cover

    def _humanize(self, text: str) -> dict[str, Any]:
        original = text
        edits = 0
        # Common AI tells → plainer language (deterministic, real transform).
        replacements = {
            r"\bdelve into\b": "look at",
            r"\bdelve\b": "dig",
            r"\bIn conclusion,?\s*": "",
            r"\bIt's worth noting that\s*": "",
            r"\bIt is important to note that\s*": "",
            r"\bfurthermore\b": "also",
            r"\bmoreover\b": "and",
            r"\bleverage\b": "use",
            r"\butilize\b": "use",
            r"\bin order to\b": "to",
            r"\ba plethora of\b": "many",
            r"\bseamless(ly)?\b": "smooth",
            r"\bunlock\b": "enable",
            r"\btapestry\b": "mix",
        }
        for pat, repl in replacements.items():
            text, k = re.subn(pat, repl, text, flags=re.IGNORECASE)
            edits += k
        # Collapse em-dash overuse and triple emphasis.
        text, k = re.subn(r"\s*—\s*", ", ", text)
        edits += k
        text = re.sub(r"\s{2,}", " ", text).strip()
        return {"original": original, "humanized": text, "edits": edits,
                "_backend": "builtin-humanizer", "_usd": 0.0}

    async def _autonomous_run(self, goal: str, max_iterations: int) -> dict[str, Any]:
        mythos = self._backend.get("mythos") if self._backend else None
        if mythos is not None:
            import asyncio
            import contextlib
            import io
            import os

            provider = "anthropic" if os.environ.get("ANTHROPIC_API_KEY") else "stub"

            def _run() -> str:
                cfg = mythos.MythosConfig(llm_provider=provider,
                                          max_iterations=max(1, min(max_iterations, 12)))
                agent = mythos.MythosAgent(config=cfg)
                with contextlib.redirect_stdout(io.StringIO()):
                    return agent.run(goal)

            conclusion = await asyncio.to_thread(_run)
            return {"goal": goal, "conclusion": conclusion, "backend_provider": provider,
                    "_backend": f"mythos:{provider}", "_usd": 0.0}
        return self._autonomous(goal, max_iterations)

    # -- mock reasoning ---------------------------------------------------
    def _think(self, prompt: str, depth: str) -> dict[str, Any]:
        keywords = _keywords(prompt)
        steps = [
            f"Frame the request: '{prompt[:80]}'",
            f"Identify salient concepts: {', '.join(keywords) or 'general'}",
            "Relate concepts to known capabilities of the federation",
            "Synthesise a grounded response",
        ]
        if depth in ("deep", "supreme"):
            steps.append("Self-critique the synthesis and refine")
        confidence = round(0.55 + min(len(keywords), 8) * 0.05, 2)
        return {
            "thought": (
                f"Considering '{prompt[:120]}', the core reasons across "
                f"{len(keywords)} concept(s) and proposes a {depth} response."
            ),
            "reasoning_steps": steps,
            "concepts": keywords,
            "confidence": confidence,
            "depth": depth,
            "_usd": 0.0,
            "_backend": "builtin-reasoner",
        }

    def _plan(self, goal: str, max_tasks: int) -> dict[str, Any]:
        keywords = _keywords(goal) or ["objective"]
        verbs = ["analyse", "design", "build", "verify", "deliver"]
        tasks = []
        for i, kw in enumerate(keywords[:max_tasks]):
            tasks.append(
                {
                    "id": i + 1,
                    "title": f"{verbs[i % len(verbs)].capitalize()} {kw}",
                    "depends_on": [i] if i else [],
                }
            )
        return {"goal": goal, "tasks": tasks, "strategy": "decompose-then-execute",
                "_usd": 0.0, "_backend": "builtin-reasoner"}

    def _autonomous(self, goal: str, max_iterations: int) -> dict[str, Any]:
        max_iterations = max(1, min(max_iterations, 12))
        trace = []
        for i in range(max_iterations):
            seed = hashlib.sha256(f"{goal}:{i}".encode()).hexdigest()
            done = i == max_iterations - 1
            trace.append(
                {
                    "iteration": i + 1,
                    "reason": f"Assess progress toward: {goal[:60]}",
                    "act": "finish" if done else f"sub-step-{seed[:6]}",
                    "observe": "goal satisfied" if done else "partial progress",
                }
            )
        return {
            "goal": goal,
            "iterations": len(trace),
            "trace": trace,
            "conclusion": f"Goal '{goal[:60]}' resolved in {len(trace)} iteration(s).",
            "_usd": 0.0,
            "_backend": "builtin-loop",
        }


def _keywords(text: str, limit: int = 8) -> list[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text.lower())
    seen: list[str] = []
    for token in tokens:
        if token in _STOPWORDS or token in seen:
            continue
        seen.append(token)
        if len(seen) >= limit:
            break
    return seen
