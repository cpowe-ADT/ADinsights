# Sprint 3 — Google Ads Cluster — Final Closeout

**Inputs cited:** `/Users/thristannewman/ADinsights/artifacts/sprint/S3-architect-design.md`, `/Users/thristannewman/ADinsights/artifacts/sprint/S3a-core-analytics.md`, `/Users/thristannewman/ADinsights/artifacts/sprint/S3b-creative-conv.md`, `/Users/thristannewman/ADinsights/artifacts/sprint/S3c-ops-tabs.md`, `/Users/thristannewman/ADinsights/artifacts/viz/sprints-plan.md` (Sprint 3 §542–773 + §5), `/Users/thristannewman/ADinsights/artifacts/sprint/S1-final-closeout.md`, `/Users/thristannewman/ADinsights/artifacts/sprint/S2-final-closeout.md`.

## Status: GREEN

Sprint 3 landed the 10-tab Google Ads cluster onto the Sprint 1 viz kit (extended with two new primitives). Both flag modes (`GOOGLE_ADS_WORKSPACE_UNIFIED = true|false`) are covered per architect §7. All data-availability strategies from the architect audit landed at the cited file:line evidence. Full test matrix, regressions, and DoD gates verified. The single full-suite failure is the documented `SavedDashboardPage.test.tsx` cross-file mock-ordering flake (pre-existing since S1; passes in isolation, confirmed 1/1 in 76ms — not caused by S3).

---

## 1. Per-tab DoD matrix

Legend: ✓ = shipped, ✗ = missing, N/A = out of spec per architect, § = file:line evidence cited below. All chart primitives ship an sr-only `<table>` (S1 a11y contract) so the "AccessibleTableToggle" column is satisfied by the primitive-level a11y contract (TrendLine/Sparkline wrap AccessibleTableToggle directly; BubbleScatter/DistributionBar/PieComposition/AssetGroupTreemap/GaugeRing ship the sr-only table variant — S1-final-closeout.md pattern).

