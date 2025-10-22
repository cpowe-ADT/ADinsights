# Airbyte Stack

This compose file boots an Airbyte OSS deployment suitable for local development.

## Usage

```bash
docker compose --env-file env.example up -d
```

The UI will be available at <http://localhost:${AIRBYTE_WEBAPP_PORT:-8000}> and the API at <http://localhost:${AIRBYTE_SERVER_PORT:-8001}>.

Copy `env.example` to `.env` (or provide equivalent environment variables) to keep credentials out of source control while letting
Compose substitute consistent defaults.

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
| `validate_tenant_config.py` | Smoke test for environment configuration. Confirms workspaces and destinations exist and validates cron/interval hints before changes are applied. |
| `bootstrap_connections.py` | Clones the template connections for every tenant, applies tenant-specific destination namespaces/prefixes, and enforces schedules that honor the SLA windows. |

Run the validator before attempting to mutate any connections:

```bash
python3 infrastructure/airbyte/scripts/validate_tenant_config.py
```

If the validation passes, bootstrap or update the tenant connections:

```bash
python3 infrastructure/airbyte/scripts/bootstrap_connections.py
```

Both scripts emit JSON summaries to stdout so you can capture the results in CI/CD pipelines. They rely solely on the environment
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

For optional connectors (LinkedIn, TikTok) provide API keys only if you have access.

## Airbyte Configuration

This directory contains declarative configuration snippets for the ingestion layer.

- `meta_source.yaml` – Production-ready Meta Marketing API source configured for incremental syncs on `updated_time`.
- `google_ads_source.yaml` – Google Ads source leveraging a custom query with incremental cursor on `segments.date`.
- `linkedin_transparency_stub.yaml` – HTTP-based placeholder for LinkedIn transparency data until a certified connector is available.
- `tiktok_transparency_stub.yaml` – HTTP-based placeholder for TikTok transparency data.

Optional transparency connectors are disabled by default in dbt via the `enable_linkedin` and `enable_tiktok` variables. When Airbyte jobs for these feeds become available, set the variables to `true` in the target profile to incorporate the additional metrics into the warehouse models.

All files assume credentials are injected from environment variables using Airbyte's declarative templates. Export the variables listed below before applying the YAML snippets. Replace placeholders with the actual workspace UUIDs and connection IDs when provisioning resources.

| Connector                    | Required environment variables                                                                                                                                                                                         |
| ---------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Google Ads                   | `AIRBYTE_GOOGLE_ADS_DEVELOPER_TOKEN`, `AIRBYTE_GOOGLE_ADS_CLIENT_ID`, `AIRBYTE_GOOGLE_ADS_CLIENT_SECRET`, `AIRBYTE_GOOGLE_ADS_REFRESH_TOKEN`, `AIRBYTE_GOOGLE_ADS_CUSTOMER_ID`, `AIRBYTE_GOOGLE_ADS_LOGIN_CUSTOMER_ID` |
| Meta Marketing API           | `AIRBYTE_META_APP_ID`, `AIRBYTE_META_APP_SECRET`, `AIRBYTE_META_ACCESS_TOKEN`, `AIRBYTE_META_ACCOUNT_ID`, `AIRBYTE_META_INSIGHTS_LOOKBACK_DAYS`, `AIRBYTE_META_HOURLY_WINDOW_DAYS`                                     |
| LinkedIn Transparency (stub) | `AIRBYTE_LINKEDIN_CLIENT_ID`, `AIRBYTE_LINKEDIN_CLIENT_SECRET`, `AIRBYTE_LINKEDIN_REFRESH_TOKEN`                                                                                                                       |
| TikTok Transparency (stub)   | `AIRBYTE_TIKTOK_TRANSPARENCY_TOKEN`, `AIRBYTE_TIKTOK_ADVERTISER_ID`                                                                                                                                                    |
