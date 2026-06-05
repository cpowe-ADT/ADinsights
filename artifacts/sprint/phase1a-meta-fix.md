# Phase 1A Meta Fix Report

**Agent:** C2A — Meta Fix  
**Date:** 2026-04-14  
**Inputs cited:**

- `/Users/thristannewman/ADinsights/artifacts/sprint/phase1a-meta-audit.json`
- `/Users/thristannewman/ADinsights/artifacts/sprint/program-design.md` (lines 502–555)

---

## Files Modified

| File                                                          | Change summary                                                                                                                                                   | Lines +/- |
| ------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- |
| `frontend/src/routes/MetaAccountsPage.tsx`                    | C1A-NEW-01: Added `!showRecoveryFallback &&` guard on row onClick; R5: added `reasonCode="error"` and `reasonCode="no_accounts"` to 2 EmptyState callers         | +3 / -1   |
| `frontend/src/routes/MetaPagePostsPage.tsx`                   | M14: Replaced raw `<div className="panel meta-warning-panel">` with `<EmptyState reasonCode="no_posts" ...>`; R5: added `reasonCode="error"` to error EmptyState | +6 / -5   |
| `frontend/src/routes/DashboardLayout.tsx`                     | C1A-NEW-02: Added reactive `metaAccountId` Zustand subscription; added `metaAccountId` to R7 reconciliation effect dep array                                     | +5 / -2   |
| `frontend/src/routes/MetaPageOverviewPage.tsx`                | C1A-NEW-03: Updated `handleMetricChange` and `handlePeriodChange` to pass `{ metric, period }` overrides to `loadTimeseries`                                     | +6 / -2   |
| `frontend/src/state/useMetaPageInsightsStore.ts`              | C1A-NEW-03: Extended `loadTimeseries` type and implementation to accept `overrides?: { metric?: string; period?: string }` matching the M16 pattern              | +3 / -2   |
| `frontend/src/routes/MetaInsightsDashboardPage.tsx`           | R5: added `reasonCode="error"` and `reasonCode="no_data_for_range"` to 2 EmptyState callers                                                                      | +2 / -0   |
| `frontend/src/routes/MetaCampaignOverviewPage.tsx`            | R5: added `reasonCode="error"` and `reasonCode="no_data_for_range"` to 2 EmptyState callers                                                                      | +2 / -0   |
| `frontend/src/routes/MetaPagesListPage.tsx`                   | R5: added `reasonCode="error"` and `reasonCode="no_accounts"` to 2 EmptyState callers                                                                            | +2 / -0   |
| `frontend/src/routes/__tests__/MetaAccountsPage.test.tsx`     | Added 2 tests: normal row click calls setFilters; recovery-fallback row click does NOT call setFilters                                                           | +52 / -1  |
| `frontend/src/routes/__tests__/MetaPagePostsPage.test.tsx`    | Added 1 test: zero posts renders EmptyState with `data-reason-code="no_posts"`                                                                                   | +18 / -0  |
| `frontend/src/routes/__tests__/MetaPageOverviewPage.test.tsx` | Added 1 test: period select change passes override to loadTimeseries                                                                                             | +18 / -1  |
| `frontend/src/routes/__tests__/DashboardLayout.test.tsx`      | Added 1 test: R7 reconciliation effect copies Meta accountId to global filters on meta route                                                                     | +32 / -8  |

---

## Tests Added

| File                            | Kind                         | Cases                                                                                |
| ------------------------------- | ---------------------------- | ------------------------------------------------------------------------------------ |
| `MetaAccountsPage.test.tsx`     | Unit — click handler guard   | (1) normal row calls setFilters; (2) recovery row does NOT call setFilters           |
| `MetaPagePostsPage.test.tsx`    | Unit — empty state component | (1) zero posts renders EmptyState with `data-reason-code="no_posts"`                 |
| `MetaPageOverviewPage.test.tsx` | Unit — overrides pattern     | (1) period change passes `{ period }` override to loadTimeseries                     |
| `DashboardLayout.test.tsx`      | Integration — R7 dep array   | (1) Meta accountId in store propagates to useDashboardStore.setFilters on meta route |

---

## Test Results

### Targeted Meta tests (all pass)

```
 ✓ MetaAccountsPage.test.tsx > explains that Meta accounts and Facebook pages are separate assets
 ✓ MetaAccountsPage.test.tsx > calls setFilters with accountId when a normal account row is clicked
 ✓ MetaAccountsPage.test.tsx > does not call setFilters when a recovery-fallback row is clicked
 Test Files  1 passed (1) | Tests  3 passed (3)

 ✓ MetaPagePostsPage.test.tsx > renders posts table and updates query on search
 ✓ MetaPagePostsPage.test.tsx > shows reconnect guidance when post insights permissions are missing
 ✓ MetaPagePostsPage.test.tsx > renders a back link to the pages list
 ✓ MetaPagePostsPage.test.tsx > renders EmptyState with reasonCode no_posts when posts list is empty
 ✓ MetaPagePostsPage.test.tsx > shows restore guidance when marketing access is orphaned
 Test Files  1 passed (1) | Tests  5 passed (5)

 ✓ MetaPageOverviewPage.test.tsx > renders KPI cards and hides unsupported metric card
 ✓ MetaPageOverviewPage.test.tsx > shows reconnect guidance when page insights permissions are missing
 ✓ MetaPageOverviewPage.test.tsx > renders a back link to the pages list
 ✓ MetaPageOverviewPage.test.tsx > shows restore guidance when marketing access is orphaned
 ✓ MetaPageOverviewPage.test.tsx > renders engagement breakdown section when breakdown data is present
 ✓ MetaPageOverviewPage.test.tsx > passes period override to loadTimeseries when period select changes
 ✓ MetaPageOverviewPage.test.tsx > does not render engagement breakdown when breakdown data is absent
 Test Files  1 passed (1) | Tests  7 passed (7)

 ✓ DashboardLayout.test.tsx (all 13 tests pass including new C1A-NEW-02 test)
 Test Files  1 passed (1) | Tests  13 passed (13)
```

