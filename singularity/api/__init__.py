"""Optional HTTP gateway for the SINGULARITY (requires the ``api`` extra)."""

from __future__ import annotations

__all__ = ["create_app"]


def __getattr__(name: str):  # lazy so importing the package never requires FastAPI
    if name == "create_app":
        from .main import create_app

        return create_app
    raise AttributeError(name)
