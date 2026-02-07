# Airbyte Stack

This compose file boots an Airbyte OSS deployment suitable for local development.

## Usage

```bash
docker compose --env-file env.example up -d
```

The UI will be available at <http://localhost:${AIRBYTE_WEBAPP_PORT:-8000}> and the API at <http://localhost:${AIRBYTE_SERVER_PORT:-8001}>.

Copy `env.example` to `.env` (or provide equivalent environment variables) to keep credentials out of source control while letting
Compose substitute consistent defaults.

## Version pinning

Airbyte OSS releases are tagged upstream; we pin to a single version across `server`, `webapp`, and `worker` images to keep API
contracts and migrations aligned. Recommended baseline: **v1.8.0** (latest 1.x series, avoids the 2.x upgrade path).

If you update the Compose images, keep all Airbyte service tags in lockstep. Official OSS images are published via Airbyte's
registry (currently GHCR). Make sure you can authenticate (`docker login ghcr.io` with a token that has `read:packages`) before
pulling, or the stack will fail to start.

## Environment variables

`env.example` now drives both the Docker Compose stack and the provisioning scripts. Populate it with redacted values before
bootstrapping any tenants.

### Global

| Variable | Purpose |
| --- | --- |
| `AIRBYTE_BASE_URL` | Base URL for the API (also consumed by the helper scripts). |
| `AIRBYTE_API_AUTH_HEADER` | Optional pre-formatted `Authorization` header sent to the API. |
| `AIRBYTE_DEFAULT_TIMEZONE` | Canonical timezone for cron schedules (defaults to `America/Jamaica`). |
| `AIRBYTE_DEFAULT_METRICS_*` | Default hourly metrics cron / interval definitions aligned with the SLA window (06:00–22:00 hourly). |
| `AIRBYTE_DEFAULT_DAILY_*` | Default daily cron / interval definitions for dimensions refreshes (02:15 daily). |
| `AIRBYTE_DEFAULT_STREAM_PREFIX` | Prefix prepended to every connection's destination stream. |
| `AIRBYTE_DEFAULT_DESTINATION_NAMESPACE` | Warehouse schema / namespace when tenants do not supply their own. |
| `AIRBYTE_DEFAULT_DESTINATION_BUCKET` | Object store landing bucket when destinations require it (optional). |

### Connection templates

Provide "golden" connection IDs to clone sync catalogs and operations for each connector. These template connections should live
in a sandbox workspace that mirrors production configurations.

| Variable | Usage |
| --- | --- |
| `AIRBYTE_TEMPLATE_DESTINATION_ID` | Destination UUID for template Meta/Google connections created by the provisioning script. |
| `AIRBYTE_TEMPLATE_META_METRICS_CONNECTION_ID` | Base Meta Marketing metrics connection. |
| `AIRBYTE_TEMPLATE_GOOGLE_METRICS_CONNECTION_ID` | Base Google Ads metrics connection. |
| `AIRBYTE_TEMPLATE_DIMENSIONS_DAILY_CONNECTION_ID` | Base daily dimensions connection. |

### Tenants

`AIRBYTE_TENANTS` lists tenant slugs. Every slug expands into environment variables using the pattern `AIRBYTE_<SLUG>_*` where the
slug is upper-cased and dashes become underscores. Key variables per tenant include:

