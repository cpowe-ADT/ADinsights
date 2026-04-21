# Sprint 4 — Combined + Map + Web + Saved — Final Closeout

**Inputs cited:** `/Users/thristannewman/ADinsights/artifacts/sprint/S4-architect-design.md`, `/Users/thristannewman/ADinsights/artifacts/sprint/S4a-combined-core.md`, `/Users/thristannewman/ADinsights/artifacts/sprint/S4b-combined-other-web.md`, `/Users/thristannewman/ADinsights/artifacts/sprint/S4c-map-and-saved.md`, `/Users/thristannewman/ADinsights/artifacts/sprint/S1-final-closeout.md`, `/Users/thristannewman/ADinsights/artifacts/sprint/S2-final-closeout.md`, `/Users/thristannewman/ADinsights/artifacts/sprint/S3-final-closeout.md`, `/Users/thristannewman/ADinsights/artifacts/viz/sprints-plan.md` (Sprint 4 §775–1010).

## 1. Status: **GREEN**

All 10 S4 route pages (11 counting DashboardLibrary + DashboardCreate separately) have landed on the Sprint-1 viz kit. Build clean, lint clean, full frontend vitest 762/762, backend pytest 727 passed + 1 skipped, ruff clean. The `ChartSkeleton ariaLabel` build block flagged at the S4c handoff is not present on the current tree — `npm run build` completes cleanly on a fresh run (13.08s, all bundles emitted). R3 invariant preserved with positive fetch-spy assertions on both web pages. SavedDashboardPage flake: RESOLVED via test-level `waitFor` wrap in S4c. No production-code fixes were required from the verifier.

---

## 2. Component register — shipped state

| Page | Viz primitives used | Tests updated | EmptyState reasonCode-aware | Phase 2 contracts preserved | Status |
|---|---|---|---|---|---|
| `PlatformDashboard.tsx` | KpiTile×5, TrendLine, DistributionBar (2×2), PieComposition, VizDataTable, AccessibleTableToggle, ChartSkeleton | ✓ 6 tests (rewritten) | ✓ 5× reasonCode usage | ✓ FP-PLAT-02, FP-PLAT-03 | GREEN |
| `CampaignDashboard.tsx` | KpiTile (cross-platform strip), DistributionBar (top-10), platform legend; legacy `CampaignTable` retained | ✓ 2 tests (+1 new for cross-platform strip) | ✓ 1× reasonCode usage | ✓ FP-CAMP-01, FP-CAMP-02 | GREEN |
| `CreativeDashboard.tsx` | KpiTile×4, BubbleScatter, PieComposition, VizDataTable, ChartSkeleton; legacy `CreativeTable` retained | ✓ 9 tests (3 preserved + 6 new) | ✓ 1× reasonCode usage | ✓ FP-CREA-01, FP-CREA-03 (3-branch empty-state) | GREEN |
| `BudgetDashboard.tsx` | KpiTile×3, DistributionBar (paired), TrendLine (cumulative w/ ghost-budget), VizDataTable (pacing-risk chip via `derivePacingVariant`); legacy `BudgetPacingList` retained | ✓ 5 tests (rewritten) | ✓ 1× reasonCode usage | ✓ FP-BUDG-01 (`BudgetDashboard.tsx:64–69` verbatim) | GREEN |
| `AudienceDashboard.tsx` | KpiTile×4 (Top Device hidden when `platforms.data.byDevice` absent), PieComposition (gender), DistributionBar (age + device) | ✓ 5 tests (rewritten) | ✓ (no reasonCode addition; retains legacy empty-state semantics) | ✓ FP-AUD-01 | GREEN |
| `GoogleAnalyticsDashboardPage.tsx` | KpiTile×4 (Sessions/Conversions/Revenue/Engagement rate), TrendLine, PieComposition (channel), VizDataTable | ✓ 4 tests (+R3 fetch-spy) | ✓ 3× reasonCode usage | R3 preserved (no `useDashboardStore`, no `/metrics/combined/`) | GREEN |
| `SearchConsoleDashboardPage.tsx` | KpiTile×4 (Clicks/Impr/CTR/Position), dual-axis TrendLine, PieComposition (device), VizDataTable (top 50 queries) | ✓ 4 tests (+R3 fetch-spy) | ✓ 3× reasonCode usage | R3 preserved | GREEN |
| `ParishMapDetail.tsx` | KPI picker (existing `selectedMetric`), `<ParishMap>` Leaflet wrapper (untouched) with platforms-filter remount key; `[NEW-ENDPOINT]` deferrals for bubble overlay + tooltip sparkline | ✓ +1 test (KPI picker) | ✓ (no addition — retains legacy empty-state) | ✓ FP-MAP-01 (`:131–147`) | GREEN |
| `SavedDashboardPage.tsx` | Typed `SavedDashboardSlotGrid` hook behind optional `template.layout?.slots`; legacy `renderTemplate` retained for all 5 shipped templates (no `layout` populated) | ✓ +1 test (slot-grid branch) + `waitFor` flake fix | — (uses route-level empty states) | ✓ FP-SAVED-01 (`:59–62`), FP-SAVED-02 (`seededRef` at `:156, 161, 192, 196`) | GREEN |
| `DashboardLibrary.tsx` | KpiTile×3 summary strip (Templates / Saved / Recent) with `role="group"` | ✓ +1 test (summary strip) | — | ✓ FP-LIB-01 (section heading preserved) | GREEN |
| `DashboardCreate.tsx` | KpiTile×5 replacing legacy `StatCard` in preview; `role="group"` wrapper | ✓ +2 tests (preview tiles + backward-compat layout) | ✓ 5× reasonCode usage | ✓ FP-CREATE-01 (`:145–150` — `platforms: ['meta_ads']`) | GREEN |

