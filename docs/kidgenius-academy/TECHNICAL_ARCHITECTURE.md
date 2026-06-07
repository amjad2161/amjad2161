# KidGenius Academy — Technical Architecture

## Internationalization (i18n)

The translation system is built from scratch using React Context in
`src/i18n/i18n.tsx`.

### Features

- **Automatic directionality:** Sets `dir="rtl"` for Arabic and Hebrew,
  `dir="ltr"` for English on the `<html>` element.
- **Document metadata:** Updates `lang` and `dir` attributes and page title on
  locale change.
- **Variable interpolation:** Replaces `{variable}` placeholders inside
  translated strings.
- **Fallback chain:** Missing keys in the active locale fall back to the
  English locale file to prevent blank UI.

### Locale Files

```
src/i18n/locales/
├── ar.json   (Arabic)
├── en.json   (English — fallback source)
└── he.json   (Hebrew)
```

---

## Registry-Driven Architecture

The entire project runs through centralized registries so hundreds of worlds
and games can be added without modifying core application code.

### Module Registry (`ModuleRegistry.ts`)

Defines each world's ID, translation keys, supported languages, age range, and
fallback strategy.

### Game Registry (`GameRegistry.ts`)

Links each 3D game to its learning objectives, progress schema, required audio
assets, and fallback mode.

### Asset Registry (`AssetRegistry.ts`)

Registers GLB/GLTF model paths and their operational states for the fallback
engine:

| Asset ID                        | Description                             |
| ------------------------------- | --------------------------------------- |
| `academy-plaza-environment`     | Main hub environment                    |
| `citrus-market-environment`     | Citrus Market world                     |
| `citrus-fruit-set`              | Orange, lemon, lime 3D models           |
| `owl-mascot-gltf`              | Cosmo the owl animated model            |
| `friendly-body-explorer-gltf`  | Interactive human body anatomy model    |

### Audio Registries

| Registry                | Content                                                        |
| ----------------------- | -------------------------------------------------------------- |
| `musicRegistry.ts`      | Background tracks per world (volume 0.16–0.20 to avoid overwhelm) |
| `sfxRegistry.ts`        | Instant sound effects (button clicks, picks, success/fail)     |
| `voiceoverRegistry.ts`  | Trilingual narrator clips for Cosmo and tutorial guidance       |

### Content Registry (`ContentRegistry.ts`)

Structured multilingual content nodes for scenes and dialogue.

---

## Audio System

### AudioManager (`AudioManager.ts`)

- Background music plays at low volume per world.
- When a narrator voice-over starts, music is ducked to `0.38` of its current
  volume.
- Music restores to full level when the clip finishes.

### Spatial Audio (`spatialAudio.ts`)

Web Audio API spatial positioning for 3D sound placement within the scene
(e.g. a fruit dropping on a table sounds positioned relative to the camera).

---

## Physics & Rendering

### PhysicsWorld (`PhysicsWorld.tsx`)

- Engine: **Rapier** (Rust-based, compiled to WASM)
- Interpolation: enabled for smooth sub-frame motion
- Gravity: `[0, -2.4, 0]` — gentler than Earth gravity for a playful feel
- Coins, fruits, and objects respond to real-time Rapier collisions

### CinematicEffects (`CinematicEffects.tsx`)

- **Bloom:** Soft glow on interactive elements
- **Depth of Field:** Cinematic focus during transitions
- Auto-disabled on screens below 720 px width to conserve battery

### WebGL Fallback (`KidGeniusCanvas.tsx`)

If the browser lacks WebGL support, the canvas is replaced by a full 2D HTML
interface (`WebGLFallback`) with an equivalent interactive diagnostic system.

---

## Progress & Persistence

### progressAdapter (`progressAdapter.ts`)

| State   | Behavior                                                           |
| ------- | ------------------------------------------------------------------ |
| Online  | Writes immediately to Supabase                                     |
| Offline | Queues events in `kidgenius.offlineProgressQueue` (localStorage)   |
| Reconnect | Silently flushes the offline queue (non-blocking to keep 60 fps) |

---

## Vehicles & Transition Mechanics

The project uses **magical/physical transport** rather than cars or fuel
vehicles:

| Transport                  | Description                                                      |
| -------------------------- | ---------------------------------------------------------------- |
| Floating Platforms         | Grassy rock islands carrying characters between academy gates    |
| Keyhole Portals            | Glowing keyhole-shaped 3D gates with dynamic light and gentle vertical motion |
| Pixel's Roller Wheels      | Magnetic wheels with orange rims for precise grid movement       |
| Cosmo's Flight Guide       | Follow-the-owl flying with motion blur for long-distance travel  |

---

## QA & Security

### Translation Key Sync (`kidgenius-qa.mjs`)

Compares translation keys across all three locale files. A missing key in any
language fails the build immediately to prevent blank or broken text in the UI.

### Hardcoded String Scanner

Scans `.tsx` files for raw text strings not wrapped in the `t()` translation
function.

### Secret Leak Prevention

Scans source for Supabase `service_role` keys, `sk_live` keys, or other
sensitive tokens. Any match blocks the build to protect child account data.

### WebGL Fallback Verification

Ensures `KidGeniusCanvas.tsx` contains the WebGL context check and the HTML
fallback component is loaded when WebGL is unavailable.

### Reduced Motion Support

Detects `prefers-reduced-motion` at the OS level and disables camera shake,
depth-of-field, and bloom effects — ensuring a safe experience for children
with epilepsy or motion sensitivity.

### Offline Queue Integrity

The offline progress queue is flushed non-blockingly so 3D rendering stays at
60 fps without frame drops during Supabase sync.
