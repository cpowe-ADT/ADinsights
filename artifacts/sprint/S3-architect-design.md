# Sprint 3 — Google Ads Cluster — Architect Design

**Inputs cited:** `/Users/thristannewman/ADinsights/artifacts/viz/sprints-plan.md` (Sprint 3 §542–773 + §24–100 design principles), `/Users/thristannewman/ADinsights/frontend/src/components/viz/index.ts` (shipped viz-kit barrel — 11 primitives), `/Users/thristannewman/ADinsights/artifacts/sprint/S1-final-closeout.md` (viz kit contract), `/Users/thristannewman/ADinsights/artifacts/sprint/S2-final-closeout.md` (Meta pattern: KPI strip → trend → distribution → drill-down table + specialized), `/Users/thristannewman/ADinsights/artifacts/fixes/B1-fix-report.md` (workspace FilterBar + clientId/accountId store unification), `/Users/thristannewman/ADinsights/artifacts/verify/google-verification.json` (A2 Google Ads verifier), plus backend view code at `backend/analytics/google_ads_views.py` and frontend lib `frontend/src/lib/googleAdsDashboard.ts`.

---

## 1. Scope summary

Sprint 3 migrates the ~10-tab Google Ads cluster onto the shipped Sprint-1 viz kit while preserving the `GOOGLE_ADS_WORKSPACE_UNIFIED` feature-flag dual-mode routing. Every tab lives twice:

- **Unified mode** (flag = true): rendered as a sub-section of `GoogleAdsWorkspacePage` at `/dashboards/google-ads?tab=<id>`. Ten tab-section components at `frontend/src/components/google-ads/workspace/tab-sections/` (three exist today — seven must be authored in this sprint).
- **Legacy mode** (flag = false): standalone routes `/dashboards/google-ads/{executive,campaigns,keywords,assets,pmax,conversions,budget,change-log,recommendations,reports}` render one page each at `frontend/src/routes/google-ads/GoogleAds<Name>Page.tsx`.

Implementers must touch **both** surfaces for every in-scope tab, otherwise one of the two flag modes regresses.

---

## 2. File-to-tab mapping (both modes)

| Sprint-3 Tab                                    | Unified-mode file (workspace tab-section)                                                                                 | Legacy-mode file (standalone route)                                                                                      | Legacy route path                        | Notes                                                                                                                                    |
| ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| **Overview**                                    | `frontend/src/components/google-ads/workspace/tab-sections/OverviewTabSection.tsx` (**exists**, 86 LOC, table-only)       | `frontend/src/routes/google-ads/GoogleAdsExecutivePage.tsx` (**exists**, 170 LOC)                                        | `/dashboards/google-ads/executive`       | Both consume summary payload; endpoints differ slightly (`workspace/summary/` adds `alerts_summary`/`governance_summary`/`top_insights`) |
| **Campaigns**                                   | `frontend/src/components/google-ads/workspace/tab-sections/CampaignsTabSection.tsx` (**exists**, 137 LOC, table + drawer) | `frontend/src/routes/google-ads/GoogleAdsCampaignsPage.tsx` (**exists**, 12 LOC thin wrapper → `GoogleAdsDataTablePage`) | `/dashboards/google-ads/campaigns`       | Legacy delegates to shared `GoogleAdsDataTablePage` generic table                                                                        |
| **Search** (keywords + search-terms + insights) | **MUST CREATE** `.../tab-sections/SearchTabSection.tsx` (currently falls through to `GenericTabSection`)                  | `frontend/src/routes/google-ads/GoogleAdsKeywordsPage.tsx` (**exists**, 40 LOC, 3-mode toggle)                           | `/dashboards/google-ads/keywords`        | Unified carries `searchMode` query (`keywords`/`search_terms`/`insights`)                                                                |
| **Assets**                                      | **MUST CREATE** `.../tab-sections/AssetsTabSection.tsx`                                                                   | `frontend/src/routes/google-ads/GoogleAdsAssetsPage.tsx` (12 LOC wrapper)                                                | `/dashboards/google-ads/assets`          | —                                                                                                                                        |
| **Pmax**                                        | **MUST CREATE** `.../tab-sections/PmaxTabSection.tsx`                                                                     | `frontend/src/routes/google-ads/GoogleAdsPmaxPage.tsx` (12 LOC wrapper)                                                  | `/dashboards/google-ads/pmax`            | Needs treemap primitive                                                                                                                  |
| **Conversions**                                 | **MUST CREATE** `.../tab-sections/ConversionsTabSection.tsx`                                                              | `frontend/src/routes/google-ads/GoogleAdsConversionsPage.tsx` (12 LOC wrapper)                                           | `/dashboards/google-ads/conversions`     | —                                                                                                                                        |
| **Pacing**                                      | **MUST CREATE** `.../tab-sections/PacingTabSection.tsx` (currently falls through to `GenericTabSection`)                  | `frontend/src/routes/google-ads/GoogleAdsBudgetPage.tsx` (119 LOC)                                                       | `/dashboards/google-ads/budget`          | Needs gauge primitive                                                                                                                    |
| **Changes**                                     | **MUST CREATE** `.../tab-sections/ChangesTabSection.tsx`                                                                  | `frontend/src/routes/google-ads/GoogleAdsChangeLogPage.tsx` (12 LOC wrapper)                                             | `/dashboards/google-ads/change-log`      | —                                                                                                                                        |
| **Recommendations**                             | **MUST CREATE** `.../tab-sections/RecommendationsTabSection.tsx`                                                          | `frontend/src/routes/google-ads/GoogleAdsRecommendationsPage.tsx` (12 LOC wrapper)                                       | `/dashboards/google-ads/recommendations` | —                                                                                                                                        |
| **Reports**                                     | **MUST CREATE** `.../tab-sections/ReportsTabSection.tsx`                                                                  | `frontend/src/routes/google-ads/GoogleAdsReportsPage.tsx` (151 LOC)                                                      | `/dashboards/google-ads/reports`         | Workflow page, minimal charts                                                                                                            |

**Out-of-scope but reachable:**

- `GoogleAdsChannelsPage.tsx` (redirects to `tab=campaigns` under unified): already folded into Campaigns — do not build a Channels tab. Sprint 3 keeps the legacy file but does not modernize it (listed redirect is stable).
- `GoogleAdsBreakdownsPage.tsx` (redirects to `tab=campaigns`): same — leave it.
- `GoogleAdsCampaignDetailPage.tsx` (legacy standalone, 78 LOC): reachable via `/google-ads/campaigns/:campaignId` in legacy; in unified mode it is replaced by the drawer in `CampaignsTabSection`. Back-link fix (B3) already landed. Not a Sprint-3 deliverable, but the drawer inside `CampaignsTabSection` **is** part of Sprint 3.

**Shared components (edit zone, not new):**

- `frontend/src/components/google-ads/workspace/WorkspaceKpiStrip.tsx` (79 LOC) — currently renders 7 raw metric cards; Sprint 3 must swap to `KpiTile` per the Meta pattern.
- `frontend/src/components/google-ads/workspace/WorkspaceInsightsRail.tsx` (53 LOC) — insight cards, no chart replacement needed; leave as-is but confirm `reasonCode` wiring when summary is empty.
- `frontend/src/components/google-ads/workspace/WorkspaceHeader.tsx` — leave alone (B1 already shrunk it).
- `frontend/src/components/google-ads/GoogleAdsDataTablePage.tsx` (149 LOC) — generic legacy helper. Sprint 3 **may not delete it** (six legacy pages depend on it). Sprint 3 replaces its rendering internals with viz-kit primitives so every legacy wrapper inherits the new look without rewriting the wrappers themselves.
- `frontend/src/routes/google-ads/GoogleAdsLegacyRedirects.tsx` — leave alone.

