"""Regression tests for the PR #17 security & hardening fixes (#1–#8).

These assert the *attack inputs* are actually blocked, so a future refactor that
reintroduces a hole fails CI instead of shipping.
"""
from __future__ import annotations

import asyncio

import pytest

from singularity.kernel.event_bus import EventBus
from singularity.kernel.governor import Governor, GovernorError
from singularity.security.netguard import SSRFError, assert_safe_url
from singularity.security.safe_render import safe_color, svg_badge


# ── #1 SSRF guard ────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/",   # cloud metadata
        "http://127.0.0.1:8188/",                       # loopback
        "http://[::1]/",                                # ipv6 loopback
        "http://localhost/admin",                       # localhost name
        "http://10.0.0.5/",                             # private
        "http://192.168.1.1/",                          # private
        "http://172.16.0.1/",                           # private
        "file:///etc/passwd",                           # non-http scheme
        "gopher://127.0.0.1/",                          # non-http scheme
        "http://metadata.google.internal/",             # gcp metadata host
    ],
)
def test_ssrf_blocks_internal_targets(url: str) -> None:
    with pytest.raises(SSRFError):
        assert_safe_url(url)


def test_control_browse_blocks_ssrf() -> None:
    from singularity.organs.control import ControlOrgan

    async def run() -> dict:
        organ = ControlOrgan()
        await organ.boot()
        return await organ.invoke(
            "control.browse", {"url": "http://169.254.169.254/latest/meta-data/"}
        )

    result = asyncio.run(run())
    assert result["ok"] is False
    assert "blocked" in str(result.get("error", "")).lower()


# ── #2 / #4 output encoding ──────────────────────────────────────────────────
def test_svg_badge_neutralises_xss() -> None:
    svg = svg_badge("</text><script>alert(1)</script>", safe_color('red" onload="x', "#abcabc"))
    assert "<script>" not in svg
    assert "onload=" not in svg


def test_safe_color_allowlist() -> None:
    assert safe_color("#3b82f6") == "#3b82f6"
    assert safe_color('red" onload="x', "#000000") == "#000000"   # rejected → fallback
    assert safe_color(None, "#123abc") == "#123abc"


def test_vision_creative_is_escaped() -> None:
    from singularity.organs.vision import VisionOrgan

    async def run() -> dict:
        organ = VisionOrgan()
        await organ.boot()
        return await organ.invoke(
            "vision.creative", {"text": "</text><script>alert(1)</script>"}
        )

    result = asyncio.run(run())
    assert "<script>" not in result["svg"]


# ── #3 gateway auth fails closed ─────────────────────────────────────────────
def test_require_token_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("fastapi")
    from fastapi import HTTPException

    from singularity.security.api_auth import require_token

    class _Req:
        headers: dict[str, str] = {}

    monkeypatch.delenv("SINGULARITY_API_TOKEN", raising=False)
    # No token configured → guarded route must refuse (503), never run open.
    with pytest.raises(HTTPException) as ei:
        asyncio.run(require_token(_Req()))   # type: ignore[arg-type]
    assert ei.value.status_code == 503


def test_require_token_rejects_bad_token(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("fastapi")
    from fastapi import HTTPException

    from singularity.security.api_auth import require_token

    monkeypatch.setenv("SINGULARITY_API_TOKEN", "secret")

    class _Req:
        headers = {"authorization": "Bearer wrong"}

    with pytest.raises(HTTPException) as ei:
        asyncio.run(require_token(_Req()))   # type: ignore[arg-type]
    assert ei.value.status_code == 403


# ── #5 governor atomic reserve ───────────────────────────────────────────────
def test_governor_reserve_is_atomic_under_fanout() -> None:
    async def run() -> None:
        gov = Governor(max_calls_per_minute=2)
        # Three concurrent reservations: exactly one must be rejected, even
        # though none has "completed" yet (the old check/record split let all 3
        # through because the slot was only claimed after the await).
        async def attempt() -> bool:
            try:
                gov.reserve()
                return True
            except GovernorError:
                return False

        results = await asyncio.gather(*[attempt() for _ in range(3)])
        assert sum(results) == 2

    asyncio.run(run())


# ── #6 event-bus handler isolation ───────────────────────────────────────────
def test_eventbus_isolates_handler_exceptions() -> None:
    async def run() -> int:
        bus = EventBus()

        async def boom(_s: object) -> None:
            raise RuntimeError("observer exploded")

        def ok(_s: object) -> None:
            return None

        bus.subscribe("#", boom)
        bus.subscribe("#", ok)
        # Publish must NOT raise even though a subscriber throws.
        return await bus.emit("test.topic", {"x": 1})

    delivered = asyncio.run(run())
    assert delivered == 1   # the good handler still received it