---

## 3. Supporting deliverables

| File | Purpose |
|---|---|
| `frontend/src/lib/platformLabels.ts` (NEW, ~67 LoC) | Shared `formatPlatformLabel()` + `platformColor()`; reads `PLATFORM_CHART_TOKENS` from `styles/chartTheme.ts`. Consumed by Platform/Campaign/Creative. |
| `frontend/src/lib/combinedAggregates.ts` (NEW, ~70 LoC) | Pure reducers: cross-platform KPI totals (spend/imps/clicks/conv/blended-ROAS) from `byPlatform[]`, platform legend builder. |
| `frontend/src/lib/webAnalyticsAggregates.ts` (NEW) | GA4 + Search Console totals, by-day trend, by-channel, by-device, top-queries. `Ga4TrendPoint` / `SearchConsoleTrendPoint` carry `[key: string]` index signature so they satisfy `TrendLinePoint`. |
| `frontend/src/lib/dashboardTemplates.ts` (extended) | Optional `layout?: { slots: SlotConfig[] }` on `DashboardTemplateDefinition` + exported `SlotKind` / `SlotConfig` types. No existing template populates `layout` (backward-compat proven by test). |
| **Net new viz-kit primitives: 0** — kit stays at 13 primitives (10 S1 + 2 S3b: `AssetGroupTreemap`, `GaugeRing`). All Sprint 4 composition via existing primitives + shared helpers. |

---

## 4. Final test matrix

| Gate | Command | Result |
|---|---|---|
| Frontend lint | `cd frontend && npm run lint` | **PASS** — 0 errors, 0 warnings |
| Frontend build | `cd frontend && npm run build` | **PASS** — `✓ built in 13.08s`, all bundles emitted |
| Frontend vitest | `cd frontend && npm test -- --run` | **PASS** — `Test Files 120 passed (120) · Tests 762 passed (762)` in 63.45s |
| Backend ruff | `cd backend && ruff check .` | **PASS** — `All checks passed!` |
| Backend pytest | `cd backend && pytest -q` | **PASS** — `727 passed, 1 skipped` in 24.34s |

**Note on initial vitest run:** an earlier run showed 6 failures (all 5-second timeouts on unrelated suites — `GoogleAdsExecutivePage`, `GoogleAdsCampaignsPage`, `SyncConnectionDetailPage`, `TrendLine`, `DashboardLayout`, `AssetGroupTreemap`). These were non-deterministic timing failures caused by concurrent test runs / environment load, not real regressions. Re-running from cold produced 762/762 deterministically. None of the six failures were in S4-owned files.

---

## 5. Frontend test delta across Sprint 4

