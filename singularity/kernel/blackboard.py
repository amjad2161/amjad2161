"""Blackboard — shared working memory for cross-organ coordination.

A blend of the classic *blackboard architecture* (organs as knowledge sources
collaborating through shared state) and LangGraph's *State with reducers*
(updates merge rather than blindly overwrite). It gives the workflow engine and
the organs a single async-safe place to accumulate knowledge during a task.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Callable

Reducer = Callable[[Any, Any], Any]


def _last_write_wins(_old: Any, new: Any) -> Any:
    return new


def append_reducer(old: Any, new: Any) -> Any:
    """Reducer that appends to a list (LangGraph's ``Annotated[list, add]``)."""

    base = list(old) if isinstance(old, list) else ([] if old is None else [old])
    base.extend(new if isinstance(new, list) else [new])
    return base


def merge_reducer(old: Any, new: Any) -> Any:
    """Reducer that shallow-merges dicts."""

    if isinstance(old, dict) and isinstance(new, dict):
        merged = dict(old)
        merged.update(new)
        return merged
    return new


class Blackboard:
    """An async-safe, reducer-aware key-value store with change history."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._reducers: dict[str, Reducer] = {}
        self._history: list[tuple[float, str, Any]] = []
        self._lock = asyncio.Lock()

    def set_reducer(self, key: str, reducer: Reducer) -> None:
        self._reducers[key] = reducer

    async def write(self, key: str, value: Any) -> Any:
        async with self._lock:
            reducer = self._reducers.get(key, _last_write_wins)
            merged = reducer(self._data.get(key), value)
            self._data[key] = merged
            self._history.append((time.time(), key, merged))
            return merged

    async def update(self, updates: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in updates.items():
            result[key] = await self.write(key, value)
        return result

    def read(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def snapshot(self) -> dict[str, Any]:
        return dict(self._data)

    def keys(self) -> list[str]:
        return list(self._data)

    def history(self, key: str | None = None) -> list[tuple[float, str, Any]]:
        if key is None:
            return list(self._history)
        return [entry for entry in self._history if entry[1] == key]

    def __len__(self) -> int:
        return len(self._data)

    def __contains__(self, key: object) -> bool:
        return key in self._data