| Pattern | Purpose |
| --- | --- |
| `AIRBYTE_<SLUG>_WORKSPACE_ID` | Workspace UUID that owns the tenant's resources. |
| `AIRBYTE_<SLUG>_DESTINATION_ID` | Destination UUID for the tenant's warehouse/bucket. |
| `AIRBYTE_<SLUG>_DESTINATION_NAMESPACE` | Optional schema override for JDBC destinations. |
| `AIRBYTE_<SLUG>_DESTINATION_BUCKET` | Optional object-store bucket for file-based destinations. |
| `AIRBYTE_<SLUG>_STREAM_PREFIX` | Default namespace prefix applied to all connections. |
| `AIRBYTE_<SLUG>_<GROUP>_CRON` | Tenant-specific cron expression for a schedule group (`METRICS`, `DAILY`, etc.). |
| `AIRBYTE_<SLUG>_<GROUP>_BASIC_UNITS` / `_BASIC_TIME_UNIT` | Interval fallback for `basic` schedules when cron is omitted. |
| `AIRBYTE_<SLUG>_<TEMPLATE>_NAME` | Override the generated connection name for a template (e.g. `META_METRICS`). |
| `AIRBYTE_<SLUG>_<TEMPLATE>_STATUS` | Desired status (`active`/`inactive`) for a connection template. |
| `AIRBYTE_<SLUG>_<TEMPLATE>_PREFIX` | Per-connection prefix override. |
| `AIRBYTE_<SLUG>_<TEMPLATE>_CONNECTION_ID` | Optional existing connection to update in-place instead of creating a new one. |

Set `AIRBYTE_WORKSPACE_ID` to your primary tenant's workspace ID to preserve compatibility with legacy scripts such as the
Airbyte health check.

## Connection bootstrap workflow

Provisioning and validation scripts live in `infrastructure/airbyte/scripts/`:

| Script | Description |
| --- | --- |
| `provision_meta_google_connectors.py` | Creates/updates Meta + Google sources, validates credentials with source connection checks, discovers stream catalogs, and upserts template metric connections. |
| `validate_tenant_config.py` | Smoke test for environment configuration. Confirms workspaces and destinations exist and validates cron/interval hints before changes are applied. |
| `bootstrap_connections.py` | Clones the template connections for every tenant, applies tenant-specific destination namespaces/prefixes, and enforces schedules that honor the SLA windows. |

Create/update the Meta + Google template connectors first:

```bash
python3 infrastructure/airbyte/scripts/provision_meta_google_connectors.py
```

Then run the validator before attempting tenant fan-out:

```bash
python3 infrastructure/airbyte/scripts/validate_tenant_config.py
```

If the validation passes, bootstrap or update the tenant connections:

```bash
python3 infrastructure/airbyte/scripts/bootstrap_connections.py
```

All scripts emit JSON summaries to stdout so you can capture the results in CI/CD pipelines. They rely solely on the environment
variables documented above—no inline secrets or per-tenant JSON files are required.

## Scheduling Guidance

All schedules reference the **America/Jamaica** timezone so they align with downstream SLAs documented in `AGENTS.md`.
Airbyte schedules live on each **Connection**; configure them via the UI (`Connections → <Connection> → Replication → Edit schedule`)
or with the API (`POST /api/v1/connections/update`).

### Hourly metrics (Meta & Google Ads)

- **Cron:** `0 6-22 * * *` to run at the top of the hour between 06:00 and 22:00.
- **Sync mode:** Incremental on `updated_time` (Meta) and `segments.date` (Google Ads) with `Additional sync lookback window = 3 days`.
- **Why:** Captures late conversions without rerunning the entire 28-day attribution window while keeping each sync under the
  <30 minute SLA.

In the API payload, set:

```json
{
  "scheduleType": "cron",
  "scheduleData": {
    "cron": {
      "cronExpression": "0 6-22 * * *",
      "cronTimeZone": "America/Jamaica"
    }
  },
  "schedule": null
}
```

### Daily dimensions (Campaign/Ad/Geo catalogs)

- **Cron:** `15 2 * * *` so campaign/ad set/ad metadata and geo lookups finish before the 03:00 SLA.
- **Sync mode:** Incremental on the appropriate `updated_time`/`segments.date` cursor with a 1-day lookback to catch late metadata changes.
- **Why:** Dimensions change slowly; a single daily run keeps downstream dbt models stable while limiting API quota usage.

Document the chosen cron/anchor in your runbook so stakeholders know when fresh numbers land. After each metrics sync, trigger dbt's
incremental staging models; schedule the aggregate marts around 05:00 so dashboards populate by 06:00.

## Source Templates

Copy the `.example` files in `sources/` to real JSON files before importing into Airbyte. Never commit actual credentials.

