# Airbyte Failure Runbook

## Trigger
- Scheduled sync task failures, webhook errors, or unexpectedly empty syncs.

## Triage
- Confirm `AIRBYTE_API_URL` and `AIRBYTE_API_TOKEN` are set in the environment.
- Check the Airbyte connection health endpoint: `GET /api/airbyte/connections/health/`.
- Review backend logs for `airbyte`-prefixed entries and recent task failures.
- Inspect Airbyte container logs when running locally:
  - `docker compose logs airbyte-server`

## Recovery
- Re-run a specific sync:
  - `POST /api/airbyte/connections/{connection_id}/sync/`
- Or trigger due syncs from the CLI:
  - `python manage.py sync_airbyte`
- Confirm the tenant status record updates:
  - `TenantAirbyteSyncStatus` should reflect the latest job metadata.

## Escalation
- Escalate if:
  - Multiple consecutive failures for the same tenant/provider.
  - Empty syncs with no upstream changes for > 24 hours.
  - Credentials appear expired or revoked.
