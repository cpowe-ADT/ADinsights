# Prometheus Scrape Validation & /metrics/app Smoke Checks

Use this guide to validate that Prometheus can scrape the backend metrics endpoint and that the `/metrics/app/` payload includes expected signals.

## Targets

- Backend metrics endpoint: `https://api.<env>.adinsights.com/metrics/app/`
- Prometheus target group: `adinsights-backend` (or the environment-specific job name)

## Quick smoke check

1. Verify the endpoint responds:

```bash
curl -sSf https://api.<env>.adinsights.com/metrics/app/ > /tmp/metrics.txt
```

2. Confirm the payload includes the core metrics:

```bash
rg -n "celery_task_executions_total|celery_task_duration_seconds|airbyte_sync_latency_seconds|airbyte_sync_rows_total|airbyte_sync_errors_total|dbt_run_duration_seconds" /tmp/metrics.txt
```

3. Confirm the content type is Prometheus text format:

```bash
curl -sI https://api.<env>.adinsights.com/metrics/app/ | rg -i "content-type: text/plain"
```

## Prometheus target validation

- In Prometheus UI: `Status -> Targets` should show the backend job as `UP`.
- If the target is `DOWN`, check the scrape error message and confirm network access, TLS certs, and path.
- Verify `scrape_interval` matches the desired resolution (default 30s or 60s).

## Troubleshooting

- **403/401**: The metrics endpoint should be accessible to the Prometheus network. Confirm ingress or auth settings.
- **404**: Ensure the backend route `/metrics/app/` is present in the deployed URL config.
- **Empty payload**: Verify workers have executed at least one Celery task or Airbyte/dbt sync. Metrics emit on activity.
- **High cardinality**: If label explosion occurs, review the label sets in `backend/core/metrics.py` and apply aggregation rules in your dashboards.

## Verification checklist

- `/metrics/app/` returns HTTP 200.
- Core metrics appear in the payload.
- Prometheus target is `UP` and recent samples are present.
- Dashboards reflect the new samples within two scrape intervals.

## See also

- `docs/runbooks/operations.md`
- `docs/ops/logging-standards.md`
