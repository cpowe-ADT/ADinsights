# B0 Triage Report

**Inputs:** /Users/thristannewman/ADinsights/artifacts/synthesis/synthesis-report.md (Phase A reference)

---

## Q1 — Google Ads workspace breakage

**Root cause hypothesis:** The workspace page at `/dashboards/google-ads` will return empty data for every fetch because `filters.customerId` is `''` by default, and the B2 mount-seed effect that was supposed to populate it from `useDashboardStore.filters.accountId` is running AFTER `hideGlobalFilters` has already hidden the global FilterBar — meaning the global store's `accountId` is also `''` since the user was never given an account picker. The workspace has no customer-selection UI of its own that lists real accounts; it exposes only a raw text input. So the user lands on the page with no customer selected, the summary fetch fires with `customer_id=` (blank), and the backend returns an empty dataset (or an unscoped one that may be empty because no `GoogleAdsAccountAssignment` rows match the tenant without an explicit id).

**Evidence:**

- `frontend/src/routes/DashboardLayout.tsx:196–203` — `hideGlobalFilters` returns `true` for any path starting with `/dashboards/google-ads`. The global FilterBar (which includes the Account selector that populates `filters.accountId`) is entirely suppressed on this route.
- `frontend/src/routes/google-ads/GoogleAdsWorkspacePage.tsx:133–142` — The B2 seed effect reads `useDashboardStore.getState().filters.accountId`. Because the global FilterBar is hidden when the user is on `/dashboards/google-ads`, `accountId` is `''` unless the user had previously visited a combined dashboard and selected an account. For a fresh session or first-time navigation directly to `/dashboards/google-ads`, `accountId` is always `''`, so the seed never fires.
- `frontend/src/components/google-ads/workspace/WorkspaceHeader.tsx:68–76` — The account selector in the workspace header is a plain `<input type="text">` labeled "Account ID", not a dropdown with real account options. The user has no way to discover their customer ID without knowing it in advance.
- `frontend/src/hooks/useGoogleAdsWorkspaceData.ts:69–78` — `buildCommonParams` always sends `platforms: 'google_ads'`. The backend `GoogleAdsExecutiveQuerySerializer` (`backend/analytics/google_ads_serializers.py:11–34`) has no `platforms` field declared; DRF silently ignores unknown fields, so this is safe and does not cause a 400. This specific concern from the brief is a non-issue.
- `backend/analytics/google_ads_views.py:504–519` — `GoogleAdsWorkspaceSummaryView` uses `GoogleAdsExecutiveQuerySerializer`. When `customer_id` is blank and the user has no `GoogleAdsAccountAssignment` rows (common for new tenants/demo mode), `_build_executive_payload` returns a zeroed payload rather than an error, so the UI shows zeros rather than an error state — making the breakage invisible.
- `frontend/src/lib/googleAdsDashboard.ts:93–96` — The summary endpoint is `/analytics/google-ads/workspace/summary/`. This URL is registered in `backend/analytics/urls.py:61–63` and exists. No 404.
- **SDK migration risk:** `backend/analytics/google_ads_views.py:524` references `GoogleAdsSdkChangeEvent` and related SDK models. If the SDK migration tables are empty (no sync run yet), the workspace summary still returns but with empty/zero signals — silent blank page.

**Fix complexity:** S

**Owner agent:** B1

**Recommended fix:**
1. Replace the free-text "Account ID" input in `WorkspaceHeader` with a dropdown populated from `GET /api/integrations/google-ads/accounts/` (same source DashboardLayout uses for combined dashboards).
2. Or: when the user has only one assigned account, auto-seed `customer_id` on mount without requiring the user to type it. The B2 effect skeleton is already there — it just needs a fallback that fetches assigned accounts if `globalAccountId` is also empty.

---

## Q2 — Client selector status

**Status:** (b) exists-broken — the component exists and is wired, but it is conditionally hidden on the Google Ads workspace route (because the global FilterBar is suppressed there), AND it only renders when `hasLiveData === true` on other routes.

**Evidence:**

- `frontend/src/components/FilterBar.tsx:378–399` — The client `<select>` renders only when `availableClients && availableClients.length > 0`. The prop is supplied by DashboardLayout.
- `frontend/src/routes/DashboardLayout.tsx:1098–1106` — The entire FilterBar (including client selector) is suppressed when `hideGlobalFilters` is true, which includes all `/dashboards/google-ads` paths.
- `frontend/src/routes/DashboardLayout.tsx:342–375` — `clientOptions` are loaded via `listClients()` but only when `hasLiveData === true`. In demo/dummy mode, `clientOptions` is explicitly set to `[]`, so the client selector never appears even on routes where the FilterBar is shown.
- `frontend/src/lib/dashboardFilters.ts:26,98` — `FilterBarState` has `clientId: ''` as a default field — the store plumbing exists end-to-end.
- `/Users/thristannewman/ADinsights/frontend/src/routes/ClientsPage.tsx` — A full client management page exists at `/clients` (not embedded in dashboards). It manages client groups but does not inject a picker into the dashboard filter bar.

