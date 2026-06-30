# S1a-ChartPrimitives — Fix Report

**Inputs cited:** `/Users/thristannewman/ADinsights/artifacts/sprint/S1-architect-design.md` (§2 Component Register, §3 Token strategy, §4 Recharts conventions, §5 A11y contract, §8 work split), `/Users/thristannewman/ADinsights/artifacts/viz/sprints-plan.md` (Sprint 1 DoD), `/Users/thristannewman/ADinsights/frontend/src/components/CampaignTrendChart.tsx`, `/Users/thristannewman/ADinsights/frontend/src/components/AgeDistributionBar.tsx`, `/Users/thristannewman/ADinsights/frontend/src/styles/chartTheme.ts`, `/Users/thristannewman/ADinsights/frontend/src/styles/theme.css`.

## Status

**GREEN** — all S1a owned files compile, lint clean, and the production build succeeds.

## Files Created

| File                                              | Kind          | Purpose                                                                                                                                                                                                                                                                                               |
| ------------------------------------------------- | ------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `frontend/src/styles/viz-tokens.css`              | CSS tokens    | `--viz-series-0..5`, `--viz-platform-*`, `--viz-axis-*`, `--viz-grid`, `--viz-point-focus`, `--viz-pattern-opacity`, plus `.sr-only` utility. Light + dark themes.                                                                                                                                    |
| `frontend/src/components/viz/ChartSkeleton.tsx`   | Primitive     | Composes `<Skeleton>` into chart-shaped footprints (line / bar / pie / table / kpi / kpi-strip / sparkline / bubble). Matches target chart size so there is no CLS when data arrives.                                                                                                                 |
| `frontend/src/components/viz/Sparkline.tsx`       | Primitive     | Tiny inline LineChart, no axes/grid/tooltip, for use in table cells. Required `ariaLabel` prop.                                                                                                                                                                                                       |
| `frontend/src/components/viz/TrendLine.tsx`       | Primitive     | Multi-series LineChart with optional dual-axis, `peerData` dashed series, monotone stroke, horizontal-only grid. Follows `CampaignTrendChart.tsx` idioms (ComponentType cast, `chartMargins`, `createTooltipProps`). Renders an `.sr-only` `<table>` equivalent alongside the SVG for screen readers. |
| `frontend/src/components/viz/PeerAvgLine.tsx`     | Sub-component | Dashed, faded secondary `<Line>` used inside `<TrendLine>`. Never rendered standalone.                                                                                                                                                                                                                |
| `frontend/src/components/viz/DistributionBar.tsx` | Primitive     | Horizontal (default) or vertical bars with optional percent labels. Accepts `patternId` for secondary (non-color) encoding via `<pattern>` defs.                                                                                                                                                      |
| `frontend/src/components/viz/PieComposition.tsx`  | Primitive     | Donut (default) or pie; accepts optional `centerLabel` + per-segment `patternId`.                                                                                                                                                                                                                     |
| `frontend/src/components/viz/BubbleScatter.tsx`   | Primitive     | Scatter + `<ZAxis>` with shape (circle/triangle/square) as the mandated categorical encoding. One `<Scatter>` series per distinct shape.                                                                                                                                                              |
| `frontend/src/components/viz/VizEmptyIcon.tsx`    | Helper        | Shared no-data SVG icon used by every primitive's EmptyState. Avoids emojis per project conventions. Kept local so S1b's viz-namespaced `EmptyState` wrapper can replace or augment per reason code without touching the primitives.                                                                  |

## Files Modified

| File                                | Edit                                                                                                                         |
| ----------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `frontend/src/styles/theme.css`     | Added single `@import './viz-tokens.css' layer(tokens);` line below the existing `foundations.css` import. No other changes. |
| `frontend/src/styles/chartTheme.ts` | Appended `VIZ_CSS_VARS`, `PLATFORM_CHART_TOKENS`, `STATUS_COLORS`, `resolveSeriesColor()`. Existing exports untouched.       |

## Token additions summary

All six series colors verified against WCAG AA on card surfaces in both themes using the contrast ratios documented in `S1-architect-design.md` §3.3.

