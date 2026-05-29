"""Autopilot — the autonomous plan → act → observe loop.

This is the soul of the whole ecosystem (Mythos' loop, agency's AutonomousLoop,
SuperAGI's executor): give the organism a goal and it reasons (``neuro.plan``),
dispatches each task to the best organ, observes the result on the blackboard,
and synthesises a conclusion (``neuro.think``) — all under the governor's budget.

It is the difference between a federation that *can* be called and one that acts
on its own initiative.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:  # pragma: no cover
    from .kernel import Singularity

# Keyword → (intent, payload-builder) routing for autonomous task dispatch.
_ROUTES: tuple[tuple[tuple[str, ...], str, Callable[[str], dict[str, Any]]], ...] = (
    (("drone", "survey", "flight", "mission", "aerial", "waypoint"),
     "sky.mission_plan", lambda t: {"kind": "survey", "lat": 37.77, "lon": -122.42, "points": 6}),
    (("trade", "market", "hedge", "price", "portfolio", "futures", "risk"),
     "trade.signal", lambda t: {"symbol": "BTC_USDT"}),
    (("image", "design", "render", "visual", "art", "badge", "creative"),
     "vision.creative", lambda t: {"text": t[:24]}),
    (("search", "skill", "prompt", "knowledge", "docs", "research", "find"),
     "knowledge.search", lambda t: {"query": t, "limit": 3}),
    (("guard", "secure", "scan", "safety", "threat"),
     "nexus.guard", lambda t: {"text": t}),
)


@dataclass(slots=True)
class AutopilotStep:
    iteration: int
    task: str
    intent: str
    observation: str
    result: dict[str, Any]


@dataclass(slots=True)
class AutopilotRun:
    goal: str
    steps: list[AutopilotStep] = field(default_factory=list)
    conclusion: str = ""
    organs_engaged: list[str] = field(default_factory=list)

    @property
    def iterations(self) -> int:
        return len(self.steps)

    def as_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "iterations": self.iterations,
            "conclusion": self.conclusion,
            "organs_engaged": self.organs_engaged,
            "steps": [
                {"iteration": s.iteration, "task": s.task, "intent": s.intent,
                 "observation": s.observation}
                for s in self.steps
            ],
        }


class Autopilot:
    """Runs a bounded autonomous loop over the federation toward a goal."""

    def __init__(self, kernel: "Singularity", *, max_iterations: int = 8) -> None:
        self.kernel = kernel
        self.max_iterations = max(1, max_iterations)

    async def run(self, goal: str, context: dict[str, Any] | None = None) -> AutopilotRun:
        run = AutopilotRun(goal=goal)
        sid = f"autopilot:{goal[:32]}"
        self.kernel.memory.remember(goal, role="user", sid=sid, intent="autopilot")
        await self.kernel.bus.emit("autopilot.start", {"goal": goal})

        plan = await self.kernel.route("neuro.plan", {"goal": goal, "max_tasks": self.max_iterations})
        tasks = [t["title"] for t in plan.get("tasks", [])] or [goal]

        for i, task in enumerate(tasks[: self.max_iterations], start=1):
            intent, payload = self._dispatch(task)
            result = await self.kernel.route(intent, payload)
            observation = self._observe(intent, result)
            run.steps.append(AutopilotStep(i, task, intent, observation, result))
            organ = result.get("_organ")
            if organ and organ not in run.organs_engaged:
                run.organs_engaged.append(organ)
            await self.kernel.blackboard.write(
                f"autopilot.{goal[:24]}.step{i}", {"task": task, "intent": intent}
            )
            await self.kernel.bus.emit(
                "autopilot.step", {"iteration": i, "intent": intent, "observation": observation}
            )

        summary = "; ".join(f"{s.intent}:{s.observation}" for s in run.steps)
        thought = await self.kernel.route(
            "neuro.think", {"prompt": f"Conclude goal '{goal}'. Evidence: {summary}", "depth": "deep"}
        )
        run.conclusion = thought.get("thought", "")
        self.kernel.memory.remember(
            run.conclusion, role="assistant", sid=sid, intent="autopilot",
            meta={"organs": run.organs_engaged, "iterations": run.iterations},
        )
        await self.kernel.bus.emit("autopilot.done", {"goal": goal, "iterations": run.iterations})
        return run

    @staticmethod
    def _dispatch(task: str) -> tuple[str, dict[str, Any]]:
        lowered = task.lower()
        for keywords, intent, builder in _ROUTES:
            if any(kw in lowered for kw in keywords):
                return intent, builder(task)
        return "agents.run", {"request": task}

    @staticmethod
    def _observe(intent: str, result: dict[str, Any]) -> str:
        for key in ("signal", "status", "conclusion", "persona", "count", "anomaly", "executed"):
            if key in result:
                return f"{key}={result[key]}"
        return "ok"
