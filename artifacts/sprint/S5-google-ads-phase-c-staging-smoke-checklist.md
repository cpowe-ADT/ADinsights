# Sprint 5 Phase C — GA-C3 Staging Regression Checklist

**Purpose:** step-by-step staging-environment smoke test for the Google Ads workspace surface (Phase A + Phase B work). Operator-runnable checklist; an agent re-running `/finish-google-ads.v2` with credentials surfaced can execute this end-to-end.

**Scope:** verifies behavior of all 10 tab sections plus the Phase A polish (pacing cache, recommendation dismiss audit, export polling) and Phase B polish (`next_cursor` pagination, saved-view verify endpoint).

**Estimated duration:** 90–120 minutes (assumes credentials and access are pre-provisioned).

**Status as of 2026-04-23:** **NOT YET EXECUTED — blocked on test-account credentials.** Agent recorded blocker in `S5-google-ads-state.json`. To execute: surface credentials (Pre-flight section below), then walk the checklist top-to-bottom.

---

## Pre-flight — required credentials & access

Operator must provide (or confirm pre-provisioned):

| Item                                                    | What                                                               | Where it goes                                                                                            |
| ------------------------------------------------------- | ------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------- |
| **Staging Google Ads OAuth refresh token**              | Issued by Google Ads UI for a user with access to ≥1 ad account    | Stored as encrypted blob on `Tenant.google_ads_refresh_token` (or wherever tenant-secret rotation lives) |
| **Staging tenant id**                                   | Real tenant row in staging DB                                      | `request.user.tenant_id` value                                                                           |
| **At least one linked Google Ads customer_id**          | A 10-digit customer-id with non-trivial ad traffic in last 30 days | `GoogleAdsSdkAccount.customer_id` for that tenant                                                        |
| **Staging JWT for a user in the tenant**                | Bearer token for hitting `/api/analytics/google-ads/…` endpoints   | `Authorization: Bearer <JWT>` header                                                                     |
| **Staging frontend URL**                                | Where the workspace is mounted                                     | `https://staging.adinsights.example/dashboards/google-ads` (replace)                                     |
| **Staging backend URL**                                 | API host                                                           | `https://staging.adinsights.example/api` (replace)                                                       |
| **DB shell access (read-only sufficient)**              | psql or equivalent                                                 | Used for tenant-isolation spot checks + `AuditLog` verification                                          |
| **Redis access (or `cache.delete_pattern` permission)** | For pacing-cache invalidation step                                 | Manage console / shell                                                                                   |

**Stop here if any item above is missing.** Do not partially execute — partial smoke tests obscure real failures.

---

## Phase 1 — health + connection sanity (≈10 min)

| #   | Check                 | Command / action                                                | Expected                                                                                  | Pass? |
| --- | --------------------- | --------------------------------------------------------------- | ----------------------------------------------------------------------------------------- | ----- |
| 1.1 | API health            | `curl -fsS $BACKEND/health/`                                    | HTTP 200, body `{"ok": true}` (or equivalent)                                             | ☐     |
| 1.2 | Timezone is Jamaica   | `curl -fsS $BACKEND/timezone/`                                  | `"timezone": "America/Jamaica"`                                                           | ☐     |
| 1.3 | Tenant social status  | `curl -H "$AUTH" $BACKEND/integrations/social/status/`          | Google Ads section shows `state: "complete"` (not `not_connected`/`started_not_complete`) | ☐     |
| 1.4 | Tenant dataset status | `curl -H "$AUTH" $BACKEND/datasets/status/`                     | `live_ready: true`, no `live_reason` blocker for Google Ads                               | ☐     |
| 1.5 | Linked customer_ids   | `curl -H "$AUTH" $BACKEND/integrations/google-ads/accounts/`    | Non-empty array; record customer_id values for later steps                                | ☐     |
| 1.6 | Workspace shell loads | Browser → `$FRONTEND/dashboards/google-ads` with logged-in user | Page renders, all 10 tab buttons visible, no console errors                               | ☐     |

If 1.3 / 1.4 / 1.5 fail, follow the **Tenant onboarding triage order** in `docs/runbooks/google-ads-operations.md` §Day-2 operations and resolve before continuing.

---

## Phase 2 — per-tab smoke (≈45 min)

For each tab below, click into the tab in the workspace and verify the expected UI. For each, also hit the underlying endpoint via curl and verify the response shape.

### 2.1 Overview tab

- ☐ UI: 4 KPI tiles render (clicks / impressions / cost / conversions or equivalent), trend line populates, channel pie renders or shows EmptyState if `campaignRows` empty.
- ☐ API: `curl -H "$AUTH" "$BACKEND/analytics/google-ads/summary/?customer_ids=<id>&start_date=2026-04-01&end_date=2026-04-23"` returns 200 with `summary` object.
- ☐ Tenant isolation: change `Authorization` to a different tenant's JWT → response should contain only that tenant's data (or 403 / empty).

