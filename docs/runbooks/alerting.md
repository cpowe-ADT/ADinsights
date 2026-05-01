# Alerting Workflow Runbook

## Overview

Alerting is driven by system SQL thresholds defined in `backend/app/alerts.py` plus tenant-defined `AlertRuleDefinition` rows. Rules are evaluated every 15 minutes by the Celery beat scheduler and results are summarized by the LLM integration. Tenant-defined rules with matching `NotificationChannel` assignments dispatch only when an evaluation returns rows. Each evaluation is persisted to the `alerts_alertrun` table and exposed via `GET /api/alerts/runs/` for historical analysis.

Default thresholds and escalation steps live in `docs/ops/alert-thresholds-escalation.md`.

## Manual Execution

```bash
curl -X POST https://api.<env>.adinsights.com/alerts/run
```

This triggers the `run_alert_cycle` task and posts results to the configured channels.

## Adding a System Rule

1. Create a new `AlertRule` entry in `backend/app/alerts.py` with SQL scoped to the relevant dataset.
2. Include a clear description and threshold.
3. Add supporting visualizations in Superset so analysts can investigate quickly.
4. Deploy and validate by running the manual execution command above.

## Tenant Rule Notification Channels

Tenant-defined alert rules use `AlertRuleDefinition.notification_channels`. The delivery path skips inactive channels and isolates failures per channel so one broken destination does not prevent the alert run from completing.

Supported `NotificationChannel.config` shapes:

- Email (`channel_type="email"`): `{"emails": ["ops@example.com", "analyst@example.com"]}` or `{"emails": "ops@example.com,analyst@example.com"}`. Optional: `from_email`.
- Slack (`channel_type="slack"`): `{"url": "https://hooks.slack.com/services/..."}`. `webhook_url` is also accepted as an alias.
- Webhook (`channel_type="webhook"`): `{"url": "https://example.com/alerts", "headers": {"X-Alert-Token": "redacted"}}`. `webhook_url` is also accepted as an alias.

Webhook payloads include the alert run id, rule id/name, severity, metric threshold, status, row count, LLM summary, and sanitized result rows. Do not store secrets directly in runbooks or screenshots; use secret-management references for webhook URLs and tokens.

## LLM Summaries

- Endpoint: `ADINSIGHTS_LLM_API_URL`
- Model: `gpt-5.1`
- Prompt: Summaries capped at 120 words with tactical next steps.
- Fallback: If the LLM request fails, alerts still log the raw payload for manual review.

## Integration Points

- Slack webhook(s) managed in 1Password or the environment's secret manager.
- Email distribution lists maintained in Google Workspace.
- DB credentials rotate via Vault every 90 days.

## Dashboards & Escalation

- Dashboards (replace `<env>` with the target environment):
  - `https://grafana.<env>.adinsights.dev/d/metrics-app` (API + metrics health).
  - `https://grafana.<env>.adinsights.dev/d/airbyte-syncs` (Airbyte sync freshness/errors).
  - `https://grafana.<env>.adinsights.dev/d/dbt-runs` (dbt run status + duration).
  - `https://grafana.<env>.adinsights.dev/d/celery-tasks` (Celery task throughput/failure).
- Escalation contacts and timeframes: `docs/ops/escalation-matrix.md`.
- Threshold definitions: `docs/ops/alert-thresholds-escalation.md`.

## Freshness & Webhook Alerts

- **Airbyte webhook silence** – Alert when no `airbyte_job_webhook` audit entries arrive for >30 minutes while
  Airbyte jobs exist. Secondary signal: `airbyte_sync_errors_total` or `/api/health/airbyte/` returning `stale`.
- **Snapshot recency** – Monitor `/api/metrics/combined/` responses: if `snapshot_generated_at` is older than 60 minutes
  per tenant, raise a `metrics_snapshot_stale` alert. Pair with Celery task metrics (`celery_task_executions_total`)
  to confirm the snapshot worker is running.
- **dbt freshness** – Alert when `/api/health/dbt/` reports `stale` or `failing`, and include the failing models list
  from the endpoint in the notification.
- **dbt runtime** – Track `dbt_run_duration_seconds{status=*}` from `/metrics/app/` to spot slow or failing runs; alert on
  sustained p95 latency increases or missing samples in the scheduled window.

## Structured Logging Checks

- Structured logs already include `tenant_id`, `task_id`, and `correlation_id` via `core.observability.ContextFilter`.
  Dashboard panels should filter on these fields to trace tenant-specific issues.
- When deploying new tasks or webhooks, validate logs in Datadog/Loki by searching for
  `correlation_id=<celery task id>` to confirm the context filter is attached.
