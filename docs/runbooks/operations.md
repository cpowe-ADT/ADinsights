# Operations Runbook

This runbook documents how to operate the ADinsights stack across the frontend, backend, BI, and scheduled services.
External production actions must be tracked in `docs/runbooks/external-actions-aws.md`.

## Environments

- **Local development** – developers run the stack via `docker compose up` (see `deploy/docker-compose.yml`).
- **Staging** – nightly refreshes of warehouse replicas and Superset metadata.
- **Production** – 15 minute refresh cadence, Superset in high-availability mode, alerts integrated with Slack and email.

## Health Checks

| Component             | Check                                                        | Command                                                                                                                                                                            |
| --------------------- | ------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Frontend              | Vite build + smoke test                                      | `npm run build` (from `frontend/`)                                                                                                                                                 |
| Backend               | Django API health endpoint                                   | `curl https://api.<env>.adinsights.com/api/health/`                                                                                                                                |
| Airbyte Orchestration | API health endpoint + status payload                         | `curl https://api.<env>.adinsights.com/api/health/airbyte/`                                                                                                                        |
| dbt Orchestration     | API health endpoint (exposes latest run results)             | `curl https://api.<env>.adinsights.com/api/health/dbt/`                                                                                                                            |
| Sync health aggregate | Tenant connection state rollup                               | `curl https://api.<env>.adinsights.com/api/ops/sync-health/`                                                                                                                       |
| Health overview       | Consolidated service health cards                            | `curl https://api.<env>.adinsights.com/api/ops/health-overview/`                                                                                                                   |
| Connector lifecycle   | Meta OAuth + page/ad account connect + provision/sync/logout | `curl https://api.<env>.adinsights.com/api/integrations/meta/setup/`, `POST .../meta/oauth/start/`, `POST .../meta/provision/`, `POST .../meta/sync/`, and `POST .../meta/logout/` |
| Social status checker | Platform-level social onboarding/sync status                 | `curl https://api.<env>.adinsights.com/api/integrations/social/status/`                                                                                                            |
| Web analytics (GA4)   | GA4 pilot rows                                               | `curl https://api.<env>.adinsights.com/api/analytics/web/ga4/`                                                                                                                     |
| Web analytics (GSC)   | Search Console pilot rows                                    | `curl https://api.<env>.adinsights.com/api/analytics/web/search-console/`                                                                                                          |
| Superset              | `/health` endpoint                                           | `curl https://bi.<env>.adinsights.com/health`                                                                                                                                      |
| Scheduler             | APScheduler heartbeat logs                                   | Check `scheduler` container logs for `Scheduler started`                                                                                                                           |
| dbt Freshness         | dbt source freshness check                                   | `make dbt-freshness` (local) or scheduler job output                                                                                                                               |
| Data contracts        | Cross-stream contract gate                                   | `python3 infrastructure/airbyte/scripts/check_data_contracts.py`                                                                                                                   |

The Airbyte health endpoint surfaces the most recent sync metadata per tenant and flags jobs that
are older than one hour. The dbt health endpoint reads the most recent `run_results.json` and marks
the service as stale when no run has completed within the past 24 hours. Both responses return
machine-friendly JSON payloads for dashboards or alerting rules.

For per-tenant investigation, use `GET /api/airbyte/telemetry/`. The response includes
`sync_status_state` (`missing`, `fresh`, `stale`) and `sync_status_age_minutes` to confirm whether
the latest sync is outside the freshness window. If no recent sync exists, trigger a manual refresh
with `python manage.py sync_airbyte` (or run the Celery task
`integrations.tasks.trigger_scheduled_airbyte_syncs`) and re-check the telemetry endpoint.
For Post-MVP operations pages, validate `/api/ops/sync-health/` and
`/api/ops/health-overview/` during the same incident window so frontend and backend status signals stay aligned.

For social onboarding, use `GET /api/integrations/social/status/` and verify each platform status:

- `not_connected`: no credential onboarded.
- `started_not_complete`: onboarding started but missing assets/provision defaults.
- `complete`: assets connected but not currently active/fresh.
- `active`: connected and recently synced.

## Meta Marketing API direct-sync operations

Use this section for the direct PostgreSQL-backed `/api/meta/*` contract.

For Facebook Page Insights + Page Post Insights ingestion and dashboard operations, use:

- `docs/runbooks/meta-page-insights-operations.md`

### Scheduled jobs (`America/Jamaica`)

- `integrations.tasks.refresh_meta_tokens` hourly from `06:00` to `22:00`
- `integrations.tasks.sync_meta_accounts` hourly from `06:00` to `22:00`
- `integrations.tasks.sync_meta_insights_incremental` hourly from `06:00` to `22:00`
- `integrations.tasks.sync_meta_hierarchy` daily at `02:15`

