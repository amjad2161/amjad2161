"""JARVIS — the unified commander over the real federation.

One organism: a single entry point that turns a natural-language goal into
action. It **plans** with the real reasoning core (neuro), **routes** each step
to the best organ, **executes independent steps in PARALLEL** across the whole
federation (the army of specialist sub-agents), then **synthesises** a
conclusion with the brain and optionally **speaks** it.

    from singularity import build_default_kernel
    from singularity.jarvis import Jarvis

    async with build_default_kernel() as k:
        jarvis = Jarvis(k)
        result = await jarvis.command("check the market and look at my screen")
        print(result["conclusion"])

This is what unifies the standalone JARVIS computer-use agent with the SINGULARITY
kernel: plan -> parallel multi-organ execution -> synthesis, all on real backends.
"""
from __future__ import annotations

from typing import Any

# Keyword -> (intent, payload-builder). First match wins; default routes the
# step to a specialist persona via the agents organ.
_ROUTES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("drone", "fly", "mission", "survey", "flight", "telemetry", "waypoint"), "sky.telemetry"),
    (("market", "trade", "price", "signal", "backtest", "hedge", "stock", "crypto"), "trade.signal"),
    (("screenshot", "screen", "see", "look", "describe", "image", "photo", "picture"), "vision.analyze"),
    (("skill", "knowledge", "search", "find", "lookup", "document", "docs"), "knowledge.search"),
    (("browse", "web", "url", "fetch", "website", "http", "page"), "control.browse"),
    (("anomaly", "sensor", "telemetry", "publish", "sync", "device"), "nexus.telemetry"),
    (("proxy", "cors", "egress", "tunnel"), "net.proxy_url"),
    (("humanize", "rewrite", "rephrase"), "neuro.humanize"),
    (("think", "reason", "analyse", "analyze", "explain", "why"), "neuro.think"),
)


class Jarvis:
    """The unified JARVIS commander over a booted kernel."""

    def __init__(self, kernel: Any, voice: Any = None) -> None:
        self.kernel = kernel
        self.voice = voice

    # -- routing ---------------------------------------------------------------
    def _intent_for(self, title: str) -> tuple[str, dict[str, Any]]:
        t = title.lower()
        for keys, intent in _ROUTES:
            if any(k in t for k in keys):
                return intent, self._payload(intent, title)
        return "agents.route", {"request": title}

    def _payload(self, intent: str, title: str) -> dict[str, Any]:
        if intent == "trade.signal":
            return {"symbol": "BTC/USDT"}
        if intent == "knowledge.search":
            return {"query": title, "limit": 5}
        if intent == "control.browse":
            return {"url": _first_url(title) or "https://example.com"}
        if intent == "nexus.telemetry":
            return {"sensor": "jarvis", "value": float(len(title) % 50)}
        if intent == "net.proxy_url":
            return {"url": _first_url(title) or "https://example.com"}
        if intent in ("neuro.think", "neuro.humanize"):
            return {"prompt": title, "text": title}
        if intent == "vision.analyze":
            return {}  # caller may inject image_path
        return {"goal": title}

    # -- the loop --------------------------------------------------------------
    async def command(self, goal: str, *, max_tasks: int = 5) -> dict[str, Any]:
        """Plan -> parallel multi-organ execute -> synthesise -> (speak)."""
        # 1) PLAN with the real reasoning core.
        plan = await self.kernel.route("neuro.plan", {"goal": goal, "max_tasks": max_tasks})
        tasks = plan.get("tasks", []) or [{"title": goal}]
        titles = [str(t.get("title", t) if isinstance(t, dict) else t) for t in tasks]

        # 2) EXECUTE every independent step IN PARALLEL across the federation.
        calls = [self._intent_for(title) for title in titles]
        results = await self.kernel.fanout(calls) if calls else []

        # 3) SYNTHESISE a conclusion with the brain.
        digest = "; ".join(
            f"{intent}->{_brief(res)}" for (intent, _), res in zip(calls, results)
        )
        synth = await self.kernel.route(
            "neuro.think",
            {"prompt": f"Goal: {goal}\nResults from the federation: {digest}\n"
                       "Give a concise one-paragraph conclusion for the operator."},
        )
        conclusion = str(synth.get("thought", "")) or "done"

        # 4) SPEAK it (if a voice backend is attached) — in the brain's own voice
        # when the backend supports per-agent voices, else plainly.
        if self.voice is not None:
            try:
                speak_as = getattr(self.voice, "speak_as", None)
                if callable(speak_as):
                    speak_as("neuro", conclusion[:400])
                else:
                    self.voice.speak(conclusion[:400])
            except Exception:  # noqa: BLE001 - voice is best-effort
                pass

        return {
            "goal": goal,
            "plan": titles,
            "executed": [intent for intent, _ in calls],
            "organs_engaged": sorted({intent.split(".")[0] for intent, _ in calls}),
            "results": results,
            "conclusion": conclusion,
            "parallel": True,
        }


def _brief(result: Any) -> str:
    if not isinstance(result, dict):
        return str(result)[:60]
    for key in ("signal", "description", "thought", "last", "anomaly", "title", "count",
                "status", "ok", "hits"):
        if key in result:
            return f"{key}={str(result[key])[:50]}"
    return result.get("_backend", "ok")


def _first_url(text: str) -> str | None:
    import re

    m = re.search(r"https?://[^\s\"'<>]+", text)
    return m.group(0) if m else None
