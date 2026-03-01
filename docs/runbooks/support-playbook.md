# Support Playbook (v0.1)

Purpose: quick triage steps for common issues.

## 1) User cannot see data

- Check tenant selection and RLS context.
- Verify `/api/metrics/combined/` returns data for tenant.
- Confirm latest snapshot timestamp.
- If stale: trigger snapshot task and inspect Celery logs.

## 2) Airbyte sync failed

- Check Airbyte health endpoint and last sync status.
- Verify credentials and lookback windows.
- Re-run sync or trigger `sync_airbyte` task.
- For local dev, confirm port profile alignment:
  - Airbyte API `http://localhost:18001`
  - Airbyte UI `http://localhost:18000`
  - Backend `AIRBYTE_API_URL=http://host.docker.internal:18001`
- If Airbyte API is down after restart, inspect bootloader and schema:
  - `docker logs airbyte-bootloader`
  - `docker exec airbyte-db psql -U airbyte -d airbyte -c '\dt'`
- If DB has no relations (`Did not find any relations`) or server logs include missing `airbyte_metadata`, migrations did not run.
  - Fix compose bootloader ordering, then `docker compose down && docker compose up -d` for `infrastructure/airbyte`.
- Port collision symptoms (bind error / connection refused) require freeing ports or updating all related env vars together.
- If Airbyte jobs fail with `FileNotFoundError: source_config.json`, worker/container mount wiring is broken.
  - Verify worker env uses `WORKSPACE_DOCKER_MOUNT=airbyte-workspace` and `LOCAL_DOCKER_MOUNT=airbyte-local`.
  - Recreate worker: `cd infrastructure/airbyte && docker compose --env-file .env rm -sf worker && docker compose --env-file .env up -d worker`.

## 3) Map is blank

- Confirm parish aggregates and GeoJSON availability.
- Check map metric selection and data ranges.
- Inspect frontend console for fetch errors.

## 4) Export issues

- Verify exporter service is reachable.
- Check credentials/permissions and output storage.
- Retry with smaller date range.

## 5) Social connector status checker

- Endpoint: `GET /api/integrations/social/status/`.
- `not_connected`: user can click `Connect with Facebook` directly on the social card; this should immediately trigger Meta OAuth.
- `started_not_complete`: continue setup (page/ad account/Instagram selection and provisioning defaults).
- `complete`: setup exists but sync is not active/fresh; trigger manual sync and confirm connection `is_active=true`.
- `active`: no action required; if user still reports no data, inspect downstream ingestion/models.
- If OAuth start fails from social card CTA: Data Sources opens the Meta setup panel and surfaces the backend error (for example missing `META_APP_ID`, redirect URI config, or app secret).
- If OAuth start fails with `META_LOGIN_CONFIG_ID` missing: set `META_LOGIN_CONFIG_ID` and confirm `META_LOGIN_CONFIG_REQUIRED` matches environment policy.
- If OAuth exchange fails with token validation errors: verify `META_APP_ID`/`META_APP_SECRET` are from the same Meta app used for login.
- If OAuth connects but permissions are missing: use the Data Sources `Re-request permissions` action, then repeat page/ad account selection.

Escalation: log incident in ops channel and reference `docs/ops/risk-register.md`.
