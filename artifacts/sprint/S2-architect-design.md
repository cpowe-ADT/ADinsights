# Sprint 2 — Meta Cluster — Architect Design

**Inputs cited:** `/Users/thristannewman/ADinsights/artifacts/viz/sprints-plan.md` (Sprint 2 §336–540, Design Principles §24–100), `/Users/thristannewman/ADinsights/frontend/src/components/viz/index.ts` (11-primitive barrel), `/Users/thristannewman/ADinsights/artifacts/sprint/S1-final-closeout.md` (kit register + a11y contract), and the 7 Meta route files under `/Users/thristannewman/ADinsights/frontend/src/routes/Meta*.tsx`.

> **Scope correction (in-scope is 7 pages, not 5).** The orchestrator prompt grouped `MetaPageOverviewPage + children` as one item. In this repo that expands to three distinct files: `MetaPagesListPage.tsx`, `MetaPageOverviewPage.tsx`, `MetaPagePostsPage.tsx`. The sprints-plan Sprint 2 section treats each individually, and the existing test suite already has one test file per route, so the splits are real. Work allocation below covers all seven.

---

## 1. Page-by-page current state

### 1.1 `MetaAccountsPage.tsx`

- **Store:** `useMetaStore` (accounts slice, filters).
- **API hits:** `GET /meta/accounts/` (via `state.loadAccounts`), `GET /api/integrations/social/status/` (inline side effect), `POST /api/integrations/meta/recovery/preview/` when `orphaned_marketing_access`.
- **Current layout:** header + actions row, intro panel, filter panel (search/status/since/until), loading/stale/error/empty banners, table with columns: Name, External ID, Account ID, Currency, Status, Business.
- **Current charts:** none. Pure table page today.
- **Empty/loading:** has `EmptyState reasonCode="no_accounts"` and `reasonCode="error"`; loading is a plain "Loading Meta accounts…" string (no skeleton).
- **R5 / Phase 1A hygiene still untouched:** none flagged — accounts page was cleared in C4 closeout.
- **KPI strip today:** absent. Needs to be added from whatever summary data we can derive client-side from `accounts.rows`. See §3 audit.

### 1.2 `MetaInsightsDashboardPage.tsx`

- **Store:** `useMetaStore` (filters, accounts, insights).
- **API hits:** `GET /meta/accounts/`, `GET /meta/insights/` (with level/account/since/until/search), `POST /api/integrations/meta/sync/` (sync-now button).
- **Current layout:** header + actions row, filter panel (account/level/since/until/search + refresh + sync-now), loading/stale/error/empty banners, `ResponsiveContainer`-wrapped `LineChart` for spend+clicks trend, `@tanstack/react-table` with 10 columns (date, level, external_id, impressions, reach, clicks, spend, cpc, cpm, conversions).
- **Current charts:** raw Recharts `LineChart` (spend + clicks), inline dashboard-table. Dual encoding on single left Y axis with two different magnitudes — layout is correct today but visually bad.
- **Empty/loading:** `EmptyState reasonCode="no_data_for_range"` and `reasonCode="error"`; loading is plain string.
- **R5 / Phase 1A hygiene:** `ComponentType<Record<string, unknown>>` casts on Recharts primitives (lines 144–148) can be dropped once we migrate to `TrendLine` which already has the type shims inside.
- **KPI strip today:** absent.

### 1.3 `MetaCampaignOverviewPage.tsx`

- **Store:** `useMetaStore` (filters, accounts, campaigns).
- **API hits:** `GET /meta/accounts/`, `GET /meta/campaigns/`.
- **Current layout:** header + actions row, 2-tile KPI-like dashboard-grid (Total Campaigns, Active Campaigns), filter panel (account/status/search/since/until + refresh), banners, plain HTML table (Campaign, External ID, Status, Objective, Account, Updated).
- **Current charts:** none.
- **Empty/loading:** `EmptyState reasonCode="no_data_for_range"` and `reasonCode="error"`; loading string.
- **R5 / Phase 1A hygiene:** the two-tile rollup is a hand-rolled `<article class="panel">` pattern — replace with `KpiTile`.
- **No spend / impressions / clicks / conversions on this response.** This is the biggest shift for this page (see §3).

### 1.4 `MetaPagesListPage.tsx` (read indirectly; pages list)

- **Store:** `useMetaPageInsightsStore` (pages, connection state).
- **API hits:** `GET /api/integrations/pages/` via `loadPages`.
- **Current layout:** Per sprints-plan §437–455 — a single list/grid of cards, no analytics charts, no combined call.
- **Empty/loading:** existing reasonCode-aware EmptyState; per Phase 1A.
- **R5 / Phase 1A hygiene:** sprint plan explicitly says **no analytics charts here** — just adopt `VizDataTable` for the tabular alternate and `KpiTile` is **not** added on this page.

### 1.5 `MetaPageOverviewPage.tsx`

