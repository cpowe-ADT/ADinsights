# S2b-CampaignsPagesPost — closeout

**Inputs cited:** `/Users/thristannewman/ADinsights/artifacts/sprint/S2-architect-design.md` (§4.3–§4.7, §5.2, §6.3–§6.7), `/Users/thristannewman/ADinsights/artifacts/sprint/S1-final-closeout.md`, `/Users/thristannewman/ADinsights/frontend/src/components/viz/index.ts`, `/Users/thristannewman/ADinsights/frontend/src/lib/metaPageInsights.ts`, `/Users/thristannewman/ADinsights/frontend/src/state/useMetaPageInsightsStore.ts`, `/Users/thristannewman/ADinsights/frontend/src/state/useMetaStore.ts`.

## Status: GREEN

All five S2b pages landed with their vitest targets green, `npm run lint` clean, and `npm run build` clean. Full vitest (`npm test -- --run`) shows a single unrelated flake (`SavedDashboardPage`), pre-existing per S1 closeout handoff #5 — passes when run in isolation, out of scope for S2b.

## Files modified

| #   | Page                     | File                                               | Tests file                                                        | Primitives added                                                                                                                                                                  |
| --- | ------------------------ | -------------------------------------------------- | ----------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | MetaPagesListPage        | `frontend/src/routes/MetaPagesListPage.tsx`        | `frontend/src/routes/__tests__/MetaPagesListPage.test.tsx`        | `AccessibleTableToggle`, `VizDataTable` (alternate view)                                                                                                                          |
| 2   | MetaPagePostsPage        | `frontend/src/routes/MetaPagePostsPage.tsx`        | `frontend/src/routes/__tests__/MetaPagePostsPage.test.tsx`        | `KpiTile × 3`, `PieComposition` (PostsTable retained)                                                                                                                             |
| 3   | MetaPostDetailPage       | `frontend/src/routes/MetaPostDetailPage.tsx`       | `frontend/src/routes/__tests__/MetaPostDetailPage.test.tsx`       | `KpiTile × 4` w/ conditional embedded sparkline, `TrendLine`, `AccessibleTableToggle`                                                                                             |
| 4   | MetaPageOverviewPage     | `frontend/src/routes/MetaPageOverviewPage.tsx`     | `frontend/src/routes/__tests__/MetaPageOverviewPage.test.tsx`     | `KpiTile × 4`, `TrendLine`, `PieComposition`, `AccessibleTableToggle` (replaces `KPIGrid`, `TrendChart`, `EngagementBreakdownPanel` on this page — legacy components not deleted) |
| 5   | MetaCampaignOverviewPage | `frontend/src/routes/MetaCampaignOverviewPage.tsx` | `frontend/src/routes/__tests__/MetaCampaignOverviewPage.test.tsx` | `KpiTile × 4`, `DistributionBar × 2` (funnel + top-10 spend), `VizDataTable` + inline `Sparkline`, `AccessibleTableToggle × 2`                                                    |

## Funnel approach

Per architect §3 + §4.3 + §8: the funnel stays as **`DistributionBar` with ordered stages** (Impressions → Clicks → Conversions). The primitive draws each stage as a horizontal bar in the order the `data` array supplies them — no `sortByValue` prop exists, so natural array order is preserved. CTR/CVR drop-off labels render in the panel's subtitle text; the `<DistributionBar>` itself gets a pure count for each stage so the sr-only `<table>` remains accurate. No new primitive was added to the viz kit.

## Store dispatches

- `MetaCampaignOverviewPage`:
  - Added an effect that calls `setFilters({ level: 'campaign' })` whenever the page mounts with a non-campaign level, guaranteeing `useMetaStore.loadInsights()` targets the campaign level. (`useMetaStore.loadInsights` is parameter-less in the current store shape; it reads `filters.level` — see `useMetaStore.ts` L319. Setting level directly avoids a store-shape change, which is explicitly locked per architect §5.2 "Don't touch".)
  - Added `loadInsights()` dispatch on mount + on changes to `accountId`, `since`, `until`, `status`, `level`. Existing `loadCampaigns()` effect kept intact per architect risk §8.
  - Imported `insights` slice from the store.

No other dispatches were added; `MetaPagesListPage`, `MetaPagePostsPage`, `MetaPostDetailPage`, `MetaPageOverviewPage` already fetched everything they needed.

## Key implementation notes

