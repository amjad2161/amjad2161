"""Tests for REEL-MAKER viral video pipeline."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from brainiac.core import CreativeEngine
from brainiac.core.reel_maker import HookType, JobStatus, Platform, ReelMaker, ReelStyle


@pytest.fixture
def reel_maker(tmp_path: Path) -> ReelMaker:
    return ReelMaker(output_dir=tmp_path)


@pytest.mark.asyncio
async def test_compose_creates_vertical_video(reel_maker: ReelMaker) -> None:
    job = await reel_maker.compose(
        "AI productivity hacks",
        style=ReelStyle.VIRAL_HOOK,
        platforms=[Platform.TIKTOK],
        voiceover=False,
    )
    assert job.status.value == "ready"
    assert job.video_path
    assert Path(job.video_path).is_file()
    assert job.script is not None
    assert job.algorithm_score > 0
    assert job.script.hook


@pytest.mark.asyncio
async def test_publish_dry_run(reel_maker: ReelMaker) -> None:
    job = await reel_maker.compose(
        "morning routine",
        platforms=[Platform.INSTAGRAM, Platform.TIKTOK],
        voiceover=False,
    )
    result = await reel_maker.publish(job.job_id, dry_run=True)
    assert result["dry_run"] is True
    assert "instagram" in result["platforms"]
    assert "tiktok" in result["platforms"]


def test_trends_and_platform_specs(reel_maker: ReelMaker) -> None:
    trends = reel_maker.get_trends("fitness")
    assert trends["viral_hooks"]
    assert trends["trending_hashtags"]
    specs = reel_maker.list_platform_specs()
    platforms = {s["platform"] for s in specs}
    assert platforms == {"tiktok", "instagram", "youtube", "facebook"}


def test_diagnostics_online(reel_maker: ReelMaker) -> None:
    diag = reel_maker.diagnostics()
    assert diag["status"] == "ONLINE"
    assert "tiktok" in diag["platforms_supported"]


def test_creative_palette_integration(tmp_path: Path) -> None:
    reel = ReelMaker(output_dir=tmp_path, creative=CreativeEngine())
    palettes = reel._visual_palettes(ReelStyle.VIRAL_HOOK)
    assert len(palettes) >= 4
    assert all(len(pair) == 2 for pair in palettes)


@pytest.mark.asyncio
async def test_hook_type_override(reel_maker: ReelMaker) -> None:
    job = await reel_maker.compose(
        "crypto tips",
        hook_type=HookType.SHOCK_STAT,
        voiceover=False,
    )
    assert job.script is not None
    assert job.script.hook_type == HookType.SHOCK_STAT


@pytest.mark.asyncio
async def test_job_persistence_across_instances(tmp_path: Path) -> None:
    maker1 = ReelMaker(output_dir=tmp_path)
    job = await maker1.compose(
        "persist test",
        platforms=[Platform.TIKTOK],
        voiceover=False,
    )
    assert job.status.value == "ready"

    maker2 = ReelMaker(output_dir=tmp_path)
    loaded = maker2.get_job(job.job_id)
    assert loaded is not None
    assert loaded.topic == "persist test"
    assert loaded.status.value == "ready"
    assert loaded.script is not None
    assert Path(loaded.video_path or "").is_file()
    assert (tmp_path / "jobs" / f"{job.job_id}.json").is_file()


@pytest.mark.asyncio
async def test_publish_payload_includes_public_video_url(
    reel_maker: ReelMaker, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BRAINIAC_REEL_PUBLIC_BASE_URL", "https://api.example.com")
    from brainiac.core import reel_maker as rm

    monkeypatch.setattr(rm, "PUBLIC_BASE_URL", "https://api.example.com")

    job = await reel_maker.compose("public url test", voiceover=False)
    payload = reel_maker._build_publish_payload(job, Platform.INSTAGRAM)
    assert payload["video_url"] == f"https://api.example.com/api/v1/reel/jobs/{job.job_id}/video"


@pytest.mark.asyncio
async def test_schedule_publish_returns_scheduled(reel_maker: ReelMaker) -> None:
    job = await reel_maker.compose("schedule me", voiceover=False)
    future = time.time() + 3600
    result = await reel_maker.publish(job.job_id, schedule_at=future, dry_run=True)
    assert result["status"] == "scheduled"
    assert result["scheduled_at"] == future
    loaded = reel_maker.get_job(job.job_id)
    assert loaded is not None
    assert loaded.scheduled_publish_at == future
    assert loaded.scheduled_platforms is not None


@pytest.mark.asyncio
async def test_delete_job_removes_persistence(tmp_path: Path) -> None:
    maker = ReelMaker(output_dir=tmp_path)
    job = await maker.compose("delete me", voiceover=False)
    job_json = tmp_path / "jobs" / f"{job.job_id}.json"
    assert job_json.is_file()
    assert maker.delete_job(job.job_id) is True
    assert maker.get_job(job.job_id) is None
    assert not job_json.is_file()


def test_cleanup_expired_jobs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from brainiac.core import reel_maker as rm
    from brainiac.core.reel_maker import ReelJob

    monkeypatch.setattr(rm, "JOB_TTL_DAYS", 7)
    maker = ReelMaker(output_dir=tmp_path)
    old_job_id = "oldjob123456"
    stale = ReelJob(
        job_id=old_job_id,
        topic="stale",
        style=ReelStyle.VIRAL_HOOK,
        platforms=[Platform.TIKTOK],
        status=JobStatus.READY,
        created_at=time.time() - 8 * 86400,
    )
    maker._jobs[old_job_id] = stale
    maker._save_job(stale)
    removed = maker.cleanup_expired_jobs()
    assert removed == 1
    assert maker.get_job(old_job_id) is None


@pytest.mark.asyncio
async def test_use_ai_script_false_uses_template(reel_maker: ReelMaker) -> None:
    mock_neuro = MagicMock()
    mock_neuro.think = AsyncMock()
    reel_maker.set_dependencies(neuro=mock_neuro)
    job = await reel_maker.compose(
        "template only",
        voiceover=False,
        use_ai_script=False,
    )
    assert job.script_source == "template"
    mock_neuro.think.assert_not_called()


@pytest.mark.asyncio
async def test_ai_script_fallback_on_neuro_error(reel_maker: ReelMaker) -> None:
    mock_neuro = MagicMock()
    mock_neuro.think = AsyncMock(side_effect=RuntimeError("api down"))
    reel_maker.set_dependencies(neuro=mock_neuro)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-real-looking-key")
    from brainiac.core import reel_maker as rm

    monkeypatch.setattr(rm, "_DUMMY_API_KEYS", frozenset({"dummy-key-for-ci", ""}))
    try:
        job = await reel_maker.compose(
            "fallback topic",
            voiceover=False,
            use_ai_script=True,
        )
    finally:
        monkeypatch.undo()
    assert job.script_source == "template"
    assert job.script is not None


@pytest.mark.asyncio
async def test_neuro_script_when_available(reel_maker: ReelMaker) -> None:
    from brainiac.core.neuro_core import ReasoningDepth, Thought

    payload: dict[str, Any] = {
        "hook": "Stop scrolling now",
        "body_lines": ["Line one", "Line two", "Line three"],
        "cta": "Follow for more",
        "hook_type": "curiosity_gap",
        "title": "AI hacks",
        "on_screen_text": ["Stop scrolling", "Line one", "Line two", "Follow"],
    }
    mock_neuro = MagicMock()
    mock_neuro.think = AsyncMock(
        return_value=Thought(
            content=__import__("json").dumps(payload),
            model="claude-test",
            depth=ReasoningDepth.FAST,
            tokens_used=60,
            latency_ms=100.0,
            cached=False,
        )
    )
    reel_maker.set_dependencies(neuro=mock_neuro)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-real-looking-key")
    from brainiac.core import reel_maker as rm

    monkeypatch.setattr(rm, "_DUMMY_API_KEYS", frozenset({"dummy-key-for-ci", ""}))
    try:
        job = await reel_maker.compose(
            "neuro topic",
            voiceover=False,
            use_ai_script=True,
        )
    finally:
        monkeypatch.undo()
    assert job.script_source == "neuro_core"
    assert job.script is not None
    assert job.script.hook == "Stop scrolling now"


def test_social_status_without_tokens(reel_maker: ReelMaker) -> None:
    status = reel_maker.social_status()
    assert status["webhook_configured"] is False
    assert "instagram" in status["platforms"]
    assert status["platforms"]["instagram"]["configured"] is False
    assert "INSTAGRAM_ACCESS_TOKEN" in status["platforms"]["instagram"]["missing_env"]
    assert status["platforms"]["instagram"]["oauth_hint"]
    assert status["accounts"] == []
    assert "oauth_providers" in status
    assert "meta" in status["oauth_providers"]
    assert "connect_all" in status
    assert status["connect_all"]["group_id"]


@pytest.mark.asyncio
async def test_webhook_on_compose_ready(
    reel_maker: ReelMaker, monkeypatch: pytest.MonkeyPatch
) -> None:
    from brainiac.core import reel_maker as rm

    calls: list[dict[str, object]] = []

    async def capture(event: str, job: Any, *, extra: dict[str, Any] | None = None) -> None:
        calls.append({"event": event, "job_id": job.job_id, "extra": extra})

    monkeypatch.setattr(rm, "WEBHOOK_URL", "https://hooks.example.com/reel")
    monkeypatch.setattr(reel_maker, "_emit_webhook", capture)
    job = await reel_maker.compose("webhook topic", voiceover=False)
    assert job.status.value == "ready"
    assert calls
    assert calls[0]["event"] == "compose.ready"


@pytest.mark.asyncio
async def test_webhook_signature_header(
    reel_maker: ReelMaker, monkeypatch: pytest.MonkeyPatch
) -> None:
    from brainiac.core import reel_maker as rm

    captured: dict[str, Any] = {}

    class FakeResponse:
        status_code = 200
        content = b""

    class FakeClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> FakeClient:
            return self

        async def __aexit__(self, *args: Any) -> None:
            return None

        async def post(self, url: str, *, content: bytes, headers: dict[str, str]) -> FakeResponse:
            captured["url"] = url
            captured["content"] = content
            captured["headers"] = headers
            return FakeResponse()

    import httpx

    monkeypatch.setattr(rm, "WEBHOOK_URL", "https://hooks.example.com/reel")
    monkeypatch.setattr(rm, "WEBHOOK_SECRET", "test-secret")
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    job = await reel_maker.compose("signed webhook", voiceover=False)
    assert job.status.value == "ready"
    assert captured["headers"]["X-Brainiac-Signature"].startswith("sha256=")
