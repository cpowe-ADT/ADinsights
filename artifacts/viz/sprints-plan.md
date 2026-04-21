# ADinsights Data-Visualization Sprint Plan

**Inputs cited:**
- `/Users/thristannewman/ADinsights/artifacts/plan.md`
- `/Users/thristannewman/ADinsights/artifacts/synthesis/synthesis-report.md`
- `/Users/thristannewman/ADinsights/artifacts/verify/meta-verification.json`
- `/Users/thristannewman/ADinsights/artifacts/verify/google-verification.json`
- `/Users/thristannewman/ADinsights/artifacts/verify/combined-verification.json`

---

## Chart Library Confirmed

**Recharts `^3.7.0`** is the sole chart library in use (`frontend/package.json`). All chart specs below use Recharts primitives only. The chart theme and palette live in `frontend/src/styles/chartTheme.ts`.

---

## Data-Contract Summary

`/api/metrics/combined/` returns a snapshot payload with top-level sections: `metrics` (period KPIs: spend, impressions, clicks, conversions, reach, ctr, cpm, roas, frequency), `campaign` (summary + trend array + rows with per-campaign KPIs including platform, objective, ctr, cpm, roas, cpa, reach, frequency), `creative` (rows: spend, impressions, clicks, conversions, reach per creative name), `budget` (rows: campaignName, spendToDate, budgetAmount, pacing_pct), `parish` (rows: parish, spend, impressions, clicks, conversions), and `platforms` (byPlatform, byDevice, byPlatformDevice, byAge, byGender, byAgeGender — all with spend, impressions, clicks, conversions, reach). Google Ads-specific endpoints (`/api/google-ads/*`) supply cost, clicks, impressions, conversions, cpa, roas, channel_type, quality_score, search_term, asset_group, pacing (spend_mtd, budget_month, forecast_month_end, over_under, pacing_pct), change events, and recommendations. Meta Pages endpoints (`/api/integrations/pages/:id/overview/`, `/posts/`, `/posts/:id/`) supply KPIs, daily_series, engagement_breakdown, and post-level metrics (reactions, shares, reach, impressions). GA4 and Search Console row-level data come from `/api/web/ga4/` and `/api/web/search-console/` — no combined call.

---

## Design Principles

These apply to every page and every chart in all four sprints.

### Layout pattern
Every dashboard page follows the 5-block structure:
1. **KPI strip** — 4–6 tiles across the top
2. **Primary trend chart** — time-series, full width
3. **Distribution chart** — composition or comparison
4. **Optional specialized viz** — map, bubble, funnel, gauge, treemap
5. **Drill-down table** — sortable, CSV-exportable

Pages with insufficient data for a block must show an `EmptyState` with a `reasonCode`, not a blank area.

### Filtered vs unfiltered `account_id` rendering

| Condition | Chart behavior |
|-----------|---------------|
| `account_id` not selected (all accounts) | Multi-series lines/bars, each series one account; legend toggle per account |
| `account_id` selected (single account) | Single-series primary line/bars + faded "peer average" dashed line derived from median of all accounts in the same date range |
| `account_id` selected, only 1 account in tenant | No peer average line; suppress legend |

**Peer average derivation:** computed client-side from the unfiltered payload that is already cached in the store. Compute the median metric value across all accounts per date point. No new endpoint required.

### Empty / Loading / Error states

| State | Behavior |
|-------|---------|
| Loading | `ChartSkeleton` shimmer matching exact footprint of target chart (same height, same column count) — no layout shift |
| Empty — no accounts | `EmptyState reasonCode="no_accounts"` with illustration + CTA to connect account |
| Empty — no data for range | `EmptyState reasonCode="no_data_for_range"` |
| Empty — adapter error | `EmptyState reasonCode="adapter_error"` with retry button |
| Empty — scoped to zero rows | `EmptyState reasonCode="no_data_for_scope"` |

Empty states use the `reasonCode` prop already added by synthesis (FP-CC-01).

### Accessibility (WCAG AA)

- Every chart has an `AccessibleTableToggle` button that switches between chart view and a semantically equivalent `<table>` with the same data
- Color is never the sole encoding: bars use pattern fills as secondary encoding, lines use distinct `strokeDasharray`
- Pie/donut segments use both color and a center label + legend with values
- Bubble charts encode a third dimension by size AND a fourth by shape (circle vs triangle)
- All interactive elements have `role`, `aria-label`, `tabIndex`
- Tooltips are keyboard-reachable via arrow-key focus on data points

### Palette tokens (existing — do not add new unless noted)

```ts
// frontend/src/styles/chartTheme.ts
chartPalette = ['#2563eb', '#f97316', '#0ea5e9', '#10b981', '#9333ea', '#f43f5e']
// Index assignments:
// 0 → meta / facebook / primary
// 1 → google_ads / secondary
// 2 → instagram / accent-blue
// 3 → conversions / green
// 4 → audience_network / purple
// 5 → alert / red
```

Platform tokens to codify in Sprint 1:
```ts
PLATFORM_CHART_TOKENS = {
  meta_ads:    chartPalette[0],   // #2563eb
  google_ads:  chartPalette[1],   // #f97316
  peer_avg:    'rgba(148,163,184,0.5)',  // dashed, faded
}
```

### Export behavior

Every `DataTable` component has a "Download CSV" button that serializes the currently-visible (filtered) rows. Filename convention: `{page-slug}-{date-range}.csv`. No backend call — pure client-side CSV generation via `blob:` URL.

### Print / PDF

No new print stylesheet needed. The existing app ships no print CSS. Mark as a deferred non-goal unless product requests it.

---

## Sprint 1 — Foundations (Shared Viz Kit)

**Duration target:** 1 sprint (1–2 weeks)  
**Owner:** Frontend / Design-viz coder agent

### Deliverables

| Component | File path | Size |
|-----------|-----------|------|
| `KpiTile` | `frontend/src/components/viz/KpiTile.tsx` | S |
| `TrendLine` | `frontend/src/components/viz/TrendLine.tsx` | M |
| `Sparkline` | `frontend/src/components/viz/Sparkline.tsx` | XS |
| `DistributionBar` | `frontend/src/components/viz/DistributionBar.tsx` | S |
| `BubbleScatter` | `frontend/src/components/viz/BubbleScatter.tsx` | M |
| `PieComposition` | `frontend/src/components/viz/PieComposition.tsx` | S |
| `DataTable` | `frontend/src/components/viz/DataTable.tsx` | M |
| `EmptyState` (extend existing) | `frontend/src/components/EmptyState.tsx` | XS |
| `ChartSkeleton` | `frontend/src/components/viz/ChartSkeleton.tsx` | S |
| `AccessibleTableToggle` | `frontend/src/components/viz/AccessibleTableToggle.tsx` | S |
| `PeerAvgLine` (sub-component) | `frontend/src/components/viz/PeerAvgLine.tsx` | XS |
| Storybook stories | `frontend/src/components/viz/*.stories.tsx` | S |

### Definition of done

- All components render in Storybook with default, loading, empty, and error states
- Axe accessibility check passes in Storybook for every story
- `DataTable` CSV export produces a correct `.csv` when snapshot-tested
- `AccessibleTableToggle` is keyboard-operable (tab + enter/space)
- `TrendLine` renders peer average line when `peerData` prop is provided
- vitest coverage >= 80% for each component
- No new Recharts dependency added

