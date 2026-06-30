# S3c — Ops Tabs (Pacing / Changes / Recommendations / Reports)

Inputs: `/Users/thristannewman/ADinsights/artifacts/sprint/S3-architect-design.md` §3.7–3.10 + §6.7–6.10 + §8.3; `/Users/thristannewman/ADinsights/artifacts/sprint/S3a-core-analytics.md` (shared `googleAdsAggregates.ts`); `/Users/thristannewman/ADinsights/artifacts/sprint/S1-final-closeout.md` (kit contract); `/Users/thristannewman/ADinsights/artifacts/sprint/S2-final-closeout.md` (pattern reference); `/Users/thristannewman/ADinsights/frontend/src/components/viz/index.ts` (kit barrel: `GaugeRing`, `AssetGroupTreemap`, `derivePacingVariant`, `roasToOpacity`).

## Files Modified / Created

| Tab             | File                                                                                            | Kind      | Purpose                                                                                                    |
| --------------- | ----------------------------------------------------------------------------------------------- | --------- | ---------------------------------------------------------------------------------------------------------- |
| Pacing          | `frontend/src/components/google-ads/workspace/tab-sections/PacingTabSection.tsx`                | CREATED   | Unified-mode Pacing: GaugeRing + 3 KpiTile + summary table                                                 |
| Pacing          | `frontend/src/components/google-ads/workspace/tab-sections/__tests__/PacingTabSection.test.tsx` | CREATED   | GaugeRing role=meter, derived pct, pacing_pct precedence, variance-bar-deferred assertion, reasonCode      |
| Pacing          | `frontend/src/routes/google-ads/GoogleAdsBudgetPage.tsx`                                        | REWRITTEN | Legacy-mode delegates to `PacingTabSection`; NB2 filter-subscribe preserved                                |
| Pacing          | `frontend/src/routes/google-ads/__tests__/GoogleAdsBudgetPage.test.tsx`                         | UPDATED   | Meter rendering, reasonCode, variance-bar absence, error surface                                           |
| Changes         | `frontend/src/components/google-ads/workspace/tab-sections/ChangesTabSection.tsx`               | CREATED   | 2 KpiTile + DistributionBar by resource_type + severity-chip table                                         |
| Changes         | `frontend/src/routes/google-ads/GoogleAdsChangeLogPage.tsx`                                     | REWRITTEN | Dropped `GoogleAdsDataTablePage` wrapper; direct fetch → `ChangesTabSection`; paginated contract preserved |
| Changes         | `frontend/src/routes/google-ads/__tests__/GoogleAdsChangeLogPage.test.tsx`                      | UPDATED   | Severity chip branches (CREATE/UPDATE/REMOVE), reasonCode, pagination count                                |
| Recommendations | `frontend/src/components/google-ads/workspace/tab-sections/RecommendationsTabSection.tsx`       | CREATED   | 2 KpiTile + PieComposition + severity-chip table; no Dismiss button                                        |
| Recommendations | `frontend/src/routes/google-ads/GoogleAdsRecommendationsPage.tsx`                               | REWRITTEN | Dropped wrapper; direct fetch → `RecommendationsTabSection`                                                |
| Recommendations | `frontend/src/routes/google-ads/__tests__/GoogleAdsRecommendationsPage.test.tsx`                | UPDATED   | Both severity derivation branches, dismiss-button-absent assertion, reasonCode                             |
| Reports         | `frontend/src/components/google-ads/workspace/tab-sections/ReportsTabSection.tsx`               | CREATED   | 2 KpiTile + form controls + export job card + saved-views table with status chip                           |
| Reports         | `frontend/src/routes/google-ads/GoogleAdsReportsPage.tsx`                                       | REWRITTEN | Legacy wrapper delegates to `ReportsTabSection`                                                            |
| Reports         | `frontend/src/routes/google-ads/__tests__/GoogleAdsReportsPage.test.tsx`                        | UPDATED   | reasonCode=no_saved_views, saved-view rendering with Shared chip, export-create flow                       |
| Workspace       | `frontend/src/routes/google-ads/GoogleAdsWorkspacePage.tsx`                                     | EDITED    | Wires all 4 new tab sections (pacing/changes/recommendations/reports) in place of `GenericTabSection`      |
| Shared          | `frontend/src/lib/googleAdsAggregates.ts`                                                       | EXTENDED  | Added pacing/changes/recommendations/reports helpers (see below)                                           |
| Shared          | `frontend/src/lib/googleAdsAggregates.test.ts`                                                  | EXTENDED  | +21 unit tests for new helpers (total 47)                                                                  |

