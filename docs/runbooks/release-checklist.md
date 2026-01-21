# Release Checklist (v0.1)

Use this before merging to main or deploying to staging/production.

## Pre-merge (feature branch)
- [ ] Work scoped to a single top-level folder per `docs/workstreams.md`.
- [ ] Relevant tests run and green (see stream-specific commands).
- [ ] Any API contract changes recorded in `docs/project/api-contract-changelog.md`.
- [ ] Runbooks updated for behavior changes.
- [ ] Design system docs updated for UI changes.

## Staging Readiness
- [ ] `docker compose config` (Airbyte/deploy) renders clean.
- [ ] Backend health endpoints return 200:
  - `/api/health/`, `/api/health/airbyte/`, `/api/health/dbt/`, `/api/timezone/`
- [ ] Snapshot freshness within SLA for demo tenant.
- [ ] Frontend loads with `VITE_MOCK_MODE=false` and renders live data.

## Production Readiness
- [ ] Secrets/KMS rotation verified (no logs leak secrets).
- [ ] Observability dashboards + alerts configured and tested.
- [ ] dbt runs green (staging + marts + tests).
- [ ] Airbyte syncs verified for Meta + Google sources.
- [ ] Rollback steps reviewed in `docs/runbooks/deployment.md`.

## Post-deploy
- [ ] Smoke test: login, tenant switch, campaign dashboard, map.
- [ ] Error budget check (no spike in 5xx/timeout).
- [ ] Update `docs/ops/agent-activity-log.md`.
