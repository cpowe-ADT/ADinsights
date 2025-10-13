# Airbyte Stack

This compose file boots an Airbyte OSS deployment suitable for local development.

## Usage

```bash
docker compose up -d
```

The UI will be available at <http://localhost:8000> and the API at <http://localhost:8001>.

## Scheduling Guidance

Airbyte schedules live on each **Connection**. From the UI (`Connections → <Connection> → Replication`) or the API (`/api/v1/connections/update`), align cadences to the downstream warehouse refresh windows:

- **Hourly metrics pulls** – Insight tables (Meta `ad_insights`, Google Ads GAQL metric queries). Configure a cron such as `0 * * * *` with an **Additional sync lookback window** of 3 days to sweep up delayed conversions.
- **Daily dimension refresh** – Entities (accounts, campaigns, ad sets/sets, ads, creatives) and geographic lookups. Use `0 6 * * *` so dbt transformations see stable dimensions before the Jamaica business day starts.
- **Weekly transparency jobs** – Optional disclosure connectors (TikTok Commercial Content, LinkedIn revenue transparency). Schedule for low-traffic windows like `0 2 * * 1`.

Document the chosen cron/anchor in your runbook so stakeholders know when fresh numbers land.

## Source Templates

Copy the `.example` files in `sources/` to real JSON files before importing into Airbyte. Never commit actual credentials.

```bash
cp sources/meta_marketing.json.example sources/meta_marketing.json
cp sources/google_ads.json.example sources/google_ads.json
```

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
