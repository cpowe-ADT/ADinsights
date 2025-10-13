# Operations Runbook

This runbook documents how to operate the ADinsights stack across the frontend, backend, BI, and scheduled services.

## Environments

- **Local development** – developers run the stack via `docker compose up` (see `deploy/docker-compose.yml`).
- **Staging** – nightly refreshes of warehouse replicas and Superset metadata.
- **Production** – 15 minute refresh cadence, Superset in high-availability mode, alerts integrated with Slack and email.

## Health Checks

| Component | Check | Command |
|-----------|-------|---------|
| Frontend  | Vite build + smoke test | `npm run build` (from `frontend/`) |
| Backend   | Django API health endpoint | `curl https://api.<env>.adinsights.com/api/health/` |
| Superset  | `/health` endpoint | `curl https://bi.<env>.adinsights.com/health` |
| Scheduler | APScheduler heartbeat logs | Check `scheduler` container logs for `Scheduler started` |

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

## Data Refresh Failures

- Validate warehouse connectors via Superset → Data → Databases.
- Re-run `dbt` transformation job via the scheduler container (`make run-dbt`).
- Escalate to Data Engineering if source pipelines show latency over 60 minutes.

## Contact

- Marketing Operations On-Call: `marketing-ops@example.com`
- Data Engineering: `data-eng@example.com`
- Platform Engineering: `platform-eng@example.com`
