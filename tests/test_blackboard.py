from __future__ import annotations

import asyncio

from singularity.kernel.blackboard import Blackboard, append_reducer, merge_reducer


def test_last_write_wins_and_history():
    async def run():
        bb = Blackboard()
        await bb.write("k", 1)
        await bb.write("k", 2)
        return bb.read("k"), bb.history("k")

    value, history = asyncio.run(run())
    assert value == 2
    assert [h[2] for h in history] == [1, 2]


def test_append_reducer_accumulates():
    async def run():
        bb = Blackboard()
        bb.set_reducer("log", append_reducer)
        await bb.write("log", "a")
        await bb.write("log", ["b", "c"])
        return bb.read("log")

    assert asyncio.run(run()) == ["a", "b", "c"]


def test_merge_reducer_merges_dicts():
    async def run():
        bb = Blackboard()
        bb.set_reducer("state", merge_reducer)
        await bb.write("state", {"x": 1})
        await bb.write("state", {"y": 2})
        return bb.read("state")

    assert asyncio.run(run()) == {"x": 1, "y": 2}


def test_snapshot_and_membership():
    async def run():
        bb = Blackboard()
        await bb.update({"a": 1, "b": 2})
        return bb.snapshot(), ("a" in bb), len(bb)

    snap, has_a, size = asyncio.run(run())
    assert snap == {"a": 1, "b": 2} and has_a and size == 2
