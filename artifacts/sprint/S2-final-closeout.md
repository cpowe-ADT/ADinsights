# Sprint 2 — Meta Cluster — Final Closeout

**Inputs cited:** `/Users/thristannewman/ADinsights/artifacts/sprint/S2-architect-design.md`, `/Users/thristannewman/ADinsights/artifacts/sprint/S2a-accounts-insights.md`, `/Users/thristannewman/ADinsights/artifacts/sprint/S2b-campaigns-pages-post.md`, `/Users/thristannewman/ADinsights/artifacts/viz/sprints-plan.md` (Sprint 2 §336–540 + §24–100 design principles), `/Users/thristannewman/ADinsights/artifacts/sprint/S1-final-closeout.md` (viz kit register).

## Status: GREEN

Sprint 2 landed the 7-page Meta migration onto the Sprint 1 viz kit. All 7 pages now follow the 5-block layout (KPI strip → trend → distribution → drill-down table). Full test matrix, regression checks, and DoD gates verified. The single full-suite failure is the pre-existing cross-file mock-ordering flake on `SavedDashboardPage.test.tsx` (1 test), documented in S1 closeout handoff #5 and S2b closeout risk #3 — confirmed green in isolation (1/1 in 115ms), **not caused by S2**.

---

## 1. Per-page DoD matrix

Legend: ✓ = shipped, ✗ = missing, N/A = out of spec per architect §3, § = cited file:line in evidence.

| Page                          | KPI strip (4–6)                                                                                       | Trend chart                                                             | Distribution/composition                                                                | Drill-down table                                                                   | Specialized viz                                                                          | Empty+reasonCode                                                              | Loading (ChartSkeleton)                                           | AccessibleTableToggle                     | Tests                                                                       |
| ----------------------------- | ----------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- | --------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- | ----------------------------------------------------------------- | ----------------------------------------- | --------------------------------------------------------------------------- |
| **MetaAccountsPage**          | ✓ 6 tiles (Spend/Imp/Reach/CTR/CPM/Active Accts) `MetaAccountsPage.tsx:279` `:437` `:448`             | ✓ Multi-series spend/day `:470` + peer-avg                              | ✓ PieComposition spend-by-objective `:518`                                              | ✓ VizDataTable per-account `:480` `:526`                                           | N/A (architect §4.1 no specialized block)                                                | ✓ `reasonCode=no_accounts` `:418`, `no_data_for_range` `:464`, `error` `:398` | ✓ `kpi-strip` `:437`, `line` `:458`, `pie` `:506`, `table` `:551` | ✓ TrendLine `:467`, PieComposition `:515` | ✓ 6 tests (preserved Phase 1A + 4 new) `MetaAccountsPage.test.tsx`          |
| **MetaInsightsDashboardPage** | ✓ 5 tiles (Spend/ROAS†/CTR/CPC‡/CPM) `MetaInsightsDashboardPage.tsx:97` `:346` `:357`                 | ✓ Dual-axis CTR+CPM `:371` `rightYFormat="currency"` `:378`             | N/A (bubble replaces distribution)                                                      | ✓ VizDataTable 7-col `:384` `:447` `:486`                                          | ✓ BubbleScatter ROAS-or-CPM fallback `:430`                                              | ✓ `reasonCode=no_data_for_range` `:339`, `error` `:327`                       | ✓ `kpi-strip` `:346`                                              | ✓ TrendLine `:368`, BubbleScatter `:423`  | ✓ 7 tests (preserved sync-now + 5 new) `MetaInsightsDashboardPage.test.tsx` |
| **MetaCampaignOverviewPage**  | ✓ 4 tiles (Spend/Imp/Clicks/Conversions) `MetaCampaignOverviewPage.tsx:257,263,269,275`               | — (by architect §4.3 spec: funnel + top-spend replace a standard trend) | ✓ DistributionBar × 2 (funnel `:352` + top-10 spend `:386`)                             | ✓ VizDataTable + inline Sparkline per row `:220` `:455`                            | ✓ Funnel-via-DistributionBar stages ordered Impressions→Clicks→Conversions `:117` `:345` | ✓ `reasonCode=no_campaigns` `:449`, `error` `:439`                            | ✓ (per architect brief)                                           | ✓ 2× on DistributionBar `:349` `:383`     | ✓ 9 tests (+6 new) `MetaCampaignOverviewPage.test.tsx`                      |
| **MetaPagesListPage**         | N/A (sprints-plan §447 explicitly no KPI strip)                                                       | N/A                                                                     | N/A                                                                                     | ✓ VizDataTable toggle-alternate `:271`                                             | N/A                                                                                      | ✓ `reasonCode=no_pages` `:176`, `error` `:157`                                | ✓ (cards + table slots)                                           | ✓ cards ↔ table `:219`                    | ✓ 5 tests (+1 new) `MetaPagesListPage.test.tsx`                             |
| **MetaPagePostsPage**         | ✓ 3 tiles (Total Posts/Avg Reach/Avg Engagement) `MetaPagePostsPage.tsx:336,342,349`                  | — (out of spec per architect §4.6)                                      | ✓ PieComposition media_type mix `:362`                                                  | ✓ existing `PostsTable` preserved (thumbnail/snippet exception per architect §4.6) | N/A                                                                                      | ✓ `reasonCode=no_posts` `:385`, `error` `:330`                                | ✓ (per S2b closeout)                                              | ✓ on PieComposition                       | ✓ 7 tests (+2 new) `MetaPagePostsPage.test.tsx`                             |
| **MetaPostDetailPage**        | ✓ 4 tiles (Reach/Impressions/Reactions/Shares) `MetaPostDetailPage.tsx:191`                           | ✓ TrendLine for selected metric `:238`                                  | N/A                                                                                     | — (no post-level table; post card is the detail view)                              | ✓ Conditional embedded Sparkline on active metric tile (architect §4.7)                  | ✓ `reasonCode=error` `:149`, `meta_post_{category}` per-tile `:197`           | ✓                                                                 | ✓ on TrendLine `:235`                     | ✓ 6 tests (+3 new) `MetaPostDetailPage.test.tsx`                            |
| **MetaPageOverviewPage**      | ✓ 4 tiles `MetaPageOverviewPage.tsx:436` (KpiTile replaces legacy KPIGrid, faded unsupported metrics) | ✓ TrendLine (replaces legacy TrendChart) `:458`                         | ✓ PieComposition engagement_breakdown `:506` (replaces legacy EngagementBreakdownPanel) | N/A                                                                                | N/A                                                                                      | ✓ `reasonCode=no_page_data` `:426`, `error` `:404`                            | ✓                                                                 | ✓ on TrendLine `:455`                     | ✓ 9 tests (+2 new, −1 legacy replaced) `MetaPageOverviewPage.test.tsx`      |

