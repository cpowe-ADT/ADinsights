# Operations Runbook

This runbook documents how to operate the ADinsights stack across the frontend, backend, BI, and scheduled services.

## Environments

- **Local development** – developers run the stack via `docker compose up` (see `deploy/docker-compose.yml`).
- **Staging** – nightly refreshes of warehouse replicas and Superset metadata.
- **Production** – 15 minute refresh cadence, Superset in high-availability mode, alerts integrated with Slack and email.

## Health Checks

| Component             | Check                                            | Command                                                     |
| --------------------- | ------------------------------------------------ | ----------------------------------------------------------- |
| Frontend              | Vite build + smoke test                          | `npm run build` (from `frontend/`)                          |
| Backend               | Django API health endpoint                       | `curl https://api.<env>.adinsights.com/api/health/`         |
| Airbyte Orchestration | API health endpoint + status payload             | `curl https://api.<env>.adinsights.com/api/health/airbyte/` |
| dbt Orchestration     | API health endpoint (exposes latest run results) | `curl https://api.<env>.adinsights.com/api/health/dbt/`     |
| Superset              | `/health` endpoint                               | `curl https://bi.<env>.adinsights.com/health`               |
| Scheduler             | APScheduler heartbeat logs                       | Check `scheduler` container logs for `Scheduler started`    |

The Airbyte health endpoint surfaces the most recent sync metadata per tenant and flags jobs that
are older than one hour. The dbt health endpoint reads the most recent `run_results.json` and marks
the service as stale when no run has completed within the past 24 hours. Both responses return
machine-friendly JSON payloads for dashboards or alerting rules.

## Deployments

1. Merge changes to `main` with green CI.
2. Tag release (`git tag -a vX.Y.Z -m "Release vX.Y.Z"`).
3. Trigger the `deploy-full-stack` GitHub Actions workflow or run `deploy/deploy_full_stack.sh`.
4. Monitor rollout via Datadog dashboards and Superset status page.

## Incident Response

1. Acknowledge alert in Slack (#adinsights-alerts).
2. Review Superset dashboards referenced in alert payloads.
3. Use `/alerts/run` endpoint to re-trigger evaluation after remediation.
4. Document root cause analysis in the incident ticket.

## Audit Logging

- **What is logged** – The backend persists `AuditLog` rows for every user
  authentication, platform credential create/update/delete, role assignment
  change, and manual sync trigger. Operators can review entries via the
  `/api/audit-logs/` endpoint (filterable by `action` or `resource_type`).
- **Storage** – Audit events live in the primary Postgres database under the
  `accounts_auditlog` table. Each row is tenant-scoped to prevent cross-tenant
  access.
- **Retention** – Maintain at least 365 days of audit history to satisfy common
  compliance requirements. Configure a nightly database task (e.g. cron job or
  managed retention policy) that deletes records older than the retention
  window: `DELETE FROM accounts_auditlog WHERE created_at < NOW() - INTERVAL '365
days';` Adjust the interval to meet contractual obligations.
- **Export/Archival** – For deployments that require longer retention, ship
  daily exports of the table to object storage (S3/GCS) before running the
  deletion query. Ensure exported files inherit the environment's encryption
  and access controls.

## Observability & Alerting

- **Structured logging** – API and Celery workloads emit JSON logs (`api.access`,
  `celery.tasks`) that include duration, tenant identifiers, and task metadata. Ingest
  these streams into your log platform with at least 30 days of retention for incident
  reconstruction.
- **Metrics baselines** – Treat an Airbyte sync as healthy when the freshest job is
  < 60 minutes old and has a `succeeded` status. dbt pipelines are healthy when the
  latest run completed successfully within 24 hours and all models report `success`
  or `skipped` in the run results payload.
- **Alerting targets** – Configure alerts when API request error rate exceeds 2% over
  5 minutes, Airbyte health responds `stale`/`no_recent_sync`, or dbt health responds
  `stale`/`failing`. Set SLA expectations at 99.5% API availability, Airbyte sync freshness
  under 60 minutes, and dbt transformations under 24 hours.
- **Dashboards** – Plot `/api/health/airbyte/` and `/api/health/dbt/` responses alongside
  Celery task durations to visualize orchestration performance trends and catch regressions
  before they breach SLAs.

## Data Refresh Failures

- Validate warehouse connectors via Superset → Data → Databases.
- Re-run `dbt` transformation job via the scheduler container (`make run-dbt`).
- Escalate to Data Engineering if source pipelines show latency over 60 minutes.

## Tenant Safety Checklist

Run this checklist before every release that touches the backend or ingestion
surface area.

1. **Settings guardrail** – `ENABLE_TENANCY` defaults to `True` in
   `backend/core/settings.py` and the environment override is present in the
   deployment manifests.
2. **HTTP traversal** – Hit `/api/analytics/campaigns/` and
   `/api/airbyte/telemetry/` with two test tenants; confirm responses contain
   only the authenticated tenant’s data (see `backend/tests/test_analytics_endpoints.py`).
3. **Warehouse adapter** – Verify `WarehouseAdapter.fetch_metrics` returns the
   correct tenant snapshot and does not leak other tenants’ payloads (also
   covered by tests).
4. **Background tasks** – Ensure Celery workers run with the latest code so
   `tenant_context(...)` is applied; spot check logs for missing `tenant_id`
   fields.
5. **Audit trail** – Confirm new endpoints/actions emit `log_audit_event(...)`
   with the current tenant and that `/api/audit-logs/` returns scoped results.

## Snapshot Lag Troubleshooting

1. **Inspect freshness** – Call `/api/metrics/combined/?source=warehouse` for
   an affected tenant. The payload now returns `snapshot_generated_at`. Treat
   any value older than the dbt SLA (60 minutes by default) as stale.
2. **Manual refresh** – Run `python manage.py snapshot_metrics --tenant-id <UUID>`
   to refresh a single tenant, or omit `--tenant-id` to rebuild every snapshot.
   The Celery task `analytics.sync_metrics_snapshots` is also available via
   Flower or `celery control broadcast run-task`.
3. **Beat schedule** – Ensure the `metrics-snapshot-sync` entry in
   `CELERY_BEAT_SCHEDULE` is enabled (30-minute cadence). Worker logs should
   include `metrics.snapshot.persisted` for each tenant.
4. **Alerts** – Configure monitoring to fire when
   `snapshot_generated_at` is older than 60 minutes or missing entirely.
   Pair this with the Airbyte/dbt health checks to pinpoint upstream causes.
5. **Dashboards** – The “Warehouse Snapshot Health” Grafana/Superset view plots
   snapshot recency per tenant. Use it to verify manual refreshes before
   closing an incident.

## Contact

- Marketing Operations On-Call: `marketing-ops@example.com`
- Data Engineering: `data-eng@example.com`
- Platform Engineering: `platform-eng@example.com`
