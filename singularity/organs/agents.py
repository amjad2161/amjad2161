"""AGENCY — persona routing & multi-agent orchestration.

Federates: agency-agents (JARVIS brain + 340 personas) and
everything-claude-code's 47 subagents. In ``REAL`` mode it routes through
``agency.jarvis_brain.SupremeJarvisBrain``; in ``MOCK`` mode it uses a compact
built-in persona catalog with the same deterministic keyword routing so any
request still gets matched to a specialist and "executed".
"""

from __future__ import annotations

from typing import Any

from ..kernel.contracts import Capability, Domain
from .base import BaseOrgan

# A compact mirror of the kind of personas the agency ships.
_PERSONAS: tuple[dict[str, Any], ...] = (
    {"slug": "frontend-developer", "keywords": ["ui", "react", "css", "component", "frontend", "web"]},
    {"slug": "backend-architect", "keywords": ["api", "service", "database", "scale", "backend", "server"]},
    {"slug": "security-reviewer", "keywords": ["security", "auth", "vulnerability", "exploit", "secret"]},
    {"slug": "data-scientist", "keywords": ["data", "model", "train", "analytics", "dataset", "ml"]},
    {"slug": "devops-engineer", "keywords": ["deploy", "ci", "docker", "infra", "pipeline", "kubernetes"]},
    {"slug": "trading-strategist", "keywords": ["trade", "market", "price", "signal", "portfolio", "risk"]},
    {"slug": "drone-pilot", "keywords": ["drone", "flight", "mission", "waypoint", "aerial", "telemetry"]},
    {"slug": "creative-director", "keywords": ["image", "design", "brand", "creative", "visual", "art"]},
    {"slug": "research-analyst", "keywords": ["research", "investigate", "summarize", "compare", "review"]},
    {"slug": "jarvis-supreme", "keywords": ["plan", "orchestrate", "autonomous", "agent", "system"]},
)


class AgentsOrgan(BaseOrgan):
    id = "agents"
    domain = Domain.AGENCY
    title = "JARVIS — agency & orchestration"
    vision = "Route any request to the best specialist persona and run it to a deliverable."
    # Real persona execution goes through a local LLM — give it ample room.
    invoke_timeout_s = 220.0
    capabilities = (
        Capability("agents.list", "List the available specialist personas.", {}),
        Capability("agents.route", "Pick the best persona for a request.", {"request": "str"}),
        Capability("agents.run", "Run a persona against a request.",
                   {"request": "str", "persona": "str?"}),
    )

    async def _attach_real(self) -> None:
        from ..kernel.bootstrap import try_import

        if try_import("agency") is None:
            raise RuntimeError("agency unavailable")
        from agency.jarvis_brain import SupremeJarvisBrain
        from agency.skills import SkillRegistry

        registry = SkillRegistry.load()
        self._backend = {"registry": registry, "brain": SupremeJarvisBrain(registry)}
        self._detail["personas"] = len(registry)

    async def _invoke(self, intent: str, payload: dict[str, Any]) -> dict[str, Any]:
        if intent == "agents.list":
            if self._backend is not None:
                reg = self._backend["registry"]
                slugs = [s.slug for s in list(reg.all())[:50]]
                return {"personas": slugs, "count": len(reg), "_backend": "agency"}
            return {"personas": [p["slug"] for p in _PERSONAS], "count": len(_PERSONAS),
                    "_backend": "builtin"}
        if intent == "agents.route":
            return self._route(str(payload.get("request", "")))
        if intent == "agents.run":
            request = str(payload.get("request", ""))
            routed = self._route(request)
            persona = str(payload.get("persona") or routed["persona"])
            deliverable = None
            backend = routed.get("_backend", "builtin")
            if self._backend is not None:
                import asyncio

                # REAL: run the matched persona's own system prompt through the
                # local LLM — turning 324 loaded specialists into 324 that act.
                deliverable = await asyncio.to_thread(self._run_persona, persona, request)
                if deliverable:
                    backend = "agency+ollama"
            if not deliverable:
                deliverable = f"[{persona}] handled: {request[:80]}"
            return {
                "persona": persona,
                "request": request,
                "deliverable": deliverable,
                "status": "completed",
                "_usd": 0.0,
                "_backend": backend,
                "_mode": "real" if "ollama" in backend else "mock",
            }
        raise AssertionError("unreachable")  # pragma: no cover

    def _find_skill(self, slug: str) -> Any:
        if self._backend is None:
            return None
        try:
            for s in self._backend["registry"].all():
                if getattr(s, "slug", None) == slug:
                    return s
        except Exception:
            return None
        return None

    def _run_persona(self, slug: str, request: str) -> str | None:
        """Execute a real persona: load its system prompt and run the request
        through the local LLM (Ollama). None if unavailable -> builtin fallback."""
        import json
        import os
        import urllib.request

        from .neuro import NeuroOrgan

        model = NeuroOrgan._probe_ollama()
        skill = self._find_skill(slug)
        if not model or skill is None:
            return None
        # Keep the persona essence but stay fast enough for a local CPU model.
        system = (getattr(skill, "system_prompt", "") or getattr(skill, "body", "")
                  or getattr(skill, "description", ""))[:1800]
        host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
        body = {"model": model, "system": system, "prompt": request, "stream": False,
                "options": {"num_predict": 220, "temperature": 0.5}}
        try:
            req = urllib.request.Request(
                f"{host}/api/generate", data=json.dumps(body).encode(),
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=200) as r:
                return str(json.loads(r.read()).get("response", "")).strip() or None
        except Exception:
            return None

    def _route(self, request: str) -> dict[str, Any]:
        if self._backend is not None:
            try:
                result = self._backend["brain"].skill_for(request)
                skill = getattr(result, "skill", result)
                slug = getattr(skill, "slug", None) or getattr(result, "slug", None)
                if slug:
                    return {"persona": slug, "score": getattr(result, "score", 1),
                            "shortlist": [slug], "_backend": "agency"}
            except Exception:  # noqa: BLE001 - fall back to builtin routing
                pass
        return {**self._route_builtin(request), "_backend": "builtin"}

    def _route_builtin(self, request: str) -> dict[str, Any]:
        text = request.lower()
        scored: list[tuple[int, str]] = []
        for persona in _PERSONAS:
            score = sum(1 for kw in persona["keywords"] if kw in text)
            scored.append((score, persona["slug"]))
        scored.sort(key=lambda item: item[0], reverse=True)
        best_score, best = scored[0]
        chosen = best if best_score > 0 else "jarvis-supreme"
        shortlist = [slug for score, slug in scored[:3] if score > 0] or ["jarvis-supreme"]
        return {"persona": chosen, "score": best_score, "shortlist": shortlist}