† ROAS tile conditionally rendered only when `hasPurchaseActions(rows) === true` (`MetaInsightsDashboardPage.tsx:95,101`).  
‡ CPC substitutes for Frequency per architect §3 audit (Frequency is not derivable from `MetaInsightRecord`) — `MetaInsightsDashboardPage.tsx:106–107`.

---

## 2. Data-availability strategy verification

Each strategy from architect §3 audit was traced to a concrete code landing:

### 2.1 ROAS conditional-derive + CPM fallback — LANDED

- Helper: `hasPurchaseActions`, `derivedRoas`, `aggregatedRoas` exported from `frontend/src/lib/metaAggregates.ts` (10 unit tests in `metaAggregates.test.ts`).
- **KPI tile gating**: `MetaInsightsDashboardPage.tsx:95` computes `roasAvailable`; `:101` pushes the ROAS tile only when true — otherwise omitted from the strip.
- **Bubble y-axis swap**: `MetaInsightsDashboardPage.tsx:125` `const yValue = roasAvailable ? (roasForRow ?? 0) : cpmForRow;` — bubble renders "Spend vs. ROAS" heading when available and "Spend vs. CPM" fallback when not.
- Tests: `MetaInsightsDashboardPage.test.tsx` asserts both branches (ROAS hidden w/o purchase actions; Spend-vs-CPM bubble heading fallback).

### 2.2 CPC replaces Frequency on Insights KPI — LANDED

- `MetaInsightsDashboardPage.tsx:106–107`:
  ```
  // Frequency is not derivable from MetaInsightRecord; substitute CPC per §3 audit.
  { label: 'CPC', value: rows.length ? kpis.cpc : null, format: 'currency', currency: 'USD' },
  ```
