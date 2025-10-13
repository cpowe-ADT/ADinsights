# Airbyte Stack

This compose file boots an Airbyte OSS deployment suitable for local development.

## Usage

```bash
docker compose up -d
```

The UI will be available at <http://localhost:8000> and the API at <http://localhost:8001>.

## Scheduling Guidance
All schedules reference the **America/Jamaica** timezone so they align with downstream SLAs documented in `AGENTS.md`. Airbyte schedules live on each **Connection**; configure them via the UI (`Connections → <Connection> → Replication`) or the API (`/api/v1/connections/update`).
- Follow Airbyte's [incremental sync guidance](https://docs.airbyte.com/understanding-airbyte/sync-modes/incremental) so hourly metrics and daily dimensions use incremental mode with the documented lookback windows.

- **sync_meta_metrics / sync_google_metrics (hourly metrics pulls):** Configure a cron such as `0 6-22 * * *` to run hourly between 06:00 and 22:00. Enable an **Additional sync lookback window** of 3 days to sweep up delayed conversions and keep each run under 30 minutes.
- **sync_dimensions_daily (dimension refresh):** Schedule at `15 2 * * *` so campaign/ad set/ad metadata and geographic lookups finish before the 03:00 SLA.
- **Optional transparency connectors:** If enabled, run during low-traffic windows such as `0 2 * * 1`.

After each metrics sync, trigger dbt's incremental staging models; schedule the aggregate marts around 05:00 so dashboards populate by 06:00.

Document the chosen cron/anchor in your runbook so stakeholders know when fresh numbers land.

## Source Templates

Copy the `.example` files in `sources/` to real JSON files before importing into Airbyte. Never commit actual credentials.

```bash
cp sources/meta_marketing.json.example sources/meta_marketing.json
cp sources/google_ads.json.example sources/google_ads.json
```

The Google Ads sample uses Airbyte's `{{ runtime_from_date }}` template variable inside each custom
query so the connector replays only the slices required by the incremental state rather than a fixed
28-day window. Keep the cursor fields and lookback windows aligned with your desired backfill
horizon when adapting the template.

For optional connectors (LinkedIn, TikTok) provide API keys only if you have access.

# Airbyte Configuration

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
| Meta Marketing API | `AIRBYTE_META_ACCESS_TOKEN`, `AIRBYTE_META_ACCOUNT_ID` |
| LinkedIn Transparency (stub) | `AIRBYTE_LINKEDIN_CLIENT_ID`, `AIRBYTE_LINKEDIN_CLIENT_SECRET`, `AIRBYTE_LINKEDIN_REFRESH_TOKEN` |
| TikTok Transparency (stub) | `AIRBYTE_TIKTOK_TRANSPARENCY_TOKEN`, `AIRBYTE_TIKTOK_ADVERTISER_ID` |
