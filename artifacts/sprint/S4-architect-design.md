# Sprint 4 — Combined + Map + Web + Saved — Architect Design

**Inputs cited:** `/Users/thristannewman/ADinsights/artifacts/viz/sprints-plan.md` (Sprint 4 §775–1010 + §5 design principles §24–100); `/Users/thristannewman/ADinsights/frontend/src/components/viz/index.ts` (13 primitives shipped: KpiTile, TrendLine, Sparkline, PeerAvgLine, ChartSkeleton, DistributionBar, BubbleScatter, PieComposition, VizDataTable, AccessibleTableToggle, EmptyState (re-export), AssetGroupTreemap + `roasToOpacity`, GaugeRing + `derivePacingVariant`); `/Users/thristannewman/ADinsights/artifacts/sprint/S1-final-closeout.md`; `/Users/thristannewman/ADinsights/artifacts/sprint/S2-final-closeout.md`; `/Users/thristannewman/ADinsights/artifacts/sprint/S3-final-closeout.md`; `/Users/thristannewman/ADinsights/artifacts/sprint/phase2-combined-test.md` (C3C GREEN — 12/12 Phase 2 DoD contracts locked); `/Users/thristannewman/ADinsights/artifacts/verify/combined-verification.json` (A3 C1C audit — B-PLAT-01..03, B-CAMP-01/02, B-CREA-01, B-AUD-01, B-BUDG-01, B-MAP-01/02, B-SAVED-01/02 register); top-level `plan.md` **not present** in repo — Sprint 4 inherits R3/R5/R6/R7 risk guardrails from the program-design in `/Users/thristannewman/ADinsights/artifacts/sprint/program-design.md` + `phase2-combined-*.md`. The 10 page files listed in §2 were read in full.

---

## 1. Scope recap

10 pages across 4 clusters. Combined + Map share `useDashboardStore` and the `/api/metrics/combined/` endpoint (platforms-scope aware after Phase 2 FP-PLAT-01/FP-CAMP-01/FP-CREA-01). Web pages have their own hooks and must **never** call `/api/metrics/combined/` (R3 rule). Saved pages compose CampaignDashboard / CreativeDashboard / BudgetDashboard / ParishMapDetail via a template registry.

---

## 2. Page-by-page current state

### 2.1 `PlatformDashboard.tsx` (352 lines)
- **Store**: `useDashboardStore` — subscribes to `platforms`, `loadAll`, `lastSnapshotGeneratedAt`.
- **Phase 2 contracts locked**: FP-PLAT-01 scope reset (in DashboardLayout), FP-PLAT-02 loaded+empty EmptyState at `:233` (`byPlatform.length===0 && byDevice.length===0`), FP-PLAT-03 `formatPlatformLabel` + top-2-by-spend at `:82–145`.
- **Viz rendered today**: StatCard KPI column, `<PlatformComparisonBars>` (custom Recharts), `<DeviceDonut>` (custom), raw `<table className="audienceTable">` for platform×device detail.
- **NOT yet on viz kit**: no `KpiTile`, no `DistributionBar`/`PieComposition`, no `TrendLine`, no `AccessibleTableToggle`, no `VizDataTable`.
- **Data available on `platforms.data`**: `byPlatform[] {platform,spend,impressions,clicks,conversions,reach}`, `byDevice[]`, `byPlatformDevice[]`. **GAP**: no per-platform daily time series (sprints-plan §802 requires this for stacked area).
- **StatusBanner + live-reason wiring** must be preserved; do not regress the `messageForLiveDatasetReason`/`liveDatasetBlocked` branches.

### 2.2 `CampaignDashboard.tsx` (452 lines)
- **Store**: `useDashboardStore` — `campaign`, `campaignRows: state.getCampaignRowsForSelectedParish()` (FP-CAMP-01 already applies `resolvePlatformFilters` server-side at store `:1490–1526`), `parish`, `availability`, `coverage`.
- **Phase 2 contracts locked**: FP-CAMP-01 selector-level platform filter; FP-CAMP-02 consolidated empty-state at `:336–376` (three branches: no data, rows=[] with availability='empty', rows=[] with availability='available'); both scope-transition reset via DashboardLayout.
- **Viz rendered today**: StatCard KPI column (11 tiles w/ inline Sparkline props), `<CampaignTrendChart>` (Recharts wrapper, not `TrendLine`), `<ParishMap>` (Leaflet) gated by `parishCoverage > 0.6`, `<RegionBreakdownTable>`, `<CampaignTable>`.
- **StatCard already carries inline sparkline prop** (legacy, not `Sparkline` from viz kit).
- **Data available**: `campaign.data.summary`, `campaign.data.trend[]` (date,spend,conversions,clicks,impressions,reach? adAccountId?), `campaign.data.rows[]`. Trend has NO `platform` field on points.
- `CampaignPerformanceRow.platform` exists — row-level platform labeling is available for platform chips in the table.

### 2.3 `CreativeDashboard.tsx` (169 lines)
- **Store**: `creative`, `campaign`, `creativeRows: state.getCreativeRowsForSelectedParish()` (FP-CREA-01 applies platforms filter server-side).
- **Phase 2 contracts locked**: FP-CREA-01 platform filter; availability-driven 3-way empty state (`no_matching_filters` / `no_recent_data` / default).
- **Viz rendered today**: StatCard×4 (Creatives/Spend/CTR/Conv./$), `<CreativeTable>` (legacy). No trend, no scatter, no composition.
- **Data available on each row**: `{id,name,campaignId,campaignName,platform,spend,impressions,reach?,clicks,conversions,roas,ctr?,cpc?,cpm?,cpa?,frequency?,thumbnailUrl?}`.
- **Minimal current state** — a full 5-block build-out is required per sprints-plan §842.

### 2.4 `BudgetDashboard.tsx` (181 lines)
- **Store**: `budget`, `campaign`, `budgetRows: state.getBudgetRowsForSelectedParish()` (FP-BUDG-02 applies platforms filter), `availability.budget`.
- **Phase 2 contracts locked**: FP-BUDG-01 `budgetAvailability !== undefined` guard at `:52–54` (prevents demo adapter triggering false empty state).
- **Viz rendered today**: StatCard×6, `<BudgetPacingList>` (legacy list). No pacing bar chart, no cumulative trend, no risk chip.
- **Data available on each row**: `{id,campaignName,platform?,monthlyBudget,windowBudget?,spendToDate,projectedSpend,pacingPercent,startDate?,endDate?}`. Note: `platform?` optional, `windowBudget?` optional → conditional pacing display per sprints-plan §863.

### 2.5 `AudienceDashboard.tsx` (316 lines)
- **Store**: `demographics` (`byAge[]`, `byGender[]`, `byAgeGender[]`).
- **Phase 2 contracts locked**: FP-AUD-01 loaded+empty EmptyState at `:194–210`.
- **Viz rendered today**: StatCard×4, `<AgeGenderPyramid>` (custom), `<GenderDonut>` (custom), `<AgeDistributionBar>` (custom), raw `<table>` for detail.
- **Data gaps vs sprints-plan §885**: sprints-plan references `payload.platforms.byDevice[]` for an Audience device-mix block; the audience **slice** does not carry byDevice (that lives in `platforms.data.byDevice`). Strategy: reuse `platforms.data.byDevice` when scoped device block is requested, OR drop device mix from Audience (it already lives on Platforms page).