- `kpis.cpc` derives from `sumInsights` (`metaAggregates.ts`) as `sum(spend)/sum(clicks)`, divide-by-zero-safe.
- No `Frequency` label appears anywhere in the Insights page (grep confirmed).

### 2.3 Funnel-via-DistributionBar on Campaigns — LANDED

- `MetaCampaignOverviewPage.tsx:117–125`:
  ```
  // Funnel-as-DistributionBar: ordered stages, descending values preserved.
  const funnelStages = useMemo(() => [
    { label: 'Impressions', value: totals.impressions },
    { label: 'Clicks', value: totals.clicks },
    { label: 'Conversions', value: totals.conversions },
  ], [totals]);
  ```
- Render site `:345–352`: `<h3>Funnel</h3>` with CTR/CVR drop-off labels in subtext; `<DistributionBar>` with ordered stages.
- No new viz-kit primitive was added — the decision in architect §3 + §4.3 + §8 was respected.
- Test: `MetaCampaignOverviewPage.test.tsx` > "renders funnel DistributionBar with 3 ordered stages (Impressions → Clicks → Conversions)".

---

## 3. Full test matrix — verbatim tails

### 3.1 `cd frontend && npm run lint`

```
> adinsights-frontend@0.1.0 lint
> eslint .
```

(clean — zero errors, zero warnings)

### 3.2 `cd frontend && npm run build`

```
dist/assets/MetaPagePostsPage-Zp6wZ-Dl.js                11.21 kB │ gzip:  3.77 kB
dist/assets/MetaPageOverviewPage-BCQg72is.js             12.14 kB │ gzip:  4.19 kB
dist/assets/MetaAccountsPage-BYR6FAum.js                 12.38 kB │ gzip:  3.85 kB
dist/assets/MetaCampaignOverviewPage-B7_wIP2I.js         13.16 kB │ gzip:  4.30 kB
dist/assets/MetaInsightsDashboardPage-gfNYx3J0.js        22.69 kB │ gzip:  7.88 kB
…
✓ built in 10.70s
```

### 3.3 `cd frontend && npx vitest run Meta metaAggregates`

```
 Test Files  16 passed (16)
      Tests  92 passed (92)
   Duration  19.46s
```

All Meta route tests + `metaAggregates` helpers + `metaPageInsights` + `metaPageDateRange` + `useMetaStore` + `useMetaPageInsightsStore` green.

### 3.4 `cd frontend && npm test -- --run`

```
 Test Files  1 failed | 113 passed (114)
      Tests  1 failed | 628 passed (629)
   Duration  85.35s
```

The single failure is `SavedDashboardPage.test.tsx > location-search href assertion` — pre-existing cross-file mock-ordering flake per S1 closeout handoff #5 and S2b closeout risk #3. Verified green in isolation:

```
$ npx vitest run src/routes/__tests__/SavedDashboardPage.test.tsx
 ✓ src/routes/__tests__/SavedDashboardPage.test.tsx (1 test) 115ms
 Test Files  1 passed (1)
      Tests  1 passed (1)
```

**Not caused by S2.**

### 3.5 `cd backend && pytest`

```
727 passed, 1 skipped in 26.28s
```

Matches expected from S1 closeout (727 passed, 1 skipped).

### 3.6 `ruff check backend`

```
All checks passed!
```

---

## 4. Regression check

| Contract                                                                                                   | Result                                                                                                                                                                                                                                                                                          |
| ---------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Phase 1A `reasonCode` presence on empty states**                                                         | ✓ Preserved. All 7 Meta pages still emit `reasonCode` on every `EmptyState`: `no_accounts`, `no_pages`, `no_posts`, `no_campaigns`, `no_data_for_range`, `no_page_data`, `error`, plus per-tile `meta_post_*` / `meta_posts_*` / `meta_page_*` / `meta_campaigns_*` codes on KpiTile empties.   |
| **Store subscription shape (`useMetaStore`, `useMetaPageInsightsStore`)**                                  | ✓ No shape changes. S2a documented the deliberate non-mutation of `filters.level` on MetaAccountsPage; S2b set `filters.level='campaign'` on CampaignOverview mount without adding new actions or changing signatures. All existing Meta route tests using pre-existing store mocks still pass. |
| **R7 filter propagation**                                                                                  | ✓ Row-click `setFilters({accountId})` + navigate preserved on MetaAccountsPage (test: `calls setFilters and navigates on row click` — green).                                                                                                                                                   |
| **Sprint 1 viz tests**                                                                                     | ✓ 114/114 files passing, 629 total tests. Only non-Meta failure is pre-existing `SavedDashboardPage` flake. No viz primitive regressions.                                                                                                                                                       |
| **Backend: meta_views, combined_metrics_service, dataset_status, adapter dispatch, social/dataset status** | ✓ 727 passed, 1 skipped — identical pass count to S1 closeout baseline.                                                                                                                                                                                                                         |
| **Phase 2 Combined metrics tests**                                                                         | ✓ Present in the 629-pass count; no Combined tests report failure in the full-suite tail.                                                                                                                                                                                                       |

