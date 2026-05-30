"""Persistence — checkpointing for durable, resumable state.

Adapted from LangGraph's checkpointer concept: snapshot the blackboard (and any
workflow context) so a long-running autonomous task survives a restart and can
resume from where it left off. Two backends ship: an in-memory one for tests and
a dependency-free JSON file store for real durability.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Checkpointer(Protocol):
    def save(self, key: str, state: dict[str, Any]) -> None: ...
    def load(self, key: str) -> dict[str, Any] | None: ...
    def list(self) -> list[str]: ...
    def delete(self, key: str) -> bool: ...


class MemoryCheckpointer:
    """In-process checkpoint store (default; ephemeral)."""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}

    def save(self, key: str, state: dict[str, Any]) -> None:
        self._store[key] = {"ts": time.time(), "state": json.loads(json.dumps(state, default=str))}

    def load(self, key: str) -> dict[str, Any] | None:
        entry = self._store.get(key)
        return entry["state"] if entry else None

    def list(self) -> list[str]:
        return sorted(self._store)

    def delete(self, key: str) -> bool:
        return self._store.pop(key, None) is not None


class JSONCheckpointer:
    """Durable checkpoint store backed by one JSON file per key."""

    def __init__(self, directory: str | Path = ".singularity/checkpoints") -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in key)
        return self.directory / f"{safe}.json"

    def save(self, key: str, state: dict[str, Any]) -> None:
        payload = {"key": key, "ts": time.time(), "state": state}
        self._path(key).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )

    def load(self, key: str) -> dict[str, Any] | None:
        path = self._path(key)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8")).get("state")

    def list(self) -> list[str]:
        return sorted(p.stem for p in self.directory.glob("*.json"))

    def delete(self, key: str) -> bool:
        path = self._path(key)
        if path.exists():
            path.unlink()
            return True
        return False
