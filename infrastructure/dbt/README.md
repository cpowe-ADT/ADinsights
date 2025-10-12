# dbt Infrastructure Notes

The dbt project in `../../dbt` expects the following infrastructure primitives:

- **Warehouse**: PostgreSQL, Snowflake, or BigQuery with support for incremental MERGE statements.
- **Profiles**: A `profiles.yml` entry named `adinsights` that points to the chosen warehouse and uses the `analytics` schema for models.
- **Environment Variables**: Credentials should be sourced from your secrets store and injected as `DBT_HOST`, `DBT_USER`, `DBT_PASSWORD`, `DBT_DATABASE`, and `DBT_SCHEMA` (override default schema if needed).
- **Execution**: Container image with dbt-core >= 1.5.0 and adapters for the target warehouse.
- **Orchestration**: See `docs/orchestration.md` for job scheduling recommendations.