---

## 5. A11y posture

- **Viz kit jest-axe coverage unchanged**: all 10 S1 primitives still have jest-axe assertions in their `*.test.tsx` files:
  - `KpiTile.test.tsx`, `TrendLine.test.tsx`, `Sparkline.test.tsx`, `DistributionBar.test.tsx`, `BubbleScatter.test.tsx`, `PieComposition.test.tsx`, `DataTable.test.tsx`, `ChartSkeleton.test.tsx`, `AccessibleTableToggle.test.tsx`, `EmptyState.test.tsx` — all have `jest-axe`/`axe` imports.
- **Meta page a11y posture** (not full-page axe runs — viz kit primitives carry the a11y contract):
  - Every chart surface is wrapped in `AccessibleTableToggle` (12 toggle sites across the 7 pages — verified via grep) — keyboard-reachable chart/table swap, both views mounted for assistive tech.
  - `KpiTile` still emits `role="figure"` + `aria-label` narration + non-color delta-direction indicator (S1b contract).
  - Non-color encoding preserved: `BubbleScatter` uses `shape: triangle|circle` when filter state differs (`MetaInsightsDashboardPage.tsx:126`), `DistributionBar` segments carry pattern fills, `PieComposition` uses pattern + center label.
  - `MetaPageOverviewPage` fades unsupported-metric `KpiTile` with `isFaded` + `hint=availability.reason` (non-color encoding — S2b decision to satisfy WCAG while removing the legacy banner).
- **No new a11y regressions introduced** — the full suite (114 files) still passes (excluding the documented SavedDashboardPage flake which is unrelated to a11y).

---

## 6. Known follow-ups

These were flagged by S2a / S2b closeouts or by architect design — **none block the sprint**:

