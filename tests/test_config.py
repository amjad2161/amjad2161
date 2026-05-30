from __future__ import annotations

import os

from singularity import build_default_kernel
from singularity.kernel.config import SingularityConfig


def test_from_env(monkeypatch=None):
    os.environ["SINGULARITY_FORCE_MOCK"] = "true"
    os.environ["SINGULARITY_MAX_CALLS_PER_MINUTE"] = "42"
    os.environ["SINGULARITY_AUTOPILOT_MAX_ITER"] = "5"
    try:
        cfg = SingularityConfig.from_env()
        assert cfg.force_mock is True
        assert cfg.max_calls_per_minute == 42
        assert cfg.autopilot_max_iterations == 5
    finally:
        for k in ("SINGULARITY_FORCE_MOCK", "SINGULARITY_MAX_CALLS_PER_MINUTE",
                  "SINGULARITY_AUTOPILOT_MAX_ITER"):
            os.environ.pop(k, None)


def test_config_drives_kernel_governor():
    cfg = SingularityConfig(force_mock=True, max_calls_per_minute=7)
    kernel = build_default_kernel(config=cfg)
    assert kernel.config.max_calls_per_minute == 7
    assert kernel.governor.max_calls_per_minute == 7


def test_from_toml(tmp_path):
    import importlib.util

    if importlib.util.find_spec("tomllib") is None and importlib.util.find_spec("tomli") is None:
        import pytest

        pytest.skip("no TOML parser available (py3.10 without tomli)")
    p = tmp_path / "s.toml"
    p.write_text("[singularity]\nforce_mock = true\nautopilot_max_iterations = 3\n")
    cfg = SingularityConfig.from_toml(str(p))
    assert cfg.force_mock is True and cfg.autopilot_max_iterations == 3