**New helper module to create:**

- `frontend/src/lib/googleAdsAggregates.ts` — aggregation + derive helpers (KPI rollups from `results[]`, channel rollups, funnel stages from campaign rows, quality-score buckets, IS% presence detector). Mirrors Sprint 2 `metaAggregates.ts` pattern.

---

## 3. Tab-by-tab current state survey

### 3.1 Overview (OverviewTabSection + GoogleAdsExecutivePage)

- **Data hooks:** unified consumes `summary` (`GoogleAdsWorkspaceSummaryResponse`) from `useGoogleAdsWorkspaceData`. Legacy uses `fetchGoogleAdsExecutive` + subscribes to `useDashboardStore.filters`.
- **Current layout:** both render three raw HTML tables (trend, top movers, pacing). No charts. `WorkspaceKpiStrip` renders 6 raw metric cards + "Pacing status" string.
- **Empty/loading/error:** unified shows `<div>Loading overview...</div>` stub; legacy uses `DashboardState` component. Neither uses `reasonCode`.
- **Replace:** tables → KPI strip + dual-axis `TrendLine` + `PieComposition` (by_channel). Keep insight cards (`top_insights`) and governance chips as plain cards (per sprints-plan §574–575).
- **Keep:** `summary.trend`, `summary.movers`, `summary.pacing`, `summary.alerts_summary`, `summary.governance_summary`, `summary.top_insights`.

### 3.2 Campaigns (CampaignsTabSection + GoogleAdsCampaignsPage)

- **Data hooks:** unified pulls `tabStates['campaigns|keywords'].data` (payload: `{count, results: CampaignRow[]}`). Legacy uses `GoogleAdsDataTablePage` → `fetchGoogleAdsList`.
- **Current layout:** unified shows a full table (9 cols) + drawer with raw key/val pairs. Legacy shows a generic auto-column table.
- **Empty/loading/error:** unified: `<div>Loading campaigns...</div>` + `role="alert"`. Legacy: `DashboardState`.
- **Replace:** add 4-tile KPI strip (aggregated from rows), add `BubbleScatter` (x=spend, y=conv rate, z=impressions, shape=channel_type), keep table but wrap in viz-kit `VizDataTable` with status chips + optional inline `Sparkline` column (the latter depends on per-campaign daily-series availability — see §4 audit).
- **Keep:** drawer behavior (`drawerCampaignId`, `onOpenDrawer`, `onCloseDrawer`); table sort/click semantics.

### 3.3 Search (SearchTabSection + GoogleAdsKeywordsPage)

- **Data hooks:** unified falls through to `GenericTabSection` with a `searchMode` toggle. Legacy page has its own 3-mode toggle and reuses `GoogleAdsDataTablePage` for each mode.
- **Current layout:** generic auto-column table, no charts.
- **Empty/loading/error:** generic stubs only; no `reasonCode`.
- **Replace:** 3-tile KPI strip (Total Keywords, Avg Quality Score, Top Keyword Conv), `BubbleScatter` (x=quality_score, y=cpc, z=impressions), `DistributionBar` top 10 search terms by conversions, two `VizDataTable`s (keywords + search terms).
- **Keep:** mode toggle (`keywords` / `search_terms` / `insights`).

### 3.4 Assets (GoogleAdsAssetsPage)

- **Data hooks:** legacy-only today — goes through `GoogleAdsDataTablePage`. Unified renders via `GenericTabSection`.
- **Current layout:** auto-column table with `asset_type, asset_id, impressions, clicks, conversions, cpa, ctr, policy_approval_status` columns.
- **Replace:** 3-tile KPI strip (Total Assets, Disapproved Count, Top Asset Conv) + `PieComposition` count-by-asset_type + `VizDataTable` with status chip column.
- **Degrade:** per-asset `Sparkline` column (sprints-plan §640) → suppress, mark `[NEW-ENDPOINT]` stub, render table without the sparkline column. Confirmed: current endpoint returns per-asset aggregates only, no per-asset daily series.

### 3.5 Pmax (GoogleAdsPmaxPage)

- **Data hooks:** legacy-only today via `GoogleAdsDataTablePage`. Unified via `GenericTabSection`.
- **Current layout:** auto-column table from `asset-groups/` endpoint.
- **Backend shape confirmed** (`google_ads_views.py:1160–1197`): `{customer_id, campaign_id, asset_group_id, asset_group_name, asset_group_status, spend, impressions, clicks, conversions, conversion_value, roas, cpa}`.
- **Replace:** 3-tile KPI strip + **treemap** (size=spend, opacity-scaled-to-ROAS) + `VizDataTable` with status chip column.

### 3.6 Conversions (GoogleAdsConversionsPage)

- **Data hooks:** legacy via `GoogleAdsDataTablePage`; unified via `GenericTabSection`.
- **Current layout:** auto-column table.
- **Row shape:** `conversion_action_name, conversions, conversion_value, cost_per_conversion` per sprints-plan; confirmed in backend `conversions/actions/` endpoint.
- **Replace:** 3-tile KPI strip + `DistributionBar`-as-funnel (Impressions → Clicks → Conversions, sourced from `summary.metrics` or campaigns-tab-cache aggregate — Meta §4.3 pattern) + `PieComposition` (source-mix by action_name) + `VizDataTable`.

### 3.7 Pacing (PacingTabSection + GoogleAdsBudgetPage)

- **Data hooks:** unified via `GenericTabSection` today; legacy via its own `fetchGoogleAdsList('/budgets/pacing/')` variant which returns a single object (not a list).
- **Current layout:** legacy renders a 7-row key/value table; unified falls through to `GenericTabSection` which detects single-object payload and renders a `<dl>`.
- **Payload:** `{month, spend_mtd, budget_month, forecast_month_end, over_under, runway_days, alerts: {overspend_risk, underdelivery}}`. **Important:** `pacing_pct` is NOT at the top of the endpoint (sprints-plan assumed it is). It is present on `summary.pacing.pacing_pct` (workspace summary) per `googleAdsDashboard.ts:21`. Use `spend_mtd / budget_month` as a derive fallback.
- **Replace:** **gauge ring** (pacing %), 3-tile KPI strip (Spend MTD / Budget Month / Forecast Month-End), `DistributionBar` per-campaign variance, `VizDataTable` of per-campaign budget rows. **[NEW-ENDPOINT] note:** per-campaign budget rows are not returned by `/budgets/pacing/` today — only the top-level pacing object. Either source from `/campaigns/` + a client-side `budget_amount` join (requires budget field — not present) or degrade to top-level only and suppress variance bar. **Decision: degrade** — keep only gauge + KPI strip + single-row pacing table until a `/budgets/per-campaign/` endpoint ships.

### 3.8 Changes (GoogleAdsChangeLogPage)

- **Data hooks:** legacy via `GoogleAdsDataTablePage`; unified via `GenericTabSection`.
- **Current layout:** generic auto-column table.
- **Row shape confirmed** (`google_ads_views.py:1384–1395`): `{customer_id, change_date_time, user_email, client_type, change_resource_type, resource_change_operation, campaign_id, ad_group_id, ad_id, changed_fields}`. Paginated (`page, page_size, num_pages`).
- **Replace:** 2-tile KPI strip (Total Changes, Changes last 7d) + `DistributionBar` by `change_resource_type` + `VizDataTable` with severity chips. **Severity derivation:** map `resource_change_operation` → severity (`CREATE` → info, `UPDATE` → warning, `REMOVE` → danger). Sprints-plan called for severity chips but no severity field exists; this is the shipped workaround.

### 3.9 Recommendations (GoogleAdsRecommendationsPage)

