# Sprint 5 — GA4 Staging Smoke-Test Checklist

**Purpose:** step-by-step staging-environment smoke test for the GA4 web-analytics surface. Operator-runnable walkthrough to close the one unchecked DoD item from `artifacts/roadmap/prompts/finish-ga4.md` — _"Dashboard at `/dashboards/google-analytics` shows real data on the dev stack."_

**Scope:** verifies the Airbyte → dbt → `agg_ga4_daily` → `GA4WebInsightsView` → dashboard path end-to-end with real GA4 property data. Also spot-checks the OAuth connect flow and the R3 contract.

**Estimated duration:** 60–90 minutes (assumes credentials and access are pre-provisioned).

**Status as of 2026-04-23:** **NOT YET EXECUTED — blocked on test-account credentials.** Code + runbook + investigation already shipped per [ga4-investigation.md](../roadmap/ga4-investigation.md) (Verdict B: wired, untested live in this environment). This checklist is the execution plan for when creds arrive.

---

## Pre-flight — required credentials & access

Operator must provide (or confirm pre-provisioned):

| Item                          | What                                                                                         | Where it goes                                                         |
| ----------------------------- | -------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| **AIRBYTE_GA4_CLIENT_ID**     | Google Cloud OAuth client id (with GA4 Data API v1beta enabled)                              | `infrastructure/airbyte/env` / Airbyte workspace env                  |
| **AIRBYTE_GA4_CLIENT_SECRET** | matching client secret                                                                       | same                                                                  |
| **AIRBYTE_GA4_REFRESH_TOKEN** | long-lived refresh token issued by `accounts.google.com/o/oauth2/token` against that client  | same                                                                  |
| **AIRBYTE_GA4_PROPERTY_ID**   | 9–10 digit numeric GA4 property id (not the G- measurement id) with ≥30 days of real traffic | same                                                                  |
| **Staging tenant id**         | Real tenant row                                                                              | `request.user.tenant_id` value                                        |
| **Staging JWT**               | Bearer token for a user in that tenant                                                       | `Authorization: Bearer <JWT>` header                                  |
| **Staging frontend URL**      | Where the dashboard is mounted                                                               | e.g. `https://staging.adinsights.example/dashboards/google-analytics` |
| **Staging backend URL**       | API host                                                                                     | e.g. `https://staging.adinsights.example/api`                         |
| **Airbyte workspace URL**     | Airbyte OSS UI                                                                               | e.g. `http://airbyte.staging.example:8000` (OSS default)              |
| **Staging DB access**         | psql or equivalent, read-write on warehouse schema                                           | Used for mart verification + tenant-isolation spot check              |
| **dbt profile access**        | Ability to flip `enable_ga4` var + run `dbt build`                                           | dbt-core shell or Airflow/scheduler console                           |

**Stop here if any item above is missing.** Half-configured GA4 ingestion is harder to debug than fully absent ingestion.

---

## Phase 1 — provision Airbyte source + dbt (≈20 min)

Per [docs/runbooks/ga4-operations.md](../../docs/runbooks/ga4-operations.md) "make-dashboard-live operator path":

| #   | Step                                | Command / action                                                                                                                                                        | Expected                                                          | Pass?     |
| --- | ----------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- | --------- | ---------- | ------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- | --- |
| 1.1 | Env vars set                        | `printenv AIRBYTE_GA4_CLIENT_ID AIRBYTE_GA4_CLIENT_SECRET AIRBYTE_GA4_REFRESH_TOKEN AIRBYTE_GA4_PROPERTY_ID`                                                            | All 4 non-empty                                                   | ☐         |
| 1.2 | Create Airbyte source from template | Airbyte UI → Sources → New → "Google Analytics 4 (GA4)" → configure via env vars (or apply `infrastructure/airbyte/ga4_source.yaml` through Airbyte OSS config-as-code) | Source saves, test connection returns **Succeeded**               | ☐         |
| 1.3 | Create destination                  | Confirm destination points to staging Postgres `raw` schema (same destination Meta/Google Ads use)                                                                      | Destination exists                                                | ☐         |
| 1.4 | Create connection                   | Airbyte UI → Connections → New → source=GA4, destination=warehouse, schedule=Manual first                                                                               | Connection saves                                                  | ☐         |
| 1.5 | Trigger first sync                  | Click "Sync now"                                                                                                                                                        | Sync completes **Succeeded**; ≥1 record in `raw.ga4_reports`      | ☐         |
| 1.6 | Enable dbt GA4 models               | Set `enable_ga4=true` in `dbt/dbt_project.yml` (or equivalent env override: `dbt build --vars '{enable_ga4: true}'`)                                                    | Variable applied                                                  | ☐         |
| 1.7 | Build GA4 dbt models                | `cd dbt && dbt build --select +agg_ga4_daily --vars '{enable_ga4: true}'`                                                                                               | `PASS` on both `stg_ga4_reports` and `agg_ga4_daily`; no warnings | ☐         |
| 1.8 | Verify mart populated               | `SELECT COUNT(*), MIN(date_day), MAX(date_day) FROM agg_ga4_daily;` via staging DB                                                                                      | count > 0; date range covers at least the last 7 days             | ☐         |
| 1.9 | PII guard                           | `grep -E "user_pseudo_id                                                                                                                                                | device_id                                                         | client_id | ip_address | stream_id" dbt/models/staging/stg_ga4_reports.sql dbt/models/marts/agg_ga4_daily.sql` | 0 hits (enforced by `test_ga4_pii_allowlist.py` — should never regress) | ☐   |

