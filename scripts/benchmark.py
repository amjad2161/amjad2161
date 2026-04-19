"""Lightweight benchmark sanity script."""
from __future__ import annotations

import asyncio
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from brainiac.core import OrbitalNav
from brainiac.core.orbital_nav import Coordinate, TransportMode


async def main() -> None:
    nav = OrbitalNav()
    start = Coordinate(lat=32.0853, lon=34.7818)
    dest = Coordinate(lat=32.10, lon=34.80)
    t0 = time.perf_counter()
    route = await nav.route(start, dest, mode=TransportMode.DRONE)
    elapsed = (time.perf_counter() - t0) * 1000
    print(f"benchmark_ready=true distance_km={route.distance_km:.2f} elapsed_ms={elapsed:.2f}")


if __name__ == "__main__":
    asyncio.run(main())