- **Data hooks:** legacy via `GoogleAdsDataTablePage`; unified via `GenericTabSection`.
- **Row shape confirmed** (`google_ads_views.py:1427–1438`): `{customer_id, recommendation_type, resource_name, campaign_id, ad_group_id, dismissed, impact_metadata, last_seen_at}`.
- **Replace:** 2-tile KPI strip (Active / Dismissed) + `PieComposition` (count by `recommendation_type`) + `VizDataTable` with status chip (Active/Dismissed), impact summary cell (extracted from `impact_metadata` JSON).
- **Defer:** "Dismiss" PATCH action — no endpoint exists (sprints-plan §740). Suppress button.

### 3.10 Reports (GoogleAdsReportsPage)

- **Data hooks:** `fetchGoogleAdsSavedViews` + `createGoogleAdsExport`.
- **Current layout:** form controls + saved-views table.
- **Replace:** keep controls strip (date range picker + Generate Report), swap the saved-views table to `VizDataTable` with status chip on export job rows. No charts per sprints-plan §756.

---

## 4. Data-availability audit (load-bearing)

Legend: ✅ available | ⚠ derive client-side | ❌ defer (gap). Source column references backend view file:line or frontend lib type.

| Tab             | Required viz                                  | Required fields                                               | Availability                                                                                                                                                                                                                                                                  | Strategy                                                                                                                                                                                                                                                                                                                                                            |
| --------------- | --------------------------------------------- | ------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| Overview        | KPI strip (5: Cost, Conv, CPA, ROAS, **IS%**) | `metrics.{spend, conversions, cpa, roas, impression_share}`   | Cost/Conv/CPA/ROAS ✅ (`summary.metrics.*`); **IS% ❌** — not in `GoogleAdsExecutiveResponse.metrics` nor backend view output (raw SDK has `metrics.search_impression_share` but not exposed via API)                                                                         | **Defer IS% tile to Sprint 5+.** Architect decision: ship a 4-tile strip (drop IS% from sprints-plan), add `[NEW-ENDPOINT]` note in the tab file. Sprints-plan §579 pre-authorized this defer.                                                                                                                                                                      |
| Overview        | Trend dual-axis (Cost + Conv)                 | `trend[].{date, spend, conversions}`                          | ✅ (`summary.trend[]`)                                                                                                                                                                                                                                                        | Direct bind; use `TrendLine` right-axis for conversions                                                                                                                                                                                                                                                                                                             |
| Overview        | Channel pie                                   | `by_channel[]`                                                | ❌ — field not present on `GoogleAdsWorkspaceSummaryResponse` today                                                                                                                                                                                                           | **Derive client-side** from workspace-summary caller — but `by_channel` needs per-channel spend which is not in the summary payload. **Strategy:** fall back to a campaign-level rollup: aggregate `tabStates['campaigns                                                                                                                                            | keywords'].data.results[]`by`channel_type`and feed`PieComposition`. If campaigns tab not yet loaded, prefetch via `loadTab('campaigns')`.      |
| Campaigns       | KPI strip (4)                                 | `sum(spend), sum(conversions), avg(cpa), avg(roas)` from rows | ✅ — campaigns endpoint returns `spend, conversions, cpa, roas` per row                                                                                                                                                                                                       | Derive in `googleAdsAggregates.ts:rollupCampaignKpis()`                                                                                                                                                                                                                                                                                                             |
| Campaigns       | BubbleScatter                                 | x=spend, y=conv/clicks, z=impressions, shape=channel_type     | ✅ all fields on row payload (spend, clicks, impressions, conversions, channel_type)                                                                                                                                                                                          | Direct bind, derive conv_rate = conv/clicks with divide-safe helper                                                                                                                                                                                                                                                                                                 |
| Campaigns       | Trend                                         | per-campaign daily series                                     | ❌ — `/campaigns/` returns aggregates only (backend l.620–670). Daily trend only available on `/campaigns/:id/` detail (backend l.735–758)                                                                                                                                    | **Fallback: `DistributionBar` of top-10 campaigns by spend.** Sprints-plan §599 pre-authorized this fallback. No `[NEW-ENDPOINT]` needed.                                                                                                                                                                                                                           |
| Campaigns       | Table inline Sparkline                        | per-campaign daily series                                     | ❌ (same reason)                                                                                                                                                                                                                                                              | **Suppress sparkline column.** Add `[NEW-ENDPOINT]` note.                                                                                                                                                                                                                                                                                                           |
| Search          | KPI strip                                     | count rows, avg QS, top conversions                           | ✅ — `quality_score` is on keyword rows (backend l.952,981)                                                                                                                                                                                                                   | Derive                                                                                                                                                                                                                                                                                                                                                              |
| Search          | BubbleScatter (x=QS, y=CPC, z=impressions)    | `quality_score, spend/clicks, impressions`                    | ✅ — QS confirmed present; `cpc = spend/clicks` divide-safe                                                                                                                                                                                                                   | Direct bind + derive cpc                                                                                                                                                                                                                                                                                                                                            |
| Search          | Top-10 search-terms bar                       | search-term + conversions                                     | ✅ — separate `/search-terms/` endpoint                                                                                                                                                                                                                                       | Fetch via existing `searchMode` toggle; need prefetch of both modes, or render only the mode the user selected and suppress the other chart. **Strategy:** when `searchMode === 'keywords'`, also fire a background `loadTab('search', 'search_terms')` once for the bar chart; if it fails, hide the bar with a subtle "search-terms data unavailable" reasonCode. |
| Assets          | KPI strip                                     | Total Assets, Disapproved Count, Top Asset Conv               | ✅ — row has `policy_approval_status`                                                                                                                                                                                                                                         | Derive                                                                                                                                                                                                                                                                                                                                                              |
| Assets          | `PieComposition` by asset_type                | ✅                                                            | Direct                                                                                                                                                                                                                                                                        |
| Assets          | per-asset Sparkline                           | per-asset daily series                                        | ❌                                                                                                                                                                                                                                                                            | **Suppress column**, `[NEW-ENDPOINT]` note                                                                                                                                                                                                                                                                                                                          |
| Pmax            | KPI strip                                     | sum(spend), count, sum(conversions)                           | ✅                                                                                                                                                                                                                                                                            | Derive                                                                                                                                                                                                                                                                                                                                                              |
| Pmax            | Treemap                                       | asset_group_name, spend, roas                                 | ✅ (backend l.1186–1196)                                                                                                                                                                                                                                                      | Direct                                                                                                                                                                                                                                                                                                                                                              |
| Pmax            | Table                                         | all asset-group fields                                        | ✅                                                                                                                                                                                                                                                                            | Direct                                                                                                                                                                                                                                                                                                                                                              |
| Conversions     | KPI strip                                     | sum(conversions), sum(conversion_value), avg(cpa)             | ✅ (conv-actions endpoint)                                                                                                                                                                                                                                                    | Derive                                                                                                                                                                                                                                                                                                                                                              |
| Conversions     | Funnel (Impressions→Clicks→Conversions)       | aggregate across campaigns or summary                         | ✅ — use `summary.metrics.{impressions, clicks, conversions}` from the workspace summary already in the store                                                                                                                                                                 | Meta §4.3 pattern, reuse                                                                                                                                                                                                                                                                                                                                            |
| Conversions     | Source-mix pie                                | `conversion_action_name`, `conversions`                       | ✅                                                                                                                                                                                                                                                                            | Direct                                                                                                                                                                                                                                                                                                                                                              |
| Pacing          | Gauge ring (pacing %)                         | `pacing.pacing_pct`                                           | ⚠ — `/budgets/pacing/` returns `spend_mtd, budget_month, forecast_month_end, over_under, runway_days, alerts` — **no `pacing_pct`** at top level; **but** `workspace/summary/` DOES expose `pacing.pacing_pct` (see `GoogleAdsExecutiveResponse.pacing: Record<string, number | null>`)                                                                                                                                                                                                                                                                                                                                                             | **Derive:** if `pacing_pct` not in payload, compute `spend_mtd / budget_month` with divide-safe; if denominator zero, render gauge empty state |
| Pacing          | Variance bar (per-campaign spend vs budget)   | per-campaign budget                                           | ❌ — `campaign_rows` with `budget_amount` not returned by any endpoint                                                                                                                                                                                                        | **Defer**, add `[NEW-ENDPOINT]`. Tab ships without this block.                                                                                                                                                                                                                                                                                                      |
| Pacing          | KPI strip                                     | spend_mtd, budget_month, forecast_month_end                   | ✅                                                                                                                                                                                                                                                                            | Direct                                                                                                                                                                                                                                                                                                                                                              |
| Changes         | KPI strip (total + 7d)                        | count rows + date filter client-side                          | ✅ `change_date_time` on row                                                                                                                                                                                                                                                  | Derive using date comparison                                                                                                                                                                                                                                                                                                                                        |
| Changes         | `DistributionBar` by type                     | `change_resource_type`                                        | ✅                                                                                                                                                                                                                                                                            | Group                                                                                                                                                                                                                                                                                                                                                               |
| Changes         | Table with severity chip                      | **severity field**                                            | ❌ — no severity column                                                                                                                                                                                                                                                       | **Derive:** map `resource_change_operation` (`CREATE`/`UPDATE`/`REMOVE`) → `info`/`warning`/`danger`. Document mapping in helper.                                                                                                                                                                                                                                   |
| Recommendations | KPI strip                                     | count where `dismissed=false`, count where `dismissed=true`   | ✅                                                                                                                                                                                                                                                                            | Derive                                                                                                                                                                                                                                                                                                                                                              |
| Recommendations | `PieComposition` by type                      | `recommendation_type`                                         | ✅                                                                                                                                                                                                                                                                            | Group                                                                                                                                                                                                                                                                                                                                                               |
| Recommendations | Table                                         | all fields + impact summary                                   | ✅ — `impact_metadata` is arbitrary JSON. Render `JSON.stringify` fallback or pluck known keys (`primary_metric`, `impact_percentage`)                                                                                                                                        | Direct                                                                                                                                                                                                                                                                                                                                                              |
| Recommendations | severity chip                                 | `impact_metadata.severity` or derive                          | ⚠ — `impact_metadata` shape is untyped. **Strategy:** try `impact_metadata?.severity` first; otherwise map `recommendation_type` → severity heuristic (budget/bid recommendations → warning; text-ad → info; policy → danger)                                                 |
| Recommendations | Dismiss action                                | PATCH endpoint                                                | ❌                                                                                                                                                                                                                                                                            | **Suppress button**, `[NEW-ENDPOINT]`                                                                                                                                                                                                                                                                                                                               |
| Reports         | Controls strip                                | form state only                                               | ✅                                                                                                                                                                                                                                                                            | Direct                                                                                                                                                                                                                                                                                                                                                              |
| Reports         | Saved-views table                             | `GoogleAdsSavedView[]`                                        | ✅                                                                                                                                                                                                                                                                            | Direct                                                                                                                                                                                                                                                                                                                                                              |
| Reports         | Export-jobs table                             | job list                                                      | ⚠ — only single-job round-trip exists via `fetchGoogleAdsExportStatus(jobId)`. Render latest-created-only (current behavior) and add `[NEW-ENDPOINT]` for a list endpoint.                                                                                                    |

