"""Lightweight SDK client for BRAINIAC API."""
from __future__ import annotations

from typing import Any

import httpx


class BrainiacClient:
    def __init__(self, base_url: str = "http://localhost:8000", timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(base_url=self.base_url, timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "BrainiacClient":
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        self.close()

    def health(self) -> dict[str, Any]:
        response = self._client.get("/health")
        response.raise_for_status()
        return response.json()

    def diagnostics(self) -> dict[str, Any]:
        response = self._client.get("/diagnostics")
        response.raise_for_status()
        return response.json()


__all__ = ["BrainiacClient"]
