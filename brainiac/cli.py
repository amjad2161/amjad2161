"""
G.A.N.E CLI — Command-line interface for operational use.

Usage:
    python -m brainiac.cli status                           — module status
    python -m brainiac.cli serve                            — start API server
    python -m brainiac.cli nav route <olat,olon> <dlat,dlon> [mode] [lang]
    python -m brainiac.cli nav position                     — current GPS position
    python -m brainiac.cli medical triage <HR> <RR> <SBP> <GCS>
    python -m brainiac.cli medical dose <drug> <weight_kg>
    python -m brainiac.cli boot                             — full orchestrator boot
"""
from __future__ import annotations

import asyncio
import sys


def _print_banner() -> None:
    print("""
╔══════════════════════════════════════════════════════════════════╗
║         G.A.N.E — GLOBAL AUTONOMOUS NAVIGATION ENGINE            ║
║                      v2.0.0 — GANE                               ║
╚══════════════════════════════════════════════════════════════════╝
""")


async def _cmd_status() -> int:
    from brainiac.core import (
        NeuroCore, OrbitalNav, SonicMatrix, SatLink,
        NexusSync, TelemetryHub, CyberShield, CreativeEngine, OmniVision,
        Localization, MedicalProtocols,
    )
    _print_banner()
    print("▶ Verifying all 11 core modules...\n")

    modules = {
        "NEURO-CORE       ": NeuroCore(),
        "ORBITAL-NAV      ": OrbitalNav(),
        "SONIC-MATRIX     ": SonicMatrix(),
        "SATLINK          ": SatLink(),
        "NEXUS-SYNC       ": NexusSync(),
        "TELEMETRY-HUB    ": TelemetryHub(),
        "CYBER-SHIELD     ": CyberShield(),
        "CREATIVE-ENGINE  ": CreativeEngine(),
        "OMNI-VISION      ": OmniVision(),
        "LOCALIZATION     ": Localization(),
        "MEDICAL-PROTOCOLS": MedicalProtocols(),
    }

    print("┌───────────────────┬────────────┐")
    print("│ MODULE            │ STATUS     │")
    print("├───────────────────┼────────────┤")
    for name, mod in modules.items():
        diag = mod.diagnostics()
        status = diag.get("status", "ONLINE" if diag else "UNKNOWN")
        print(f"│ {name} │ {status:<10} │")
    print("└───────────────────┴────────────┘")
    print(f"\n✅ All {len(modules)} G.A.N.E systems verified.\n")
    return 0


async def _cmd_boot() -> int:
    from brainiac import Brainiac
    _print_banner()
    print("▶ Booting full G.A.N.E orchestrator …\n")
    bot = Brainiac()
    report = await bot.boot()
    print(f"  System state   : {report.system_state.value}")
    print(f"  Uptime         : {report.uptime_s}s")
    print(f"  Modules online : {len(report.modules)}")
    for name, status in report.modules.items():
        print(f"    - {name:20}: {status}")
    if report.alerts:
        print(f"  ⚠  Alerts     : {report.alerts}")
    await bot.shutdown()
    print("\n✅ Boot cycle complete.\n")
    return 0


def _cmd_serve() -> int:
    import uvicorn
    _print_banner()
    print("▶ Starting G.A.N.E API server on 0.0.0.0:8000…\n")
    uvicorn.run("brainiac.api.main:app", host="0.0.0.0", port=8000, reload=False)
    return 0


async def _cmd_nav_route(
    olat: float, olon: float, dlat: float, dlon: float,
    mode: str = "driving", lang: str = "en",
) -> int:
    from brainiac.core import OrbitalNav
    from brainiac.core.orbital_nav import Coordinate, TransportMode

    _print_banner()
    nav = OrbitalNav()
    origin = Coordinate(lat=olat, lon=olon)
    dest   = Coordinate(lat=dlat, lon=dlon)
    tmode  = TransportMode(mode)

    print(f"▶ Computing {mode.upper()} route …")
    route = await nav.route(origin, dest, mode=tmode)
    print(f"  ✓ Distance: {route.distance_km:.2f} km")
    print(f"  ✓ ETA:      {route.eta_minutes:.1f} min")
    print(f"  ✓ Mode:     {route.mode.value}")
    print(f"  ✓ Precision:{route.precision.value}")

    print(f"\n▶ Turn-by-turn ({lang}):")
    for i, step in enumerate(nav.build_turn_by_turn(route, lang=lang), 1):
        dist = (
            f"{step['distance_m']/1000:.1f} km"
            if step["distance_m"] >= 1000 else f"{int(step['distance_m'])} m"
        )
        print(f"  {i:2}. [{dist:>8}]  {step['instruction']}")
    return 0


