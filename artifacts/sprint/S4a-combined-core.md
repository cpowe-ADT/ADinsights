# S4a CombinedCore — Closeout Report

**Inputs cited**: `artifacts/sprint/S4-architect-design.md` §6–§9 · viz-kit barrel `frontend/src/components/viz/index.ts` · `frontend/src/styles/chartTheme.ts#PLATFORM_CHART_TOKENS` · Phase 2 contracts (FP-PLAT-02, FP-PLAT-03, FP-CAMP-01, FP-CAMP-02, FP-CREA-01, FP-CREA-03).

## Scope

Upgraded the three combined-dashboard route pages (Platform, Campaign, Creative) to consume Sprint 1 viz-kit primitives, shared platform-label/color helpers, and client-side cross-platform aggregates — without touching the Zustand stores, any viz primitive internals, adapters, or backend.

## Files Modified

| File                                                              | Action                                                                                                            | LoC |
| ----------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- | --- |
| `frontend/src/lib/platformLabels.ts`                              | **NEW** — shared `formatPlatformLabel` + `platformColor`                                                          | ~67 |
| `frontend/src/lib/combinedAggregates.ts`                          | **NEW** — pure reducers for cross-platform KPIs                                                                   | ~70 |
| `frontend/src/routes/PlatformDashboard.tsx`                       | Rewritten around viz kit (KpiTile×5, TrendLine, DistributionBar 2×2, PieComposition, VizDataTable)                | 550 |
| `frontend/src/routes/CampaignDashboard.tsx`                       | Added cross-platform KpiTile strip, platform legend, top-10 DistributionBar — legacy CampaignTable preserved      | 568 |
| `frontend/src/routes/CreativeDashboard.tsx`                       | Rewritten around viz kit (KpiTile×4, BubbleScatter, PieComposition, VizDataTable) — legacy CreativeTable retained | 386 |
| `frontend/src/routes/__tests__/PlatformDashboard.test.tsx`        | Rewritten with viz-kit mocks — 6 tests                                                                            | —   |
| `frontend/src/routes/__tests__/CampaignDashboard.layout.test.tsx` | Extended with cross-platform strip + legend + top-10 bar assertions                                               | —   |
| `frontend/src/routes/__tests__/CreativeDashboard.test.tsx`        | Extended with viz-kit mocks + 6 new tests                                                                         | —   |

## Phase 2 contracts — preservation citations

- **FP-PLAT-03** (top-2-by-spend label derivation): preserved by extracting `formatPlatformLabel()` to `frontend/src/lib/platformLabels.ts:20-49` and consuming it in `PlatformDashboard.tsx` KPI label construction (`formatPlatformLabel(topRow.platform) + ' spend'`). Test assertion still holds verbatim: `screen.getByText(/Facebook spend: 2000/)` and `screen.getByText(/Instagram spend: 1500/)` (see `PlatformDashboard.test.tsx:154-155`).
- **FP-PLAT-02** (empty state): preserved — `PlatformDashboard.tsx` still branches on empty `byPlatform` and renders the same title "No platform data yet" (tested at `PlatformDashboard.test.tsx:199-209`).
- **FP-CAMP-02** (consolidated 3-branch empty-state): preserved at original position in `CampaignDashboard.tsx` — untouched. Legacy `<CampaignTable>` drill-down preserved per architect §8.2.
- **FP-CREA-01 / FP-CREA-03** (3-branch availability empty-state): preserved exactly in `CreativeDashboard.tsx:194-225`. Tested by the 3 retained existing tests + 2 new variant tests (`no_matching_filters`, `no_recent_data`).
- **Parish selector state**: untouched — `getCreativeRowsForSelectedParish` still consumed; no store surgery performed.

## StackedArea fallback note

Per architect §6 "Deferred per-platform daily trend":

> The combined metrics payload's `CampaignTrendPoint` lacks a `platform` discriminator. Stacking by platform would require a new backend endpoint.

Implemented: single-series `TrendLine` with an inline `[NEW-ENDPOINT]` comment block at `PlatformDashboard.tsx:323-338` marking the deferral. Trend card uses `AccessibleTableToggle` wrapping `TrendLine` for a11y.

## Platform color parity

All three dashboards consume `platformColor()` from `frontend/src/lib/platformLabels.ts:51-66`, which reads `PLATFORM_CHART_TOKENS` from `frontend/src/styles/chartTheme.ts`:

- Meta family (`meta`, `facebook`, `instagram`) → `PLATFORM_CHART_TOKENS.meta_ads` (blue)
- Google family (`google`, `google_ads`) → `PLATFORM_CHART_TOKENS.google_ads` (orange)
- Fallback → `PLATFORM_CHART_TOKENS.peer_avg` (gray)

