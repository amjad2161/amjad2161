#!/usr/bin/env python3
"""
G.A.N.E Benchmark Suite
=========================
Real latency and throughput numbers for every module — no mocks.
Run with:  python scripts/benchmark.py
"""
from __future__ import annotations

import asyncio
import statistics
import sys
import time
from pathlib import Path
from typing import Callable, Awaitable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from brainiac.core import (
    OrbitalNav, SatLink, TelemetryHub, NexusSync,
    CyberShield, CreativeEngine, SonicMatrix,
)
from brainiac.core.orbital_nav import Coordinate, TransportMode
from brainiac.core.satlink import SOSPriority
from brainiac.core.telemetry_hub import SensorReading
from brainiac.core.nexus_sync import DeviceType, Protocol


# ── Utilities ─────────────────────────────────────────────────────────────────

def _fmt_us(seconds: float) -> str:
    if seconds >= 1.0:
        return f"{seconds*1000:,.2f} ms"
    if seconds >= 0.001:
        return f"{seconds*1000:,.2f} ms"
    return f"{seconds*1_000_000:,.1f} μs"


async def bench(name: str, fn: Callable[[], Awaitable], n: int = 1000) -> dict:
    """Run an async callable N times and return timing statistics."""
    samples = []
    for _ in range(n):
        t0 = time.perf_counter()
        await fn()
        samples.append(time.perf_counter() - t0)

    samples.sort()
    return {
        "name": name,
        "n": n,
        "min":  samples[0],
        "p50":  samples[n // 2],
        "p95":  samples[int(n * 0.95)],
        "p99":  samples[int(n * 0.99)],
        "max":  samples[-1],
        "mean": statistics.mean(samples),
        "ops":  n / sum(samples),
    }


def print_result(r: dict) -> None:
    print(
        f"  {r['name']:<38} "
        f"p50={_fmt_us(r['p50']):>12}  "
        f"p99={_fmt_us(r['p99']):>12}  "
        f"ops={r['ops']:>11,.0f}/s"
    )


# ── Benchmarks ────────────────────────────────────────────────────────────────

async def bench_orbital_nav():
    print("\n[ORBITAL-NAV]")
    nav = OrbitalNav()

    print_result(await bench(
        "get_position",
        lambda: nav.get_position(),
        n=5000,
    ))

    print_result(await bench(
        "get_satellite_status",
        lambda: nav.get_satellite_status(),
        n=2000,
    ))

    origin = Coordinate(lat=32.0, lon=34.0)
    dest = Coordinate(lat=33.0, lon=35.0)
    print_result(await bench(
        "drone route (great-circle)",
        lambda: nav.route(origin, dest, mode=TransportMode.DRONE),
        n=2000,
    ))


async def bench_satlink():
    print("\n[SATLINK-X]")
    satlink = SatLink()
    await satlink.connect()

    print_result(await bench(
        "send_sos (6 channels)",
        lambda: satlink.send_sos(
            lat=32.0, lon=34.8, message="bench",
            priority=SOSPriority.ROUTINE,
        ),
        n=500,
    ))

    print_result(await bench(
        "predict_passes (24h)",
        lambda: satlink.predict_passes(lat=32.0, lon=34.8, hours_ahead=24),
        n=2000,
    ))

    print_result(await bench(
        "uplink_telemetry (PQC encrypt)",
        lambda: satlink.uplink_telemetry({"k": "v", "ts": time.time()}),
        n=5000,
    ))


async def bench_telemetry_hub():
    print("\n[TELEMETRY-HUB]")
    hub = TelemetryHub(window_size=100)

    # Warm up with 100 readings so stats are computed
    for i in range(100):
        await hub.ingest(SensorReading(sensor_id="s1", value=20.0 + (i % 10) * 0.1, unit="C"))

    counter = [0]
    async def ingest_one():
        counter[0] += 1
        await hub.ingest(SensorReading(sensor_id="s1", value=20.0 + (counter[0] % 10) * 0.1, unit="C"))

    print_result(await bench("ingest reading + anomaly check", ingest_one, n=10_000))


async def bench_nexus_sync():
    print("\n[NEXUS-SYNC]")
    nexus = NexusSync()
    nexus.register_device("bench-device", DeviceType.IOT_SENSOR, Protocol.MQTT, "mqtt://bench")
    await nexus.connect_device("bench-device")

    print_result(await bench(
        "publish (no subscribers)",
        lambda: nexus.publish("bench-device", "bench/topic", {"v": 1}),
        n=10_000,
    ))

    print_result(await bench(
        "command dispatch",
        lambda: nexus.command("bench-device", "ping"),
        n=5000,
    ))


def bench_cyber_shield():
    print("\n[CYBER-SHIELD]  (synchronous)")
    shield = CyberShield(secret_key="bench-secret")

    def scan():
        shield.scan_input("Hello world — this is a completely normal message")

    samples = []
    for _ in range(10_000):
        t0 = time.perf_counter()
        scan()
        samples.append(time.perf_counter() - t0)
    samples.sort()
    print_result({
        "name": "scan_input (clean)",
        "n": len(samples),
        "min": samples[0], "p50": samples[5000], "p95": samples[9500], "p99": samples[9900],
        "max": samples[-1], "mean": statistics.mean(samples),
        "ops": len(samples) / sum(samples),
    })

    # HMAC
    payload = {"a": 1, "b": 2, "c": "hello", "d": [1, 2, 3]}
    samples = []
    for _ in range(10_000):
        t0 = time.perf_counter()
        shield.sign(payload)
        samples.append(time.perf_counter() - t0)
    samples.sort()
    print_result({
        "name": "HMAC sign",
        "n": len(samples),
        "min": samples[0], "p50": samples[5000], "p95": samples[9500], "p99": samples[9900],
        "max": samples[-1], "mean": statistics.mean(samples),
        "ops": len(samples) / sum(samples),
    })


def bench_creative_engine():
    print("\n[CREATIVE-ENGINE]  (synchronous)")
    engine = CreativeEngine()

    samples = []
    for _ in range(5000):
        t0 = time.perf_counter()
        engine.generate_image_prompt("a futuristic drone")
        samples.append(time.perf_counter() - t0)
    samples.sort()
    print_result({
        "name": "generate_image_prompt",
        "n": len(samples),
        "min": samples[0], "p50": samples[2500], "p95": samples[4750], "p99": samples[4950],
        "max": samples[-1], "mean": statistics.mean(samples),
        "ops": len(samples) / sum(samples),
    })

    samples = []
    for _ in range(5000):
        t0 = time.perf_counter()
        engine.generate_svg_badge("ONLINE")
        samples.append(time.perf_counter() - t0)
    samples.sort()
    print_result({
        "name": "generate_svg_badge",
        "n": len(samples),
        "min": samples[0], "p50": samples[2500], "p95": samples[4750], "p99": samples[4950],
        "max": samples[-1], "mean": statistics.mean(samples),
        "ops": len(samples) / sum(samples),
    })


# ── Main ──────────────────────────────────────────────────────────────────────

async def main() -> None:
    print("""
╔══════════════════════════════════════════════════════════════════╗
║             G.A.N.E PERFORMANCE BENCHMARKS                       ║
║         Real numbers — no mocks, no network calls                ║
╚══════════════════════════════════════════════════════════════════╝
""")
    t0 = time.time()

    await bench_orbital_nav()
    await bench_satlink()
    await bench_telemetry_hub()
    await bench_nexus_sync()
    bench_cyber_shield()
    bench_creative_engine()

    print(f"\n Total benchmark duration: {time.time() - t0:.2f}s\n")
    print("═" * 70)
    print("  ✅ Benchmark complete.")
    print("═" * 70)


if __name__ == "__main__":
    asyncio.run(main())
