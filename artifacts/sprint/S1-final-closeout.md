# Sprint 1 — Shared Viz Kit — Final Closeout

**Inputs cited:** `/Users/thristannewman/ADinsights/artifacts/sprint/S1-architect-design.md`, `S1a-chart-primitives.md`, `S1b-table-and-kpi.md`, `S1c-stories-and-a11y.md`, `/Users/thristannewman/ADinsights/artifacts/viz/sprints-plan.md`

## Status: GREEN

Sprint 1 delivered a fully-typed, a11y-tested, Storybook-documented shared viz kit at `frontend/src/components/viz/`. All 10 primitives in the `sprints-plan.md` deliverable list are shipped. Downstream sprints (Meta Sprint 2, Google Ads Sprint 3, Combined Sprint 4) can now `import { KpiTile, TrendLine, … } from '@/components/viz'` without further coordination.

## Component register — shipped state

| Component | File | Built by | Tests | Story |
|---|---|---|---|---|
| `KpiTile` | `viz/KpiTile.tsx` | S1b | ✅ | ✅ |
| `TrendLine` | `viz/TrendLine.tsx` | S1a | ✅ | ✅ |
| `Sparkline` | `viz/Sparkline.tsx` | S1a | ✅ | ✅ |
| `DistributionBar` | `viz/DistributionBar.tsx` | S1a | ✅ | ✅ |
| `BubbleScatter` | `viz/BubbleScatter.tsx` | S1a | ✅ | ✅ |
| `PieComposition` | `viz/PieComposition.tsx` | S1a | ✅ | ✅ |
| `VizDataTable` | `viz/DataTable.tsx` | S1b | ✅ | ✅ |
| `EmptyState` | `components/EmptyState.tsx` (re-export) | pre-existing | ✅ | ✅ |
| `ChartSkeleton` | `viz/ChartSkeleton.tsx` | S1a | ✅ | ✅ |
| `AccessibleTableToggle` | `viz/AccessibleTableToggle.tsx` | S1b | ✅ | ✅ |
| `PeerAvgLine` (sub-component) | `viz/PeerAvgLine.tsx` | S1a | via TrendLine | via TrendLine.WithPeerAvg |
| `VizEmptyIcon` (internal) | `viz/VizEmptyIcon.tsx` | S1a | — | — |

## Supporting deliverables

- **Design tokens**: new `frontend/src/styles/viz-tokens.css` with `--viz-series-0..5` (WCAG AA), `--viz-platform-*`, `--viz-axis-*`, `--viz-grid`, `--viz-point-focus`, `.sr-only` utility. Light + dark themes.
- **`chartTheme.ts`**: appended `VIZ_CSS_VARS`, `PLATFORM_CHART_TOKENS`, `STATUS_COLORS`, `resolveSeriesColor()` without modifying any existing exports.
- **`csvExport.ts`**: RFC-4180 serializer with CSV-injection hardening (`=/+/-/@` → `'`-prefixed). Full torture test coverage in `csvExport.test.ts`.
- **`@storybook/addon-a11y@8.6.14`**: installed and wired into `.storybook/main.ts`.
- **Barrel**: `viz/index.ts` exports all 11 primitives + `EmptyState` re-export.

## Final test matrix (run after all three agents landed)

| Gate | Command | Result |
|---|---|---|
| Frontend lint | `cd frontend && npm run lint` | **clean** |
| Frontend build | `cd frontend && npm run build` | **✓ built in 5.57s** |
| Frontend vitest (full) | `cd frontend && npm test -- --run` | **597 passed / 597** (113/113 files) |
| Backend pytest (full) | `cd backend && pytest` | **727 passed, 1 skipped** |
| Backend ruff | `ruff check backend` | **All checks passed!** |

Storybook also builds cleanly (confirmed by S1c: `✓ built in 18.26s`, addon-a11y axe bundle confirmed at 572 kB).

## Frontend test delta across the whole session

| Snapshot | Pass | Fail | Note |
|---|---|---|---|
| Pre-sprint (C4 closeout) | 514 | 14 | DataSources scrollIntoView cascade |
| After scrollIntoView polyfill | 527 | 1 | SavedDashboardPage assertion drift |
| After S1 viz kit | **597** | **0** | +70 new tests, remaining drift cleared |

## Accessibility posture

- Every chart primitive emits `role="img"` + mandatory `aria-label` prop
- Every chart primitive renders a hidden `<table>` tabular-equivalent (inside `.sr-only`)
- `AccessibleTableToggle` keeps both views mounted; `hidden` + `aria-hidden` gate visibility without destroying a11y tree
- Non-color encoding: `BubbleScatter` uses shape (circle/triangle/square); `TrendLine` supports `strokeDasharray`; `DistributionBar` + `PieComposition` support SVG `<pattern>` fills
- jest-axe runs on every primitive's Default render — zero violations observed

## Handoff / follow-ups (not in Sprint 1)

1. **Callsite migration** — `CampaignTrendChart.tsx`, `AgeDistributionBar.tsx`, `DeviceDonut.tsx`, `Metric.tsx`, `Skeleton.tsx`, legacy `DataTable.tsx` callsites can progressively swap to viz-kit primitives in Sprint 2+. The architect explicitly put this out of scope.
2. **`TrendLine.StackedArea`** variant — noted by S1c as deferred; the primitive doesn't expose that mode yet. Add when Sprint 4 combined area charts need it.
3. **`prefers-reduced-motion`** polyfill — architect called out the JSDOM `matchMedia` gap; deferred to Sprint 2 when a shared hook lands.
4. **Vitest ≥ 80% coverage gate** — skipped per architect §10.10 because Recharts SVG output inflates coverage noise; add proper filter before enabling.
5. **Top-level `SavedDashboardPage` test assertion drift** — appears to have cleared in the full-suite run now that the scrollIntoView cascade is gone. Keep an eye on it in CI; it was flaky due to cross-file mock ordering.

## Artifact trail

- Architect: `artifacts/sprint/S1-architect-design.md`
- Chart primitives: `artifacts/sprint/S1a-chart-primitives.md`
- Table + KPI: `artifacts/sprint/S1b-table-and-kpi.md`
- Stories + a11y: `artifacts/sprint/S1c-stories-and-a11y.md`
- This closeout: `artifacts/sprint/S1-final-closeout.md`

## Verdict: GREEN — Sprint 1 foundations are ready for Sprint 2 (Meta charts) to consume.