### Direct read APIs

- `GET /api/meta/accounts/`
- `GET /api/meta/campaigns/?account_id=<act_id>`
- `GET /api/meta/adsets/?campaign_id=<campaign_id>`
- `GET /api/meta/ads/?adset_id=<adset_id>`
- `GET /api/meta/insights/?account_id=<act_id>&level=ad&since=<YYYY-MM-DD>&until=<YYYY-MM-DD>`

### Failure modes and operator actions

1. Token expired/invalid
   - Signal: `PlatformCredential.token_status in (invalid, reauth_required)` or `/api/integrations/social/status/` reason `credential_reauth_required`.
   - Action: trigger reconnect via `/api/integrations/meta/oauth/start/` and complete page/ad-account connect; verify token via Meta Access Token Debugger.
2. Missing scopes
   - Signal: OAuth exchange/page connect returns `missing_required_permissions` (gate is `(ads_read OR ads_management)` + `business_management` + `pages_read_engagement` + `pages_show_list`).
   - Action: restart OAuth with `auth_type=rerequest` and confirm required scopes are granted before provisioning/sync.
3. Ad account access denied
   - Signal: `integrations_apierrorlog` row for provider `META` with account endpoint failures (403-like upstream errors), `MetaAccountSyncState.last_job_status=failed`.
   - Action: verify user/test-user has access to the selected ad account in Business Manager, then rerun `sync_meta_accounts` and `sync_meta_hierarchy`.
4. Rate limited (429 / transient)
   - Signal: `integrations_apierrorlog.is_retryable=true`, elevated retry logs from `meta.graph.retry`.
   - Action: allow bounded retries (base-2 exponential, max 5 attempts with jitter) to complete; if sustained, temporarily reduce manual sync frequency and retry in next hourly window.

Validation evidence for staging/test-app runs should be stored at:

- `docs/project/evidence/meta-validation/<timestamp>.md`
- Template: `docs/project/evidence/meta-validation/_TEMPLATE.md`

Meta OAuth configuration requirements for browser-redirect flow:

- `META_APP_ID`
- `META_APP_SECRET`
- `META_LOGIN_CONFIG_ID` (required when `META_LOGIN_CONFIG_REQUIRED=1`)
- `META_OAUTH_REDIRECT_URI` (or `FRONTEND_BASE_URL` fallback)
- `META_OAUTH_SCOPES` must include required ad-data permissions for provisioning.

### Local Airbyte runtime recovery (DockerHub `0.50.22` profile)

Use this flow when local Meta provisioning/sync fails because Airbyte is unreachable or not initialized.

1. Confirm local profile and ports:
   - Airbyte API: `http://localhost:18001`
   - Airbyte UI: `http://localhost:18000`
   - Backend container env: `AIRBYTE_API_URL=http://host.docker.internal:18001`
2. Render compose config:
   - `cd infrastructure/airbyte && docker compose --env-file .env config`
3. Restart Airbyte services:
   - `cd infrastructure/airbyte && docker compose --env-file .env down`
   - `cd infrastructure/airbyte && docker compose --env-file .env up -d`
4. Validate bootloader migrations:
   - `docker logs airbyte-bootloader`
   - Expected: migration completes and container exits with status `0`.
5. Validate schema exists:
   - `docker exec airbyte-db psql -U airbyte -d airbyte -c '\dt'`
   - If output is `Did not find any relations`, migrations did not run.
6. Validate API health:
   - `curl -sS http://localhost:18001/api/v1/health`

Known failure modes:

- Port collision: startup fails or health endpoint is unreachable. Free conflicting ports or update `.env` and backend `AIRBYTE_API_URL` consistently.
- Empty Airbyte DB schema (`airbyte_metadata` missing): `airbyte-server` crashes with relation-not-found errors. Ensure `airbyte-bootloader` runs successfully before `server`/`worker`, then recreate the Airbyte stack.
- Connector runtime cannot find `source_config.json`: Airbyte jobs fail with `FileNotFoundError` from the source container. Ensure worker mount wiring is volume-name based (`WORKSPACE_DOCKER_MOUNT=airbyte-workspace`, `LOCAL_DOCKER_MOUNT=airbyte-local`) and recreate `airbyte-worker`.

## Deployments

1. Merge changes to `main` with green CI.
2. Tag release (`git tag -a vX.Y.Z -m "Release vX.Y.Z"`).
3. Trigger the `deploy-full-stack` GitHub Actions workflow or run `deploy/deploy_full_stack.sh`.
4. Monitor rollout via Datadog dashboards and Superset status page.