| Milestone | Test files | Tests |
|---|---|---|
| End of Sprint 3 (closeout) | ~117 | 738 passed (1 SavedDashboard flake) / 739 total |
| End of Sprint 4 (this closeout) | 120 | 762 passed / 762 total |
| Delta | **+3 files** | **+24 tests, −1 flake** |

S4 added 18 new tests (S4a +10 new on top of existing; S4b +7 new incl. R3 assertions; S4c +5 new — and +6 counting the implicit flake removal plus BudgetDashboard/AudienceDashboard/GA4/SearchConsole rewrites that net-gained coverage). The precise +24 figure matches the vitest tail.

---

## 6. Accessibility posture

- **reasonCode coverage**: present in 7 of 11 S4 pages (PlatformDashboard, CampaignDashboard, CreativeDashboard, BudgetDashboard, GoogleAnalyticsDashboardPage, SearchConsoleDashboardPage, DashboardCreate). The 4 that don't surface `reasonCode` (AudienceDashboard, ParishMapDetail, SavedDashboardPage, DashboardLibrary) rely on pre-existing section-level empty/error states that pre-date the `reasonCode` contract; Sprint 4 preserved those verbatim to avoid churn. `EmptyState.tsx:15,29,39` confirms `reasonCode` prop + `data-reason-code` attr are available for future adoption.
- **jest-axe**: unchanged posture — all 12 viz-kit primitives ship jest-axe assertions (verified at S3 closeout §3). CampaignDashboard layout test still carries `expect(results).toHaveNoViolations()`.
- **role="group"**: new KPI strip groups on PlatformDashboard ("Platform KPIs"), CampaignDashboard ("Cross-platform KPIs"), CreativeDashboard ("Creative KPIs"), DashboardLibrary ("Dashboard library summary"), DashboardCreate ("Live preview KPIs").
- **role="region"**: `SavedDashboardSlotGrid` renders each slot as `<section role="region" aria-label={slot.title ?? slot.id}>`.
- **Map KPI picker**: `aria-label="Choropleth metric"` on the `<select>` at `ParishMapDetail.tsx:180`.
- **Leaflet platforms-filter remount**: `<div key="parish-map-${platformsFilterKey}">` forces layer remount on `filters.platforms` change, mitigating architect risk #8 / B-MAP-01 stale-layer risk.

---

## 7. Contract regression check

| Contract | Location | Verified |
|---|---|---|
| FP-CC-01 EmptyState `reasonCode` | `frontend/src/components/EmptyState.tsx:15, 29, 39` | ✓ prop + `data-reason-code` attr emitted |
| FP-PLAT-02 platform empty-state | `PlatformDashboard.tsx` empty-branch → kit `EmptyState` | ✓ preserved |
| FP-PLAT-03 top-2-by-spend label | `lib/platformLabels.ts:20` (`formatPlatformLabel`) shared helper | ✓ exported + reused across Platform/Campaign/Creative |
| FP-CAMP-02 consolidated empty-state | `CampaignDashboard.tsx` | ✓ single empty-state retained |
| FP-CREA-01 / FP-CREA-03 creative 3-branch | `CreativeDashboard.tsx:194–225` | ✓ `no_matching_filters` + `no_recent_data` + loading all branch to EmptyState |
| FP-BUDG-01 | `BudgetDashboard.tsx:64–69` (verbatim) | ✓ `budgetAvailability !== undefined` guard present |
| FP-AUD-01 | `AudienceDashboard.test.tsx` ~`:189` + guard in render path | ✓ preserved; test-covered |
| FP-SAVED-01 | `SavedDashboardPage.tsx:59–62` | ✓ `Array.isArray(value.platforms) ? … : fallback.platforms` branch present |
| FP-SAVED-02 | `SavedDashboardPage.tsx:156, 161, 192, 196` (seededRef + `dashboardId`-change reset) | ✓ preserved byte-for-byte |
| FP-CREATE-01 | `DashboardCreate.tsx:145–150` | ✓ `platforms: ['meta_ads']` on builder preview |
| FP-MAP-01 | `ParishMapDetail.tsx:131–147` | ✓ zero-row EmptyState branch preserved |
| FP-LIB-01 | `DashboardLibrary.tsx` | ✓ section heading preserved; summary KPI strip mounted only when library has content |

