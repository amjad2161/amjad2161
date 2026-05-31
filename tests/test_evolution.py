"""The self-learning / evolution layer: experience + learned routing."""
from __future__ import annotations

import asyncio

from singularity.evolution import Evolver, ExperienceStore
from singularity.jarvis import Jarvis
from singularity.kernel.kernel import build_default_kernel


def test_learned_routing_improves_with_reinforcement(tmp_path: object) -> None:
    store = ExperienceStore(str(tmp_path / "ev.db"))  # type: ignore[operator]
    assert store.best_organ("widget") is None          # unseen term -> no preference
    for _ in range(3):                                  # reinforce a strong mapping
        store.reinforce("widget", "trade", 1.0)
    assert store.best_organ("widget") == "trade"        # now it has learned
    # a competing-but-worse organ does not win
    store.reinforce("widget", "vision", 0.0)
    assert store.best_organ("widget") == "trade"
    store.close()


def test_evolver_observe_records_and_reinforces(tmp_path: object) -> None:
    store = ExperienceStore(str(tmp_path / "ev.db"))   # type: ignore[operator]
    ev = Evolver(store)
    reward = ev.observe("goal", ["a task"], [("price", "trade")],
                        [{"ok": True, "signal": "HOLD"}], "concluded")
    assert reward == 1.0
    assert store.stats()["runs"] == 1
    assert store.best_organ("price", min_n=1) == "trade"
    # a failing result yields zero reward and is recorded honestly
    ev.observe("goal2", ["x"], [("price", "trade")], [{"ok": False, "error": "boom"}], "c")
    assert store.stats()["runs"] == 2
    store.close()


def test_core_memory_persists_and_self_edits(tmp_path: object) -> None:
    store = ExperienceStore(str(tmp_path / "ev.db"))   # type: ignore[operator]
    assert "JARVIS" in store.memory_get("persona")     # seeded persona
    store.memory_append("directives", "prefer the trade organ for market goals")
    store.memory_append("human", "the operator is building JARVIS")
    rendered = store.memory_render()
    assert "DIRECTIVES" in rendered and "prefer the trade organ" in rendered
    assert "HUMAN" in rendered and "building JARVIS" in rendered
    store.close()
    # persists across reopen (durable, like letta/MemGPT)
    store2 = ExperienceStore(str(tmp_path / "ev.db"))  # type: ignore[operator]
    assert "prefer the trade organ" in store2.memory_render()
    store2.close()


def test_jarvis_with_evolver_records_experience(tmp_path: object) -> None:
    store = ExperienceStore(str(tmp_path / "ev.db"))   # type: ignore[operator]

    async def run() -> dict:
        async with build_default_kernel(force_mock=True) as kernel:
            return await Jarvis(kernel, evolver=Evolver(store)).command(
                "check the market and search my skills", max_tasks=3)

    result = asyncio.run(run())
    assert result["reward"] is not None                # a reward was computed
    assert store.stats()["runs"] >= 1                  # the run was recorded
    store.close()
