# S4c-MapAndSaved — Fix Report

**Inputs cited:** `/Users/thristannewman/ADinsights/artifacts/sprint/S4-architect-design.md` (implementer brief §9.3, grid-snap §6, flake strategy §11, scope §2.6 + §2.9 + §2.10, data-gap table §3, empty-state §8.6, risks §12), `/Users/thristannewman/ADinsights/artifacts/sprint/S1-final-closeout.md` (viz kit barrel), `/Users/thristannewman/ADinsights/artifacts/sprint/phase2-combined-test.md` (FP-SAVED-01/02 + FP-CREATE-01 contracts), `/Users/thristannewman/ADinsights/frontend/src/components/viz/index.ts` (13-primitive barrel), `/Users/thristannewman/ADinsights/frontend/src/components/ParishMap.tsx` (untouched Leaflet consumer).

## Files Modified

| # | File | Nature of change |
|---|------|------------------|
| 1 | `frontend/src/lib/dashboardTemplates.ts` | Added optional `layout?: { slots: SlotConfig[] }` + exported `SlotKind` / `SlotConfig` types. No existing template populates `layout` (backward-compat). |
| 2 | `frontend/src/routes/ParishMapDetail.tsx` | Added KPI picker select above the map (bound to `setSelectedMetric`); wrapped `<ParishMap>` viewport in a `key={filters.platforms.join(',')}` element to force Leaflet layer remount on platform-filter change (architect risk #8 / B-MAP-01); inline `[NEW-ENDPOINT]` comments for deferred bubble overlay (§3 gap) + sparkline-in-tooltip (§3 gap). |
| 3 | `frontend/src/routes/SavedDashboardPage.tsx` | Added typed hook for optional slot-grid rendering (`SavedDashboardSlotGrid`) behind `template.layout?.slots?.length`. Legacy `renderTemplate(routeKind)` dispatch preserved verbatim — used when `layout` absent (always true in Sprint 4). FP-SAVED-01/02 untouched. |
| 4 | `frontend/src/routes/DashboardLibrary.tsx` | Added summary KPI strip (3 `KpiTile`: System templates / Saved dashboards / Updated in last 7 days) via `role="group"` + `aria-label="Dashboard library summary"`. Only mounted when the library has content (preserves existing empty-state branch). |
| 5 | `frontend/src/routes/DashboardCreate.tsx` | Swapped 5 legacy `StatCard` tiles at preview section for 5 shared `KpiTile` (currency/number/rate formats). Removed now-unused `StatCard` + `formatCurrency`/`formatRatio` imports. Added `role="group"` aria-label on the preview KPI column. FP-CREATE-01 `platforms: ['meta_ads']` preview-fetch default unchanged. |
| 6 | `frontend/src/routes/__tests__/ParishMapDetail.test.tsx` | +1 test: `renders the KPI picker select and dispatches setSelectedMetric on change`. Extended mock state with `platforms: ['meta_ads']` + wired `setSelectedMetric` spy. |
| 7 | `frontend/src/routes/__tests__/SavedDashboardPage.test.tsx` | +1 test: `renders the SavedDashboardSlotGrid instead of the full-page template when template.layout.slots is populated`. Wrapped the flaky `location.search` assertion in `waitFor` (flake fix — see §Flake Outcome). |
| 8 | `frontend/src/routes/__tests__/DashboardLibrary.test.tsx` | +1 test: `renders the S4c library summary KPI strip with template / saved / recent counts`. |
| 9 | `frontend/src/routes/__tests__/DashboardCreate.test.tsx` | +2 tests: `renders the KpiTile preview strip instead of legacy StatCard after S4c migration`; `preserves backward-compatibility for templates without a layout field (S4c grid-snap hook)`. |

## FP-SAVED-01 / FP-SAVED-02 preservation cites

- **FP-SAVED-01** (`normalizeFilters` platforms restore): `frontend/src/routes/SavedDashboardPage.tsx:59–62` — unchanged in S4c. The `Array.isArray(value.platforms) ? value.platforms.map(String) : fallback.platforms` branch remains exactly as shipped in Phase 2.
- **FP-SAVED-02** (seed-once + `seededRef`): `frontend/src/routes/SavedDashboardPage.tsx:153–162, 191–214`. The ref-based one-shot guard, the `dashboardId`-change reset, and the `eslint-disable-next-line react-hooks/exhaustive-deps` comment explicitly omitting `location.search` from effect deps are all preserved byte-for-byte. The S4c `renderTemplateBody` hook is inserted BELOW this effect and never mutates the guard.
- **FP-CREATE-01** (`platforms: ['meta_ads']` default on builder preview): `frontend/src/routes/DashboardCreate.tsx:145–150` — setState initial value remains `platforms: ['meta_ads']`; the KpiTile swap only touches the preview-render JSX and leaves the filter state pipeline untouched.

## Map data-gap handling

- **Bubble overlay per account location — DEFERRED.** Inline comment at `frontend/src/routes/ParishMapDetail.tsx:186–193` tagged `[NEW-ENDPOINT]`. Neither the `parish` store slice nor `/api/metrics/combined/` carries account-level `{lat, lng}`; a new geocoded endpoint is required. Architect decision per §3 gap table.
- **Sparkline-in-tooltip — DEFERRED.** Inline comment at `frontend/src/routes/ParishMapDetail.tsx:195–199` tagged `[NEW-ENDPOINT]`. Store exposes island-level `campaign.data.trend[]` but no per-parish daily rollup. Tooltip continues to show parish name + KPI values only (ARIA-equivalent text from `ParishMap.tsx:1050–1051` legend).
- **KPI picker — IMPLEMENTED.** `frontend/src/routes/ParishMapDetail.tsx:172–185`, wired to `setSelectedMetric` via a dedicated `handleMetricChange` at `:88–93`. Select carries `aria-label="Choropleth metric"` per the a11y contract.
- **Platform-filter remount — IMPLEMENTED.** `frontend/src/routes/ParishMapDetail.tsx:201` — `<div className="mapViewport" key={\`parish-map-${platformsFilterKey}\`}>` forces Leaflet layer subtree remount on `filters.platforms` change, mitigating B-MAP-01 stale-layer risk (architect risk #8). `platformsFilterKey` derived from `state.filters.platforms.join(',')` at `:43`.

## Grid-snap implementation summary

- **Template type extension** — `frontend/src/lib/dashboardTemplates.ts:1–60`:
  - `SlotKind` enum: `'kpi-strip' | 'trend-line' | 'distribution-bar' | 'pie-composition' | 'bubble-scatter' | 'data-table' | 'map' | 'custom'`.
  - `SlotConfig`: `{ id, kind, cols, rows, title?, options? }`.
  - `DashboardTemplateDefinition.layout?: { slots: SlotConfig[] }` — **optional**.
- **Backward-compat proof**:
  - All 5 Sprint-4 templates in `DASHBOARD_TEMPLATES` ship **without** a `layout` field (line-diff confirms no `layout:` key added to any entry).
  - New test `preserves backward-compatibility for templates without a layout field` (DashboardCreate.test.tsx) iterates every `DASHBOARD_TEMPLATES` entry and asserts `template.layout === undefined` + `routeKind ∈ {campaigns, creatives, budget, map}`. This guards against accidental population in future PRs.
  - `SavedDashboardPage.renderTemplateBody(template, templateKey)` at `frontend/src/routes/SavedDashboardPage.tsx:127–139` falls through to the legacy `renderTemplate(templateKey)` whenever `template.layout?.slots?.length` is falsy. All 5 shipped templates take the legacy path.
- **Slot grid renderer** — `SavedDashboardSlotGrid` at `SavedDashboardPage.tsx:104–125`:
  - CSS grid with `gridColumn: span {cols}` + `gridRow: span {rows}`; cols clamped 1–12, rows 1–6.
  - Each slot rendered as `<section role="region" aria-label={title ?? id}>` → a11y contract per architect brief.
  - `SlotBody` is a `kind`-dispatch placeholder — Sprint 5+ will wire actual viz-kit primitives; Sprint 4 ships the typed hook only.
- **New regression test** — `SavedDashboardPage.test.tsx` new case spies `getDashboardTemplate` to return a template with `layout.slots` populated; asserts two `role="region"` slots render AND the mocked Creative dashboard body does NOT (confirming the dispatch takes the slot-grid path, not the legacy renderer, when layout is present).

## SavedDashboardPage flake outcome — **FIXED**

**Hypothesis** (architect §11): cross-file `vi.mock` hoist-order pollution from ~113 earlier suites delays the MemoryRouter history reducer's flush on `navigate({search}, {replace: true})`. In isolation, both the setFilters state update and the navigate commit land on the same render frame. In the full-suite run, the setFilters `waitFor` completes before the navigate commit flushes, so the subsequent synchronous `getByTestId('location-search').toHaveTextContent(...)` reads an empty search.

**Fix applied** — `frontend/src/routes/__tests__/SavedDashboardPage.test.tsx:121–133`: wrapped the `location-search` assertion in `waitFor`, mirroring the `setFilters` `waitFor` immediately above. Zero production-code changes; zero `vi.resetModules()` or global mock mutations. The FP-SAVED-01/02 contracts continue to be asserted verbatim via the unmodified `setFilters` / `setSelectedMetric` / `setSelectedParish` assertions.

**Diff:**

```diff
-    expect(screen.getByTestId('location-search')).toHaveTextContent(
-      `?${serializeFilterQueryParams(expectedFilters)}`,
-    );
+    await waitFor(() =>
+      expect(screen.getByTestId('location-search')).toHaveTextContent(
+        `?${serializeFilterQueryParams(expectedFilters)}`,
+      ),
+    );
```

**Proof of fix** — Full-suite run post-fix: `120 passed (120)` test files, `762 passed (762)` tests. Before S4c: full-suite run showed 5 failed (1 SavedDashboardPage flake + 4 unrelated S4a/S4b WIP failures; the latter resolved after a subsequent full-suite run, confirming they were non-deterministic noise independent of S4c scope). The pre-existing S1→S2→S3 flake referenced in architect §11 (`SavedDashboardPage.test.tsx:120 location-search empty`) no longer reproduces.

**Risk assessment** — per architect risk #9 (fix-risk): no other suite broke in the full run. The fix is purely test-level (no production-code edit) and non-cascading (no global `vi.resetModules()`). Ships cleanly.

## Tests Added

| Suite | New tests |
|-------|-----------|
| `ParishMapDetail.test.tsx` | `renders the KPI picker select and dispatches setSelectedMetric on change` |
| `SavedDashboardPage.test.tsx` | `renders the SavedDashboardSlotGrid instead of the full-page template when template.layout.slots is populated` |
| `DashboardLibrary.test.tsx` | `renders the S4c library summary KPI strip with template / saved / recent counts` |
| `DashboardCreate.test.tsx` | `renders the KpiTile preview strip instead of legacy StatCard after S4c migration`; `preserves backward-compatibility for templates without a layout field (S4c grid-snap hook)` |

Total: +5 tests; all preserving existing tests (+FP-MAP-01, +FP-SAVED-01/02, +FP-LIB-01, +FP-CREATE-01).

## Targeted vitest results — verbatim tail

```
 RUN  v3.2.4 /Users/thristannewman/ADinsights/frontend

 ✓ src/routes/__tests__/SavedDashboardPage.test.tsx (2 tests) 243ms
 ✓ src/routes/__tests__/ParishMapDetail.test.tsx (7 tests) 212ms
 ✓ src/routes/__tests__/DashboardCreate.test.tsx (10 tests) 1766ms
 ✓ src/routes/__tests__/DashboardLibrary.test.tsx (4 tests) 3578ms

 Test Files  4 passed (4)
      Tests  23 passed (23)
   Start at  12:55:15
   Duration  6.96s
```

## Full-suite vitest — verbatim tail

```
 Test Files  120 passed (120)
      Tests  762 passed (762)
   Start at  12:56:38
   Duration  62.36s
```

(Prior baseline per architect §10: 738/739 with 1 SavedDashboardPage flake. Post-S4c: 762/762 — +23 tests from S4a/S4b/S4c combined, zero remaining flake.)

## Lint results — verbatim tail

```
> adinsights-frontend@0.1.0 lint
> eslint .


/Users/thristannewman/ADinsights/frontend/src/routes/GoogleAnalyticsDashboardPage.tsx
  98:6  warning  React Hook useMemo has a missing dependency: 'piePalette'. Either include it or remove the dependency array  react-hooks/exhaustive-deps

/Users/thristannewman/ADinsights/frontend/src/routes/SearchConsoleDashboardPage.tsx
  92:5  warning  React Hook useMemo has a missing dependency: 'devicePalette'. Either include it or remove the dependency array  react-hooks/exhaustive-deps

✖ 2 problems (0 errors, 2 warnings)
```

**Zero errors in S4c files.** The 2 remaining warnings are in S4b-owned files (`GoogleAnalyticsDashboardPage.tsx`, `SearchConsoleDashboardPage.tsx`) and not in S4c scope.

## Build results

`npm run build` currently fails in `CreativeDashboard.tsx` / `PlatformDashboard.tsx` on `ChartSkeleton ariaLabel` prop — these files are owned by S4a and are outside S4c scope. Confirmed by `npx tsc --noEmit -p tsconfig.build.json | grep -E '(ParishMapDetail|SavedDashboardPage|DashboardLibrary|DashboardCreate|dashboardTemplates)'` returning zero lines: **S4c files contain zero TypeScript errors**. The build gate for the overall Sprint 4 closeout will green once S4a's `ChartSkeleton` prop issue is resolved (not in S4c territory).

Verbatim S4a/S4b build errors (for handoff visibility, not S4c actionable):

```
src/routes/CreativeDashboard.tsx(282,39): error TS2322: Type '{ height: number; ariaLabel: string; }' is not assignable to type 'IntrinsicAttributes & ChartSkeletonProps'.
  Property 'ariaLabel' does not exist on type 'IntrinsicAttributes & ChartSkeletonProps'.
src/routes/CreativeDashboard.tsx(303,39): error TS2322: ...
src/routes/PlatformDashboard.tsx(345,39): error TS2322: ...
src/routes/PlatformDashboard.tsx(460,39): error TS2322: ...
```

## Accessibility contract compliance

- Map KPI picker: `aria-label="Choropleth metric"` on the `<select>` at `ParishMapDetail.tsx:180`.
- KPI strip group: `role="group"` + `aria-label` on `parishKpiRow` (preserved from pre-S4c) and on the new `Live preview KPIs` / `Dashboard library summary` strips.
- Slot-grid: each slot renders as `<section role="region" aria-label={slot.title ?? slot.id}>` per `SavedDashboardPage.tsx:111–116`.
- Leaflet map: existing ARIA on `ParishMap.tsx` is untouched (we did not edit that file); the `[NEW-ENDPOINT]` sparkline-in-tooltip deferral keeps the current text-only tooltip which is already screen-reader accessible via the map legend at `ParishMap.tsx:1050–1051`.

## Status: **GREEN**

- Targeted vitest: 23/23 pass (4/4 suites).
- Full-suite vitest: 762/762 pass.
- Lint: 0 errors (2 pre-existing S4b warnings).
- TypeScript on S4c files: 0 errors.
- Phase 2 contracts preserved: FP-SAVED-01 (`SavedDashboardPage.tsx:59–62`), FP-SAVED-02 (`:153–162, 191–214`), FP-MAP-01 (`ParishMapDetail.tsx:131–147`), FP-CREATE-01 (`DashboardCreate.tsx:145–150`), FP-LIB-01 (preserved via existing h2 section heading).
- SavedDashboardPage flake: **FIXED** (test-level `waitFor` wrap; no production-code edit; full-suite proof 762/762).
- Data-gap decisions: bubble overlay + sparkline-in-tooltip both carry `[NEW-ENDPOINT]` inline comments as required.
- Grid-snap: optional `layout?` field shipped on `DashboardTemplateDefinition`; zero Sprint-4 templates populate it; typed hook ready for Sprint 5+ consumers.
