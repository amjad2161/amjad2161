"""CONTEXT — the dynamic, time-and-state-aware adaptation engine.

The recurring idea across the surfaced repos is one operating principle: behaviour
must be **dynamic, interactive and self-adapting** — it changes with TIME and
STATE and applies to *everything*. This module is that principle, made concrete.

``Context.snapshot`` assembles a live situational picture — the wall-clock time
and day-phase, which organs are real / mock / down right now, the most recent
nervous-system events, the agent's self-edited memory, and (optionally) what the
camera senses around it. ``Context.render`` turns it into the conditioning text
the planner reads, so JARVIS **plans differently at night than at noon, leans on
the organs that are actually real, avoids organs that are down, and reacts to its
surroundings** — every run adapts to the moment.
"""
from __future__ import annotations

from typing import Any


class Context:
    """Builds and renders the live operating context for adaptive behaviour."""

    @staticmethod
    async def snapshot(kernel: Any, evolver: Any = None, *,
                       sense_presence: bool = False) -> dict[str, Any]:
        import datetime

        now = datetime.datetime.now()  # noqa: DTZ005 - local wall-clock is intended
        hour = now.hour
        phase = ("night" if hour < 6 else "morning" if hour < 12
                 else "afternoon" if hour < 18 else "evening")

        status = kernel.status()
        health = status.get("health", []) or []
        organs = {h["organ"]: {"mode": h.get("mode"), "alive": bool(h.get("ok", True))}
                  for h in health}
        real_organs = [o for o, v in organs.items() if v["mode"] == "real" and v["alive"]]
        down_organs = [o for o, v in organs.items() if not v["alive"]]

        events: list[str] = []
        try:
            events = [s.topic for s in kernel.bus.history("#")[-6:]]
        except Exception:
            events = []

        memory = ""
        if evolver is not None:
            try:
                memory = evolver.store.memory_render()
            except Exception:
                memory = ""

        presence = None
        if sense_presence:
            try:
                w = await kernel.route("vision.watch", {"frames": 4})
                presence = w.get("summary")
            except Exception:
                presence = None

        return {
            "time": now.strftime("%Y-%m-%d %H:%M"),
            "hour": hour,
            "phase": phase,
            "real_mode": status.get("real_mode"),
            "real_organs": real_organs,
            "down_organs": down_organs,
            "recent_events": events,
            "memory": memory,
            "presence": presence,
        }

    @staticmethod
    def render(snap: dict[str, Any]) -> str:
        lines = [
            f"Time: {snap.get('time')} ({snap.get('phase')}).",
            f"State: {snap.get('real_mode')}/9 organs real and live; "
            f"available = {', '.join(snap.get('real_organs') or []) or 'none'}.",
        ]
        if snap.get("down_organs"):
            lines.append(f"Currently DOWN (avoid routing to these): "
                         f"{', '.join(snap['down_organs'])}.")
        if snap.get("recent_events"):
            lines.append(f"Recent activity: {', '.join(snap['recent_events'][-4:])}.")
        if snap.get("presence"):
            lines.append(f"Surroundings: {snap['presence']}.")
        if snap.get("memory"):
            lines.append(f"What I remember:\n{snap['memory']}")
        lines.append("Adapt the plan to the current time, state and context.")
        return "\n".join(lines)