---

### KpiTile

**Props:**
```ts
interface KpiTileProps {
  label: string
  value: number | null
  format: 'currency' | 'number' | 'percent' | 'rate'
  currency?: string          // default 'JMD'
  change?: number | null     // period-over-period delta as decimal (0.12 = +12%)
  isLoading?: boolean
  isFaded?: boolean          // for tiles outside current filter scope
  reasonCode?: string        // passed through to EmptyState if value is null
}
```

**Data binding:** caller maps `payload.metrics.*` fields to individual tiles.

**Interactions:** hover shows tooltip with raw value + period label. No click.

**Empty state:** shows `--` and faded background when `value === null`.

**Loading state:** shimmer rectangle 100% wide × 80px tall.

**A11y:** `role="figure"` + `aria-label="{label}: {formatted_value}"`.

**Test:** snapshot renders for each `format`, loading state, null value.

---

### TrendLine

**Props:**
```ts
interface TrendLineProps {
  data: Array<{ date: string; [seriesKey: string]: number | string }>
  series: Array<{ key: string; label: string; color: string; dashed?: boolean }>
  peerData?: Array<{ date: string; value: number }>  // renders as faded dashed line
  yFormat?: ChartValueType
  currency?: string
  height?: number         // default 260
  isLoading?: boolean
  emptyReasonCode?: string
}
```

**Interactions:** legend toggle hides/shows individual series. Hover tooltip shows all active series values at that date. Click on data point fires optional `onPointClick(date)` callback.

**Loading state:** two skeleton rectangles (one for legend, one for chart body).

**A11y:** `AccessibleTableToggle` button; table has columns Date + one column per series.

---

### Sparkline

**Props:**
```ts
interface SparklineProps {
  data: Array<{ date: string; value: number }>
  color?: string
  height?: number  // default 40
  showTooltip?: boolean
}
```

Used inline in table cells. No axis labels. No legend.

---

### DistributionBar

Horizontal stacked or grouped bar chart. Used for platform mix, age/gender, channel type.

**Props:**
```ts
interface DistributionBarProps {
  data: Array<{ label: string; value: number; color?: string }>
  showPercent?: boolean      // renders % labels on bars
  yFormat?: ChartValueType
  currency?: string
  isLoading?: boolean
  emptyReasonCode?: string
}
```

**Interactions:** tooltip on hover. Legend below chart.

---

### BubbleScatter

**Props:**
```ts
interface BubbleScatterProps {
  data: Array<{
    id: string
    label: string
    x: number
    y: number
    z: number    // bubble radius dimension
    shape?: 'circle' | 'triangle'  // non-color encoding
    color?: string
  }>
  xLabel: string
  yLabel: string
  zLabel: string
  xFormat?: ChartValueType
  yFormat?: ChartValueType
  isLoading?: boolean
  onBubbleClick?: (id: string) => void
  emptyReasonCode?: string
}
```

**Interactions:** hover tooltip with id, x, y, z values. Click fires `onBubbleClick`.

---

### PieComposition

**Props:**
```ts
interface PieCompositionProps {
  data: Array<{ label: string; value: number; color?: string }>
  innerRadius?: number  // 0 = pie, >0 = donut
  yFormat?: ChartValueType
  currency?: string
  showLegend?: boolean
  isLoading?: boolean
  emptyReasonCode?: string
}
```

**Non-color encoding:** each segment gets a distinct `patternId` cross-hatch in addition to color.

---

### DataTable

**Props:**
```ts
interface DataTableProps<T> {
  columns: ColumnDef<T>[]   // TanStack Table ColumnDef
  data: T[]
  isLoading?: boolean
  onRowClick?: (row: T) => void
  csvFilename?: string
  emptyReasonCode?: string
  pageSize?: number         // default 25
}
```

Built on TanStack Table (already in use). CSV export is client-side. Supports sortable columns, pagination, row click.

---

### ChartSkeleton

**Props:**
```ts
interface ChartSkeletonProps {
  height?: number   // matches target chart height
  rows?: number     // for table skeletons
  variant?: 'line' | 'bar' | 'pie' | 'table' | 'kpi-strip'
}
```

Renders shimmer animation. Shape mimics final chart layout to prevent layout shift.

---

### AccessibleTableToggle

**Props:**
```ts
interface AccessibleTableToggleProps {
  chartNode: ReactNode
  tableNode: ReactNode
  defaultView?: 'chart' | 'table'
}
```

Renders a toggle button (icon only, `aria-label="Switch to table view"`) that swaps chart and table. Both nodes exist in DOM simultaneously; inactive one is `aria-hidden`.

---

### Dependencies

- TanStack Table already in `package.json`
- Recharts already in `package.json`
- `EmptyState.tsx` already exists with `reasonCode` prop

### Risks

- Storybook a11y plugin must be confirmed installed. Check `frontend/.storybook/` for `@storybook/addon-a11y`.
- `DataTable` re-implements some of what existing ad-hoc tables do. Sprint 2–4 should migrate existing tables to use it, but existing tables must not be removed until their page is migrated.

---

## Sprint 2 — Meta Cluster

**Duration target:** 1 sprint  
**Owner:** Frontend coder agent (Meta scope)

### Definition of done

- All Meta routes render with real data from `useMetaStore` / Meta endpoints
- No `/api/metrics/combined/` call fired from `meta/status` or `meta/pages` list
- `account_id` selection from `MetaAccountsPage` propagates correctly to `MetaInsightsDashboardPage` (R7 reconciliation already applied by A4)
- `EmptyState` with correct `reasonCode` for zero-account and zero-data tenants
- vitest: new tests for each new chart component wiring
- Playwright: account row click → insights scoped to that account

---

### meta/accounts — MetaAccountsPage

**Route:** `/dashboards/meta/accounts`  
**Store:** `useMetaStore`  
**File:** `frontend/src/routes/MetaAccountsPage.tsx`

#### Layout

| Block | Chart | Data source |
|-------|-------|-------------|
| KPI strip | 6 tiles: Total Spend, Total Impressions, Total Reach, Avg CTR, Avg CPM, Active Accounts | `payload.metrics.*` from `/api/metrics/combined/?platforms=meta_ads` |
| Trend | `TrendLine` — Spend by day, one series per account | `payload.campaign.trend` (date + spend per account, aggregated client-side) |
| Distribution | `PieComposition` — Spend by objective | `payload.campaign.rows` grouped by `objective` |
| Table | `DataTable` — per-account: Account Name, Spend, Impressions, Reach, CTR, CPM, ROAS | `/api/metrics/combined/?platforms=meta_ads` → `campaign.rows` grouped by account_id |

#### Filtered vs unfiltered account_id

- Unfiltered: TrendLine shows one series per account (up to 6 by palette; remaining grouped as "Other")
- Filtered: TrendLine single series + peer average line

#### Drill-down

Row click in table → navigate to `/dashboards/meta/insights?account_id={id}`

#### Empty state

`reasonCode="no_accounts"` when `accounts.length === 0`; `reasonCode="no_data_for_range"` when rows empty but accounts exist.

#### Loading state

