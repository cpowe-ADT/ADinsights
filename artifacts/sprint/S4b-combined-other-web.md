# S4b — CombinedOther+Web Implementation Report

Input citations:
- `artifacts/sprint/S4-architect-design.md` §3 (page layouts), §4 (R3 fetch-URL assertion test), §9.2 (DoD).
- `CLAUDE.md` (guardrails, adapter priority, frontend state architecture).
- `docs/project/api-contract-changelog.md` (Phase 2 contracts B-BUDG-01, FP-AUD-01).

## Files Modified

| Path | Change |
|---|---|
| `frontend/src/lib/webAnalyticsAggregates.ts` | NEW — shared client-side aggregators for GA4 + Search Console (totals, trend-by-day, by-channel, by-device, top queries). Exports `Ga4TrendPoint` / `SearchConsoleTrendPoint` with `[key: string]` index signature so they satisfy `TrendLinePoint`. |
| `frontend/src/routes/BudgetDashboard.tsx` | Refactored to 5-block viz-kit layout (KpiTile×3, paired DistributionBar, cumulative TrendLine with ghost budget line, VizDataTable with pacing risk chip, legacy BudgetPacingList retained). Platform-color legend added. FP-BUDG-01 guard preserved verbatim at lines 64–69. |
| `frontend/src/routes/AudienceDashboard.tsx` | Refactored to 5-block layout (KpiTile×4 with Top Device hidden when `platforms.data.byDevice` absent, PieComposition by gender, DistributionBar for age, DistributionBar for device). FP-AUD-01 guard preserved verbatim. |
| `frontend/src/routes/GoogleAnalyticsDashboardPage.tsx` | Refactored to KPI strip + Sessions trend + channel PieComposition + VizDataTable. **R3 preserved**: no `useDashboardStore` import. Substituted KPIs per architect §3 (Sessions / Conversions / Revenue / Engagement rate — Users/Bounce/Duration not in GA4 payload). `PIE_PALETTE` hoisted to module scope to satisfy exhaustive-deps lint. |
| `frontend/src/routes/SearchConsoleDashboardPage.tsx` | Refactored to KPI strip + dual-axis TrendLine + device PieComposition + VizDataTable (top 50 queries). **R3 preserved**: no `useDashboardStore` import. `DEVICE_PALETTE` hoisted to module scope to satisfy exhaustive-deps lint. |
| `frontend/src/routes/__tests__/BudgetDashboard.test.tsx` | Replaced with viz-kit test: mocks viz primitives via `data-testid`, verifies KPI strip + DistributionBar + TrendLine + VizDataTable + pacing-risk-chip; preserves FP-BUDG-01 (`availability === undefined` → no empty state). |
| `frontend/src/routes/__tests__/AudienceDashboard.test.tsx` | Replaced with viz-kit test: verifies 4 KpiTiles when `platforms.data` present, 3 when absent (Top Device hidden), preserves FP-AUD-01 empty-state branch. |
| `frontend/src/routes/__tests__/GoogleAnalyticsDashboardPage.test.tsx` | Replaced with viz-kit test + R3 fetch-spy assertion that `/metrics/combined/` is never called and `fetchGoogleAnalyticsWebRows` is the only path. |
| `frontend/src/routes/__tests__/SearchConsoleDashboardPage.test.tsx` | Replaced with viz-kit test + R3 fetch-spy assertion. |

## Phase 2 Contracts Preserved

### FP-BUDG-01 (B-BUDG-01) — demo-adapter false empty-state guard
File: `frontend/src/routes/BudgetDashboard.tsx` lines 64–69 (verbatim):

```tsx
// FP-BUDG-01: Guard against undefined availability (e.g. demo adapter) triggering false empty state.
// Only show empty state when availability is explicitly populated and non-available,
// OR when there is genuinely no budget data yet.
const shouldShowEmptyState =
  (budgetAvailability !== undefined && budgetAvailability.status !== 'available') ||
  (!budget.data && budget.status !== 'loading');
```

Guarded by test `BudgetDashboard.test.tsx` — `"FP-BUDG-01: does NOT render empty state when availability is undefined (demo adapter)"` (lines 221–246).

### FP-AUD-01 — gender/age-gender empty detection
File: `frontend/src/routes/AudienceDashboard.tsx` — guard retained in the render path. Covered by test `AudienceDashboard.test.tsx` — `"FP-AUD-01: shows empty state when byAgeGender and byGender arrays are empty"` (lines 189–203).

## R3 Invariant — Web pages never call `/metrics/combined/`

Both GA4 and Search Console pages import NO Zustand store and NO `apiClient` combined-metrics helper; they only call the dedicated wrappers in `frontend/src/lib/webAnalytics.ts` which hit `/analytics/web/ga4/` and `/analytics/web/search-console/` respectively.

**GA4 R3 test** — `frontend/src/routes/__tests__/GoogleAnalyticsDashboardPage.test.tsx`:

