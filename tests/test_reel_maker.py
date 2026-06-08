"""Tests for REEL-MAKER viral video pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest

from brainiac.core import CreativeEngine
from brainiac.core.reel_maker import HookType, Platform, ReelMaker, ReelStyle


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