### 2.6 `ParishMapDetail.tsx` (218 lines)
- **Store**: `parish`, `selectedParish`, `setSelectedParish`, `selectedMetric`, `campaign.data.summary`, `demographics.data`.
- **Phase 2 contracts locked**: FP-MAP-01 zero-row EmptyState at `:118–132`. Parish-selection drilldown drives Campaign/Creative/Budget selectors (store `:1490–1616`).
- **Viz rendered today**: StatCard×5 KPI row (Spend/Impressions/Clicks/Conversions/ROAS), `<ParishMap>` (Leaflet), `<ParishDetailPanel>`, `<ParishComparisonChart>`, `<RegionBreakdownTable>`.
- **`ParishMap` component** already does: Leaflet `L.GeoJSON` layer + `useRef`, fetches `/analytics/parish-geometry/` then `/dashboards/parish-geometry/` then `/jm_parishes.json` fallback; joins parish rows by normalized name; applies `selectedMetric` fill.
- **Data shape on each `ParishAggregate`**: `{parish,spend,impressions,reach?,clicks,conversions,roas?,ctr?,cpc?,cpm?,cpa?,frequency?,campaignCount?,campaigns?[{id,name}],currency?}`. NO `lat/lng`.
- **sprints-plan §911 requires**: KPI picker dropdown (Spend/Impressions/Clicks/Conversions) controlling fill — a `selectedMetric` mechanism already exists in the store; picker needs to be surfaced inline.

### 2.7 `GoogleAnalyticsDashboardPage.tsx` (233 lines)
- **Store**: local `useState` only (no `useDashboardStore`). Fetches via `fetchGoogleAnalyticsWebRows` from `lib/webAnalytics.ts` (path `/analytics/web/ga4/`).
- **R3 CRITICAL**: confirmed — no `useDashboardStore` import, no `/metrics/combined/` call. **Must be preserved and asserted in tests.**
- **Viz rendered today**: StatCard×4 (Sessions/Conversions/Revenue/Top channel), three inline panels (Latest row / Engagement rate / Conversion rate), raw `<table className="dashboard-table">` with 8 columns. No trend line, no pie.
- **Data available on each row**: `{tenant_id,date_day,property_id,channel_group,country,city,campaign_name,sessions,engaged_sessions,conversions,purchase_revenue,engagement_rate,conversion_rate}`. Backend caps to 500 rows, ordered `date_day DESC`.
- **EmptyState already uses kit `EmptyState`** — good foundation, reasonCode missing.

### 2.8 `SearchConsoleDashboardPage.tsx` (205 lines)
- **Store**: local `useState` only. Fetches via `fetchSearchConsoleWebRows` (path `/analytics/web/search-console/`).
- **R3 CRITICAL**: confirmed — no `useDashboardStore` import, no `/metrics/combined/` call.
- **Viz rendered today**: StatCard×4 (Clicks/Impressions/Avg CTR/Avg Position), raw `<table>` 9 columns. Rows pre-sorted by clicks desc. No trend, no device mix pie.
- **Data available**: `{date_day,site_url,country,device,query,page,clicks,impressions,ctr,position}`.

