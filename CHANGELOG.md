## [2.1.1] – Unreleased

- Fixed dependency resolution in `requirements.txt` by aligning `anthropic` with `langchain-anthropic`, removing `asyncio` (stdlib), and de-duplicating `httpx`.
- Hardened API request handling with a strict 10MB request-body cap validated from both `Content-Length` and actual read bytes.
- Added correlation IDs to API responses via `X-Request-Id` middleware header.
- Improved orbital navigation offline ETA fallbacks by covering all transport modes, including submarine and spacecraft.
- Exported a stable top-level `brainiac.__all__` surface for import-smoke validation.