### 2.2 Campaigns tab

- ☐ UI: campaign rows render in the table; sortable columns work; filter text input narrows the rows.
- ☐ API: `GET /analytics/google-ads/campaigns/?customer_ids=<id>&start_date=…&end_date=…` returns 200 with `results` array.

### 2.3 Search tab (keywords + search-terms modes)

- ☐ UI keywords: rows render, top-10 chart populates.
- ☐ UI search_terms: toggle mode, rows render.
- ☐ API: `GET /analytics/google-ads/keywords/` and `GET /analytics/google-ads/search-terms/` both 200.

### 2.4 Assets tab

- ☐ UI: text/image/video asset inventory renders, type filter works.
- ☐ API: `GET /analytics/google-ads/assets/` returns 200 with asset rows.

### 2.5 PMax tab

- ☐ UI: asset-group treemap renders with ROAS palette.
- ☐ API: `GET /analytics/google-ads/asset-groups/` returns 200.

### 2.6 Conversions tab

- ☐ UI: conversion-action list renders, daily series chart populates.
- ☐ API: `GET /analytics/google-ads/conversions/` returns 200.

### 2.7 Pacing tab — Phase A check

- ☐ UI: gauge-ring renders; tenant rollup KPI tiles populate; per-campaign rows render; **unmatched campaigns** (no `CampaignBudget` row) render `"—"` in pace/variance columns.
- ☐ API: `GET /analytics/google-ads/budgets/pacing/?customer_ids=<id>&end_date=…` returns 200 with both tenant rollup and `campaigns: [...]` array.
- ☐ Cache served-from indicator: load page, then reload immediately → second load shows `cache.served_from_cache: true` in the response (or via UI badge if surfaced).
- ☐ **Cache invalidation drill:** in a backend shell, `from django.core.cache import cache; cache.delete_pattern("ga_pacing_v1:*")`. Reload Pacing tab → response shows `cache.served_from_cache: false`.

### 2.8 Changes tab — Phase B check (next_cursor pagination)

- ☐ UI: change events render in table; if there are >page_size rows, "Load more" button visible.
- ☐ API page 1: `GET /analytics/google-ads/change-events/?page=1&page_size=10` returns 200; if more rows exist, `next_cursor: "2"` (string).
- ☐ Click "Load more" in UI → table appends rows, count header updates from e.g. `10/47` to `20/47`. `next_cursor` becomes `"3"` (or `null` on last page).
- ☐ API last page: `GET …?page=<num_pages>&page_size=10` → `next_cursor: null`.
- ☐ Tenant isolation: query change-events with another tenant's JWT → only that tenant's rows return.

### 2.9 Recommendations tab — Phase A check (LOCAL ONLY dismiss)

- ☐ UI: recommendation cards render; each shows a Dismiss button.
- ☐ API list: `GET /analytics/google-ads/recommendations/` returns 200; each row has `id`, `dismissed_at: null`, `dismissed_by_user_id: null` (for not-yet-dismissed rows).
- ☐ Dismiss flow: click Dismiss on one card → card removes from view (optimistic).
- ☐ API dismiss: `POST /analytics/google-ads/recommendations/<pk>/dismiss/` returns 200; the row is now `dismissed_at: <iso>`, `dismissed_by_user_id: <id>`.
- ☐ **AuditLog verification:** in DB shell, `SELECT * FROM analytics_auditlog WHERE action = 'google_ads_recommendation_dismissed' ORDER BY created_at DESC LIMIT 1;` → row exists, references the dismissed recommendation pk + user.
- ☐ **Local-only enforcement:** `git grep -n "DismissRecommendation" backend/ -- ':!**/google_ads/v*' ':!**/site-packages/*'` → returns **zero** hits. (Vendored SDK files allowed; production code must not call upstream dismiss.)

### 2.10 Reports tab — Phase A + B checks (export polling + saved-view drift)

#### Saved-view drift (Phase B)

- ☐ UI: open Reports tab; if any saved view has unknown filter keys / column names, dismissible amber banner renders at top (`role="status"`, `data-testid="drift-banner"`).
- ☐ API: `GET /analytics/google-ads/saved-views/<id>/verify/` returns 200 with `{drift: bool, unknown_filter_keys: [...], unknown_columns: [...], checked_against_version: "google-ads-v23"}`.
- ☐ Negative case: in DB shell, `UPDATE analytics_googleadssavedview SET filters = jsonb_set(filters, '{banana}', '1') WHERE id = '<test-view-id>';`. Reload tab → banner appears with that view name in the list. Roll back the UPDATE after.
- ☐ Tenant isolation: cross-tenant pk → 404.

#### Export polling (Phase A)