- **Store:** `useMetaPageInsightsStore` (pages, metrics, overview, timeseries, filters, exports).
- **API hits:** `GET /api/integrations/pages/:pageId/overview/`, `GET /api/integrations/pages/:pageId/timeseries/`, metric registry, social status, saved views, exports.
- **Current layout:** breadcrumbs, header with 7+ buttons (sync, csv/pdf/png export, save/load/delete view), `MetaPagesFilterBar`, compare-to checkbox, orphan-access warning panel, missing-permissions warning panel, sync meta, `MetricPicker`, period select, `MetricAvailabilityBadge`, `KPIGrid` (existing), `EngagementBreakdownPanel`, `TrendChart` (legacy component).
- **Current charts:** legacy `TrendChart` (`components/TrendChart.tsx`) — single metric line. Legacy `KPIGrid` and `EngagementBreakdownPanel`.
- **Empty/loading:** EmptyState on error; "No trend points available" plain panel when zero points.
- **R5 / Phase 1A hygiene:** legacy `TrendChart`, `KPIGrid`, `EngagementBreakdownPanel` callsites should migrate to `TrendLine`, `KpiTile × N`, `PieComposition`. Existing components are NOT to be removed in S2 (S1 closeout handoff #1 says "progressively swap"), but this page is the swap.

### 1.6 `MetaPagePostsPage.tsx`

- **Store:** `useMetaPageInsightsStore` (pages, posts, filters, postsQuery, exports).
- **API hits:** `GET /api/integrations/pages/:pageId/posts/` (paginated with offset/limit/metric/sort/media_type/q/since/until).
- **Current layout:** breadcrumbs, header, `MetaPagesFilterBar`, warning panels, metric selector, controls panel (search/type/sort), `PostsTable` (existing component), EmptyState, pagination.
- **Current charts:** none — `PostsTable` today is the only grid. No KPI strip, no post-type-mix pie.
- **Empty/loading:** `reasonCode="no_posts"` and `reasonCode="error"`; loading string.
- **R5 / Phase 1A hygiene:** `PostsTable` is a bespoke component — can be kept (it handles post-row rendering including thumbnail + message snippet which `VizDataTable` does not). **Decision:** keep `PostsTable` for the posts grid; ADD a `KpiTile` strip and a `PieComposition` post-type-mix above it. The sprints-plan §498 says "Posts table: DataTable" but the rich post cells here are a legitimate exception — the architect decision is to leave `PostsTable` and document the divergence.

### 1.7 `MetaPostDetailPage.tsx`

- **Store:** `useMetaPageInsightsStore` (pages, postDetail, postTimeseries, filters).
- **API hits:** `GET /api/integrations/posts/:postId/`, `GET /api/integrations/posts/:postId/timeseries/`.
- **Current layout:** breadcrumbs, header, post card (message + media type + last synced + permalink), metric/period selectors, `TrendChart` (legacy) for timeseries.
- **Current charts:** legacy `TrendChart`.
- **Empty/loading:** `EmptyState` on error; no special empty for zero-series.
- **R5 / Phase 1A hygiene:** no KPI strip, no sparklines — sprints-plan calls for a KPI strip (Reach, Impressions, Reactions, Shares from `metrics{}`) + `Sparkline` per metric. Comments block is explicitly **suppressed for Sprint 2** (no endpoint).

---

## 2. Cross-cutting observations that gate the design

1. **Meta pages do NOT call `/api/metrics/combined/`.** The sprints-plan §365 and §397 examples that reference `payload.metrics.*` and `payload.campaign.trend` are aspirational — those fields do NOT exist in the Meta store today. Actual data shapes: `MetaAccount[]`, `MetaCampaign[]`, `MetaInsightRecord[]` (for ads pages) and `MetaOverviewResponse` / `MetaPostsResponse` / `MetaPostDetailResponse` / `MetaTimeseriesResponse` (for page insights). Sprint 2 code must bind to these shapes, not combined-metrics shapes. This is the single most-important data-availability finding.
2. **ROAS, revenue, conversion_value are NOT in `MetaInsightRecord`.** Sprints-plan §396 lists ROAS as a Meta Insights KPI; the response has `conversions` (count) and `actions[]` (array of `{action_type, value}`). Revenue/ROAS is derivable only if the `actions[]` array contains an `action_type === "omni_purchase"` or `"purchase"` entry with a `value`. We treat ROAS as **conditional-derive**: if derivable per-row, compute; if zero rows yield purchase action, **degrade gracefully** (hide ROAS tile + bubble y-axis swap to CPM).
3. **Frequency is NOT in `MetaInsightRecord`.** Not derivable without reach breakdown per unique user. **Degrade gracefully** — omit from Meta Insights KPI strip, replace with CPC which IS present.
4. **Objective is on `MetaCampaign`, not on `MetaInsightRecord`.** Joining spend-by-objective for the Accounts PieComposition requires a client-side join: `insights.rows` grouped by `campaign_external_id` joined against `campaigns.rows` on `external_id`. Campaigns slice is already loaded on Accounts/Insights pages via `loadAccounts` siblings; for Accounts page we must also call `loadCampaigns()` to get objective. **This is a new fetch for MetaAccountsPage** — document it in the implementer brief.
5. **Per-account spend for `MetaAccountsPage` trend** requires `/meta/insights/?level=account&since=…&until=…` (no account_id filter) — the sum of daily spend per `account_external_id`. This means **MetaAccountsPage must start calling `loadInsights()` with `level=account` and NO accountId filter**. That's a new dispatch for this page; it is in-scope and does not require store changes (the `loadInsights` action already exists; we invoke it with an override filter).
6. **`MetaPagesListPage` has no `fan_count` in current API shape.** `MetaPageRecord` fields (lib/metaPageInsights.ts lines 15–27) — need to verify what fields are on the record; sprints-plan §451 assumes fan_count. If not present, card shows `name + last_synced_at` only and the KPI strip is omitted (this page has no KPI strip per spec anyway).
7. **Loading "shimmer" today is plain text.** Every page has `"Loading X…"` divs. S2 replaces these with `ChartSkeleton variant=…`.

---

## 3. Data-availability audit

Legend: **OK** = field exists as-is; **DERIVE** = computable client-side from adjacent fields; **JOIN** = needs cross-slice join (document the fetch); **DEGRADE** = if field missing, hide block; **DEFER** = requires backend work, out of Sprint 2 scope.

| Page          | Required viz                                         | Required fields                                                      | Availability                   | Strategy                                                                                                                                                                                                                                                                                        |
| ------------- | ---------------------------------------------------- | -------------------------------------------------------------------- | ------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Accounts      | KPI: Total Spend                                     | `sum(insights.rows[l=account].spend)`                                | **JOIN**                       | Call `loadInsights({level:'account', accountId:''})` when page mounts                                                                                                                                                                                                                           |
| Accounts      | KPI: Total Impressions                               | `sum(insights.impressions)`                                          | **JOIN**                       | Same call                                                                                                                                                                                                                                                                                       |
| Accounts      | KPI: Total Reach                                     | `sum(insights.reach)`                                                | **JOIN**                       | Same call (note: sum-of-reach overcounts — document as "aggregate reach", not "unique reach")                                                                                                                                                                                                   |
| Accounts      | KPI: Avg CTR                                         | `sum(clicks)/sum(impressions)`                                       | **DERIVE**                     | Compute from insights                                                                                                                                                                                                                                                                           |
| Accounts      | KPI: Avg CPM                                         | `sum(spend)/sum(impressions)*1000`                                   | **DERIVE**                     | Compute from insights                                                                                                                                                                                                                                                                           |
| Accounts      | KPI: Active Accounts                                 | `accounts.rows.filter(a => a.status === 'ACTIVE').length`            | **OK**                         | Store already has rows                                                                                                                                                                                                                                                                          |
| Accounts      | TrendLine: spend/day/account                         | insights grouped by `date, account_external_id`                      | **JOIN**                       | From `level=account` insights                                                                                                                                                                                                                                                                   |
| Accounts      | PieComposition: spend by objective                   | `insights × campaigns` join on `campaign_external_id`→`objective`    | **JOIN**                       | Requires `loadCampaigns()` + `loadInsights({level:'campaign'})` both                                                                                                                                                                                                                            |
| Accounts      | Table: per-account metrics                           | account rows + aggregated insights                                   | **JOIN**                       | Build once from both slices                                                                                                                                                                                                                                                                     |
| Insights      | KPI: Spend                                           | `sum(insights.spend)`                                                | **OK**                         | Already in slice                                                                                                                                                                                                                                                                                |
| Insights      | KPI: ROAS                                            | from `actions[]` where `action_type` in purchase set                 | **DERIVE (conditional)**       | If any row has purchase value → compute; else degrade — hide tile                                                                                                                                                                                                                               |
| Insights      | KPI: CTR                                             | `sum(clicks)/sum(impressions)`                                       | **DERIVE**                     | —                                                                                                                                                                                                                                                                                               |
| Insights      | KPI: Frequency                                       | impressions / unique users                                           | **DEFER**                      | Not derivable. **Degrade**: replace with CPC tile                                                                                                                                                                                                                                               |
| Insights      | KPI: CPM                                             | `sum(spend)/sum(impressions)*1000`                                   | **DERIVE**                     | —                                                                                                                                                                                                                                                                                               |
| Insights      | TrendLine dual-axis CTR + CPM                        | insights grouped by date                                             | **DERIVE**                     | Group existing `chartData` transform by date, compute per-day                                                                                                                                                                                                                                   |
| Insights      | BubbleScatter x=spend y=ROAS z=impressions           | campaign-level insights                                              | **JOIN + DERIVE**              | `level=campaign` insights; y-axis swaps to CPM if ROAS not derivable for any row                                                                                                                                                                                                                |
| Insights      | Table: top campaigns                                 | existing rows                                                        | **OK**                         | Already rendered                                                                                                                                                                                                                                                                                |
| Campaigns     | KPI: Spend                                           | NOT on `MetaCampaign`                                                | **JOIN**                       | Call `loadInsights({level:'campaign'})`                                                                                                                                                                                                                                                         |
| Campaigns     | KPI: Impressions                                     | same                                                                 | **JOIN**                       | Same                                                                                                                                                                                                                                                                                            |
| Campaigns     | KPI: Clicks                                          | same                                                                 | **JOIN**                       | Same                                                                                                                                                                                                                                                                                            |
| Campaigns     | KPI: Conversions                                     | same                                                                 | **JOIN**                       | Same                                                                                                                                                                                                                                                                                            |
| Campaigns     | Funnel: Impressions → Clicks → Conversions           | summed metrics                                                       | **DERIVE**                     | **No Funnel primitive in viz kit.** Use `DistributionBar orientation="horizontal"` with ordered 3 stages + drop-off % labels — architect decision per prompt line 45                                                                                                                            |
| Campaigns     | DistributionBar: spend by campaign (top 10)          | campaign-level insights                                              | **JOIN**                       | Same insights call                                                                                                                                                                                                                                                                              |
| Campaigns     | Table with inline Sparkline per row                  | row's daily spend history                                            | **JOIN**                       | Group `level=campaign` insights by date per campaign; feed per-row array to `Sparkline`                                                                                                                                                                                                         |
| Pages List    | Cards + DataTable                                    | `pages[]` from existing store                                        | **OK**                         | No KPI strip per spec                                                                                                                                                                                                                                                                           |
| Pages List    | `fan_count` on card                                  | `MetaPageRecord.fan_count`                                           | **VERIFY** (check record type) | If absent → show name + last_synced_at only                                                                                                                                                                                                                                                     |
| Page Overview | KPI: followers, reach, engagement                    | `overview.kpis[]`                                                    | **OK**                         | Already in store; migrate from legacy `KPIGrid` to `KpiTile × 4`                                                                                                                                                                                                                                |
| Page Overview | TrendLine: follower growth                           | `overview.daily_series[primary_metric]`                              | **OK**                         | Already in store; migrate from legacy `TrendChart`                                                                                                                                                                                                                                              |
| Page Overview | PieComposition: post-type mix / engagement breakdown | `overview.engagement_breakdown[metric]`                              | **OK**                         | `BreakdownEntry[]` shape matches PieComposition slice input                                                                                                                                                                                                                                     |
| Posts list    | KPI: Total Posts, Avg Reach, Avg Engagement          | computed from `posts.results[]`                                      | **DERIVE**                     | From `results[].metrics`. Avg reach = mean of `metrics[reach_metric]`; avg engagement = mean of engagement metric. Use first available metric key from `metric_availability`                                                                                                                    |
| Posts list    | PieComposition post-type mix                         | `results[].media_type` counts                                        | **DERIVE**                     | `groupBy(results, 'media_type')`                                                                                                                                                                                                                                                                |
| Posts list    | Posts table                                          | existing `PostsTable`                                                | **OK**                         | Keep as-is; do NOT migrate to `VizDataTable` (thumbnail + message snippet cell is non-standard)                                                                                                                                                                                                 |
| Post Detail   | KPI: Reach, Impressions, Reactions, Shares           | `postDetail.metrics{}`                                               | **OK (conditional)**           | Pick first available of each category from `metric_availability`. If a category missing → hide that tile                                                                                                                                                                                        |
| Post Detail   | Sparkline per KPI tile                               | would need per-metric timeseries; only 1 metric at a time is fetched | **DEFER / DEGRADE**            | Sprints-plan §520 says one `TrendLine` for selected metric, not per-tile sparkline. **Decision:** render one `TrendLine` + single `Sparkline` on each tile showing the _selected_ metric's last-7-points. Do NOT fire 4 timeseries calls. Alternative: hide Sparkline until user selects metric |
| Post Detail   | Comments table                                       | no endpoint                                                          | **DEFER**                      | Suppress block entirely (sprints-plan §524)                                                                                                                                                                                                                                                     |

### Gap summary for implementers

- **Two new fetches on MetaAccountsPage** (`loadInsights({level:'account'})` + `loadCampaigns()`). Both actions exist in the store today.
- **Two new fetches on MetaCampaignOverviewPage** (`loadInsights({level:'campaign'})` plus optional `level=campaign` grouped-by-date for sparklines). Single insights call serves both (group client-side).
- **ROAS is conditional** everywhere — implementers MUST branch on `hasPurchaseActions`. No backend request.
- **Frequency is dropped** from the Insights KPI strip — replaced with CPC. No backend request.
- **Funnel viz** uses `DistributionBar` per §3 row; no new primitive added this sprint.
- **Post-detail sparklines per tile** scope-reduced to one sparkline of the currently-selected metric.

---

## 4. Per-page design spec

Each page follows the 5-block layout from sprints-plan §28: KPI strip → Trend → Distribution/specialized → Drill-down table. Exceptions called out.

### 4.1 MetaAccountsPage

**Target layout (top to bottom):**

1. Keep existing header + intro + filter panel (unchanged).
2. `KpiTile × 6` in a grid (Spend, Impressions, Reach, CTR, CPM, Active Accounts). On skeleton: `ChartSkeleton variant="kpi-strip" count={6}`.
3. `TrendLine` full-width: spend/day, multi-series when `filters.accountId === ''`, single-series + `PeerAvgLine` when a filter is set.
4. `PieComposition` half-width next to a placeholder or legend panel: spend by objective.
5. `VizDataTable` full-width: per-account metrics. Row click → navigate to `/dashboards/meta/insights?accountId=${external_id}` (replace the current `setFilters({accountId})` behaviour — URL navigation is the drill-down per sprints-plan §374).

**Primitives used:** `KpiTile × 6`, `TrendLine` (+ `PeerAvgLine` sub-use), `PieComposition`, `VizDataTable`, `ChartSkeleton` (3 variants), `EmptyState` (`reasonCode=no_accounts`|`no_data_for_range`|`error`), `AccessibleTableToggle` on both TrendLine and PieComposition.

**Data transforms (pseudocode):**

```ts
// from insights slice loaded with level='account'
const byAccountDay = groupBy(
  insights.rows,
  (r) => `${r.date}|${r.account_external_id}`,
);
const trendSeries = filters.accountId
  ? [{ name: accountName, data: dailyFor(filters.accountId) }]
  : topNAccountsByTotalSpend(6).map((acct) => ({
      name: acct.name,
      data: dailyFor(acct.external_id),
    }));
const peerAvg = computeMedianPerDate(allAccountsDaily); // only when filtered

// objective slice: left join campaigns
const campaignIdToObjective = new Map(
  campaigns.rows.map((c) => [c.external_id, c.objective]),
);
const spendByObjective = insights.rows.reduce(
  (acc, r) => {
    const obj = campaignIdToObjective.get(r.campaign_external_id) ?? 'UNKNOWN';
    acc[obj] = (acc[obj] ?? 0) + Number(r.spend);
    return acc;
  },
  {} as Record<string, number>,
);
const pieSlices = Object.entries(spendByObjective).map(([name, value]) => ({
  name,
  value,
}));

// KPI aggregates
const totalSpend = sum(insights.rows, (r) => Number(r.spend));
const totalImpressions = sum(insights.rows, (r) => r.impressions);
const totalReach = sum(insights.rows, (r) => r.reach);
const ctr = totalImpressions ? sumClicks / totalImpressions : 0;
const cpm = totalImpressions ? (totalSpend / totalImpressions) * 1000 : 0;
const activeAccounts = accounts.rows.filter((a) =>
  /ACTIVE/.test(a.status),
).length;
```

**Empty-state reasonCodes:**

- `no_accounts` when `accounts.status === 'loaded' && accounts.rows.length === 0` (keep existing block).
- `no_data_for_range` when accounts exist but `insights.rows.length === 0` — shown in the chart/table blocks only, not page-level.
- `error` on either slice errors.
- Adapter errors surface via existing `errorCode` path → renders into same EmptyState.

**A11y toggles:** `AccessibleTableToggle` on `TrendLine` and `PieComposition`. VizDataTable is already a table.

### 4.2 MetaInsightsDashboardPage

**Target layout:**

1. Keep filter panel + sync-now button.
2. `KpiTile × 5`: Spend, ROAS (conditional — hide tile if `!hasPurchaseActions`), CTR, CPC (substitute for Frequency — see §3), CPM.
3. `TrendLine` dual-axis: left y = CTR (percent), right y = CPM (currency). Requires the `rightYFormat` prop landed in S1 (confirm in `TrendLine.tsx` before starting; if missing, this becomes two stacked `TrendLine` charts side-by-side — document in brief).
4. `BubbleScatter`: x=spend, y=ROAS (or CPM fallback), z=impressions, shape by `objective` when `filters.accountId === ''`, shape by `level` when filtered.
5. `VizDataTable` replacing the current `@tanstack/react-table` grid. Columns: Campaign Name, Spend, Impressions, CTR, CPM, ROAS, Objective. Row click → `/dashboards/meta/campaigns?campaignId=…` (no-op route for S2 per sprints-plan §410 — leave the click handler prop off or pointing to a sentinel).

**Primitives used:** `KpiTile × 5`, `TrendLine` (dual-axis), `BubbleScatter`, `VizDataTable`, `ChartSkeleton`, `EmptyState`, `AccessibleTableToggle × 2` (TrendLine + BubbleScatter).

**Data transforms:**

```ts
// dual-axis trend
const trendByDay = groupBy(insights.rows, (r) => r.date);
const trendPoints = [...trendByDay.entries()].map(([date, rows]) => ({
  date,
  ctr: totalClicks(rows) / (totalImpressions(rows) || 1),
  cpm: (totalSpend(rows) / (totalImpressions(rows) || 1)) * 1000,
}));

// bubble
const bubbleRows = insights.rows
  .filter((r) => r.level === 'campaign')
  .map((r) => ({
    id: r.external_id,
    x: Number(r.spend),
    y: derivedRoas(r) ?? Number(r.cpm),
    z: r.impressions,
    shapeCategory: filters.accountId ? r.level : objectiveFor(r),
    label: nameFor(r),
  }));

// ROAS helper
function derivedRoas(r) {
  const purchase = r.actions?.find(
    (a) => a.action_type === 'omni_purchase' || a.action_type === 'purchase',
  );
  if (!purchase?.value || !Number(r.spend)) return null;
  return Number(purchase.value) / Number(r.spend);
}
```

**Empty states:** `no_data_for_range`, `error`. Same as today.

**A11y toggles:** on TrendLine and BubbleScatter.

### 4.3 MetaCampaignOverviewPage

**Target layout:**

1. Replace the 2-tile hand-rolled rollup with `KpiTile × 4` (Spend, Impressions, Clicks, Conversions). Keep filter panel.
2. **Funnel (via `DistributionBar`)**: 3 stages Impressions → Clicks → Conversions with drop-off % in subtext. Architect decision — `DistributionBar` with `orientation="horizontal"` and ordered categories achieves the funnel pattern without adding a new primitive. Use `valueFormatter` to render both absolute and drop-off %.
3. `DistributionBar`: spend by campaign, top 10.
4. `VizDataTable`: Campaign, Status, Objective, Account, Spend, Impressions, Clicks, Conversions, Updated — with an inline `Sparkline` in a new "Spend trend" column (last 14 days of daily spend per campaign).

**Primitives used:** `KpiTile × 4`, `DistributionBar × 2` (funnel + spend-by-campaign), `VizDataTable` + inline `Sparkline`, `ChartSkeleton`, `EmptyState`, `AccessibleTableToggle × 2`.

**Data transforms:**

```ts
// campaign-level insights must be loaded for this page
const byCampaign = groupBy(insights.rows, (r) => r.campaign_external_id);
const sparklinesByCampaign = new Map(
  [...byCampaign.entries()].map(([cid, rows]) => [
    cid,
    rows.sort(byDate).map((r) => ({ date: r.date, value: Number(r.spend) })),
  ]),
);

// funnel as DistributionBar
const totals = sumAll(insights.rows);
const funnelStages = [
  { name: 'Impressions', value: totals.impressions },
  {
    name: 'Clicks',
    value: totals.clicks,
    sublabel: `${pct(totals.clicks / totals.impressions)} CTR`,
  },
  {
    name: 'Conversions',
    value: totals.conversions,
    sublabel: `${pct(totals.conversions / totals.clicks)} CVR`,
  },
];

// top 10 spend
const topSpend = [...byCampaign.entries()]
  .map(([cid, rows]) => ({
    name: campaignName(cid),
    value: sum(rows, (r) => Number(r.spend)),
  }))
  .sort((a, b) => b.value - a.value)
  .slice(0, 10);
```

**Empty states:** `no_campaigns` when `campaigns.rows.length === 0`; `no_data_for_range` when campaigns exist but insights empty; `error`.

**A11y toggles:** on both `DistributionBar` instances. Row-level sparklines inherit VizDataTable's table a11y.

### 4.4 MetaPagesListPage

**Target layout:**

1. Keep breadcrumbs + header + filter bar (unchanged).
2. Cards grid (existing) — per-page cards wrapped in `<Link>` to `/dashboards/meta/pages/:pageId/overview`.
3. `VizDataTable` toggle — mount `AccessibleTableToggle` _around_ the cards section. Toggle view = table with Page Name, Fan Count (if present), Last Synced At columns.

**Primitives used:** `VizDataTable`, `AccessibleTableToggle`, `EmptyState`, `ChartSkeleton variant="table"`. No `KpiTile`, no charts (per sprints-plan §447).

**Data transforms:** trivial — `pages.map(p => ({ name: p.name, fan_count: p.fan_count, last_synced_at: p.last_synced_at }))`.

**Empty states:** `no_pages` (existing reasonCode), `error`.

**A11y:** cards are links; table alternate is already a `<table>`.

### 4.5 MetaPageOverviewPage

**Target layout:** preserve breadcrumbs, header, filter bar, compare-to, warning panels, metric picker, period select, badge, sync-meta line. Replace the data blocks:

1. Replace `KPIGrid` → `KpiTile × 4` (from `overview.kpis[]` — typically page_fans/page_impressions/page_engaged_users/page_total_reach).
2. `TrendLine` full-width (replace `TrendChart`) of `daily_series[selected_metric]`.
3. `PieComposition` (replace `EngagementBreakdownPanel`) of `overview.engagement_breakdown[selected_metric]`.
4. `MetaPageExportHistory` block unchanged.

**Primitives used:** `KpiTile × 4`, `TrendLine`, `PieComposition`, `ChartSkeleton × 3`, `EmptyState reasonCode="no_page_data"`, `AccessibleTableToggle × 2`.

**Data transforms:**

```ts
const kpiTiles = overview.kpis.slice(0, 4).map((k) => ({
  label: formatMetricLabel(k.resolved_metric),
  value: k.value ?? 0,
  delta: k.change_pct ?? undefined,
  tone: k.change_pct != null && k.change_pct < 0 ? 'negative' : 'positive',
}));

const trendPoints =
  overview.daily_series[selectedMetric]?.map((p) => ({
    date: p.date,
    value: p.value ?? 0,
  })) ?? [];

const breakdownSlices = (
  overview.engagement_breakdown?.[selectedMetric] ?? []
).map((e) => ({ name: e.type, value: e.value ?? 0 }));
```

**Empty states:** `no_page_data` when `kpis.every(k => k.value === null)`. Existing `dashboardStatus` drives loading/error.

**A11y toggles:** on TrendLine + PieComposition.

### 4.6 MetaPagePostsPage

**Target layout:**

1. Keep breadcrumbs + header + warning panels + filter bar + controls + metric selector.
2. **New:** `KpiTile × 3` (Total Posts, Avg Reach, Avg Engagement).
3. **New:** `PieComposition`: media_type distribution.
4. Keep `PostsTable` (existing bespoke component — see §1.6 decision).
5. Pagination row unchanged.

**Primitives used:** `KpiTile × 3`, `PieComposition`, `ChartSkeleton`, `EmptyState reasonCode="no_posts"`, `AccessibleTableToggle × 1` on PieComposition.

**Data transforms:**

```ts
const posts = data?.results ?? [];
const selectedEngagementMetric = postsQuery.metric; // already in store
const avgReach = mean(
  posts,
  (p) =>
    p.metrics['post_impressions_unique'] ??
    p.metrics['page_total_media_view_unique'],
);
const avgEngagement = mean(
  posts,
  (p) => p.metrics[selectedEngagementMetric] ?? 0,
);

const typeMix = Object.entries(
  groupByCount(posts, (p) => p.media_type || 'UNKNOWN'),
).map(([name, count]) => ({ name, value: count }));
```

**Empty states:** `no_posts`, `error`. Existing reasonCodes preserved.

**A11y toggle:** on PieComposition.

### 4.7 MetaPostDetailPage

**Target layout:**

1. Keep breadcrumbs + header + post message card.
2. **New:** `KpiTile × 4` (Reach, Impressions, Reactions, Shares from `postDetail.metrics`). Each tile renders a `Sparkline` only for the _currently selected_ timeseries metric (one call already fires); other tiles render sparkline as `null`. Alternatively, show Sparkline only on the tile whose metric matches the selected one — architect recommends the latter to avoid implying data we don't have.
3. Keep metric/period selectors.
4. `TrendLine` replacing `TrendChart` for the selected metric.
5. Comments block SUPPRESSED (sprints-plan §524).

**Primitives used:** `KpiTile × 4` (with conditional embedded `Sparkline`), `TrendLine`, `ChartSkeleton`, `EmptyState`, `AccessibleTableToggle × 1`.

**Data transforms:**

```ts
const metricKeysByCategory = {
  reach: ['post_impressions_unique', 'page_total_media_view_unique'],
  impressions: ['post_impressions', 'page_impressions'],
  reactions: ['post_reactions_by_type_total', 'post_reactions_like_total'],
  shares: ['post_shares'],
};
function pickFirstAvailable(category) {
  return metricKeysByCategory[category].find(
    (k) => postDetail.metric_availability[k],
  );
}
const kpiEntries = ['reach', 'impressions', 'reactions', 'shares']
  .map((cat) => {
    const k = pickFirstAvailable(cat);
    return k
      ? { label: cat, value: postDetail.metrics[k] ?? null, metricKey: k }
      : null;
  })
  .filter(Boolean);

const trendPoints = (postTimeseries?.points ?? []).map((p) => ({
  date: p.end_time.slice(0, 10),
  value: p.value ?? 0,
}));
const sparklineForTileWhereMetricMatches = (tile) =>
  tile.metricKey === metric ? trendPoints.slice(-7) : undefined;
```

**Empty states:** `error` on postStatus === 'error'; `no_data_for_range` when `trendPoints.length === 0`.

**A11y toggle:** on TrendLine.

---

## 5. Implementer briefs

Two implementer agents run in parallel with **zero file overlap**. Both must land before S2 closes.

### 5.1 S2a-AccountsInsights — implementer brief (paste to orchestrator verbatim)

**Role:** Frontend implementer for Sprint 2 — Meta Accounts + Meta Insights pages.

**Inputs to cite in first line:**

1. `/Users/thristannewman/ADinsights/artifacts/sprint/S2-architect-design.md` — this document (§4.1, §4.2, §3 audit rows for Accounts + Insights)
2. `/Users/thristannewman/ADinsights/frontend/src/components/viz/index.ts` — import only from `@/components/viz`
3. `/Users/thristannewman/ADinsights/frontend/src/lib/meta.ts` — `MetaInsightRecord`, `MetaCampaign`, `MetaAccount` shapes
4. `/Users/thristannewman/ADinsights/frontend/src/state/useMetaStore.ts` — `accounts`, `campaigns`, `insights` slices + `loadAccounts`/`loadCampaigns`/`loadInsights` actions

**Scope (modify / create):**

- `frontend/src/routes/MetaAccountsPage.tsx` — add KPI strip, TrendLine, PieComposition, migrate table to `VizDataTable`. Dispatch `loadCampaigns()` and `loadInsights({level:'account'})` on mount (and on filter change).
- `frontend/src/routes/MetaInsightsDashboardPage.tsx` — add KPI strip, dual-axis TrendLine, BubbleScatter, migrate table to `VizDataTable`. Drop `@tanstack/react-table` import.
- `frontend/src/routes/__tests__/MetaAccountsPage.test.tsx` — add/update tests per §6.1
- `frontend/src/routes/__tests__/MetaInsightsDashboardPage.test.tsx` — add/update tests per §6.2
- Optional: new `frontend/src/lib/metaAggregates.ts` (pure functions: `sumInsights`, `groupByDateAccount`, `derivedRoas`, `computePeerMedian`) with unit tests at `frontend/src/lib/metaAggregates.test.ts`.

**Don't touch:**

- `MetaCampaignOverviewPage.tsx`, `MetaPagesListPage.tsx`, `MetaPageOverviewPage.tsx`, `MetaPagePostsPage.tsx`, `MetaPostDetailPage.tsx`
- `useMetaStore.ts` — only dispatch existing actions; NO signature/state-shape changes
- `components/EmptyState.tsx`, viz kit (`components/viz/*`) — consume only
- Legacy `TrendChart.tsx`, `KPIGrid.tsx` — don't delete (other pages consume them until S2b lands)
- Backend endpoints (out of sprint scope)

**Process:**

1. Read §4.1 and §4.2 of the architect design + the current page files.
2. Verify `TrendLine` supports `rightYFormat` / dual axis — if not, fall back to two stacked `TrendLine`s per §4.2.
3. Implement MetaAccountsPage first (simpler — single-axis trend).
4. Implement MetaInsightsDashboardPage.
5. Update tests. Preserve Phase 1A contract assertions: `reasonCode` prop present, store subscription shape unchanged, filter propagation to `loadInsights`.
6. Run: `cd frontend && npm run lint && npm run build && npm test -- --run src/routes/__tests__/MetaAccountsPage.test.tsx src/routes/__tests__/MetaInsightsDashboardPage.test.tsx`.
7. Full suite must stay green: `cd frontend && npm test -- --run`.

**Expected output location:** `/Users/thristannewman/ADinsights/artifacts/sprint/S2a-accounts-insights.md` — closeout with diffs summary, test counts, any design deviations.

---

### 5.2 S2b-CampaignsPagesPost — implementer brief (paste to orchestrator verbatim)

**Role:** Frontend implementer for Sprint 2 — Meta Campaigns + Meta Page Overview + Pages List + Posts List + Post Detail.

**Inputs to cite in first line:**

1. `/Users/thristannewman/ADinsights/artifacts/sprint/S2-architect-design.md` — this document (§4.3–§4.7, §3 audit rows for Campaigns/Pages/Posts)
2. `/Users/thristannewman/ADinsights/frontend/src/components/viz/index.ts`
3. `/Users/thristannewman/ADinsights/frontend/src/lib/metaPageInsights.ts` — `MetaOverviewResponse`, `MetaPostsResponse`, `MetaPostDetailResponse`, `MetaTimeseriesResponse`
4. `/Users/thristannewman/ADinsights/frontend/src/state/useMetaPageInsightsStore.ts`
5. `/Users/thristannewman/ADinsights/frontend/src/state/useMetaStore.ts` — only `campaigns` + `insights` slices for the campaigns page

**Scope (modify / create):**

- `frontend/src/routes/MetaCampaignOverviewPage.tsx` — KPI strip, funnel-as-DistributionBar, top-10 spend DistributionBar, VizDataTable with inline Sparklines. Dispatch `loadInsights({level:'campaign'})` on filter change.
- `frontend/src/routes/MetaPagesListPage.tsx` — wrap cards grid with `AccessibleTableToggle`; add `VizDataTable` alternate view.
- `frontend/src/routes/MetaPageOverviewPage.tsx` — replace `KPIGrid` → `KpiTile × 4`; replace `TrendChart` → `TrendLine`; replace `EngagementBreakdownPanel` → `PieComposition`. Keep breadcrumbs, filter bar, exports, warning panels, metric picker, period select untouched.
- `frontend/src/routes/MetaPagePostsPage.tsx` — add `KpiTile × 3` (Total Posts/Avg Reach/Avg Engagement) and `PieComposition` (media_type mix) above the existing `PostsTable`. Do NOT replace `PostsTable`.
- `frontend/src/routes/MetaPostDetailPage.tsx` — add `KpiTile × 4` block (Reach/Impressions/Reactions/Shares) using `metric_availability` to pick first-available keys; replace `TrendChart` → `TrendLine`.
- Corresponding test files under `frontend/src/routes/__tests__/Meta*.test.tsx` — see §6.3–§6.7.

**Don't touch:**

- `MetaAccountsPage.tsx`, `MetaInsightsDashboardPage.tsx` (S2a owns)
- `components/TrendChart.tsx`, `components/KPIGrid.tsx`, `components/EngagementBreakdownPanel.tsx` — leave them untouched for now (can be deleted in a follow-up after S2 verification)
- `components/PostsTable.tsx` — keep in use on `MetaPagePostsPage`
- `useMetaPageInsightsStore.ts`, `useMetaStore.ts` — no shape changes
- Backend endpoints, `MetaPagesFilterBar`, `MetricPicker`, `MetaPageExportHistory`, `MetricAvailabilityBadge` — reuse unchanged
- Saved-views logic on `MetaPageOverviewPage` — preserve exactly as-is
- Viz kit internals

**Process:**

1. Read §4.3–§4.7 and the five current page files.
2. Order of implementation: Pages List (lowest risk) → Posts List → Post Detail → Page Overview (most visual change) → Campaign Overview (most new fetches). This lets the implementer build confidence before touching the two highest-impact pages.
3. Preserve Phase 1A contract assertions in all tests.
4. Run the gates from §5.1 step 6 + 7 against the five modified files.

**Expected output location:** `/Users/thristannewman/ADinsights/artifacts/sprint/S2b-campaigns-pages-post.md`.

---

## 6. Test strategy

Baseline: every test file already exists; architect preserves Phase 1A contract tests (reasonCode presence, store subscription shape, filter propagation). Tests added below are **additive**.

### 6.1 MetaAccountsPage.test.tsx

- **KPI tile rendering:** mount with mocked accounts + insights rows → assert 6 `KpiTile` presences by `aria-label`/`data-testid`.
- **Empty state switches reasonCode** based on `accounts.rows.length === 0` vs `insights.rows.length === 0`.
- **Trend series count:** when `filters.accountId === ''` → assert `TrendLine` gets N series (capped at 6 + "Other"); when set → 1 series + `PeerAvgLine`.
- **Pie computed from join:** mock insights + campaigns; assert `PieComposition` receives N slices matching unique objectives.
- **Row click navigates:** click a table row → assert `navigate('/dashboards/meta/insights?accountId=…')` called.
- Keep existing filter-input tests.

### 6.2 MetaInsightsDashboardPage.test.tsx

- **Conditional ROAS tile:** mock insights with no purchase actions → assert ROAS tile absent; with purchase action → present.
- **Dual-axis trend:** assert `TrendLine` receives both `ctr` and `cpm` series; if `TrendLine` does not support dual-axis, assert two stacked charts render.
- **BubbleScatter shape encoding:** assert shape prop switches between "objective" and "level" based on filter.
- **VizDataTable replaces tanstack-table:** assert column header count = 7.
- **Sync-now behavior preserved.**

### 6.3 MetaCampaignOverviewPage.test.tsx

- **KPI tile count = 4** (Spend, Impressions, Clicks, Conversions).
- **Funnel bar stages = 3** in correct order (Impressions, Clicks, Conversions).
- **Drop-off labels** are numeric percentages.
- **Top-10 spend DistributionBar slice count <= 10**.
- **Inline Sparkline per row:** assert each VizDataTable row has a Sparkline element.
- **Insights dispatch:** mount → assert `loadInsights({level:'campaign', …})` called with current filters.

### 6.4 MetaPagesListPage.test.tsx

- **AccessibleTableToggle toggles** between cards and VizDataTable views.
- Preserve existing card-rendering test.

### 6.5 MetaPageOverviewPage.test.tsx

- **KpiTile × 4 replaces KPIGrid** (assert absence of `KPIGrid` testid if present; presence of 4 `KpiTile`).
- **TrendLine replaces TrendChart** for `daily_series[selectedMetric]`.
- **PieComposition slice count** matches `engagement_breakdown[selectedMetric].length`.
- **Saved-view load/save/delete paths preserved** (don't regress existing coverage).
- **`no_page_data` reasonCode when all kpis null.**

### 6.6 MetaPagePostsPage.test.tsx

- **KpiTile × 3 renders** with correct labels.
- **PieComposition** slice count matches distinct `media_type` values.
- **PostsTable preserved** (assert existing component still mounts with same `rows` prop).
- Pagination unchanged.

### 6.7 MetaPostDetailPage.test.tsx

- **KpiTile × 4 renders for available metric categories**; tile hidden when no availability-entry exists for category.
- **TrendLine replaces TrendChart.**
- **Comments block absent** (assert by `data-testid` or by ensuring no section with "Comments" heading).
- **Sparkline only on tile matching selected metric** (per §4.7 decision).

### Cross-page regression

- Existing `MetaDashboardEmptyStates.test.tsx` must stay green — it tests reasonCode propagation across all Meta pages. Both implementer briefs call it out.

---

## 7. Risks

1. **Data shape mismatch — `payload.metrics.*` doesn't exist.** Sprints-plan §365/§397 cites combined-metrics shapes; the Meta store uses paginated `MetaInsightRecord[]`. Implementers who copy the plan verbatim will break the build. §2 and §3 above explicitly redirect — but the brief must be read carefully.
2. **Dual-axis TrendLine capability unverified.** Sprint 1 landed TrendLine with peer-avg, but the `rightYFormat` prop (sprints-plan §401) may not be in the shipped API. S2a must verify before coding the Insights trend; fallback plan is two stacked charts.
3. **Peer-average calc edge cases.** Tenants with 1 account: suppress the line (sprints-plan §45). Tenants with uneven date coverage across accounts: use median ignoring nulls per date. Date-range containing zero-data days: decide whether to draw 0 or gap (recommend gap).
4. **Layout shift on Recharts swap.** Replacing a `ResponsiveContainer` + inline `LineChart` with `TrendLine` primitive must preserve the 260px min-height or users see a jump. `ChartSkeleton` footprint must match.
5. **Empty-state cascade.** Each page has 3–4 independent loading slices (accounts, insights, campaigns, posts, overview). Risk of flashing multiple empty states during staggered loads. Implementers must gate empty renders on `status !== 'loading'` for each slice.
6. **Snapshot test fragility.** Existing test files may use snapshot matchers that break on the markup change. Prefer `getByRole`/`getByTestId` + prop assertions; avoid `toMatchSnapshot` for the visual blocks. Update snapshots only when necessary.
7. **`MetaPagesListPage` fan_count uncertainty.** If `MetaPageRecord` doesn't include `fan_count`, the VizDataTable's column must be conditionally omitted. Implementer must read the record type first.
8. **New fetches on MetaAccountsPage** (`loadCampaigns`, `loadInsights`) may race with existing debounced filter effect. Keep the existing `useEffect` dependency arrays intact and add the new calls to the same effect rather than a parallel one to avoid duplicate dispatches.
9. **Post-detail per-tile sparkline:** sprints-plan phrasing implies 4 sparklines but only 1 timeseries call fires. §4.7 scope-reduction risks user surprise — mitigate by showing the sparkline only on the "active" tile and labeling it clearly.

---

## 8. Out of scope (explicit callouts)

- **No Funnel primitive added to viz kit.** `DistributionBar` with ordered stages fulfills the Campaign page funnel requirement per architect decision §3 + §4.3.
- **Combined / Google Ads / parish-map pages** — Sprint 3 (Google Ads) and Sprint 4 (Combined + Map) own those pages. Do not touch `/frontend/src/pages/*Dashboard*` combined routes or Google Ads routes.
- **Backend endpoints** — no Django changes in Sprint 2. ROAS, Frequency, per-user reach gaps do NOT trigger backend work — they degrade gracefully or are deferred.
- **`useMetaStore` / `useMetaPageInsightsStore` refactor** — store shapes are frozen per CLAUDE.md "locked from re-architecture".
- **Legacy component deletion** (`TrendChart`, `KPIGrid`, `EngagementBreakdownPanel`) — deferred to a follow-up cleanup sprint once all callsites migrate (S1 closeout handoff #1).
- **Comments block on Post Detail** — no endpoint; suppress for Sprint 2 (sprints-plan §524).
- **Sparkline-per-tile on Post Detail** — scope-reduced to one sparkline on the active tile.
- **Print/PDF styling** — sprints-plan §98 deferred as non-goal.
- **`prefers-reduced-motion`** — S1 closeout handoff #3 noted this as deferred; ChartSkeleton shimmer will animate unconditionally. Acceptable for S2.
- **Playwright e2e updates** — sprints-plan §348 mentions "Playwright: account row click → insights scoped to that account". S2 architect recommends deferring the Playwright addition to a post-S2 PR; the row-click assertion is covered by vitest in §6.1.