**What needs to happen:**

For the **Google Ads workspace**: the workspace has no client selector at all. `WorkspaceHeader` would need a client dropdown (from `/api/clients/`) that maps to `filters.customerId` via the `client_id` → `customer_id` backend resolution already implemented (`backend/analytics/google_ads_serializers.py:19`).

For **combined dashboards**: the client selector is already wired. The only blocker is that it only appears in live data mode (`hasLiveData`). In demo mode, the user will never see it. This is intentional per the comment in DashboardLayout but may surprise users testing in demo.

**Fix complexity:** S (for workspace) / XS (the combined dashboard path already works)

**Owner agent:** B2

---

## Q3 — Other landmines

- **`/dashboards/google-ads` — invisible empty state:** When `customer_id` is blank and no accounts are assigned, all workspace tab fetches return 200 with zero/empty data. No error banner fires. User sees a blank-looking workspace with no explanation. Needs a "connect or select an account" empty-state guard before firing fetches.

- **`/dashboards/google-ads/[legacy-subpage]`** — All legacy sub-routes (`/keywords`, `/assets`, `/channels`, etc.) redirect to the workspace with `?tab=…` via `GoogleAdsTabRedirect`. If `VITE_GOOGLE_ADS_WORKSPACE_UNIFIED` is absent from `.env`, `resolveBooleanFlag` defaults to `true` (`router.tsx:115–118`), so old bookmarks redirect correctly. No breakage, but worth noting.

- **`/me` (ProfilePage):** Listed as an active work area in CLAUDE.md ("remaining polish items: /me profile page"). The route is registered (`router.tsx:219–222`) and the file exists. Risk: if the profile update API endpoint is half-built, the page may render but the Save action silently fails.

- **`/dashboards/uploads/:uploadId` (CsvUploadDetail):** Also called out in CLAUDE.md as in-progress ("CSV upload detail"). Route exists, file exists — same pattern as ProfilePage: render likely OK, detail actions may be incomplete.

- **Demo mode + client selector:** As noted in Q2, `clientOptions` is hard-coded to `[]` in demo mode (`DashboardLayout.tsx:347–350`). If a demo user asks "where is the client selector?", there is no UI affordance explaining it only appears in live mode.

- **`platforms` forced to `google_ads` in workspace fetches** (`useGoogleAdsWorkspaceData.ts:76`) — The non-summary tab endpoints (campaigns, keywords, etc.) also receive `platforms=google_ads`. Those endpoints use `GoogleAdsListQuerySerializer` which also has no `platforms` field — DRF ignores it silently. Safe but dead code.

---

## Recommended fix order

1. **B1 — Google Ads workspace account picker** — Highest user-facing pain. Replace the free-text "Account ID" input with a dropdown populated from the assigned accounts API. This unblocks all workspace data.
2. **B2 — Workspace client selector / seed effect hardening** — Once accounts load correctly, also expose a `client_id` dropdown in `WorkspaceHeader` that maps to the existing backend `client_id` → `customer_id` resolution path. Harden the B2 mount-seed to also query the accounts API when `globalAccountId` is empty.
3. **B3 — Empty-state guard for workspace with no account** — Add a conditional empty-state banner ("Select an account above to load data") that fires when `customerId` is empty and the summary returns zero spend.

---

## Open questions blocking fix agents

1. **Which API endpoint lists assignable Google Ads accounts?** DashboardLayout calls something to build `accountOptions` — confirm it is `GET /api/integrations/google-ads/accounts/` or equivalent and that it returns customer_id + label suitable for a dropdown.
2. **SDK migration completeness:** `GoogleAdsSdkChangeEvent`, `GoogleAdsSdkRecommendation`, `GoogleAdsSdkAdGroupAdDaily` are referenced in `GoogleAdsWorkspaceSummaryView`. If these tables have no rows (migration in-progress), the workspace will always show zeros. Is there a fallback to Airbyte-synced tables? Confirm before declaring B1 fixed.
3. **`VITE_GOOGLE_ADS_WORKSPACE_UNIFIED` in local `.env`** — Confirm it is unset or set to `true` so the workspace route is active, not the legacy redirect branch.