KPI strip: `ChartSkeleton variant="kpi-strip"`. Trend: `ChartSkeleton variant="line" height={260}`. Table: `ChartSkeleton variant="table" rows={8}`.

---

### meta/insights — MetaInsightsDashboardPage

**Route:** `/dashboards/meta/insights`  
**Store:** `useMetaStore`  
**File:** `frontend/src/routes/MetaInsightsDashboardPage.tsx`

#### Layout

| Block | Chart | Data source |
|-------|-------|-------------|
| KPI strip | 5 tiles: Spend, ROAS, CTR, Frequency, CPM | `payload.metrics.*` |
| Trend | `TrendLine` dual-axis — CTR (left) + CPM (right), daily | `payload.campaign.trend` (date, ctr, cpm) |
| Bubble | `BubbleScatter` — x=Spend, y=ROAS, z=Impressions, shape by objective | `payload.campaign.rows` |
| Table | `DataTable` — Campaign Name, Spend, Impressions, CTR, CPM, ROAS, Frequency, Objective | `payload.campaign.rows` |

**Note:** dual-axis `TrendLine` requires an optional `rightYFormat` prop on `TrendLine`. Add this in Sprint 1.

#### Filtered vs unfiltered

- Unfiltered: bubble shows all campaigns across all accounts, color = account
- Filtered: bubble shows only selected account's campaigns, color = objective

#### Drill-down

Bubble click OR table row click → campaign detail (if route exists; else no-op for Sprint 2)

---

### meta/campaigns — MetaCampaignOverviewPage

**Route:** `/dashboards/meta/campaigns`  
**Store:** `useMetaStore`  
**File:** `frontend/src/routes/MetaCampaignOverviewPage.tsx`

#### Layout

| Block | Chart | Data source |
|-------|-------|-------------|
| KPI strip | 4 tiles: Spend, Impressions, Clicks, Conversions | `payload.metrics.*` |
| Funnel | Impressions → Clicks → Conversions (3-step vertical funnel) | Sum from `payload.metrics.*` |
| Bar | `DistributionBar` — Spend by campaign (top 10) | `payload.campaign.rows` sorted by spend, top 10 |
| Table | `DataTable` with inline `Sparkline` per campaign | `payload.campaign.rows` + `payload.campaign.trend` joined on campaign_id |

**Funnel:** Recharts does not have a native Funnel chart. Use Recharts `FunnelChart` + `Funnel` (added in Recharts 2.x — confirm available in v3.7.0). Fallback: render as three stacked `ProgressBar` rows with absolute values and drop-off percentage between steps.

#### Empty state

`reasonCode="no_campaigns"` when `payload.campaign.rows.length === 0`

---

### meta/pages (list) — MetaPagesListPage

**Route:** `/dashboards/meta/pages`  
**Store:** `useMetaStore`  
**File:** `frontend/src/routes/MetaPagesListPage.tsx`

**Endpoint:** `GET /api/integrations/pages/` (list of pages with page_id, name, fan_count, last_synced_at)

#### Layout

Single list/grid — no KPI strip (page-level KPIs are on the detail page):

| Block | Chart | Data source |
|-------|-------|-------------|
| Cards grid | Per-page card: name, thumbnail (if available), fan_count, last_synced_at | `/api/integrations/pages/` |
| Table (toggle) | `DataTable` — Page Name, Fan Count, Last Synced | same |

No analytics charts here. No combined call.

---

### meta/pages/:pageId/overview — MetaPageOverviewPage

**Route:** `/dashboards/meta/pages/:pageId/overview`  
**Store:** `useMetaStore`  
**File:** `frontend/src/routes/MetaPageOverviewPage.tsx`  
**Endpoint:** `GET /api/integrations/pages/:pageId/overview/`

Response shape: `{ kpis[], daily_series, engagement_breakdown, date_preset, since, until }`

Each KPI: `{ metric, value, today_value, prior_value, change_pct }`

#### Layout

| Block | Chart | Data source |
|-------|-------|-------------|
| KPI strip | 4 tiles from `kpis[]` — typically: page_fans (followers), page_impressions, page_engaged_users, reach | `kpis[]` |
| Trend | `TrendLine` — primary_metric daily series | `daily_series[primary_metric]` |
| Engagement breakdown | `PieComposition` — engagement breakdown by type (post type, reaction type, etc.) | `engagement_breakdown[metric]` |
| Posts preview | Not charted here — link to posts page |

No combined call.

#### Empty state

`reasonCode="no_page_data"` when `kpis.every(k => k.value === null)`

---

### meta/pages/:pageId/posts — MetaPagePostsPage

**Route:** `/dashboards/meta/pages/:pageId/posts`  
**Store:** `useMetaStore`  
**File:** `frontend/src/routes/MetaPagePostsPage.tsx`  
**Endpoint:** `GET /api/integrations/pages/:pageId/posts/`

Response shape: `{ results[], page_id, since, until, total_count, page, page_size }`  
Each post: `{ post_id, created_time, media_type, message, thumbnail_url, metrics{} }`

#### Layout

| Block | Chart | Data source |
|-------|-------|-------------|
| KPI summary strip | 3 tiles: Total Posts, Avg Reach, Avg Engagement | computed from `results[]` |
| Post type mix | `PieComposition` — media_type distribution | `results[]` grouped by `media_type` |
| Posts table | `DataTable` — Thumbnail, Message (truncated), Created, Reach, Reactions, Shares, Media Type; click → post detail | `results[]` |

Paginated — `DataTable` pagination uses API offset/limit.

---

### meta/posts/:postId — MetaPostDetailPage

**Route:** `/dashboards/meta/posts/:postId`  
**Store:** `useMetaStore`  
**File:** `frontend/src/routes/MetaPostDetailPage.tsx`  
**Endpoints:** `GET /api/integrations/posts/:postId/` + `GET /api/integrations/posts/:postId/timeseries/`

#### Layout

| Block | Chart | Data source |
|-------|-------|-------------|
| KPI strip | 4 tiles: Reach, Impressions, Reactions, Shares (from `metrics{}`) | `metrics` from post detail |
| Trend | `TrendLine` — metric over time | `timeseries` endpoint results |
| Comments table | `DataTable` — if comment data is available; otherwise suppress block | N/A — no endpoint currently |
| Metadata row | Media type, created time, permalink | `media_type`, `created_time`, `permalink` |

**Note:** No comments endpoint exists. Suppress the comments block for Sprint 2. Mark as `[NEW-ENDPOINT]` in open questions.

---

### Sprint 2 Dependencies

- Sprint 1 kit must be complete before Sprint 2 begins
- `useMetaStore` R7 reconciliation effect is already applied (A4 synthesis)
- `EmptyState.reasonCode` prop is already added (A4 synthesis)

### Sprint 2 Risks

- `payload.campaign.trend` may not include per-account series — it aggregates across all accounts. For multi-series TrendLine on accounts page, client-side grouping by account_id from `campaign.rows` is needed. Verify `campaign.rows` includes `account_id` field. If not, mark `[NEW-ENDPOINT]`.
- FunnelChart availability in Recharts v3.7.0: confirm before Sprint 2 begins. Check `node_modules/recharts/es2015/chart/FunnelChart.js` exists.
- Post comments table: no endpoint exists. Suppress block, add `[NEW-ENDPOINT]` note.