```bash
cp sources/meta_marketing.json.example sources/meta_marketing.json
cp sources/google_ads.json.example sources/google_ads.json
```

The Meta Marketing template configures incremental streams on `updated_time` with an Insights lookback window (default 3 days) across a 28-day
attribution horizon, both of which are controlled by `AIRBYTE_META_HOURLY_WINDOW_DAYS` and `AIRBYTE_META_INSIGHTS_LOOKBACK_DAYS`. The Google Ads template uses Airbyte's `{{ runtime_from_date }}` / `{{ runtime_to_date }}` variables so custom
GAQL queries only replay the slices required by the incremental state.
If you prefer environment-based substitution, duplicate `env.example` to `.env` and export it before running `docker compose up`.

The Google Ads sample uses Airbyte's `{{ runtime_from_date }}` template variable inside each custom
query so the connector replays only the slices required by the incremental state rather than a fixed
28-day window. Keep the cursor fields and lookback windows aligned with your desired backfill
horizon when adapting the template.

Custom connectors for LinkedIn and TikTok live under `sources/linkedin_ads/` and `sources/tiktok_ads/`. Export the required environment variables (documented below) before packaging them with `airbyte-ci` or when importing the specs via the Airbyte UI.

## Airbyte Configuration

This directory contains declarative configuration snippets for the ingestion layer.

- `meta_source.yaml` – Meta Marketing API source configured for incremental syncs on `updated_time` with lookback tuning knobs.
- `google_ads_source.yaml` – Google Ads source leveraging a custom GAQL query with incremental cursor on `segments.date`.
- `ga4_source.yaml` – GA4 reporting source template for Phase 2 web analytics ingestion.
- `search_console_source.yaml` – Search Console source template for Phase 2 SEO ingestion.
- `linkedin_ads_source.yaml` – Connection payload for the custom LinkedIn Ads connector in `sources/linkedin_ads/`.
- `tiktok_ads_source.yaml` – Connection payload for the custom TikTok Ads connector in `sources/tiktok_ads/`.

Optional connectors are disabled by default in dbt via the `enable_linkedin` and `enable_tiktok` variables. Toggle the variables to `true` in the target profile once the corresponding Airbyte connections are enabled so the warehouse models pick up the new feeds.

All files assume credentials are injected from environment variables using Airbyte's declarative templates. Export the variables listed below before applying the YAML snippets. Replace placeholders with the actual workspace UUIDs and connection IDs when provisioning resources.

### Meta Ads secrets & tuning knobs

| Variable | Description |
| --- | --- |
| `AIRBYTE_META_ACCOUNT_ID` | Ads account to query (prefixed with `act_`). |
| `AIRBYTE_META_ACCESS_TOKEN` | Long-lived system token with `ads_read` scope. |
| `AIRBYTE_META_APP_ID` / `AIRBYTE_META_APP_SECRET` | App credentials used for token refreshes. |
| `AIRBYTE_META_START_DATE` | ISO timestamp for the initial backfill (defaults to `2023-01-01T00:00:00Z`). |
| `AIRBYTE_META_INSIGHTS_LOOKBACK_DAYS` | Rolling attribution window (default `3` days). |
| `AIRBYTE_META_HOURLY_WINDOW_DAYS` | Additional sync window applied to incremental jobs (default `3`). |
| `AIRBYTE_META_ATTRIBUTION_WINDOW_DAYS` | Horizon for attribution metrics (default `30`). |

### Google Ads secrets & tuning knobs

