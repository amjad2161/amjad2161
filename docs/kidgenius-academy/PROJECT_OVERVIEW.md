# KidGenius Academy — Project Overview

## Concept & Educational Philosophy

**KidGenius Academy** is a 3D interactive educational platform designed for
children aged 4–10. The core philosophy rejects traditional worksheet and linear
video approaches in favor of a **Single Canvas Cinematic Experience** — a
continuous, breathing 3D world that feels like a Pixar animated film.

### Three Interactive Languages

The system supports Arabic (RTL), Hebrew (RTL), and English (LTR) dynamically
through a unified translation provider backed by locale JSON files under
`src/i18n/locales/`.

### Stealth Learning

The cinematic scenario pauses automatically at predetermined trigger points.
The environment transforms into a live interactive world powered by a physics
engine and simulations. Children solve puzzles as a natural part of the story
without feeling tested.

---

## Platform Identity

| Property         | Value                                                |
| ---------------- | ---------------------------------------------------- |
| Project codename | MEDSIM ACADEMY / KidGenius Academy                   |
| Target age       | 4–10 years                                           |
| Languages        | Arabic · Hebrew · English                            |
| Runtime          | Browser (WebGL with HTML fallback)                   |
| Duration         | 60-minute cinematic session (90 scenes, 12 triggers) |
| Framework        | React 19 / TypeScript / Vite                         |
| 3D engine        | React Three Fiber (R3F) + Rapier physics             |
| Backend sync     | Supabase (online) / localStorage (offline)           |

---

## High-Level Architecture

```
App.tsx
├── KidGeniusCanvas.tsx          (single persistent WebGL canvas)
│   ├── CameraDirector.tsx       (smooth 3D path-based camera transitions)
│   ├── PhysicsWorld.tsx         (Rapier physics with child-friendly gravity)
│   ├── CinematicEffects.tsx     (bloom, depth of field — disabled on low-end)
│   └── Active 3D Scene          (CitrusWorld / AnatomyWorld / …)
├── WorldHud.tsx / SceneDock.tsx (2D HUD overlay)
└── AudioManager.ts              (music ducking at 0.38 during voice-overs)
```

### Core Controllers

| Component              | Responsibility                                                                                          |
| ---------------------- | ------------------------------------------------------------------------------------------------------- |
| `App.tsx`              | Lazy-loads the canvas, initializes the i18n provider, unlocks audio on first interaction                 |
| `KidGeniusCanvas.tsx`  | Checks WebGL support, sets up lighting/fog/shadows, enables reduced-motion for epilepsy/motion-sensitive |
| `CameraDirector.tsx`   | Drives the camera along smooth 3D spline paths for seamless world transitions without loading screens    |
| `PhysicsWorld.tsx`     | Wraps Rapier with interpolation enabled and reduced gravity `[0, -2.4, 0]`                              |
| `CinematicEffects.tsx` | Post-processing (bloom + DoF) auto-disabled below 720 px to save battery on mobile                      |
| `AudioManager.ts`      | Ducks background music to 0.38 during narrator clips, restores on completion                            |
| `progressAdapter.ts`   | Writes to Supabase when online; queues in `localStorage` when offline                                   |

---

## Related Repositories

| Repository                 | Role                                           |
| -------------------------- | ---------------------------------------------- |
| `amjad2161`                | Profile repo — documentation hub               |
| `citrus-inspectors-academy`| Citrus-themed 3D educational game (React/Vite) |
| `english-explorer-kids`    | English learning platform for kids (React/Vite) |