**Key gap callouts for implementers (prominent):**

1. **IS% (Impression Share)** is not in the API. 4-tile strip on Overview instead of 5.
2. **Quality Score** IS available on `/keywords/` — use it for the search bubble scatter.
3. **PMax asset-group shape** IS as-documented in sprints-plan — no surprise.
4. **Change-log rows** have no severity field; derive from `resource_change_operation`.
5. **Recommendations severity** must come from `impact_metadata?.severity` or fall back to type-heuristic. Keep the derivation inside `googleAdsAggregates.ts:deriveRecommendationSeverity()` with a unit test.
6. **Per-campaign daily series + per-asset daily series** not available — suppress sparklines.
7. **Per-campaign budget rows** for pacing variance bar not available — defer.
8. **Reports list endpoint** does not exist — keep latest-job display only.

---

## 5. Specialized primitives decision matrix

Criteria per architect brief: ≥2 consumers or stable shape → add to kit; 1 consumer + irregular → inline. Other criteria: reuseability for Sprint 4/5, a11y investment (toggle + hidden table requires primitive-level plumbing), and Recharts API cost.

| Primitive                                                      | Sprint-3 Consumers  | Expected future consumers                                                                                      | Recharts coverage                                                                                        | Shape irregularity                                                                                                                                                                                                             | **Decision**                                                                                | Justification                                                                                                                                                                                                                                                             |
| -------------------------------------------------------------- | ------------------- | -------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Treemap** (PMax asset-group: size=spend, color=ROAS opacity) | 1 (PMax tab only)   | Sprint 4 CreativeDashboard may reuse for creative-group treemap; Sprint 4 ParishMapDetail may reuse for hexbin | ✅ Recharts 3.7 ships `<Treemap>` (confirmed in `frontend/package.json` + sprints-plan §661)             | Low — stable `{name, value, opacity}` shape                                                                                                                                                                                    | **ADD TO KIT** as `AssetGroupTreemap` — `frontend/src/components/viz/AssetGroupTreemap.tsx` | 1 consumer today + 2 likely consumers in S4. Meta-pattern parity: Sprint 2 hesitated on a funnel primitive and we paid for it with a 3-line `DistributionBar` adapter in every consumer. A11y (hidden table equivalent) and color-token wiring are cheaper to build once. |
| **Gauge ring** (Pacing %, needle-ish radial bar)               | 1 (Pacing tab only) | Sprint 4 Pacing/Budget dashboard reuses; Sprint 5 tenant KPI overview may reuse                                | ⚠ Not a first-class Recharts component — assembled from `<RadialBarChart>` + angle math + reference arcs | Medium — domain `[0, 1.2]`, reference zones at 0.8/1.1, dial needle needs custom polar-coord SVG                                                                                                                               | **ADD TO KIT** as `GaugeRing` — `frontend/src/components/viz/GaugeRing.tsx`                 | Radial-bar plumbing + a11y (aria-valuenow/min/max pattern) is nontrivial. Two guaranteed future consumers. A11y is the deciding vote: a primitive can bake in the `role="meter"` + accessible-table equivalent, whereas an inline version tends to skip both.             |
| **Heat-tinted asset grid** (thumbnails + per-asset sparkline)  | 1 (Assets tab)      | Sprint 4 CreativeDashboard asset grid                                                                          | ❌ No Recharts support — pure CSS grid                                                                   | **Moot — blocked:** per-asset daily series not available (see §4) so the "per-asset Sparkline" piece is suppressed anyway. The remaining "heat-tinted thumbnails" piece degenerates to a list + color-scale on a single metric | **INLINE** (no kit primitive)                                                               | Without sparklines this is a `<ul>` with CSS grid and `resolveSeriesColor(series=0, intensity=metric/max)`. Adding a primitive for a one-consumer degenerate case has zero leverage. Sprint 4 can revisit if a creative grid is commissioned.                             |

### 5a. Viz-kit extension plan (ordered work within Sprint 3)

A mini-step **S3-kit-extension** must land before S3a/S3b/S3c implementers can ship:

- `frontend/src/components/viz/AssetGroupTreemap.tsx` + test + story
- `frontend/src/components/viz/GaugeRing.tsx` + test + story
- `frontend/src/components/viz/index.ts` — append two barrel exports

**Owner:** first task of the S3b-CreativeConv implementer brief (since PMax + Pacing are the consumers that would otherwise block). Estimated 1/2 day. No parallel overlap risk because S3a + S3c don't depend on these primitives.

