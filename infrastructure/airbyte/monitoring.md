# Airbyte Monitoring Cheat Sheet

Use these API endpoints to observe connector health from automation or dashboards. All paths are relative to the OSS server (`http://localhost:8001` in local compose).

## Connections
- `POST /api/v1/connections/get` – Provide the `connectionId` to retrieve the latest job status, schedule type, and sync catalog hash.
- `POST /api/v1/jobs/list` – Filter by `connectionId` to fetch the most recent sync attempts and failure reasons.
- `POST /api/v1/jobs/get` – Given a `jobId`, returns attempt-level metrics (records synced, bytes, total time).

## Sources & Destinations
- `POST /api/v1/sources/get` – Ensure the OAuth credentials are still valid and note the configured start date/lookback window.
- `POST /api/v1/destinations/get` – Confirm the target warehouse credentials.

## Health Checks
- `GET /api/v1/health` – Lightweight service probe confirming the server process is up.
- `GET /api/v1/openapi` – Returns the OpenAPI schema; availability implies routing through Temporal and the database is functioning.

## Observability Signals
- **Metrics:** Track sync latency, success rate, rows processed, and API cost units per connector. Compare against the SLAs in `AGENTS.md`.
- **Logs:** Emit structured JSON logs that include `tenant_id`, `task_id`, and `correlation_id`; never log secrets or plaintext OAuth tokens.
- **Alerts:** Page on two consecutive failures within the America/Jamaica business day, expiring secrets, or unexpectedly empty syncs.

## Alerting Tips
- Set up a cron to call `jobs/list` hourly; raise an alert if the latest attempt status is `failed` for more than one run in the America/Jamaica business day.
- Track job latency by comparing `createdAt` vs `updatedAt`; spikes often indicate API quota exhaustion.
- Record the `attempts[0].metrics` payload to surface sync volume trends alongside downstream dbt freshness dashboards.