- ☐ Trigger an export from the Reports UI (or `POST /analytics/google-ads/reports/export/`). Response returns `job_id`.
- ☐ Browser DevTools Network tab: confirm polling sequence on `…/status/` is **3s, then 6s, 12s, 24s, 48s, 60s capped** (exponential backoff to 60s).
- ☐ When job completes, UI surfaces download button; clicking it follows redirect from `…/download/` to a pre-signed URL (S3 / equivalent); file downloads successfully.

---

## Phase 3 — cross-cutting checks (≈15 min)

| #   | Check                                                         | Command / action                                                                                                                                                                                                                             | Expected                                     | Pass? |
| --- | ------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------- | ----- |
| 3.1 | All endpoints require auth                                    | `curl -i $BACKEND/analytics/google-ads/summary/` (no Authorization header)                                                                                                                                                                   | HTTP 401                                     | ☐     |
| 3.2 | All endpoints reject foreign-tenant pk on detail-view actions | `POST /analytics/google-ads/recommendations/<other-tenant-pk>/dismiss/`                                                                                                                                                                      | HTTP 404 (not 200, not 403 with leak)        | ☐     |
| 3.3 | Frontend bundle has no console errors during a full tab walk  | Open DevTools console, click through all 10 tabs                                                                                                                                                                                             | No red errors; warnings okay if pre-existing | ☐     |
| 3.4 | Frontend network tab — no 5xx during tab walk                 | DevTools Network filter `status >= 500`                                                                                                                                                                                                      | Empty                                        | ☐     |
| 3.5 | Adapter env-flag isolation                                    | Confirm `ENABLE_WAREHOUSE_ADAPTER`, `ENABLE_META_DIRECT_ADAPTER` settings on staging do not affect Google Ads workspace data (workspace always reads SDK tables — verify by toggling the flag for a moment if safe, or grep code to confirm) | Workspace data unchanged                     | ☐     |
| 3.6 | Pacing whitelist drift sanity                                 | `git diff main…HEAD -- backend/analytics/google_ads_views.py` since last whitelist update — if new `KNOWN_FILTER_KEYS` / `KNOWN_COLUMN_KEYS` were added, confirm corresponding saved-view verify behavior                                    | No saved view falsely flagged                | ☐     |

---

## Phase 4 — record results (≈5 min)

1. Save a copy of this file as `S5-google-ads-phase-c-staging-smoke-results-<YYYYMMDD>.md` with checkboxes filled in and any failures annotated inline.
2. Update `S5-google-ads-state.json`:
   - If all green: `"GA-C3": {"status": "done", "completed_at": "<ISO>", "commit_sha": "<results doc commit>", "notes": "Staging regression: <X>/<Y> checks pass."}`. Remove the GA-C3 entry from `blockers`.
   - If any red: `"GA-C3": {"status": "in_progress", "notes": "Staging regression: <failed-check-list>; remediation tracked in <ticket>."}`. Keep blocker open with revised reason.
3. Update `artifacts/roadmap/project-punchlist.md` Quick status row for Google Ads to reflect 100% complete (if green).
4. Append a Phase C addendum to `S5-google-ads-phase-c-closeout.md` summarizing the smoke-test result.
5. Commit results doc + state.json + punchlist as `docs(google-ads): GA-C3 staging regression results — <YYYY-MM-DD>`.

---

## Failure triage cheat sheet

| Symptom                                       | First thing to check                                                                                             |
| --------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| Empty workspace, all tabs blank               | `…/integrations/social/status/` and `…/datasets/status/` (steps 1.3 / 1.4)                                       |
| Per-tab 500                                   | Django logs for `TenantAwareManager` filter — usually missing `tenant_id` on `request.user`                      |
| Per-tab 200 but empty data                    | Direct-SDK sync worker (`backend.integrations.google_ads.tasks`) — last sync recent? errors?                     |
| Pacing cache stale                            | `cache.delete_pattern("ga_pacing_v1:*")` — see step 2.7                                                          |
| Drift banner false positive                   | `KNOWN_FILTER_KEYS` / `KNOWN_COLUMN_KEYS` in `backend/analytics/google_ads_views.py` — needs whitelist update PR |
| `next_cursor` always null                     | `has_next()` on `Paginator.get_page()` — may be `page_size >= total` for the test data                           |
| `DismissRecommendation` regression test fails | Someone added a real upstream call; revert that change — dismiss is LOCAL ONLY by product decision (April 2026)  |

---

## Out of scope for this checklist

- Real-account write operations (creating campaigns, mutating budgets) — none exist in this surface today.
- Cross-platform combined-metrics endpoint behavior — that path is owned by the Meta + warehouse adapters, not the Google Ads workspace.
- Performance / load testing — separate exercise; this is a functional smoke.
- OAuth re-authorization flow — covered in `docs/runbooks/google-ads-sdk-migration.md`, not here.
