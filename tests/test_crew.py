"""The multi-agent CREW: a team of specialists tackles a goal in parallel."""
from __future__ import annotations

import asyncio

from singularity.organs.agents import AgentsOrgan


def test_crew_assigns_a_team_in_mock_mode() -> None:
    """With no real backend the crew degrades deterministically: it still names a
    lead and a team, so the delegation shape is always observable."""
    organ = AgentsOrgan()  # not attached -> builtin/mock path
    result = asyncio.run(organ._invoke("agents.crew", {"goal": "build a trading bot", "size": 3}))

    assert result["_backend"] == "builtin"
    assert result["lead"]                      # a lead was chosen
    assert result["crew_size"] >= 2            # a team, not a solo
    assert len(result["crew"]) == result["crew_size"]
    for member in result["crew"]:
        assert member["persona"]
        assert member["deliverable"]


def test_crew_size_is_bounded() -> None:
    organ = AgentsOrgan()
    big = asyncio.run(organ._invoke("agents.crew", {"goal": "x", "size": 99}))
    assert big["crew_size"] <= 4               # capped so it never runs away
    small = asyncio.run(organ._invoke("agents.crew", {"goal": "x", "size": 1}))
    assert small["crew_size"] >= 2             # always at least a pair
