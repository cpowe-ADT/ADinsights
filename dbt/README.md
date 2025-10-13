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

The repository includes a `Makefile` with common workflows. Operators running
the project locally can also execute the canonical build sequence manually if
they prefer to see each phase complete before moving on to the next. Run these
commands from the repository root so dbt can find the project under `dbt/`:

1. Load seed data: `dbt seed`
2. Build the staging layer: `dbt run --select staging`
3. Capture snapshot tables: `dbt snapshot`
4. Build the mart models: `dbt run --select marts`

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

Generated marts include slowly changing dimensions (`dim_campaign`, `dim_adset`, `dim_ad`) built via the shared `scd2_dimension` macro, the static `dim_geo` lookup, the `fct_ad_performance` fact, and aggregate views (`vw_campaign_daily`, `vw_creative_daily`, `vw_pacing`). Metric calculations such as CTR, CPM, and cost efficiency leverage the reusable helpers in `dbt/macros/metrics.sql`.

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

## Continuous integration fixtures

The repository ships lightweight CSV seeds under `dbt/seeds/` that emulate the
raw Airbyte tables referenced by the staging layer. CI jobs can run the staging
models without connecting to Airbyte by seeding these fixtures and setting the
`CI_USE_SEEDS=true` environment variable before invoking `dbt run`. An on-run-
start macro creates (and replaces) views in the expected raw schemas that point
to the seeded relations, so the process is idempotent and safe to rerun. Teams
can override the raw schema names with dbt variables such as `raw_schema`,
`raw_google_ads_schema`, or `raw_meta_schema` when needed.