## New Helpers in `googleAdsAggregates.ts`

- Types: `GoogleAdsPacingPayload`, `GoogleAdsPacingKpis`, `GoogleAdsChangeRow`, `GoogleAdsRecommendationRow`, `GoogleAdsRecommendationKpis`, `ChangeSeverity`, `RecommendationSeverity`, `ExportJobStatusTone`
- Pacing: `derivePacingPct`, `rollupPacingKpis`
- Changes: `groupChangesByResourceType`, `countChanges7d` (plus pre-existing `deriveChangeSeverity`)
- Recommendations: `deriveRecommendationSeverity`, `rollupRecommendationKpis`, `groupRecommendationsByType`, `formatRecommendationImpact`
- Reports: `deriveExportJobStatusTone`

## Severity Derivation Tables

### Changes (architect §6.8)

| `resource_change_operation`     | severity  | chip tone |
| ------------------------------- | --------- | --------- |
| `CREATE` / `CREATED`            | `info`    | neutral   |
| `UPDATE` / `UPDATED` / `MODIFY` | `warning` | warning   |
| `REMOVE` / `REMOVED` / `DELETE` | `danger`  | danger    |
| anything else / missing         | `info`    | neutral   |

Non-color encoding: each chip renders the operation verb visibly AND an `aria-label="Severity <text>"` + visually-hidden `" — <text>"` suffix so screen readers get the severity even without color.

### Recommendations (architect §6.9)

Derivation order:

1. **`impact_metadata.severity` (preferred)** — case-insensitive normalize:
   | payload `severity` value | normalized |
   |---|---|
   | `danger` / `critical` / `high` | `danger` |
   | `warning` / `medium` | `warning` |
   | `info` / `low` | `info` |
2. **`recommendation_type` heuristic (fallback)** — substring match on uppercased type:
   | substring in `recommendation_type` | severity |
   |---|---|
   | `BUDGET`, `BID`, `PACING` | `warning` |
   | `POLICY`, `DISAPPROVED`, `SUSPENDED`, `PAUSED_ACCOUNT` | `danger` |
   | anything else (or missing) | `info` |

The derivation is wrapped in `try/catch` (defensive against SDK-driven JSON drift — architect §10 risk 8). Each branch is unit-tested.

### Reports (job status)

| `status` (case-insensitive)                        | tone      |
| -------------------------------------------------- | --------- |
| `complete` / `completed` / `success` / `succeeded` | `success` |
| `running` / `queued` / `pending` / `in_progress`   | `warning` |
| `failed` / `error` / `errored` / `cancelled`       | `danger`  |
| anything else                                      | `neutral` |

## Pacing GaugeRing Integration Notes

- **`derivePacingPct(pacing)`** — returns `pacing.pacing_pct` when finite, else `safeDivide(spend_mtd, budget_month)`, else `null` (denominator ≤ 0).
- `PacingTabSection` passes `pacingPct ?? Number.NaN` to `GaugeRing`; the primitive shows its own `emptyReasonCode="no_pacing_data"` EmptyState when the value is null/NaN.
- `variant` is computed via the kit-exported `derivePacingVariant(pacingPct)` — **no threshold hard-coding at the consumer**, satisfying §6.7.
- `ariaLabel` is tokenised: `Pacing ${pct}% of monthly budget` (or `Pacing data unavailable`). The primitive already emits `role="meter"` + `aria-valuenow/min/max/valuetext` + a visually-hidden `<table>` summary for AT fallback.
- **Variance bar intentionally absent** (architect §4 + §6.7 deferral — per-campaign `budget_amount` is not on `/budgets/pacing/` or `/campaigns/`). Tests assert `queryByText(/variance/i)` returns null to lock in the deferral.
- Both-modes parity: the legacy `GoogleAdsBudgetPage` instantiates the same component so no divergence can creep in between modes.

