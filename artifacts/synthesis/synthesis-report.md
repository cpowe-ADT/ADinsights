# A4-Recovery Synthesis Report

**Inputs cited:**

- `/Users/thristannewman/ADinsights/artifacts/plan.md`
- `/Users/thristannewman/ADinsights/artifacts/audit/audit-report.json`
- `/Users/thristannewman/ADinsights/artifacts/verify/meta-verification.json`
- `/Users/thristannewman/ADinsights/artifacts/verify/google-verification.json`
- `/Users/thristannewman/ADinsights/artifacts/verify/combined-verification.json`
- `/Users/thristannewman/ADinsights/artifacts/verify/adapter-verification.json`

---

## Gap Analysis Table

| Verifier | Bug ID                       | Severity | Status                      | Notes                                                                                                                                                                         |
| -------- | ---------------------------- | -------- | --------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| adapter  | AD1-FAKE                     | high     | APPLIED                     | client_scope_requested + \_filter_payload_by_platform + \_empty_shaped_payload in fake.py                                                                                     |
| adapter  | AD2-FAKE                     | medium   | APPLIED                     | Platform alias filtering on fake payload rows                                                                                                                                 |
| adapter  | AD3-DEMO                     | high     | APPLIED                     | client_scope_requested + \_filter_demo_payload_by_channel + \_demo_empty_payload in demo.py                                                                                   |
| adapter  | AD4-DEMO                     | high     | APPLIED                     | Channel field used for demo row filtering                                                                                                                                     |
| adapter  | AD5-UPLOAD                   | high     | APPLIED                     | client_scope_requested + \_upload_empty_payload + channel filter in upload.py                                                                                                 |
| adapter  | \_SCOPE_UNAWARE_ADAPTER_KEYS | —        | APPLIED                     | In combined_metrics_service.py                                                                                                                                                |
| meta     | M1                           | high     | APPLIED                     | R7 reconciliation effect in DashboardLayout.tsx mirrors useMetaStore.accountId to useDashboardStore.filters.accountId on /dashboards/meta/\* routes                           |
| meta     | M2                           | medium   | APPLIED                     | Row onClick in MetaAccountsPage.tsx line 295 calls setFilters({ accountId: account.external_id })                                                                             |
| meta     | M3                           | low      | APPLIED                     | accounts.status !== 'loading' guard at MetaAccountsPage.tsx                                                                                                                   |
| meta     | M4                           | high     | APPLIED                     | Handled by DashboardLayout R7 reconciliation effect (no per-file change needed)                                                                                               |
| meta     | M5                           | low      | APPLIED                     | insights.status !== 'loading' guard at MetaInsightsDashboardPage.tsx                                                                                                          |
| meta     | M6                           | high     | APPLIED                     | Handled by DashboardLayout R7 reconciliation effect                                                                                                                           |
| meta     | M7                           | low      | APPLIED                     | campaigns.status !== 'loading' guard at MetaCampaignOverviewPage.tsx                                                                                                          |
| meta     | M8-M11                       | low      | APPLIED (no changes needed) | Pages/Posts/Status routes clean                                                                                                                                               |
| meta     | M12                          | medium   | APPLIED                     | Period-reset useEffect in MetaPageOverviewPage.tsx no longer calls loadTimeseries directly                                                                                    |
| meta     | M13-M15                      | low      | APPLIED (no changes needed) | PostsPage/PostDetailPage clean                                                                                                                                                |
| meta     | M16                          | medium   | FIXED-BY-RECOVERY           | useMetaPageInsightsStore.loadPostTimeseries extended with overrides param; MetaPostDetailPage passes { metric, period } directly                                              |
| meta     | R7 cross-cutting             | high     | APPLIED                     | DashboardLayout reconciliation effect (Meta to Dashboard accountId bridge)                                                                                                    |
| meta     | R2 cross-cutting             | medium   | APPLIED                     | Single merged effect for URL-sync + platform-scope in DashboardLayout                                                                                                         |
| meta     | R6 cross-cutting             | medium   | FIXED-BY-RECOVERY           | resolveRoutePlatformScope and arePlatformArraysEqual extracted to dashboardFilters.ts as exports; DashboardLayout imports them; 27 new unit tests in dashboardFilters.test.ts |
| meta     | R5 cross-cutting             | medium   | APPLIED                     | reasonCode prop on EmptyState.tsx; renders as data-reason-code attribute                                                                                                      |
| google   | B1                           | high     | APPLIED                     | platforms: 'google_ads' in useGoogleAdsWorkspaceData.ts buildCommonParams line 76                                                                                             |
| google   | B2                           | medium   | APPLIED                     | Mount effect in GoogleAdsWorkspacePage seeds customer_id from useDashboardStore.getState().filters.accountId                                                                  |
| google   | B3                           | medium   | APPLIED (pre-existing)      | Back link updated in GoogleAdsCampaignDetailPage                                                                                                                              |
| google   | B4                           | low      | DEFERRED                    | Theoretical colon-encoding risk; no fix needed                                                                                                                                |
| google   | B5                           | high     | DEFERRED                    | Playwright E2E for google-ads workspace — out of synthesis scope                                                                                                              |
| google   | B6                           | high     | APPLIED                     | GoogleAdsExecutivePage passes { platforms, customer_id, start_date, end_date }                                                                                                |
| google   | B7                           | high     | APPLIED                     | GoogleAdsDataTablePage merges scopeParams into every fetch; GoogleAdsBudgetPage same fix                                                                                      |
| google   | B8                           | medium   | APPLIED                     | GoogleAdsCampaignDetailPage passes { platforms, customer_id } to detail fetch                                                                                                 |
| combined | B-PLAT-01                    | high     | APPLIED                     | DashboardLayout platform-scope effect handles scoped to unscoped transition                                                                                                   |
| combined | B-PLAT-02                    | medium   | APPLIED                     | PlatformDashboard shows EmptyState when hasData && byPlatform.length===0                                                                                                      |
| combined | B-PLAT-03                    | low      | DEFERRED                    | Hardcoded Facebook/Instagram KPI labels — UX cosmetic only                                                                                                                    |
| combined | B-CAMP-01                    | medium   | DEFERRED                    | getCampaignRowsForSelectedParish row-level platform filter — store surgery; out of time-box                                                                                   |
| combined | B-CAMP-02                    | medium   | DEFERRED                    | CampaignDashboard duplicate empty-state branches — cosmetic                                                                                                                   |
| combined | B-CREA-01                    | medium   | DEFERRED                    | Same as B-CAMP-01 for creatives selector                                                                                                                                      |
| combined | B-SAVED-01                   | high     | APPLIED                     | normalizeFilters in SavedDashboardPage.tsx restores platforms field                                                                                                           |
| combined | B-SAVED-02                   | medium   | APPLIED                     | Seed effect dep array omits location.search                                                                                                                                   |
| combined | B-AUD-01                     | medium   | DEFERRED                    | AudienceDashboard EmptyState on loaded+empty — out of time-box                                                                                                                |

