# Weather Buddy — Activity Advisor Heuristics & Scoring Algorithms

The `activity_advisor` tool in Weather Buddy provides customized recommendations for outdoor pursuits based on meteorological sensor telemetry. This document details the mathematical models and scoring rules implemented by the tool.

---

## 1. Multi-Factor Meteorological Scoring Engine

The advisor evaluates four environmental dimensions:
1. **Thermal Comfort ($S_{\text{temp}}$):** Heat index and wind chill evaluation.
2. **Hydrological Risk ($S_{\text{precip}}$):** Probability of precipitation (PoP) and rainfall rate.
3. **Aerodynamic Resistance ($S_{\text{wind}}$):** Sustained wind velocity and gust thresholds.
4. **Radiative Exposure ($S_{\text{uv}}$):** Solar irradiance and ultraviolet danger index.

The composite suitability score ($S \in [0, 100]$) is computed as a weighted geometric mean:

$$S = 100 \times \left( \bar{S}_{\text{temp}}^{w_1} \times \bar{S}_{\text{precip}}^{w_2} \times \bar{S}_{\text{wind}}^{w_3} \times \bar{S}_{\text{uv}}^{w_4} \right)$$

---

## 2. Activity-Specific Threshold Profiles

Different outdoor sports have distinct vulnerability curves to weather elements:

| Activity | Ideal Temp Range | Wind Cutoff | Max Rain Tolerance | Primary Risk Factor |
|----------|:----------------:|:-----------:|:------------------:|:--------------------|
| **Running / Jogging** | 10°C - 18°C | 35 km/h | 1.0 mm/h | Heat stroke & dehydration |
| **Road Cycling** | 15°C - 24°C | 25 km/h | 0.2 mm/h | Slick tarmac & crosswinds |
| **Mountain Hiking** | 12°C - 22°C | 40 km/h | 2.5 mm/h | Hypothermia & lightning |
| **Golfing** | 18°C - 26°C | 30 km/h | 0.0 mm/h | Ball trajectory & standing water |
| **Beach / Swimming** | 24°C - 32°C | 20 km/h | 0.0 mm/h | Wave chop & UV sunburn |

---

## 3. Mathematical Comfort Formulations

### 3.1 Heat Index ($HI$) Formulation
For temperatures exceeding 27°C (80°F) and relative humidity ($RH \ge 40\%$), the Steadman Heat Index equation is evaluated:

$$HI = c_1 + c_2 T + c_3 RH + c_4 T \cdot RH + c_5 T^2 + c_6 RH^2 + c_7 T^2 RH + c_8 T \cdot RH^2 + c_9 T^2 RH^2$$

Where $c_1 \dots c_9$ are the Rothfusz regression coefficients.

### 3.2 Wind Chill Index ($WCI$)
For temperatures below 10°C (50°F) and wind velocities ($V > 4.8\text{ km/h}$):

$$WCI = 13.12 + 0.6215 T - 11.37 V^{0.16} + 0.3965 T \cdot V^{0.16}$$

---

## 4. Scoring Verdict Thresholds

| Score Range | Verdict | Advisory Status |
|:-----------:|:-------:|:----------------|
| **85 – 100** | **Ideal** | Optimal weather conditions; high participant comfort. |
| **65 – 84** | **Acceptable** | Minor adjustments recommended (e.g. windbreaker, hydration). |
| **40 – 64** | **Caution** | Significant weather interference; exercise vigilance. |
| **0 – 39** | **Not Recommended** | Potentially hazardous conditions (thunderstorms, gale winds, heat warning). |
