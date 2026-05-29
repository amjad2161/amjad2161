"""Typed configuration — env first, optional TOML, sane defaults.

Echoes BRAINIAC's ``config.py`` ethos: one typed object that the kernel and its
guards read from, hydrated from ``SINGULARITY_*`` environment variables or a
TOML file, never from scattered ``os.environ`` reads.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ[name])
    except (KeyError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ[name])
    except (KeyError, ValueError):
        return default


@dataclass(slots=True)
class SingularityConfig:
    """All runtime knobs for the kernel in one typed place."""

    force_mock: bool = False
    supervise: bool = False
    watchdog_interval_s: float = 5.0
    max_usd_per_hour: float = 0.0
    max_calls_per_minute: int = 0
    autopilot_max_iterations: int = 8
    request_timeout_s: float = 10.0
    log_level: str = "INFO"
    repos_root: str | None = None

    @classmethod
    def from_env(cls) -> "SingularityConfig":
        return cls(
            force_mock=_env_bool("SINGULARITY_FORCE_MOCK", False),
            supervise=_env_bool("SINGULARITY_SUPERVISE", False),
            watchdog_interval_s=_env_float("SINGULARITY_WATCHDOG_INTERVAL_S", 5.0),
            max_usd_per_hour=_env_float("SINGULARITY_MAX_USD_PER_HOUR", 0.0),
            max_calls_per_minute=_env_int("SINGULARITY_MAX_CALLS_PER_MINUTE", 0),
            autopilot_max_iterations=_env_int("SINGULARITY_AUTOPILOT_MAX_ITER", 8),
            request_timeout_s=_env_float("SINGULARITY_REQUEST_TIMEOUT_S", 10.0),
            log_level=os.environ.get("SINGULARITY_LOG_LEVEL", "INFO"),
            repos_root=os.environ.get("SINGULARITY_REPOS_ROOT"),
        )

    @classmethod
    def from_toml(cls, path: str) -> "SingularityConfig":
        import tomllib  # stdlib (py3.11+)

        with open(path, "rb") as fh:
            data = tomllib.load(fh)
        section = data.get("singularity", data)
        base = cls()
        known = {f for f in asdict(base)}
        merged = {**asdict(base), **{k: v for k, v in section.items() if k in known}}
        return cls(**merged)

    def as_dict(self) -> dict[str, object]:
        return asdict(self)
