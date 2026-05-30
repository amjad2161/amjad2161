"""``BaseOrgan`` — the mock-first adapter foundation.

Concrete organs declare their ``id``, ``domain``, ``title``, ``vision`` and
``capabilities`` and implement :meth:`_invoke`. They may optionally implement
:meth:`_attach_real` to upgrade to a live backend; if that raises (missing
dependency, no credentials, no hardware) the organ falls back to a
deterministic mock so the whole singularity always boots offline.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping

from ..kernel.contracts import (
    Capability,
    Domain,
    Health,
    Liveness,
    Mode,
    OrganError,
    OrganInfo,
)
from ..kernel.ecosystem import repo_names_for_organ


class BaseOrgan:
    """Common lifecycle, health and dispatch for every organ."""

    id: str = "base"
    domain: Domain = Domain.REASONING
    title: str = "Base Organ"
    vision: str = ""
    capabilities: tuple[Capability, ...] = ()
    # Optional per-organ invocation timeout (seconds); None → kernel default.
    invoke_timeout_s: float | None = None

    def __init__(self, *, force_mock: bool = False) -> None:
        self._force_mock = force_mock or _env_force_mock()
        self._mode = Mode.MOCK
        self._liveness = Liveness.DORMANT
        self._backend: Any = None
        self._detail: dict[str, Any] = {}
        self._intents = {cap.intent for cap in self.capabilities}

    # -- lifecycle --------------------------------------------------------
    async def boot(self) -> None:
        self._liveness = Liveness.BOOTING
        self._detail.clear()
        if not self._force_mock:
            try:
                await self._attach_real()
                self._mode = Mode.REAL
                self._detail["backend"] = "real"
            except Exception as exc:  # noqa: BLE001 - degrade to mock, never crash boot
                self._mode = Mode.MOCK
                self._detail["backend"] = "mock"
                self._detail["real_error"] = type(exc).__name__
        else:
            self._mode = Mode.MOCK
            self._detail["backend"] = "mock"
        await self._on_boot()
        self._liveness = Liveness.ALIVE

    async def shutdown(self) -> None:
        try:
            await self._on_shutdown()
        finally:
            self._liveness = Liveness.DORMANT
            self._backend = None

    def degrade(self, reason: str = "") -> None:
        """Mark the organ DEGRADED — responding with reduced fidelity but still
        invokable. Used by the watchdog when reboots are exhausted, so the organ
        becomes usable-but-degraded instead of staying DOWN and rejecting calls.
        """
        self._liveness = Liveness.DEGRADED
        if reason:
            self._detail["degraded"] = reason

    # -- health / describe ------------------------------------------------
    def health(self) -> Health:
        return Health(self.id, self._liveness, self._mode, dict(self._detail))

    def describe(self) -> OrganInfo:
        return OrganInfo(
            id=self.id,
            domain=self.domain,
            title=self.title,
            vision=self.vision,
            repos=repo_names_for_organ(self.id),
            capabilities=list(self.capabilities),
            mode=self._mode,
        )

    # -- dispatch ---------------------------------------------------------
    async def invoke(self, intent: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        if self._liveness not in (Liveness.ALIVE, Liveness.DEGRADED):
            raise OrganError(f"organ {self.id!r} is not alive (state={self._liveness.value})")
        if intent not in self._intents:
            raise OrganError(f"organ {self.id!r} does not handle intent {intent!r}")
        result = await self._invoke(intent, dict(payload))
        result.setdefault("_organ", self.id)
        result.setdefault("_mode", self._mode.value)
        # Honest provenance: every result declares what produced it.
        result.setdefault("_backend", "builtin" if self._backend is None else "real")
        return result

    # -- hooks for subclasses --------------------------------------------
    async def _attach_real(self) -> None:
        raise RuntimeError("no real backend configured")

    async def _on_boot(self) -> None:  # pragma: no cover - default no-op
        return None

    async def _on_shutdown(self) -> None:  # pragma: no cover - default no-op
        return None

    async def _invoke(self, intent: str, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    # -- helpers ----------------------------------------------------------
    @staticmethod
    def repos_root() -> Path | None:
        """Locate the sibling-repos checkout, if present (for ASSET organs)."""

        override = os.environ.get("SINGULARITY_REPOS_ROOT")
        candidates = [override] if override else []
        candidates += ["/agent/repos", str(Path(__file__).resolve().parents[3])]
        for candidate in candidates:
            if candidate and Path(candidate).is_dir():
                return Path(candidate)
        return None


def _env_force_mock() -> bool:
    return os.environ.get("SINGULARITY_FORCE_MOCK", "").lower() in ("1", "true", "yes")