**Contract for both new primitives:**

- Props mirror Sprint-1 pattern: `isLoading?`, `ariaLabel` required, `height?` with sensible default.
- Both render a hidden `<table>` equivalent inside `.sr-only` (S1 contract).
- Both render a `ChartSkeleton` when `isLoading` per S1 pattern.
- Color comes from `resolveSeriesColor` / `PLATFORM_CHART_TOKENS.google_ads` — no new tokens.
- jest-axe assertion in the primitive test.
- Storybook stories: Default, Loading, Empty, Extreme (treemap: one dominant slice; gauge: 0% and 150% values).

---

## 6. Per-tab design spec

### 6.1 Overview

**Target layout (top → bottom):**

1. `KpiTile` × 4 — Cost, Conversions, CPA, ROAS (IS% deferred)
2. `TrendLine` dual-axis — left axis Cost (currency), right axis Conversions (number); `AccessibleTableToggle` wrapping it
3. `PieComposition` — Cost by channel_type (derive-fallback from campaigns cache)
4. **Insight cards row** — 3 card components (existing `WorkspaceInsightsRail` already renders these; keep)
5. **Governance chips** — 3 chip-style stats (Recent Changes 7d / Active Recommendations / Disapproved Ads) from `summary.governance_summary`
6. No drill-down table (link CTA → Campaigns tab)

**Data transforms (`googleAdsAggregates.ts`):**

```
rollupOverviewKpis(summary) → { spend, conversions, cpa, roas }
buildChannelPie(campaignRows) → [{ name: channel_type, value: sum(spend) }]
deriveTrendSeries(summary.trend) → { data: [{date, spend, conversions}], series: [spend@left, conversions@right] }
```

**Empty-state `reasonCode`s:** `no_customer_selected` (already handled by `GoogleAdsWorkspacePage`), `no_data_for_range` (when `summary.trend` empty), `adapter_error` (on fetch error).

**AccessibleTableToggle placement:** on `TrendLine` and `PieComposition`.

### 6.2 Campaigns

**Target layout:**

1. `KpiTile` × 4 — Total Cost, Total Conversions, Avg CPA, Avg ROAS
2. `BubbleScatter` — x=spend, y=conv_rate, z=impressions, shape={SEARCH: circle, DISPLAY: triangle, VIDEO: square, PERFORMANCE_MAX: diamond, SHOPPING: cross, OTHER: circle}
3. `DistributionBar` top-10 campaigns by spend (replaces the pre-removed `TrendLine` fallback)
4. `VizDataTable` — columns: Campaign (button → drawer), Status chip, Channel, Cost, Clicks, Impr, Conv, CPA, ROAS, (sparkline column suppressed)
5. Drawer (keep existing `<aside>` semantics) — populated from row, no secondary fetch per verifier B3

**Data transforms:**

```
rollupCampaignKpis(rows) → { totalSpend, totalConv, avgCpa, avgRoas }
buildBubblePoints(rows) → [{x, y, z, shape, label}]  // divide-safe conv_rate
buildTopSpendBars(rows) → top 10 by spend
```

**Status chip colors** (using `STATUS_COLORS` from `chartTheme.ts`): ENABLED → green, PAUSED → yellow, REMOVED → red, UNKNOWN → gray.

**Empty-state `reasonCode`s:** `no_campaigns` (zero rows), `no_data_for_range`, `adapter_error`.

**AccessibleTableToggle placement:** on `BubbleScatter` and `DistributionBar`.

### 6.3 Search

**Target layout:**

1. Mode toggle (Keywords / Search Terms / Insights) — existing, keep
2. `KpiTile` × 3 — Total Keywords (mode=keywords), Avg Quality Score, Top Keyword Conversions
3. `BubbleScatter` — x=quality_score (0–10), y=cpc (currency), z=impressions, shape=match_type
4. `DistributionBar` — Top 10 Search Terms by conversions (always fetched via background `loadTab('search','search_terms')` when `searchMode='keywords'`; hidden with reasonCode when unavailable)
5. `VizDataTable` keywords — columns: Keyword, Match Type, Status, QS, Impressions, Clicks, Conv, CPA
6. `VizDataTable` search terms — columns: Search Term, Impressions, Clicks, Conv, CPA (only visible when `searchMode !== 'insights'`)

**Data transforms:**

```
rollupKeywordKpis(rows) → { count, avgQs, topConv }
buildQsCpcBubble(rows) → [{x, y, z, shape, label}]
topSearchTermsByConv(rows) → top 10
```

**Empty-state `reasonCode`s:** `no_keywords` (mode=keywords, 0 rows), `no_search_terms`, `no_search_insights`, `no_data_for_range`.

**AccessibleTableToggle placement:** on `BubbleScatter` and `DistributionBar`.

### 6.4 Assets

**Target layout:**

1. `KpiTile` × 3 — Total Assets, Disapproved Count, Top Asset Conv
2. `PieComposition` — count by asset_type
3. `VizDataTable` — columns: Asset Type, Asset ID, Impressions, Clicks, Conv, CPA, Status chip (from `policy_approval_status`)

**Data transforms:**

```
rollupAssetKpis(rows) → { total, disapproved, topAssetConv }
buildAssetTypePie(rows) → counts by asset_type
```

**Empty-state `reasonCode`s:** `no_assets`, `no_data_for_range`, `adapter_error`.

**AccessibleTableToggle placement:** on `PieComposition`.

### 6.5 PMax

**Target layout:**

1. `KpiTile` × 3 — Total Asset Groups, Total Cost, Total Conv
2. `AssetGroupTreemap` (new kit primitive) — size=spend, opacity mapped from ROAS (clamp `[0,2]` to `[0.3,1.0]`, orange `chartPalette[1]`)
3. `VizDataTable` — columns: Asset Group, Status chip, Cost, Impressions, Conv, CPA, ROAS

**Data transforms:**

```
rollupPmaxKpis(rows) → { totalGroups, totalCost, totalConv }
buildTreemapData(rows) → [{ name, value: spend, opacity: clamp01(roas/2) }]
```

**Empty-state `reasonCode`s:** `no_pmax_groups`, `no_data_for_range`, `adapter_error`.

**AccessibleTableToggle placement:** on `AssetGroupTreemap`.

### 6.6 Conversions

**Target layout:**

1. `KpiTile` × 3 — Total Conversions, Total Conv Value, Avg CPA
2. `DistributionBar`-as-funnel (Impressions → Clicks → Conversions) — sourced from `summary.metrics.{impressions,clicks,conversions}` per §4 audit
3. `PieComposition` — Source mix by conversion_action_name
4. `VizDataTable` — columns: Action Name, Conversions, Value, CPA

**Data transforms:**

```
buildFunnelStages(summaryMetrics) → [{label:'Impressions',value}, {label:'Clicks',value}, {label:'Conversions',value}]
buildConvActionPie(rows) → [{name: conversion_action_name, value: conversions}]
rollupConversionKpis(rows) → { totalConv, totalValue, avgCpa }
```

**Empty-state `reasonCode`s:** `no_conversions`, `no_data_for_range`, `adapter_error`.

**AccessibleTableToggle placement:** on `DistributionBar` (funnel) and `PieComposition`.

### 6.7 Pacing

**Target layout:**

1. `GaugeRing` (new kit primitive) — value = `pacing_pct` (derived if missing), zones: `0–0.8 underdelivery`, `0.8–1.1 on track`, `>1.1 overspend`
2. `KpiTile` × 3 — Spend MTD, Budget Month, Forecast Month-End
3. (Deferred) Variance bar — suppressed per §4 audit
4. Single-row pacing summary table (replaces legacy 7-row key/val `<dl>`)

**Data transforms:**