| Variable | Description |
| --- | --- |
| `AIRBYTE_GOOGLE_ADS_DEVELOPER_TOKEN` | Manager account developer token. |
| `AIRBYTE_GOOGLE_ADS_CLIENT_ID` / `AIRBYTE_GOOGLE_ADS_CLIENT_SECRET` | OAuth client configured for API access. |
| `AIRBYTE_GOOGLE_ADS_REFRESH_TOKEN` | Refresh token tied to the Ads manager. |
| `AIRBYTE_GOOGLE_ADS_CUSTOMER_ID` | Customer ID (without dashes) that owns the campaigns. |
| `AIRBYTE_GOOGLE_ADS_LOGIN_CUSTOMER_ID` | Login customer for MCC hierarchies. |
| `AIRBYTE_GOOGLE_ADS_START_DATE` | YYYY-MM-DD start date for backfills (default `2023-01-01`). |
| `AIRBYTE_GOOGLE_ADS_CONVERSION_WINDOW_DAYS` | Conversion lag considered during syncs (default `30`). |
| `AIRBYTE_GOOGLE_ADS_LOOKBACK_WINDOW_DAYS` | Additional incremental replay window (default `3`). |
| `AIRBYTE_GOOGLE_ADS_CUSTOM_QUERY` | Optional override for the GAQL metrics query (defaults to packaged query). |

| Connector             | Required environment variables |
| --------------------- | -------------------------------- |
| Google Ads            | `AIRBYTE_GOOGLE_ADS_DEVELOPER_TOKEN`, `AIRBYTE_GOOGLE_ADS_CLIENT_ID`, `AIRBYTE_GOOGLE_ADS_CLIENT_SECRET`, `AIRBYTE_GOOGLE_ADS_REFRESH_TOKEN`, `AIRBYTE_GOOGLE_ADS_CUSTOMER_ID`, `AIRBYTE_GOOGLE_ADS_LOGIN_CUSTOMER_ID`, `AIRBYTE_GOOGLE_ADS_START_DATE` (optional), `AIRBYTE_GOOGLE_ADS_CONVERSION_WINDOW_DAYS` (optional), `AIRBYTE_GOOGLE_ADS_LOOKBACK_WINDOW_DAYS` (optional), `AIRBYTE_GOOGLE_ADS_CUSTOM_QUERY` (optional) |
| Meta Marketing API    | `AIRBYTE_META_ACCOUNT_ID`, `AIRBYTE_META_ACCESS_TOKEN`, `AIRBYTE_META_START_DATE` (optional), `AIRBYTE_META_INSIGHTS_LOOKBACK_DAYS` (optional), `AIRBYTE_META_ATTRIBUTION_WINDOW_DAYS` (optional) |
| Google Analytics 4    | `AIRBYTE_GA4_CLIENT_ID`, `AIRBYTE_GA4_CLIENT_SECRET`, `AIRBYTE_GA4_REFRESH_TOKEN`, `AIRBYTE_GA4_PROPERTY_ID`, `AIRBYTE_GA4_START_DATE` (optional), `AIRBYTE_GA4_LOOKBACK_WINDOW_DAYS` (optional) |
| Search Console        | `AIRBYTE_SEARCH_CONSOLE_CLIENT_ID`, `AIRBYTE_SEARCH_CONSOLE_CLIENT_SECRET`, `AIRBYTE_SEARCH_CONSOLE_REFRESH_TOKEN`, `AIRBYTE_SEARCH_CONSOLE_SITE_URL`, `AIRBYTE_SEARCH_CONSOLE_START_DATE` (optional), `AIRBYTE_SEARCH_CONSOLE_LOOKBACK_WINDOW_DAYS` (optional) |
| LinkedIn Ads (custom) | `AIRBYTE_LINKEDIN_ACCOUNT_ID`, `AIRBYTE_LINKEDIN_ACCESS_TOKEN`, `AIRBYTE_LINKEDIN_START_DATE` (optional), `AIRBYTE_LINKEDIN_LOOKBACK_DAYS` (optional) |
| TikTok Ads (custom)   | `AIRBYTE_TIKTOK_ADVERTISER_ID`, `AIRBYTE_TIKTOK_ACCESS_TOKEN`, `AIRBYTE_TIKTOK_START_DATE` (optional), `AIRBYTE_TIKTOK_LOOKBACK_DAYS` (optional) |

### Authentication & Rollout Notes

