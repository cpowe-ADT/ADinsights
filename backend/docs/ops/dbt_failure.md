# dbt Failure Runbook

## Trigger

- dbt runs fail in CI or scheduled jobs.
- Warehouse-derived metrics endpoints return stale data.

## Triage

- From repo root, ensure dependencies resolve:
  - `make dbt-deps`
- Validate the dbt project parses:
  - `dbt --project-dir dbt parse`
- Inspect run logs and artifacts:
  - `dbt/target/run_results.json`
  - `dbt/target/logs/dbt.log`

## Recovery

- Re-run staging models:
  - `dbt --project-dir dbt run --select staging`
- Re-run tests for failing models:
  - `dbt --project-dir dbt test --select <model_name>`
- If schema changes are involved, coordinate a rollback and re-run.

## Escalation

- Escalate if:
  - Failures persist across two runs.
  - Source schemas changed upstream without versioned updates.
  - Production dashboards show incorrect aggregated metrics.
