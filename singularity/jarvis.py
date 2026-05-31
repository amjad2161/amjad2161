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


# Each organ's default intent (used when learned routing picks an organ).
_ORGAN_INTENT = {
    "neuro": "neuro.think", "agents": "agents.route", "knowledge": "knowledge.search",
    "sky": "sky.telemetry", "trade": "trade.signal", "vision": "vision.analyze",
    "nexus": "nexus.telemetry", "net": "net.proxy_url", "control": "control.browse",
}


class Jarvis:
    """The unified JARVIS commander over a booted kernel."""

    def __init__(self, kernel: Any, voice: Any = None, evolver: Any = None) -> None:
        self.kernel = kernel
        self.voice = voice
        self.evolver = evolver  # optional self-learning layer

    # -- routing ---------------------------------------------------------------
    def _intent_for(self, title: str) -> tuple[str, dict[str, Any], str]:
        t = title.lower()
        # 1) learned routing: if experience says a term strongly maps to an organ.
        if self.evolver is not None:
            for word in t.split():
                organ = self.evolver.learned_organ(word)
                if organ and organ in _ORGAN_INTENT:
                    intent = _ORGAN_INTENT[organ]
                    return intent, self._payload(intent, title), word
        # 2) static keyword router.
        for keys, intent in _ROUTES:
            for k in keys:
                if k in t:
                    return intent, self._payload(intent, title), k
        return "agents.route", {"request": title}, ""

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
        """Plan -> parallel multi-organ execute -> synthesise -> (speak).

        Everything here is conditioned on the LIVE context (time + state + memory +
        surroundings), so the plan and the routing adapt to the moment."""
        # 1) Build the dynamic context and PLAN on it (the self-adapting principle).
        ctx = ""
        snap: dict[str, Any] = {}
        try:
            from .context import Context

            snap = await Context.snapshot(self.kernel, self.evolver)
            ctx = Context.render(snap)
        except Exception:
            ctx = ""
        plan_goal = f"{ctx}\n\nGoal: {goal}" if ctx else goal
        plan = await self.kernel.route("neuro.plan", {"goal": plan_goal, "max_tasks": max_tasks})
        tasks = plan.get("tasks", []) or [{"title": goal}]
        titles = [str(t.get("title", t) if isinstance(t, dict) else t) for t in tasks]

        # 2) EXECUTE every step IN PARALLEL — but ADAPT routing to live state:
        #    a step routed to a DOWN organ is redirected to a live specialist.
        down = set(snap.get("down_organs") or [])
        routed: list[tuple[str, dict[str, Any], str]] = []
        for title in titles:
            intent, payload, term = self._intent_for(title)
            if intent.split(".")[0] in down:
                intent, payload = "agents.route", {"request": title}
            routed.append((intent, payload, term))
        calls = [(intent, payload) for intent, payload, _ in routed]
        results = await self.kernel.fanout(calls) if calls else []

        # 3) SYNTHESISE a conclusion with the brain.
        digest = "; ".join(
            f"{intent}->{_brief(res)}" for (intent, _, _), res in zip(routed, results)
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

        # 5) LEARN — record the experience and reinforce learned routing.
        reward = None
        if self.evolver is not None:
            try:
                reward = self.evolver.observe(
                    goal, titles,
                    [(term, intent.split(".")[0]) for intent, _, term in routed],
                    results, conclusion)
            except Exception:  # noqa: BLE001 - learning is best-effort
                reward = None

        return {
            "goal": goal,
            "plan": titles,
            "executed": [intent for intent, _, _ in routed],
            "organs_engaged": sorted({intent.split(".")[0] for intent, _, _ in routed}),
            "results": results,
            "conclusion": conclusion,
            "parallel": True,
            "reward": reward,
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


def _load_voice() -> Any:
    """Best-effort voice backend (the local jarvis_voice if importable)."""
    try:
        import importlib

        return importlib.import_module("jarvis_voice").Voice()
    except Exception:
        return None


async def awaken(*, voice: bool = False, open_browser: bool = True, sentinel: bool = False,
                 host: str = "127.0.0.1", port: int = 8088, goal: str | None = None) -> None:
    """It all as one: boot the kernel (real organs), serve the live dashboard,
    enable per-agent voice, and run the interactive JARVIS commander — all in ONE
    process sharing ONE kernel + event bus, so the dashboard shows exactly what
    JARVIS does as it does it."""
    import asyncio
    import contextlib
    import webbrowser

    from .kernel.kernel import build_default_kernel

    kernel = build_default_kernel(supervise=True)
    await kernel.boot()
    real = kernel.status().get("real_mode", "?")

    server = None
    server_task = None
    try:  # shared-kernel API + dashboard server (optional; needs the api extra)
        import uvicorn

        from .api.main import create_app

        app = create_app(kernel=kernel)
        config = uvicorn.Config(app, host=host, port=port, log_level="warning", lifespan="off")
        server = uvicorn.Server(config)
        server_task = asyncio.create_task(server.serve())
        for _ in range(60):  # wait until it is actually serving
            if getattr(server, "started", False):
                break
            await asyncio.sleep(0.1)
    except Exception as exc:  # noqa: BLE001
        print(f"(dashboard server unavailable: {exc}) — continuing headless")

    url = f"http://{host}:{port}/"
    print(f"\n  ===  J A R V I S   A W A K E N E D  ===  {real}/9 organs REAL")
    if server is not None:
        print(f"  living interface: {url}\n")
        if open_browser:
            with contextlib.suppress(Exception):
                webbrowser.open(url)

    v = _load_voice() if voice else None
    jarvis = Jarvis(kernel, voice=v)

    sentinel_task = None
    if sentinel:  # PROACTIVE: sense the environment and react on its own
        from .sentinel import Sentinel

        sentinel_task = asyncio.create_task(
            Sentinel(kernel, voice=v).watch_forever(interval_s=20.0))
        print("  sentinel: proactive monitoring on (greets on presence, alerts on motion)")
    if v is not None:
        with contextlib.suppress(Exception):
            v.speak_as("jarvis", f"JARVIS awakened. {real} of nine organs are real. I am ready.")

    async def handle(g: str) -> None:
        res = await jarvis.command(g)
        print("JARVIS ›", res["conclusion"])
        print(f"  (parallel organs: {', '.join(res['organs_engaged'])})")

    try:
        if goal:
            await handle(goal)
        else:
            print("Speak or type a goal (or 'exit')." if v else "Type a goal (or 'exit').")
            while True:
                try:
                    if v is not None:
                        g, src = await asyncio.to_thread(v.listen)
                        if src == "speech":
                            print(f"you (spoken) › {g}")
                    else:
                        g = (await asyncio.to_thread(input, "\nyou › ")).strip()
                except (EOFError, KeyboardInterrupt):
                    break
                if not g:
                    continue
                if g.lower() in ("exit", "quit", "יציאה"):
                    break
                await handle(g)
    finally:
        if server is not None and server_task is not None:
            server.should_exit = True
            with contextlib.suppress(Exception):
                await server_task
        if sentinel_task is not None:
            sentinel_task.cancel()
            with contextlib.suppress(Exception):
                await sentinel_task
        await kernel.shutdown()
        if v is not None:
            with contextlib.suppress(Exception):
                v.speak_as("jarvis", "Goodbye, sir.")


def awaken_main(**kwargs: Any) -> int:
    import asyncio

    try:
        asyncio.run(awaken(**kwargs))
    except KeyboardInterrupt:
        pass
    return 0