Color is backed by text labels on every chip/legend (non-color encoding) per WCAG.

## Accessibility

- All new chart primitives carry `role="img"` + `aria-label` (from viz-kit defaults).
- Legend chips use `aria-hidden` dots with text labels (non-color encoding).
- `AccessibleTableToggle` wraps the `TrendLine` in PlatformDashboard for keyboard table access.
- `KpiTile` strip wrapped in `role="group"` with stable aria-labels (`"Platform KPIs"`, `"Cross-platform KPIs"`, `"Creative KPIs"`).
- CampaignDashboard axe pass preserved (`expect(results).toHaveNoViolations()` in the layout test).

## Tests Added

**PlatformDashboard.test.tsx (6 tests, replaces prior scaffold)**

1. Renders heading, KPI strip ×5, and FP-PLAT-03 top-2 labels
2. Renders 2×2 DistributionBar small-multiples grid (4 cells)
3. Renders VizDataTable drill-down with one row per platform
4. Renders PieComposition + TrendLine scaffolds
5. FP-PLAT-02 empty-state preserved
6. Error state on platforms error

**CampaignDashboard.layout.test.tsx (2 tests, +1 new)**

1. Renders dashboard hierarchy and passes axe checks (preserved)
2. _NEW_: Renders cross-platform KpiTile strip alongside legacy CampaignTable + platform legend + top-10 DistributionBar

**CreativeDashboard.test.tsx (9 tests, +6 new on top of 3 existing)**

1. Renders creative leaderboard heading when data is available (preserved)
2. Shows empty state when no creative data (preserved)
3. Shows loading state (preserved)
4. _NEW_: Renders KpiTile ×4 strip when rows populated
5. _NEW_: Renders BubbleScatter with one datum per creative row
6. _NEW_: Renders PieComposition with one slice per unique platform
7. _NEW_: Renders VizDataTable drill-down with one row per creative
8. _NEW_: Preserves 3-branch empty-state — `no_matching_filters` variant
9. _NEW_: Preserves 3-branch empty-state — `no_recent_data` variant

## Verification tails

### vitest

```
 ✓ src/routes/__tests__/CreativeDashboard.test.tsx (9 tests) 211ms
 ✓ src/routes/__tests__/PlatformDashboard.test.tsx (6 tests) 217ms
 ✓ src/state/useDashboardStore.test.ts (14 tests) 1653ms
 ✓ src/routes/__tests__/CampaignDashboard.layout.test.tsx (2 tests) 819ms

 Test Files  4 passed (4)
      Tests  31 passed (31)
   Duration  3.36s
```

### eslint

```
/Users/thristannewman/ADinsights/frontend/src/routes/GoogleAnalyticsDashboardPage.tsx
  98:6  warning  React Hook useMemo has a missing dependency: 'piePalette'
/Users/thristannewman/ADinsights/frontend/src/routes/SearchConsoleDashboardPage.tsx
  92:5  warning  React Hook useMemo has a missing dependency: 'devicePalette'

✖ 2 problems (0 errors, 2 warnings)
```

Warnings are in **S4b scope** (GA4 / Search Console), **not S4a**. Zero errors.

### tsc (S4a scope only)

```
$ npx tsc -p tsconfig.build.json --noEmit 2>&1 | grep -E "PlatformDashboard|CampaignDashboard|CreativeDashboard|platformLabels|combinedAggregates"
(no output — zero errors in S4a files)
```

### vite build

Full-repo `npm run build` currently fails inside `GoogleAnalyticsDashboardPage.tsx` (piePalette identifier renamed mid-edit). Those errors are **entirely in S4b CombinedOther+Web implementer's scope** — that agent is still running (per the session-runner status line) and will rebase over my clean S4a tree when they land.

Confirmed S4a-owned files compile cleanly against `tsconfig.build.json`.

## Status

**GREEN** — all S4a deliverables complete:

- 3 route pages upgraded to viz kit with contract-preserving structure.
- 2 new shared helper modules in `frontend/src/lib/`.
- 31/31 targeted tests pass (`PlatformDashboard`, `CampaignDashboard`, `CreativeDashboard`, `useDashboardStore`).
- 0 lint errors, 0 TypeScript errors in S4a scope.
- Phase 2 contracts FP-PLAT-02, FP-PLAT-03, FP-CAMP-02, FP-CREA-01/03 preserved with explicit file:line citations above.
- Build failures outside S4a scope are awaiting S4b closeout.