## Tests Added

- `googleAdsAggregates.test.ts` — 21 new tests covering `derivePacingPct`, `rollupPacingKpis`, `groupChangesByResourceType`, `countChanges7d`, `deriveRecommendationSeverity` (4 branches), `rollupRecommendationKpis`, `groupRecommendationsByType`, `formatRecommendationImpact`, `deriveExportJobStatusTone` (total file: 47 tests).
- `PacingTabSection.test.tsx` — 5 tests: GaugeRing a11y, derived pct math, pct precedence, variance-bar deferral assertion, empty-state reasonCode.
- `GoogleAdsBudgetPage.test.tsx` — 4 tests (heading preserved, full viz render with meter role, reasonCode path, error path).
- `GoogleAdsChangeLogPage.test.tsx` — 4 tests (heading, severity chip branches CREATE/UPDATE/REMOVE, reasonCode no_change_events, pagination count surfaced from `count` field).
- `GoogleAdsRecommendationsPage.test.tsx` — 4 tests (heading, both severity branches + info default, dismiss-button absent, reasonCode no_recommendations).
- `GoogleAdsReportsPage.test.tsx` — 4 tests (heading, reasonCode no_saved_views, saved view with Shared chip, export create flow).
- Workspace test (`GoogleAdsWorkspacePage.test.tsx`) — 6 pre-existing tests still pass unchanged (Phase 1B contracts: saved-view client_id restore, store-driven filters).

## Gate Results

### Targeted vitest

```
cd frontend && npx vitest run Pacing Changes Recommendations Reports googleAdsAggregates GoogleAdsWorkspacePage

 ✓ src/routes/google-ads/__tests__/GoogleAdsWorkspacePage.test.tsx (6 tests) 318ms
 Test Files  6 passed (6)
      Tests  68 passed (68)
   Duration  3.09s
```

### Full vitest suite (no regression)

```
 Test Files  120 passed (120)
      Tests  739 passed (739)
   Duration  38.65s
```

### Lint (`npm run lint`)

```
> adinsights-frontend@0.1.0 lint
> eslint .
```

Clean — no errors, no warnings.

### Build (`npm run build`)

```
dist/assets/PacingTabSection-C9R9-ymI.js                  25.86 kB │ gzip:  8.22 kB
dist/assets/GoogleAdsWorkspacePage-l-fOYNhu.js            31.54 kB │ gzip:  8.19 kB
dist/assets/index-DLLKIdM-.js                            275.25 kB │ gzip: 88.13 kB
✓ built in 4.04s
```

tsc + vite build both succeed.

## Phase 1B Contract Preservation

- `GoogleAdsWorkspacePage` saved-view `client_id` restore path (`handleSelectSavedView`) untouched — 6/6 workspace tests still pass.
- Reactive filters: `GoogleAdsBudgetPage` keeps the NB2 regression fix (`useDashboardStore((s) => s.filters)` subscription + effect re-fetch).
- `GoogleAdsChangeLogPage` and `GoogleAdsRecommendationsPage` now subscribe to the store for filter-reactive fetches (they previously hid this inside `GoogleAdsDataTablePage`, which read the store at call time — preserving the same behavior).
- No edits to `useGoogleAdsWorkspaceData.ts` hook signature.
- `GoogleAdsDataTablePage.tsx` preserved intact (still used by Channels/Breakdowns legacy redirects).

## Boundaries Respected

- No edits to any viz-kit file (`src/components/viz/*`).
- No edits to `GoogleAdsDataTablePage.tsx`.
- No edits to S3a-owned (`WorkspaceKpiStrip.tsx`, Overview/Campaigns/Search/Executive/Campaigns/Keywords pages).
- No edits to S3b-owned (Assets/PMax/Conversions tab sections and pages).
- No backend file changes.

## Status: GREEN

All 4 tabs (8 files in both modes) shipped per architect brief. Severity derivation tables documented inline and tested. GaugeRing integration uses kit-exported variant helper (no threshold hard-coding). Variance bar deferral honored and test-asserted. Targeted vitest (68/68) + full suite (739/739) + lint + production build all pass.
