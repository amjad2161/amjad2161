from __future__ import annotations

import asyncio

from singularity import build_default_kernel
from singularity.kernel.persistence import JSONCheckpointer, MemoryCheckpointer


def test_memory_checkpointer_roundtrip():
    cp = MemoryCheckpointer()
    cp.save("a", {"x": 1})
    assert cp.load("a") == {"x": 1}
    assert cp.list() == ["a"]
    assert cp.delete("a") is True
    assert cp.load("a") is None


def test_json_checkpointer_roundtrip(tmp_path):
    cp = JSONCheckpointer(directory=tmp_path)
    cp.save("run-1", {"k": [1, 2, 3]})
    assert cp.load("run-1") == {"k": [1, 2, 3]}
    assert "run-1" in cp.list()


def test_kernel_checkpoint_and_restore():
    async def run():
        kernel = build_default_kernel(force_mock=True)
        await kernel.boot()
        await kernel.blackboard.write("memo", {"phase": 1})
        kernel.checkpoint("snap")
        # mutate, then restore
        await kernel.blackboard.write("memo", {"phase": 99})
        restored = kernel.restore("snap")
        value = kernel.blackboard.read("memo")
        await kernel.shutdown()
        return restored, value

    restored, value = asyncio.run(run())
    assert restored is True
    assert value == {"phase": 1}