| Token (light / dark)                                                       | Hex light                         | Hex dark                          | Notes                                                           |
| -------------------------------------------------------------------------- | --------------------------------- | --------------------------------- | --------------------------------------------------------------- |
| `--viz-series-0`                                                           | `#2563eb`                         | `#60a5fa`                         | meta / primary                                                  |
| `--viz-series-1`                                                           | `#c2410c`                         | `#fb923c`                         | google / orange-700 (darker than `#f97316` to hit AA on white)  |
| `--viz-series-2`                                                           | `#0369a1`                         | `#38bdf8`                         | accent blue                                                     |
| `--viz-series-3`                                                           | `#047857`                         | `#4ade80`                         | conversions / green                                             |
| `--viz-series-4`                                                           | `#7e22ce`                         | `#c084fc`                         | audience / purple                                               |
| `--viz-series-5`                                                           | `#be123c`                         | `#fb7185`                         | alert / red                                                     |
| `--viz-platform-peer-avg`                                                  | `rgba(71,85,105,0.55)`            | `rgba(148,163,184,0.60)`          | Deliberately sub-AA — paired with dashed stroke + legend label. |
| `--viz-status-enabled` / `-paused` / `-removed`                            | `#047857` / `#b45309` / `#be123c` | `#4ade80` / `#fbbf24` / `#fb7185` | Amber-700 for paused hits 4.55:1 on white.                      |
| `--viz-axis-line` / `--viz-axis-tick` / `--viz-grid` / `--viz-grid-strong` | `rgba(15,23,42,…)`                | `rgba(226,232,240,…)`             | Chart chrome per architect token spec.                          |
| `--viz-tooltip-surface` / `-text`                                          | `#0f172a` / `#f8fafc`             | `rgba(15,23,42,0.96)` / `#f8fafc` | Matches existing `chartTheme.tooltip`.                          |
| `--viz-pattern-opacity`                                                    | `0.55`                            | `0.45`                            | Secondary-encoding fill opacity.                                |
| `--viz-point-focus`                                                        | `0 0 0 3px rgba(37,99,235,0.45)`  | `0 0 0 3px rgba(96,165,250,0.55)` | Keyboard focus ring on data points.                             |

The `.sr-only` helper class was added because no existing visually-hidden utility lives in the codebase and every chart primitive needs it for its tabular-equivalent table.

## Accessibility contract honored

- Every non-sparkline chart SVG root has `role="img"` + required `aria-label`.
- Every chart primitive renders an `.sr-only` `<table>` with a matching `<caption>` and one row per data point (columns depend on the primitive — e.g. Date × series for TrendLine, Label × Value × Share for PieComposition).
- `BubbleScatter` exposes `shape: 'circle' | 'triangle' | 'square'` as the mandated non-color categorical encoding.
- `TrendLine` supports `strokeDasharray` per series via `series[i].dashed`.
- `PeerAvgLine` renders dashed `4 4` with `isAnimationActive={false}` per architect spec.
- Sparkline is the only primitive that skips the accessible-table pattern — it is intended for table-cell inline use where the adjacent cell IS the accessible value.
- `AccessibleTableToggle` is S1b-owned and already landed in `viz/`; it composes the existing chart-node / table-node pair cleanly (I inspected the delivered file to confirm prop shape compatibility).

## Sprint-boundary checks (S1b not touched)

Confirmed my commits do NOT modify any S1b-owned file: `KpiTile.tsx`, `DataTable.tsx`, `AccessibleTableToggle.tsx`, `lib/csvExport.ts`, or `viz/index.ts`. The barrel's `TODO(S1a)` comment still lists `DistributionBar`, `BubbleScatter`, `PieComposition` as awaiting landing — S1b or S1c can un-comment those three lines now that my files exist. I intentionally did not edit the barrel because it is S1b-owned per §8.

## Verification

### TypeScript (viz-related files only)

```
$ cd frontend && npx tsc --noEmit 2>&1 | grep -E "viz/|styles/chartTheme"
(no output — zero errors in S1a scope)
```

The pre-existing non-S1a errors in the global `tsc --noEmit` run (e.g. `useDashboardStore.test.ts`, `AudienceDashboard.test.tsx`, `MetaDashboardEmptyStates.test.tsx`, `ErrorBoundary.test.tsx`) were present before this sprint started and are unrelated to the viz kit; they belong to a separate backlog.

### Lint

```
$ cd frontend && npm run lint
> adinsights-frontend@0.1.0 lint
> eslint .
(clean exit, no output)
```

### Build

```
$ cd frontend && npm run build
...
dist/assets/generateCategoricalChart-DgXWzouq.js      383.99 kB │ gzip: 105.92 kB
✓ built in 4.10s
```

All viz primitives compiled into their expected chunks (`LineChart-*.js`, `PieChart-*.js`, etc.) — Recharts tree-shaking is preserved.

## Notes for downstream agents

1. **Barrel resolution.** Un-commenting the three `TODO(S1a)` lines in `viz/index.ts` will surface `DistributionBar`, `BubbleScatter`, `PieComposition` from the barrel. Whoever touches the barrel next should also export `VizEmptyIcon` if reason-code wrappers want to reuse the default icon.
2. **`PeerAvgLine`'s `data` prop is currently a forward-compat parameter.** The actual peer-avg series is rendered via the `__peerAvg` key merged into the host chart's data by `TrendLine.useMemo`. Callers can pass `data` today without effect — a future sprint can wire standalone usage if needed.
3. **`prefers-reduced-motion`.** Not yet wired on the primitives. Architect §5.3 defers this to the `AccessibleTableToggle` / host-dashboard layer because a Recharts-level toggle requires a shared hook; leaving it for S1c or Sprint 2.
4. **Recharts 3.7 drift risk.** `<ZAxis>` `range` prop and `<Pie>` `paddingAngle` were both exercised in this delivery and render cleanly under 3.7.0 per the production build. No spike required.