```ts
it('R3: uses the dedicated GA4 endpoint and never calls /metrics/combined/', async () => {
  // R3: Web page must never call /metrics/combined/.
  const fetchSpy = vi.spyOn(window, 'fetch');
  render(
    <MemoryRouter>
      <GoogleAnalyticsDashboardPage />
    </MemoryRouter>,
  );
  await waitFor(() => {
    expect(webAnalyticsMocks.fetchGoogleAnalyticsWebRows).toHaveBeenCalled();
  });
  const urls = fetchSpy.mock.calls.map((c) => String(c[0]));
  expect(urls.some((u) => u.includes('/metrics/combined/'))).toBe(false);
  expect(webAnalyticsMocks.fetchGoogleAnalyticsWebRows).toHaveBeenCalledTimes(1);
});
```

**Search Console R3 test** — `frontend/src/routes/__tests__/SearchConsoleDashboardPage.test.tsx`:

```ts
it('R3: uses the dedicated Search Console endpoint and never calls /metrics/combined/', async () => {
  // R3: Web page must never call /metrics/combined/.
  const fetchSpy = vi.spyOn(window, 'fetch');
  render(
    <MemoryRouter>
      <SearchConsoleDashboardPage />
    </MemoryRouter>,
  );
  await waitFor(() => {
    expect(webAnalyticsMocks.fetchSearchConsoleWebRows).toHaveBeenCalled();
  });
  const urls = fetchSpy.mock.calls.map((c) => String(c[0]));
  expect(urls.some((u) => u.includes('/metrics/combined/'))).toBe(false);
  expect(webAnalyticsMocks.fetchSearchConsoleWebRows).toHaveBeenCalledTimes(1);
});
```

Note on methodology: the page wraps its call through the `fetchGoogleAnalyticsWebRows` / `fetchSearchConsoleWebRows` helpers (mocked in these tests). The `window.fetch` spy complements the mock: it asserts that NO fetch activity at all reaches `/metrics/combined/`, while the helper-call assertion proves the dedicated endpoint wrapper is the only data path. Both conditions must hold.

Source file inline comments at `GoogleAnalyticsDashboardPage.tsx` lines 25–29 and `SearchConsoleDashboardPage.tsx` lines 25–29 also document the R3 rule at the import boundary.

## GA4 KPI Substitution (architect §3)

GA4 rows do NOT expose `users`, `bounce_rate`, or `avg_session_duration` in the pilot payload. Per architect §3 availability audit, substituted the KPI strip with the four available fields: **Sessions / Conversions / Revenue / Engagement rate**. Documented inline at `GoogleAnalyticsDashboardPage.tsx` lines 30–35.

## Tests Added

| Test File | New Tests |
|---|---|
| `BudgetDashboard.test.tsx` | renders KpiTile + viz-kit blocks; skips paired bar for null-budget rows; FP-BUDG-01 preserved (availability blocked); FP-BUDG-01 demo-adapter branch (availability undefined); loading state. |
| `AudienceDashboard.test.tsx` | renders 4 KpiTiles with Top Device when platforms.data present; hides Top Device + device block when platforms.data absent; FP-AUD-01 empty-state branch; no-data empty state; error state. |
| `GoogleAnalyticsDashboardPage.test.tsx` | renders KpiTile×4 + TrendLine + PieComposition + VizDataTable; **R3 fetch-spy assertion**; `no_ga4_property_selected` empty state; `no_data_for_range` empty state. |
| `SearchConsoleDashboardPage.test.tsx` | renders KpiTile×4 + dual-axis TrendLine + PieComposition + VizDataTable; **R3 fetch-spy assertion**; `no_search_console_site_selected` empty state; `no_data_for_range` empty state. |

## Targeted Vitest — PASS

```
 RUN  v3.2.4 /Users/thristannewman/ADinsights/frontend

 ✓ src/routes/__tests__/BudgetDashboard.test.tsx (5 tests) 159ms
 ✓ src/routes/__tests__/AudienceDashboard.test.tsx (5 tests) 178ms
 ✓ src/routes/__tests__/SearchConsoleDashboardPage.test.tsx (4 tests) 231ms
 ✓ src/routes/__tests__/GoogleAnalyticsDashboardPage.test.tsx (4 tests) 316ms

 Test Files  4 passed (4)
      Tests  18 passed (18)
   Duration  4.87s
```

## Lint — PASS (zero errors, zero warnings)

```
> adinsights-frontend@0.1.0 lint
> eslint .
```

## Build — PASS

```
dist/assets/AudienceDashboard-DWZvHkDj.js                 10.13 kB │ gzip:  3.66 kB
dist/assets/BudgetDashboard-G2_qu1AR.js                   10.98 kB │ gzip:  3.96 kB
...
✓ built in 4.09s
```

## Status: **GREEN**

- R3 invariant holds for both GA4 and Search Console (fetch-spy + wrapper-call assertions).
- FP-BUDG-01 demo-adapter guard preserved verbatim and test-covered.
- FP-AUD-01 empty-state branch preserved and test-covered.
- GA4 KPI substitution documented inline and in this report (Sessions / Conversions / Revenue / Engagement rate).
- 18/18 targeted tests pass, lint clean, build clean.