- **Meta Marketing API:** Generate a long-lived access token scoped for the Ad Insights API and inject it through `AIRBYTE_META_ACCESS_TOKEN`. The connector honours the 28-day attribution window via `AIRBYTE_META_ATTRIBUTION_WINDOW_DAYS` and will replay late conversions as long as the lookback exceeds your expected delay profile.
- **Google Ads:** Service account OAuth credentials must be refreshed through the provided refresh token. Set `AIRBYTE_GOOGLE_ADS_CUSTOM_QUERY` only when custom GAQL slices are required; otherwise the default query projects the PRD field set.
- **LinkedIn Ads:** Provision a reporting-only OAuth token with the `r_ads_reporting` scope and copy the numeric account identifier. The connector automatically requests seven-day slices with a two-day lookback to capture late attributions.
- **TikTok Ads:** Generate an advertiser-scoped token with access to `report/integrated` and store it in `AIRBYTE_TIKTOK_ACCESS_TOKEN`. TikTok returns spend in account currency; downstream dbt models cast to standard currency types.

### Acceptance Tests

Connector manifests ship with Airbyte's connector test harness. Run the incremental discovery suite before shipping changes:

```bash
pytest infrastructure/airbyte/sources/tests -q
python3 infrastructure/airbyte/scripts/check_data_contracts.py
```

The harness uses mocked HTTP responses so the tests execute without contacting upstream APIs.

### Rollout Checklist

1. Export the environment variables listed above and verify `docker compose --env-file .env config` renders without unresolved templates.
2. Run `python3 infrastructure/airbyte/scripts/check_data_contracts.py` to verify query aliases, seed headers, and env-name consistency.
3. Import each `{platform}_ads_source.yaml` file into Airbyte (UI or API) and complete the OAuth consent flows where applicable.
4. Run the acceptance tests locally (`pytest infrastructure/airbyte/sources/tests -q`) and validate discovery in the Airbyte UI.
5. Create destinations/connection pairs, enable incremental sync with the documented cron schedule, and monitor the first run for quota or schema issues.
6. Flip the corresponding dbt feature flags (`enable_linkedin`, `enable_tiktok`) once the first sync succeeds.

## Production Readiness Verification (Meta + Google)

Use this sequence before promoting tenant connections in staging/production. Ownership:
Maya (integrations), Leo (Celery/retries), Priya (dbt), Sofia (metrics API), Raj (cross-stream).

1. Prepare env vars in a secure store and load them into the runtime shell (no inline secrets).
2. Verify compose rendering:
   - `cd infrastructure/airbyte && docker compose --env-file .env config`
3. Create/update Meta + Google template sources/connections and capture returned connection IDs:
   - `python3 infrastructure/airbyte/scripts/provision_meta_google_connectors.py`
   - persist outputs:
     - `AIRBYTE_TEMPLATE_META_METRICS_CONNECTION_ID`
     - `AIRBYTE_TEMPLATE_GOOGLE_METRICS_CONNECTION_ID`
4. Verify tenant + template config:
   - `python3 infrastructure/airbyte/scripts/validate_tenant_config.py`
5. Verify production-only connector vars are present and non-placeholder:
   - `python3 infrastructure/airbyte/scripts/verify_production_readiness.py`
6. Apply/update tenant connections:
   - `python3 infrastructure/airbyte/scripts/bootstrap_connections.py`
7. Validate connection health:
   - `python3 infrastructure/airbyte/scripts/airbyte_health_check.py`
8. Validate backend telemetry + freshness:
   - `GET /api/health/airbyte/`
   - `GET /api/airbyte/telemetry/`
9. Validate downstream marts/dashboard contract:
   - `GET /api/health/dbt/`
   - `GET /api/metrics/combined/?source=warehouse`

### Retry, Backoff, and Telemetry Expectations

- Sync orchestration retries use exponential backoff (base 2), max 5 attempts, with jitter.
- Configuration errors use a higher base delay (`300s`) with a `900s` cap.
- Structured logs include `tenant_id`, `task_id`, `correlation_id`, provider, and connection IDs.
- Alert when:
  - two or more consecutive sync failures occur for a connection,
  - `/api/health/airbyte/` reports `stale` or `sync_failed`,
  - telemetry indicates unexpectedly empty syncs.
