# dbt Project

This project seeds lookup data and builds staging models for Meta and Google Ads feeds synced by Airbyte.

## Setup

1. Copy `profiles-example.yml` to `~/.dbt/profiles.yml` and adjust credentials.
2. Install dbt (e.g. `pip install dbt-postgres`).
3. Run checks:

```bash
dbt debug
dbt seed
dbt run --select staging
```

Models are incremental and re-pull a 30 day window to catch late conversions.
