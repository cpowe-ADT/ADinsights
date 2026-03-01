# Backend Telemetry CI Runbook

This runbook explains how to operate the **Backend Telemetry CI** workflow and
interpret the artifacts it produces. The goal is to detect breaking changes in
our telemetry payloads before they affect downstream dashboards or analysts.

## Workflow Overview

- **Workflow file:** `.github/workflows/backend-telemetry.yml`
- **Triggers:**
  - Pull requests touching `backend/**`, telemetry fixtures, or runbooks.
  - Scheduled run at `11:15 UTC` (06:15 local time in `America/Jamaica`).
  - Manual execution via the GitHub Actions UI.
- **Jobs:**
  1. **Ruff telemetry** – lints `backend/` with `ruff` using the shared Python
     toolchain and pip cache.
  2. **Pytest telemetry** – runs `pytest backend` with coverage, generates
     `backend-ci-summary.json`, `ci-metrics.csv`, JUnit XML, and HTML coverage
     reports that mirror the main backend workflow artifacts.
  3. **Telemetry schema guard** – executes
     `scripts/ci/check_backend_telemetry.py` to hydrate telemetry fixtures,
     validate payloads against JSON Schema baselines, and publish human-friendly
     summaries.

All jobs reuse the same Python 3.11 environment, pip cache, and environment
variables as the core backend workflow to minimise surprises.

## Artifacts

| Artifact                         | Produced By            | Contents                                                                                        |
| -------------------------------- | ---------------------- | ----------------------------------------------------------------------------------------------- |
| `backend-ci-summary.json`        | Pytest telemetry       | Aggregated pass/fail counts for dashboards.                                                     |
| `ci-metrics.csv`                 | Pytest telemetry       | Time-series friendly metrics for observability pipelines.                                       |
| `backend-tests/junit.xml`        | Pytest telemetry       | Raw JUnit output for CI surfaces.                                                               |
| `backend-coverage/`              | Pytest telemetry       | `coverage.xml` + HTML coverage report.                                                          |
| `backend-telemetry-summary.md`   | Telemetry schema guard | Markdown digest of telemetry payloads per tenant.                                               |
| `backend-telemetry-summary.json` | Telemetry schema guard | Structured log (with `tenant_id`, `task_id`, `correlation_id`) for analysts and alerting rules. |

> **Tenant isolation:** The Markdown and JSON outputs only include data for the
> seeded telemetry tenant (`Telemetry Tenant`). Ensure analysts never cross-mix
> tenants when comparing artifacts.

## Schema Baselines

Canonical schemas live under `backend/tests/schemas/`. They cover:

- Dashboard aggregate snapshot (`dashboard_aggregate_snapshot.schema.json`).
- Airbyte health telemetry (`airbyte_health.schema.json`).
- dbt health telemetry (`dbt_health.schema.json`).

### Regenerating Baselines

1. Update fixtures or adapters locally.
2. Run `python scripts/ci/check_backend_telemetry.py` – it hydrates
   `backend/tests/schemas/fixtures/telemetry.json`, refreshes Airbyte/dbt
   timestamps, and rewrites:
   - `backend-telemetry-summary.md`
   - `backend-telemetry-summary.json`
3. Review the generated Markdown/JSON and commit schema updates if the changes
   are expected. Always sanity check that required sections (campaign, creative,
   budget, parish aggregates) and Airbyte/dbt job summaries remain present.

### Adding New Schemas

- Place the schema under `backend/tests/schemas/`.
- Extend `SCHEMA_FILES` in `scripts/ci/check_backend_telemetry.py` and the
  assertions in `backend/tests/test_schema_regressions.py`.
- Add any required fixtures under `backend/tests/schemas/fixtures/`.

## Troubleshooting

| Symptom                                                     | Likely Cause                                               | Resolution                                                                                                                 |
| ----------------------------------------------------------- | ---------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| Telemetry schema guard fails with `Apps aren't loaded yet`. | Django environment not configured before script execution. | Ensure `scripts/ci/check_backend_telemetry.py` runs from repo root or call `python -m scripts.ci.check_backend_telemetry`. |
| Airbyte health reports `stale` in CI.                       | Fixture timestamps older than one hour.                    | Re-run the schema guard script locally to refresh timestamps or update fixtures.                                           |
| dbt health reports `missing_run_results`.                   | `dbt/target/run_results.json` missing.                     | Verify the script copied the template; rerun the guard script.                                                             |
| Markdown summary references multiple tenants.               | Fixtures accidentally seeded additional tenants.           | Reset the database (`rm backend/db.sqlite3`) and rerun the script; confirm fixture only contains `Telemetry Tenant`.       |

## Related Documentation

- [Deployment Runbook](./deployment.md)
- [Operations Runbook](./operations.md)
- [Logging Standards](../ops/logging-standards.md)

Keep this document updated whenever telemetry fixtures, schemas, or workflow
steps change.