---

## Phase 2 — OAuth connect flow (≈15 min)

Spot-check the in-app OAuth path — note this is decorative for Airbyte ingestion (Airbyte uses its own refresh token), but the `GoogleAnalyticsConnection` row is still written and the status endpoints must work.

| #   | Step                   | Command / action                                               | Expected                                                                                                       | Pass? |
| --- | ---------------------- | -------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- | ----- |
| 2.1 | Connect-flow reachable | Browser → `$FRONTEND/dashboards/data-sources` with staging JWT | DataSources page loads; GA4 card visible                                                                       | ☐     |
| 2.2 | Start OAuth            | Click "Connect" on the GA4 card                                | Redirect to Google OAuth consent with scopes `analytics.readonly + openid + userinfo.email + userinfo.profile` | ☐     |
| 2.3 | Consent                | Grant consent with the staging Google account                  | Redirects back to `/dashboards/data-sources` with `code` + `state`                                             | ☐     |
| 2.4 | Property selection     | Properties list populates                                      | ≥1 property listed; pick the one matching `AIRBYTE_GA4_PROPERTY_ID`                                            | ☐     |
| 2.5 | Provision              | Click "Provision"                                              | `POST /api/integrations/ga4/provision/` returns 200; `GoogleAnalyticsConnection` row exists for this tenant    | ☐     |
| 2.6 | Status endpoint        | `curl -H "$AUTH" $BACKEND/integrations/ga4/status/`            | Returns `{status: "connected", property_id: "...", last_synced_at: ...}`                                       | ☐     |

---

## Phase 3 — dashboard end-to-end (≈15 min)

The core DoD bullet: the dashboard renders live data.

| #   | Step                        | Command / action                                                                          | Expected                                                                                          | Pass? |
| --- | --------------------------- | ----------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- | ----- |
| 3.1 | API via curl                | `curl -H "$AUTH" "$BACKEND/analytics/web/ga4/?start_date=2026-03-24&end_date=2026-04-23"` | HTTP 200; response `{source: "ga4", status: "ok", count: N, rows: [...]}` with N > 0              | ☐     |
| 3.2 | Dashboard renders live data | Browser → `$FRONTEND/dashboards/google-analytics`                                         | 4 KPI tiles populate with real numbers (not `—`): Sessions, Conversions, Revenue, Engagement rate | ☐     |
| 3.3 | TrendLine populates         | Same page                                                                                 | Trend chart renders with multiple data points; daily sessions visible                             | ☐     |
| 3.4 | PieComposition populates    | Same page                                                                                 | Channel-group breakdown pie renders (e.g. Organic Search / Paid Search / Direct)                  | ☐     |
| 3.5 | VizDataTable populates      | Same page                                                                                 | Table shows rows with property_id, channel_group, country, city, campaign_name, 4 metrics         | ☐     |
| 3.6 | Date range filter works     | Change date range to a narrower window (e.g. last 7 days)                                 | KPIs + chart re-fetch; row count drops                                                            | ☐     |
| 3.7 | Dimension filter works      | If UI exposes channel/country filter, apply one (e.g. country=Jamaica)                    | Rows filter; totals recompute                                                                     | ☐     |
| 3.8 | No console errors           | DevTools Console during tab walk                                                          | 0 red errors                                                                                      | ☐     |
| 3.9 | No 5xx                      | DevTools Network filter `status >= 500`                                                   | Empty                                                                                             | ☐     |

---

## Phase 4 — R3 contract + tenant isolation (≈10 min)