async def _cmd_nav_position() -> int:
    from brainiac.core import OrbitalNav
    _print_banner()
    nav = OrbitalNav()
    print("▶ Acquiring position …")
    pos = await nav.get_position()
    sats = await nav.get_satellite_status()
    print(f"  ✓ Position: {pos}")
    print(f"  ✓ Accuracy: {pos.accuracy_m}m")
    print(f"  ✓ Satellites: {len(sats)} constellations")
    for s in sats:
        print(f"    - {s.system:8}  used={s.satellites_used:2}  HDOP={s.hdop}  fix={s.fix_type}")
    return 0


def _cmd_medical_triage(hr: int, rr: int, sbp: int, gcs: int) -> int:
    from brainiac.core import MedicalProtocols
    _print_banner()
    med = MedicalProtocols()
    print("▶ Running triage assessment …")
    result = med.triage(heart_rate=hr, respiratory_rate=rr, systolic_bp=sbp, gcs=gcs)
    print(f"  ✓ Category: {result.category.value.upper()}")
    print(f"  ✓ Score:    {result.score}")
    print(f"  ✓ Rationale: {result.rationale}")
    if result.recommended_protocol:
        print(f"  ✓ Recommended protocol: {result.recommended_protocol}")
    return 0


def _cmd_medical_dose(drug: str, weight_kg: float) -> int:
    from brainiac.core import MedicalProtocols
    _print_banner()
    med = MedicalProtocols()
    print(f"▶ Calculating {drug} dose for {weight_kg} kg …")
    result = med.calculate_dose(drug, weight_kg)
    if "error" in result:
        print(f"  ✗ {result['error']}")
        return 1
    print(f"  ✓ Drug:       {result['drug']}")
    print(f"  ✓ Dose:       {result['actual_dose_mg']} mg  (calculated: {result['calculated_mg']} mg)")
    print(f"  ✓ Route:      {result['route']}")
    print(f"  ✓ Frequency:  {result['frequency']}")
    print(f"  ✓ Reference:  {result['reference']}")
    print(f"  ⚠  {result['disclaimer']}")
    return 0


def _parse_coord_pair(s: str) -> tuple[float, float]:
    parts = s.split(",")
    if len(parts) != 2:
        raise ValueError(f"Invalid coordinate: {s!r} (expected 'lat,lon')")
    return float(parts[0]), float(parts[1])


def _print_help() -> None:
    _print_banner()
    print("Commands:")
    print("  status                                          — Show module status")
    print("  boot                                            — Boot full orchestrator")
    print("  serve                                           — Start FastAPI server")
    print("  nav route <olat,olon> <dlat,dlon> [mode] [lang] — Route with turn-by-turn")
    print("  nav position                                    — Current GPS position")
    print("  medical triage <HR> <RR> <SBP> <GCS>            — Vital-sign triage")
    print("  medical dose <drug> <weight_kg>                 — Weight-based dosing")


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help", "help"):
        _print_help()
        return 0

    cmd = args[0]
    if cmd == "status":
        return asyncio.run(_cmd_status())
    if cmd == "boot":
        return asyncio.run(_cmd_boot())
    if cmd == "serve":
        return _cmd_serve()
    if cmd == "nav":
        sub = args[1] if len(args) > 1 else ""
        if sub == "position":
            return asyncio.run(_cmd_nav_position())
        if sub == "route":
            try:
                olat, olon = _parse_coord_pair(args[2])
                dlat, dlon = _parse_coord_pair(args[3])
            except (IndexError, ValueError) as exc:
                print(f"Usage: nav route <olat,olon> <dlat,dlon> [mode] [lang]\n  {exc}")
                return 1
            mode = args[4] if len(args) > 4 else "driving"
            lang = args[5] if len(args) > 5 else "en"
            return asyncio.run(_cmd_nav_route(olat, olon, dlat, dlon, mode, lang))
        print(f"Unknown nav subcommand: {sub!r}")
        return 1
    if cmd == "medical":
        sub = args[1] if len(args) > 1 else ""
        if sub == "triage":
            try:
                return _cmd_medical_triage(
                    int(args[2]), int(args[3]), int(args[4]), int(args[5]),
                )
            except (IndexError, ValueError) as exc:
                print(f"Usage: medical triage <HR> <RR> <SBP> <GCS>\n  {exc}")
                return 1
        if sub == "dose":
            try:
                return _cmd_medical_dose(args[2], float(args[3]))
            except (IndexError, ValueError) as exc:
                print(f"Usage: medical dose <drug> <weight_kg>\n  {exc}")
                return 1
        print(f"Unknown medical subcommand: {sub!r}")
        return 1

    print(f"Unknown command: {cmd!r}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
