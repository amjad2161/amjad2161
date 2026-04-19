# Changelog

## v2.1.0
- Removed `asyncio` third-party dependency from `requirements.txt`.
- Updated Anthropic dependency floor to `>=0.26.0`; kept `httpx` runtime dependency.
- Added 12-module health/diagnostics surface (`INS`, `MedicalProtocols`, `Localization` added).
- Added mission planning/orchestrator scaffolding and agent layer modules.
- Hardened API request validation with dedicated Pydantic request models for nav/medical/security additions.
- Added `.env.example` and required `GF_SECURITY_ADMIN_PASSWORD` compose env.
- Added new tests for routing helpers, geofencing, INS fusion/corridor checks, localization, orchestrator flows, and SDK smoke usage.
