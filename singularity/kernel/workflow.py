"""Workflow — a DAG orchestration engine over intents.

Adapted from LangGraph's state-graph model: a workflow is a set of **steps**
(nodes) wired by **dependencies** (edges) over a shared **context** (state).
Independent steps in the same topological layer run concurrently; a step may
build its payload from the accumulated context and may be gated by a condition.

This is the richest expression of "work together": a single declarative graph
threads a goal across many organs, with parallelism, branching and shared memory.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

from .blackboard import Blackboard

if TYPE_CHECKING:  # pragma: no cover
    from .kernel import Singularity

PayloadBuilder = "dict[str, Any] | Callable[[dict[str, Any]], dict[str, Any]]"


class WorkflowError(RuntimeError):
    """Raised for cyclic graphs, missing dependencies or duplicate steps."""


@dataclass(slots=True)
class Step:
    name: str
    intent: str
    payload: Any = field(default_factory=dict)  # dict | Callable[[context], dict]
    depends_on: tuple[str, ...] = ()
    when: Callable[[dict[str, Any]], bool] | None = None
    output_key: str | None = None


@dataclass(slots=True)
class WorkflowResult:
    name: str
    outputs: dict[str, Any]
    skipped: list[str]
    context: dict[str, Any]
    organs_engaged: list[str]
    elapsed_ms: float
    layers: list[list[str]]

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "outputs": self.outputs,
            "skipped": self.skipped,
            "organs_engaged": self.organs_engaged,
            "elapsed_ms": round(self.elapsed_ms, 2),
            "layers": self.layers,
        }


class Workflow:
    """A declarative, fluently-built DAG of intent invocations."""

    def __init__(self, name: str = "workflow") -> None:
        self.name = name
        self._steps: dict[str, Step] = {}

    def add_step(
        self,
        name: str,
        intent: str,
        payload: Any = None,
        *,
        depends_on: tuple[str, ...] | list[str] = (),
        when: Callable[[dict[str, Any]], bool] | None = None,
        output_key: str | None = None,
    ) -> "Workflow":
        if name in self._steps:
            raise WorkflowError(f"duplicate step: {name!r}")
        self._steps[name] = Step(
            name=name,
            intent=intent,
            payload={} if payload is None else payload,
            depends_on=tuple(depends_on),
            when=when,
            output_key=output_key,
        )
        return self

    # -- planning ---------------------------------------------------------
    def layers(self) -> list[list[str]]:
        """Kahn topological sort into parallelizable layers."""

        indegree = {name: 0 for name in self._steps}
        dependents: dict[str, list[str]] = {name: [] for name in self._steps}
        for step in self._steps.values():
            for dep in step.depends_on:
                if dep not in self._steps:
                    raise WorkflowError(f"step {step.name!r} depends on unknown {dep!r}")
                indegree[step.name] += 1
                dependents[dep].append(step.name)

        ready = sorted(name for name, deg in indegree.items() if deg == 0)
        layers: list[list[str]] = []
        seen = 0
        while ready:
            layers.append(ready)
            seen += len(ready)
            nxt: list[str] = []
            for name in ready:
                for child in dependents[name]:
                    indegree[child] -= 1
                    if indegree[child] == 0:
                        nxt.append(child)
            ready = sorted(nxt)
        if seen != len(self._steps):
            raise WorkflowError("workflow graph contains a cycle")
        return layers

    # -- execution --------------------------------------------------------
    async def run(
        self,
        kernel: "Singularity",
        context: dict[str, Any] | None = None,
        *,
        blackboard: Blackboard | None = None,
    ) -> WorkflowResult:
        layers = self.layers()
        ctx: dict[str, Any] = dict(context or {})
        outputs: dict[str, Any] = {}
        skipped: list[str] = []
        organs: list[str] = []
        started = time.perf_counter()

        for layer in layers:
            runnable = [self._steps[name] for name in layer if self._should_run(self._steps[name], ctx)]
            skipped.extend(name for name in layer if name not in {s.name for s in runnable})

            async def _run_step(step: Step) -> tuple[str, dict[str, Any]]:
                payload = step.payload(ctx) if callable(step.payload) else dict(step.payload)
                result = await kernel.route(step.intent, payload)
                return step.name, result

            results = await asyncio.gather(*(_run_step(s) for s in runnable))
            for name, result in results:
                step = self._steps[name]
                key = step.output_key or name
                outputs[name] = result
                ctx[key] = result
                organ = result.get("_organ")
                if organ and organ not in organs:
                    organs.append(organ)
                if blackboard is not None:
                    await blackboard.write(f"workflow.{self.name}.{key}", result)

        elapsed_ms = (time.perf_counter() - started) * 1000.0
        return WorkflowResult(
            name=self.name,
            outputs=outputs,
            skipped=skipped,
            context=ctx,
            organs_engaged=organs,
            elapsed_ms=elapsed_ms,
            layers=layers,
        )

    @staticmethod
    def _should_run(step: Step, ctx: dict[str, Any]) -> bool:
        return step.when is None or bool(step.when(ctx))