| #   | Check                                        | Command / action                                                                        | Expected                                                                  | Pass? |
| --- | -------------------------------------------- | --------------------------------------------------------------------------------------- | ------------------------------------------------------------------------- | ----- |
| 4.1 | R3 contract: no combined-metrics call        | DevTools Network panel while on `/dashboards/google-analytics`                          | Zero requests to `/api/metrics/combined/`                                 | ☐     |
| 4.2 | Endpoint used                                | Network panel                                                                           | Exactly the dedicated `/api/analytics/web/ga4/` is called                 | ☐     |
| 4.3 | Tenant isolation: cross-tenant GA4 data leak | Log in as a second staging tenant (or swap JWT via Postman) and hit the same date range | Response rows have 0 overlap with tenant 1 by `tenant_id` + `property_id` | ☐     |
| 4.4 | Unauthenticated rejection                    | `curl -i "$BACKEND/analytics/web/ga4/"` (no Authorization header)                       | HTTP 401                                                                  | ☐     |

---

## Phase 5 — freshness + scheduling (≈5 min)

| #   | Check                       | Command / action                                                                                                                    | Expected                            | Pass? |
| --- | --------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------- | ----- |
| 5.1 | Airbyte connection schedule | Airbyte UI → GA4 connection → change schedule from Manual to Every 24h (or whatever cadence matches tenant tier)                    | Schedule saved                      | ☐     |
| 5.2 | last_synced_at updates      | Trigger another manual sync, then `SELECT last_synced_at FROM integrations_googleanalyticsconnection WHERE tenant_id = '<tenant>';` | Timestamp within last 5 min         | ☐     |
| 5.3 | dbt run scheduled           | Confirm Airflow / cron / dagster / dbt Cloud job runs `dbt build --select +agg_ga4_daily` on a cadence (typically daily)            | Schedule exists; last run succeeded | ☐     |

---

## Phase 6 — record results (≈5 min)

1. Save this file as `S5-ga4-staging-smoke-results-<YYYYMMDD>.md` with checkboxes filled in and any failures annotated inline.
2. Update `artifacts/roadmap/project-punchlist.md` Quick status row for GA4:
   - If all green: 80% → 100% + add note: _"Staging regression green <YYYY-MM-DD>; live end-to-end verified."_
   - If any red: keep at current %, list failed checks, open follow-on ticket.
3. Append a results addendum to `S5-ga4-finish-closeout.md` summarizing the smoke-test outcome.
4. Commit results doc + punchlist update as `docs(ga4): staging regression results — <YYYY-MM-DD>`.
5. If green: T1-04 is DONE. Close sprint.

---

## Failure triage cheat sheet

| Symptom                                                    | First thing to check                                                                                                 |
| ---------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| Dashboard shows EmptyState with `no_ga4_property_selected` | User has no `GoogleAnalyticsConnection` row → re-run Phase 2                                                         |
| Dashboard shows EmptyState with `no_data_for_range`        | Mart exists but is empty for this tenant+range → check Airbyte last sync + dbt last run + `agg_ga4_daily` row counts |
| API returns `{status: "unavailable", detail: "..."}`       | `agg_ga4_daily` table missing → Phase 1.6/1.7 (dbt build) did not run                                                |
| Airbyte sync fails with "Invalid refresh token"            | `AIRBYTE_GA4_REFRESH_TOKEN` expired / wrong client → regenerate at Google OAuth Playground with matching client id   |
| dbt build fails on `stg_ga4_reports`                       | `enable_ga4` var still false, or `raw.ga4_reports` table doesn't exist → Phase 1.5 sync didn't populate              |
| KPIs render `—` despite API returning rows                 | Frontend response-normalizer mismatch → check `fetchGoogleAnalyticsWebRows` in `frontend/src/lib/webAnalytics.ts`    |
| R3 check fails (combined-metrics call detected)            | Regression — someone touched `GoogleAnalyticsDashboardPage.tsx` and bypassed the dedicated endpoint. Revert.         |
| Cross-tenant leak in 4.3                                   | Serious bug — `GA4WebInsightsView` RLS filter broken at `backend/analytics/web_views.py:126`. File as P0.            |

---

## Known architectural quirk

Per `ga4-investigation.md` §Primary gap: the in-app OAuth flow (Phase 2) writes `GoogleAnalyticsConnection` rows but those **do not** feed Airbyte — Airbyte uses its own `AIRBYTE_GA4_REFRESH_TOKEN` env var. This means a tenant who completes OAuth in the UI still sees an empty dashboard until the operator provisions Airbyte for their property separately. This is documented as out-of-scope for T1-04 ("finish GA4") and tracked as a future feature (bridge OAuth-captured tokens into Airbyte config).

## Out of scope for this checklist

- Multi-property tenants (current architecture assumes one GA4 property per tenant)
- Real-time API (BigQuery export → GA4 realtime intraday is a separate connector)
- Custom event / audience dimensions (mart uses the prompt-specified 5 dimensions only)
- Performance / load testing
