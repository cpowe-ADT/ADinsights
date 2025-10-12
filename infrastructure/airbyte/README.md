# Airbyte Stack

This compose file boots an Airbyte OSS deployment suitable for local development.

## Usage

```bash
docker compose up -d
```

The UI will be available at <http://localhost:8000> and the API at <http://localhost:8001>.

## Scheduling Guidance

- **Hourly**: Performance/insights tables (Meta `ad_insights`, Google Ads GAQL metrics). Re-pull a rolling 3-day lookback to catch late conversions.
- **Daily**: Dimension tables (accounts, campaigns, ad sets, ads, creatives) and Google GeoTarget constants.
- **Weekly**: Transparency/optional connectors (TikTok Commercial Content, LinkedIn revenue metrics) when configured.

Use Airbyte's connection scheduling to set cron expressions that align with the above cadence.

## Source Templates

Copy the `.example` files in `sources/` to real JSON files before importing into Airbyte. Never commit actual credentials.

```bash
cp sources/meta_marketing.json.example sources/meta_marketing.json
cp sources/google_ads.json.example sources/google_ads.json
```

For optional connectors (LinkedIn, TikTok) provide API keys only if you have access.
