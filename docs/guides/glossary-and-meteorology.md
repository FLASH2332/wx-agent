# Weather Buddy — Meteorological Glossary, Science Handbook & Formulas

This handbook provides an authoritative glossary of meteorological terms, physical formulas, atmospheric science concepts, and unit conversion standards implemented within Weather Buddy.

---

## 1. Thermodynamic & Moisture Metrics

### 1.1 Relative Humidity ($RH$) & Vapor Pressure
Relative humidity expresses the ratio of actual vapor pressure ($e$) to saturation vapor pressure ($e_s(T)$) at a given dry-bulb temperature:

$$RH = 100 \times \frac{e}{e_s(T)}$$

Where saturation vapor pressure is calculated via the **Tetens equation**:

$$e_s(T) = 0.61078 \exp\left( \frac{17.27 \cdot T}{T + 237.3} \right) \quad [\text{kPa}]$$

### 1.2 Dew Point Temperature ($T_d$)
The temperature to which ambient air must be cooled at constant barometric pressure for water vapor to condense into liquid dew:

$$T_d = \frac{237.3 \cdot \gamma(T, RH)}{17.27 - \gamma(T, RH)}$$

Where:
$$\gamma(T, RH) = \frac{17.27 \cdot T}{237.3 + T} + \ln\left(\frac{RH}{100}\right)$$

*Human Comfort Interpretation:*
- $T_d < 10^\circ\text{C}$: Dry, crisp, comfortable air.
- $13^\circ\text{C} \le T_d \le 18^\circ\text{C}$: Comfortable to slightly humid.
- $19^\circ\text{C} \le T_d \le 23^\circ\text{C}$: Oppressive, sticky humidity.
- $T_d > 24^\circ\text{C}$: Dangerous tropical mugginess.

---

## 2. Dynamic Wind & Barometric Pressure

### 2.1 Beaufort Wind Scale Reference

Weather Buddy maps wind velocities to the international Beaufort Scale:

| Beaufort Force | Velocity Range (km/h) | Wind Description | Physical Sea & Land Observations |
|:--------------:|:---------------------:|:-----------------|:---------------------------------|
| **0** | $< 1$ | Calm | Smoke rises vertically; sea surface mirror-like. |
| **1** | $1 - 5$ | Light Air | Smoke drift indicates wind direction; wind vanes unmoved. |
| **2** | $6 - 11$ | Light Breeze | Wind felt on face; leaves rustle; ordinary vanes moved. |
| **3** | $12 - 19$ | Gentle Breeze | Leaves and small twigs in constant motion; light flags extended. |
| **4** | $20 - 28$ | Moderate Breeze | Dust and loose paper raised; small branches move. |
| **5** | $29 - 38$ | Fresh Breeze | Small trees in leaf begin to sway; crested wavelets on lakes. |
| **6** | $39 - 49$ | Strong Breeze | Large branches in motion; umbrellas used with difficulty. |
| **7** | $50 - 61$ | Near Gale | Whole trees in motion; resistance felt walking against wind. |
| **8** | $62 - 74$ | Gale | Twigs break off trees; progress generally impeded. |
| **9** | $75 - 88$ | Strong Gale | Slight structural damage occurs; chimney pots removed. |
| **10** | $89 - 102$ | Storm | Trees uprooted; considerable structural damage. |
| **11** | $103 - 117$ | Violent Storm | Widespread damage; very rarely experienced inland. |
| **12** | $\ge 118$ | Hurricane Force | Devastation; catastrophic destruction. |

---

## 3. Severe Convective Storms & Lightning Safety

### 3.1 The 30/30 Lightning Safety Rule
When severe thunderstorms are identified via `get_alerts`:
1. **The 30-Second Rule:** If the time delay between a visible lightning flash and the audible thunder crack is under 30 seconds, the lightning stroke is within 10 km (6 miles). Seek immediate shelter inside an enclosed building or hard-topped vehicle.
2. **The 30-Minute Rule:** Wait at least 30 minutes following the last observed lightning flash or thunderclap before resuming outdoor activities.

---

## 4. International Meteorological Units & Conversions

Weather Buddy handles bidirectional dynamic conversion across standard unit systems:

| Metric Measurement | SI / Metric Base Unit | Imperial Base Unit | Conversion Equation |
|--------------------|:---------------------:|:------------------:|:--------------------|
| **Temperature** | Celsius ($^\circ\text{C}$) | Fahrenheit ($^\circ\text{F}$) | $^\circ\text{F} = (^\circ\text{C} \times 9/5) + 32$ |
| **Wind Velocity** | Meters / Second ($\text{m/s}$) | Miles / Hour ($\text{mph}$) | $\text{mph} = \text{m/s} \times 2.23694$ |
| **Wind Velocity** | Kilometers / Hour ($\text{km/h}$) | Knots ($\text{kn}$) | $\text{kn} = \text{km/h} \times 0.539957$ |
| **Atmospheric Pressure**| Hectopascals ($\text{hPa}$) | Inches of Mercury ($\text{inHg}$) | $\text{inHg} = \text{hPa} \times 0.02953$ |
| **Rainfall Accumulation**| Millimeters ($\text{mm}$) | Inches ($\text{in}$) | $\text{in} = \text{mm} \times 0.03937$ |
