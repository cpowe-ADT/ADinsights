# Alerting Workflow Runbook

## Overview

Alerting is driven by SQL thresholds defined in `backend/app/alerts.py`. Rules are evaluated every 15 minutes by the Celery beat scheduler and results are summarized by the LLM integration before being dispatched to Slack/email. Each evaluation is persisted to the `alerts_alertrun` table and exposed via `GET /api/alerts/runs/` for historical analysis.

## Manual Execution

```bash
curl -X POST https://api.<env>.adinsights.com/alerts/run
```

This triggers the `run_alert_cycle` task and posts results to the configured channels.

## Adding a New Rule

1. Create a new `AlertRule` entry in `backend/app/alerts.py` with SQL scoped to the relevant dataset.
2. Include a clear description, threshold, and channels.
3. Add supporting visualizations in Superset so analysts can investigate quickly.
4. Deploy and validate by running the manual execution command above.

## LLM Summaries

- Endpoint: `ADINSIGHTS_LLM_API_URL`
- Model: `gpt-5.1`
- Prompt: Summaries capped at 120 words with tactical next steps.
- Fallback: If the LLM request fails, alerts still log the raw payload for manual review.

## Integration Points

- Slack webhook(s) managed in 1Password.
- Email distribution lists maintained in Google Workspace (`marketing-ops@example.com`).
- DB credentials rotate via Vault every 90 days.

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
