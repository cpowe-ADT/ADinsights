# dbt Project

This project seeds lookup data, builds staging models for ad platform feeds, and surfaces mart-level dimensions and dashboards-ready views for downstream reporting.

## Setup

1. Copy `profiles-example.yml` to `~/.dbt/profiles.yml` and adjust credentials.
2. Install dbt (e.g. `pip install dbt-postgres`).
3. Install dependencies and seed lookup data:

```bash
make dbt-deps
make dbt-seed
```

## Building the warehouse

The repository includes a `Makefile` with common workflows.

```bash
# Run the full build (staging, marts, tests)
make dbt-build

# Recompute incremental models from scratch
make dbt-build-full

# Run just the automated tests
make dbt-test

# Check source recency for all active connectors
make dbt-freshness
```

Generated marts include slowly changing dimensions (`dim_campaign`, `dim_adset`, `dim_ad`, `dim_geo`), the `fct_ad_performance` fact, and aggregate views (`vw_campaign_daily`, `vw_creative_daily`, `vw_pacing`). These models leverage the shared `scd2_dimension` macro alongside reusable metric macros in `dbt/macros/metrics.sql`.

## Optional connectors

LinkedIn and TikTok transparency feeds are disabled by default. To enable either source:

1. Configure the corresponding Airbyte syncs.
2. Set the dbt variables in your profile or the CLI:

```bash
# Example: enable TikTok while running a one-off build
make dbt-build DBT="dbt --project-dir dbt --profiles-dir dbt --vars '{enable_tiktok: true}'"
```

You can also add the variables to the `vars` section of your profile so they are always on:

```yaml
vars:
  enable_linkedin: true
  enable_tiktok: true
```

When enabled, freshness checks and staging model tests for the optional connectors are activated automatically.
