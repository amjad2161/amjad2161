# KidGenius Academy — Cognitive Diagnostics & Game Registry

## Diagnostic Engine

The progress adapter (`progressAdapter.ts`) contains an integrated diagnostic
engine that measures child performance and generates reports based on six
metrics.

### The 6 Diagnostic Metrics

| # | Metric              | Description                                                                                                  |
| - | ------------------- | ------------------------------------------------------------------------------------------------------------ |
| 1 | **Accuracy**        | Ratio of correct answers to attempts. Ranges from `1.0` (instant correct) to `0.4` or lower on repeated errors |
| 2 | **Score**           | Cumulative points awarded (e.g. 100 for correct sort, 35 for partial)                                       |
| 3 | **Time Spent**      | Response latency measured via `performance.now()` in seconds from puzzle open to solve                       |
| 4 | **Progress**        | Percentage representing skill advancement (+0.2 on success, +0.06 on retry)                                 |
| 5 | **Difficulty Level** | Dynamically adjusted across three tiers: `intro` → `growing` → `mastery`                                   |
| 6 | **Metadata**        | Per-interaction fields: `itemId`, `quality`, targeted cognitive skill                                        |

---

## 15 Targeted Cognitive Skills

Every child interaction is classified against this skill taxonomy:

| Skill                      | Application in Games                                                          |
| -------------------------- | ----------------------------------------------------------------------------- |
| **Classification**         | Sorting shapes, colors, and attributes (e.g. ripe fruit sorting)              |
| **Pattern Recognition**    | Identifying geometric or mathematical sequences                               |
| **Sequencing**             | Understanding temporal/spatial order of events                                 |
| **Cause and Effect**       | Understanding action outcomes (e.g. heartbeat acceleration)                   |
| **Spatial Reasoning**      | 3D orientation, depth perception inside WebGL                                 |
| **Working Memory**         | Retaining and recalling temporary information (e.g. rhythm repetition)        |
| **Attention**              | Filtering distractors, focusing on glowing/required elements                  |
| **Problem Solving**        | Sequential steps to reach a closed goal                                       |
| **Strategy**               | Proactive planning (e.g. arrow movements to guide Pixel)                     |
| **Pre-Coding**             | Building step-by-step directional algorithms                                  |
| **Decision Making**        | Choosing the best option among alternatives                                   |
| **Creativity**             | Free-form coloring, building, and structural creation                         |
| **Emotional Reasoning**    | Recognizing facial expressions and providing appropriate support              |
| **Safety Awareness**       | Distinguishing safe from dangerous environments (kitchen, street)             |
| **Daily Independence**     | Simulating room cleanup and daily routines for self-reliance                  |

---

## Registered Games

### 1. Academy Plaza (`academy-plaza`)

| Property           | Value                                              |
| ------------------ | -------------------------------------------------- |
| Age range          | 6–12                                               |
| Learning goals     | `spatial_navigation`, `choice_agency`              |
| Progress metric    | `classification_accuracy` (gate/zone visits)       |
| Audio assets       | Academy music, flying camera SFX                   |
| Fallback mode      | `responsive-html`                                  |

### 2. Citrus Quality Sort (`citrus-quality-sort`)

| Property           | Value                                              |
| ------------------ | -------------------------------------------------- |
| Age range          | 6–12                                               |
| Learning goals     | `classification`, `observation`, `scientific_reasoning` |
| Progress metric    | Sort accuracy by item ID, quality grade, score     |
| Audio assets       | Fruit pick-up SFX, success/fail chimes, Cosmo VO  |
| Fallback mode      | `webgl-scene`                                      |

### 3. English Phonics Garden (`english-phonics-garden`)

| Property           | Value                                              |
| ------------------ | -------------------------------------------------- |
| Age range          | 6–12                                               |
| Learning goals     | `phonics`, `listening`, `vocabulary`               |
| Progress metric    | Phonics match by letter ID, sound key, accuracy %  |
| Audio assets       | Letter sounds, match chimes                        |
| Fallback mode      | `asset-slot`                                       |

### 4. Anatomy Friendly Explorer (`anatomy-friendly-explorer`)

| Property           | Value                                              |
| ------------------ | -------------------------------------------------- |
| Age range          | 6–12                                               |
| Learning goals     | `body_awareness`, `spatial_recognition`            |
| Progress metric    | Target organ focus, body system identification     |
| Audio assets       | Heartbeat SFX, organ highlight chimes              |
| Fallback mode      | `asset-slot`                                       |

---

## Module Registry

Each world is registered in `ModuleRegistry.ts` with language support,
age gating, and a fallback strategy:

```typescript
{
  id: "citrus",
  titleKey: "citrus.title",
  promptKey: "citrus.prompt",
  sceneId: "citrus",
  languages: ["en", "he", "ar"],
  ageRange: [6, 12],
  fallbackMode: "webgl-scene",
}
```

Supported fallback modes:

| Mode              | Behavior                                      |
| ----------------- | --------------------------------------------- |
| `responsive-html` | Full 2D HTML interface                        |
| `webgl-scene`     | Simplified WebGL with reduced effects         |
| `asset-slot`      | Dynamic 2D interactive asset slot             |
