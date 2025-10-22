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
