# S3a — Core Analytics (Overview / Campaigns / Search)

Inputs: `/Users/thristannewman/ADinsights/artifacts/sprint/S3-architect-design.md` §2/§4/§6.2/§6.3/§8.1; Sprint 1 viz kit (`frontend/src/components/viz/`); Phase 1B contracts in `docs/project/api-contract-changelog.md`.

## Files Modified / Created

| File | Kind | Purpose |
|------|------|---------|
| `frontend/src/lib/googleAdsAggregates.ts` | CREATED | Shared helper module: KPIs, bubble points, top-spend bars, trend series, channel pie, severity/tone derivation |
| `frontend/src/lib/googleAdsAggregates.test.ts` | CREATED | 26 unit tests covering every exported helper |
| `frontend/src/components/google-ads/workspace/WorkspaceKpiStrip.tsx` | REWRITTEN | 4-tile `KpiTile` strip (Cost/Conv/CPA/ROAS) — IS% tile removed per architect §4 |
| `frontend/src/components/google-ads/workspace/__tests__/WorkspaceKpiStrip.test.tsx` | CREATED | Tile count, loading skeleton, error role=alert, reasonCode tagging |
| `frontend/src/components/google-ads/workspace/tab-sections/OverviewTabSection.tsx` | REWRITTEN | KpiTile×4 + dual-axis TrendLine + PieComposition (channel cost, derived from campaigns cache) |
| `frontend/src/components/google-ads/workspace/tab-sections/CampaignsTabSection.tsx` | REWRITTEN | KpiTile×4 + BubbleScatter (cost/conv-rate/impressions) + DistributionBar top-10 (sparkline fallback) + severity chips |
| `frontend/src/components/google-ads/workspace/tab-sections/SearchTabSection.tsx` | CREATED | Mode-aware (keywords/search_terms/insights); KpiTile×3 + BubbleScatter QS-vs-CPC + DistributionBar top search terms |
| `frontend/src/routes/google-ads/GoogleAdsWorkspacePage.tsx` | EDITED | Wires SearchTabSection; prefetches campaigns (overview) and search_terms (keywords) via `loadTab` |
| `frontend/src/routes/google-ads/GoogleAdsExecutivePage.tsx` | REWRITTEN | Legacy-mode viz-kit equivalent; 4 KPI tiles + dual-axis TrendLine + movers table |
| `frontend/src/routes/google-ads/GoogleAdsCampaignsPage.tsx` | REWRITTEN | Dropped `GoogleAdsDataTablePage` wrapper; mirrors CampaignsTabSection layout |
| `frontend/src/routes/google-ads/GoogleAdsKeywordsPage.tsx` | REWRITTEN | Dropped `GoogleAdsDataTablePage` wrapper; mirrors SearchTabSection |
| `frontend/src/routes/google-ads/__tests__/GoogleAdsExecutivePage.test.tsx` | UPDATED | Asserts 4-tile KPI grid (no IS%), dual-axis TrendLine aria-label, movers |
| `frontend/src/routes/google-ads/__tests__/GoogleAdsCampaignsPage.test.tsx` | UPDATED | KPI strip, BubbleScatter, top-10 bar, severity chips via `data-status-tone`, EmptyState reasonCode |
| `frontend/src/routes/google-ads/__tests__/GoogleAdsKeywordsPage.test.tsx` | UPDATED | KPI strip, QS-vs-CPC bubble, top-10 terms bar, mode toggle re-fetch |

## Helpers Shipped (`googleAdsAggregates.ts`)

Exports:
- Type-safe row interfaces: `GoogleAdsCampaignRow`, `GoogleAdsKeywordRow`, `GoogleAdsSearchTermRow`
- KPI rollups: `rollupOverviewKpis`, `rollupCampaignKpis`, `rollupKeywordKpis`
- Trend/pie derivations: `deriveTrendSeries`, `buildChannelPie`
- Scatter/bar builders: `buildCampaignBubblePoints`, `buildQsCpcBubblePoints`, `buildTopSpendBars`, `topSearchTermsByConv`
- Enum mappers: `channelTypeToBubbleShape`, `matchTypeToBubbleShape`, `deriveChangeSeverity`, `deriveCampaignStatusTone`
- Math utils: `toNumber`, `safeDivide`

