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

## 3) Map is blank
- Confirm parish aggregates and GeoJSON availability.
- Check map metric selection and data ranges.
- Inspect frontend console for fetch errors.

## 4) Export issues
- Verify exporter service is reachable.
- Check credentials/permissions and output storage.
- Retry with smaller date range.

Escalation: log incident in ops channel and reference `docs/ops/risk-register.md`.
