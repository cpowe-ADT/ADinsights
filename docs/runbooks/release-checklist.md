# Release Checklist (v0.1)

Use this before merging to main or deploying to staging/production.
External production actions must be tracked in `docs/runbooks/external-actions-aws.md`.

## Pre-merge (feature branch)
- [ ] Work scoped to a single top-level folder per `docs/workstreams.md`.
- [ ] Relevant tests run and green (see stream-specific commands).
- [ ] Data-contract gate passes: `python3 infrastructure/airbyte/scripts/check_data_contracts.py`.
- [ ] Observability prereq gate passes: `python3 infrastructure/airbyte/scripts/verify_observability_prereqs.py`.
- [ ] Any API contract changes recorded in `docs/project/api-contract-changelog.md`.
- [ ] Runbooks updated for behavior changes.
- [ ] Design system docs updated for UI changes.

## Staging Readiness
- [ ] `docker compose config` (Airbyte/deploy) renders clean.
- [ ] Backend health endpoints return 200:
  - `/api/health/`, `/api/health/airbyte/`, `/api/health/dbt/`, `/api/timezone/`
- [ ] Post-MVP ops endpoints return 200 with expected payload shape:
  - `/api/ops/sync-health/`, `/api/ops/health-overview/`
- [ ] Connector lifecycle endpoints return expected status and sync behavior:
  - `GET /api/integrations/google_ads/status/`
  - `GET /api/integrations/ga4/status/`
  - `GET /api/integrations/search_console/status/`
  - `GET /api/integrations/{provider}/jobs/`
  - `POST /api/integrations/{provider}/sync/` returns `200`/`202`
  - `POST /api/integrations/{provider}/reconnect/` returns OAuth authorize URL
  - `POST /api/integrations/{provider}/disconnect/` pauses connection and removes credentials
- [ ] Snapshot freshness within SLA for demo tenant.
- [ ] Frontend loads with `VITE_MOCK_MODE=false` and renders live data.
- [ ] Frontend Post-MVP routes render with live API responses:
  - `/reports`, `/alerts`, `/summaries`, `/ops/audit`

## Production Readiness
- [ ] Secrets/KMS rotation verified (no logs leak secrets).
- [ ] SES sender identity verified and password reset/invite emails deliver successfully.
- [ ] Observability dashboards + alerts configured and tested.
- [ ] Observability simulation checklist completed in staging: `docs/runbooks/observability-alert-simulations.md`.
- [ ] dbt runs green (staging + marts + tests).
- [ ] Airbyte syncs verified for Meta + Google sources.
- [ ] GA4 and Search Console pilot sources validated in target environment (or explicitly feature-flagged off with rollback note).
- [ ] CORS allowlist configured with explicit origins (`CORS_ALLOWED_ORIGINS`); wildcard origins disabled in production.
- [ ] DRF auth/public throttles configured (`DRF_THROTTLE_AUTH_BURST`, `DRF_THROTTLE_AUTH_SUSTAINED`, `DRF_THROTTLE_PUBLIC`) and smoke-tested for `429` behavior.
- [ ] `python3 infrastructure/airbyte/scripts/validate_tenant_config.py` succeeds in target env.
- [ ] `python3 infrastructure/airbyte/scripts/verify_production_readiness.py` reports no errors.
- [ ] `python3 infrastructure/airbyte/scripts/airbyte_health_check.py` reports healthy connections for Meta + Google.
- [ ] SES readiness checklist complete: identity + DKIM + SPF/DMARC + sandbox exit + final from-address match.
- [ ] Rollback steps reviewed in `docs/runbooks/deployment.md`.

## Post-deploy
- [ ] Smoke test: login, invite acceptance, password reset, tenant switch, campaign dashboard, map.
- [ ] Error budget check (no spike in 5xx/timeout).
- [ ] Update `docs/ops/agent-activity-log.md`.
