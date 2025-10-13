# Orchestration Plan

This document outlines how ADinsights keeps paid media data synchronized and models refreshed. The approach assumes a containerized deployment (e.g., ECS/Kubernetes) but is portable to any scheduler that can run Docker images.

## Airbyte Syncs (Hourly)

- **Scheduler**: Celery beat (preferred) or a cron entry that runs the Django management command below.
- **Bootstrap**:
  1. Export the environment variables listed in the root README so Airbyte source templates resolve secrets (`AIRBYTE_*`).
  2. Insert `integrations.AirbyteConnection` rows per tenant via Django admin or the shell:
     ```python
     from integrations.models import AirbyteConnection
     AirbyteConnection.objects.create(
         tenant=<tenant>,
         name="Meta Incremental",
         connection_id="<airbyte-connection-uuid>",
         schedule_type=AirbyteConnection.SCHEDULE_INTERVAL,
         interval_minutes=60,
     )
     ```
  3. Configure `AIRBYTE_API_URL` and `AIRBYTE_API_TOKEN` (or username/password) so the backend can authenticate with Airbyte.
- **Command**:
  ```bash
  python manage.py sync_airbyte
  ```
  The command calls the Airbyte API for each due connection, triggers a sync job, and persists the `last_synced_at`, job ID, and status on the `AirbyteConnection` record for observability.
- **Cadence**: For hourly feeds schedule the command at `5 * * * *` to start after the hour. Lower-frequency connections can use cron expressions or longer intervals in their respective model rows.
- **Backfill strategy**: Each incremental stream keeps a 30-day lookback window via the configured start date cursors. Airbyte's state management ensures only new slices are processed.
- **Monitoring**: Ship job events to CloudWatch/Stackdriver and configure alerts for repeated failures or API quota errors. The `AirbyteConnection` table acts as the source of truth for the last successful attempt per tenant.

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
