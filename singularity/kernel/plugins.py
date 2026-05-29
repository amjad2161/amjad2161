"""Plugins — third-party organs without editing the kernel.

The organism grows by adding organs. This module lets external packages
contribute organs through two mechanisms:

* **Entry points** — packages declaring the ``singularity.organs`` group.
* **Spec strings** — ``module:attr`` entries via the ``SINGULARITY_PLUGINS`` env
  var (comma-separated), e.g. ``mypkg.organs:WeatherOrgan``.

Each target may be an ``Organ`` instance, a zero-arg class, or a factory; loaded
defensively so one broken plugin never blocks boot.
"""

from __future__ import annotations

import importlib
import os
from typing import Any

from .contracts import Organ


def _instantiate(obj: Any) -> Organ | None:
    try:
        candidate = obj() if isinstance(obj, type) or callable(obj) else obj
    except Exception:  # noqa: BLE001 - a broken factory must not crash discovery
        return None
    return candidate if isinstance(candidate, Organ) else None


def load_spec_organs(specs: list[str]) -> list[Organ]:
    """Load organs from ``module:attr`` spec strings."""

    organs: list[Organ] = []
    for spec in specs:
        spec = spec.strip()
        if not spec or ":" not in spec:
            continue
        module_name, _, attr = spec.partition(":")
        try:
            module = importlib.import_module(module_name)
            target = getattr(module, attr)
        except (ImportError, AttributeError):
            continue
        organ = _instantiate(target)
        if organ is not None:
            organs.append(organ)
    return organs


def load_entrypoint_organs(group: str = "singularity.organs") -> list[Organ]:
    """Load organs declared via the ``singularity.organs`` entry-point group."""

    from importlib.metadata import entry_points

    organs: list[Organ] = []
    try:
        eps = entry_points(group=group)
    except TypeError:  # pragma: no cover - very old importlib.metadata
        eps = entry_points().get(group, [])  # type: ignore[attr-defined]
    for ep in eps:
        try:
            target = ep.load()
        except Exception:  # noqa: BLE001
            continue
        organ = _instantiate(target)
        if organ is not None:
            organs.append(organ)
    return organs


def discover_plugin_organs(
    *, group: str = "singularity.organs", env_var: str = "SINGULARITY_PLUGINS"
) -> list[Organ]:
    """Discover plugin organs from entry points and the env spec list."""

    organs = load_entrypoint_organs(group)
    raw = os.environ.get(env_var, "")
    if raw:
        organs.extend(load_spec_organs([s for s in raw.split(",") if s.strip()]))
    return organs