## `WorkspaceKpiStrip.tsx` Props

```ts
type Props = {
  overview: GoogleAdsExecutiveResponse | null;
  isLoading?: boolean;
  errorMessage?: string;
};
```

Renders exactly 4 `KpiTile`s with `reasonCode="no_data_for_range"` when the metric is null. IS% is intentionally absent (architect §4: not in backend payload).

## Tests Added

- `googleAdsAggregates.test.ts`: 26 tests (toNumber coercion, safeDivide zero-guard, KPI rollups, trend derivation, pie/scatter/bar builders, shape mappers, severity + tone derivation)
- `WorkspaceKpiStrip.test.tsx`: 4 tests (tile count, loading skeleton, error surface, reasonCode tagging)
- Updated page tests (Executive, Campaigns, Keywords): chart aria-label + status chip + EmptyState reasonCode coverage

## Gate Results

### Targeted vitest

```
 Test Files  17 passed (17)
      Tests  91 passed (91)
   Start at  11:44:09
   Duration  19.08s
```

### Lint (`npm run lint`)

```
> adinsights-frontend@0.1.0 lint
> eslint .
```
Clean — no errors, no warnings.

### Build (`npm run build`)

```
dist/assets/GoogleAdsWorkspacePage-Dp4wpFJq.js            31.06 kB │ gzip:  8.05 kB
dist/assets/chartTheme-7qXzEHi3.js                       271.13 kB │ gzip: 85.39 kB
dist/assets/index-CAmXMTWb.js                            274.63 kB │ gzip: 87.91 kB
✓ built in 6.79s
```
tsc + vite build both succeed.

## Architect Gap Strategies — Landed and Cited

1. **IS% tile deferred (architect §4)** — `WorkspaceKpiStrip.tsx:71-96` renders only 4 tiles (Cost/Conv/CPA/ROAS); no IS% slot. `GoogleAdsExecutivePage.tsx:104-108` likewise. Executive test asserts absence: `GoogleAdsExecutivePage.test.tsx:60`.
2. **Per-campaign daily-series unavailable → DistributionBar top-10 fallback (architect §4/§6.2)** — `CampaignsTabSection.tsx:122-131` and `GoogleAdsCampaignsPage.tsx:148-156` replace the sparkline-grid plan with a top-10 `DistributionBar`. Aggregate helper: `googleAdsAggregates.ts:buildTopSpendBars`.
3. **Channel pie derived from campaigns cache (architect §4)** — `OverviewTabSection.tsx` consumes `campaignRows` prop and feeds `buildChannelPie` (`googleAdsAggregates.ts:buildChannelPie`) for PieComposition. Workspace prefetch wired in `GoogleAdsWorkspacePage.tsx:116-131`: when `activeTab === 'overview'` the hook's `loadTab('campaigns', searchMode)` is kicked off so the pie has data by the time Overview renders.
4. **BubbleShape degradation (architect §6.2 vs kit API)** — Kit only exports circle/triangle/square, so `channelTypeToBubbleShape` in `googleAdsAggregates.ts` maps SEARCH→circle, DISPLAY→triangle, and VIDEO/PERFORMANCE_MAX/SHOPPING→square; documented inline.

## Phase 1B Contract Preservation

- Saved-view `client_id` restore path untouched in `GoogleAdsWorkspacePage.tsx` (existing `handleSavedViewSelect` flow retained; workspace test `restores client_id from saved view …` still passes).
- Reactive filters: `GoogleAdsExecutivePage.tsx:33` and `GoogleAdsCampaignsPage.tsx:51` subscribe to `filters` via `useDashboardStore`; effects re-fetch on change (NB1 regression avoided).
- Filter-bar unification: no FilterBar edits; pages consume filters through the shared store.

## Boundaries Respected

- No edits to viz-kit files (`src/components/viz/*`).
- No edits to `GoogleAdsDataTablePage.tsx`.
- No changes to `useGoogleAdsWorkspaceData.ts` hook signature (added a defensive guard at call-site only: `GoogleAdsWorkspacePage.tsx:116` checks `typeof loadTab === 'function'` before invoking prefetch).
- No backend file edits.
- S3b/S3c-owned tab sections untouched.

## Status: GREEN

All owned scope delivered. Targeted vitest (91/91), lint, and full production build all pass.
