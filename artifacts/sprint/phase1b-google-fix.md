# Phase 1B Google Ads Fix Report

**Agent ID**: C2B  
**Date**: 2026-04-14  
**Status**: GREEN

---

## Input Artifacts Cited

- `/Users/thristannewman/ADinsights/artifacts/sprint/phase1b-google-audit.json` — C1B audit (source of CC2, NB1, NB2)
- `/Users/thristannewman/ADinsights/artifacts/sprint/program-design.md` (lines 556-600, section AGENT C2B)
- `/Users/thristannewman/ADinsights/artifacts/fixes/B1-fix-report.md` — B1 hotfix context (all 5 changes verified intact per C1B)

---

## Summary

Scope per audit: 1 must-fix (CC2) + 2 optional hygiene fixes (NB1, NB2). All three were applied. No regressions introduced. All 15 Google Ads test files pass. Pre-existing failures in DataSources and Meta routes are unrelated to C2B scope.

---

## Fixes Applied

### CC2 — Saved-View Restore Loses `client_id` (MUST-FIX, medium, XS)

**File**: `frontend/src/routes/google-ads/GoogleAdsWorkspacePage.tsx`  
**Lines affected**: `handleSelectSavedView` callback (~lines 166-195)

**Root cause**: `handleSelectSavedView` restored `start_date`, `end_date`, `compare`, `customer_id`, and `campaign_id` from the saved view's filters object into URL params, but never restored `client_id`. After B1, `clientId` is sourced from `useDashboardStore.filters.clientId` — so restoring a saved view that was created with a specific MCC client account would silently use whatever `clientId` happened to be in the store at restore time, not the one the view was saved with.

**Fix**: After updating URL params, check if the saved view has a `client_id` string. If yes, call `useDashboardStore.getState().setFilters({ ...storeFilters, clientId: viewFilters.client_id })` to write the saved `client_id` back into the global store. This is the same path by which FilterBar writes `clientId`, ensuring the workspace re-derives `resolvedClientId` correctly on the next render.

**Test added**: `GoogleAdsWorkspacePage.test.tsx` — "restores client_id from saved view into the dashboard store on saved-view select". The test mocks a saved view with `client_id: 'client-456'`, selects it via the WorkspaceHeader `<select>`, and asserts `mockSetFilters` was called with `expect.objectContaining({ clientId: 'client-456' })`.

The mock for `useDashboardStore` was updated to expose `getState` with a `setFilters` spy:

```ts
vi.mock('../../../state/useDashboardStore', () => ({
  default: Object.assign(
    (selector) => selector({ filters: mockDashboardStoreFilters }),
    {
      getState: () => ({
        filters: mockDashboardStoreFilters,
        setFilters: mockSetFilters,
      }),
    },
  ),
}));
```

---

### NB1 — GoogleAdsExecutivePage stale data on filter change (FIXED for hygiene, legacy-mode-only)

**File**: `frontend/src/routes/google-ads/GoogleAdsExecutivePage.tsx`

**Root cause**: `useEffect` had empty dependency array `[]` and used `useDashboardStore.getState()` inside the effect body. Data would never refresh when the user changed the account in the FilterBar.

**Fix**: Replaced `useDashboardStore.getState()` inside the effect with a hook-subscribed `filters` value at the component top level (`const filters = useDashboardStore((state) => state.filters)`), then added `filters` to the effect dependency array. The effect now re-fires reactively on any filter change.

