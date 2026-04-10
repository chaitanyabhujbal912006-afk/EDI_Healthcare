# Design System Strategy: the EdiPro design language

## 1. Overview & Creative North Star
In the complex, high-stakes world of Healthcare EDI (Electronic Data Interchange), clarity isn't just a preference—it's a clinical requirement. This design system moves away from the rigid, "heavy-duty" software aesthetic common in enterprise healthcare, adopting instead the **"EdiPro"** North Star.

**the EdiPro design language** represents a fusion of macOS Sonoma's glass-like depth with the high-density informational needs of medical data. We break the traditional "table-heavy" template by using intentional asymmetry, organic glassmorphism, and a depth model that feels physical. We treat data as living objects floating on a sophisticated, layered canvas, utilizing breathable white space to reduce the cognitive load of HIPAA-regulated workflows.

---

## 2. Colors & Surface Philosophy

Our palette balances professional authority with modern vibrancy. We use high-fidelity tokens to ensure the interface feels custom, not generic.

### Core Palette
- **Primary Blue (`primary` #0058bc):** The anchor of trust. Used for core actions.
- **Success Green (`#34C759` / standard):** For validated claims and successful transmissions.
- **Error Red (`error` #ba1a1a):** For EDI rejection codes and critical validation errors.
- **AI Indigo (`tertiary` #4a47d2):** Specifically reserved for automated parsing hints and AI-driven insights.

### Surface Hierarchy & The "No-Line" Rule
To achieve a high-end editorial feel, we prohibit the use of 1px solid borders for structural sectioning. 

*   **Boundary Definition:** Contrast is achieved via background shifts. A `surface-container-low` section should sit against a `surface` background to define its territory.
*   **Surface Nesting:** Treat the UI as stacked sheets.
    *   **Level 0 (Base):** `surface` (#f9f9fb)
    *   **Level 1 (Sections):** `surface-container-low` (#f3f3f5)
    *   **Level 2 (Active Cards):** `surface-container-lowest` (#ffffff)
*   **The Glass Rule:** For floating modals or navigation sidebars, use `surface` at 80% opacity with a `backdrop-filter: blur(20px)`. This allows the vibrant brand colors to bleed through subtly, creating a "frosted" effect that feels integrated into the OS.

---

## 3. Typography
We utilize a single-typeface system (Inter/SF Pro) to maintain professional cohesion, relying on extreme weight and scale shifts for editorial hierarchy.

*   **Display (3.5rem - 2.25rem):** Used for dashboard overviews (e.g., total claim volume). 
*   **Headline (2rem - 1.5rem):** Used for page titles. These should feel bold and authoritative, anchoring the top-left of the layout.
*   **Title (1.375rem - 1rem):** Used for card headers.
*   **Body (1rem - 0.75rem):** The workhorse of the EDI app. Use `body-md` for standard data and `body-sm` for secondary metadata.
*   **Labels (0.75rem - 0.6875rem):** All-caps or bolded sub-labels for technical EDI field names (e.g., ISA05, GS01).

---

## 4. Elevation & Depth
Depth is the differentiator. We use **Tonal Layering** instead of structural lines.

*   **Ambient Shadows:** Use extra-diffused shadows. For a floating card, use a blur of 32px-64px at 6% opacity. The shadow color must be a tinted version of `on-surface` (#1a1c1d) to ensure it feels like natural light, not a "dirty" grey drop.
*   **The Ghost Border:** If a container requires a border for accessibility, use the `outline-variant` token at 20% opacity. This creates a "hairline" effect that guides the eye without cluttering the screen.
*   **Layering Principle:** Place a `surface-container-highest` element (like a search bar) on a `surface-container-low` header to create a soft, natural lift.

---

## 5. Components

### Buttons
*   **Primary:** Solid `primary` (#0058bc) with a subtle gradient to `primary-container`. Use `lg` (1rem) rounding.
*   **Secondary:** `surface-container-high` background with `on-surface` text. No border.
*   **Tertiary:** Transparent background, `primary` text. Use for low-emphasis actions like "Cancel."

### Input Fields
*   **Style:** Minimalist. A subtle `surface-container-highest` background with a 1px `outline-variant` at 10% opacity. 
*   **Focus State:** The border transitions to `primary` with a 3px soft outer glow (ambient shadow) in the primary color.
*   **Rounding:** Always `md` (0.75rem) or `lg` (1rem).

### EDI Cards & Data Lists
*   **The No-Divider Rule:** Forbid 1px horizontal lines between list items. Instead, use a 4px `spacing` gap and alternating `surface-container-low` backgrounds, or simply generous vertical white space (8px-12px) to separate claim records.
*   **Status Chips:** Use `full` rounding (pill shape). Use `secondary-container` for neutral states and the AI Indigo for smart-parsed data.

### AI Insight Tooltips
*   **Style:** Pure Glassmorphism. `surface-container-lowest` at 70% opacity, `backdrop-filter: blur(12px)`. These should appear to float above the EDI stream, providing context-sensitive parsing help.

---

## 6. Do's and Don'ts

### Do
*   **Do** use overlapping elements. Let a glassmorphic sidebar slightly overlap the main content area to prove depth.
*   **Do** use high-density layouts for data grids, but keep the padding within cells at `spacing-3` (0.75rem) to ensure readability.
*   **Do** use the AI Indigo color sparingly—only when the system is making an automated decision or suggestion.

### Don't
*   **Don't** use solid black (#000000) for text. Use `on-surface` (#1a1c1d) for a softer, more premium contrast.
*   **Don't** use sharp corners. Everything—including inputs and containers—must fall between `md` (12px) and `xl` (24px) rounding.
*   **Don't** use traditional "Material" style heavy shadows. If a shadow is visible at first glance, it is too dark. It should feel like a presence, not a shape.

