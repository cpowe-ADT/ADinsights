# Search Console Operations Runbook

Timezone baseline: `America/Jamaica`.

## Status (2026-04-23) — ingestion deferred post-launch

Search Console is shipping to launch in a **partially wired** state. The downstream components are built and tested; the tenant-facing on-ramp is not. This runbook documents what works, what is deferred, and the operator path to stand the dashboard up manually when needed.

| Component                                                                                          | State                                                                                                                                                                         |
| -------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Frontend route `/dashboards/search-console` (`frontend/src/routes/SearchConsoleDashboardPage.tsx`) | Built. Surfaces a persistent "ingestion deferred" notice (reason `search_console_ingestion_deferred`)                                                                         |
| Backend view `SearchConsoleInsightsView` (`backend/analytics/web_views.py:130`)                    | Built. `GET /api/analytics/web/search-console/` reads `agg_search_console_daily` via raw SQL with `WHERE tenant_id = %s`. Returns `{status: "unavailable"}` if mart is absent |
| dbt model `stg_search_console` (`dbt/models/staging/stg_search_console.sql`)                       | Built. Gated by `enable_search_console` var (default `false`)                                                                                                                 |
| dbt mart `agg_search_console_daily` (`dbt/models/marts/agg_search_console_daily.sql`)              | Built. Gated by `enable_search_console` var                                                                                                                                   |
| Airbyte source template (`infrastructure/airbyte/search_console_source.yaml`)                      | Built. Reads operator-level OAuth credentials from env vars                                                                                                                   |
| Tenant-facing OAuth flow (e.g. `backend/integrations/search_console/`)                             | **Not built.** No parallel to `backend/integrations/google_analytics/`. No `POST /api/integrations/search_console/oauth/start/`                                               |
| Combined-metrics adapter                                                                           | **Not built.** No `SearchConsoleAdapter`; the dashboard does not depend on the adapter path                                                                                   |

**What "deferred" means:** a tenant cannot self-serve connect Search Console from the Data Sources UI today. The dashboard will populate only if an operator manually wires Airbyte using operator-level OAuth tokens. Building the tenant-facing on-ramp is the remaining work (tracked in `artifacts/roadmap/project-punchlist.md` §T1-05).

## Scope

Operate Search Console ingestion and dashboard freshness for:

- Airbyte Search Console source (`infrastructure/airbyte/search_console_source.yaml`) — the only ingestion path today
- dbt models `stg_search_console` (staging view) + `agg_search_console_daily` (mart) — gated by `enable_search_console` var
- `backend.analytics.web_views.SearchConsoleInsightsView` — `GET /api/analytics/web/search-console/` reading `agg_search_console_daily`
- Frontend route `/dashboards/search-console` — R3 contract: must NOT call `/api/metrics/combined/`

## Architecture — single read path (dashboard-only)

```
Google Search Console → Airbyte Search Console source (operator creds)
  → Postgres raw.search_console_performance
  → dbt stg_search_console → dbt agg_search_console_daily
  → SearchConsoleInsightsView (tenant-scoped SQL) → dashboard page
```

Unlike GA4, Search Console has **one** read path. There is no combined-metrics adapter, no live live API fallback, and no tenant-OAuth bridge. Tenant isolation is enforced by the raw SQL `WHERE tenant_id = %s` bind in `_load_rows`, same as GA4.

R3 contract: the dashboard calls only `/api/analytics/web/search-console/`, never `/api/metrics/combined/`. The fetch-spy test in `SearchConsoleDashboardPage.test.tsx` asserts this.

## How to make the dashboard go live (operator path)

Tenant-facing OAuth is deferred. To light up `agg_search_console_daily` → `SearchConsoleInsightsView` an operator must:

1. **Obtain operator-level Search Console OAuth credentials.** Create a Google Cloud project (or reuse the GA4 project), enable the Search Console API, configure an OAuth consent screen, and capture a refresh token against the site(s) you plan to sync. Scope: `https://www.googleapis.com/auth/webmasters.readonly`.
2. **Set Airbyte env vars** (per deployment):
   - `AIRBYTE_SEARCH_CONSOLE_CLIENT_ID`, `AIRBYTE_SEARCH_CONSOLE_CLIENT_SECRET`, `AIRBYTE_SEARCH_CONSOLE_REFRESH_TOKEN`
   - `AIRBYTE_SEARCH_CONSOLE_SITE_URL` (e.g. `sc-domain:example.com` or `https://www.example.com/`)
   - Optional: `AIRBYTE_SEARCH_CONSOLE_START_DATE` (default `2024-01-01`), `AIRBYTE_SEARCH_CONSOLE_LOOKBACK_WINDOW_DAYS` (default `3`)
   - `AIRBYTE_SEARCH_CONSOLE_SOURCE_DEFINITION_ID` and `AIRBYTE_WORKSPACE_ID`
3. **Deploy the Airbyte source** using `infrastructure/airbyte/search_console_source.yaml` (rendered via env vars). Create the destination connection targeting the warehouse schema used by dbt's `raw` source (`{{ source('raw', 'search_console_performance') }}`).
4. **Flip the dbt var** `enable_search_console: true` (e.g. via `dbt run --vars '{"enable_search_console": true}'` or set persistently in `dbt_project.yml`).
5. **Run dbt** (`dbt build --select stg_search_console+`) to materialize the staging view and the mart.
6. **Wait for the first Airbyte sync.** Subsequent syncs run on the configured schedule.

Notes:

- Airbyte runs with operator-level credentials. Tenant isolation for Search Console rows comes from the `tenant_id` column populated by the `tenant_id_expr()` macro in `stg_search_console`. Confirm that the raw ingestion tags rows with the right tenant before enabling multi-tenant use; single-tenant deployments are the safe default until the tenant-facing on-ramp ships.
- PII policy (AGENTS.md §130): Search Console `query` and `page` columns are aggregated impression/click counts. Do NOT add per-user dimensions. The allowed schema is fixed in `stg_search_console.sql`; adding new columns requires review.

## How to trigger a sync

- **Airbyte (scheduled)**: runs on the Airbyte connection's configured schedule. No Django hook.
- **Airbyte (on-demand)**: trigger via Airbyte API `POST /api/v1/connections/sync` with the connection id, or through the Airbyte UI at `http://localhost:18000/` (dev default).
- **dbt (on-demand)**: from the repo root, `cd dbt && dbt build --select stg_search_console+ --vars '{"enable_search_console": true}'`.

## How to verify live (one-liner + deeper)

One-liner (requires DB access + known tenant id):

```bash
docker exec -e PGPASSWORD=<pw> adinsights-postgres-1 psql -U adinsights_user -d adinsights -tAc \
  "SET app.tenant_id = '<tenant_uuid>'; \
   SELECT MAX(date_day), COUNT(*), COUNT(DISTINCT site_url) \
   FROM agg_search_console_daily \
   WHERE date_day >= NOW() - INTERVAL '7 days';"
```

Expected: `MAX(date_day)` within 48h, non-zero row count. Zero rows with RLS set is a red flag — check the Airbyte last-sync status and the dbt `agg_search_console_daily` build timestamp.

Deeper:

1. `GET /api/analytics/web/search-console/?start_date=<YYYY-MM-DD>&end_date=<YYYY-MM-DD>` (authed as tenant admin) — expect `{source: "search_console", status: "ok", count: N, rows: [...]}`. If `status: "unavailable"`, the mart is missing; re-run dbt.
2. Airbyte UI → connection detail → last sync status + row counts.
3. dbt run log: `agg_search_console_daily` materialization must complete after each Airbyte sync.

## Troubleshooting

