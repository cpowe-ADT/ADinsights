# GA4 (Google Analytics 4) Operations Runbook

Timezone baseline: `America/Jamaica`.

## Scope

Operate GA4 Reporting ingestion, OAuth connection, and dashboard freshness for:

- `integrations.models.PlatformCredential` (provider `google_analytics`) — AES-GCM+KMS-encrypted OAuth tokens
- `integrations.models.GoogleAnalyticsConnection` — per-tenant property selection and sync metadata
- `backend.integrations.google_analytics.client.GoogleAnalyticsClient` — GA4 Data API v1beta live fetch (used by the warehouse/adapter path, not by the dashboard page)
- Airbyte GA4 source (`infrastructure/airbyte/ga4_source.yaml`) — the dashboard ingestion path
- dbt models `stg_ga4_reports` (staging view) + `agg_ga4_daily` (mart) — gated by `enable_ga4` var
- `backend.analytics.web_views.GA4WebInsightsView` — `GET /api/analytics/web/ga4/` reading `agg_ga4_daily` via raw SQL (tenant-scoped)
- Frontend route `/dashboards/google-analytics` (`frontend/src/routes/GoogleAnalyticsDashboardPage.tsx`) — R3 contract: must NOT call `/api/metrics/combined/`

## Architecture — two parallel read paths

GA4 has two independent code paths by design. Know which path you're diagnosing.

### Path 1 — Dashboard (`/dashboards/google-analytics`)

```
Google Analytics → Airbyte GA4 source (scheduled) → Postgres raw.ga4_reports
  → dbt stg_ga4_reports → dbt agg_ga4_daily → GA4WebInsightsView → dashboard page
```

- Airbyte handles OAuth refresh transparently via stored refresh token (env var `AIRBYTE_GA4_REFRESH_TOKEN`).
- Ingestion is batch/scheduled. Dashboard freshness is bounded by Airbyte sync cadence + dbt run cadence (typically daily, `America/Jamaica`).
- Tenant isolation is enforced in `GA4WebInsightsView._load_rows` by the raw SQL `WHERE tenant_id = %s` bind.
- R3 contract: the dashboard calls only `/api/analytics/web/ga4/`, never `/api/metrics/combined/`. The fetch-spy test in `GoogleAnalyticsDashboardPage.test.tsx` asserts this.

### Path 2 — Combined-metrics adapter

```
GoogleAnalyticsConnection → GoogleAnalyticsAdapter.fetch_metrics
  → GoogleAnalyticsClient.fetch_traffic_acquisition (live GA4 Data API v1beta)
  → combined-metrics orchestrator (/api/metrics/combined/)
```

- Uses the tenant-scoped OAuth tokens from `PlatformCredential` (provider `google_analytics`).
- Schema is different from the mart: `sessionSource / sessionMedium / sessionCampaignName` + `sessions / totalUsers / newUsers / engagementRate / averageSessionDuration / keyEvents / eventCount`.
- Feeds surfaces other than the GA4 dashboard page. The GA4 dashboard page does NOT call this.
- OAuth token refresh: handled transparently by `google.oauth2.credentials.Credentials` using the stored refresh token, client id/secret, and `GOOGLE_OAUTH_TOKEN_URI`. On 401, the Google SDK refreshes without Django intervention.

## How to connect a GA4 property (tenant-facing)

1. Tenant admin opens `/dashboards/data-sources?sources=web`.
2. Click Connect for GA4. Frontend calls `POST /api/integrations/google_analytics/oauth/start/` → returns `authorize_url` + signed `state`.
3. User completes Google consent. Google redirects to `http://localhost:5173/dashboards/data-sources` (env `GOOGLE_ANALYTICS_OAUTH_REDIRECT_URI`).
4. Frontend posts `{code, state, ...}` to `POST /api/integrations/google_analytics/oauth/exchange/`. Backend exchanges, fetches `userinfo`, creates/updates a `PlatformCredential` row (tokens AES-GCM+KMS-encrypted via `PlatformCredential.set_raw_tokens`).
5. Frontend calls `GET /api/integrations/google_analytics/properties/?credential_id=<uuid>` and renders the property list.
6. Tenant selects a property. Frontend posts to `POST /api/integrations/google_analytics/provision/` → creates/updates `GoogleAnalyticsConnection` (the active per-tenant property selection).
7. `GET /api/integrations/google_analytics/status/` returns `{status: "complete" | "active", ...}`.