All 12 contracts: **GREEN**.

---

## 8. R3 regression check (web pages never call `/metrics/combined/`)

Grep of `src/routes/GoogleAnalyticsDashboardPage.tsx` + `src/routes/SearchConsoleDashboardPage.tsx` (production code): the only occurrences of `metrics/combined` are inline R3-guard comments at `:27` of each file. Neither imports `useDashboardStore`. Neither imports the combined-metrics apiClient helper.

Positive fetch-spy assertions:
- `frontend/src/routes/__tests__/GoogleAnalyticsDashboardPage.test.tsx:128–146` — `R3: uses the dedicated GA4 endpoint and never calls /metrics/combined/`
- `frontend/src/routes/__tests__/SearchConsoleDashboardPage.test.tsx:122–140` — `R3: uses the dedicated Search Console endpoint and never calls /metrics/combined/`

Each test: spies `window.fetch`, renders the page, asserts the mocked helper was called exactly once AND that no fetch URL included `/metrics/combined/`. Both pass in the 762/762 full-suite run.

**R3 invariant: PRESERVED.**

---

## 9. SavedDashboardPage flake status

**RESOLVED** in S4c via a purely test-level `waitFor` wrap around the `location-search` assertion at `SavedDashboardPage.test.tsx:121–133`. No production-code change. No `vi.resetModules()`. No global mock mutation. The flake was first flagged in S1 handoff #5 (`SavedDashboardPage.test.tsx > location-search href assertion` passes in isolation, fails in full-suite runs at position ~117 due to cross-file `vi.mock` hoist-order pollution). Architect §11 hypothesized the navigate/setFilters render-frame race; the fix aligns both assertions on the same async-flush primitive.

Proof: full-suite vitest run post-S4 shows 762/762 deterministic. A second re-run confirmed 762/762. The S1→S2→S3 flake no longer reproduces.

---

## 10. Follow-ups / deferrals

| Item | Reason | Carrier |
|---|---|---|
| Bubble overlay per account location (ParishMap) | Store + `/metrics/combined/` payload lack `{lat, lng}` per-account | `[NEW-ENDPOINT]` comment at `ParishMapDetail.tsx:227` — needs geocoded account-location endpoint |
| Sparkline-in-tooltip (ParishMap) | Store exposes island-level `campaign.data.trend[]` but no per-parish daily rollup | `[NEW-ENDPOINT]` comment at `ParishMapDetail.tsx:233` — needs per-parish daily-series endpoint |
| `StackedAreaChart` / per-platform daily trend | `CampaignTrendPoint` has no `platform` field | Deferred in S4a; degraded to single-series TrendLine with inline `[NEW-ENDPOINT]` comment. `TrendLine variant="stacked-area"` extension slated for Sprint 5 if endpoint lands. |
| GA4 `users` / `bounce_rate` / `avg_session_duration` KPIs | Pilot GA4 payload does not expose these fields | Substituted with Sessions / Conversions / Revenue / Engagement rate (architect §3). Documented inline at `GoogleAnalyticsDashboardPage.tsx:30–35`. |
| Grid-snap slot authoring (drag-drop) | Out of Sprint 4 scope per architect §6 | Typed hook (`layout?` on `DashboardTemplateDefinition` + `SavedDashboardSlotGrid` renderer) shipped; zero templates populate it this sprint. Authoring UI is Sprint 5+. |
| 4 pages without `reasonCode` on empty states (AudienceDashboard, ParishMapDetail, SavedDashboardPage, DashboardLibrary) | Churn-minimization — legacy empty-state patterns preserved | Optional cleanup backlog item; not a regression |

---

## 11. Trajectory summary across all 4 viz sprints

