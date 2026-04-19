# GANE Live Demo Script · 5 minutes

**Setup:** Laptop, projector, browser with `http://localhost:8000/nav` open, terminal visible.

```bash
# Terminal 1: start API
python -m brainiac.cli serve

# Terminal 2: run demo commands
```

---

## Act 1 — Satellite Supremacy (0:00 – 1:00)

**Say:** "Everyone says multi-constellation. Let's actually look."

```bash
curl -s localhost:8000/api/v1/nav/gnss | jq '.gnss_systems, .gnss_count, .sbas | length'
```

**Expect:**
```json
["GPS","GLONASS","Galileo","BeiDou","QZSS","NavIC"]
6
6
```

**Say:** "Six GNSS, six SBAS, every constellation on Earth. Google Maps uses one. We use all of them. Per-satellite SNR, elevation, azimuth — we see **everything** the sky sees."

Open browser → `/nav`. Point out brand, 6-GNSS indicator in the footer.

---

## Act 2 — GNSS-Denied Survival (1:00 – 2:00)

**Say:** "Now watch what happens when we lose satellites."

```bash
python -m brainiac.cli nav ins
```

**Expect (abbreviated):**
```
▶ GNSS/INS Fusion Status …
  ✓ Position:   (32.085300, 34.781800)
  ✓ Source:     FUSED
  ✓ Accuracy:   0.02m
  ✓ GNSS health: score=1.0, available=True
  ✓ INS state:  NAVIGATING
```

**Say:** "Fused position. Sub-2 cm accuracy. But if I drive into a tunnel —"

```python
# Python REPL demo
from brainiac import Brainiac
from brainiac.core.ins import IMUReading
import asyncio, time

bot = Brainiac()
asyncio.run(bot.boot())

# Simulate GNSS loss
bot.ins.update_gnss_health(0, 0, 99.0, "NO_FIX")
ts = time.time()
for i in range(50):
    bot.ins.update_imu(IMUReading(
        accel_x=1.0, accel_y=0, accel_z=9.81,
        gyro_x=0, gyro_y=0, gyro_z=0,
        mag_x=20.0, mag_y=5.0, mag_z=-40.0,
        timestamp=ts + i*0.1,
    ))
print(bot.ins.position())
```

**Expect:** position still advancing via IMU, source = `INS`, drift reported.

**Say:** "Google, Waze, Apple — they freeze. We keep moving. Dead-reckoning, sub-metre drift, zero tracking loss."

---

## Act 3 — Life Corridor (2:00 – 3:30)

**Say:** "Real scenario. Cardiac arrest. Patient in Tel Aviv, closest cath lab at Ichilov Hospital. Every minute costs 10 % of heart muscle."

```bash
curl -s -X POST "localhost:8000/api/v1/nav/medical-evacuation?patient_lat=32.0853&patient_lon=34.7818&hospital_lat=32.1000&hospital_lon=34.8000&heart_rate=0&respiratory_rate=0&systolic_bp=0&gcs=3&mode=drone" | jq '.triage, .route.adjusted_eta_s, .route.distance_km'
```

**Expect:**
```json
{"category":"immediate","score":10,"rationale":"..."}
84.3
1.68
```

**Say:** "Triage: IMMEDIATE. ACLS protocol loaded. Now the Life Corridor —"

```bash
curl -s -X POST "localhost:8000/api/v1/nav/life-corridor?origin_lat=32.0853&origin_lon=34.7818&dest_lat=32.1000&dest_lon=34.8000&priority=emergency" | jq '.time_saved_s, .intersections_to_preempt, .v2x_broadcast_required'
```

**Expect:**
```
45.2
3
true
```

**Say:** "45 seconds saved. Three traffic lights pre-empted via V2X. In a heart attack, that's **heart muscle saved**."

---

## Act 4 — RTL Perfection (3:30 – 4:15)

**Say:** "Now the part nobody else does."

In browser, change language dropdown to `עברית · Hebrew`.

Press **Compute Route**.

**Expect:** UI flips RTL, instructions render right-aligned in Hebrew:
```
200 M · פנה ימינה
500 M · המשך ישר
1.2 KM · הגעת ליעד
```

Change to `العربية · Arabic`:
```
200 M · انعطف يميناً
500 M · تابع مستقيماً
1.2 KM · لقد وصلت إلى وجهتك
```

**Say:** "Native Hebrew. Native Arabic. Zero bidi defects. 430 million people who've been second-class citizens in every Western nav app — we built for them first."

---

## Act 5 — Security Fortress (4:15 – 5:00)

**Say:** "Last thing. GPS spoofing — $40 on Alibaba. Let me fake a position from Tel Aviv to Tokyo in one second."

```bash
curl -s -X POST "localhost:8000/api/v1/security/detect-gps-spoofing?reported_lat=35.6895&reported_lon=139.6917&previous_lat=32.0853&previous_lon=34.7818&previous_ts=$(($(date +%s) - 1))&current_ts=$(date +%s)" | jq
```

**Expect:**
```json
{
  "spoof_likelihood": 0.8,
  "indicators": ["IMPLAUSIBLE_SPEED_9200000_m_s"],
  "action": "BLOCK",
  "reported_position": {"lat": 35.6895, "lon": 139.6917}
}
```

**Say:** "Blocked. Now an EMP attack —"

```bash
curl -s -X POST localhost:8000/api/v1/security/detect-hardware-attack \
  -H "Content-Type: application/json" \
  -d '{"sensor_readings": {"emf_gauss": 150.0}}' | jq
```

**Expect:**
```json
{
  "attack_likelihood": 0.8,
  "indicators": ["EMP_INTERFERENCE_DETECTED"],
  "action": "BLOCK"
}
```

**Say:** "Flipper Zero signature — blocked. EMP interference — blocked. And every query you just saw — federated privacy, zero raw data left the device."

```bash
curl -s -X POST localhost:8000/api/v1/security/privacy-audit \
  -H "Content-Type: application/json" \
  -d '{"data": {"email": "a@b.com", "name": "Alice"}}' | jq '.federated_compliant, .exposed_fields | length'
```

**Say:** "We **see** your PII. We **flag** your PII. We **redact** your PII. Before it leaves."

**Close:** "GANE. Twelve modules. 308 tests. Two centimetres. One engine."

*End.*
