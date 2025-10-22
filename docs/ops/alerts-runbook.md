# Nightly Sync Alerts Runbook

This guide documents how to respond when dashboards or alerts indicate that the nightly sync is stale or incomplete. The scope includes Airbyte ingestion jobs, downstream dbt models, and the health signals wired into the observability stack.

## When to engage this runbook

- PagerDuty or Slack alerts for "Nightly sync lagging" or "Stale staging metrics".
- Dashboard tiles missing the most recent date after 07:00 America/Jamaica.
- Airbyte job failure emails for Meta, Google Ads, or dimension refreshes.

## Immediate triage checklist

1. Acknowledge the alert in PagerDuty or Slack to let others know you are working the issue.
2. Confirm the reported timestamp versus the current time. The nightly pipeline should complete by 06:00, with alerts firing at 06:30 if no fresh rows arrive.
3. Review the latest deployments or configuration changes that may have landed since the last successful run.

## Step 0 — Check the nightly health workflow

1. Open the **Nightly Health** GitHub Actions workflow run that corresponds to the alert window.
2. Review the `Observability health summary` section in the run summary. It renders the rows from `observability-health.csv` so you can spot failing probes without downloading artifacts.
3. Download the `nightly-health-logs` artifact. The zip contains `observability-health.csv` at the root for spreadsheet import plus the `health-logs/` directory with per-attempt bodies, headers, and stderr captures.
4. If the workflow logs show HTTP errors (4xx/5xx) when calling health endpoints:
   - Validate the endpoint URL in `infrastructure/monitoring/health-checks.yml` and retry the request manually with `curl` to confirm reachability.
   - Coordinate with the owning service team if the API recently changed or requires maintenance mode.
5. If secrets are missing or access is denied, inspect the `Load secrets` step. Regenerate or re-authorize the secret in the secrets manager, then re-run the **Nightly Health** workflow.
6. When endpoint paths changed, update both the monitoring configuration and any reverse-proxy routing rules before re-running the workflow to collect a clean set of checks.

## Step 1 — Inspect Airbyte sync jobs

1. Open the Airbyte UI (`https://airbyte.example.internal`) and sign in with your platform account.
2. Navigate to **Connections → Paid Media → [source name] → Jobs**.
3. Filter to the failing stream (Meta, Google Ads, or Dimensions) and review the last two runs.
4. If the most recent job failed:
   - Download the logs and search for HTTP errors, rate limits, or authentication issues.
   - Re-run the sync manually using **Actions → Sync now** once the upstream issue is resolved.
   - If credentials expired, rotate them in the secrets manager and kick off another sync.
5. If the job succeeded but rows look stale, compare the **Records synced** metric with the historical baseline (visible in the Airbyte job detail sidebar). Sudden drops often indicate upstream API blanks or segment filters.

Document any remediation in the incident ticket, especially if you contacted the media platform owners.

## Step 2 — Verify dbt staging models

1. SSH into the analytics runner or use GitHub Actions re-run capabilities.
2. Execute `make dbt-deps && dbt --project-dir dbt run --select staging` from the repository root. This mirrors the CI workflow and rebuilds staging tables.
3. Check the dbt run output for warnings about missing sources or schema changes.
4. If dbt reports relation or permission errors, validate that the Postgres warehouse is reachable and that credentials match the values in `dbt/profiles.yml`.
5. For persistent failures, open a thread in `#adinsights-data` and attach the dbt log artifact.

## Step 3 — Refresh aggregates if needed

- If staging models succeed but dashboards are still stale, trigger a targeted rebuild: `dbt --project-dir dbt run --select tag:nightly`.
- Re-run the reporting jobs or API webhooks that consume the aggregates, if they are part of the automated schedule.
- Communicate the updated completion time to stakeholders once metrics are backfill complete.

## Contract validation

- When the dashboard API returns malformed aggregate payloads (missing campaign or parish keys), run `dbt test --project-dir dbt --select test_type:aggregate_snapshot_contract` to verify the warehouse side of the `/api/dashboards/aggregate-snapshot/` contract before escalating to the backend team.
- Compare responses against [`docs/project/api/aggregate_snapshot.schema.json`](../project/api/aggregate_snapshot.schema.json) to confirm the expected fields and naming conventions.
- Capture any contract regressions in the incident timeline so frontend engineers understand which keys or metrics were impacted.

## Escalation and follow-up

- Escalate to the on-call data engineer if:
  - Airbyte syncs fail twice consecutively after manual retries.
  - dbt encounters schema drift requiring model updates.
  - The incident spans more than one reporting cycle.
- Capture the root cause, mitigation steps, and duration in the incident record. Include log links, connector IDs, and impacted tenants.
- Schedule a retrospective if the issue was customer-facing or repeated within the last 30 days.
