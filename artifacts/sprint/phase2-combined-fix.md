Inputs cited: `/Users/thristannewman/ADinsights/artifacts/sprint/program-design.md` (prompt template lines 601-648) and `/Users/thristannewman/ADinsights/artifacts/sprint/phase2-combined-audit.json` (C1C audit).

# Phase 2 — C2C Combined Fix Report

Agent: C2C
Scope: Combined/cross-platform dashboard polish (B-CAMP-02 empty-state gap, B-PLAT-03 hardcoded KPI labels, regression test for FP-CAMP-01/FP-CREA-01/FP-BUDG-02 selectors).
Deferred (not touched): NB-PLAT-01 (demo-mode toggles — per OQ2), B-CAMP-01/B-CREA-01/B-BUDG-02 selectors (already APPLIED).

## Files Modified

| File                                                       | Change summary                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 | Line delta |
| ---------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | ------------------- | --------- |
| `frontend/src/routes/CampaignDashboard.tsx`                | FP-CAMP-02: Collapsed two duplicate empty-state branches (prev lines 336-365 and 367-400) into a single consolidated guard. Added missing case: `hasCampaignData && rows.length === 0 && availability.status === 'available'` now renders the "no-results" EmptyState instead of a silently empty `CampaignTable`. Reason detection falls through `availabilityReason                                                                                                                          |            | availableButEmpty`. | -22 (net) |
| `frontend/src/routes/PlatformDashboard.tsx`                | FP-PLAT-03: Replaced hardcoded `fbRow` / `igRow` lookups with a top-2-by-spend derivation from `byPlatform`. KPI labels now read `${formatPlatformLabel(row.platform)} spend` so the tiles reflect whichever platforms are returned (Meta-only, Google-only, or both). "Top platform" by conversions also uses the new formatter so it no longer leaks raw `facebook` / `instagram` strings. Added a local `formatPlatformLabel` helper that capitalizes tokens and uppercases short acronyms. | +22 (net)  |
| `frontend/src/state/useDashboardStore.test.ts`             | Added regression test asserting that `getCampaignRowsForSelectedParish`, `getCreativeRowsForSelectedParish`, and `getBudgetRowsForSelectedParish` all honor `filters.platforms` (with and without a `selectedParish`, for both single-platform and both-platforms scopes). Guards against silent regression of the FP-CAMP-01 / FP-CREA-01 / FP-BUDG-02 selector patches in `useDashboardStore.ts` lines 1485-1617.                                                                            | +156       |
| `frontend/src/routes/__tests__/PlatformDashboard.test.tsx` | Updated existing "renders heading and KPIs" assertion to expect the new capitalized `Top platform: Facebook` label emitted by the FP-PLAT-03 formatter (previously asserted raw `facebook`). Added inline comment pointing to FP-PLAT-03.                                                                                                                                                                                                                                                      | +2 / -2    |

## Tests Added

### `useDashboardStore > parish-drilldown selectors respect filters.platforms (FP-CAMP-01/FP-CREA-01/FP-BUDG-02)`

Seeds the store with a mixed Meta + Google Ads dataset (campaign, creative, budget rows, all in Kingston) and asserts:

1. **Baseline (`platforms=[]`)** — all three selectors return both rows each (control).
2. **`platforms=['meta_ads']`, no parish selected** — `getCampaignRowsForSelectedParish` returns only `cmp_meta_kg`; `getCreativeRowsForSelectedParish` returns only `cr_meta_kg`; `getBudgetRowsForSelectedParish` returns only `bg_meta_kg`. Google Ads rows are excluded.
3. **Same scope, parish drilldown into Kingston** — selectors still return the single Meta row each. This is the exact scenario B-CAMP-01 / B-CREA-01 / B-BUDG-02 addressed.
4. **`platforms=['google_ads']`** — selectors return only the Google Ads rows; Meta rows are excluded.
5. **`platforms=['meta_ads','google_ads']`** — both rows returned by each selector (both-platforms scope parity).

### `PlatformDashboard > renders heading and KPIs with platforms data` (updated)

Now asserts `Top platform: Facebook` (FP-PLAT-03 capitalized label) instead of `Top platform: facebook`.

## Test Results

### Targeted vitest

```
 ✓ src/routes/__tests__/BudgetDashboard.test.tsx (3 tests) 138ms
 ✓ src/routes/__tests__/PlatformDashboard.test.tsx (3 tests) 168ms
 ✓ src/routes/__tests__/AudienceDashboard.test.tsx (3 tests) 174ms
 ✓ src/routes/__tests__/SavedDashboardPage.test.tsx (1 test) 121ms
 ✓ src/routes/__tests__/ParishMapDetail.test.tsx (6 tests) 188ms
 ✓ src/routes/__tests__/CampaignDashboard.layout.test.tsx (1 test) 448ms

 Test Files  6 passed (6)
      Tests  17 passed (17)
```

Additional confirmation on `useDashboardStore.test.ts` (14 tests, including the new regression):

```
 ✓ src/state/useDashboardStore.test.ts (14 tests) 701ms

 Test Files  1 passed (1)
      Tests  14 passed (14)
```

### Lint

```
> adinsights-frontend@0.1.0 lint
> eslint .
```

(exit 0, no warnings)

### Build

```
dist/assets/CampaignDashboard-CwFGspOX.js              28.79 kB │ gzip:  10.09 kB
dist/assets/DashboardLayout-Ccr32snM.js                29.47 kB │ gzip:   9.83 kB
dist/assets/useDashboardStore-B0-1E8X6.js              32.42 kB │ gzip:   8.15 kB
...
✓ built in 3.79s
```

## Status

**GREEN** — All three scoped fixes applied with minimal diffs, all targeted vitest suites pass (17/17), regression coverage added for the parish-drilldown platform-filter selectors, lint clean, production build succeeds.

Pre-existing failures noted (out of scope per prompt): `DataSources.test.tsx` scrollIntoView failures documented in the C1C audit baseline — not re-triggered because `DataSources` is not in the targeted suite list.
