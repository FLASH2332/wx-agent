# Weather Buddy — GDACS Emergency Disaster Alert Architecture

This specification documents the disaster hazard detection pipeline in Weather Buddy, detailing integration with the **Global Disaster Alert and Coordination System (GDACS)**, CAP (Common Alerting Protocol) XML schema parsing, and geospatial proximity matching.

---

## 1. Disaster Hazard Integration Overview

In addition to municipal forecasts, Weather Buddy monitors global catastrophic meteorological and geological events (Tropical Cyclones, Floods, Earthquakes, Volcanic Eruptions, and Forest Fires) to alert users to imminent environmental threats.

```
┌─────────────────────────────────┐
│     United Nations / GDACS      │
│     Real-Time Alert Feed (RSS)  │
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│     Next.js API Route Proxy     │  ◄── 5-Minute In-Memory Cache
│     (/api/alerts)               │      Avoids upstream rate throttling
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│  Geospatial Proximity Evaluator │  ◄── Calculates Haversine distance
│  (Haversine Distance Formula)   │      between user GPS and hazard epicenter
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│   Glassmorphic Alert Banner     │  ◄── Renders high-priority warning pill
│   (frontend/components/Alert...)│      with danger color coding
└─────────────────────────────────┘
```

---

## 2. Common Alerting Protocol (CAP) Parsing

GDACS publishes alert bulletins conforming to the OASIS Common Alerting Protocol (CAP v1.2):

### Core Alert Attributes
- **`identifier`:** Globally unique event hash (e.g., `GDACS-TC-1000921`).
- **`sender`:** Authoritative meteorological agency (e.g., `GDACS-JRC-EC`).
- **`sent`:** ISO 8601 UTC timestamp of bulletin dispatch.
- **`status`:** Operational status (`Actual`, `Exercise`, `System`, `Test`).
- **`msgType`:** Bulletin category (`Alert`, `Update`, `Cancel`).
- **`scope`:** Distribution scope (`Public`, `Restricted`).

### Severity & Priority Tiers
Weather Buddy maps CAP severity ratings to UI visual indicators:

| GDACS Alert Level | CAP Severity | Hex Color Code | UI Badge Label | Alert Description |
|:------------------:|:------------:|:--------------:|:--------------:|:------------------|
| **Red** | `Extreme` | `#EF4444` | **Severe Emergency** | Catastrophic hazard; immediate life-safety precautions required. |
| **Orange** | `Severe` | `#F97316` | **Hazard Warning** | Significant risk; localized destruction anticipated. |
| **Green** | `Moderate` | `#10B981` | **Advisory Notice** | Potential meteorological activity; monitor conditions. |

---

## 3. Geospatial Proximity Matching (Haversine Formula)

When a user requests weather for a city or triggers GPS auto-location, Weather Buddy calculates whether active disaster hazards fall within a warning radius ($R_{\text{warn}} = 250\text{ km}$):

$$d = 2 R \arcsin \left( \sqrt{\sin^2\left(\frac{\Delta \phi}{2}\right) + \cos(\phi_1) \cos(\phi_2) \sin^2\left(\frac{\Delta \lambda}{2}\right)} \right)$$

Where:
- $\phi_1, \phi_2$: Geodetic latitudes in radians.
- $\Delta \phi = \phi_2 - \phi_1$: Latitude delta.
- $\Delta \lambda = \lambda_2 - \lambda_1$: Longitude delta.
- $R = 6,371\text{ km}$: Mean volumetric radius of the Earth.

---

## 4. Resilience & Graceful Fallback Strategies

1. **Proxy Cache Hardening:** The `/api/alerts` route caches responses for 300 seconds (`s-maxage=300`). If GDACS upstream fails with HTTP 500, the proxy returns stale cached data (`stale-while-revalidate=600`) to prevent UI disruption.
2. **Silent Failure Toleration:** If both GDACS and NWS alert endpoints are unreachable, the dashboard suppresses the alert banner cleanly without throwing runtime exceptions.
