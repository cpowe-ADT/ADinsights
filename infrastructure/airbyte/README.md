# Airbyte Stack

This compose file boots an Airbyte OSS deployment suitable for local development.

## Usage

```bash
docker compose --env-file env.example up -d
```

The UI will be available at <http://localhost:${AIRBYTE_WEBAPP_PORT:-8000}> and the API at <http://localhost:${AIRBYTE_SERVER_PORT:-8001}>.

Copy `env.example` to `.env` (or provide equivalent environment variables) to keep credentials out of source control while letting
Compose substitute consistent defaults.

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

The Meta Marketing template configures incremental streams on `updated_time` with an Insights lookback window of 3 days across a 28-day
attribution horizon. The Google Ads template uses Airbyte's `{{ runtime_from_date }}` / `{{ runtime_to_date }}` variables so custom
GAQL queries only replay the slices required by the incremental state.

For optional connectors (LinkedIn, TikTok) provide API keys only if you have access.

## Airbyte Configuration

This directory contains declarative configuration snippets for the ingestion layer.

- `meta_source.yaml` – Production-ready Meta Marketing API source configured for incremental syncs on `updated_time`.
- `google_ads_source.yaml` – Google Ads source leveraging a custom query with incremental cursor on `segments.date`.
- `linkedin_transparency_stub.yaml` – HTTP-based placeholder for LinkedIn transparency data until a certified connector is available.
- `tiktok_transparency_stub.yaml` – HTTP-based placeholder for TikTok transparency data.

Optional transparency connectors are disabled by default in dbt via the `enable_linkedin` and `enable_tiktok` variables. When Airbyte jobs for these feeds become available, set the variables to `true` in the target profile to incorporate the additional metrics into the warehouse models.

All files assume credentials are injected from environment variables using Airbyte's declarative templates. Export the variables listed below before applying the YAML snippets. Replace placeholders with the actual workspace UUIDs and connection IDs when provisioning resources.

| Connector | Required environment variables |
| --- | --- |
| Google Ads | `AIRBYTE_GOOGLE_ADS_DEVELOPER_TOKEN`, `AIRBYTE_GOOGLE_ADS_CLIENT_ID`, `AIRBYTE_GOOGLE_ADS_CLIENT_SECRET`, `AIRBYTE_GOOGLE_ADS_REFRESH_TOKEN`, `AIRBYTE_GOOGLE_ADS_CUSTOMER_ID`, `AIRBYTE_GOOGLE_ADS_LOGIN_CUSTOMER_ID` |
| Meta Marketing API | `AIRBYTE_META_APP_ID`, `AIRBYTE_META_APP_SECRET`, `AIRBYTE_META_ACCESS_TOKEN`, `AIRBYTE_META_ACCOUNT_ID` |
| LinkedIn Transparency (stub) | `AIRBYTE_LINKEDIN_CLIENT_ID`, `AIRBYTE_LINKEDIN_CLIENT_SECRET`, `AIRBYTE_LINKEDIN_REFRESH_TOKEN` |
| TikTok Transparency (stub) | `AIRBYTE_TIKTOK_TRANSPARENCY_TOKEN`, `AIRBYTE_TIKTOK_ADVERTISER_ID` |