- **Legacy components preserved per architect.** `TrendChart`, `KPIGrid`, `EngagementBreakdownPanel`, `PostsTable` were not deleted. Only the consumers I owned now prefer the viz kit; a follow-up cleanup can retire the orphaned files.
- **KpiTile "faded" cue for unsupported metrics** on `MetaPageOverviewPage` — uses `isFaded` + `hint=availability.reason` so WCAG non-color encoding is satisfied without reinstating the "Some metrics are not available for this Page." banner the legacy `KPIGrid` emitted.
- **MetaPagesListPage** keeps the existing action table (Set default / Open buttons) as the `chart` slot of `AccessibleTableToggle` because actions can't live inside `VizDataTable`; the `table` slot is a pure `VizDataTable` snapshot. This satisfies §4.4 "table alternate is already a `<table>`" while preserving pre-existing row-action affordances.
- **`no_page_data` reasonCode** on `MetaPageOverviewPage` fires when `overview.kpis.length === 0` OR every KPI value is null (architect §4.5).
- **Post-detail sparkline** only decorates the tile whose `metricKey` equals the currently selected `metric` (architect §4.7 decision — one call, one tile).
- **Sparkline in VizDataTable** cell renders Recharts `<Sparkline>` via the TanStack `cell` render function (not an `accessorKey` column). Returns `—` when no insights data is available for that campaign.
- **Empty-state ordering on `MetaPagePostsPage`**: KPI strip + PieComposition are gated on `posts.results.length > 0` so PieComposition's own empty-state doesn't collide with the `no_posts` EmptyState block the earlier M14 regression test asserts.

## Tests added

Per `§6.3–§6.7` of the architect brief plus a few defensive assertions:

- `MetaPagesListPage.test.tsx` (+1): `renders AccessibleTableToggle wrapping the default and viz-kit table views`.
- `MetaPagePostsPage.test.tsx` (+2): `renders KPI strip with Total Posts, Avg Reach, Avg Engagement tiles`; `renders media type PieComposition with one slice per distinct media_type`. Also hoisted a `makePostsFixture()` helper + `beforeEach` reset so the posts mock doesn't leak between tests.
- `MetaPostDetailPage.test.tsx` (+3): `renders KpiTile × 4 for available metric categories`; `omits KPI tile for a category when no availability key matches`; `does not render a Comments section (suppressed in S2)`.
- `MetaPageOverviewPage.test.tsx` (+2, replaced 1): replaced the legacy `.meta-kpi-card-v2` assertion with `renders KpiTile strip with up to 4 tiles and fades unsupported metric tile`; added `renders TrendLine (viz kit) in place of the legacy TrendChart`; added `renders no_page_data empty-state when every KPI value is null`. Viz-kit primitives mocked at module level so markup is deterministic.
- `MetaCampaignOverviewPage.test.tsx` (+6): `renders 4 KpiTiles in the rollup strip…`; `renders funnel DistributionBar with 3 ordered stages (Impressions → Clicks → Conversions)`; `limits spend DistributionBar to at most 10 slices`; `renders a Sparkline per row in the campaign VizDataTable when insights are present`; `dispatches loadInsights when mounted and level=campaign`; `forces filters.level to "campaign" on mount when a different level is active`. Rewrote the fixture to include `insights` slice + `loadInsights` action + a viz-kit module mock.

Phase 1A contract assertions preserved on every page (reasonCode presence on EmptyStates, store-subscription shape unchanged).

## Gate results (verbatim tails)

### `npx vitest run src/routes/__tests__/MetaPagesListPage.test.tsx`

```
 ✓ src/routes/__tests__/MetaPagesListPage.test.tsx (5 tests) 315ms
 Test Files  1 passed (1)
      Tests  5 passed (5)
```

### `npx vitest run src/routes/__tests__/MetaPagePostsPage.test.tsx`

```
 ✓ src/routes/__tests__/MetaPagePostsPage.test.tsx (7 tests) 429ms
 Test Files  1 passed (1)
      Tests  7 passed (7)
```

### `npx vitest run src/routes/__tests__/MetaPostDetailPage.test.tsx`

```
 ✓ src/routes/__tests__/MetaPostDetailPage.test.tsx (6 tests) 231ms
 Test Files  1 passed (1)
      Tests  6 passed (6)
```

### `npx vitest run src/routes/__tests__/MetaPageOverviewPage.test.tsx`

