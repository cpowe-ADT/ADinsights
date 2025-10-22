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

Generated marts include slowly changing dimensions (`dim_campaign`, `dim_adset`, `dim_ad`) built via the shared `scd2_dimension` macro, the static `dim_geo` lookup, the `fct_ad_performance` fact, and aggregate views (`vw_campaign_daily`, `vw_creative_daily`, `vw_pacing`). Metric calculations such as CTR, CPM, ROAS, CPC, and pacing leverage the reusable helpers in `dbt/macros/metrics/`.

### Metrics macros

Reusable metric helpers live under `dbt/macros/metrics/` so derived fields stay consistent across marts. They all wrap the shared `safe_divide` macro to protect against divide-by-zero edge cases.

| Macro | Purpose |
| ----- | ------- |
| `metric_ctr(clicks, impressions)` | Click-through rate with zero guards. |
| `metric_conversion_rate(conversions, clicks)` | Downstream conversion rate. |
| `metric_cost_per_click(spend, clicks)` | Average CPC calculations. |
| `metric_cost_per_conversion(spend, conversions)` | Cost per acquisition/conversion. |
| `metric_cpm(spend, impressions)` | Cost per 1,000 impressions. |
| `metric_return_on_ad_spend(revenue, spend)` | ROAS style efficiency. |
| `metric_pacing(actual_value, target_value)` | Ratio between actual and target (e.g. trailing averages) for pacing views. |

To use a helper in a model:

```sql
select
  date_day,
  {{ metric_ctr('clicks', 'impressions') }} as ctr,
  {{ metric_pacing('spend', 'trailing_7d_avg_spend') }} as pacing_vs_7d_avg
from {{ ref('vw_pacing') }}
```

The aggregated marts leverage these macros alongside SCD2 dimensions (`dim_campaign`, `dim_ad`, `dim_adset`) so late-arriving dimension changes remain historically accurate. Incremental configurations refresh a seven-day lookback window on each run, matching the nightly `dbt_aggregates` cadence while still capturing hourly late-arriving fact corrections.

### Downstream dashboards

BI dependencies are tracked through dbt exposures so Superset and Metabase rebuild correctly when mart schemas change:

- `superset_campaign_overview` depends on `vw_campaign_daily` and `vw_creative_daily`.
- `metabase_pacing_monitor` depends on `vw_pacing` and `vw_campaign_daily`.

CI runs include the aggregated marts via the `unique_combination_of_columns` schema test, ensuring the new views stay keyed by date/platform/account IDs even in seed-driven pipelines.
Generated marts include slowly changing dimensions (`dim_campaign`, `dim_adset`, `dim_ad`) built via the shared `scd2_dimension` macro, the static `dim_geo` lookup, the normalized `fact_performance` fact, and aggregate views (`vw_campaign_daily`, `vw_creative_daily`, `vw_pacing`). Metric calculations such as CTR, CPM, and cost efficiency leverage the reusable helpers in `dbt/macros/metrics.sql`, while attribution alignment macros standardize conversion windows across platforms.

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
raw Airbyte tables referenced by the staging layer. The on-run-start macro will
automatically create views that point to these seeds when the expected raw
relations are missing, so a local `dbt run --select staging` succeeds even
without upstream tables. When DuckDB is the target and the seed tables have not
been materialized yet, the macro now falls back to reading the CSV fixtures
directly so `make dbt-build` works out of the box in fresh environments. In CI
pipelines you can still set the `CI_USE_SEEDS=true` environment variable to
force the fixtures to replace any existing relations and guarantee deterministic
inputs. Teams can override the raw schema names with dbt variables such as
`raw_schema`, `raw_google_ads_schema`, or `raw_meta_schema` when needed.
