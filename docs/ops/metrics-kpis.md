# Metrics & KPIs

This reference tracks the operational Key Performance Indicators (KPIs) that the ops team reviews during daily standups and incident postmortems. Each KPI is sourced from structured logs or CI telemetry to ensure it can be audited and trended over time.

## Pipeline reliability

- **Successful nightly syncs** — Count of Airbyte connections completing before 06:00 America/Jamaica. Target: ≥ 99% of nights per 30-day window.
- **dbt staging freshness** — Percentage of `stg_*` models whose `max_loaded_at` is less than 90 minutes old at 06:30. Target: ≥ 98%.
- **Alert closure latency** — Median minutes from PagerDuty trigger to incident resolution for data freshness alerts. Target: ≤ 45 minutes.

## CI health

- **Backend workflow pass rate** — Ratio of green runs to total runs on `main` for the Backend CI workflow. Target: ≥ 97%.
- **Frontend bundle verification** — Share of Frontend CI runs producing the `frontend-dist.zip` artifact without rebuild. Target: ≥ 95%.
- **dbt regression coverage** — Percentage of PRs touching `dbt/**` that attach the `dbt-staging-artifacts` bundle. Target: 100%.

## Cost and efficiency

- **Airbyte API unit consumption** — Rolling 7-day average of units consumed per tenant normalized by synced rows. Target: ≤ 1.2x baseline.
- **CI runtime** — Median duration of each workflow; goal is < 12 minutes backend, < 15 minutes frontend, < 10 minutes dbt.
- **Retry volume** — Weekly count of manual reruns triggered in GitHub Actions. Target: ≤ 5 with annotations explaining each retry.

## Customer impact

- **Dashboard freshness SLA adherence** — Percentage of customers whose dashboards show data < 6 hours old during business hours. Target: ≥ 99%.
- **Incident notifications sent** — Number of customer communications per quarter related to data freshness. Target: ≤ 2 (lower is better).
- **Support follow-ups** — Count of Zendesk tickets created from data latency issues. Target: 0 in any rolling 7-day window.