| Tab | KPI strip | Trend | Distribution/composition | Drill-down table | Specialized viz | EmptyState + reasonCode | Loading (ChartSkeleton) | A11y table-equivalent on charts | Severity chips | Tests | Both modes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **Overview** | ✓ 4-tile (IS% deferred per architect §4) `OverviewTabSection.tsx:60–63`; legacy `GoogleAdsExecutivePage.tsx:104–108` | ✓ Dual-axis TrendLine `OverviewTabSection.tsx:70–80` | ✓ PieComposition channel cost (derived from campaigns cache) `OverviewTabSection.tsx:93–100` | N/A (movers table present `:106–136` but Overview design has no primary drill-down) | N/A | ✓ `no_data_for_range` `:46,79,90,98` | ✓ via primitives (S1 contract) | ✓ via TrendLine+PieComposition (S1 contract) | N/A | ✓ `GoogleAdsExecutivePage.test.tsx` (5 tests incl. IS% absence) | ✓ unified + legacy |
| **Campaigns** | ✓ 4-tile `CampaignsTabSection.tsx:99–102`; legacy `GoogleAdsCampaignsPage.tsx` | N/A — replaced with DistributionBar top-10 per architect §6.2 | ✓ DistributionBar top-10 `CampaignsTabSection.tsx:128–134`; BubbleScatter `:108–119` | ✓ 9-col table + drawer `:138–225` | ✓ BubbleScatter | ✓ `no_campaigns` `:80` | ✓ via primitives | ✓ via BubbleScatter+DistributionBar sr-only | ✓ Status tone chips `:174–180` (data-status-tone) | ✓ `GoogleAdsCampaignsPage.test.tsx` | ✓ unified + legacy |
| **Search** | ✓ 3-tile `SearchTabSection.tsx:127–138` | N/A | ✓ DistributionBar top search terms `:170` + BubbleScatter `:145` | ✓ Keywords + search-terms tables | ✓ BubbleScatter QS-vs-CPC | ✓ `no_keywords/no_search_terms/no_search_insights` per mode `:44,88,167` | ✓ | ✓ via primitives | N/A | ✓ `GoogleAdsKeywordsPage.test.tsx` | ✓ unified + legacy |
| **Assets** | ✓ 3-tile `AssetsTabSection.tsx:112–129` | N/A | ✓ PieComposition by asset_type `:137` | ✓ inline table with status chips | N/A — heat grid inline (architect §5) | ✓ `no_assets` `:95,134` | ✓ via primitives | ✓ via PieComposition | ✓ policy_approval_status chips (inline) | ✓ `GoogleAdsAssetsPage.test.tsx` (4) | ✓ unified + legacy |
| **PMax** | ✓ 3-tile `PmaxTabSection.tsx:100–111` | N/A | N/A | ✓ inline table with status chips | ✓ **AssetGroupTreemap** (new kit primitive) `:126` | ✓ `no_pmax_groups` `:83` | ✓ via primitives | ✓ via AssetGroupTreemap sr-only (`role="img"`) | ✓ asset_group_status chips | ✓ `GoogleAdsPmaxPage.test.tsx` (4) | ✓ unified + legacy |
| **Conversions** | ✓ 3-tile `ConversionsTabSection.tsx:99–114` | N/A | ✓ PieComposition source-mix `:144` | ✓ inline table (Action/Conv/Value/CPA) | ✓ **Funnel-via-DistributionBar** `:125–131` (stages ordered Impr→Clicks→Conv) | ✓ `no_conversions` `:82,141` | ✓ via primitives | ✓ via DistributionBar + PieComposition | N/A | ✓ `GoogleAdsConversionsPage.test.tsx` (4) | ✓ unified + legacy |
| **Pacing** | ✓ 3-tile `PacingTabSection.tsx:109–127` | N/A | N/A (variance bar deferred) | ✓ single-row pacing summary `:134–166` | ✓ **GaugeRing** (new kit primitive) `:88–99` | ✓ `no_pacing_data` `:77` | ✓ via primitives | ✓ GaugeRing sr-only (`role="meter"` + aria-value*) | N/A | ✓ `PacingTabSection.test.tsx` (5) + `GoogleAdsBudgetPage.test.tsx` (4) | ✓ unified + legacy |
| **Changes** | ✓ 2-tile `ChangesTabSection.tsx:131–132` | N/A | ✓ DistributionBar by resource_type `:138–144` | ✓ table with severity chips `:149–195` | N/A | ✓ `no_change_events` `:103` | ✓ via primitives | ✓ via DistributionBar sr-only | ✓ Severity CREATE/UPDATE/REMOVE `:162,175–183` | ✓ `GoogleAdsChangeLogPage.test.tsx` (4) | ✓ unified + legacy |
| **Recommendations** | ✓ 2-tile `RecommendationsTabSection.tsx:105–106` | N/A | ✓ PieComposition by recommendation_type `:112–117` | ✓ table with severity + status chips `:135–173` | N/A | ✓ `no_recommendations` `:91` | ✓ via primitives | ✓ via PieComposition | ✓ Severity derived (impact_metadata.severity ?? type heuristic) `:136,155–163` | ✓ `GoogleAdsRecommendationsPage.test.tsx` (4) | ✓ unified + legacy |
| **Reports** | ✓ 2-tile `ReportsTabSection.tsx:133–134` | N/A | N/A (workflow page per sprints-plan §756) | ✓ saved-views + export-job cards/tables | N/A | ✓ `no_saved_views` `:188` | ✓ | N/A (no chart — tables are semantic) | ✓ export-job status tone chips (via `deriveExportJobStatusTone`) | ✓ `GoogleAdsReportsPage.test.tsx` (4) | ✓ unified + legacy |

---

## 2. Data-availability strategy verification

Every gap strategy from architect §4 traced to concrete code:

