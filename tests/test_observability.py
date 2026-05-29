from __future__ import annotations

import asyncio

from singularity import build_default_kernel
from singularity.kernel.observability import Metrics


def test_counters_gauges_histograms_render():
    m = Metrics()
    m.inc("requests_total", {"organ": "neuro"})
    m.inc("requests_total", {"organ": "neuro"})
    m.set_gauge("organs_alive", 8)
    m.observe("latency_ms", 7.0, {"organ": "neuro"})
    m.observe("latency_ms", 42.0, {"organ": "neuro"})

    snap = m.snapshot()
    assert snap["counters"]['requests_total{organ="neuro"}'] == 2.0
    assert snap["gauges"]["organs_alive"] == 8
    assert snap["histograms"]['latency_ms{organ="neuro"}']["count"] == 2

    text = m.render_prometheus()
    assert "# TYPE requests_total counter" in text
    assert "latency_ms_bucket" in text
    assert 'le="+Inf"' in text


def test_kernel_records_route_metrics():
    async def run():
        kernel = build_default_kernel(force_mock=True)
        await kernel.boot()
        await kernel.route("neuro.think", {"prompt": "hi"})
        await kernel.route("trade.status", {})
        snap = kernel.metrics.snapshot()
        await kernel.shutdown()
        return snap

    snap = asyncio.run(run())
    total = sum(v for k, v in snap["counters"].items() if k.startswith("singularity_route_total"))
    assert total >= 2