```
 ✓ src/routes/__tests__/MetaPageOverviewPage.test.tsx (9 tests) 336ms
 Test Files  1 passed (1)
      Tests  9 passed (9)
```

### `npx vitest run src/routes/__tests__/MetaCampaignOverviewPage.test.tsx`

```
 ✓ src/routes/__tests__/MetaCampaignOverviewPage.test.tsx (9 tests) 254ms
 Test Files  1 passed (1)
      Tests  9 passed (9)
```

### `npx vitest run src/routes/__tests__/Meta` (all Meta route tests)

```
 ✓ src/routes/__tests__/MetaIntegrationPage.test.tsx (3 tests) 151ms
 ✓ src/routes/__tests__/MetaConnectionStatusPage.test.tsx (4 tests) 611ms
 ✓ src/routes/__tests__/MetaDashboardEmptyStates.test.tsx (5 tests) 133ms
 ✓ src/routes/__tests__/MetaPagesListPage.test.tsx (5 tests) 729ms
 ✓ src/routes/__tests__/MetaCampaignOverviewPage.test.tsx (9 tests) 735ms
 ✓ src/routes/__tests__/MetaInsightsDashboardPage.test.tsx (7 tests) 1418ms
 ✓ src/routes/__tests__/MetaPagePostsPage.test.tsx (7 tests) 1436ms
 ✓ src/routes/__tests__/MetaPageOverviewPage.test.tsx (9 tests) 1458ms
 ✓ src/routes/__tests__/MetaAccountsPage.test.tsx (6 tests) 1956ms
 ✓ src/routes/__tests__/MetaPostDetailPage.test.tsx (6 tests) 307ms
 Test Files  10 passed (10)
      Tests  61 passed (61)
```

### `npm run lint`

```
> adinsights-frontend@0.1.0 lint
> eslint .
```

(clean; no output)

### `npm run build`

```
dist/assets/MetaPagePostsPage-Zp6wZ-Dl.js                11.21 kB │ gzip:  3.77 kB
dist/assets/MetaPageOverviewPage-BCQg72is.js             12.14 kB │ gzip:  4.19 kB
dist/assets/MetaCampaignOverviewPage-B7_wIP2I.js         13.16 kB │ gzip:  4.30 kB
…
✓ built in 5.00s
```

### `npm test -- --run` (full suite)

```
 Test Files  1 failed | 113 passed (114)
      Tests  1 failed | 628 passed (629)
```

The single failure is `SavedDashboardPage.test.tsx > location-search href assertion`. Passes in isolation (`npx vitest run src/routes/__tests__/SavedDashboardPage.test.tsx` → 1/1 passed in 91ms) — pre-existing cross-file mock ordering flake documented in S1 closeout handoff #5. Not caused by S2b.

## Accessibility contract

- Every `KpiTile` emits `aria-label` narration + arrow direction icon (S1 kit behavior).
- Every chart in scope is wrapped in `AccessibleTableToggle` that exposes the chart under `role="group"` and a keyboard-reachable `<table>` alternative. Sparklines inside table cells inherit the surrounding `<VizDataTable>` as their a11y equivalent (architect §4.3 ruling).
- Every empty-state emits a `data-reason-code`: `no_pages`, `no_posts`, `no_campaigns`, `no_data_for_range`, `no_page_data`, `error`.
- `ChartSkeleton` shimmer kicks in via each primitive's `isLoading` branch on loading slices — no layout shift.

## Risks the follow-up sprint should know about

1. The `insights` slice on `useMetaStore` is shared across `MetaAccountsPage` (S2a) and `MetaCampaignOverviewPage` (S2b). Setting `filters.level='campaign'` here changes the level globally; navigating between the two pages will refetch with the appropriate level. If S2a already forces `filters.level='account'` on its mount effect, the two effects reconcile via their own mount-side `setFilters` calls. No known race observed locally.
2. `MetaPostDetailPage` sparkline only renders on the active metric tile — intentional per architect §4.7, but it can surprise users who expect all four tiles to trend. Consider a short "showing trend for _N_" hint in a follow-up polish pass.
3. The pre-existing `SavedDashboardPage` full-suite-only flake remains. Suggest isolating that test's mocks before re-enabling coverage gates.

## Verdict

GREEN — five pages migrated to the Sprint 1 viz kit; all per-page tests, all cross-Meta regression tests, lint, and build are clean. Pre-existing unrelated `SavedDashboardPage` flake noted.