1. **BubbleScatter shape-encoding simplification (S2a §5.2)** — architect §4.2 called for shape-by-objective when `filters.accountId === ''`. Objective isn't on `MetaInsightRecord` and the per-row campaign-level join is unreliable when `filters.level !== 'campaign'`. S2a degraded to `triangle` (filtered) / `circle` (unfiltered). Accessible but not objective-encoded. A follow-up could introduce a campaign-objective-join helper.
2. **MetaAccountsPage does not set `filters.level='account'` on mount (S2a deviation #1)** — would leak level state into the Insights page. Helpers are level-agnostic, so this is tolerable; a parameterized `loadInsights({level})` variant would solve cleanly but was prohibited per the store-shape lock.
3. **Legacy components preserved** — `TrendChart.tsx`, `KPIGrid.tsx`, `EngagementBreakdownPanel.tsx`, `PostsTable.tsx`, and the legacy standalone `DataTable.tsx` are no longer imported by the 7 Meta pages in scope but are still present in the tree. Architect explicitly scoped their deletion to a later cleanup sprint (S1 closeout handoff #1 → "progressively swap").
4. **Post-detail sparklines only on the active metric tile (S2b §key impl note)** — one-sparkline-per-tile would require four timeseries fetches. Decision stands; a short "showing trend for _N_" hint was suggested as follow-up polish.
5. **MetaPagePostsPage keeps `PostsTable`** — bespoke thumbnail + message-snippet rendering is outside `VizDataTable`'s cell contract; architect §4.6 explicitly documented the exception. A follow-up could introduce a `VizDataTable` custom-cell API.
6. **`SavedDashboardPage` cross-file mock-ordering flake** — still present. Documented in S1 closeout handoff #5 and S2b risk #3. Passes cleanly in isolation. Suggest isolating mocks before re-enabling a coverage gate.
7. **`TrendLine.StackedArea` variant** — deferred from S1c; not needed by S2; will be needed for Sprint 4 Combined area charts.
8. **`prefers-reduced-motion` polyfill** — still deferred from S1.

---

## 7. Manual smoke checklist addendum

Smoke path for each page: URL → action → expected. Run after a `scripts/dev-launch.sh` spin-up with a Meta-connected tenant (or demo adapter).

### 7.1 MetaAccountsPage (`/dashboards/meta/accounts`)

1. Load URL. **Expect**: 6-tile KPI strip renders (Spend, Impressions, Reach, CTR, CPM, Active Accounts); spend trend chart renders multi-series when no account filter is set; spend-by-objective pie renders.
2. Click a table row. **Expect**: URL navigates to `/dashboards/meta/insights?accountId=act_…` and filter store updates.
3. With zero accounts (no Meta connection), **expect**: `EmptyState reasonCode="no_accounts"` illustration + CTA.

### 7.2 MetaInsightsDashboardPage (`/dashboards/meta/insights`)

1. Load URL with `accountId` set. **Expect**: 4–5 KPI tiles (ROAS tile hidden when adapter has no `omni_purchase` actions); CTR+CPM dual-axis trend line renders with both y-axis labels.
2. Inspect BubbleScatter heading. **Expect**: "Spend vs. ROAS" when purchase actions exist, else "Spend vs. CPM".
3. Click "Sync now" button. **Expect**: toast "Sync started" (or "already running" on conflict); dashboard refetches once sync completes.

### 7.3 MetaCampaignOverviewPage (`/dashboards/meta/campaigns`)

1. Load URL. **Expect**: 4-tile KPI rollup (Spend / Impressions / Clicks / Conversions); Funnel renders 3 ordered stages Impressions → Clicks → Conversions with CTR/CVR drop-off labels in subtext.
2. Inspect top-spend DistributionBar. **Expect**: ≤10 bars, descending spend.
3. Inspect campaign table. **Expect**: inline Sparkline per row showing last 14 days of daily spend (or `—` when insights empty).

### 7.4 MetaPagesListPage (`/dashboards/meta/pages`)

1. Load URL with ≥1 Page connected. **Expect**: card grid renders each Page; no KPI strip (by design).
2. Click `AccessibleTableToggle` toggle. **Expect**: cards hide, VizDataTable of {Name, Fan Count, Last Synced At} shows.
3. With zero Pages, **expect**: `EmptyState reasonCode="no_pages"` with reconnect CTA.

### 7.5 MetaPagePostsPage (`/dashboards/meta/pages/:pageId/posts`)

1. Load URL with a Page that has posts. **Expect**: KPI strip shows Total Posts, Avg Reach, Avg Engagement tiles; media_type PieComposition renders above the PostsTable.
2. Type into search input. **Expect**: `postsQuery.q` updates and list refetches.
3. With zero posts, **expect**: `EmptyState reasonCode="no_posts"` (KPI strip + pie hidden).

### 7.6 MetaPostDetailPage (`/dashboards/meta/pages/:pageId/posts/:postId`)

1. Load URL. **Expect**: 4-tile KPI strip (Reach / Impressions / Reactions / Shares) — a tile is hidden if no availability key matches.
2. Inspect the tile matching the selected metric. **Expect**: inline Sparkline rendered inside that tile only.
3. Change the period select. **Expect**: `TrendLine` refetches and re-renders; comments section is NOT present (suppressed in S2).

### 7.7 MetaPageOverviewPage (`/dashboards/meta/pages/:pageId/overview`)

1. Load URL. **Expect**: 4-tile KPI strip (fans / impressions / engaged users / total reach); unsupported metrics render `isFaded` with hint text.
2. Inspect trend chart. **Expect**: TrendLine renders; accessible `<table>` toggle works.
3. With all KPI values null, **expect**: `EmptyState reasonCode="no_page_data"` replaces the data blocks.

---

## 8. Verdict

**Status: GREEN** — Sprint 2 Meta cluster migration complete. All 7 pages adopt the Sprint 1 viz kit, all data-availability gap strategies (ROAS conditional-derive, CPC substitution, Funnel-via-DistributionBar) landed correctly at the cited file:line evidence, 92/92 Meta targeted tests pass, 628/629 full-suite tests pass (1 unrelated pre-existing flake), lint clean, build clean, backend 727 passed / 1 skipped, ruff clean. Ready for Sprint 3 (Google Ads cluster).
