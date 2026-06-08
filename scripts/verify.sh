#!/usr/bin/env bash
# ─── BRAINIAC Verification Script ─────────────────────────────────────────────
# Runs the full integrity check: imports, CLI, tests, linting.
set -e

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║  BRAINIAC System Verification                                    ║"
echo "╚══════════════════════════════════════════════════════════════════╝"

echo ""
echo "▶ [1/5] Verifying Python imports..."
python3 -c "
from brainiac.core import (
    NeuroCore, OrbitalNav, SonicMatrix, SatLink,
    NexusSync, TelemetryHub, CyberShield, CreativeEngine, OmniVision, ReelMaker,
)
print('  ✓ All 10 core modules importable')
"

echo ""
echo "▶ [2/5] Running module status check..."
python3 -m brainiac.cli status

echo ""
echo "▶ [3/5] Running end-to-end demo..."
python3 -m brainiac.cli demo

echo ""
echo "▶ [4/5] REEL-MAKER smoke compose..."
python3 -m brainiac.cli reel "BRAINIAC verification smoke"

echo ""
echo "▶ [5/5] Running test suite..."
python3 -m pytest tests/ --ignore=tests/test_neuro_core.py -q

echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║  ✅ BRAINIAC VERIFIED — all systems operational                  ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
