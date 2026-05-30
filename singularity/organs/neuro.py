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

    # Real LLM reasoning can be slow on a local model — give it room.
    invoke_timeout_s = 120.0

    async def _attach_real(self) -> None:
        # Real reasoning backends, in order of capability: a local Ollama LLM
        # (genuine generation, no cloud), Mythos' autonomous loop, and BRAINIAC's
        # NeuroCore. Any one present makes the organ REAL.
        from ..kernel.bootstrap import try_import

        mythos = try_import("mythos")
        brainiac = try_import("brainiac")
        ollama = self._probe_ollama()
        if mythos is None and brainiac is None and ollama is None:
            raise RuntimeError("no real reasoning backend available")
        self._backend = {"mythos": mythos, "brainiac": brainiac, "ollama": ollama}
        self._detail["mythos"] = mythos is not None
        self._detail["brainiac"] = brainiac is not None
        self._detail["ollama"] = ollama or False

    @staticmethod
    def _probe_ollama() -> str | None:
        """Return a usable local Ollama model name, or None. Prefers the smallest
        model (most likely to fit in memory / respond fastest)."""
        import json
        import os
        import urllib.request

        host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
        forced = os.environ.get("JARVIS_OLLAMA_MODEL")
        try:
            with urllib.request.urlopen(f"{host}/api/tags", timeout=2) as r:
                models = json.loads(r.read()).get("models", [])
        except Exception:
            return None
        names = [m.get("name") for m in models if m.get("name")]
        if not names:
            return None
        if forced and forced in names:
            return forced
        return sorted(models, key=lambda m: m.get("size", 1 << 62))[0].get("name")

    def _ollama_generate(self, prompt: str, *, json_mode: bool = False,
                         num_predict: int = 220) -> str | None:
        """Real local generation via Ollama. None on any failure → builtin fallback."""
        import json
        import os
        import urllib.request

        model = (self._backend or {}).get("ollama")
        if not model:
            return None
        host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
        body: dict[str, Any] = {"model": model, "prompt": prompt, "stream": False,
                                "options": {"num_predict": num_predict, "temperature": 0.4}}
        if json_mode:
            body["format"] = "json"
        try:
            req = urllib.request.Request(
                f"{host}/api/generate", data=json.dumps(body).encode(),
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=110) as r:
                return str(json.loads(r.read()).get("response", "")).strip() or None
        except Exception:
            return None

    # Backends whose presence in a result's ``_backend`` means it was genuinely
    # produced by real upstream code (vs. the deterministic builtin reasoner).
    _REAL_BACKENDS = ("mythos", "brainiac", "neurocore", "ollama")

    async def _invoke(self, intent: str, payload: dict[str, Any]) -> dict[str, Any]:
        if intent == "neuro.think":
            result = self._think(str(payload.get("prompt", "")), str(payload.get("depth", "standard")))
        elif intent == "neuro.plan":
            result = self._plan(str(payload.get("goal", "")), int(payload.get("max_tasks", 5)))
        elif intent == "neuro.autonomous_run":
            result = await self._autonomous_run(
                str(payload.get("goal", "")), int(payload.get("max_iterations", 3))
            )
        elif intent == "neuro.humanize":
            result = self._humanize(str(payload.get("text", "")))
        else:
            raise AssertionError("unreachable")  # pragma: no cover

        # Honest provenance (fixes P1): the organ may be in REAL mode because a
        # backend attached for `neuro.autonomous_run`, but `think`/`plan`/
        # `humanize` are served by the deterministic builtin reasoner. Stamp
        # `_mode` from what ACTUALLY produced the result so a builtin answer is
        # never advertised as "real" just because the organ reached REAL mode.
        backend = str(result.get("_backend", ""))
        result["_mode"] = "real" if backend.startswith(self._REAL_BACKENDS) else "mock"
        return result

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

    # -- reasoning (real LLM when available, deterministic builtin otherwise) --
    def _think(self, prompt: str, depth: str) -> dict[str, Any]:
        if (self._backend or {}).get("ollama"):
            out = self._ollama_generate(
                "You are JARVIS's reasoning core. Think about the request and give a "
                f"concise, grounded answer (no preamble).\n\nRequest: {prompt}",
                num_predict=256 if depth in ("deep", "supreme") else 160)
            if out:
                model = self._backend["ollama"]
                return {"thought": out, "depth": depth, "model": model,
                        "_usd": 0.0, "_backend": f"ollama:{model}"}

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
        if (self._backend or {}).get("ollama"):
            import json as _json

            raw = self._ollama_generate(
                f"Decompose this goal into at most {max_tasks} ordered, concrete tasks. "
                'Respond ONLY as JSON: {"tasks":[{"id":1,"title":"...","depends_on":[]}]}.'
                f"\n\nGoal: {goal}", json_mode=True, num_predict=320)
            if raw:
                try:
                    tasks = (_json.loads(raw).get("tasks") or [])[:max_tasks]
                except Exception:
                    tasks = []
                if tasks:
                    model = self._backend["ollama"]
                    return {"goal": goal, "tasks": tasks, "strategy": "llm-decomposed",
                            "model": model, "_usd": 0.0, "_backend": f"ollama:{model}"}

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
