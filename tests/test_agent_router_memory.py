from brainiac.agent.memory import AgentMemory
from brainiac.agent.router import AgentRouter


def test_router_medical_priority_over_telemetry():
    router = AgentRouter()
    assert router.route("medical reading for triage") == "medical"


def test_memory_tie_break_and_eviction_stable():
    mem = AgentMemory(capacity=2)
    mem.store_fact("alpha beta")
    mem.store_fact("alpha gamma")
    results = mem.search_facts("alpha", limit=2)
    assert len(results) == 2
    mem.store_fact("alpha delta")
    assert len(mem._facts) == 2
