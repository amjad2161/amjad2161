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
    capabilities = (
        Capability("agents.list", "List the available specialist personas.", {}),
        Capability("agents.route", "Pick the best persona for a request.", {"request": "str"}),
        Capability("agents.run", "Run a persona against a request.",
                   {"request": "str", "persona": "str?"}),
    )

    async def _attach_real(self) -> None:
        from agency.jarvis_brain import SupremeJarvisBrain  # type: ignore
        from agency.skills import SkillRegistry  # type: ignore

        registry = SkillRegistry.load()
        self._backend = SupremeJarvisBrain(registry)
        self._detail["personas"] = len(registry)

    async def _invoke(self, intent: str, payload: dict[str, Any]) -> dict[str, Any]:
        if intent == "agents.list":
            return {"personas": [p["slug"] for p in _PERSONAS], "count": len(_PERSONAS)}
        if intent == "agents.route":
            return self._route(str(payload.get("request", "")))
        if intent == "agents.run":
            request = str(payload.get("request", ""))
            persona = payload.get("persona") or self._route(request)["persona"]
            return {
                "persona": persona,
                "request": request,
                "deliverable": f"[{persona}] handled: {request[:80]}",
                "status": "completed",
                "_usd": 0.0,
            }
        raise AssertionError("unreachable")  # pragma: no cover

    def _route(self, request: str) -> dict[str, Any]:
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