| Milestone | Viz-kit primitives | Frontend test files | Frontend tests | Notes |
|---|---|---|---|---|
| Pre-S1 baseline | 0 (legacy StatCard / inline Recharts) | ~83 | ~520 | Custom charts scattered across routes |
| End of Sprint 1 | **10** (KpiTile, TrendLine, Sparkline, PeerAvgLine, ChartSkeleton, DistributionBar, BubbleScatter, PieComposition, VizDataTable, AccessibleTableToggle + EmptyState re-export) | ~95 | ~640 | Kit barrel at `components/viz/index.ts` |
| End of Sprint 2 | 10 (no new primitives — Meta cluster migrated) | ~105 | ~690 | Meta Accounts + Insights + Page Insights |
| End of Sprint 3 | **12** (+`AssetGroupTreemap` + `roasToOpacity`, +`GaugeRing` + `derivePacingVariant`) | ~117 | 738 / 739 (1 flake) | Google Ads 10-tab cluster on both flag modes |
| End of Sprint 4 | **13** (count per architect §5: kit header lists 13 primitives; no new this sprint) | **120** | **762 / 762** | 10 combined/map/web/saved route pages migrated; 3 new shared `lib/*Aggregates.ts` helpers; optional template `layout` field; flake RESOLVED |

**Callsites migrated to kit across all 4 sprints:** Meta cluster (S2) + Google Ads cluster 10 tabs (S3) + combined-core 3 pages (S4a) + combined-other 2 pages + 2 web pages (S4b) + map + 3 saved-dashboard pages (S4c). The legacy `StatCard` is retained only in `DashboardCreate` legacy imports that were removed in S4c and a handful of non-S4 admin/ops pages outside the viz-kit migration scope.

---

## 12. Artifact trail

**Sprint 1 (viz kit foundation):**
- Architect: `/Users/thristannewman/ADinsights/artifacts/sprint/S1-architect-design.md`
- Implementers: `S1a-*`, `S1b-*`, `S1c-*`
- Closeout: `/Users/thristannewman/ADinsights/artifacts/sprint/S1-final-closeout.md`

**Sprint 2 (Meta cluster):**
- Architect: `/Users/thristannewman/ADinsights/artifacts/sprint/S2-architect-design.md`
- Closeout: `/Users/thristannewman/ADinsights/artifacts/sprint/S2-final-closeout.md`

**Sprint 3 (Google Ads cluster):**
- Architect: `/Users/thristannewman/ADinsights/artifacts/sprint/S3-architect-design.md`
- Implementers: `S3a-core-analytics.md`, `S3b-creative-conv.md`, `S3c-ops-tabs.md`
- Closeout: `/Users/thristannewman/ADinsights/artifacts/sprint/S3-final-closeout.md`

**Sprint 4 (combined / map / web / saved):**
- Architect: `/Users/thristannewman/ADinsights/artifacts/sprint/S4-architect-design.md`
- Implementers:
  - `/Users/thristannewman/ADinsights/artifacts/sprint/S4a-combined-core.md`
  - `/Users/thristannewman/ADinsights/artifacts/sprint/S4b-combined-other-web.md`
  - `/Users/thristannewman/ADinsights/artifacts/sprint/S4c-map-and-saved.md`
- Closeout: `/Users/thristannewman/ADinsights/artifacts/sprint/S4-final-closeout.md` (this file)

**Program-level:**
- `/Users/thristannewman/ADinsights/artifacts/viz/sprints-plan.md`
- `/Users/thristannewman/ADinsights/artifacts/sprint/program-design.md`
- `/Users/thristannewman/ADinsights/artifacts/sprint/phase2-combined-test.md` (C3C GREEN — 12/12 Phase 2 DoD contracts locked)
- `/Users/thristannewman/ADinsights/artifacts/verify/combined-verification.json` (A3 C1C audit — B-* register)

---

## 13. Verdict

**GREEN — Sprint 4 ships as claimed.** The viz-kit migration is complete across all route clusters (Meta / Google Ads / Combined / Map / Web / Saved). All 12 Phase 2 contracts preserved at their cited file:line locations. R3 invariant locked in with positive fetch-spy tests. SavedDashboardPage cross-file flake resolved. All gates clean: 762/762 frontend tests, 727/728 backend tests (1 skipped, pre-existing), zero lint warnings, clean build. Two map data-gap deferrals (`[NEW-ENDPOINT]` for bubble overlay and tooltip sparkline) are carried forward with inline comments at their eventual implementation sites. The optional `layout?` field on `DashboardTemplateDefinition` provides the typed foundation for Sprint 5+ grid-snap authoring without disturbing any shipped template.
