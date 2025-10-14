# Airbyte Monitoring & Runbook

Use these API endpoints to observe connector health from automation or dashboards. All paths are relative to the OSS server (`$AIRBYTE_BASE_URL`, default `http://localhost:8001` in local compose).

> **Configuration validation:** Render the cleaned compose file with `docker compose config` after copying `env.example` to `.env` so you can confirm the sample environment resolves before starting services.

## Quick status checks

- `python3 infrastructure/airbyte/scripts/airbyte_health_check.py` – emits a JSON summary of every connection and exits non-zero when a job is stale or failing. Requires `AIRBYTE_WORKSPACE_ID` and respects `AIRBYTE_BASE_URL` plus optional auth header.

## Automated alerts

Leverage the bundled health probe and GitHub Actions template to fail fast when syncs drift outside their SLA.

```bash
# Local run example
export AIRBYTE_BASE_URL=http://localhost:8001
export AIRBYTE_WORKSPACE_ID="$(jq -r '.workspaceId' infrastructure/airbyte/env.example)"
python3 infrastructure/airbyte/scripts/airbyte_health_check.py
```

- Copy `infrastructure/airbyte/github-action-airbyte-healthcheck.yaml` to `.github/workflows/airbyte-healthcheck.yaml`.
- Populate repository secrets `AIRBYTE_BASE_URL`, `AIRBYTE_WORKSPACE_ID`, and `AIRBYTE_API_AUTH_HEADER` (if needed) so the workflow has network access to the deployment.
- The workflow emits the script output as job logs and fails the run when a connection is stale (>1.5× its scheduled interval) or the latest job failed.
- Combine with GitHub branch protection or external alert routing (e.g., Slack, OpsGenie) to notify the on-call rotation when scheduled runs fail.

## Quick runbook

Check for stale jobs and trigger on-call responses with the commands below (replace placeholders with real IDs):

```bash
# List all connections and grab the UUID for the pipeline you care about
curl -s "$AIRBYTE_BASE_URL/api/v1/connections/list" -H 'content-type: application/json' -d '{"workspaceId": "00000000-0000-0000-0000-000000000000"}' | jq '.connections[] | {name, connectionId, scheduleType}'

# Fetch the latest sync metadata for a connection
curl -s "$AIRBYTE_BASE_URL/api/v1/connections/get" -H 'content-type: application/json' -d '{"connectionId": "<CONNECTION_ID>"}' | jq '{name: .name, schedule: .scheduleData, latestJobCreatedAt: .latestSyncJobCreatedAt}'

# Inspect the most recent job result to distinguish "stale" from "failing"
curl -s "$AIRBYTE_BASE_URL/api/v1/jobs/list" -H 'content-type: application/json' -d '{"configTypes": ["sync"], "configId": "<CONNECTION_ID>", "pagination": {"pageSize": 1}}' | jq '.jobs[0] | {jobId, status, createdAt, updatedAt, attempts: [.attempts[] | {status, failureReason: .failureSummary?.failureReason}]}'
```

- **Healthy:** `status` is `succeeded` and `updatedAt` is within the expected schedule window.
- **Stale:** `status` is `succeeded` but `updatedAt` is older than the cron cadence → investigate scheduler drift or paused jobs.
- **Failing:** `status` is `failed` and `attempts[0].failureReason` is populated → capture the error text and create/attach to the incident ticket.

## Connections

- `POST /api/v1/connections/get` – Provide the `connectionId` to retrieve the latest job status, schedule type, and sync catalog hash.
- `POST /api/v1/jobs/list` – Filter by `connectionId` to fetch the most recent sync attempts and failure reasons.
- `POST /api/v1/jobs/get` – Given a `jobId`, returns attempt-level metrics (records synced, bytes, total time).

List all connections and their current schedule/state:

```bash
curl -s \
  -X POST "$AIRBYTE_BASE_URL/api/v1/connections/list" \
  -H 'Content-Type: application/json' \
  -d '{
        "workspaceId": "'"${AIRBYTE_WORKSPACE_ID}"'"
      }' | jq '.connections[] | {name: .name, connectionId: .connectionId, status: .status, scheduleType: .scheduleType}'
```

Grab an individual connection's high-level summary:

```bash
payload=$(jq -n --arg connectionId "$CONNECTION_ID" '{connectionId: $connectionId}')
curl -s \
  -X POST "$AIRBYTE_BASE_URL/api/v1/connections/get" \
  -H 'Content-Type: application/json' \
  -d "$payload"
```

## Last job outcome

Fetch the latest sync attempts for a connection:

```bash
payload=$(jq -n --arg connectionId "$CONNECTION_ID" '{configType: "sync", connectionId: $connectionId, pagination: {pageSize: 1}}')
curl -s \
  -X POST "$AIRBYTE_BASE_URL/api/v1/jobs/list" \
  -H 'Content-Type: application/json' \
  -d "$payload" | jq '.jobs[0] | {jobId: .job.id, status: .job.status, startedAt: .job.createdAt, updatedAt: .job.updatedAt}'
```

Inspect a specific job for records processed and error context:

```bash
payload=$(jq -n --argjson id "$JOB_ID" '{id: $id}')
curl -s \
  -X POST "$AIRBYTE_BASE_URL/api/v1/jobs/get" \
  -H 'Content-Type: application/json' \
  -d "$payload" | jq '.job.attempts[0].metrics'
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
