"""Small SDK client for BRAINIAC API."""
from __future__ import annotations

from typing import Any

import httpx


class BrainiacClient:
    def __init__(self, base_url: str, timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(timeout=timeout)

    def health(self) -> dict[str, Any]:
        r = self._client.get(f"{self.base_url}/health")
        r.raise_for_status()
        return r.json()

    def close(self) -> None:
        self._client.close()
