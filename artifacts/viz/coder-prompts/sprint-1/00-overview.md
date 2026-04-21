# Sprint 1 Overview — Shared Visualization Kit

**Sprint:** 1
**Goal:** Build the shared viz component library that all Sprint 2–4 pages depend on. Nothing in Sprint 2, 3, or 4 should be started until Sprint 1 is complete and merged.

## Deliverable ordering within Sprint 1

These deliverables can be worked in parallel by multiple engineers, but must all pass before any Sprint 2 work begins:

| Order | Deliverable | File | Size | Parallelizable? |
|-------|------------|------|------|-----------------|
| 1a | `ChartSkeleton` | `chart-skeleton.md` | S | Yes |
| 1a | `EmptyState` (extend) | covered in `kpi-tile.md` | XS | Yes |
| 1b | `KpiTile` | `kpi-tile.md` | S | Yes — after EmptyState |
| 1b | `AccessibleTableToggle` | `accessible-table-toggle.md` | S | Yes |
| 1b | `Sparkline` | `sparkline.md` | XS | Yes |
| 1c | `TrendLine` | `trend-line.md` | M | After ChartSkeleton + AccessibleTableToggle |
| 1c | `DistributionBar` | `distribution-bar.md` | S | After ChartSkeleton + AccessibleTableToggle |
| 1c | `PieComposition` | `pie-composition.md` | S | After ChartSkeleton + AccessibleTableToggle |
| 1c | `BubbleScatter` | `bubble-scatter.md` | M | After ChartSkeleton + AccessibleTableToggle |
| 1d | `DataTable` | `data-table.md` | M | After ChartSkeleton |
| 1e | Storybook stories | `storybook-stories.md` | S | After all components |

## Key constraints (must not be violated)

- Do NOT install new npm packages. The following are already present:
  - `recharts ^3.7.0` (installed: 3.8.1)
  - `@tanstack/react-table ^8.15.0`
  - `leaflet ^1.9.4`
  - Storybook 8.6.14 with `@storybook/addon-essentials`, `@storybook/addon-interactions`, `@storybook/react-vite`
  - `jest-axe ^9.0.0`, `@types/jest-axe`, `eslint-plugin-jsx-a11y`
  - **PapaParse is NOT installed** — CSV export must use a hand-rolled serializer (see `data-table.md`)
  - **`@storybook/addon-a11y` is NOT installed** — use `jest-axe` for a11y testing in vitest instead
  - **`FunnelChart` is NOT available in Recharts 3.8.1** — the node_modules directory is not present locally but the lock file confirms 3.8.1. The Recharts v3 release removed FunnelChart. Use a stepped-bar fallback (see `meta-campaigns.md` in sprint-2)

- All components go in `frontend/src/components/viz/`
- `EmptyState` already exists at `frontend/src/components/EmptyState.tsx` with `reasonCode` prop — extend, do not replace
- Chart theme tokens live in `frontend/src/styles/chartTheme.ts`
- Test files go in `frontend/src/components/viz/__tests__/`

## Sprint 1 Definition of Done

- [ ] All components render in Storybook with default, loading, empty, and error story variants
- [ ] `jest-axe` a11y assertions pass in vitest for every component
- [ ] `DataTable` CSV export snapshot test passes
- [ ] `AccessibleTableToggle` is keyboard-operable (tab + enter/space)
- [ ] `TrendLine` renders peer average line when `peerData` prop is provided
- [ ] No new npm packages added
- [ ] `cd frontend && npm test -- --run` green (excluding pre-existing DataSources failures)
- [ ] `cd frontend && npm run lint` clean
- [ ] `cd frontend && npm run build` clean