---

## Sprint 3 — Google Ads Cluster

**Duration target:** 1 sprint  
**Owner:** Frontend coder agent (Google Ads scope)

### Definition of done

- All Google Ads workspace tabs render charts bound to correct endpoints
- `platforms=google_ads` sent on every combined call from these routes (B1 fix already applied by A4)
- `customer_id` seeded from global store on workspace mount (B2 fix already applied)
- Back-link from campaign detail uses workspace tab URL (B3 fix already applied)
- All charts have `EmptyState` + loading skeleton
- vitest: chart binding tests for each tab
- Playwright: tab navigation preserves `customer_id` query param

---

### google-ads/overview — GoogleAdsExecutivePage (Workspace Overview tab)

**Route:** `/dashboards/google-ads` → Overview tab  
**Store:** workspace-local + `useDashboardStore`  
**Endpoint:** `GET /api/google-ads/executive/` (returns metrics, comparison, pacing, movers, trend, by_channel, alerts_summary, governance_summary, top_insights)

The executive endpoint is the primary data source for this tab.

#### Layout

| Block | Chart | Fields |
|-------|-------|--------|
| KPI strip | 5 tiles: Cost, Conversions, CPA, ROAS, Impression Share | `metrics.{spend, conversions, cpa, roas}` + IS from `metrics.impression_share` if available |
| Trend | `TrendLine` dual-axis — Cost (left) + Conversions (right) | `trend[]` → date, spend, conversions |
| Channel pie | `PieComposition` — Cost by channel_type | `by_channel[]` → channel_type, spend |
| Insights cards | 3 alert insight cards (not a Recharts chart — plain card component) | `top_insights[]` + `alerts_summary` |
| Governance row | 3 stat chips: Recent Changes (7d), Active Recommendations, Disapproved Ads | `governance_summary.*` |

No drill-down table at overview level — link to Campaigns tab.

**[NEW-ENDPOINT] note:** Impression Share (`impression_share`) is not confirmed in the executive payload. Defer IS tile until verified or endpoint extended.

---

### google-ads/campaigns — GoogleAdsCampaignsPage

**Route:** `/dashboards/google-ads` → Campaigns tab  
**Endpoint:** `GET /api/google-ads/campaigns/`

Each row: `campaign_id, campaign_name, campaign_status, channel_type, spend, impressions, clicks, conversions, cpa, roas, ctr`

#### Layout

| Block | Chart | Fields |
|-------|-------|--------|
| KPI strip | 4 tiles: Total Cost, Total Conversions, Avg CPA, Avg ROAS | aggregated from rows |
| Bubble | `BubbleScatter` — x=Cost, y=Conv Rate (conv/clicks), z=Impressions, shape=channel_type | `campaign rows` |
| Trend | `TrendLine` — Cost by day (top 5 campaigns) | Requires date-series — **[NEW-ENDPOINT]** if campaign daily series not available from this endpoint. Fallback: suppress trend, show bar chart of spend by campaign instead |
| Table | `DataTable` — Campaign Name, Status chip, Channel, Cost, Clicks, Conv, CPA, ROAS; click → campaign detail | `campaign rows` |

**Fallback for trend:** Use `DistributionBar` — Top 10 Campaigns by Spend — if no daily series available.

#### Status chips

`campaign_status` values (ENABLED, PAUSED, REMOVED) rendered as colored chips in the table: green / yellow / red — using existing Tailwind classes.

---

### google-ads/search — GoogleAdsKeywordsPage / GoogleAdsSearchTermsPage

**Routes:** `/dashboards/google-ads` → Search tab (covers keywords + search terms)  
**Endpoints:** `GET /api/google-ads/keywords/`, `GET /api/google-ads/search-terms/`

Keyword row fields: `keyword_text, match_type, criterion_status, quality_score, impressions, clicks, conversions, cpa, ctr, cpm`  
Search term row fields: `search_term, impressions, clicks, conversions, cpa, ctr`

#### Layout

| Block | Chart | Fields |
|-------|-------|--------|
| KPI strip | 3 tiles: Total Keywords, Avg Quality Score, Top Keyword Conv | from keyword rows |
| Scatter | `BubbleScatter` — x=Quality Score, y=CPC (spend/clicks), z=Impressions, one point per keyword | `keyword rows` |
| Bar | `DistributionBar` — Top 10 Search Terms by Conversions | `search_term rows` sorted by conversions |
| Keyword table | `DataTable` — Keyword, Match Type, Status, QS, Impressions, Clicks, Conv, CPA | `keyword rows` |
| Search terms table | `DataTable` — Search Term, Impressions, Clicks, Conv, CPA | `search_term rows` |

---

### google-ads/assets — GoogleAdsAssetsPage

**Route:** `/dashboards/google-ads` → Assets tab  
**Endpoint:** `GET /api/google-ads/assets/`

Asset row fields: `asset_type, asset_id, impressions, clicks, conversions, cpa, ctr, policy_approval_status`

#### Layout

| Block | Chart | Fields |
|-------|-------|--------|
| KPI strip | 3 tiles: Total Assets, Disapproved Count, Top Asset Conv | from rows |
| Asset type distribution | `PieComposition` — Count by asset_type | `rows` grouped by `asset_type` |
| Performance table | `DataTable` with inline `Sparkline` per asset — Asset Type, Asset ID, Impressions, Clicks, Conv, CPA, Status chip | `rows` |

**Note:** Per-asset sparkline requires date-series per asset — not available from current endpoint. Suppress sparkline column; add `[NEW-ENDPOINT]` note. Render table without sparklines.

---

### google-ads/pmax — GoogleAdsPmaxPage

**Route:** `/dashboards/google-ads` → PMax tab  
**Endpoint:** `GET /api/google-ads/pmax-asset-groups/`

Asset group row fields: `asset_group_id, asset_group_name, asset_group_status, spend, impressions, clicks, conversions, cpa, roas`

#### Layout

| Block | Chart | Fields |
|-------|-------|--------|
| KPI strip | 3 tiles: Total Asset Groups, Total Cost, Total Conv | from rows |
| Treemap | Asset group treemap — size=spend, color intensity=ROAS | `rows` → `asset_group_name, spend, roas` |
| Table | `DataTable` — Asset Group, Status, Cost, Impressions, Conv, CPA, ROAS | `rows` |

**Treemap:** Recharts provides `Treemap` component. Use `chartPalette[1]` (orange) with opacity scaled to `roas` value (0–2 range mapped to 0.3–1.0 opacity). This avoids introducing new chart types.

---

### google-ads/conversions — GoogleAdsConversionsPage

**Route:** `/dashboards/google-ads` → Conversions tab  
**Endpoint:** `GET /api/google-ads/conversions-by-action/`

Row fields: `conversion_action_name, conversions, conversion_value, cost_per_conversion`

#### Layout

| Block | Chart | Fields |
|-------|-------|--------|
| KPI strip | 3 tiles: Total Conversions, Total Conv Value, Avg CPA | from rows |
| Funnel | Impressions → Clicks → Conversions (3-step) | Source: aggregate from campaigns endpoint or combined payload |
| Source mix pie | `PieComposition` — Conv by action_name | `rows` grouped by `conversion_action_name` |
| Table | `DataTable` — Action Name, Conversions, Value, CPA | `rows` |