**Expected end state (Path 2 only):** `GoogleAnalyticsConnection` with `is_active=true`. Combined-metrics surfaces start returning live GA4 rows via `GoogleAnalyticsAdapter`.

**This does NOT populate the dashboard.** The dashboard (`/dashboards/google-analytics`) reads the mart (Path 1), which requires Airbyte + dbt.

## How to make the dashboard go live (operator path)

The tenant-facing OAuth flow does not, today, provision an Airbyte source. To light up the dashboard (`agg_ga4_daily` → `GA4WebInsightsView`) an operator must:

1. **Set Airbyte env vars** (per deployment):
   - `AIRBYTE_GA4_CLIENT_ID`, `AIRBYTE_GA4_CLIENT_SECRET`, `AIRBYTE_GA4_REFRESH_TOKEN`
   - `AIRBYTE_GA4_PROPERTY_ID` (the GA4 numeric property id, no `properties/` prefix)
   - Optional: `AIRBYTE_GA4_START_DATE` (default `2024-01-01`), `AIRBYTE_GA4_LOOKBACK_WINDOW_DAYS` (default `3`), `AIRBYTE_DEFAULT_TIMEZONE` (default `America/Jamaica`)
   - `AIRBYTE_GA4_SOURCE_DEFINITION_ID` and `AIRBYTE_WORKSPACE_ID`
2. **Deploy the Airbyte source** using `infrastructure/airbyte/ga4_source.yaml` (rendered via env vars). Create the destination connection targeting the warehouse schema used by dbt's `raw` source (`{{ source('raw', 'ga4_reports') }}`).
3. **Flip the dbt var** `enable_ga4: true` (e.g. via `dbt run --vars '{"enable_ga4": true}'` or set persistently in `dbt_project.yml`). This enables `stg_ga4_reports` + `agg_ga4_daily`.
4. **Run dbt** (`dbt build --select stg_ga4_reports+`) to materialize the staging view and the mart.
5. **Wait for the first Airbyte sync.** Subsequent syncs run on the configured schedule.

Notes:
- The per-tenant OAuth tokens captured via the app UI are **not** bridged into Airbyte. Bridging is a future enhancement (T3-ish). Today, Airbyte runs with operator-level credentials, and tenant isolation is enforced in dbt and the Django view layer.
- PII policy (AGENTS.md §130): the GA4 staging model only pulls `property_id, tenant_id, date_day, channel_group, country, city, campaign_name` and aggregatable metrics. Do NOT add GA4 dimensions like `user_pseudo_id`, `device_id`, `client_id`, `ip_address`, or `stream_id` to the mart schema — the PII allowlist test (`backend/tests/test_ga4_pii_allowlist.py`) will fail the build.

## How to trigger a sync

- **Airbyte (scheduled)**: runs on the Airbyte connection's configured schedule. No Django hook.
- **Airbyte (on-demand)**: trigger via Airbyte API `POST /api/v1/connections/sync` with the connection id, or through the Airbyte UI at `http://localhost:18000/` (dev default).
- **dbt (on-demand)**: from the repo root, `cd dbt && dbt build --select stg_ga4_reports+ --vars '{"enable_ga4": true}'`.

## How to verify live (one-liner + deeper)

One-liner (requires DB access + known tenant id):

```bash
docker exec -e PGPASSWORD=<pw> adinsights-postgres-1 psql -U adinsights_user -d adinsights -tAc \
  "SET app.tenant_id = '<tenant_uuid>'; \
   SELECT MAX(date_day), COUNT(*), COUNT(DISTINCT property_id) \
   FROM agg_ga4_daily \
   WHERE date_day >= NOW() - INTERVAL '7 days';"
```

Expected: `MAX(date_day)` within 48h, non-zero row count. Zero rows with RLS set is a red flag — check the Airbyte last-sync status and the dbt `agg_ga4_daily` build timestamp.

Deeper:

1. `GET /api/integrations/google_analytics/status/` — Does the tenant show `complete` or `active`?
2. `GET /api/analytics/web/ga4/?start_date=<YYYY-MM-DD>&end_date=<YYYY-MM-DD>` (authed as tenant admin) — expect `{source: "ga4", status: "ok", count: N, rows: [...]}`. If `status: "unavailable"`, the mart is missing; re-run dbt.
3. Airbyte UI → connection detail → last sync status + row counts.
4. dbt run log: `agg_ga4_daily` materialization must complete after each Airbyte sync.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Dashboard shows `reason: no_ga4_property_selected` empty state | No `GoogleAnalyticsConnection` row OR `status: "unavailable"` from mart missing | Walk tenant through OAuth flow; if OAuth is fine, check mart + Airbyte |
| `/api/analytics/web/ga4/` returns `status: "unavailable"` | `agg_ga4_daily` table doesn't exist OR dbt hasn't run with `enable_ga4=true` | `cd dbt && dbt build --select stg_ga4_reports+ --vars '{"enable_ga4": true}'` |
| Mart exists but rows are stale | Airbyte connection disabled OR failing syncs | Check Airbyte connection → last sync → failure reason; verify refresh token is valid |
| `/api/integrations/google_analytics/oauth/exchange/` returns 502 "Token exchange failed" | OAuth client credentials misconfigured or redirect URI mismatch | Verify `GOOGLE_ANALYTICS_CLIENT_ID`, `GOOGLE_ANALYTICS_CLIENT_SECRET`, `GOOGLE_ANALYTICS_OAUTH_REDIRECT_URI` and the Google Cloud project's authorized redirect URIs match exactly |
| `GoogleAnalyticsClientError: credential_missing_refresh_token` | Tenant connected without consent screen `prompt=consent` (Google omits the refresh token on re-authorization) | Frontend must send `prompt=consent` on `oauth/start/`. If already stored, re-run the connect flow |
| `GoogleAnalyticsClientError: oauth_not_configured` | `GOOGLE_ANALYTICS_CLIENT_ID` or `GOOGLE_ANALYTICS_CLIENT_SECRET` env vars not set | Set in `.env`; restart backend |
| GA4 data shows up in combined metrics but dashboard is empty | Expected — Path 1 (dashboard/mart) and Path 2 (live adapter) are independent | Wire Airbyte + dbt as described above |

## OAuth token refresh

- Tokens are stored encrypted via `PlatformCredential.set_raw_tokens` → AES-GCM with a KMS-derived data key per AGENTS.md §90.
- `GoogleAnalyticsClient._build_client` passes refresh token + client id/secret + token uri to `google.oauth2.credentials.Credentials`. The Google SDK refreshes transparently on expiry.
- Django code does NOT currently persist refreshed access tokens back to the DB. This is acceptable because each API call rebuilds credentials from the stored refresh token. If future work needs to persist rotated refresh tokens, add a save hook around `client.refresh()` calls.
- Airbyte maintains its own refresh token in env/secret store. Rotating the operator-level token requires an Airbyte source update.

## Rate limits and quotas

- GA4 Data API v1beta: see <https://developers.google.com/analytics/devguides/reporting/data/v1/quotas>. Most relevant: "Core tokens per property per day" (default 25,000) and "Concurrent requests per property" (10).
- Airbyte's GA4 source manages pagination, backoff, and the `lookback_window` knob (default 3 days in our template) to pick up late-arriving conversions.
- Live adapter (Path 2): in dev, prefer VCR-cached or mocked responses for smoke tests (`test_google_analytics_client.py` uses monkeypatched SDK symbols). Do NOT hammer the live API in CI.

## Required OAuth scopes

- Web app in-flow consent: `analytics.readonly`, `openid`, `userinfo.email`, `userinfo.profile` (see `DEFAULT_GA4_OAUTH_SCOPES` in `backend/integrations/google_analytics/views.py`).
- Airbyte source: `analytics.readonly` only.
- Do NOT broaden scopes without review (AGENTS.md §86 — aggregated metrics only).

## Test commands

```bash
# Backend unit coverage for GA4
cd backend && pytest tests/test_google_analytics_client.py tests/test_google_analytics_api.py tests/test_ga4_pii_allowlist.py -q

# Web endpoint tenant isolation
cd backend && pytest tests/test_phase2_api.py::test_ga4_web_insights_isolates_rows_by_tenant -q

# R3 contract (frontend)
cd frontend && npx vitest run src/routes/__tests__/GoogleAnalyticsDashboardPage.test.tsx
```

## Related docs

- `AGENTS.md` §83 (RLS), §86 (aggregated metrics), §90 (OAuth token encryption), §130 (PII), §140 (timezone)
- `docs/runbooks/meta-page-insights-operations.md` — sister runbook for the Meta path
- `artifacts/roadmap/ga4-investigation.md` — the investigation that produced this runbook
- `artifacts/roadmap/project-punchlist.md` §T1-04 — the ticket this closes
