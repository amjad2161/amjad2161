"""Tests for CREATIVE-ENGINE module."""

import pytest

from brainiac.core.creative_engine import CreativeEngine, MediaType, Style


@pytest.fixture
def engine():
    return CreativeEngine()


def test_generate_text(engine):
    asset = engine.generate_text("Describe a neural network", style=Style.TECHNICAL)
    assert asset.media_type == MediaType.TEXT
    assert asset.format == "txt"
    assert len(asset.data) > 0
    assert asset.asset_id


def test_image_prompt_photorealistic(engine):
    prompt = engine.generate_image_prompt(
        subject="a futuristic space station",
        style=Style.PHOTOREALISTIC,
        width=1024,
        height=1024,
    )
    assert "ultra-realistic" in prompt["prompt"].lower() or "8K" in prompt["prompt"]
    assert prompt["size"] == "1024x1024"
    assert prompt["model"] == "dall-e-3"


def test_image_prompt_all_styles(engine):
    for style in Style:
        prompt = engine.generate_image_prompt("a robot", style=style)
        assert "prompt" in prompt
        assert len(prompt["prompt"]) > 0


def test_generate_3d_scene(engine):
    scene = engine.generate_3d_scene("A spaceship cockpit with holographic displays")
    assert "threejs_config" in scene
    assert scene["threejs_config"]["renderer"] == "WebGLRenderer"
    assert len(scene["threejs_config"]["lighting"]) >= 2


def test_compose_audio_spec(engine):
    spec = engine.compose_audio_spec(mood="epic", duration_s=60.0)
    assert spec["mood"] == "epic"
    assert spec["duration_s"] == 60.0
    assert spec["bpm"] == 140
    assert len(spec["instruments"]) > 0


def test_svg_badge(engine):
    svg = engine.generate_svg_badge("ONLINE", color="#00ff00")
    assert svg.startswith("<svg")
    assert "ONLINE" in svg
    assert "#00ff00" in svg


def test_diagnostics(engine):
    d = engine.diagnostics()
    assert d["status"] == "ONLINE"
    assert "total_assets" in d