## API Edge Controls (Production)

### CORS policy

- Keep `CORS_ALLOW_ALL_ORIGINS=0` in production.
- Configure explicit origins through `CORS_ALLOWED_ORIGINS` (comma-separated full origins).
- Verify preflight behavior from approved and unapproved origins:
  - Approved origin should receive `Access-Control-Allow-Origin`.
  - Unapproved origin should not receive CORS headers and preflight should be rejected.

### Auth/Public throttles

- Rate limits are controlled by:
  - `DRF_THROTTLE_AUTH_BURST` (short window)
  - `DRF_THROTTLE_AUTH_SUSTAINED` (long window)
  - `DRF_THROTTLE_PUBLIC` (public endpoint budget)
- Smoke check by issuing repeated requests to:
  - `POST /api/token/`
  - `POST /api/auth/login/`
  - `POST /api/auth/password-reset/`
- Expect HTTP `429` once thresholds are exceeded.

## Incident Response

1. Acknowledge alert in Slack (#adinsights-alerts).
2. Review Superset dashboards referenced in alert payloads.
3. Use `/alerts/run` endpoint to re-trigger evaluation after remediation.
4. Document root cause analysis in the incident ticket.

## Audit Logging

- **What is logged** – The backend persists `AuditLog` rows for every user
  authentication, platform credential create/update/delete, role assignment
  change, and manual sync trigger. Operators can review entries via the
  `/api/audit-logs/` endpoint (filterable by `action` or `resource_type`).
- **Storage** – Audit events live in the primary Postgres database under the
  `accounts_auditlog` table. Each row is tenant-scoped to prevent cross-tenant
  access.
- **Retention** – Maintain at least 365 days of audit history to satisfy common
  compliance requirements. Configure a nightly database task (e.g. cron job or
  managed retention policy) that deletes records older than the retention
  window: `DELETE FROM accounts_auditlog WHERE created_at < NOW() - INTERVAL '365
days';` Adjust the interval to meet contractual obligations.
- **Export/Archival** – For deployments that require longer retention, ship
  daily exports of the table to object storage (S3/GCS) before running the
  deletion query. Ensure exported files inherit the environment's encryption
  and access controls.

## Observability & Alerting

- **Structured logging** – API and Celery workloads emit JSON logs (`api.access`,
  `celery.tasks`) that include duration, tenant identifiers, and task metadata. Ingest
  these streams into your log platform with at least 30 days of retention for incident
  reconstruction.
- **Metrics baselines** – Treat an Airbyte sync as healthy when the freshest job is
  < 60 minutes old and has a `succeeded` status. dbt pipelines are healthy when the
  latest run completed successfully within 24 hours and all models report `success`
  or `skipped` in the run results payload.
- **Alerting targets** – Configure alerts when API request error rate exceeds 2% over
  5 minutes, Airbyte health responds `stale`/`no_recent_sync`, or dbt health responds
  `stale`/`failing`. Set SLA expectations at 99.5% API availability, Airbyte sync freshness
  under 60 minutes, and dbt transformations under 24 hours. Use `/metrics/app/` → `dbt_run_duration_seconds`
  to watch for regressions in dbt runtime, and `make dbt-freshness`/scheduled freshness jobs to confirm
  source recency. Hourly metrics feeds (Meta/Google) should warn after 2 hours and error after 4 hours
  of staleness; dashboards should alert if `/api/health/dbt/` reports stale/failing or if freshness checks breach.
  For dev/CI with seeds, override dbt vars `freshness_warn_hours`/`freshness_error_hours` to avoid false positives.
- **Dashboards** – Plot `/api/health/airbyte/` and `/api/health/dbt/` responses alongside
  Celery task durations to visualize orchestration performance trends and catch regressions
  before they breach SLAs.
- **Simulation runbook** – Execute `docs/runbooks/observability-alert-simulations.md` in staging before release gates are marked complete.

## Stale Snapshot Monitoring Spec

Use this spec to define when `/api/metrics/combined/` snapshots are considered stale and
what signals should trigger alerts.

### Definition

- **Snapshot scope** – A snapshot is the cached payload returned by
  `/api/metrics/combined/?source=warehouse`.
- **Freshness timestamp** – `snapshot_generated_at` (ISO-8601 string).
- **Default freshness window** – 60 minutes in America/Jamaica (aligns with dbt freshness).

### Alert thresholds

- **Warning** – Snapshot age > 60 minutes.
- **Critical** – Snapshot age > 120 minutes or `snapshot_generated_at` missing.
- **Suppression** – Allow a 15-minute grace window after dbt completes to avoid false alarms.

### Signals to monitor

- **API sampling** – Poll `/api/metrics/combined/?source=warehouse` per tenant and record
  `snapshot_generated_at`.
- **Task telemetry** – `analytics.sync_metrics_snapshots` task duration, success rate, and
  rows processed (structured logs should include `tenant_id`, `task_id`, `correlation_id`).
- **Upstream health** – `/api/health/airbyte/` and `/api/health/dbt/` staleness flags.

### Expected behavior

- Filtered requests (`start_date`, `end_date`, `parish`) bypass cache and must not update the
  snapshot timestamp.
- A manual refresh (`python manage.py snapshot_metrics --tenant-id <UUID>`) should update
  `snapshot_generated_at` within one run cycle.
- Empty payloads are acceptable but should still contain a timestamp.

### Escalation

- Page Data Engineering if stale snapshots persist after one manual refresh attempt or if
  > 20% of tenants report stale snapshots in a single monitoring interval.
- Page Platform if API sampling fails or `/api/metrics/combined/` returns non-200 status codes.

## Airbyte Webhook Operations

Airbyte emits job-completion webhooks to `/api/airbyte/webhook/` so the platform can persist
latency/records metadata immediately after a sync. Keep the following guardrails in place:

- **Authentication** – Every request must include the header `X-Airbyte-Webhook-Secret`. The backend
  compares the header to `AIRBYTE_WEBHOOK_SECRET` (see `backend/core/settings.py`). Missing or wrong
  secrets return `403` without touching tenant data. When onboarding a new environment, place the
  shared secret in the secret manager AND in Airbyte’s destination settings so they match. If
  `AIRBYTE_WEBHOOK_SECRET_REQUIRED=1` but the variable is unset, the endpoint returns `503` and logs
  `Airbyte webhook secret required but not configured`—deploys must set a value before enabling syncs.
- **Rotation** – Rotate the secret quarterly or after any suspected exposure:
  1. Generate a new 32+ character value (e.g., `openssl rand -hex 32`).
  2. Update the environment’s secret store / `AIRBYTE_WEBHOOK_SECRET` variable.
  3. Update the Airbyte Cloud/OSS webhook configuration.
  4. Deploy the backend; confirm `/api/airbyte/webhook/` rejects the previous secret and accepts the new one.
  5. Record the rotation in the on-call log. The placeholder in `backend/.env.sample` must stay redacted.
- **Replay / Troubleshooting**
  - Use the Airbyte UI → Connections → Job History to re-send the webhook payload (copy as cURL and include the header).
  - Watch `backend` logs for `Airbyte webhook processed` messages; they include `tenant_id`, `connection_id`, and `job_id`.
  - If a webhook repeatedly fails with `404 connection not found`, ensure the connection ID matches the UUID stored in ADinsights (Admins can list via `/api/integrations/airbyte/connections/`).
  - For 500s, capture the payload and raise an incident; malformed JSON should be retried from Airbyte after the fix.
- **Monitoring**
  - Alerts are triggered when `airbyte_job_webhook` audit events stop arriving for >30 minutes while Airbyte jobs exist.
  - Grafana dashboard “Airbyte Webhook Health” tracks webhook count, success rate, and median latency between sync completion and webhook ingestion.
  - Structured logs always include `correlation_id` matching the Celery task when the webhook links to a scheduled sync.
- **Disaster Recovery** – If webhooks are down, scheduled syncs still run via Celery; metrics will be delayed until
  the webhook endpoint accepts payloads again. Use `manage.py sync_airbyte --tenant` to backfill and then replay the
  missed webhooks from Airbyte so telemetry stays accurate.

## Secrets Rotation CLI

- Use `python scripts/rotate_deks.py --dry-run` to see how many tenant keys would be touched.
- Rotate a single tenant with `python scripts/rotate_deks.py --tenant-id <tenant_uuid>` or all tenants by omitting the flag.
- The CLI initialises Django automatically; run it from the repo root after exporting production credentials or pointing
  `DJANGO_SETTINGS_MODULE` at the correct settings module.
- Celery beat already schedules `core.tasks.rotate_deks` weekly. Use the CLI for emergency rotations or to verify a
  rotation completed after a KMS incident.

## Data Refresh Failures

- Validate warehouse connectors via Superset → Data → Databases.
- Re-run `dbt` transformation job via the scheduler container (`make run-dbt`).
- Escalate to Data Engineering if source pipelines show latency over 60 minutes.

## SES Readiness Checklist (adtelligent.net)

Complete these steps before enabling `EMAIL_PROVIDER=ses` in production:

1. Verify SES identity for `adtelligent.net` (domain identity).
2. Enable Easy DKIM and confirm all CNAME records are in `verified` state.
3. Confirm SPF and DMARC records align with SES sending path.
4. Move SES account out of sandbox for required recipient scope.
5. Set final sender address:
   - `EMAIL_FROM_ADDRESS=<approved-address>@adtelligent.net`
   - `SES_EXPECTED_FROM_DOMAIN=adtelligent.net`
6. Optional: set `SES_CONFIGURATION_SET` for delivery metrics/alerts.
7. Run smoke tests:
   - Invite flow: `POST /api/users/invite/` then accept link delivery check.
   - Password reset flow: `POST /api/auth/password-reset/` delivery check.
8. Record timestamp, operator, and from-address confirmation in release notes.

## Tenant Safety Checklist

Run this checklist before every release that touches the backend or ingestion
surface area.

1. **Settings guardrail** – `ENABLE_TENANCY` defaults to `True` in
   `backend/core/settings.py` and the environment override is present in the
   deployment manifests.
2. **HTTP traversal** – Hit `/api/analytics/campaigns/` and
   `/api/airbyte/telemetry/` with two test tenants; confirm responses contain
   only the authenticated tenant’s data (see `backend/tests/test_analytics_endpoints.py`).
3. **Warehouse adapter** – Verify `WarehouseAdapter.fetch_metrics` returns the
   correct tenant snapshot and does not leak other tenants’ payloads (also
   covered by tests).
4. **Background tasks** – Ensure Celery workers run with the latest code so
   `tenant_context(...)` is applied; spot check logs for missing `tenant_id`
   fields.
5. **Audit trail** – Confirm new endpoints/actions emit `log_audit_event(...)`
   with the current tenant and that `/api/audit-logs/` returns scoped results.

## Snapshot Lag Troubleshooting

1. **Inspect freshness** – Call `/api/metrics/combined/?source=warehouse` for
   an affected tenant. The payload now returns `snapshot_generated_at`. Treat
   any value older than the dbt SLA (60 minutes by default) as stale.
2. **Manual refresh** – Run `python manage.py snapshot_metrics --tenant-id <UUID>`
   to refresh a single tenant, or omit `--tenant-id` to rebuild every snapshot.
   The Celery task `analytics.sync_metrics_snapshots` is also available via
   Flower or `celery control broadcast run-task`.
3. **Beat schedule** – Ensure the `metrics-snapshot-sync` entry in
   `CELERY_BEAT_SCHEDULE` is enabled (30-minute cadence). Worker logs should
   include `metrics.snapshot.persisted` for each tenant.
4. **Connector sync schedule** – Ensure `airbyte-scheduled-syncs-hourly` is enabled
   (`integrations.tasks.trigger_scheduled_airbyte_syncs`, hour `06:00-22:00` America/Jamaica).
   This drives Meta/Google connection syncs when each tenant connection is due.
5. **Alerts** – Configure monitoring to fire when
   `snapshot_generated_at` is older than 60 minutes or missing entirely.
   Pair this with the Airbyte/dbt health checks to pinpoint upstream causes.
6. **Dashboards** – The “Warehouse Snapshot Health” Grafana/Superset view plots
   snapshot recency per tenant. Use it to verify manual refreshes before
   closing an incident.

## Performance Review + Cache Verification

Use this checklist when reviewing `/api/metrics/combined/` performance or after
changes to snapshot logic.

### Performance checklist

1. **Latency** – Compare p95 `/api/metrics/combined/` response time for cached
   vs uncached requests; cached responses should be materially faster.
2. **Snapshot task duration** – Confirm `analytics.sync_metrics_snapshots`
   duration trends are stable and within expected SLA.
3. **Row volumes** – Review `row_totals` emitted by the snapshot task logs for
   unexpected spikes that could affect response times.
4. **Error rate** – Ensure API error rate remains <2% over 5 minutes following
   the deployment.

### Cache verification

1. **Warm cache** – Call `/api/metrics/combined/?source=warehouse` twice and
   confirm the second response matches cached payload (no adapter hit).
2. **Bypass behavior** – Call `/api/metrics/combined/?cache=false` and confirm
   the payload refreshes and `snapshot_generated_at` changes.
3. **Filtered requests** – Call `/api/metrics/combined/?parish=Kingston` and
   confirm the response does not update the stored snapshot (timestamp should
   remain unchanged for the unfiltered cache).

## Contact

- Marketing Operations On-Call: `marketing-ops@example.com`
- Data Engineering: `data-eng@example.com`
- Platform Engineering: `platform-eng@example.com`