```
derivePacingPct(pacing) → pacing.pacing_pct ?? safeDiv(spend_mtd, budget_month)
rollupPacingKpis(pacing) → { spendMtd, budgetMonth, forecast }
```

**Empty-state `reasonCode`s:** `no_pacing_data` (both spend_mtd and budget_month are zero/null), `adapter_error`.

**AccessibleTableToggle placement:** on `GaugeRing`.

### 6.8 Changes

**Target layout:**

1. `KpiTile` × 2 — Total Changes, Changes last 7 days
2. `DistributionBar` — count by `change_resource_type`
3. `VizDataTable` — columns: Date/Time, User, Resource Type, Operation severity chip, Campaign, Changed Fields (json-pretty); paginated

**Data transforms:**

```
countChanges7d(rows) → filter by change_date_time ≥ today-7d
groupByResourceType(rows) → counts
deriveChangeSeverity(operation) → 'info' | 'warning' | 'danger'
```

**Empty-state `reasonCode`s:** `no_change_events`, `no_data_for_range`, `adapter_error`.

**AccessibleTableToggle placement:** on `DistributionBar`.

### 6.9 Recommendations

**Target layout:**

1. `KpiTile` × 2 — Active, Dismissed
2. `PieComposition` — count by `recommendation_type`
3. `VizDataTable` — columns: Type, Campaign, Impact summary cell, Severity chip (derived), Status chip (Active/Dismissed), Last Seen; no Dismiss button

**Data transforms:**

```
rollupRecKpis(rows) → { active: count(!dismissed), dismissed: count(dismissed) }
groupByType(rows) → PieComposition data
deriveRecommendationSeverity(row) → row.impact_metadata?.severity ?? typeHeuristic(row.recommendation_type)
formatImpact(row) → extract primary_metric/impact_percentage from impact_metadata JSON
```

**Empty-state `reasonCode`s:** `no_recommendations`, `adapter_error`.

**AccessibleTableToggle placement:** on `PieComposition`.

### 6.10 Reports

**Target layout:**

1. Controls strip — date range picker + "Generate Report" button + Saved View name input (keep existing form)
2. `VizDataTable` export jobs — columns: Created, Status chip (queued/running/completed/failed), Date Range, Download link (only current job today; add `[NEW-ENDPOINT]` note)
3. `VizDataTable` saved views — columns: Name, Description, Shared, Updated

**Data transforms:** none beyond row mapping.

**Empty-state `reasonCode`s:** `no_saved_views`, `no_export_jobs`, `adapter_error`.

**AccessibleTableToggle placement:** none (no chart — tables are already semantic).

---

## 7. Workspace vs legacy coverage confirmation

Every one of the 10 tabs is reachable in both flag modes. No tab has been removed from legacy. Non-scoped legacy routes (`/channels`, `/breakdowns`) redirect in unified mode and remain accessible in legacy mode; Sprint 3 does not modernize them.

**Implementer rule:** for every tab, you touch exactly **two** files from the per-tab row in §2 — the `tab-sections/*.tsx` file for unified mode and the `routes/google-ads/GoogleAds<X>Page.tsx` file for legacy mode. Do not touch `GoogleAdsDataTablePage.tsx` directly except in one coordinated pass (assigned to the brief that touches the most legacy pages — see §8 assignment).

**WorkspaceKpiStrip.tsx ownership:** S3a owns it (Overview depends on it most directly). Single editor — no merge conflicts.

---

## 8. Implementer briefs (S3a, S3b, S3c) — pasteable prompts

### 8.1 S3a-CoreAnalytics brief

```
You are the S3a-CoreAnalytics implementer for Sprint 3.

Inputs to cite on your first line:
- /Users/thristannewman/ADinsights/artifacts/sprint/S3-architect-design.md (authoritative)
- /Users/thristannewman/ADinsights/artifacts/viz/sprints-plan.md §559–624
- /Users/thristannewman/ADinsights/frontend/src/components/viz/index.ts (kit barrel)
- /Users/thristannewman/ADinsights/artifacts/sprint/S2-final-closeout.md (pattern to mirror)

Scope (three tabs, both flag modes each = 6 page files + shared helpers):
1. Overview — OverviewTabSection.tsx + GoogleAdsExecutivePage.tsx
2. Campaigns — CampaignsTabSection.tsx + GoogleAdsCampaignsPage.tsx (legacy delegates to GoogleAdsDataTablePage which you must NOT touch; instead, replace the wrapper's body with a direct fetch + viz-kit render like GoogleAdsBudgetPage.tsx does)
3. Search — SearchTabSection.tsx (create new) + GoogleAdsKeywordsPage.tsx (rewrite, do NOT delegate to GoogleAdsDataTablePage)

Also ship:
- frontend/src/lib/googleAdsAggregates.ts (shared helper module — KPI rollups, bubble builders, funnel stages, channel pie, QS bucket helpers) + googleAdsAggregates.test.ts
- Update frontend/src/components/google-ads/workspace/WorkspaceKpiStrip.tsx to render KpiTile instead of raw metric cards

Boundaries (do NOT touch):
- frontend/src/components/google-ads/workspace/tab-sections/{Assets,Pmax,Conversions,Pacing,Changes,Recommendations,Reports}TabSection.tsx
- frontend/src/routes/google-ads/{GoogleAdsAssetsPage,GoogleAdsPmaxPage,GoogleAdsConversionsPage,GoogleAdsBudgetPage,GoogleAdsChangeLogPage,GoogleAdsRecommendationsPage,GoogleAdsReportsPage}.tsx
- frontend/src/components/google-ads/GoogleAdsDataTablePage.tsx (leave intact for S3-tree migration; the Channels/Breakdowns legacy pages continue to depend on it)
- frontend/src/components/viz/* (except if you need to add new kit primitives — none in S3a scope)
- frontend/src/hooks/useGoogleAdsWorkspaceData.ts (signature is locked per architect §10)

Critical pre-flight:
- Confirm IS% is deferred — Overview ships 4 KPI tiles, not 5 (see architect §4)
- Confirm campaigns daily-trend fallback is `DistributionBar` top-10 (architect §6.2)
- Confirm channel pie data source is the campaigns-tab cache aggregate, not an `overview.by_channel` field (architect §4)
- Preserve CampaignsTabSection drawer behavior and the drawer-via-URL contract (B3/B4 verifier)
- Every chart uses AccessibleTableToggle; every empty surface uses EmptyState + reasonCode
- Preserve the B1-fixed store.filters.accountId/clientId → filters.customerId flow exactly
- Preserve the saved-view restore behavior (CC2 fix in GoogleAdsWorkspacePage.tsx:186–191)

Tests to add/update:
- frontend/src/lib/googleAdsAggregates.test.ts (10+ unit tests for each exported helper)
- frontend/src/routes/google-ads/__tests__/GoogleAdsExecutivePage.test.tsx (add: KpiTile renders, TrendLine renders with dual axes, PieComposition renders, empty-state reasonCode)
- frontend/src/routes/google-ads/__tests__/GoogleAdsCampaignsPage.test.tsx (add: KPI strip, BubbleScatter, DistributionBar top-10 fallback, status chip colors)
- frontend/src/routes/google-ads/__tests__/GoogleAdsKeywordsPage.test.tsx (add: mode toggle preserved, bubble scatter, top-10 search-terms bar, reasonCodes per mode)
- frontend/src/routes/google-ads/__tests__/GoogleAdsWorkspacePage.test.tsx (regression: drawer, B1 customer-id propagation, CC2 saved-view restore — preserve all existing passing tests)
- frontend/src/components/google-ads/workspace/__tests__/WorkspaceKpiStrip.test.tsx (new: KpiTile rendered with each metric, loading + empty paths)

Output artifact path: /Users/thristannewman/ADinsights/artifacts/sprint/S3a-CoreAnalytics.md
Time-box: 1 day.
Closeout format: final file-by-file summary table + test matrix tails (lint, vitest run, build).
```