| Gap | Strategy | Evidence |
|---|---|---|
| IS% deferred (Overview 4-tile not 5) | Ship 4-tile strip, omit IS% slot | `WorkspaceKpiStrip.tsx:24–29` (TILES array is {spend, conversions, cpa, roas} — no IS%); `OverviewTabSection.tsx:60–65` (4 KpiTiles + inline comment "// IS% intentionally deferred — architect §4"); `GoogleAdsExecutivePage.test.tsx` asserts absence |
| Per-campaign daily-trend → DistributionBar top-10 fallback | Use `buildTopSpendBars(rows, 10)` + `DistributionBar` | `CampaignsTabSection.tsx:61,122–134` (includes inline note "Per-campaign daily trend is not yet available from the API"); `googleAdsAggregates.ts` exports `buildTopSpendBars` |
| Per-campaign inline Sparkline suppressed | Column omitted from table | `CampaignsTabSection.tsx:140–153` — 9-column table, no sparkline column |
| Channel pie derived from campaigns cache | `buildChannelPie(campaignRows)` with prefetch | `OverviewTabSection.tsx:38,93–100`; `googleAdsAggregates.ts:buildChannelPie`; `GoogleAdsWorkspacePage.tsx` prefetches campaigns when `activeTab === 'overview'` (per S3a closeout §Gap strategies #3) |
| Change-log severity from `resource_change_operation` | `deriveChangeSeverity` mapping | `googleAdsAggregates.ts:341–345` (CREATE→info, UPDATE/MODIFY→warning, REMOVE/DELETE→danger); consumer `ChangesTabSection.tsx:162,175–183` |
| Recommendations severity from `impact_metadata?.severity` ?? heuristic | `deriveRecommendationSeverity` with try/catch | `googleAdsAggregates.ts:505–555` (explicit severity first then type substring heuristic: BUDGET/BID/PACING→warning, POLICY/DISAPPROVED/SUSPENDED→danger, else info); consumer `RecommendationsTabSection.tsx:136,155–163` |
| Pacing variance bar deferred | No per-campaign variance viz in Pacing tab | `PacingTabSection.tsx:128–130` inline comment "Variance bar intentionally deferred — architect §4 + §6.7"; test assertion for absence documented in `PacingTabSection.test.tsx` |
| Heat-tinted asset grid inline (no kit primitive, no per-asset sparkline) | Inline CSS grid + heat tone chips | `AssetsTabSection.tsx` — no `AssetGroupTreemap`/`Sparkline` import; `googleAdsCreativeConvAggregates.ts` exports `deriveHeatTone`, `buildAssetHeatGrid` |
| Funnel-via-DistributionBar on Conversions | `buildFunnelStages(summary.metrics)` | `googleAdsCreativeConvAggregates.ts:235–249` (ordered Impressions→Clicks→Conversions); `ConversionsTabSection.tsx:6,57–58,125–131` (uses `summary.metrics`, not campaigns rows) |
| Pacing % derived if missing | `derivePacingPct` fallback to `spend_mtd / budget_month` | `googleAdsAggregates.ts:389–406` (direct `pacing_pct` first, then `safeDivide(spend_mtd, budget_month)`); consumer `PacingTabSection.tsx:56,89` |
| Reports dismiss/list endpoint gaps | Dismiss button suppressed; single-job display | `RecommendationsTabSection.tsx` — no dismiss `<button>` (asserted in test); `ReportsTabSection.tsx` surfaces most-recent job card only |

---

## 3. New kit primitives verification

### AssetGroupTreemap
- File: `frontend/src/components/viz/AssetGroupTreemap.tsx`
- Barrel: `frontend/src/components/viz/index.ts:47` — `export { default as AssetGroupTreemap, roasToOpacity }` + types at `:48–51`
- A11y contract: `role="img"` + `aria-label` wrapper (line 186); sr-only hidden table; ChartSkeleton on `isLoading`; EmptyState with `reasonCode` when empty
- Non-color encoding: diagonal hatch pattern overlay on low-ROAS quartile (S3b closeout §Part 1)
- `roasToOpacity` helper: clamps `roas/2` to `[0,1]` then scales to `[0.3,1.0]` opacity (viz/AssetGroupTreemap.tsx:41–43,72)
- Tests: `AssetGroupTreemap.test.tsx` — 8 tests incl. 2 jest-axe passes (default + empty)

### GaugeRing
- File: `frontend/src/components/viz/GaugeRing.tsx`
- Barrel: `frontend/src/components/viz/index.ts:53` — `export { default as GaugeRing, derivePacingVariant }` + types at `:54`
- A11y contract: `role="meter"` at `:177` + `aria-valuenow` `:179` + `aria-valuemax` `:181` + `aria-valuemin` + `aria-valuetext` (imperfect AT coverage so also ships sr-only table — S3b closeout)
- `derivePacingVariant` helper: thresholds `<0.8` warning, `0.8–1.1` ok, `>1.1` danger; negative/NaN → danger
- Non-color encoding: four tick notches on ring edge — compound visual encoding
- Tests: `GaugeRing.test.tsx` — 11 tests incl. 2 jest-axe passes (default + empty)

### S1 a11y contract parity
All 12 viz-kit primitives (10 S1 + 2 S3b) carry jest-axe assertions in their test files (grep confirmed — KpiTile, TrendLine, Sparkline, DistributionBar, BubbleScatter, PieComposition, DataTable, ChartSkeleton, AccessibleTableToggle, EmptyState, AssetGroupTreemap, GaugeRing).

---

## 4. Full test matrix — verbatim tails

### 4.1 `cd frontend && npm run lint`
```
> adinsights-frontend@0.1.0 lint
> eslint .
```
(clean — zero errors, zero warnings; exit 0)

### 4.2 `cd frontend && npm run build`
```
dist/assets/PmaxTabSection-CBVAJq1T.js                    23.95 kB │ gzip:  8.48 kB
dist/assets/PacingTabSection-C9R9-ymI.js                  25.86 kB │ gzip:  8.22 kB
dist/assets/GoogleAdsWorkspacePage-l-fOYNhu.js            31.54 kB │ gzip:  8.19 kB
dist/assets/useDashboardStore-C1If0oAi.js                 32.42 kB │ gzip:  8.15 kB
dist/assets/chartTheme-Dm5qJK7P.js                       243.08 kB │ gzip: 78.57 kB
dist/assets/index-DLLKIdM-.js                            275.25 kB │ gzip: 88.13 kB
✓ built in 5.71s
```
tsc + vite build both succeed. (S3b closeout's flagged pre-existing TS errors in S3a files — `CampaignsTabSection`, `OverviewTabSection`, `GoogleAdsCampaignsPage`, `GoogleAdsExecutivePage` — were ultimately resolved: my fresh `npm run build` succeeds cleanly. Evidence: build tail above.)

### 4.3 `cd frontend && npx vitest run google-ads googleAdsAggregates googleAdsCreativeConvAggregates WorkspaceKpiStrip AssetGroupTreemap GaugeRing Pacing Changes Recommendations Reports Assets PMax Conversions Overview Campaigns Search`
```
 ✓ src/routes/google-ads/__tests__/GoogleAdsBudgetPage.test.tsx (4 tests) 590ms
 ✓ src/routes/google-ads/__tests__/GoogleAdsExecutivePage.test.tsx (5 tests) 886ms
 ✓ src/routes/google-ads/__tests__/GoogleAdsReportsPage.test.tsx (4 tests) 925ms
 ✓ src/components/google-ads/workspace/tab-sections/__tests__/PacingTabSection.test.tsx (5 tests) 900ms
 ✓ src/routes/google-ads/__tests__/GoogleAdsRecommendationsPage.test.tsx (4 tests) 434ms
 ✓ src/routes/google-ads/__tests__/GoogleAdsAssetsPage.test.tsx (4 tests) 494ms
 ✓ src/routes/google-ads/__tests__/GoogleAdsLegacyRedirects.test.tsx (2 tests) 53ms
 ✓ src/lib/googleAdsCreativeConvAggregates.test.ts (15 tests) 37ms
 ✓ src/lib/googleAdsAggregates.test.ts (47 tests) 54ms
 ✓ src/routes/google-ads/__tests__/GoogleAdsChannelsPage.test.tsx (2 tests) 75ms
 ✓ src/routes/google-ads/__tests__/GoogleAdsCampaignDetailPage.test.tsx (5 tests) 165ms
 ✓ src/routes/google-ads/__tests__/GoogleAdsBreakdownsPage.test.tsx (3 tests) 104ms
 ✓ src/routes/google-ads/__tests__/GoogleAdsChangeLogPage.test.tsx (4 tests) 94ms
 ✓ src/routes/google-ads/__tests__/GoogleAdsPmaxPage.test.tsx (4 tests) 98ms

 Test Files  26 passed (26)
      Tests  182 passed (182)
   Duration  23.83s
```

### 4.4 `cd frontend && npm test -- --run` (full suite)
```
 Test Files  1 failed | 119 passed (120)
      Tests  1 failed | 738 passed (739)
   Duration  68.58s
```
Single failure: `src/routes/__tests__/SavedDashboardPage.test.tsx:120:51` — the pre-existing cross-file mock-ordering flake documented in S1 handoff #5 and S2 closeout §3.4. Verified green in isolation:
```
 ✓ src/routes/__tests__/SavedDashboardPage.test.tsx (1 test) 76ms
 Test Files  1 passed (1)
      Tests  1 passed (1)
```
**Not caused by Sprint 3.** Identical flake signature + file as prior sprints.

### 4.5 `cd backend && pytest`
```
727 passed, 1 skipped in 20.97s
```
Matches S1/S2 baseline exactly.

### 4.6 `ruff check backend`
```
All checks passed!
```

---

## 5. Regression check

| Contract | Result | Evidence |
|---|---|---|
| Phase 1A Meta tests (7 pages) | ✓ All preserved in full-suite (119/120 file pass) | — |
| Phase 1B Google Ads CC2 saved-view `client_id` restore | ✓ Preserved at `GoogleAdsWorkspacePage.tsx:214–216` with CC2 comment; test `restores client_id from saved view …` still in `__tests__/GoogleAdsWorkspacePage.test.tsx:246` |
| Phase 1B NB1/NB2 reactive `useEffect` filter-subscribe | ✓ All 9 Google Ads route files subscribe via `useDashboardStore((s) => s.filters)` (grep count) — Executive/ChangeLog/Recommendations/Budget/Campaigns/Assets/Conversions/Pmax/Keywords |
| B1 hot-fix: global FilterBar visible on `/dashboards/google-ads` | ✓ Preserved; test at `DashboardLayout.test.tsx:537` — "renders global FilterBar on /dashboards/google-ads route (not hidden)" |
| B3/B4 drawer-via-URL contract | ✓ `CampaignsTabSection.tsx:197–225` drawer + `onOpenDrawer(campaignId)` cell renderer preserved |
| Phase 2 Combined metrics tests | ✓ Included in 738 full-suite pass count |
| Sprint 1 viz kit jest-axe coverage (10 primitives) | ✓ All 10 `.test.tsx` files still carry jest-axe; plus 2 new S3b primitives |
| Sprint 2 Meta targeted tests (92 tests) | ✓ Included in 738 full-suite pass count; no Meta route test failures |
| Backend adapter dispatch, dataset_status, meta_views, google_ads_views | ✓ 727 passed, 1 skipped — identical pass count to S1/S2 baseline |
| `useGoogleAdsWorkspaceData` hook signature locked | ✓ No edits (boundary respected by S3a/S3b/S3c per each closeout §Boundaries) |
| `GoogleAdsDataTablePage.tsx` preserved for Channels/Breakdowns legacy redirects | ✓ No edits; Channels + Breakdowns redirect tests still pass (2 + 3 tests) |

---

## 6. A11y posture

- **Viz kit jest-axe coverage**: 12/12 primitives (10 S1 + 2 S3b) carry jest-axe assertions. S3b's `AssetGroupTreemap.test.tsx` and `GaugeRing.test.tsx` each run jest-axe twice (default + empty).
- **New-primitive ARIA roles**:
  - `AssetGroupTreemap.tsx:186` → `role="img"` + `aria-label` wrapper + sr-only `<table>` listing Asset Group/Spend/ROAS
  - `GaugeRing.tsx:177–181` → `role="meter"` + `aria-valuenow` + `aria-valuemin` + `aria-valuemax` + `aria-valuetext` + sr-only `<table>` fallback
- **Severity chips are not color-only**: all three chip systems (Campaigns status, Changes severity, Recommendations severity, Reports status) render visible text AND `aria-label`/sr-only suffix describing the severity (e.g. `ChangesTabSection.tsx:178–183` aria-label `Severity ${text}` + sr-only ` — ${text}`).
- **Non-color encoding on new viz**: AssetGroupTreemap uses diagonal hatch pattern overlay on low-ROAS quartile; GaugeRing adds four tick-notch overlays at variant thresholds (non-color threshold cues).
- **Meta page a11y posture (S2)**: unchanged — 12 `AccessibleTableToggle` wrap sites preserved across the 7 Meta pages.
- **Google Ads page a11y posture (S3)**: every chart in the 10 tabs carries the S1 primitive-level a11y contract (either AccessibleTableToggle wrap as with TrendLine/Sparkline, or sr-only table equivalent as with BubbleScatter/DistributionBar/PieComposition/AssetGroupTreemap/GaugeRing).

---

## 7. Known follow-ups (deferred, non-blocking)

1. **IS% (Impression Share)** still not in API — 4-tile Overview strip. `[NEW-ENDPOINT]` needed; inline TODO at `OverviewTabSection.tsx:65`.
2. **Per-campaign daily series** still unavailable — sparkline column suppressed in Campaigns. `[NEW-ENDPOINT]` needed.
3. **Per-asset daily series** still unavailable — heat-tinted grid degrades to `conversion_rate` single-metric heat + tone chips. Inline-only (no kit primitive per architect §5).
4. **Pacing variance bar** deferred — no `/budgets/per-campaign/` endpoint. `PacingTabSection.tsx:128–130` comment locks the deferral.
5. **Recommendations Dismiss PATCH** — no endpoint; button suppressed.
6. **Reports export-jobs list endpoint** — only single-job round-trip exists.
7. **SavedDashboardPage cross-file mock-ordering flake** — still present (per S1 handoff #5). Passes in isolation. Suggest isolating mocks before coverage-gate re-enable.
8. **Channels + Breakdowns legacy pages** — still delegate to `GoogleAdsDataTablePage`; not modernized (out of scope per architect §2). Redirects to `tab=campaigns` still stable.
9. **Campaigns + others use raw `<table className="dashboard-table">`** rather than `VizDataTable`. The primitive is not being consumed in the new tab sections; the architect brief allowed either approach. Consider a cleanup sprint to unify on `VizDataTable`.
10. **`TrendLine.StackedArea` variant** — deferred from S1, not needed by S3; Sprint 4 Combined area charts will need it.
11. **`prefers-reduced-motion` polyfill** — still deferred from S1.
12. **Coverage-gate re-enable** — still deferred (S1 handoff #4, S2 handoff #8).
13. **Playwright E2E** for `/dashboards/google-ads` — not added; flagged in architect §11.

---

## 8. Frontend test trajectory

| Sprint closeout | Files passing | Tests passing | Tests failing | Net delta |
|---|---|---|---|---|
| Pre-S1 baseline (closeout header) | — | ~530 | 0 | — |
| S1 (viz kit shipped) | — | ~579 | 1 flake | +49 |
| S2 (Meta cluster) | 113 pass / 114 total | 628 / 629 | 1 flake | +50 |
| **S3 (Google Ads cluster)** | **119 pass / 120 total** | **738 / 739** | **1 flake (same)** | **+110** |

Backend: 727 passed, 1 skipped — flat across S1/S2/S3 (no backend file edits in Sprint 3).

---

## 9. Manual smoke checklist addendum

Smoke path for each of 10 Google Ads tabs, both workspace modes where applicable. Run after `scripts/dev-launch.sh --profile 1 --non-interactive` with `GOOGLE_ADS_WORKSPACE_UNIFIED` flag toggled per step.

### 9.1 Overview
**Unified** (`GOOGLE_ADS_WORKSPACE_UNIFIED=true`):
1. Visit `/dashboards/google-ads?tab=overview`. **Expect**: 4 KPI tiles (Cost/Conversions/CPA/ROAS — no IS%), dual-axis TrendLine (left=Cost, right=Conversions), PieComposition of cost-by-channel (may show "no channel breakdown available" reason if campaigns cache empty).
2. Switch to Campaigns tab then back. **Expect**: channel pie populates after campaigns prefetch.

**Legacy** (`=false`): Visit `/dashboards/google-ads/executive`. **Expect**: same 4 KPI tiles + dual-axis TrendLine + movers table.

### 9.2 Campaigns
**Unified**: Visit `/dashboards/google-ads?tab=campaigns`. **Expect**: 4-tile KPI strip, BubbleScatter (Cost vs Conversion rate), top-10 DistributionBar, 9-col table, drawer opens on row click.
**Legacy**: `/dashboards/google-ads/campaigns`. **Expect**: parity with unified; status chips visible per row.

### 9.3 Search
**Unified**: Visit `/dashboards/google-ads?tab=search&searchMode=keywords`. **Expect**: 3-tile KPI, QS-vs-CPC BubbleScatter, top-10 search-terms DistributionBar. Switch `searchMode` to `search_terms` / `insights`. **Expect**: different `reasonCode` EmptyState if no data.
**Legacy**: `/dashboards/google-ads/keywords`. **Expect**: mode toggle preserved; same charts.

### 9.4 Assets
**Unified**: `/dashboards/google-ads?tab=assets`. **Expect**: 3-tile KPI, PieComposition by asset_type, inline table with policy_approval_status chips.
**Legacy**: `/dashboards/google-ads/assets`. Same expectations.

### 9.5 PMax
**Unified**: `/dashboards/google-ads?tab=pmax`. **Expect**: 3-tile KPI, **AssetGroupTreemap** renders (size=spend, opacity scales with ROAS, low-ROAS slices get hatch overlay), sr-only table available to screen readers.
**Legacy**: `/dashboards/google-ads/pmax`. Same.

### 9.6 Conversions
**Unified**: `/dashboards/google-ads?tab=conversions`. **Expect**: 3-tile KPI, Funnel-via-DistributionBar (3 ordered stages Impressions→Clicks→Conversions), source-mix PieComposition, action-name table.
**Legacy**: `/dashboards/google-ads/conversions`. Same.

### 9.7 Pacing
**Unified**: `/dashboards/google-ads?tab=pacing`. **Expect**: **GaugeRing** (role=meter, aria-valuenow live, tick notches at 0/0.4/0.8/1.1, variant color+hatch based on pct), 3-tile KPI (Spend MTD/Budget Month/Forecast), single-row summary table. Variance bar should NOT appear.
**Legacy**: `/dashboards/google-ads/budget`. Same. With zero data, **expect** EmptyState `reasonCode="no_pacing_data"`.

### 9.8 Changes
**Unified**: `/dashboards/google-ads?tab=changes`. **Expect**: 2-tile KPI (Total / last 7d), DistributionBar by resource_type, table with severity chips (CREATE→info, UPDATE→warning, REMOVE→danger). Pagination count visible.
**Legacy**: `/dashboards/google-ads/change-log`. Same.

### 9.9 Recommendations
**Unified**: `/dashboards/google-ads?tab=recommendations`. **Expect**: 2-tile KPI (Active/Dismissed), PieComposition by recommendation_type, table with severity + status chips. **No Dismiss button** anywhere.
**Legacy**: `/dashboards/google-ads/recommendations`. Same.

### 9.10 Reports
**Unified**: `/dashboards/google-ads?tab=reports`. **Expect**: 2-tile KPI (Total saved views / Shared views), form controls (date range + Generate button + Saved View name input), latest export-job card with status chip, saved-views table with Shared chip.
**Legacy**: `/dashboards/google-ads/reports`. Same. With no saved views, **expect** `reasonCode="no_saved_views"`.

---

## 10. Verdict

**Status: GREEN** — Sprint 3 Google Ads cluster migration complete. All 10 tabs adopt the Sprint 1+3b viz kit with both flag modes covered. All 11 data-availability gap strategies landed at cited file:line evidence. 2 new kit primitives (AssetGroupTreemap + GaugeRing) ship with jest-axe coverage + role="img"/role="meter" a11y contracts + non-color compound encoding (hatch + ticks). Frontend full-suite 738/739 (single unrelated pre-existing SavedDashboardPage flake), targeted 182/182, lint clean, build clean. Backend 727 passed / 1 skipped, ruff clean. Phase 1A/1B/2 + S1/S2 regressions all preserved. Ready for Sprint 4.
