# Observability Alert Simulations (P1-X4)

Purpose: execute deterministic, safe staging simulations for required Phase 1 alert gates and capture evidence for release readiness.

Timezone: `America/Jamaica`.

## Execution Notes

1. Run simulations in staging only.
2. Keep one operator as trigger owner and one as observer.
3. Capture monitor IDs, timestamps, and notification route proof.
4. Revert test conditions immediately after each simulation.

## Scenario 1: Consecutive sync failures

- Trigger method:
  1. Pause or invalidate one staging source credential for a non-critical test tenant.
  2. Trigger sync attempts until consecutive failures threshold is crossed.
- Expected signal:
  - Airbyte/Celery telemetry shows repeated failed sync status with increasing attempt count.
- Expected alert route:
  - Slack `#adinsights-alerts` + configured email/pager target.
- Max detection time:
  - 10 minutes from threshold breach.
- Evidence artifact:
  - Failure run IDs, alert event screenshot/link, acknowledgment timestamp.

## Scenario 2: Unexpectedly empty sync

- Trigger method:
  1. Run sync for a tenant/date range known to have baseline data.
  2. Force query/filter conditions that return zero rows (staging test scope only).
- Expected signal:
  - Rows processed metric or payload indicates empty sync where non-empty baseline is expected.
- Expected alert route:
  - Slack + email warning channel for data quality alerts.
- Max detection time:
  - 15 minutes.
- Evidence artifact:
  - Baseline vs test row count snapshot + alert payload.

## Scenario 3: Stale `/api/health/airbyte/`

- Trigger method:
  1. Stop or pause Airbyte sync execution beyond freshness threshold in staging.
  2. Poll `/api/health/airbyte/` until stale state appears.
- Expected signal:
  - Health response transitions to stale/no-recent-sync state.
- Expected alert route:
  - Slack + pager (critical if stale exceeds critical threshold).
- Max detection time:
  - 10 minutes after stale threshold crossing.
- Evidence artifact:
  - Health endpoint response samples + monitor fire event.

## Scenario 4: Stale `/api/health/dbt/`

- Trigger method:
  1. Delay/disable scheduled dbt run in staging until stale threshold.
  2. Poll `/api/health/dbt/` and confirm stale/failing status.
- Expected signal:
  - dbt health endpoint indicates stale or failing latest run.
- Expected alert route:
  - Slack + email/pager per configured severity.
- Max detection time:
  - 15 minutes after stale threshold crossing.
- Evidence artifact:
  - Health payload + run metadata + alert event.

## Required fields in simulation evidence

1. Operator
2. Date/time (`America/Jamaica`)
3. Environment
4. Trigger steps executed
5. Raw outputs/screenshots
6. Pass/fail result
7. Follow-up ticket (if failed)

Use: `docs/project/evidence/phase1-closeout/external/templates/observability-simulation-template.md`.

External production actions must be tracked in `docs/runbooks/external-actions-aws.md`.
