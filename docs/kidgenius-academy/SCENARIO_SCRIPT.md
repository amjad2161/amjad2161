# KidGenius Academy — 60-Minute Master Script

The cinematic scenario runs at 60 fps and spans **5 acts**, **90 scenes**, and
**12 interactive trigger points** across a continuous 60-minute session.

---

## Act I — Morning Routine (00:00 – 12:00)

**Scenes 1–10**

The camera descends with a gentle crane shot into the Academy Hub. Cosmo the
owl delivers a trilingual morning greeting. A match-cut through a stone window
transitions to Adam's messy bedroom.

### Trigger #1 — Room Cleanup (02:10)

Three colored bins appear in 3D. The child drags 5 scattered toys into the
correct bin by color. Successful drops produce golden particle bursts.

- **Cognitive skills:** Classification, Daily Independence
- **Metric:** `classification_accuracy`

### Trigger #2 — Kitchen Safety Hero (05:00)

Adam moves to the kitchen. A blue fridge (safe) and a red-hot stove (danger)
are visible. The child drags fresh apples into the fridge while avoiding the
stove, which pulses red on contact — teaching temperature awareness and home
safety.

- **Cognitive skills:** Safety Awareness, Cause and Effect
- **Lighting:** Fridge at 8000 K (cool blue), stove at 2000 K (pulsing red)

### Trigger #3 — Safe Street Crossing (09:12)

A red car stops before the crosswalk. The child presses the correct pedestrian
signal icons to activate the green walk light, allowing Adam and Sara to cross
using IK foot-placement animations.

- **Cognitive skills:** Safety Awareness, Sequencing, Decision Making

---

## Act II — Citrus Puzzles & Coding (12:00 – 26:00)

**Scenes 11–30**

The children pass through a green-leaf tunnel into the cheerful Citrus Market.

### Trigger #4 — Orange Fractions (14:10)

The vendor asks for 2 whole oranges. The child assembles halves and quarters to
form complete fruits (fraction lesson), then pays 3 gold coins that drop and
roll on the table using Rapier real-time physics.

- **Cognitive skills:** Pattern Recognition, Problem Solving
- **Metric:** `classification_accuracy` (item ID + quality + score)

### Trigger #5 — Pixel's Coding Path (20:20)

The walkway transforms into a programming grid. The child drags directional
command blocks (forward, turn right, forward) to guide the Pixel robot to its
charging station while avoiding magnetic obstacles.

- **Cognitive skills:** Pre-Coding, Strategy, Sequencing
- **Metric:** Steps used, path efficiency

---

## Act III — Body & Nature Secrets (26:00 – 42:00)

**Scenes 31–60**

Pixel's screen flashes, transporting everyone into a 3D holographic human body.

### Trigger #6 — Heartbeat Simulator (28:10)

The child sees a heart beating at 80 bpm. Pressing the "run" button increases
the rate to 120 bpm, and red blood-cell particles accelerate through the
arteries — an interactive explanation of physical exertion.

- **Cognitive skills:** Cause and Effect, Body Awareness
- **Asset:** `friendly-body-explorer-gltf`

### Trigger #7 — Science Garden Growth (33:15)

Inside the glass greenhouse, the child drags clouds to release rain and pulls
the sun to send light rays toward seeds. Glowing flowers grow with a smooth
scale animation.

- **Cognitive skills:** Cause and Effect, Creativity
- **Mechanic:** Drag-to-grow with progressive scale tween

### Trigger #8 — Animal Habitat Classification (38:45)

The children meet Leo the lion cub. The child sorts 4 animals (panda, penguin,
camel, dolphin) into their correct biomes (forest, polar ice, ocean).

- **Cognitive skills:** Classification, Spatial Reasoning
- **Metric:** Correct placements / total attempts

---

## Act IV — Rhythm & Languages (42:00 – 53:00)

**Scenes 61–80**

Leo's educational roar transforms into a welcoming musical note on the Music
Stage.

### Trigger #9 — Rhythm Repetition (43:20)

Cosmo taps a rhythm on fruit instruments (lemon piano, watermelon drums). The
child repeats the sequence by tapping the same instruments in order. Audio
latency target: ≤ 5 ms.

- **Cognitive skills:** Working Memory, Attention, Pattern Recognition
- **Metric:** Sequence accuracy, timing precision

### Trigger #10 — Empathy Wheel (47:15)

Sara is sad after losing her sketchbook. The child chooses the empathy option
("help her search"). The scene transitions from cold grey to warm golden
lighting over 1.2 seconds using blendshape facial animations on Sara's face.

- **Cognitive skills:** Emotional Reasoning, Decision Making
- **Lighting:** Grey → warm gold in 1.2 s

### Trigger #11 — Constellation Words (50:15)

Stars in the cosmic sky transform into trilingual letters. The child draws a
glowing line connecting letter-asteroids in the correct order to spell a target
word in all three languages (تفاحة / APPLE / תפוח).

- **Cognitive skills:** Attention, Sequencing, Working Memory

---

## Act V — The Academy Key & Graduation (53:00 – 60:00)

**Scenes 81–90**

The letters and stars converge in a luminous halo, revealing the Academy's
sealed gates locked by 3 massive golden padlocks.

### Trigger #12 — The Three Locks (53:40)

To open the locks, the child solves 3 combined puzzles drawn from earlier
lessons:

1. **Lock 1 — Coding path** for Pixel (from Trigger #5)
2. **Lock 2 — Fruit fractions** (from Trigger #4)
3. **Lock 3 — Word spelling** (from Trigger #11)

Each solved lock triggers a screen shake, a heavy metallic unlock SFX, and the
padlock falling away.

- **Cognitive skills:** Problem Solving, Working Memory, Strategy

### Finale — Graduation Ceremony (57:00 – 60:00)

The third lock opens. The gates swing inward. The children enter the grand
Academy hall to cheering characters and falling confetti. A golden medal floats
to the center of the screen. The camera rises toward the sky, closing a golden
book into a full black frame — ready for the next lesson.

---

## Timing Summary

| Act | Time Range    | Scenes  | Triggers     |
| --- | ------------- | ------- | ------------ |
| I   | 00:00 – 12:00 | 1 – 10  | #1, #2, #3   |
| II  | 12:00 – 26:00 | 11 – 30 | #4, #5       |
| III | 26:00 – 42:00 | 31 – 60 | #6, #7, #8   |
| IV  | 42:00 – 53:00 | 61 – 80 | #9, #10, #11 |
| V   | 53:00 – 60:00 | 81 – 90 | #12          |