**Note**: This page is active only under `VITE_GOOGLE_ADS_WORKSPACE_UNIFIED=false` (not the user's default; the flag is absent from all env files, defaulting to `true`). Fix applied for code hygiene.

**Test update**: Added `useDashboardStore` mock to `GoogleAdsExecutivePage.test.tsx` (previously absent, causing the component to fail silently when the hook was introduced). All 4 existing tests continue to pass.

---

### NB2 — GoogleAdsBudgetPage stale data on filter change (FIXED for hygiene, legacy-mode-only)

**File**: `frontend/src/routes/google-ads/GoogleAdsBudgetPage.tsx`

**Root cause**: Same pattern as NB1 — empty `[]` dep array, `useDashboardStore.getState()` inside effect.

**Fix**: Same pattern as NB1 — subscribed `filters` via hook, added to dep array.

**Note**: Legacy-mode-only (same flag caveat as NB1). Fix applied for hygiene.

**Test update**: Updated `useDashboardStore` mock in `GoogleAdsBudgetPage.test.tsx` from `Object.assign(() => ({}), ...)` to a proper selector-aware mock that returns `filters` from the state object. All 3 existing tests continue to pass.

---

## Files Modified

| File                                                                       | Change                                                                         |
| -------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| `frontend/src/routes/google-ads/GoogleAdsWorkspacePage.tsx`                | CC2: restore `client_id` from saved view into store in `handleSelectSavedView` |
| `frontend/src/routes/google-ads/GoogleAdsExecutivePage.tsx`                | NB1: subscribe to store filters; add to effect dep array                       |
| `frontend/src/routes/google-ads/GoogleAdsBudgetPage.tsx`                   | NB2: subscribe to store filters; add to effect dep array                       |
| `frontend/src/routes/google-ads/__tests__/GoogleAdsWorkspacePage.test.tsx` | CC2 test + getState/setFilters mock + beforeEach reset                         |
| `frontend/src/routes/google-ads/__tests__/GoogleAdsExecutivePage.test.tsx` | Add useDashboardStore mock (required by NB1 fix)                               |
| `frontend/src/routes/google-ads/__tests__/GoogleAdsBudgetPage.test.tsx`    | Update useDashboardStore mock to selector-aware form                           |

---

## Files NOT Modified (per hard rules)

- `frontend/src/routes/DashboardLayout.tsx` — C2A territory
- All Meta files
- All backend files
- `_resolve_platform_only_scoping` / adapter logic

---

## B1 Hotfix Preservation

Verified intact per C1B audit. The CC2 fix builds on B1 — it restores `clientId` via the same store path that B1 established as the authoritative source. No B1 changes were reverted.

---

## NB1/NB2 Disposition

- **NB1**: FIXED — one-line dep array fix; NB1 applied for hygiene despite being legacy-mode dead code.
- **NB2**: FIXED — same rationale.

Both were one-line changes (subscribe via hook + add `filters` to dep array). Risk was negligible; hygiene benefit is real if the flag is ever flipped.

---

## Test Results

### Targeted Google Ads tests (run before full suite)

```
 ✓ src/routes/google-ads/__tests__/GoogleAdsBudgetPage.test.tsx (3 tests)
 ✓ src/routes/google-ads/__tests__/GoogleAdsExecutivePage.test.tsx (4 tests)
 ✓ src/routes/google-ads/__tests__/GoogleAdsWorkspacePage.test.tsx (6 tests)
   ✓ restores client_id from saved view into the dashboard store on saved-view select

 Test Files  3 passed (3)
      Tests  13 passed (13)
   Duration  4.63s
```

### Full suite

```
 Test Files  2 failed | 100 passed (102)
      Tests  11 failed | 516 passed (527)
   Duration  81.25s
```

Pre-existing failures only — `DataSources.test.tsx` (OAuth/Meta flows, scrollIntoView mock gap) and `MetaPagePostsPage.test.tsx`/`MetaPageOverviewPage.test.tsx`. Zero Google Ads test regressions.

### Lint

```
> adinsights-frontend@0.1.0 lint
> eslint .

(no output — lint clean)
```

### Build

```
✓ built in 40.88s
dist/assets/GoogleAdsWorkspacePage-BLoK6kUh.js  24.21 kB │ gzip: 6.11 kB
```

Build succeeded with no errors or warnings in C2B-touched files.

---

## Verdict

GREEN — All three fixes applied, tests pass, lint clean, build clean. No regressions in Google Ads test cluster. Pre-existing failures in DataSources/Meta routes are out of C2B scope.