### 8.2 S3b-CreativeConv brief

```
You are the S3b-CreativeConv implementer for Sprint 3. You OWN the viz-kit extension for this sprint.

Inputs to cite on your first line:
- /Users/thristannewman/ADinsights/artifacts/sprint/S3-architect-design.md (authoritative, §5 for primitives)
- /Users/thristannewman/ADinsights/artifacts/viz/sprints-plan.md §627–682
- /Users/thristannewman/ADinsights/frontend/src/components/viz/TrendLine.tsx (reference pattern for new primitives)
- /Users/thristannewman/ADinsights/artifacts/sprint/S1-final-closeout.md (primitive contract)

Scope:
FIRST, ship the two new viz-kit primitives (mini-step S3-kit-extension):
- frontend/src/components/viz/AssetGroupTreemap.tsx (Recharts <Treemap>, size=value, opacity-scaled)
- frontend/src/components/viz/AssetGroupTreemap.stories.tsx
- frontend/src/components/viz/AssetGroupTreemap.test.tsx (jest-axe + snapshot + hidden-table equivalent)
- frontend/src/components/viz/GaugeRing.tsx (Recharts <RadialBarChart>, domain [0,1.2], zones at 0.8/1.1, role="meter")
- frontend/src/components/viz/GaugeRing.stories.tsx
- frontend/src/components/viz/GaugeRing.test.tsx
- frontend/src/components/viz/index.ts — append both barrel exports

THEN, migrate three tabs (both modes each):
1. Assets — AssetsTabSection.tsx (create) + GoogleAdsAssetsPage.tsx (rewrite, do NOT delegate to GoogleAdsDataTablePage)
2. PMax — PmaxTabSection.tsx (create) + GoogleAdsPmaxPage.tsx (rewrite)
3. Conversions — ConversionsTabSection.tsx (create) + GoogleAdsConversionsPage.tsx (rewrite)

Use helpers from lib/googleAdsAggregates.ts (owned by S3a — wait for the first pass or merge-rebase once shipped). If S3a ships the helpers, just import.

Boundaries (do NOT touch):
- frontend/src/components/google-ads/workspace/tab-sections/{Overview,Campaigns,Search,Pacing,Changes,Recommendations,Reports}TabSection.tsx
- frontend/src/routes/google-ads/{GoogleAdsExecutivePage,GoogleAdsCampaignsPage,GoogleAdsKeywordsPage,GoogleAdsBudgetPage,GoogleAdsChangeLogPage,GoogleAdsRecommendationsPage,GoogleAdsReportsPage}.tsx
- frontend/src/components/google-ads/GoogleAdsDataTablePage.tsx (leave intact)
- frontend/src/components/google-ads/workspace/WorkspaceKpiStrip.tsx (owned by S3a)
- frontend/src/hooks/useGoogleAdsWorkspaceData.ts (locked)

Critical pre-flight:
- Ship the primitives FIRST. Vet them via Storybook + vitest + jest-axe before migrating the consumers.
- Asset per-asset Sparkline: SUPPRESS the column, do not attempt to backfill a per-asset daily fetch.
- Pacing variance bar is out of scope (deferred per §4 audit).
- Conversions funnel reads from `summary.metrics` (the workspace summary), NOT from campaigns rows — ensure the summary fetch ran via `useGoogleAdsWorkspaceData`.

Tests to add/update:
- AssetGroupTreemap.test.tsx, GaugeRing.test.tsx (unit + a11y + non-color encoding assertion)
- GoogleAdsAssetsPage.test.tsx (KpiTile, PieComposition, table status chips, reasonCode=no_assets)
- GoogleAdsPmaxPage.test.tsx (Treemap renders, opacity mapping, hidden-table equivalent)
- GoogleAdsConversionsPage.test.tsx (funnel, source-mix pie, reasonCode=no_conversions)

Output artifact path: /Users/thristannewman/ADinsights/artifacts/sprint/S3b-CreativeConv.md
Time-box: 1 day.
```

### 8.3 S3c-OpsTabs brief

```
You are the S3c-OpsTabs implementer for Sprint 3.

Inputs to cite on your first line:
- /Users/thristannewman/ADinsights/artifacts/sprint/S3-architect-design.md (authoritative, §6.7–6.10)
- /Users/thristannewman/ADinsights/artifacts/viz/sprints-plan.md §685–757

Scope (four tabs, both modes each = 8 page files):
1. Pacing — PacingTabSection.tsx (create) + GoogleAdsBudgetPage.tsx (already has filter-subscribed fetch, rewrite render)
2. Changes — ChangesTabSection.tsx (create) + GoogleAdsChangeLogPage.tsx (rewrite, do NOT delegate to GoogleAdsDataTablePage)
3. Recommendations — RecommendationsTabSection.tsx (create) + GoogleAdsRecommendationsPage.tsx (rewrite)
4. Reports — ReportsTabSection.tsx (create) + GoogleAdsReportsPage.tsx (rewrite — workflow page, keep form controls)

Depends on:
- S3a's lib/googleAdsAggregates.ts (especially deriveChangeSeverity, deriveRecommendationSeverity — add both there, with tests)
- S3b's GaugeRing primitive (Pacing uses it) — do NOT start Pacing tab until GaugeRing is in the kit barrel

Boundaries (do NOT touch):
- frontend/src/components/google-ads/workspace/tab-sections/{Overview,Campaigns,Search,Assets,Pmax,Conversions}TabSection.tsx
- frontend/src/routes/google-ads/{GoogleAdsExecutivePage,GoogleAdsCampaignsPage,GoogleAdsKeywordsPage,GoogleAdsAssetsPage,GoogleAdsPmaxPage,GoogleAdsConversionsPage}.tsx
- frontend/src/components/google-ads/GoogleAdsDataTablePage.tsx
- frontend/src/components/google-ads/workspace/WorkspaceKpiStrip.tsx
- frontend/src/components/viz/* (primitives are already in barrel by S3b)

Critical pre-flight:
- Pacing: derive pacing_pct if missing (spend_mtd / budget_month, divide-safe). GaugeRing in kit is a prereq.
- Pacing variance bar is DEFERRED (§4 — no per-campaign budget data).
- Changes: severity is DERIVED from resource_change_operation (CREATE→info, UPDATE→warning, REMOVE→danger). Add unit tests in googleAdsAggregates.test.ts.
- Recommendations: severity is DERIVED from impact_metadata?.severity ?? typeHeuristic. Dismiss button suppressed.
- Reports: keep the form controls + saved-view create flow; only the saved-views and export-jobs tables are replaced with VizDataTable.
- Changes endpoint is paginated — preserve page/page_size contract.

Tests to add/update:
- GoogleAdsBudgetPage.test.tsx (GaugeRing renders, pacing_pct derived path, reasonCode=no_pacing_data)
- GoogleAdsChangeLogPage.test.tsx (DistributionBar by type, severity chips, pagination preserved)
- GoogleAdsRecommendationsPage.test.tsx (PieComposition, severity derivation branches, no-dismiss-button assertion)
- GoogleAdsReportsPage.test.tsx (VizDataTable for both tables, reasonCode=no_saved_views)

Output artifact path: /Users/thristannewman/ADinsights/artifacts/sprint/S3c-OpsTabs.md
Time-box: 1 day (starts only after S3a's helpers + S3b's GaugeRing are merged).
```

---

## 9. Test strategy per tab

All three implementers must run these gates before closing out:

- `cd frontend && npx vitest run` on their scoped test files
- `cd frontend && npm run lint`
- `cd frontend && npm run build`
- Final pass: `cd frontend && npm test -- --run` (expect ≥629 passing; single pre-existing SavedDashboardPage flake tolerated per S2 closeout §3.4)