**Funnel source:** Campaign-level totals from `GET /api/google-ads/campaigns/` (sum impressions, clicks, conversions). No new endpoint needed.

---

### google-ads/pacing — GoogleAdsBudgetPage

**Route:** `/dashboards/google-ads` → Pacing tab  
**Endpoint:** `GET /api/google-ads/budget-pacing/`

Pacing fields: `spend_mtd, budget_month, forecast_month_end, over_under, pacing_pct, overspend_risk, underdelivery`  
Campaign budget rows: `campaign_id, campaign_name, campaign_status, channel_type, spend, budget_amount, pacing_pct`

#### Layout

| Block | Chart | Fields |
|-------|-------|--------|
| Gauge ring | Single gauge: MTD pacing % (needle at pacing_pct; red zone > 110%, yellow 80–100%) | `pacing.pacing_pct` |
| KPI strip | 3 tiles: Spend MTD, Budget Month, Forecast Month-End | `pacing.*` |
| Variance bar | `DistributionBar` — Per-campaign spend vs budget (paired bars) | `campaign_rows` |
| Table | `DataTable` — Campaign, Status, Spend, Budget, Forecast, Over/Under, Risk chip | `campaign_rows` |

**Gauge ring:** Recharts `RadialBarChart` with a single bar, domain [0, 1.2], reference lines at 0.8 (under) and 1.1 (over). No new chart type.

---

### google-ads/changes — GoogleAdsChangeLogPage

**Route:** `/dashboards/google-ads` → Changes tab  
**Endpoint:** `GET /api/google-ads/change-events/`

Row fields: `customer_id, change_date_time, user_email, client_type, change_resource_type, resource_change_operation, campaign_id, ad_group_id, ad_id, changed_fields`

#### Layout

| Block | Chart | Fields |
|-------|-------|--------|
| KPI strip | 2 tiles: Total Changes, Changes last 7d | count from rows |
| Changes by type | `DistributionBar` — Count by change_resource_type | `rows` grouped by type |
| Table | `DataTable` — Date/Time, User, Resource Type, Operation, Campaign, Changed Fields; paginated | `rows` |

**No trend chart** — change log is event-based, not time-series. Suppressed to avoid padding.

---

### google-ads/recommendations — GoogleAdsRecommendationsPage

**Route:** `/dashboards/google-ads` → Recommendations tab  
**Endpoint:** `GET /api/google-ads/recommendations/`

Row fields: `customer_id, recommendation_type, resource_name, campaign_id, ad_group_id, dismissed, impact_metadata, last_seen_at`

#### Layout

| Block | Chart | Fields |
|-------|-------|--------|
| KPI strip | 2 tiles: Active Recommendations, Dismissed | count from `dismissed` field |
| Type distribution | `PieComposition` — Count by recommendation_type | `rows` grouped by type |
| Table | `DataTable` — Type, Campaign, Impact, Status chip (Active/Dismissed), Last Seen; "Dismiss" action button if wired | `rows` |

**Dismiss action:** button calls `PATCH /api/google-ads/recommendations/:id/dismiss/` if that endpoint exists. If not, suppress button and mark `[NEW-ENDPOINT]`.

---

### google-ads/reports — GoogleAdsReportsPage

**Route:** `/dashboards/google-ads` → Reports tab  
**Endpoint:** `GET /api/google-ads/exports/` (list) + `POST /api/google-ads/exports/` (create)

#### Layout

| Block | Chart | Fields |
|-------|-------|--------|
| Controls strip | Date range picker + "Generate Report" button | — |
| Export jobs table | `DataTable` — Created, Status chip, Date Range, Download link | export jobs list |

No chart components needed here — this is a workflow page, not analytics. Keep minimal.

---

### Sprint 3 Dependencies

- Sprint 1 shared kit (all components)
- Google Ads `buildCommonParams` fix (B1, already applied)
- Workspace customer_id seeding (B2, already applied)

### Sprint 3 Risks

- `GoogleAdsCampaignsPage` trend daily series: current `/api/google-ads/campaigns/` returns aggregate rows, not a date series. The `TrendLine` for campaigns requires a daily breakdown. Use `/api/google-ads/channels/` as a fallback for a date+channel series. If per-campaign daily series is needed, mark `[NEW-ENDPOINT]`.
- `FunnelChart` in Recharts 3.7.0: confirm availability before Conversions page sprint.
- Recommendations dismiss action: no PATCH endpoint confirmed. Suppress or stub.
- Impression Share metric not confirmed in executive payload. Defer IS tile.

---

## Sprint 4 — Combined + Map + Web

**Duration target:** 1 sprint  
**Owner:** Frontend coder agent (combined/map/web scope)

### Definition of done

- `platforms` page shows both platforms, no cross-platform row leakage (B-PLAT-01 fix confirmed)
- `map` page renders choropleth with parish data
- `web/ga4` and `web/search-console` make no `/combined/` calls
- All charts have `EmptyState` + loading skeleton
- Saved dashboards builder can place any shared kit component into a grid slot

---

### platforms — PlatformDashboard

**Route:** `/dashboards/platforms`  
**Store:** `useDashboardStore`  
**File:** `frontend/src/routes/PlatformDashboard.tsx`  
**Endpoint:** `/api/metrics/combined/?platforms=meta_ads,google_ads`

#### Layout

| Block | Chart | Fields |
|-------|-------|--------|
| KPI strip | 5 tiles: Total Spend, Total Impressions, Total Clicks, Total Conversions, Blended ROAS | `payload.metrics.*` |
| Stacked area trend | `TrendLine` — Spend by platform over time (stacked area mode) | `payload.campaign.trend` split by `platform` field |
| Small-multiples bar | 4 mini `DistributionBar` charts in 2×2 grid — Spend / Impressions / Clicks / Conv each showing Meta vs Google split | `payload.platforms.byPlatform[]` |
| Platform comparison table | `DataTable` — Platform, Spend, Impressions, Clicks, Conversions, CTR, CPM, ROAS | `payload.platforms.byPlatform[]` |

**Stacked area:** `TrendLine` prop `variant="stacked-area"` — renders Recharts `AreaChart` with `stackId` per platform. Add `variant` prop to `TrendLine` in Sprint 1 (mark as needed by Sprint 4).

**account_id unfiltered:** Small-multiples show Meta and Google as two colored bars. Each bar represents the platform total.  
**account_id filtered:** Small-multiples show selected account's platform split vs. peer average account's split.

**B-PLAT-03 deferred:** `platform === 'facebook'` label hardcoding is a known cosmetic gap. Fix in this sprint: normalize platform labels client-side (facebook → Meta, google_ads → Google Ads) using a lookup map in `platformLabels.ts`.

---

### campaigns — CampaignDashboard

**Route:** `/dashboards/campaigns`  
**Store:** `useDashboardStore`  
**File:** `frontend/src/routes/CampaignDashboard.tsx`  
**Endpoint:** `/api/metrics/combined/`

#### Layout

