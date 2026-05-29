# Link analysis — curated frontier sources → SINGULARITY

An honest record of the links provided, what was genuinely accessible, the idea
behind each, and exactly how it was integrated into the federation. **No source
was faked**; where a link could not be read, it says so.

## Accessibility summary

| Source type | Accessible? | How integrated |
|-------------|-------------|----------------|
| GitHub repos / public tools | ✅ fetched & read | Federated as ecosystem entries + concrete organ capabilities |
| Instagram posts/reels | ⚠️ login-walled | Only public captions/comments readable; used for theme confirmation, not faked |

The Instagram corpus (accounts like `lukebuildsai`, `aiupdatelab`, `placement.guide`,
`tys.ais`) is overwhelmingly **"build your own Jarvis"** content and free-AI-repo
lists. One caption captured a genuinely useful architectural insight:

> "PAI's evolving loop is the smart bet — the architecture stays portable even
> when the underlying model swaps every six months. The repo + identity layer is
> what'll still be load-bearing in two years."

That is precisely SINGULARITY's thesis: a portable kernel + identity/memory layer
that outlives any single model. Most reels were waitlist/teaser posts whose video
content is not machine-readable without login — so they informed direction, not code.

## GitHub / tool sources and their integration

| Source | Idea | Integrated as |
|--------|------|---------------|
| **bytedance/UI-TARS-desktop** (35.6k★) | Multimodal computer-use GUI agent stack | `control` organ — `control.plan_actions` (UI-TARS-style action space: navigate/click/type/scroll/extract/verify) |
| **LycidPsyche/auto-browser** | Goal-driven browser automation | `control.browse` — a **real** stdlib HTTP GET (verified live: 200 + page title) |
| **browserbase / autobrowse** (skills.sh) | Hosted browser automation skill | `control` organ design + MCP-mountable as an external tool server |
| **HQarroum/docker-android** (5.7k★) | Android emulator as a service | `control` organ federation target (device the organ can drive) |
| **localsend/localsend** (82k★) | Cross-platform AirDrop alternative (P2P) | `control.transfer` — localsend-v2 session/pin/chunk spec |
| **PurpleAILAB/Decepticon** (4.1k★) | Autonomous red-team hacking agent | Folded into `nexus` (CyberShield) threat modelling |
| **PrathamLearnsToCode/paper2code** (1.4k★) | arXiv paper → working implementation | `neuro` federation (reasoning core target) |
| **blader/humanizer** (21.5k★) | Remove AI-writing tells (Claude Code skill) | `neuro.humanize` — a **real** deterministic transform (delve/leverage/plethora/em-dash…) |
| **braedonsaunders/codeflow** (3.2k★) | GitHub URL → interactive architecture map | `knowledge` federation (codebase onboarding) |
| **fspecii/ace-step-ui** (4k★) | Open-source Suno alternative (music gen) | `vision.audio` — emits a **real, playable WAV** (16-bit PCM) |
| **playcanvas/supersplat** (8.8k★) | 3D Gaussian Splat editor | `vision.splat` — emits a 3D gaussian-splat scene spec |
| **cobalt.tools** | Media downloader | `vision` federation (media ingestion) |
| **thedotmack/claude**, **1jehuang/jcode** | Claude-Code variants / coding agents | Conceptually align with `agents` + `neuro`; noted for parity |

## Common denominator

These sources define the **2026 agentic frontier**: agents that *act* in the
digital world (browser/GUI/device), *create* media (audio/3D/image), *defend*
(red-team), and *understand code* (paper→code, architecture maps) — all wrapped
around a portable, model-agnostic loop with an identity/memory layer. SINGULARITY
already embodied that loop; this round adds the **CONTROL** lobe (digital
embodiment) and real media/text generation, and records every source in the
federation manifest so the mapping is auditable, not decorative.