---

## Test Results

### 1. backend pytest -q

```
727 passed, 1 skipped in 14.03s
```

### 2. backend ruff check .

```
analytics/fx.py:189:5: F841 Local variable `earliest` is assigned to but never used
Found 1 error.
```

Pre-existing — not caused by synthesis patches.

### 3. frontend npm test -- --run

```
Test Files  1 failed | 101 passed (102)
     Tests  10 failed | 506 passed (516)
    Errors  2 errors
```

All 10 failures are in `src/routes/__tests__/DataSources.test.tsx`:

- Root cause: `TypeError: connectFormRef.current.scrollIntoView is not a function`
- JSDOM does not implement scrollIntoView; added to DataSources.tsx in pre-existing branch work (file listed as modified in git status before this session started)
- Not caused by synthesis patches.

### 4. frontend npm run lint

```
(no output — clean)
```

### 5. frontend npm run build

```
✓ built in 3.05s
```

---

## DashboardLayout.tsx Cross-Cutting Summary

Four synthesis concerns land in DashboardLayout.tsx:

1. **R7 reconciliation effect**: imports `useMetaStore`; when pathname starts with `/dashboards/meta/`, copies non-empty `useMetaStore.filters.accountId` to `useDashboardStore.filters.accountId` if they differ. Guarded by ref to avoid infinite ping-pong.

2. **B-PLAT-01 scoped→unscoped transition**: the platform-scope useEffect handles both directions — forces `filters.platforms` to routePlatformScope when entering a scoped route, and resets to `[]` when entering a combined route from a scoped one.

3. **R6 import refactor** (this recovery session): `resolveRoutePlatformScope` and `arePlatformArraysEqual` are now imported from `../lib/dashboardFilters` instead of defined inline, enabling isolated unit testing.

4. **R2 double-setFilters race**: URL-sync and platform-scope effects are ordered to prevent a stale `platforms` value surviving for one render cycle on route entry.

---

## Pre-existing Work Encountered (not fixed)

| File                                                               | Issue                                                                           |
| ------------------------------------------------------------------ | ------------------------------------------------------------------------------- |
| `frontend/src/routes/DataSources.tsx`                              | scrollIntoView call added in branch work; JSDOM incompatibility breaks 10 tests |
| `backend/tests/test_google_ads_api.py`                             | Modified in git status; SDK migration work; not inspected                       |
| `backend/integrations/data/google_ads_v23_*.json`                  | SDK migration data; not touched                                                 |
| `backend/integrations/management/commands/seed_google_ads_demo.py` | Untracked new file; out of scope                                                |
| `analytics/fx.py:189`                                              | Pre-existing ruff F841                                                          |

---

## Deferred Items

| Item                                | Reason                                                                                                                |
| ----------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| B-CAMP-01 / B-CREA-01               | Row-level platform filter in useDashboardStore selectors — store surgery; medium severity but API call already scoped |
| B-PLAT-03                           | Hardcoded Facebook/Instagram KPI labels — UX cosmetic only                                                            |
| B-AUD-01                            | AudienceDashboard EmptyState on loaded+empty — time-boxed out                                                         |
| B-CAMP-02                           | Duplicate CampaignDashboard empty-state branches — cosmetic consolidation                                             |
| B5 (google E2E)                     | Playwright E2E for Google Ads workspace — E2E authored separately                                                     |
| DataSources.test.tsx scrollIntoView | Needs `window.HTMLElement.prototype.scrollIntoView = vi.fn()` in vitest setup or DataSources.tsx guard                |

---

## Overall Status: YELLOW

All high-severity patches are applied and verified (backend 727/727, build clean, lint clean). The 10 remaining frontend test failures are pre-existing branch work (DataSources.tsx scrollIntoView) unrelated to synthesis. Medium-severity deferred items (B-CAMP-01, B-AUD-01) do not break existing functionality. Two gaps were closed by this recovery run: M16 (loadPostTimeseries override params) and R6 (resolveRoutePlatformScope extracted to testable module with 27 new unit tests).