Per-tab test additions (preserving all Phase-1B contract tests):

| Tab             | Preserve (must still pass)                                                                                             | Add                                                                                                                       |
| --------------- | ---------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| Overview        | GoogleAdsWorkspacePage B1 tests (B1-fix-report.md §Tests Added); existing GoogleAdsExecutivePage filter-subscribe test | KpiTile×4 rendered; TrendLine dual-axis; PieComposition renders with derived `by_channel`; `reasonCode=no_data_for_range` |
| Campaigns       | Drawer open/close via URL; B4 drawer URL decode (workspace test); row-click semantics                                  | KPI strip; BubbleScatter shape-by-channel; DistributionBar top-10 fallback; status chip color asserts                     |
| Search          | Mode-toggle preserves URL param; existing GoogleAdsKeywordsPage filter fetch                                           | 3 KPI tiles; QS-vs-CPC bubble; top-10 search-terms bar (with fallback reasonCode when prefetch fails)                     |
| Assets          | —                                                                                                                      | KPI strip; PieComposition by asset_type; sparkline column suppressed; status chip                                         |
| PMax            | —                                                                                                                      | AssetGroupTreemap renders + opacity mapped; hidden-table equivalent present; jest-axe clean                               |
| Conversions     | —                                                                                                                      | KPI strip; Funnel-via-DistributionBar ordered stages; source-mix pie                                                      |
| Pacing          | GoogleAdsBudgetPage filter-subscribe regression (NB2 fix)                                                              | GaugeRing renders with derived pacing_pct; 3 KPI tiles; variance bar absent (asserted)                                    |
| Changes         | Pagination contract                                                                                                    | KPI×2; DistributionBar by type; severity chip derivation branches                                                         |
| Recommendations | —                                                                                                                      | KPI×2; PieComposition by type; severity derivation (both branches); dismiss button absent (asserted)                      |
| Reports         | Saved-view create + export-job create flows                                                                            | VizDataTable renders saved views; reasonCode=no_saved_views                                                               |

**Both-modes coverage rule:** the unified-mode test lives in `routes/google-ads/__tests__/GoogleAdsWorkspacePage.test.tsx` (one file drives all ten tab-section components via `?tab=…`) plus optional deep-mount tests under `components/google-ads/workspace/tab-sections/__tests__/` for complex tabs (Pacing, PMax). The legacy-mode test lives per-page under `routes/google-ads/__tests__/GoogleAds<X>Page.test.tsx`. Each implementer owns both.

---

## 10. Risks (≥8)

1. **IS% tile defer creates a data-parity gap** between the product spec (5 tiles) and what ships (4 tiles). Mitigation: file `[NEW-ENDPOINT]` note in the tab file header comment so a future sprint can re-enable without re-architecting. Add a TODO near the KPI strip render.
2. **PMax treemap color encoding is ROAS-driven opacity** — if a tenant has a single dominant asset group with wildly higher ROAS, opacity mapping produces one bright tile and N near-invisible ones. Mitigation: clamp opacity floor at 0.3 (already in spec); consider log-scale if visual QA complains.
3. **Change-log pagination** breaks `DistributionBar`-by-type aggregation if client-side groupBy only sees the current page. Mitigation: document limitation inline (`// NB: aggregation covers current page only`); consider page_size=500 cap for the chart and separate paged table.
4. **Gauge a11y** — `role="meter"` is not universally announced; combine with `role="img"` + `aria-label="Pacing 87%"` + hidden table equivalent. S3b must jest-axe the new primitive. Test an `aria-valuetext` fallback.
5. **Both-modes test cost:** duplicating test surfaces for 10 tabs × 2 modes could balloon the test count from 629 → 700+. Mitigation: unified-mode tests are thin (they mock `useGoogleAdsWorkspaceData` once and cycle tabs); deep chart-binding assertions live on the legacy per-page test which renders the same helpers directly.
6. **Recharts 3.7 `<Treemap>` API** — it accepts `data={[{name, size, children}]}` with `size` as the value key (not `value`); prop names shift between 2.x and 3.x. S3b must confirm before building consumers.
7. **Channel pie derive from campaigns cache** — creates a load-order dependency (Overview needs Campaigns rows). Mitigation: when on Overview tab, fire `loadTab('campaigns','keywords')` in parallel with `loadSummary`. If campaigns cache empty, render a `reasonCode=channel_mix_unavailable` EmptyState inside the pie slot only (Overview page still renders).
8. **Recommendations `impact_metadata` shape drift** — backend returns raw JSON from Google Ads SDK. A change in SDK version could break the severity-derivation code path. Mitigation: wrap access in try/catch + default to `typeHeuristic`; unit test both branches.
9. **Search-terms background prefetch** (when `searchMode='keywords'`) doubles API traffic on every Search-tab visit. Mitigation: cache in `tabCacheRef` (already supported by the hook) and only issue the secondary fetch on first visit per filter window.
10. **Workspace flag flip test regression** — changing `VITE_GOOGLE_ADS_WORKSPACE_UNIFIED` at build-time means E2E must run twice (S3b5 already noted). Add `VITE_GOOGLE_ADS_WORKSPACE_UNIFIED` to the vitest env-file for both values or mock at module level.
11. **GoogleAdsDataTablePage is still referenced** by Channels + Breakdowns (legacy redirects in unified). Sprint 3 must not remove it and must ensure every wrapper that no longer uses it is updated to do direct fetches. Risk: accidental deletion breaks those two legacy routes.
12. **Drawer contract** (B3/B4 verifier) — the campaign drawer URL-encoded colon must survive the VizDataTable refactor. Preserve `onOpenDrawer(campaignId)` contract in the new `VizDataTable` cell renderer.

---

## 11. Out-of-scope

1. Backend endpoints — no new `/api/google-ads/*` routes (IS%, per-campaign budgets, per-asset daily series, recommendations dismiss PATCH, exports list). All flagged `[NEW-ENDPOINT]` inline.
2. Removing legacy Google Ads pages — users may deep-link to them, and the `GOOGLE_ADS_WORKSPACE_UNIFIED=false` rollback path depends on them continuing to work.
3. Extending `useGoogleAdsWorkspaceData` signature — locked per B1 fix; any filter additions must come through `WorkspaceFilters` shape changes (already holds `clientId`).
4. Modernizing `GoogleAdsChannelsPage` / `GoogleAdsBreakdownsPage` — these redirect to existing tabs under unified mode; no migration needed.
5. Modernizing `GoogleAdsCampaignDetailPage` — drawer is the forward path; detail page is a legacy-mode-only relic. Back-link fix (B3) already landed.
6. Playwright E2E coverage for `/dashboards/google-ads` — verifier B5 flagged this; assign to a separate QA sprint.
7. Storybook stories for non-primitive tab sections — only the two new viz-kit primitives (`AssetGroupTreemap`, `GaugeRing`) need stories. Tab-section components are integration-level and don't get stories (per Sprint-2 precedent).
8. Coverage-gate re-enable — still deferred (S1 handoff #4, S2 handoff #8).
9. `prefers-reduced-motion` polyfill — still deferred (S1 handoff #3).
10. Dashboard-builder slot integration for Google Ads widgets — Sprint 4 scope.

---

## 12. Verdict

Architect phase complete. Implementer briefs in §8 are self-contained and pasteable. Load-bearing decisions (IS% defer, treemap + gauge into kit, heat-grid inline, per-campaign daily-series fallback to top-10 bar, pacing variance defer, change-severity derivation, recommendations severity derivation) are all documented with inline justification. Ready for S3-kit-extension → S3a + S3b in parallel → S3c once S3b's GaugeRing lands.
