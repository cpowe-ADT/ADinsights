# Airbyte Monitoring & Runbook

Use these API endpoints to observe connector health from automation or dashboards. All paths are relative to the OSS server (`http://localhost:8001` in local compose).

## Quick status checks

List all connections and their current schedule/state:

```bash
curl -s \
  -X POST http://localhost:8001/api/v1/connections/list \
  -H 'Content-Type: application/json' \
  -d '{
        "workspaceId": "REPLACE_WITH_WORKSPACE_ID"
      }' | jq '.connections[] | {name: .name, connectionId: .connectionId, status: .status, scheduleType: .scheduleType}'
```

Grab an individual connection's high-level summary:

```bash
curl -s \
  -X POST http://localhost:8001/api/v1/connections/get \
  -H 'Content-Type: application/json' \
  -d '{
        "connectionId": "REPLACE_WITH_CONNECTION_ID"
      }'
```

## Last job outcome

Fetch the latest sync attempts for a connection:

```bash
curl -s \
  -X POST http://localhost:8001/api/v1/jobs/list \
  -H 'Content-Type: application/json' \
  -d '{
        "configType": "sync",
        "connectionId": "REPLACE_WITH_CONNECTION_ID",
        "pagination": { "pageSize": 1 }
      }' | jq '.jobs[0] | {jobId: .job.id, status: .job.status, startedAt: .job.createdAt, updatedAt: .job.updatedAt}'
```

Inspect a specific job for records processed and error context:

```bash
curl -s \
  -X POST http://localhost:8001/api/v1/jobs/get \
  -H 'Content-Type: application/json' \
  -d '{
        "id": REPLACE_WITH_JOB_ID
      }' | jq '.job.attempts[0].metrics'
```

A healthy incremental sync should show `recordsEmitted` increasing over time, with `totalTimeInSeconds` staying within the SLA window (≤1800 seconds for hourly metrics).

## Stale vs failing

- **Failing:** The latest job's `status` is `failed`. Page immediately if two consecutive jobs fail between 06:00 and 22:00 America/Jamaica.
- **Stale:** The latest successful job `updatedAt` timestamp is older than the expected cadence (e.g., >90 minutes for hourly metrics or >26 hours for daily dimensions) even though no failure is reported. Investigate upstream auth/quota issues or stuck jobs in Temporal.

Correlate the timestamps returned by `jobs/list` with dbt freshness dashboards to confirm whether downstream models are catching up.

## Health checks

- `GET /api/v1/health` – Lightweight service probe confirming the server process is up.
- `GET /api/v1/openapi` – Returns the OpenAPI schema; availability implies routing through Temporal and the database is functioning.

## Observability signals

- **Metrics:** Track sync latency, success rate, rows processed, and API cost units per connector. Compare against the SLAs in `AGENTS.md`.
- **Logs:** Emit structured JSON logs that include `tenant_id`, `task_id`, and `correlation_id`; never log secrets or plaintext OAuth tokens.
- **Alerts:** Page on two consecutive failures within the America/Jamaica business day, expiring secrets, or unexpectedly empty syncs.