| Block | Chart | Fields |
|-------|-------|--------|
| KPI strip | 4 tiles: Total Spend, Total Clicks, Total Conv, Blended ROAS | `payload.metrics.*` |
| Trend | `TrendLine` — Spend by day, colored by platform | `payload.campaign.trend` |
| Spend by campaign | `DistributionBar` — Top 10 campaigns by spend | `payload.campaign.rows` top 10 by spend |
| Table | `DataTable` with inline `Sparkline` — Campaign, Platform chip, Spend, Clicks, Conv, ROAS, CTR; click → campaign detail | `payload.campaign.rows` |

**Platform toggle:** When user toggles Meta-only via the filter bar, `resolvePlatformFilters()` already filters rows by platform (FP-CAMP-01 applied). Chart reacts automatically.

---

### creatives — CreativeDashboard

**Route:** `/dashboards/creatives`  
**Store:** `useDashboardStore`  
**File:** `frontend/src/routes/CreativeDashboard.tsx`  
**Endpoint:** `/api/metrics/combined/`

#### Layout

| Block | Chart | Fields |
|-------|-------|--------|
| KPI strip | 4 tiles: Total Spend, Total Impressions, Total Clicks, Top Creative Spend | `payload.metrics.*` |
| Scatter | `BubbleScatter` — x=Spend, y=CTR, z=Impressions per creative | `payload.creative[]` (rows with name, spend, impressions, clicks, reach, ctr, cpm) |
| Format mix | `PieComposition` — Impressions by creative format/platform | `payload.creative[]` grouped by `platform` |
| Table | `DataTable` — Creative Name, Platform chip, Spend, Impressions, Clicks, CTR, CPM, Reach | `payload.creative[]` |

**Note:** `payload.creative[]` rows have `name`, `platform`, spend/impressions/clicks/conversions/reach fields. Computed fields (ctr, cpm) must be derived client-side: `ctr = clicks/impressions`, `cpm = spend*1000/impressions`.

---

### budget — BudgetDashboard

**Route:** `/dashboards/budget`  
**Store:** `useDashboardStore`  
**File:** `frontend/src/routes/BudgetDashboard.tsx`  
**Endpoint:** `/api/metrics/combined/`

Budget rows shape: `{ campaignName, spendToDate, budgetAmount (if available), pacing_pct }`  
Note: `budgetAmount` may be absent for Meta campaigns (meta_direct adapter). Render pacing bar only when `budgetAmount > 0`.

#### Layout

| Block | Chart | Fields |
|-------|-------|--------|
| KPI strip | 3 tiles: Total Spend to Date, Total Budget, Overall Pacing % | aggregated from `payload.budget[]` |
| Pacing bar | `DistributionBar` (horizontal) — Spend vs Budget per campaign, paired bars | `payload.budget[]` |
| Trend | `TrendLine` — Cumulative spend vs budget ceiling per day | `payload.campaign.trend` cumulative sum vs budget line (static horizontal reference line) |
| Table | `DataTable` — Campaign, Platform, Spend, Budget, Pacing %, Risk chip | `payload.budget[]` |

**B-BUDG-01 (false empty state) fix is already applied.** `budgetAvailability !== undefined` guard is in place.

---

### audience — AudienceDashboard

**Route:** `/dashboards/audience`  
**Store:** `useDashboardStore`  
**File:** `frontend/src/routes/AudienceDashboard.tsx`  
**Endpoint:** `/api/metrics/combined/`

Audience data lives in `payload.platforms`: `byAge[]`, `byGender[]`, `byAgeGender[]`, `byDevice[]`, `byPlatform[]`

#### Layout

| Block | Chart | Fields |
|-------|-------|--------|
| KPI strip | 4 tiles: Total Reach, Avg Frequency, Top Age Range, Top Device | `payload.metrics.reach`, `payload.metrics.frequency`, derived from `byAge[]`, `byDevice[]` |
| Age distribution | `DistributionBar` — Reach by age range | `payload.platforms.byAge[]` (ageRange, reach) |
| Gender split | `PieComposition` — Reach by gender | `payload.platforms.byGender[]` (gender, reach) |
| Device mix | `DistributionBar` — Impressions by device | `payload.platforms.byDevice[]` (device, impressions) |
| Age × Gender heatmap | **[NEW-ENDPOINT]** — A heatmap of spend by ageRange × gender is desirable but requires a dedicated endpoint returning a 2D matrix. Defer to later sprint. The `byAgeGender[]` data does exist but rendering as a proper heatmap requires a Recharts-compatible approach. For Sprint 4, render `byAgeGender[]` as a grouped `DistributionBar` (age on X, gender as series). | `payload.platforms.byAgeGender[]` |

**B-AUD-01 zero-row guard is already applied.**

---

### map — ParishMapDetail

**Route:** `/dashboards/map`  
**Store:** `useDashboardStore`  
**File:** `frontend/src/routes/ParishMapDetail.tsx`  
**Endpoints:** `/api/metrics/combined/` (parish rows) + `/api/parish-geometry/` (GeoJSON)

Parish rows: `{ parish, spend, impressions, clicks, conversions }`  
GeoJSON: standard FeatureCollection with parish name properties

#### Layout

| Block | Chart | Fields |
|-------|-------|--------|
| KPI strip | 4 tiles: Total Spend (all parishes), Top Parish, Top Parish Spend, Parish Coverage % | from `payload.parish[]` |
| KPI picker | Dropdown: Spend / Impressions / Clicks / Conversions — controls choropleth fill metric | user selection, client-side |
| Choropleth map | Leaflet choropleth — parish polygons filled by selected KPI metric, 5-bucket sequential color scale (monochromatic blue using `chartPalette[0]` alpha steps) | parish rows joined to GeoJSON on parish name |
| Sparkline tooltip | On parish hover: popup with parish name + all 4 KPI values + `Sparkline` of spend over time | parish rows |
| Table | `DataTable` — Parish, Spend, Impressions, Clicks, Conv; click row highlights map polygon | `payload.parish[]` |

**Platform toggle:** B-MAP-01 (platform filter lag in Leaflet layer) is deferred — document as known gap. Workaround: when platform filter changes, force re-render of the entire Leaflet choropleth layer by changing its React key.

**Sparkline in map tooltip:** requires date-series per parish — not in current payload. Suppress sparkline in tooltip for Sprint 4; add `[NEW-ENDPOINT]` note.

**B-MAP-02 EmptyState already applied.**

---

### web/ga4 — GoogleAnalyticsDashboardPage

**Route:** `/dashboards/web/ga4`  
**Store:** own (no `useDashboardStore`, no combined call)  
**File:** `frontend/src/routes/GoogleAnalyticsDashboardPage.tsx`  
**Endpoint:** `GET /api/web/ga4/?start_date=...&end_date=...`

Response: `{ source: 'ga4', status: 'ok', count: N, rows: [{date_day, property_id, channel_group, country, city, campaign_name, sessions, engaged_sessions, conversions, purchase_revenue, engagement_rate, conversion_rate}] }`

#### Layout

| Block | Chart | Fields |
|-------|-------|--------|
| KPI strip | 4 tiles: Total Sessions, Total Conversions, Total Revenue, Avg Engagement Rate | aggregated from `rows` |
| Trend | `TrendLine` — Sessions by day | `rows` aggregated by `date_day` |
| Channel mix | `PieComposition` — Sessions by channel_group | `rows` grouped by `channel_group` |
| Device/Source table | `DataTable` — Channel Group, Sessions, Conv, Revenue, Engagement Rate | `rows` grouped by `channel_group` |

