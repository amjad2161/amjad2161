# BRAINIAC / G.A.N.E v2.1.0 Architecture

## Core modules (12)
1. `NeuroCore`
2. `OrbitalNav`
3. `SatLink`
4. `SonicMatrix`
5. `NexusSync`
6. `TelemetryHub`
7. `CyberShield`
8. `CreativeEngine`
9. `OmniVision`
10. `INS`
11. `MedicalProtocols`
12. `Localization`

## Agent layer
- `AgentRouter` routes prompts by keyword priority.
- `AgentMemory` stores/evicts/searches facts deterministically.
- `AgentLoop` wraps Anthropic streaming/tool usage.
- `AgentManager` builds tool surfaces per domain.

## Orchestrator + resilience
- `brainiac.orchestrator.Brainiac` wires modules and exposes:
  - `fused_position`
  - `voice_guided_route`
  - `medical_evacuation_route`
  - `emergency`
  - `self_heal`
  - `graceful_shutdown`

## Public API re-export policy
- `brainiac/__init__.py` only re-exports stable public symbols.
- Internal helpers remain in module-local namespaces.
- New public symbols must be added to `__all__` and covered by import tests.
