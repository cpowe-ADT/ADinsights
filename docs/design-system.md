# Design System Tokens

The dashboard shell now centralizes theme primitives and semantic mappings so FilterBar, navigation, KPI cards, and sidebar panels
inherit consistent light/dark styling. Tokens live in `frontend/src/styles/foundations.css` (primitives) and
`frontend/src/styles/theme.css` (semantic aliases) with usage captured in Storybook.

## Primitive layer (`foundations.css`)

The foundations file defines the reusable scales the team agreed on:

- **Typography** – font family and roles (`--font-size-h1`, `--font-size-body`, `--font-size-label`) plus font weights.
- **Spacing** – a 4px-derived scale (`--space-1` … `--space-10`) used for padding, gaps, and layout clamps.
- **Radii & shadows** – `--radius-sm`, `--radius-md`, `--radius-pill`, and shadow presets (`--shadow-subtle`, `--shadow-elevated`).
- **Color palette** – neutral slate ramp, blue accent ramp, semantic state hues (`--color-green-500`, `--color-red-500`, etc.).
- **Motion** – shared durations/easings (`--motion-duration-short`, `--motion-ease-out`).

These primitives replace scattered hex values while remaining agnostic of light/dark themes.

## Semantic layer (`theme.css`)

`theme.css` maps primitives onto semantic tokens that components consume. Both `.theme-light` and `.theme-dark` blocks provide the
same token names, allowing `ThemeProvider` to toggle via a class on `<html>` without inline overrides.

Key semantic groups:

- **Surfaces & text** – `--color-surface-canvas`, `--color-surface-card`, `--color-text-primary`, and focus rings.
- **Shell chrome** – `--shell-header-bg-start/end`, `--shell-filterbar-surface`, `--shell-filterchip-*`, `--shell-nav-*`,
  and status tones. Filter chips, nav pills, and sticky bars now derive their background/border/text colors from these tokens.
- **Analytics cards** – `--metric-card-*`, `--metric-badge-*`, `--metric-delta-*`, and `--stat-card-*` control KPI tiles, stat cards,
  and sparkline colors across themes.
- **Layout helpers** – aliases for historical variables (`--surface-card`, `--border-soft`, etc.) remain for backwards compatibility
  while pointing to the new names.

## Usage guidelines

- Reference semantic tokens in components (`var(--shell-filterchip-active)`) rather than hard-coding palette values. The new
  `FilterBar.tokens.test.tsx` ensures light/dark tokens resolve correctly and runs `jest-axe` accessibility checks in both modes.
- Use `--space-*` scale for layout spacing. Shell padding now relies on `clamp()` with `--space-6`/`--space-10` for responsive gutters.
- Prefer semantic card tokens (`--metric-card-surface`, `--stat-card-border`) for analytic tiles so gradients and borders adjust with
  theme mappings.
- When building new surfaces, pick the closest semantic token; only introduce a new token if multiple components will reuse it.
- Storybook decorators expose a global **Theme** toolbar. Light/Dark stories in `Metric.stories.tsx`, `FilterBar.stories.tsx`, and
  `DashboardLayout.stories.tsx` demonstrate expected usage and provide Chromatic baselines.

By layering primitives and semantics, the shell now switches themes entirely through CSS custom properties, keeping React components
free from theme-specific logic.

## Tenant switcher accessibility

- The dashboard header now includes an accessible tenant switcher built on a listbox pattern. Keyboard support covers <kbd>Tab</kbd>, <kbd>Arrow</kbd>, <kbd>Home/End</kbd>, <kbd>Enter</kbd>, and <kbd>Escape</kbd> with focus returning to the trigger.
- Live updates announce loading states (“Loading tenants…”), fetch results, and tenant changes via an `aria-live="polite"` region so assistive technologies stay synchronized.
- Menu surfaces reuse shell tokens for contrast (`--header-select-bg`, `--surface-subtle`, `--shell-filterchip-active`) and inherit the global focus ring to satisfy WCAG 2.1 AA contrast targets in light and dark themes.
- Storybook exercises the component in light/dark themes with mocked tenant data so Chromatic can snapshot focus styling and aria-live copy without relying on the API.

## Dashboard spacing & typography refresh (2024-10)

- Dashboard shell spacing now uses `--space-*` tokens exclusively. Primary gutters are `clamp(var(--space-6), 3vw, var(--space-10))` on the layout, while card padding steps up from `var(--space-5)` mobile to `var(--space-6)` at ≥768 px.
- Heading hierarchy follows semantic tokens: eyebrow labels use `--font-size-label` with uppercase tracking, page `h1` clamps between design values, and card titles use `--font-size-h2` at `var(--font-weight-semibold)`.
- KPI grid aligns to Figma with `var(--space-4)` gaps and ensures tiles land on an 8 px rhythm (±2 px tolerance verified in Chromatic once updated).
- Chart footer typography uses muted tokens for helper text and primary text tokens for values to maintain a 3:1 contrast in both themes.

## Semantic tokens for analytics table & parish map

- Added table semantic tokens in `theme.css` (`--table-surface`, `--table-toolbar-surface`, `--table-control-active`, etc.) to standardize zebra striping, hover, selected, and focus states. Hover/focus states meet ≥3:1 contrast against the base row tone.
- Density toggles use `--table-control-text` and `--table-control-text-active` to keep text legible against pill backgrounds across themes.
- Map legend, tooltip, and control surfaces now consume `--map-*` tokens. Both Leaflet layers and legends source fills from `--map-fill-0…5` while outlines and highlight states reference `--map-border`/`--map-highlight` for keyboard focus visibility.
- Removed hard-coded hex ramps from `ParishMap` and DataTable styles; all state cues resolve through semantic CSS variables for consistency with Branch 1 tokens.

## Component checklist (dashboard refresh)

| Component | Light theme | Dark theme | Notes |
| --- | --- | --- | --- |
| KPI stat cards | ✅ | ✅ | Uses `--stat-card-*` tokens and matches spacing guidance above. |
| Parish map | ✅ | ✅ | Legend/tooltips consume `--map-*` tokens; hover/focus contrast ≥3:1. |
| Campaign data table | ✅ | ✅ | Tokenized rows, hover, selected, and density controls; focus rings preserved. |
