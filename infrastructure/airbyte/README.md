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
- `linkedin_ads_source.yaml` – Connection payload for the custom LinkedIn Ads connector in `sources/linkedin_ads/`.
- `tiktok_ads_source.yaml` – Connection payload for the custom TikTok Ads connector in `sources/tiktok_ads/`.

Optional connectors are disabled by default in dbt via the `enable_linkedin` and `enable_tiktok` variables. Toggle the variables to `true` in the target profile once the corresponding Airbyte connections are enabled so the warehouse models pick up the new feeds.

All files assume credentials are injected from environment variables using Airbyte's declarative templates. Export the variables listed below before applying the YAML snippets. Replace placeholders with the actual workspace UUIDs and connection IDs when provisioning resources.

| Connector             | Required environment variables |
| --------------------- | -------------------------------- |
| Google Ads            | `AIRBYTE_GOOGLE_ADS_DEVELOPER_TOKEN`, `AIRBYTE_GOOGLE_ADS_CLIENT_ID`, `AIRBYTE_GOOGLE_ADS_CLIENT_SECRET`, `AIRBYTE_GOOGLE_ADS_REFRESH_TOKEN`, `AIRBYTE_GOOGLE_ADS_CUSTOMER_ID`, `AIRBYTE_GOOGLE_ADS_LOGIN_CUSTOMER_ID`, `AIRBYTE_GOOGLE_ADS_START_DATE` (optional), `AIRBYTE_GOOGLE_ADS_CUSTOM_QUERY` (optional) |
| Meta Marketing API    | `AIRBYTE_META_ACCOUNT_ID`, `AIRBYTE_META_ACCESS_TOKEN`, `AIRBYTE_META_START_DATE` (optional), `AIRBYTE_META_INSIGHTS_LOOKBACK_DAYS` (optional), `AIRBYTE_META_ATTRIBUTION_WINDOW_DAYS` (optional) |
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
```

The harness uses mocked HTTP responses so the tests execute without contacting upstream APIs.

### Rollout Checklist

1. Export the environment variables listed above and verify `docker compose --env-file .env config` renders without unresolved templates.
2. Import each `{platform}_ads_source.yaml` file into Airbyte (UI or API) and complete the OAuth consent flows where applicable.
3. Run the acceptance tests locally (`pytest infrastructure/airbyte/sources/tests -q`) and validate discovery in the Airbyte UI.
4. Create destinations/connection pairs, enable incremental sync with the documented cron schedule, and monitor the first run for quota or schema issues.
5. Flip the corresponding dbt feature flags (`enable_linkedin`, `enable_tiktok`) once the first sync succeeds.

