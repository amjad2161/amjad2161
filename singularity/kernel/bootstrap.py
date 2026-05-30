"""Bootstrap — make the real sibling repositories importable.

Authenticity demands that the organs run the *actual* code of the federated
repositories, not look-alikes. This module locates the checkout root (default
``/agent/repos`` or ``SINGULARITY_REPOS_ROOT``) and puts each repo's import path
on ``sys.path`` so organs can ``import skycore`` / ``import agency`` /
``import mythos`` / ``import brainiac`` and call the genuine implementations.

If a repo is absent the import simply fails and the organ falls back to its
deterministic builtin — honestly reported, never faked.
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from types import ModuleType

# package import-name -> repo-relative path(s) that must be on sys.path
_SIBLINGS: dict[str, tuple[str, ...]] = {
    # Each name may live under several repo-relative paths; the first that
    # exists wins. "SkyCore" is the real drone repo checkout name (the skycore
    # package sits directly inside it).
    "skycore": ("Dji-owner", "SkyCore"),
    "agency": ("agency-agents/runtime", "agency/runtime"),
    "mythos": ("Mythos",),
    "brainiac": ("amjad2161",),
}


def repos_root() -> Path | None:
    """Locate the multi-repo checkout root, if present."""

    override = os.environ.get("SINGULARITY_REPOS_ROOT")
    candidates = [override] if override else []
    candidates += ["/agent/repos", str(Path(__file__).resolve().parents[3])]
    for candidate in candidates:
        if candidate and Path(candidate).is_dir():
            root = Path(candidate)
            # Heuristic: a real multi-repo root contains at least one sibling.
            if any((root / rel).is_dir() for rels in _SIBLINGS.values() for rel in rels):
                return root
    return None


def _extra_paths() -> list[str]:
    """Absolute import dirs for repos that live OUTSIDE a single checkout root.

    Real machines keep repos scattered. Two generic, portable sources:
      * ``SINGULARITY_REPO_PATHS`` env var (os.pathsep-separated absolute dirs)
      * ``~/.singularity/repos.txt`` (one absolute dir per line, ``#`` comments)
    Each listed dir is the directory that makes a package importable (e.g. the
    ``runtime`` folder containing the ``agency`` package).
    """
    paths: list[str] = []
    env = os.environ.get("SINGULARITY_REPO_PATHS", "")
    if env:
        paths += [p for p in env.split(os.pathsep) if p.strip()]
    cfg = Path.home() / ".singularity" / "repos.txt"
    if cfg.is_file():
        try:
            paths += [ln.strip() for ln in cfg.read_text(encoding="utf-8").splitlines()
                      if ln.strip() and not ln.strip().startswith("#")]
        except Exception:  # noqa: BLE001 - unreadable config is non-fatal
            pass
    return paths


def ensure_paths() -> list[str]:
    """Add every available sibling repo path to ``sys.path``. Idempotent."""

    added: list[str] = []
    # 1) Scattered repos declared via env / config file (absolute dirs).
    for p in _extra_paths():
        if p and Path(p).is_dir() and p not in sys.path:
            sys.path.append(p)
            added.append(p)
    # 2) Single-checkout-root model (all siblings under one parent).
    root = repos_root()
    if root is not None:
        for rels in _SIBLINGS.values():
            for rel in rels:
                path = (root / rel).resolve()
                sp = str(path)
                if path.is_dir() and sp not in sys.path:
                    sys.path.append(sp)
                    added.append(sp)
    return added


def try_import(name: str) -> ModuleType | None:
    """Best-effort import of a real sibling package; ``None`` if unavailable."""

    ensure_paths()
    try:
        return importlib.import_module(name)
    except Exception:  # noqa: BLE001 - missing/broken backend → honest fallback
        return None


def available() -> dict[str, bool]:
    """Report which real backends can currently be imported."""

    return {name: try_import(name) is not None for name in _SIBLINGS}
