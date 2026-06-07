# KidGenius Academy Documentation

Comprehensive design and technical documentation for the **KidGenius Academy**
(MEDSIM ACADEMY) interactive 3D educational platform for children aged 4–10.

## Documents

| Document                                                  | Contents                                                  |
| --------------------------------------------------------- | --------------------------------------------------------- |
| [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md)                | Concept, philosophy, high-level architecture              |
| [ENVIRONMENTS.md](ENVIRONMENTS.md)                        | 10 3D worlds with visual and lighting specifications      |
| [CHARACTERS.md](CHARACTERS.md)                            | Full character cast with Pixar-quality design specs       |
| [SCENARIO_SCRIPT.md](SCENARIO_SCRIPT.md)                  | 60-minute script — 5 acts, 90 scenes, 12 interaction triggers |
| [COGNITIVE_DIAGNOSTICS.md](COGNITIVE_DIAGNOSTICS.md)      | 6 metrics, 15 cognitive skills, game registry             |
| [TECHNICAL_ARCHITECTURE.md](TECHNICAL_ARCHITECTURE.md)    | Code structure, registries, i18n, audio, physics, QA      |
| [VEHICLES_AND_TRANSITIONS.md](VEHICLES_AND_TRANSITIONS.md)| Transport mechanics and world transition design           |

## Quick Facts

| Property         | Value                                          |
| ---------------- | ---------------------------------------------- |
| Target age       | 4–10 years                                     |
| Languages        | Arabic (RTL) · Hebrew (RTL) · English (LTR)   |
| Runtime          | WebGL with full HTML fallback                  |
| Framework        | React 19 + TypeScript + Vite                   |
| 3D engine        | React Three Fiber + Rapier physics             |
| Session length   | 60 minutes (90 scenes, 12 interactive triggers)|
| Persistence      | Supabase (online) / localStorage (offline)     |
| Accessibility    | `prefers-reduced-motion` support throughout    |

## Related Repositories

- [`citrus-inspectors-academy`](https://github.com/amjad2161/citrus-inspectors-academy) — Citrus-themed 3D educational game
- [`english-explorer-kids`](https://github.com/amjad2161/english-explorer-kids) — English learning platform for kids