**No combined call.** No platform filter. Date range from own date picker.

---

### web/search-console — SearchConsoleDashboardPage

**Route:** `/dashboards/web/search-console`  
**Store:** own (no combined call)  
**File:** `frontend/src/routes/SearchConsoleDashboardPage.tsx`  
**Endpoint:** `GET /api/web/search-console/?start_date=...&end_date=...`

Response rows: `{ date_day, site_url, country, device, query, page, clicks, impressions, ctr, position }`

#### Layout

| Block | Chart | Fields |
|-------|-------|--------|
| KPI strip | 4 tiles: Total Clicks, Total Impressions, Avg CTR, Avg Position | aggregated from `rows` |
| Trend | `TrendLine` — Clicks + Impressions by day (dual axis) | `rows` aggregated by `date_day` |
| Device mix | `PieComposition` — Clicks by device | `rows` grouped by `device` |
| Top queries table | `DataTable` — Query, Clicks, Impressions, CTR, Avg Position; top 50 by clicks | `rows` grouped by `query` |

**No combined call.** No platform filter.

---

### Saved Dashboards Builder — SavedDashboardPage + DashboardCreate

**Routes:** `/dashboards/saved/:id`, `/dashboards/create`, `/dashboards/library`  
**Files:** `frontend/src/routes/SavedDashboardPage.tsx`, `DashboardCreate.tsx`, `DashboardLibrary.tsx`

The builder uses a grid-snapped slot system. Each slot accepts a shared kit component from Sprint 1.

#### Slot system

- Grid: 12-column, variable row height
- Slot types: `kpi-strip`, `trend-line`, `distribution-bar`, `pie-composition`, `bubble-scatter`, `data-table`, `map`
- Each slot has a `dataBinding` config: `{ endpoint, fields, filters }`
- Saved definition includes `filters.platforms` (FP-SAVED-01 fix already applied)
- On load, `seededRef` pattern prevents re-applying saved filters on every URL change (FP-SAVED-02 fix already applied)

#### Sprint 4 scope

- Render saved dashboards using shared kit components (swap existing ad-hoc charts for kit components)
- Library page heading fix already applied (FP-LIB-01)
- DashboardCreate initial state fix already applied (FP-CREATE-01)
- New Sprint 4 work: wire each saved slot type to the corresponding kit component

---

### Sprint 4 Dependencies

- Sprint 1 (shared kit), Sprint 2 (Meta components), Sprint 3 (Google Ads components)
- `resolvePlatformFilters()` in `useDashboardStore` (FP-CAMP-01, already applied)
- Parish geometry endpoint (`/api/parish-geometry/`) must be accessible

### Sprint 4 Risks

- Leaflet choropleth and Recharts coexist — no conflict expected. Leaflet is already used.
- `byAgeGender[]` grouped bar chart will have 12+ bars per group — may need scrollable chart area.
- Saved dashboard slot `dataBinding` config is not formally typed. Risk of drift between slot types and kit component props. Define a `SlotConfig` TypeScript union type as part of Sprint 4.
- `web/ga4` and `web/search-console` row limit is 500 from the backend. For tenants with high data volume, daily aggregation should happen server-side. The current endpoint already orders by `date_day DESC LIMIT 500` — adequate for sprint 4.

---

## Per-Page Visualization Specification (Quick-Reference Matrix)

| Route | KPI Count | Primary Trend | Distribution | Specialized | Table | No Combined? |
|-------|-----------|--------------|--------------|-------------|-------|-------------|
| `meta/accounts` | 6 | Spend/day/account | Spend by objective (pie) | — | Per-account drill | — |
| `meta/insights` | 5 | CTR+CPM dual-axis | — | Bubble (spend×ROAS×impr) | Campaign rows | — |
| `meta/campaigns` | 4 | — | Spend by campaign (bar) | Funnel impr→click→conv | Campaign + sparklines | — |
| `meta/pages` (list) | — | — | — | Cards grid | Pages table | YES |
| `meta/pages/:id/overview` | 4 | Primary metric daily | Engagement breakdown (pie) | — | — | YES |
| `meta/pages/:id/posts` | 3 | — | Post type mix (pie) | — | Posts | YES |
| `meta/posts/:postId` | 4 | Metric timeseries | — | — | Metadata | YES |
| `google-ads` overview | 5 | Cost+Conv dual-axis | Channel cost (pie) | Insights cards | — | — |
| `google-ads` campaigns | 4 | Cost by campaign (bar) | — | Bubble (cost×conv×impr) | Campaign rows | — |
| `google-ads` search | 3 | — | Top terms by conv (bar) | QS vs CPC scatter | Keywords + terms | — |
| `google-ads` assets | 3 | — | Asset type (pie) | — | Assets | — |
| `google-ads` pmax | 3 | — | — | Treemap (spend×ROAS) | Asset groups | — |
| `google-ads` conversions | 3 | — | Conv by action (pie) | Funnel | Conversion actions | — |
| `google-ads` pacing | 3 | Cum spend vs budget | Spend vs budget/campaign | Gauge ring | Budget rows | — |
| `google-ads` changes | 2 | — | Changes by type (bar) | — | Change log | — |
| `google-ads` recommendations | 2 | — | Type dist (pie) | — | Recommendations | — |
| `google-ads` reports | — | — | — | — | Export jobs | — |
| `platforms` | 5 | Stacked area by platform | 4×mini distribution bars | — | Platform comparison | — |
| `campaigns` | 4 | Spend/day by platform | Spend by campaign (bar) | — | Campaign + sparklines | — |
| `creatives` | 4 | — | Format mix (pie) | Bubble (spend×CTR×impr) | Creatives | — |
| `budget` | 3 | Cum spend vs budget | Spend vs budget (bar) | — | Budget rows | — |
| `audience` | 4 | — | Age dist + device mix | Gender pie + Age×Gender bar | — | — |
| `map` | 4 | — | — | Choropleth + KPI picker | Parish rows | — |
| `web/ga4` | 4 | Sessions/day | Channel mix (pie) | — | Channel breakdown | YES |
| `web/search-console` | 4 | Clicks+Impr dual-axis | Device mix (pie) | — | Top queries | YES |
| `saved/:id` | Variable | Variable | Variable | Variable | Variable | depends |

---

## Cross-Cutting Specifications

### Shared viz kit props API (Sprint 1 summary)

| Component | Key props |
|-----------|----------|
| `KpiTile` | label, value, format, currency, change, isLoading, isFaded, reasonCode |
| `TrendLine` | data, series, peerData, yFormat, currency, height, isLoading, emptyReasonCode, variant |
| `Sparkline` | data, color, height, showTooltip |
| `DistributionBar` | data[{label,value,color}], showPercent, yFormat, currency, isLoading, emptyReasonCode |
| `BubbleScatter` | data[{id,label,x,y,z,shape,color}], xLabel, yLabel, zLabel, xFormat, yFormat, isLoading, onBubbleClick, emptyReasonCode |
| `PieComposition` | data[{label,value,color}], innerRadius, yFormat, currency, showLegend, isLoading, emptyReasonCode |
| `DataTable` | columns, data, isLoading, onRowClick, csvFilename, emptyReasonCode, pageSize |
| `ChartSkeleton` | height, rows, variant |
| `AccessibleTableToggle` | chartNode, tableNode, defaultView |
| `PeerAvgLine` | (sub-component, used inside TrendLine; not standalone) |

