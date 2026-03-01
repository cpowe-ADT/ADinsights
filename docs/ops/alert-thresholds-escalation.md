# Alert Thresholds & Escalation Runbook

This runbook defines the default alert thresholds for observability signals and the escalation path to use when an alert fires. Tune thresholds per environment and record deviations in the incident notes.

## Scope

- Prometheus metrics exposed by `/metrics/app/`.
- Health endpoints (`/api/health/`, `/api/health/airbyte/`, `/api/health/dbt/`).
- Airbyte webhooks and dbt run telemetry.
- API error rate and latency dashboards.

## Default thresholds

| Alert                    | Signal                                           | Warn threshold      | Page threshold       | Notes                                                       |
| ------------------------ | ------------------------------------------------ | ------------------- | -------------------- | ----------------------------------------------------------- |
| API error rate           | 5xx rate over 5m                                 | >= 2%               | >= 5%                | Use total request volume >= 200 to avoid low-traffic noise. |
| API latency              | p95 latency over 10m                             | >= 1.5s             | >= 3s                | Split by endpoint group (metrics vs auth).                  |
| Metrics endpoint down    | `/metrics/app/` target `up`                      | `up=0` for 5m       | `up=0` for 15m       | Confirm network policy before paging.                       |
| Airbyte sync staleness   | `/api/health/airbyte/` `latest_sync_age_minutes` | >= 60m              | >= 120m              | Hourly sync window; use 3-day lookback where configured.    |
| Airbyte webhook silence  | `airbyte_job_webhook` audit count                | No events for 30m   | No events for 60m    | Cross-check Airbyte job history.                            |
| Airbyte sync errors      | `airbyte_sync_errors_total`                      | >= 3 in 30m         | >= 5 in 30m          | Group by tenant and provider.                               |
| dbt run stale            | `/api/health/dbt/` `age_hours`                   | >= 24h              | >= 36h               | Daily 05:00 schedule; check `dbt_run_duration_seconds`.     |
| dbt run failures         | `/api/health/dbt/` status                        | `failing` for 1 run | `failing` for 2 runs | Capture failing model names in alert payload.               |
| Snapshot freshness       | `/api/metrics/combined/` `snapshot_generated_at` | > 60m               | > 120m               | Per-tenant; pair with Celery task metrics.                  |
| Celery task failure rate | `celery_task_executions_total{status="failure"}` | >= 5% in 15m        | >= 10% in 15m        | Exclude manual backfills.                                   |
| Log ingestion errors     | Log pipeline error rate                          | >= 1% in 15m        | >= 3% in 15m         | Track malformed JSON or dropped events.                     |

## Escalation steps

1. Acknowledge the alert and capture the alert ID, timestamp, and affected tenant(s).
2. Determine severity using `docs/ops/escalation-matrix.md`:
   - **SEV-1**: platform down, data exposure risk, or security event.
   - **SEV-2**: multiple tenants impacted or missing data for a full reporting cycle.
   - **SEV-3**: localized degradation or delayed syncs.
3. Notify the on-call responder and the stream owner (Observability & Alerts: Omar; backup Hannah).
4. If the issue persists beyond the timeframe in the escalation matrix, page the next escalation contact.
5. Start an incident record with the following fields: summary, start time, affected tenants, primary symptom, and current hypothesis.

## Communication checklist

- Post a brief status update in `#adinsights-alerts` after triage (what, who, next action, ETA).
- If SEV-1/SEV-2, open a bridge call and share the incident link.
- Update the incident log with each major mitigation step and relevant dashboards.

## Post-incident follow-up

- Update the relevant runbook if gaps were discovered.
- Add or tune alert thresholds if false positives occurred.
- Capture action items in the risk register when long-term work is required.

## See also

- `docs/runbooks/alerting.md`
- `docs/ops/alerts-runbook.md`
- `docs/ops/escalation-matrix.md`