### 2.9 `SavedDashboardPage.tsx` (197 lines)
- **Store**: `useDashboardStore` (`setFilters`, `setSelectedMetric`, `setSelectedParish`). Fetches `DashboardDefinition` via `getDashboardDefinition(dashboardId)`.
- **Phase 2 contracts locked**: FP-SAVED-01 `normalizeFilters` restores `platforms` field at `:55–58`; FP-SAVED-02 `seededRef` pattern at `:91,133` prevents re-seed on URL changes.
- **Template renderer at `:64–77`**: switches on `template.routeKind` → `CampaignDashboard | CreativeDashboard | BudgetDashboard | ParishMapDetail`. This is the current "layout" system — single whole-page component per template.
- **Known flake**: `SavedDashboardPage.test.tsx > location-search href assertion` — pre-existing cross-file mock-ordering flake (S1 handoff #5 → S2 §6.5 → S3 §7.7). Passes cleanly in isolation. Not introduced by any sprint 1–3.

### 2.10 `DashboardLibrary.tsx` (587 lines) + `DashboardCreate.tsx` (630 lines)
- **Library**: fetches via `fetchDashboardLibrary()`, displays system templates + saved dashboards as cards. Has rename/duplicate/archive/delete. FP-LIB-01 (heading) already applied.
- **Create**: template picker + metadata + FilterBar + widget-checklist + live preview (calls `/metrics/combined/` with hardcoded `platforms: ['meta_ads']` — FP-CREATE-01 at `:149`). Saves via `createDashboardDefinition`.
- Both are already 5-block-shaped; the "builder grid-snap" sprints-plan §980 requirement is **rendering-level** (templates compose kit blocks) not drag-drop authoring.

---

## 3. Data-availability audit

| Page | Required viz (sprints-plan) | Required fields | Availability | Strategy |
|---|---|---|---|---|
| PlatformDashboard | KPI×5 strip (Spend / Impressions / Clicks / Conversions / Blended ROAS) | `payload.metrics.*` totals | **DERIVE** from `byPlatform[].reduce(...)` (no top-level `metrics` on the store slice today) | Sum `byPlatform[]` + guard divide-by-zero for ROAS |
| PlatformDashboard | **Stacked area** trend by platform | per-platform daily series | **GAP** — `CampaignTrendPoint` has NO `platform` field | **DEGRADE** to single-series `TrendLine` (spend-by-day, blended) and note `[NEW-ENDPOINT]` in code. `StackedAreaChart` primitive NOT built this sprint. |
| PlatformDashboard | Small-multiples bar (Spend/Impr/Clicks/Conv) | `byPlatform[]` per KPI | **AVAILABLE** | 2×2 grid of 4 inline `DistributionBar` instances. Do NOT ship a `SmallMultiplesBar` primitive (see §5). |
| PlatformDashboard | Platform-comparison `VizDataTable` | `byPlatform[]` + derived CTR/CPM/ROAS | **AVAILABLE** (derive client-side) | VizDataTable 8 cols: Platform / Spend / Impr / Clicks / Conv / CTR / CPM / ROAS, with `formatPlatformLabel` |
| PlatformDashboard | Device split PieComposition | `byDevice[]` | **AVAILABLE** | Replace `<DeviceDonut>` with `PieComposition` |
| CampaignDashboard | KPI×4 (Spend/Clicks/Conv/Blended ROAS) | `campaign.data.summary` | **AVAILABLE** | Replace StatCard→`KpiTile` |
| CampaignDashboard | Trend (spend by day, colored by platform) | per-platform trend | **GAP** (same as Platforms) | **DEGRADE** to single-series `TrendLine` — platform-color legend only applies if we synthesize per-platform trend from row aggregation (row+trend has NO platform-date join) |
| CampaignDashboard | Top-10 spend DistributionBar | `campaign.data.rows` sorted by spend | **AVAILABLE** | `DistributionBar` from top 10 |
| CampaignDashboard | VizDataTable w/ inline Sparkline | `campaign.data.rows` + per-row trend | per-row trend **GAP** | Legacy `<CampaignTable>` already renders with inline sparkline — keep it as the drill-down table OR migrate to `VizDataTable` with per-row sparkline omitted (same S3 Campaigns precedent) |
| CreativeDashboard | KPI×4 (Spend/Impr/Clicks/Top Creative Spend) | derived from `creativeRows` | **AVAILABLE** | `KpiTile` |
| CreativeDashboard | `BubbleScatter` Spend×CTR×Impr | `creativeRows` | **AVAILABLE** (derive CTR client-side per row) | Shape: triangle when `filters.accountId` set, circle unfiltered (S2 precedent) |
| CreativeDashboard | `PieComposition` by platform (impressions) | `creativeRows` grouped by platform | **AVAILABLE** | Group-by-platform |
| CreativeDashboard | VizDataTable | `creativeRows` | **AVAILABLE** | 8 cols w/ platform chip |
| BudgetDashboard | KPI×3 (Spend to Date / Budget / Pacing %) | `budgetRows` aggregates | **AVAILABLE** | `KpiTile` |
| BudgetDashboard | Horizontal paired-bar pacing | `budgetRows` (spend vs window/monthly budget) | **PARTIAL** — `windowBudget?` optional; `platform?` optional | Render bar only when `budget > 0`; omit bar with hint chip when `budget_unavailable` |
| BudgetDashboard | Cumulative-spend vs ceiling trend | `campaign.data.trend` cumsum vs total budget | **AVAILABLE** (derive) | `TrendLine` with horizontal reference line (flat at totalBudget) — Recharts `<ReferenceLine>` inside TrendLine’s children, or add via existing `peerData` contract |
| BudgetDashboard | VizDataTable w/ risk chip | `budgetRows` + pacing variant | **AVAILABLE** | Reuse `derivePacingVariant` from GaugeRing (already exported from viz kit per S3) for chip tone |
| AudienceDashboard | KPI×4 (Reach / Freq / Top Age / Top Device) | demographics aggregates | **PARTIAL** — Top Device needs `platforms.byDevice[]` (not in demographics slice) | Strategy: read from `platforms.data.byDevice` when present; hide the tile when scope has no device data |
| AudienceDashboard | Age `DistributionBar` | `byAge[]` | **AVAILABLE** | |
| AudienceDashboard | Gender `PieComposition` | `byGender[]` | **AVAILABLE** | |
| AudienceDashboard | Device `DistributionBar` | `platforms.byDevice[]` | **CROSS-SLICE** — requires subscribing to `platforms.data.byDevice` in addition to `demographics.data` | Hide block when `platforms.data` absent |
| AudienceDashboard | Age×Gender heatmap | `byAgeGender[]` | **GAP per sprints-plan §895** — deferred; render grouped `DistributionBar` fallback | Keep existing `<AgeGenderPyramid>` OR replace with grouped `DistributionBar` using `byAgeGender[]` |
| ParishMapDetail | KPI×4 (Spend / Top Parish / Top Parish Spend / Parish Coverage %) | `parish.data` + `availability.parish_map.coveragePercent` | **AVAILABLE** | `KpiTile` |
| ParishMapDetail | Choropleth + KPI picker | Leaflet layer fill driven by `selectedMetric` | **AVAILABLE** — existing `ParishMap` already reads `selectedMetric` | Surface the existing metric picker UI inline above the map |
| ParishMapDetail | Bubble overlay per account location | per-account `{lat,lng}` | **GAP** — no lat/lng in store or API (grep confirmed) | **DEFER** with `[NEW-ENDPOINT]` comment; do NOT spec this block for Sprint 4 |
| ParishMapDetail | Sparkline-in-tooltip | per-parish daily series | **GAP per sprints-plan §923** | Explicit deferral; tooltip shows parish name + 4 KPI values only |
| ParishMapDetail | Parish VizDataTable | `parish.data` | **AVAILABLE** | Replace raw `<RegionBreakdownTable>` with `VizDataTable` OR keep legacy (S3 precedent allows either) — keep legacy this sprint to minimize risk |
| GoogleAnalyticsDashboardPage | KPI×4 (Sessions / Users / Bounce / Avg Session Duration) | rows aggregates | **PARTIAL** — payload has `sessions,engaged_sessions,conversions,purchase_revenue,engagement_rate,conversion_rate` but **no `users`, no `bounce_rate`, no `avg_session_duration`** | Use current KPI set (Sessions / Conversions / Revenue / Top channel or Engagement rate) — sprints-plan §942 KPI names are aspirational; substitute with present fields |
| GoogleAnalyticsDashboardPage | Sessions/day `TrendLine` | `rows` aggregated by `date_day` | **AVAILABLE** | Aggregate client-side |
| GoogleAnalyticsDashboardPage | Channel `PieComposition` | grouped by `channel_group` | **AVAILABLE** | |
| GoogleAnalyticsDashboardPage | `VizDataTable` (by channel) | grouped by `channel_group` | **AVAILABLE** | Replace inline `<table>` |
| SearchConsoleDashboardPage | KPI×4 (Clicks / Impr / Avg CTR / Avg Position) | aggregates | **AVAILABLE** | |
| SearchConsoleDashboardPage | Dual-axis Clicks+Impr `TrendLine` | rows by `date_day` | **AVAILABLE** (dual-axis is already a S2 Insights precedent) | |
| SearchConsoleDashboardPage | Device `PieComposition` | grouped by `device` | **AVAILABLE** | |
| SearchConsoleDashboardPage | Top-queries VizDataTable | top 50 by clicks | **AVAILABLE** | |
| Saved pages | Render a template via grid-snapped slots | each slot a kit primitive | **DERIVED** — `template.routeKind` already dispatches a full-page component. Slot-level rendering is a layout meta-field on the template. | §6 design below |

---

## 4. R3 enforcement plan (web pages)

R3 = "Web pages must not hit `/api/metrics/combined/`". This is non-negotiable per sprints-plan §784 and A3 audit. Current state: PASS (grep confirms no `useDashboardStore` or `metrics/combined/` in either web file). Sprint 4 must add positive test assertions so this can never regress silently.

**Required test additions (S4b-Web, both files):**

1. `frontend/src/routes/__tests__/GoogleAnalyticsDashboardPage.test.tsx` — add:
   ```ts
   // R3: Web page must never call /metrics/combined/
   const fetchSpy = vi.spyOn(window, 'fetch');
   render(<GoogleAnalyticsDashboardPage />);
   await waitFor(() => expect(fetchMock).toHaveBeenCalled());
   const urls = fetchSpy.mock.calls.map(c => String(c[0]));
   expect(urls.some(u => u.includes('/metrics/combined/'))).toBe(false);
   expect(urls.some(u => u.includes('/analytics/web/ga4/'))).toBe(true);
   ```
2. Same assertion in `SearchConsoleDashboardPage.test.tsx` against `/analytics/web/search-console/`.
3. Optional belt-and-braces: assert `useDashboardStore` is never imported. Grep-based test or module-graph eslint rule. **Defer** eslint rule (out of scope for a visualization sprint). Rely on the fetch assertion.
4. Mock `fetchGoogleAnalyticsWebRows` / `fetchSearchConsoleWebRows` in these tests so the fetch spy remains the authoritative R3 signal.

**Implementer must not**:
- Import `useDashboardStore` into either web page
- Import any filter from `useDashboardStore`
- Add a `loadAll` call or any `/metrics/combined/` fetch
- Route through `DashboardLayout`'s FilterBar (GA4 & SC have their own date pickers)

---

## 5. NEW primitives decision matrix

Sprint 3 precedent: add primitive to kit only when ≥2 consumers exist OR when a11y contract (`role="meter"`, etc.) materially differs from existing primitives.

| Candidate primitive | Consumer count (S4) | Future consumers | a11y contract unique? | Decision | Justification |
|---|---|---|---|---|---|
| `StackedAreaChart` | 1 (PlatformDashboard) — **and only if per-platform trend data existed, which it doesn't** | Combined funnel trend (Sprint 5+), revenue-by-source | `role="img"` + sr-only table (same as TrendLine) | **INLINE / DEFERRED** | Data gap degrades the spec to single-series TrendLine. No real consumer. Defer the `TrendLine variant="stacked-area"` extension to a Sprint 5 when the `/metrics/combined/` payload grows per-platform daily series. If Sprint 5 needs it, extend `TrendLine` (per S1c plan) — not a new primitive. |
| `SmallMultiplesBar` | 1 (PlatformDashboard 2×2 grid) | None obvious | Same as DistributionBar | **INLINE** | Four `DistributionBar` instances inside a CSS-grid wrapper. No shared axis/legend because each bar shows a different metric on its own scale. A wrapper primitive would leak unused configuration. Inline pattern (4 Cards in grid) is more testable. |
| `ChoroplethMap` (Leaflet wrapper) | 1 (ParishMapDetail) — also embedded in CampaignDashboard via existing `<ParishMap>` | None in Sprint 5+ road | Leaflet lives outside Recharts; a11y cannot piggyback on SVG role="img" | **INLINE** (existing `<ParishMap>` stays as-is) | `<ParishMap>` is already the Leaflet wrapper. Extending it with a KPI-picker UI is a local enhancement, not a primitive. Adding it to viz-kit creates a hard Leaflet dependency on every viz import graph — undesirable for Storybook a11y runs. |
| Map-tooltip sparkline overlay | 0 (deferred per §3 gap) | Unknown | N/A | **DEFER** | Data gap. |
| `GridSlotLayout` (saved-dashboard builder) | 1 (SavedDashboardPage render path) | None | Not a chart — no role="img" | **INLINE** | A 12-col CSS grid with slot-type switch is not a chart primitive. Lives in `lib/dashboardTemplates.ts` as a `layout` metadata field + a local renderer. |
| `PlatformLegend` helper (color swatches for Meta/Google) | 3 (Platform/Campaign/Creative) | Many | `<ul role="list">` + swatches | **INLINE helper** in `lib/platformLabels.ts` (new file) — not a primitive | Shared `formatPlatformLabel` already exists inside `PlatformDashboard.tsx:86`. Promote to a shared helper (2-function module) referenced by all 5 combined pages. Not a viz-kit primitive — it's a string + color lookup. |

**Net new primitives shipped in Sprint 4: 0.** The kit stays at 13 primitives. All Sprint 4 composition is via existing primitives + 1 shared helper module (`lib/platformLabels.ts`).

---

## 6. Saved dashboards grid-snap design

### 6.1 Schema — backward-compatible

- **`DashboardDefinition.filters` schema**: LOCKED (FP-SAVED-01 contract). Do **not** add new fields. `platforms[]` restore at `SavedDashboardPage.tsx:55–58` preserved.
- **Template registry** (`lib/dashboardTemplates.ts`): extend each `DashboardTemplateDefinition` with an OPTIONAL `layout` field. Unknown / missing → current whole-page render path continues.
  ```ts
  type SlotKind =
    | 'kpi-strip' | 'trend-line' | 'distribution-bar' | 'pie-composition'
    | 'bubble-scatter' | 'data-table' | 'map' | 'custom';
  type SlotConfig = {
    id: string;              // stable key
    kind: SlotKind;
    colSpan: 1|2|3|4|6|8|12; // of 12-col grid
    rowSpan?: 1|2|3;
    title?: string;
    dataBinding?: {          // purely descriptive; actual data comes from store
      slice: 'campaign' | 'creative' | 'budget' | 'platforms' | 'parish' | 'demographics';
      metric?: string;
      groupBy?: string;
      topN?: number;
    };
  };
  type DashboardTemplateDefinition = {
    // existing fields…
    layout?: { slots: SlotConfig[] };  // NEW, OPTIONAL
  };
  ```
- **Backend stays untouched** — `layout` field is frontend-only template metadata. Saved-dashboard payloads already include a `layout` field (Phase 2 shape `{routeKind, widgets}`) but it has no grid semantics; leave it as-is.

### 6.2 Rendering

- `SavedDashboardPage.renderTemplate(template_key)` continues to return the whole-page component (CampaignDashboard / CreativeDashboard / BudgetDashboard / ParishMapDetail). **No change** to the existing four route-kinds.
- **Optional** slot renderer inside SavedDashboardPage: if `template.layout?.slots` is present, render a grid of `<SlotRenderer slot={slot} />`. Sprint 4 does NOT add slots to the shipped 5 templates — this is an extension point only. Sprint 5+ can fill `layout.slots` for new template keys.
- `DashboardCreate.tsx` stays as template-picker + metadata + widget-checklist (NOT drag-drop). This matches sprints-plan §988 "Render saved dashboards using shared kit components" — the kit lives inside the composed page components. sprints-plan §980 slot system is design-level intent, not a Sprint 4 implementation of drag-drop authoring. **Confirm with Raj/Mira if drag-drop authoring is actually in scope — default to NO.**

### 6.3 What does NOT change

- Serialization format (§7 original plan): unchanged
- `FP-SAVED-01` (platforms restore) and `FP-SAVED-02` (seededRef) logic
- `DashboardDefinition.layout` Phase 2 shape
- `DashboardLibrary` filtering UI
- `DashboardCreate` preview logic or `FP-CREATE-01` `platforms: ['meta_ads']` default

---

## 7. Phase 2 contract preservation list

Implementers MUST NOT break these cited file:line contracts:

| # | Contract | File | Lines | Phase-2 fix ID |
|---|---|---|---|---|
| 1 | `formatPlatformLabel` + top-2-by-spend KPI tiles | `frontend/src/routes/PlatformDashboard.tsx` | 82–145 | FP-PLAT-03 |
| 2 | Loaded+empty EmptyState on PlatformDashboard | `frontend/src/routes/PlatformDashboard.tsx` | 231–249 | FP-PLAT-02 |
| 3 | Scope-transition reset: null-scope route resets `filters.platforms=[]`; scoped route sets `filters.platforms=scope` | `frontend/src/routes/DashboardLayout.tsx` | 230–248 | FP-PLAT-01 |
| 4 | Parish-selector platform filter (campaigns) via `resolvePlatformFilters` | `frontend/src/state/useDashboardStore.ts` | 1490–1526 | FP-CAMP-01 |
| 5 | Parish-selector platform filter (creatives) | `frontend/src/state/useDashboardStore.ts` | 1533–1574 | FP-CREA-01 |
| 6 | Parish-selector platform filter (budget) + withFilters | `frontend/src/state/useDashboardStore.ts` | 1355–1380, 1581–1616 | FP-BUDG-02 |
| 7 | Consolidated 3-branch empty state on Campaigns | `frontend/src/routes/CampaignDashboard.tsx` | 336–376 | FP-CAMP-02 |
| 8 | `budgetAvailability !== undefined` false-empty-state guard | `frontend/src/routes/BudgetDashboard.tsx` | 49–54 | FP-BUDG-01 |
| 9 | Loaded+empty EmptyState on Audience | `frontend/src/routes/AudienceDashboard.tsx` | 192–210 | FP-AUD-01 |
| 10 | Loaded+zero-parishes EmptyState on Map | `frontend/src/routes/ParishMapDetail.tsx` | 117–132 | FP-MAP-01 |
| 11 | `normalizeFilters` platforms-restore | `frontend/src/routes/SavedDashboardPage.tsx` | 55–58 | FP-SAVED-01 |
| 12 | `seededRef` one-shot seeding pattern | `frontend/src/routes/SavedDashboardPage.tsx` | 91–99, 130–152 | FP-SAVED-02 |
| 13 | R7 meta-store → dashboard-store accountId reconciliation | `frontend/src/routes/DashboardLayout.tsx` | 263–286 | R7 effect |
| 14 | Live-reason gating + `liveDatasetBlocked` branches on every page | 5 combined pages | local | Phase-1-B |
| 15 | `FP-CREATE-01` — builder preview scoped to `platforms: ['meta_ads']` | `frontend/src/routes/DashboardCreate.tsx` | 145–150 | FP-CREATE-01 |

Every implementer brief (§9) reiterates these as a don't-break list. Targeted vitest suite in §10 confirms 34/34 Phase 2 tests remain green.

---

## 8. Per-page design spec

### 8.1 PlatformDashboard

**5-block layout:**
1. **KPI strip** — `KpiTile × 5`: Total Spend / Total Impressions / Total Clicks / Total Conversions / Blended ROAS (conversions/spend). Derived from `byPlatform[].reduce`. **Keep** existing `formatPlatformLabel`-driven Top Platform / Second Platform tiles as an alternate row IF product wants per-sprints-plan §801 (5 tiles) — decision: go with the sprints-plan §801 set to match cross-page convention.
2. **Primary trend** — `TrendLine` single series (blended spend by day) with `AccessibleTableToggle`. Dashed peer-average line via `PeerAvgLine` when `filters.accountId` is set (S1 pattern). **Stacked-area per-platform deferred** — note inline: `// [NEW-ENDPOINT] Per-platform daily series — sprints-plan §802 deferred (see S4-architect-design §3 gap)`.
3. **Distribution** — 2×2 grid of `DistributionBar` (Spend / Impressions / Clicks / Conversions), each showing 2 bars (Meta, Google Ads) driven by `byPlatform[]`. Colors from `PLATFORM_CHART_TOKENS`.
4. **Composition** — `PieComposition` for device split (replaces `<DeviceDonut>`).
5. **Drill-down table** — `VizDataTable` 8 columns: Platform chip / Spend / Impressions / Clicks / Conversions / CTR / CPM / ROAS. `formatPlatformLabel` on Platform column. CSV export via the kit's built-in button.

**Empty state**: preserve FP-PLAT-02 at a single guard point — `EmptyState reasonCode="no_data_for_range"`.
**Loading**: `ChartSkeleton` per block.
**a11y**: every chart wrapped in `AccessibleTableToggle` (or ships sr-only table intrinsically).
**Platform legend**: shared helper `lib/platformLabels.ts` exports `{formatPlatformLabel, platformColor(platform)}` reading from `PLATFORM_CHART_TOKENS`. Render a legend card above the 2×2 grid.

### 8.2 CampaignDashboard

**5-block layout:**
1. **KPI strip** — `KpiTile × 4`: Spend / Clicks / Conv / Blended ROAS. Simplified from current 11-tile set; keep 11-tile legacy StatCard row available as a feature flag OR collapse to the standard 4 + full metric panel under "Details".
2. **Primary trend** — `TrendLine` single series (spend/day) + `PeerAvgLine` on filter. Platform-colored gradient WOULD need per-platform series — degraded, same `[NEW-ENDPOINT]` note.
3. **Distribution** — `DistributionBar` top-10 campaigns by spend.
4. **Specialized map block** — keep existing `<ParishMap>` (Leaflet) under `parishCoverage > 0.6` guard. Preserve `<RegionBreakdownTable>` as drill-down companion.
5. **Drill-down** — migrate `<CampaignTable>` → `VizDataTable` OR keep legacy per S3 precedent (Campaigns tab kept raw table). **Decision: keep legacy `<CampaignTable>`** this sprint — its inline sparkline + platform chip rendering is bespoke and `VizDataTable`'s cell contract doesn't match.

**Empty state**: preserve FP-CAMP-02 3-branch at `:336–376` — do NOT refactor.
**a11y**: `AccessibleTableToggle` on the new TrendLine and DistributionBar.

### 8.3 CreativeDashboard

**Currently almost empty** — this is a full build-out.

**5-block layout:**
1. **KPI strip** — `KpiTile × 4`: Total Spend / Total Impressions / Total Clicks / Top Creative Spend (= max of `creativeRows.map(r => r.spend)`).
2. **Specialized viz** — `BubbleScatter`: x=spend, y=ctr (derive `clicks/impressions` per row), z=impressions. Shape = triangle when `accountId` filtered, circle when not (S2 Insights precedent). Platform color on each bubble via `PLATFORM_CHART_TOKENS`.
3. **Composition** — `PieComposition` — sum of impressions grouped by `platform` field of `creativeRows`.
4. **Drill-down** — `VizDataTable` 8 cols: Creative / Platform chip / Spend / Impressions / Clicks / CTR / CPM / Reach. CTR/CPM derived client-side.
5. No trend (not in sprints-plan §842 spec).

**Empty state**: preserve existing 3-reason guard at `:122–152`.

### 8.4 BudgetDashboard

**5-block layout:**
1. **KPI strip** — `KpiTile × 3`: Spend to Date / Total Budget / Overall Pacing % (spendToDate / windowBudget_or_monthlyBudget).
2. **Distribution** — Horizontal paired `DistributionBar`: per-campaign Spend vs Budget bars. Skip the paired bar when `windowBudget == null || windowBudget === 0` — render a "Budget unavailable" chip in that row.
3. **Primary trend** — `TrendLine` cumulative spend vs horizontal reference line at total budget. Use Recharts' `<ReferenceLine>` as a child of the primitive's internal chart — OR (safer) render `PeerAvgLine`-style ghost line via existing `peerData` prop at a flat series.
4. **Drill-down** — `VizDataTable` 6 cols: Campaign / Platform chip (when `platform?` present) / Spend / Budget / Pacing % / Risk chip. Risk chip uses `derivePacingVariant(pacingPercent)` from viz kit (S3).
5. No bubble, no pie (not in sprints-plan §862).

**Empty state**: preserve FP-BUDG-01 guard. Extend the 4-branch existing empty-state texts.

### 8.5 AudienceDashboard

**5-block layout:**
1. **KPI strip** — `KpiTile × 4`: Total Reach / Avg Frequency / Top Age Range / Top Device. Top Device requires subscribing to `platforms.data.byDevice` in addition to `demographics.data`; hide the tile (do NOT render `—`) when `platforms.data` absent.
2. **Distribution (age)** — `DistributionBar` by `byAge[].reach` OR user-selected metric via existing picker.
3. **Composition (gender)** — `PieComposition` by `byGender[].reach`. Replaces `<GenderDonut>`.
4. **Distribution (device)** — `DistributionBar` by `platforms.byDevice[].impressions`. Hide entire block when `platforms.data` absent.
5. **Drill-down (age × gender)** — Grouped `DistributionBar` (Age on X, Gender as series) per sprints-plan §895 fallback. Keep existing raw `<table>` below it as a11y toggle target.

**Empty state**: preserve FP-AUD-01 guard.
**Out of scope this sprint**: proper 2D heatmap for byAgeGender.

### 8.6 ParishMapDetail

**5-block layout:**
1. **KPI strip** — `KpiTile × 4`: Total Spend / Top Parish / Top Parish Spend / Parish Coverage % (from `availability.parish_map.coveragePercent`).
2. **KPI picker** — inline `<select>` above the map (Spend / Impressions / Clicks / Conversions) → `setSelectedMetric`. The store action already exists; wire the select to it.
3. **Choropleth map** — existing `<ParishMap>` component (Leaflet) consumes `selectedMetric` and re-renders fill. **Do not replace.** FP-MAP-01 empty state preserved.
4. **Specialized** — bubble overlay per-account DEFERRED (data gap, §3). No change.
5. **Drill-down** — keep existing `<RegionBreakdownTable>` (it already supports click-to-select-parish + reload).

**Hover tooltip**: show parish name + 4 KPI values. Sparkline DEFERRED (§3 gap). Add inline comment `// [NEW-ENDPOINT] Per-parish daily series — sprints-plan §923 deferred`.
**Platform toggle**: when `filters.platforms` changes the store refetches via `withFilters` (FP-BUDG-02/parish). Force Leaflet layer re-render using React `key={filters.platforms.join(',')}` on `<ParishMap>` to avoid B-MAP-01 stale-layer risk.

### 8.7 GoogleAnalyticsDashboardPage

**5-block layout:**
1. **KPI strip** — `KpiTile × 4`: Sessions / Conversions / Revenue / Engagement rate (substitute for the unavailable Users/Bounce/Avg Duration per §3 availability audit).
2. **Primary trend** — `TrendLine` single series: sessions-by-day aggregated from rows via `date_day`.
3. **Composition** — `PieComposition` sessions by `channel_group` (top 6 + "Other").
4. **Drill-down** — `VizDataTable` grouped by `channel_group`: Channel / Sessions / Conversions / Revenue / Engagement rate. CSV export.
5. No specialized viz (sprints-plan §938 spec has 4 blocks).

**Empty-state reasonCodes**:
- `no_ga4_property_selected` (when `status === 'loaded' && payload.status === 'unavailable'`)
- `no_data_for_range` (when `payload.status === 'ok' && rows.length === 0`)
- `error` (fetch failure)

**R3 assertion** per §4.
**a11y**: `AccessibleTableToggle` on TrendLine and PieComposition.
**Date picker**: keep local `useState`; do NOT introduce global FilterBar.

### 8.8 SearchConsoleDashboardPage

**5-block layout:**
1. **KPI strip** — `KpiTile × 4`: Clicks / Impressions / Avg CTR / Avg Position.
2. **Primary trend** — dual-axis `TrendLine` (Clicks left, Impressions right) aggregated by `date_day`. Reuse S2 Insights dual-axis pattern.
3. **Composition** — `PieComposition` clicks by `device` (desktop/mobile/tablet).
4. **Drill-down** — `VizDataTable`: Query / Clicks / Impressions / CTR / Avg Position. Top 50 by clicks (current default sort).
5. No specialized block.

**Empty-state reasonCodes**:
- `no_search_console_site_selected`
- `no_data_for_range`
- `error`

**R3 assertion** per §4.

### 8.9 SavedDashboardPage

- No structural change. Template render path unchanged.
- Extend template registry (`lib/dashboardTemplates.ts`) with optional `layout?: { slots: SlotConfig[] }` field — not populated in Sprint 4.
- Preserve FP-SAVED-01 and FP-SAVED-02 exactly as cited.
- If the `template.layout?.slots` field is populated by a future template, the renderer calls a new `<SavedDashboardSlotGrid slots={…} />` component instead of `renderTemplate()`. Sprint 4 ships the typed hook but not a consumer.
- Template subtitle / name / description UI unchanged.

### 8.10 DashboardLibrary + DashboardCreate

- `DashboardLibrary`: no layout change. Preserve FP-LIB-01 heading. Optional polish: add reasonCode `no_saved_dashboards_for_owner` to the filter-empty branch (`:402–412`). Card grid stays.
- `DashboardCreate`: no layout change. Preserve FP-CREATE-01. Optional addition: render a mini `KpiTile` strip in the preview section (already close — replace the 5 `<StatCard>` at `:593–598` with `<KpiTile>`). Do NOT refactor save logic, preview fetch, or FilterBar wiring.
- **No drag-drop authoring in Sprint 4.** Confirmed §6.2.

---

## 9. Implementer briefs (three parallel, zero file overlap)

### 9.1 S4a-CombinedCore — PlatformDashboard + CampaignDashboard + CreativeDashboard

**Files you MAY edit:**
- `frontend/src/routes/PlatformDashboard.tsx`
- `frontend/src/routes/CampaignDashboard.tsx`
- `frontend/src/routes/CreativeDashboard.tsx`
- `frontend/src/routes/__tests__/PlatformDashboard.test.tsx`
- `frontend/src/routes/__tests__/CampaignDashboard.*.test.tsx`
- `frontend/src/routes/__tests__/CreativeDashboard.test.tsx`
- `frontend/src/lib/platformLabels.ts` — **CREATE** this new 30-line helper module exporting `formatPlatformLabel(value: string): string` (copy from `PlatformDashboard.tsx:86–95`) and `platformColor(platform: string): string` (reads `PLATFORM_CHART_TOKENS`).
- Optional `frontend/src/lib/combinedAggregates.ts` — **CREATE** for shared client-side reducers (top-10 spend, per-platform rollup, derived CTR/CPM/ROAS).

**Files you MUST NOT edit:**
- `useDashboardStore.ts`, `DashboardLayout.tsx`, any `meta_*` / `google-ads/*` route, any viz primitive, any adapter, any test fixture under `useDashboardStore.test.ts`.

**Pre-flight critical:**
1. Read §7 contract preservation list. Assert each cited line survives.
2. Remove `formatPlatformLabel` local copy in `PlatformDashboard.tsx:86` only **after** importing the shared helper — don't delete the implementation behavior.
3. Do NOT refactor the `FP-CAMP-02` consolidated empty-state guard; thread viz-kit primitives in BEFORE/AFTER it, not through it.
4. `StackedArea` is NOT shipped — use single-series `TrendLine` with the `[NEW-ENDPOINT]` TODO comment. Do not attempt to synthesize per-platform trend client-side.

**Tests to add:**
- PlatformDashboard: `renders KpiTile x5 with aggregated totals`; `renders 2x2 SmallMultiples DistributionBar grid`; `renders VizDataTable with formatPlatformLabel` (re-use existing B-PLAT-03 test).
- CampaignDashboard: `renders new viz-kit KpiTile strip alongside legacy CampaignTable`; preserve existing FP-CAMP-01 parish-scope test and FP-CAMP-02 3-branch tests.
- CreativeDashboard: new 5-test suite asserting KpiTile×4, BubbleScatter present, PieComposition present, VizDataTable present, empty-state branch still renders.

**DoD:** targeted vitest green; preserve `frontend npm test -- --run` at 738/739 baseline (only pre-existing SavedDashboardPage flake).

### 9.2 S4b-CombinedOther+Web — BudgetDashboard + AudienceDashboard + GoogleAnalytics + SearchConsole

**Files you MAY edit:**
- `frontend/src/routes/BudgetDashboard.tsx`
- `frontend/src/routes/AudienceDashboard.tsx`
- `frontend/src/routes/GoogleAnalyticsDashboardPage.tsx`
- `frontend/src/routes/SearchConsoleDashboardPage.tsx`
- `frontend/src/routes/__tests__/BudgetDashboard.test.tsx`
- `frontend/src/routes/__tests__/AudienceDashboard.test.tsx`
- `frontend/src/routes/__tests__/GoogleAnalyticsDashboardPage.test.tsx` — **CREATE** if absent
- `frontend/src/routes/__tests__/SearchConsoleDashboardPage.test.tsx` — **CREATE** if absent
- Optional aggregates in `frontend/src/lib/webAnalyticsAggregates.ts` (client-side reducers for GA4 / SC rows)

**Files you MUST NOT edit:**
- `useDashboardStore.ts`, `DashboardLayout.tsx`, `lib/webAnalytics.ts` (API contract locked), any Meta/Google-Ads route, any viz primitive.
- **MUST NOT import `useDashboardStore` into GA4 or Search Console pages.** R3 CRITICAL.

**Pre-flight critical — R3:**
1. Before any file edit on GA4/SC: verify the current file does not import `useDashboardStore` (grep confirms it doesn't). Keep that invariant.
2. Before commit: add the `expect(urls).not.toContain('/metrics/combined/')` fetch-spy assertions per §4.
3. Do NOT wire GA4/SC into global FilterBar. They ship with local date pickers.
4. Preserve Audience FP-AUD-01 and Budget FP-BUDG-01 guards verbatim.

**Tests to add:**
- Budget: `renders KpiTile x3`; `renders paired DistributionBar skipping rows with null budget`; `renders risk chip via derivePacingVariant`; preserve FP-BUDG-01 guard test.
- Audience: `renders PieComposition for gender`; `renders grouped DistributionBar for byAgeGender`; `hides device block when platforms.data absent`; preserve FP-AUD-01 guard test.
- GA4: **R3 assertion** (fetchSpy check); `renders KpiTile×4 with present fields only`; `renders TrendLine for sessions/day`; `renders PieComposition by channel_group`; `renders VizDataTable with CSV export button`; `renders EmptyState with reasonCode=no_ga4_property_selected on status=unavailable`.
- Search Console: **R3 assertion**; `renders dual-axis TrendLine`; `renders PieComposition by device`; `renders VizDataTable top 50 by clicks`; empty-state reasonCode tests.

**DoD:** targeted vitest green + R3 assertion passing + no regression in full suite.

### 9.3 S4c-MapAndSaved — ParishMapDetail + SavedDashboardPage + DashboardLibrary + DashboardCreate

**Files you MAY edit:**
- `frontend/src/routes/ParishMapDetail.tsx`
- `frontend/src/routes/SavedDashboardPage.tsx`
- `frontend/src/routes/DashboardLibrary.tsx`
- `frontend/src/routes/DashboardCreate.tsx`
- `frontend/src/lib/dashboardTemplates.ts` — extend with optional `layout` field
- `frontend/src/routes/__tests__/ParishMapDetail.test.tsx`
- `frontend/src/routes/__tests__/SavedDashboardPage.test.tsx`
- `frontend/src/routes/__tests__/DashboardLibrary.test.tsx`
- `frontend/src/routes/__tests__/DashboardCreate.test.tsx`

**Files you MUST NOT edit:**
- `components/ParishMap.tsx` (Leaflet wrapper) — don't refactor; add the KPI-picker UI *inside* `ParishMapDetail.tsx` above the map container and pass `selectedMetric` via the store.
- `useDashboardStore.ts`, `DashboardLayout.tsx`.
- `lib/phase2Api.ts` `DashboardDefinition` shape (no new saved-dashboard fields).
- `lib/webAnalytics.ts`.

**Pre-flight critical:**
1. Leaflet SSR / JSDOM idiom: `ParishMap` already gates `L.map(…)` inside a `useEffect`. When adding the KPI-picker select, do NOT move any Leaflet call out of the effect. Test mocks `ParishMap` via `vi.mock`.
2. Preserve FP-MAP-01 zero-parishes guard.
3. Preserve FP-SAVED-01 (platforms restore) and FP-SAVED-02 (seededRef one-shot) exactly.
4. Preserve FP-CREATE-01 `platforms: ['meta_ads']` default on builder preview.
5. `layout` is OPTIONAL on the template type. Sprint 4 does NOT populate any template's `layout` field. Shipping the typed hook only.
6. Force re-render of Leaflet layer on platform change: wrap `<ParishMap />` in a React element with `key={filters.platforms.join(',')}`. Subscribe to `filters.platforms` in `ParishMapDetail`.

**Tests to add:**
- ParishMapDetail: `renders KPI picker select that updates selectedMetric`; `renders KpiTile x4`; preserve existing 6 tests including FP-MAP-01.
- SavedDashboardPage: add `template with layout.slots renders SavedDashboardSlotGrid instead of renderTemplate` (use a test-only fake template). Preserve the FP-SAVED-01/02 existing test. **Attempt to fix the pre-existing flake** — see §11.
- DashboardLibrary: preserve all current tests; optionally add a `no_saved_dashboards_for_owner` reasonCode test.
- DashboardCreate: preserve FP-CREATE-01; optionally add `renders KpiTile preview instead of legacy StatCard`.

**DoD:** targeted vitest green + SavedDashboardPage either fixed or explicitly deferred with evidence.

---

## 10. Test strategy per page

| Page | Targeted tests | Critical assertions |
|---|---|---|
| PlatformDashboard | 6 | KPI×5, 2×2 DistributionBar grid, PieComposition device, VizDataTable, `formatPlatformLabel` cite, FP-PLAT-02 empty state |
| CampaignDashboard | 5 | KpiTile row, `CampaignTable` legacy preserved, FP-CAMP-01 platform filter still excludes Google rows, FP-CAMP-02 3 empty-state branches |
| CreativeDashboard | 5 (new suite) | KpiTile×4, BubbleScatter, PieComposition by platform, VizDataTable, 3-branch empty |
| BudgetDashboard | 5 | KpiTile×3, paired DistributionBar, null-budget skip, pacing-variant chip, FP-BUDG-01 guard |
| AudienceDashboard | 5 | KpiTile×4 (Top Device hidden on no platforms.data), Age DistributionBar, Gender PieComposition, Age×Gender grouped bar, FP-AUD-01 |
| ParishMapDetail | 7 (6 existing + 1 new) | KPI picker updates store, FP-MAP-01, platforms key forces layer remount |
| GoogleAnalyticsDashboardPage | 6 (new suite) | **R3** fetch-URL assertion, KpiTile×4, TrendLine sessions/day, PieComposition channel, VizDataTable, `no_ga4_property_selected` reasonCode |
| SearchConsoleDashboardPage | 6 (new suite) | **R3**, dual-axis TrendLine, PieComposition device, VizDataTable top-50, reasonCodes |
| SavedDashboardPage | 2 | FP-SAVED-01/02 preserved; flake isolated OR fixed (§11) |
| DashboardLibrary + DashboardCreate | preserve all current | FP-LIB-01, FP-CREATE-01 |

**Full-suite gate**: `cd frontend && npm test -- --run` must land at >= 738/739 with only the pre-existing SavedDashboardPage flake remaining (OR 739/739 if the flake is fixed). **Backend pytest**: 727 passed / 1 skipped unchanged (no backend edits).

**Lint + build**: `npm run lint` clean, `npm run build` clean. `ruff check backend` not required (no backend edits).

**Targeted cmd for S4 smoke:**
```
cd frontend && npx vitest run PlatformDashboard CampaignDashboard CreativeDashboard BudgetDashboard AudienceDashboard ParishMapDetail GoogleAnalyticsDashboardPage SearchConsoleDashboardPage SavedDashboardPage DashboardLibrary DashboardCreate platformLabels combinedAggregates webAnalyticsAggregates
```

---

## 11. SavedDashboardPage flake strategy

**Current state**: single failing test in the full-suite run — `src/routes/__tests__/SavedDashboardPage.test.tsx:120:51` on the `location-search` href assertion. Present in S1 → S2 → S3 full-suite runs. Passes cleanly in isolation (1/1 in 76–115 ms across all three closeouts). Documented as cross-file mock-ordering flake with no single offending file.

**Decision: ATTEMPT FIX as part of S4c-MapAndSaved, with explicit defer-if-risky fallback.**

Rationale:
- S4c is already editing `SavedDashboardPage.tsx` and its test file to thread the `layout.slots` hook, so there is no separate touch-cost.
- Fix attempt should be isolated: restructure the `vi.mock` hoist order so the `useLocation` mock and `getDashboardDefinition` mock are declared before the `SavedDashboardPage` import, or use `vi.hoisted` for the `LocationProbe` component.
- If one focused attempt (≤1 hour) fails or destabilizes other tests, **defer** with a new handoff entry and cite that the flake is non-load-bearing for Phase 2 contract preservation (all 12 phase2 DoD items are asserted in isolation-green tests elsewhere).
- Do NOT attempt a `beforeAll(() => { vi.resetModules(); })` global mutation — that risks cascading failures into 113 other suites.

**Escalation signal**: if the fix attempt fails, flag in S4 closeout §handoff with the exact `vi.mock` resolution order observed and recommend a dedicated hardening sprint.

---

## 12. Risks (≥8)

1. **R3 bleed** (HIGH) — Any import of `useDashboardStore` into GA4/SC drops R3 silently. Mitigation: R3 fetch-URL assertion at test level + reviewer must grep `useDashboardStore` in web pages before merge.
2. **Platform-color legend parity** (MEDIUM) — Three combined pages (Platforms, Campaigns, Creatives) all need consistent Meta=blue / Google=orange colors. Mitigation: single helper `lib/platformLabels.ts` with `platformColor` reading `PLATFORM_CHART_TOKENS`; snapshot test on helper.
3. **GA4/SC data-shape drift** (MEDIUM) — Sprints-plan §942 KPI set (Sessions/Users/Bounce/AvgDuration) is a superset of the backend payload today. Substituting (Sessions/Conversions/Revenue/Engagement) may be a scope change. Mitigation: document in §3 and in implementer brief; flag for product review.
4. **Saved grid-snap backward-compat** (LOW) — Adding optional `layout?` to templates could confuse the existing widget-checklist UI in DashboardCreate. Mitigation: `layout` purely opt-in, no template in Sprint 4 populates it; checklist UI untouched.
5. **Phase 2 contract preservation** (HIGH) — 15 cited contracts in §7 span 4 files (DashboardLayout, useDashboardStore, 5 routes). Mitigation: §7 list in every implementer brief; targeted-vitest command includes `useDashboardStore.test.ts` for FP-CAMP-01/FP-CREA-01/FP-BUDG-02 coverage.
6. **Bubble-overlay lat/lon gap** (LOW) — sprints-plan §911 calls for an overlay; data not available. Mitigation: explicit defer in §3 + inline `[NEW-ENDPOINT]` comment.
7. **Stacked-area trend data gap** (MEDIUM) — sprints-plan §802 calls for per-platform daily series; not in store. Mitigation: single-series degrade, document in §5 and §8.1 with `[NEW-ENDPOINT]` comment.
8. **Leaflet re-render on platform filter change** (MEDIUM) — B-MAP-01 in A3 audit noted platform-filter lag on the Leaflet layer. Mitigation: `key={filters.platforms.join(',')}` on `<ParishMap>` forces subtree remount.
9. **SavedDashboardPage flake fix risk** (LOW–MEDIUM) — attempting to fix it may destabilize 113 other suites. Mitigation: §11 single-attempt rule + hard defer if any other suite breaks.
10. **Cross-slice data dependency in AudienceDashboard** (LOW) — Top Device tile and device DistributionBar need `platforms.data.byDevice` which lives in a different store slice than `demographics.data`. Mitigation: subscribe to both slices; hide block when `platforms.data` absent rather than render `—`.
11. **Template registry breaking change** (LOW) — Extending `DashboardTemplateDefinition` with an optional field. TypeScript-safe. Mitigation: `layout?` is optional; all existing code paths untouched.
12. **VizDataTable CSV column mismatch** (LOW) — Replacing legacy `<CampaignTable>` / `<CreativeTable>` with `VizDataTable` risks changing exported CSV headers. Mitigation: keep legacy `<CampaignTable>` in Campaigns (§8.2); CSV contract for other tables documented via test snapshots.

---

## 13. Out of scope

- Backend endpoint changes (no new `/metrics/combined/` payload fields, no new per-parish or per-platform time-series endpoint, no lat/lng for accounts).
- Leaflet replacement (stays on the current version).
- Adapter priority changes (warehouse > meta_direct > demo > fake unchanged).
- Dashboard sharing / permissions (outside Sprint 4).
- New saved-dashboard serialization format.
- Drag-drop authoring in DashboardCreate (keep template-picker + checklist).
- 2D heatmap primitive for Audience Age×Gender (sprints-plan §895 deferred).
- `TrendLine variant="stacked-area"` primitive extension (defer to Sprint 5 when data exists).
- `prefers-reduced-motion` polyfill (still deferred from S1).
- Coverage-gate re-enable (still deferred).
- Replacing the legacy `<CampaignTable>` / `<CreativeTable>` with `VizDataTable` (keep legacy per S3 precedent).
- GA4 / Search Console pagination beyond current 500-row cap.
- Alternate dataset adapters for GA4 / SC (they remain their own warehouse-pilot path).

---

## Verdict

Sprint 4 is scoped to **zero new viz primitives**, a single new helper module (`lib/platformLabels.ts`) + optional `combinedAggregates.ts` + optional `webAnalyticsAggregates.ts`, and three parallel implementer streams with zero file overlap. All 15 Phase 2 contracts are preserved with cited evidence. R3 is enforced via explicit fetch-URL test assertions. Two sprints-plan specs are degraded with `[NEW-ENDPOINT]` comments (stacked-area per-platform trend; bubble-overlay account lat/lng). The SavedDashboardPage flake gets a single fix attempt with a hard defer-fallback. Backend untouched.