### Theme / Palette tokens

No new tokens needed. Extend `chartTheme.ts` with two additions only:

```ts
// Add to chartTheme.ts:
export const PLATFORM_CHART_TOKENS = {
  meta_ads: chartPalette[0],      // #2563eb
  google_ads: chartPalette[1],    // #f97316
  peer_avg: 'rgba(148,163,184,0.45)',
} as const;

export const STATUS_COLORS = {
  ENABLED: '#10b981',   // chartPalette[3]
  PAUSED:  '#f97316',   // chartPalette[1]
  REMOVED: '#f43f5e',   // chartPalette[5]
} as const;
```

### Peer average rendering rule

1. When `account_id` is not set in `useDashboardStore.filters`: render all accounts as separate series.
2. When `account_id` is set:
   a. Fetch or use the already-cached unfiltered payload (the store may hold it from the previous render).
   b. From unfiltered `campaign.rows`, extract all account_ids distinct from the selected one.
   c. For each date in the trend, compute the **median** spend (or selected metric) across those other accounts.
   d. Render as `PeerAvgLine`: dashed, `stroke=PLATFORM_CHART_TOKENS.peer_avg`, `strokeDasharray="4 4"`, `strokeWidth=1.5`, not clickable, labeled "Peer avg" in legend.
   e. If only 1 account exists in tenant, suppress peer avg line entirely.

### Export to CSV

`DataTable` provides client-side CSV export. Implementation:
- Serialize visible (filtered, sorted) rows using `Papa.unparse` OR a minimal manual CSV serializer (avoid adding PapaParse if not already present — check `frontend/package.json`).
- Trigger download via `URL.createObjectURL(new Blob([csv], {type:'text/csv'}))`.
- Filename: `{page-slug}-{start_date}-{end_date}.csv`.

**Check:** if `papaparse` is not in `package.json`, use the manual serializer (escape commas, wrap strings with quotes) rather than adding a new dependency.

### Print / PDF

Deferred. No print stylesheet. Not in scope for these four sprints.

---

## Open Questions for A6

1. **Campaign trend series for Google Ads:** Does `/api/google-ads/campaigns/` return a date-series per campaign? If not, mark `TrendLine` on the Campaigns tab as `[NEW-ENDPOINT]` and plan fallback `DistributionBar`.

2. **Post comments endpoint:** No endpoint for post-level comments exists. The `MetaPostDetailPage` comments table block is suppressed. Mark `[NEW-ENDPOINT: GET /api/integrations/posts/:postId/comments/]` for a future sprint.

3. **Per-asset sparkline data:** `/api/google-ads/assets/` returns aggregate totals only. To render per-asset trend sparklines, a date-series-per-asset endpoint is needed. Mark `[NEW-ENDPOINT: GET /api/google-ads/assets/?group_by=date]`.

4. **Per-parish spend sparkline in map tooltip:** `payload.parish[]` has aggregate totals only, no daily series. Mark `[NEW-ENDPOINT]` or derive from `payload.campaign.trend` if parish is a dimension there.

5. **Impression Share metric:** Not confirmed in `/api/google-ads/executive/` response. A6 should verify and either add it or suppress the IS KPI tile.

6. **Recommendations dismiss endpoint:** No `PATCH /api/google-ads/recommendations/:id/dismiss/` confirmed. A6 must check model / URL registration.

7. **Funnel chart in Recharts 3.7.0:** Confirm `FunnelChart` + `Funnel` are exported from the installed version before Sprint 2/3 coding begins.

8. **PapaParse dependency:** Check `frontend/package.json` for `papaparse`. If absent, use manual CSV serializer in `DataTable`.

9. **CC-02 channels/platforms reconciliation:** The channel checkbox UI and `filters.platforms` remain independent (synthesis deferred). A6 must decide: do coder agents wire channel checkboxes to platform scope, or document the gap in the UI?

10. **FP-UPLOD-01:** `buildMetricsFromUpload` does not filter by `filters.platforms`. Upload page viz is out of scope for these sprints, but note for completeness.

11. **Age × Gender heatmap:** `byAgeGender[]` data is available but a proper 2D heatmap via Recharts is awkward. Sprint 4 uses grouped `DistributionBar` as fallback. A6 should decide whether to spec a custom SVG heatmap cell grid (still within existing tech stack — pure SVG + React) or accept the grouped bar fallback.

---

## Handoff to A6 — Agentic Workflow Spec

### Sprint ordering

```
Sprint 1 (Foundations) ────────────────────────┐
                                                ↓
                              Sprint 2 (Meta)   Sprint 3 (Google Ads)
                              [parallel after Sprint 1 completes]
                                    ↓                    ↓
                              Sprint 4 (Combined + Map + Web)
                              [after Sprint 2 + Sprint 3 complete]
```

Sprints 2 and 3 are fully parallelizable after Sprint 1. Sprint 4 depends on both.

### Coder agent ownership

| Agent | Sprint | Scope |
|-------|--------|-------|
| `frontend-meta` | Sprint 2 | `MetaAccountsPage`, `MetaInsightsDashboardPage`, `MetaCampaignOverviewPage`, `MetaPagesListPage`, `MetaPageOverviewPage`, `MetaPagePostsPage`, `MetaPostDetailPage` |
| `frontend-google` | Sprint 3 | All `google-ads/*` page components, workspace tabs |
| `frontend-combined` | Sprint 4 | `PlatformDashboard`, `CampaignDashboard`, `CreativeDashboard`, `BudgetDashboard`, `AudienceDashboard`, `ParishMapDetail`, `GoogleAnalyticsDashboardPage`, `SearchConsoleDashboardPage`, saved dashboard slot wiring |
| `frontend-kit` | Sprint 1 | All shared viz components, Storybook stories, a11y tests |
| `backend-endpoints` | On-demand | Only if `[NEW-ENDPOINT]` items are approved by A6 |
| `qa` | Post-sprint | Vitest unit tests per component, Playwright e2e per route |

### What A6 coder prompts should include per deliverable

For each component / page:
1. The exact file path
2. The Props API from this document
3. The endpoint + field mapping table from this document
4. The empty / loading state specs
5. A reference to the shared kit component it consumes
6. The acceptance criteria from the sprint's Definition of Done
7. Any open question (from the list above) that must be resolved before coding

### Pre-flight checklist for A6

- [ ] Confirm `FunnelChart` in Recharts 3.7.0
- [ ] Confirm `papaparse` presence or absence in `package.json`
- [ ] Confirm `@storybook/addon-a11y` installed
- [ ] Confirm impression_share field in executive payload
- [ ] Confirm campaign daily series availability from campaigns endpoint
- [ ] Confirm recommendations dismiss endpoint

---

*Absolute path to this file:*
`/Users/thristannewman/ADinsights/artifacts/viz/sprints-plan.md`
