"""UTF-8 console safety for the CLI.

The CLI prints arrows, box-drawing and status glyphs. On a legacy Windows
console codepage (cp1255 Hebrew, cp1252, cp437) those raise UnicodeEncodeError.
Importing this module reconfigures stdout/stderr to UTF-8 so ``singularity demo``
runs anywhere; it is a no-op where streams are already UTF-8 or cannot be
reconfigured (e.g. redirected to a pipe that rejects it).
"""
from __future__ import annotations

import sys


def enable() -> None:
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


enable()
