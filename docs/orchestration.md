# Orchestration Plan

This document outlines how ADinsights keeps paid media data synchronized and models refreshed. The approach assumes a containerized deployment (e.g., ECS/Kubernetes) but is portable to any scheduler that can run Docker images.

## Airbyte Syncs (Hourly)

- **Scheduler**: `cron` entry on the orchestration host or a Celery beat schedule that triggers the Airbyte API.
- **Cadence**: Every hour on the half hour to avoid top-of-the-hour API contention.
- **Command**:
  ```bash
  0 * * * * curl -X POST "$AIRBYTE_API_URL/api/v1/jobs/runs" \
      -H "Content-Type: application/json" \
      -d '{"connectionId": "<UUID>", "jobType": "sync"}'
  ```
- **Backfill strategy**: Each incremental stream keeps a 30-day lookback window via the configured start date cursors. Airbyte's state management ensures only new slices are processed.
- **Monitoring**: Ship job events to CloudWatch/Stackdriver and configure alerts for repeated failures or API quota errors.

## dbt Transformations (Nightly)

- **Scheduler**: Celery beat task that queues a `dbt run` worker each night at 02:00 local time (07:00 UTC) when API activity is low.
- **Task payload**:
  ```python
  app.conf.beat_schedule = {
      "dbt-nightly": {
          "task": "orchestration.run_dbt",
          "schedule": crontab(hour=2, minute=0),
          "args": (["seed", "run", "test"],),
      }
  }
  ```
- **Worker implementation**: `orchestration.run_dbt` spins up a container with the analytics warehouse credentials and runs `dbt deps && dbt seed && dbt run --select state:modified+ && dbt test`.
- **Dependencies**: The dbt task waits for the latest Airbyte sync job to finish (polling the Airbyte API). If sync failures occur, it raises a retry and alerts the data team.

## Metadata & Logging

- Persist Airbyte job metadata to a warehouse table for observability.
- Log Celery task outcomes and durations for historical SLA reporting.
- Use a shared notification channel (Slack/MS Teams) for both sync and transformation alerts.

## Future Enhancements

- Replace cron with a managed scheduler (e.g., MWAA, Dagster, or Prefect) once workloads grow.
- Add data quality gates (dbt expectations, Great Expectations) to block downstream dashboards when anomalies occur.
- Integrate auto-retries with exponential backoff for quota/timeout errors.
