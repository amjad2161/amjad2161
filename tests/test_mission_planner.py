import pytest

from brainiac.core import CyberShield, MedicalProtocols, MissionPlanner, OrbitalNav
from brainiac.core.mission_planner import MissionStore
from brainiac.core.orbital_nav import Coordinate


class _StubNeuro:
    async def think(self, prompt: str):
        return prompt


@pytest.mark.asyncio
async def test_mission_planner_plan_and_resume():
    store = MissionStore()
    planner = MissionPlanner(_StubNeuro(), OrbitalNav(), MedicalProtocols(), CyberShield(), store=store)
    plan = await planner.create_plan(origin=Coordinate(32, 34), destination=Coordinate(32.1, 34.1))
    assert plan.mission_id
    resumed = planner.resume(plan.mission_id)
    assert resumed is not None


def test_multi_vehicle_allocation():
    planner = MissionPlanner(_StubNeuro(), OrbitalNav(), MedicalProtocols(), CyberShield())
    alloc = planner.allocate_tasks(["d1", "d2"], ["a", "b", "c"])
    assert set(alloc) == {"d1", "d2"}
