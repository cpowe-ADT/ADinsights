# Observability Stability Tests & Runbook QA

Use this checklist to validate observability stability after deploys or config changes. Run at least monthly and after any alerting or logging changes.

## Stability tests

### 1) Metrics pipeline

- `/metrics/app/` returns 200 and includes core metrics.
- Prometheus target is `UP` and scrape errors are zero.
- Sample dashboards show new data within two scrape intervals.

### 2) Health endpoints

- `/api/health/`, `/api/health/airbyte/`, `/api/health/dbt/` return 200.
- `status` values match expected state for the last scheduled run.
- Staleness fields (`age_hours`, `latest_sync_age_minutes`) match current time.

### 3) Celery instrumentation

- Trigger a manual task (e.g., `sync_meta_metrics`) and confirm:
  - `celery_task_executions_total` increments for success and failure cases.
  - `celery_task_duration_seconds` emits a histogram sample.
  - Logs include `tenant_id`, `task_id`, and `correlation_id`.

### 4) Airbyte telemetry

- Run a single Airbyte sync and verify:
  - `airbyte_sync_latency_seconds` and `airbyte_sync_rows_total` emit samples.
  - Errors increment `airbyte_sync_errors_total` when failures occur.
  - `/api/health/airbyte/` shows the updated sync timestamp.

### 5) dbt telemetry

- Execute a dbt run and verify:
  - `dbt_run_duration_seconds{status="success"}` emits a sample.
  - `/api/health/dbt/` reflects the latest run status.

## Runbook QA checklist

- Thresholds and escalation contacts are up to date.
- Each alert links to a dashboard and a primary runbook.
- Commands and endpoints have been smoke-tested in the target environment.
- Known edge cases (rate limits, empty syncs, stale data) are documented.
- Runbook owners are listed and backups confirmed.

## Evidence to capture

- Screenshots or links to Prometheus targets and dashboards.
- Sample log entries with required fields.
- Incident notes for any failures uncovered during testing.

## See also

- `docs/ops/metrics-scrape-validation.md`
- `docs/ops/alert-thresholds-escalation.md`
- `docs/runbooks/operations.md`