### Full suite

```
 Test Files  2 failed | 100 passed (102)
      Tests  11 failed | 516 passed (527)
   Start at  00:43:20
   Duration  71.06s
```

Pre-existing failures only (unchanged from baseline):

- `DataSources.test.tsx` — 10 failures, all from `scrollIntoView is not a function` (pre-existing jsdom limitation)
- `SavedDashboardPage.test.tsx` — 1 failure (pre-existing, unrelated to this sprint)

No new failures introduced by this patch.

---

## Build Output

```
dist/assets/MetaPagePostsPage-iJHuWBqi.js               9.27 kB │ gzip:   3.11 kB
dist/assets/MetaPageOverviewPage-CKHSJWTq.js           12.36 kB │ gzip:   4.15 kB
dist/assets/DashboardLayout-CrcN-5n9.js                29.47 kB │ gzip:   9.83 kB
dist/assets/index-CPu-RCGp.js                         273.09 kB │ gzip:  87.34 kB
dist/assets/generateCategoricalChart-CynvBb_n.js      383.99 kB │ gzip: 105.92 kB
✓ built in 18.81s
```

Lint: clean (no ESLint errors).

---

## Fix Details

### C1A-NEW-01 — Recovery-fallback row click guard (MetaAccountsPage.tsx line 297)

**Root cause:** The M2 onClick handler called `setFilters({ accountId: account.external_id })` unconditionally for all rows including recovery-discovered accounts. Recovery rows have ghost IDs not in the ORM; downstream `loadInsights`/`loadCampaigns` would return 0 rows.  
**Fix:** `onClick={() => !showRecoveryFallback && setFilters({ accountId: account.external_id })}`  
Recovery rows are still rendered (for display/triage), but clicking them is a no-op.

### M14 — Zero posts EmptyState (MetaPagePostsPage.tsx lines 305–311)

**Root cause:** The raw `<div className="panel meta-warning-panel">` remained despite the synthesis report marking M14 as clean.  
**Fix:** Replaced with `<EmptyState icon=... title="No posts found" message="..." reasonCode="no_posts" className="panel" />` — consistent with the cluster pattern.

### C1A-NEW-02 — DashboardLayout R7 dep array (DashboardLayout.tsx lines 148–152, 290)

**Root cause:** The reconciliation effect's dep array `[location.pathname, setFilters]` only fired on navigation. Intra-route account changes (clicking a second account while staying on `/dashboards/meta/accounts`) updated `useMetaStore` but not the global FilterBar.  
**Fix:** Added `const metaAccountId = useMetaStore((state) => state.filters.accountId)` as a reactive selector; added `metaAccountId` to the dep array. The effect now re-fires whenever the Meta store's accountId changes, regardless of route navigation.

### C1A-NEW-03 — handleMetricChange/handlePeriodChange overrides (MetaPageOverviewPage.tsx + useMetaPageInsightsStore.ts)

**Root cause:** Both handlers called `setFilters()` then `void loadTimeseries(pageId)` without passing the new values. `loadTimeseries` read from `get().filters` — which was already updated synchronously by Zustand's `set()` — but the call bypassed the primary data effect entirely. The M16 fix (overrides pattern) was not applied to this code path.  
**Fix:** Extended `loadTimeseries` type signature to accept `overrides?: { metric?: string; period?: string }` and implemented fallback `overrides?.metric ?? filters.metric`. Both handlers now pass the new values explicitly: `loadTimeseries(pageId, { metric, period: nextPeriod })` and `loadTimeseries(pageId, { period })`.

### R5 — EmptyState reasonCode at all Meta-cluster call sites

**Root cause:** The `reasonCode` prop was added to `EmptyState.tsx` (R5 component-level fix) but never passed at any call site in the Meta cluster.  
**Fix:** Added `reasonCode` to 10 EmptyState call sites across 5 files:

- `MetaAccountsPage.tsx`: `"error"`, `"no_accounts"`
- `MetaInsightsDashboardPage.tsx`: `"error"`, `"no_data_for_range"`
- `MetaCampaignOverviewPage.tsx`: `"error"`, `"no_data_for_range"`
- `MetaPagesListPage.tsx`: `"error"`, `"no_accounts"`
- `MetaPagePostsPage.tsx`: `"error"`, `"no_posts"` (the new EmptyState from M14)

---

## Deferred (with reasons)

None — all 5 assigned bugs addressed.

Note: The `MetaPagePostsPage.tsx` and `MetaPageOverviewPage.tsx` tests expose that the component's `<label>` for the period `<select>` uses a `<span>` (not a proper `for=`/`id` link). The test worked via `{ name: /period/i }` because the label wraps the select. This is a minor accessibility debt but is out of scope per sprint instructions.

---

## Status: GREEN

All 5 assigned bugs fixed. Lint clean. Build succeeds. 4 new test cases added, all passing. Pre-existing failures (DataSources scrollIntoView, SavedDashboardPage) unchanged.
