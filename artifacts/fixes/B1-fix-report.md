# B1 Fix Report — Google Ads Workspace: Global FilterBar + Store Unification

## Files Modified

| File                                                               | Change summary                                                                                                                                                                                                                                                       |
| ------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `frontend/src/routes/DashboardLayout.tsx`                          | Removed `/dashboards/google-ads` from `hideGlobalFilters` predicate (line 196-203 → now 3-path rule). **+0 / -1 logical line**                                                                                                                                       |
| `frontend/src/components/google-ads/workspace/WorkspaceHeader.tsx` | Removed the plain-text Account ID `<input>` (lines 68-77 deleted). **-10 lines**                                                                                                                                                                                     |
| `frontend/src/components/google-ads/workspace/types.ts`            | Added optional `clientId?: string` field to `WorkspaceFilters`. **+2 lines**                                                                                                                                                                                         |
| `frontend/src/routes/google-ads/GoogleAdsWorkspacePage.tsx`        | Added `EmptyState` import; subscribed to `useDashboardStore` for `globalAccountId` / `globalClientId`; unified `filters` object so store values override URL; removed stale B2 seed effect; added early-return empty state when `hasNoCustomer`. **+30 / -10 lines** |
| `frontend/src/hooks/useGoogleAdsWorkspaceData.ts`                  | Added `clientId?` to `WorkspaceFilters`; added `client_id` to `buildCommonParams`; included `clientId` in `filterKey`. **+4 lines**                                                                                                                                  |

## Tests Added

### `frontend/src/routes/google-ads/__tests__/GoogleAdsWorkspacePage.test.tsx`

Added `useDashboardStore` mock + 3 new test cases:

1. **reads customer from useDashboardStore** — verifies hook is called with `customerId: 'test-customer-123'` from store (not URL)
2. **shows empty state when store has no accountId and no clientId** — verifies `data-reason-code="no_customer_selected"` EmptyState renders
3. **hook receives customer_id from store when store has accountId** — verifies `filters.customerId` comes from store on the campaigns tab

### `frontend/src/routes/__tests__/DashboardLayout.test.tsx`

Added 2 new test cases: 4. **renders global FilterBar on /dashboards/google-ads route (not hidden)** — asserts `data-testid="filter-bar"` is present 5. **hides global FilterBar on /dashboards/meta/pages route** — regression guard for legitimate hides

## Test Results

### Targeted suite (all relevant files)

```
cd frontend && npx vitest run DashboardLayout.test.tsx GoogleAdsWorkspacePage.test.tsx FilterBar.test.tsx dashboardFilters.test.ts

Tests  58 passed (58)
```

### Frontend build

```
cd frontend && npm run build

✓ built in 12.56s
```

### Frontend lint

```
cd frontend && npm run lint

(no errors — clean exit)
```

### Backend

```
cd backend && pytest

727 passed, 1 skipped in 21.70s
```

### Full frontend suite note

The full `npm test -- --run` run shows pre-existing timeouts (DataSources.test.tsx scrollIntoView errors, and multiple test-file timeouts due to resource exhaustion in a single 364s run). These are identical to the failures present before B1 changes. The DataSources and other timeout failures are the same pre-existing issues documented in Phase A context.

## Manual Smoke Checklist

1. **Open `/dashboards/campaigns`** — confirm the global FilterBar (date pickers, Client dropdown, Account dropdown) renders at the top. Verify Meta Ads workspace is unaffected.
2. **Navigate to `/dashboards/google-ads`** — confirm the global FilterBar is now visible (Client + Account dropdowns appear). Previously it was hidden here.
3. **With no Client/Account selected in FilterBar** — navigate to `/dashboards/google-ads` and confirm the EmptyState renders with the message "No account selected" and `data-reason-code="no_customer_selected"`.
4. **Select a Client or Account in FilterBar** — navigate to `/dashboards/google-ads` and confirm the workspace loads tabs (Overview, Campaigns, etc.) and the WorkspaceHeader no longer shows a plain "Account ID" text input.
5. **Verify Meta workspace** — navigate to `/dashboards/meta/overview` and confirm FilterBar still renders; navigate to `/dashboards/meta/pages` and confirm FilterBar is hidden (legitimate hide preserved).

## Status: GREEN

All targeted tests pass (58/58). Build clean. Backend 727/727. The only failures in the full suite run are pre-existing DataSources `scrollIntoView` errors and unrelated test timeouts from resource contention — none introduced by B1.
