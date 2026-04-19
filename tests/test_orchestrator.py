import pytest

from brainiac.core.ins import IMUReading
from brainiac.core.orbital_nav import Coordinate
from brainiac.orchestrator import Brainiac


@pytest.mark.asyncio
async def test_orchestrator_core_flows():
    bot = Brainiac()
    fused = bot.fused_position(Coordinate(32.0, 34.0), IMUReading(0.1, 0.1))
    assert fused is not None

    route = await bot.voice_guided_route(Coordinate(32.0, 34.0), Coordinate(32.01, 34.01), lang="he")
    assert route["rtl"] is True
    assert route["instructions"]

    med = await bot.medical_evacuation_route(
        Coordinate(32.0, 34.0),
        Coordinate(32.1, 34.1),
        vitals={"heart_rate": 190, "systolic_bp": 80, "spo2": 85},
    )
    assert med["triage"] in {"RED", "YELLOW", "GREEN", "BLACK"}

    emergency = await bot.emergency(32.0, 34.0, "test")
    assert emergency["incident_id"]
