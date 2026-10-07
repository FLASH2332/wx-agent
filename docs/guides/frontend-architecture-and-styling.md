# Weather Buddy — Frontend Architecture, Tailwind CSS & Glassmorphism System

This design guide documents the visual design tokens, component architecture, CSS variables, and layout guidelines implemented across Weather Buddy's Next.js 14 frontend.

---

## 1. Design System Philosophy: Premium Glassmorphism

Weather Buddy's interface is crafted to evoke modern meteorological instrumentation with translucent, high-contrast, layered visual surfaces:

1. **Depth via Layered Transparency:** Instead of opaque card backgrounds, surfaces use translucent dark glass with multi-layered diffuse drop shadows:
   ```css
   background: rgba(15, 23, 42, 0.65);
   backdrop-filter: blur(16px) saturate(180%);
   border: 1px solid rgba(255, 255, 255, 0.08);
   box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
   ```
2. **Concentric Border Radii:** Nested component containers follow concentric geometric curves:
   $$R_{\text{outer}} = R_{\text{inner}} + \text{Padding}$$
3. **Micro-Interactions & Press Feedback:** All interactive buttons incorporate active compression feedback:
   ```css
   transition: transform 120ms cubic-bezier(0.2, 0, 0, 1);
   &:active {
     transform: scale(0.96);
   }
   ```

---

## 2. Color Palette & Atmospheric Accents

Weather Buddy utilizes an adaptive palette reflecting meteorological states:

| Atmospheric Condition | Accent Primary | Background Glow Accent | Semantic Role |
|-----------------------|:--------------:|:----------------------:|:--------------|
| **Clear / Sunny** | `#F59E0B` (Amber) | `rgba(245, 158, 11, 0.15)` | Temperature highlights & sun badges |
| **Rain / Drizzle** | `#38BDF8` (Sky Blue) | `rgba(56, 189, 248, 0.15)` | Precipitation probability & moisture |
| **Thunderstorm** | `#A855F7` (Purple) | `rgba(168, 85, 247, 0.18)` | Severe hazard badges & high alerts |
| **Snow / Frost** | `#E2E8F0` (Slate Light)| `rgba(226, 232, 240, 0.12)` | Freezing level & low temp alerts |
| **Wind / Gusts** | `#34D399` (Emerald) | `rgba(52, 211, 153, 0.14)` | Wind speed vectors & compass dial |

---

## 3. Typography & Tabular Numerals

Meteorological dashboards suffer visual instability when changing numbers cause sibling elements to shift. Weather Buddy eliminates jitter by enforcing **tabular numeric glyphs**:

```css
.tabular-nums {
  font-variant-numeric: tabular-nums;
  font-feature-settings: "tnum";
}
```

---

## 4. Responsive Breakpoint Strategy

| Breakpoint Token | Min Width | Layout Behavior |
|:----------------:|:---------:|:----------------|
| `base` (Mobile) | $0\text{ px}$ | Single column vertical stack; horizontal scroll timeline; sticky bottom chat bar. |
| `md` (Tablet) | $768\text{ px}$ | Two-column split (current weather hero + forecast sidebar); expanded chat window. |
| `lg` (Desktop) | $1024\text{ px}$| Three-column dashboard; full 24-hour horizontal forecast grid; embedded conversation panel. |
| `xl` (Ultrawide)| $1280\text{ px}$| Max container width capped at $1280\text{px}$ with centered ambient glow vignette. |
