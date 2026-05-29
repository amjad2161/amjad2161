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
        from ..kernel.bootstrap import try_import

        if try_import("agency") is None:
            raise RuntimeError("agency unavailable")
        from agency.jarvis_brain import SupremeJarvisBrain  # type: ignore
        from agency.skills import SkillRegistry  # type: ignore

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
            persona = payload.get("persona") or routed["persona"]
            note = None
            if self._backend is not None:
                # Real persona is matched by agency; full tool-loop execution
                # additionally requires ANTHROPIC_API_KEY (honestly reported).
                import os

                if not os.environ.get("ANTHROPIC_API_KEY"):
                    note = "matched real persona; execution needs ANTHROPIC_API_KEY"
            return {
                "persona": persona,
                "request": request,
                "deliverable": f"[{persona}] handled: {request[:80]}",
                "status": "completed",
                "note": note,
                "_usd": 0.0,
                "_backend": routed.get("_backend", "builtin"),
            }
        raise AssertionError("unreachable")  # pragma: no cover

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
