"""Offline map cache layer (JSON/MBTiles stub)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class OfflineMapCache:
    def __init__(self, cache_path: str | None = None) -> None:
        self.cache_path = Path(cache_path) if cache_path else None
        self._mem: dict[str, Any] = {}

    def get(self, key: str) -> Any | None:
        if key in self._mem:
            return self._mem[key]
        if not self.cache_path or not self.cache_path.exists():
            return None
        data = json.loads(self.cache_path.read_text())
        return data.get(key)

    def set(self, key: str, value: Any) -> None:
        self._mem[key] = value
        if self.cache_path:
            payload = {}
            if self.cache_path.exists():
                payload = json.loads(self.cache_path.read_text())
            payload[key] = value
            self.cache_path.write_text(json.dumps(payload))
