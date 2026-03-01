# ADinsights Frontend Design System (v0.1)

This guide documents the current UI tokens and component conventions used in the
React + Vite frontend. It is intentionally short and practical.

## Principles

- Prioritize hierarchy: the most important metric should be immediately legible.
- Keep surfaces calm: use subtle elevation, avoid heavy gradients or busy backgrounds.
- Favor clarity over decoration: labels are small, values are bold.
- Keep motion meaningful and opt-in for reduced motion.

## Change log

- v0.1: Initial system definition with tokens, components, and motion guidance.

## Token Sources

- Typography + spacing + radii + base shadows: `frontend/src/styles/foundations.css`
- Theme tokens (light/dark): `frontend/src/styles/theme.css`
- App and component styles: `frontend/src/styles.css`, `frontend/src/styles/dashboard.css`

## Typography

- Display/value text: larger sizes from `--font-size-h1`/`--font-size-h2`.
- Labels: use `--font-size-label` with uppercase and letter spacing.
- Body text: `--font-size-body` with `--line-height-body`.

## Color

- Use `--color-text-primary`/`secondary`/`muted` for copy.
- Accent actions: `--color-accent` and `--color-accent-strong`.
- Borders: `--color-border-subtle` for cards, `--color-border-field` for inputs.

## Layout + Spacing

- Prefer `--space-*` tokens for padding/margins.
- Grid rhythm: 24px (`--space-6`) or 28px (`--space-7`) for major blocks.

## Components

### KPI/Metric Cards

- Canonical card: `Metric` (`frontend/src/components/Metric.tsx`).
- Compact variant: `.metric-card--compact` for detail pages.

Example

```tsx
<Metric label="Spend" value="$12,340" trend={[2, 6, 4, 9]} />
<Metric label="ROAS" value="3.4" className="metric-card--compact" />
```

### Chart Cards

- Use `ChartCard` for consistent header/actions/footer layout.
- Keep titles in `--font-size-h2` and descriptions muted.

Example

```tsx
<ChartCard title="Daily spend" description="Last 7 days">
  <ResponsiveContainer>
    <CampaignTrendChart data={trend} currency="USD" />
  </ResponsiveContainer>
</ChartCard>
```

### Tables

- Toolbar: search + density controls on the right.
- Header row: uppercase labels, smaller type, subtle divider shadow.

Example

```tsx
<DataTable
  title="Campaign metrics"
  description="Performance breakdown"
  columns={columns}
  data={rows}
/>
```

### Map Panel

- Controls grouped in overlay with subtle blur.
- Legend uses small uppercase label and consistent spacing.

## Motion

- Use `fade-rise` for chart/table reveal.
- Use `dashboard-reveal` for grid tiles.
- Must be disabled under `prefers-reduced-motion`.

## Accessibility

- Preserve focus-visible outlines (`--focus-ring`).
- Keep contrast at or above AA for key text and controls.
- Avoid tooltips as the only way to access information.

## Checklist for New UI

- Uses tokens from `theme.css` and spacing from `foundations.css`.
- Follows component patterns above (Metric/ChartCard/DataTable).
- Motion respects reduced-motion.
- Focus styles remain visible and consistent.

## Dos and Don'ts

- Do reuse tokens and component classes; avoid one-off styles.
- Do keep “value” typography consistent across KPI/Chart/Table.
- Don't introduce new colors or fonts without updating tokens.
- Don't add motion without reduced-motion guardrails.