| Symptom                                                                                     | Likely cause                                                                                           | Fix                                                                                         |
| ------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------- |
| Dashboard shows the persistent "coming soon" notice and an "ingestion deferred" empty state | Default state: no Airbyte feed wired in this environment                                               | Either accept the deferral, or walk through the operator path above                         |
| `/api/analytics/web/search-console/` returns `status: "unavailable"`                        | `agg_search_console_daily` table doesn't exist OR dbt hasn't run with `enable_search_console=true`     | `cd dbt && dbt build --select stg_search_console+ --vars '{"enable_search_console": true}'` |
| Mart exists but rows are stale                                                              | Airbyte connection disabled OR failing syncs                                                           | Check Airbyte connection → last sync → failure reason; verify refresh token is valid        |
| Mart exists but zero rows for known-good site                                               | Site URL format mismatch. Search Console distinguishes `sc-domain:` vs URL-prefix properties           | Confirm `AIRBYTE_SEARCH_CONSOLE_SITE_URL` matches the property as Google expects it         |
| Tenant-facing "Connect Search Console" button is missing                                    | Expected — tenant OAuth module is deferred (`backend/integrations/search_console/` does not exist yet) | See roadmap §T1-05 for the build plan                                                       |

## OAuth token refresh

- Airbyte maintains its own refresh token in env/secret store. Rotating the operator-level token requires an Airbyte source update.
- No tenant-scoped OAuth tokens are stored today because the tenant-facing flow is not wired. When T1-05 follow-on work builds `backend/integrations/search_console/`, token storage should mirror the GA4 pattern: AES-GCM+KMS-encrypted via `PlatformCredential.set_raw_tokens` (AGENTS.md §90).

## Rate limits and quotas

- Search Console API: 1,200 queries/minute per user. Airbyte's source paginates and backs off automatically. Row limit in the template is `25000` per request.
- Historical data: Search Console retains ~16 months. Plan `AIRBYTE_SEARCH_CONSOLE_START_DATE` accordingly.

## Required OAuth scopes

- Airbyte source (operator): `https://www.googleapis.com/auth/webmasters.readonly`.
- Do NOT broaden scopes without review (AGENTS.md §86 — aggregated metrics only).

## Building the tenant-facing on-ramp (future work, T1-05 follow-on)

To finish the symmetry with GA4, the outstanding deliverables are:

1. `backend/integrations/search_console/` module mirroring `backend/integrations/google_analytics/` — `client.py` (Search Console API wrapper), `views.py` (OAuth start/exchange/provision/status), `urls.py`, serializers.
2. Frontend Data Sources card for Search Console that drives the OAuth flow and lists sites (`GET /api/integrations/search_console/sites/`).
3. An operator bridge (or provisioning hook) that populates Airbyte connection config from the per-tenant OAuth tokens instead of env vars, OR a deliberate decision to keep Airbyte operator-credentialed and use the `tenant_id_expr()` macro to tag ingested rows.
4. `SearchConsoleAdapter` in the combined-metrics pipeline if Search Console ever needs to feed the multi-source grid (not required for the dashboard).

Remove or revise the deferred notice on `SearchConsoleDashboardPage.tsx` only after (1)-(3) land.

## Test commands

```bash
# Frontend unit + R3 contract
cd frontend && npx vitest run src/routes/__tests__/SearchConsoleDashboardPage.test.tsx

# Backend: tenant-scoped web view unit coverage (shares BaseWebSourceView with GA4)
cd backend && pytest tests/test_phase2_api.py -k search_console -q
```

## Related docs

- `AGENTS.md` §83 (RLS), §86 (aggregated metrics), §90 (OAuth token encryption), §130 (PII), §140 (timezone)
- `docs/runbooks/ga4-operations.md` — sister runbook; Search Console's tenant-facing on-ramp should mirror GA4's when built
- `artifacts/roadmap/project-punchlist.md` §T1-05 — the ticket this closes (with deferral)
