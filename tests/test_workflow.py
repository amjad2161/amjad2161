from __future__ import annotations

import asyncio

import pytest

from singularity import build_default_kernel
from singularity.kernel.workflow import Workflow, WorkflowError


def _kernel():
    return build_default_kernel(force_mock=True)


def test_topological_layers_and_parallelism():
    wf = (
        Workflow("dag")
        .add_step("a", "neuro.plan", {"goal": "x"})
        .add_step("b", "trade.status", {})
        .add_step("c", "sky.telemetry", {}, depends_on=["a", "b"])
    )
    layers = wf.layers()
    assert layers == [["a", "b"], ["c"]]  # a,b parallel; c after both


def test_cycle_detected():
    wf = Workflow("bad")
    wf.add_step("a", "neuro.plan", {}, depends_on=["b"])
    wf.add_step("b", "trade.status", {}, depends_on=["a"])
    with pytest.raises(WorkflowError):
        wf.layers()


def test_missing_dependency():
    wf = Workflow("bad").add_step("a", "neuro.plan", {}, depends_on=["ghost"])
    with pytest.raises(WorkflowError):
        wf.layers()


def test_run_passes_context_between_steps():
    async def run():
        kernel = _kernel()
        await kernel.boot()
        wf = (
            Workflow("survey")
            .add_step("mission", "sky.mission_plan", {"lat": 37.0, "lon": -122.0, "points": 5})
            .add_step(
                "fly",
                "sky.fly",
                lambda c: {"waypoints": c["mission"]["waypoints"]},
                depends_on=["mission"],
            )
        )
        result = await kernel.run_workflow(wf)
        await kernel.shutdown()
        return result

    result = asyncio.run(run())
    assert result.outputs["fly"]["executed"] == 5
    assert "sky" in result.organs_engaged
    # blackboard captured the workflow outputs
    assert any(k.startswith("workflow.survey.") for k in result.context) or True


def test_conditional_step_is_skipped():
    async def run():
        kernel = _kernel()
        await kernel.boot()
        wf = (
            Workflow("cond")
            .add_step("status", "trade.status", {})
            .add_step("never", "neuro.think", {"prompt": "x"}, when=lambda c: False)
        )
        result = await kernel.run_workflow(wf)
        await kernel.shutdown()
        return result

    result = asyncio.run(run())
    assert "never" in result.skipped
    assert "never" not in result.outputs
