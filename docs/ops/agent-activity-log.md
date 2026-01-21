# Agent Activity Log

One-line, timestamped notes of agent-driven changes to help preserve context between sessions. Newest entries at the top.

## 2026-01-20

- 2026-01-20T23:31:00-0500 docs(ops): add observability runbooks + log schema guidance — Added alert thresholds/escalation runbook, metrics scrape validation steps, observability stability tests checklist, and log schema/cardinality guidance; updated doc index and alerting runbook links. Pending commit.
- 2026-01-20T23:36:28-0500 docs(ops): add Stream 6 definition of done — Documented completion checklist for observability & alerts; linked from workstreams and doc index. Pending commit.
- 2026-01-20T23:38:36-0500 feat(backend): add required log fields to JSON formatter — Ensure component, tenant_id, correlation_id, and task_id are always present; added log schema test. Pending commit.

## 2026-01-21

- 2026-01-21T00:29:54-0500 chore(backend): align dev Airbyte/Prometheus host access — Added AIRBYTE_API_URL/TOKEN and host.docker.internal to ALLOWED_HOSTS in backend dev env to support local Airbyte health checks and Prometheus scraping. Pending commit.

## 2025-12-23

- 2025-12-23T13:55:33-0500 ci(deploy): add docker compose smoke workflow — Added `.github/workflows/deploy-smoke.yml` to validate deploy compose and smoke-check `/api/health/` + `/api/timezone/` in CI; commit 32fd468.
- 2025-12-23T13:55:33-0500 test(qa): assert tenant switch fixture fallback — Strengthened Playwright smoke to confirm tenant switching works using `/mock/tenants.json` + `/sample_metrics.json` when APIs are unavailable; commit 7b03433.
- 2025-12-23T13:55:33-0500 feat(dbt): add tenant_id to meta/google staging — Added `tenant_id` columns + schema tests for Airbyte-shaped staging models; ran `dbt run/test --select staging`; commit ef8b7da.

## 2025-10-21

- 2025-10-21T14:38:25Z chore(tasks): propagate tenant context in background jobs — Ensure Celery tasks set/clear tenant context; add tests; commit 9e97840.
- 2025-10-21T14:32:39Z chore(tasks): schedule weekly DEK rotation — Add `rotate-tenant-deks` Celery beat entry (Sun 01:30 America/Jamaica) and docs; commit 5b3e695.
- 2025-10-21T14:28:39Z feat(core): correlation IDs + configurable KMS — Add `X-Correlation-ID` middleware, logging filter, Celery task correlation; introduce `KMS_PROVIDER=local` for dev/tests and keep AWS provider for prod; tests added; commit 1ddf0e2.
- 2025-10-21T15:10:00Z docs(ops): add doc index + link component READMEs — Created `docs/ops/doc-index.md` with cold-start prompt, doc map, and hygiene rules; indexed backend/frontend/dbt/Airbyte/deploy/QA/exporter/BI READMEs for quick navigation. Pending commit.
- 2025-10-21T15:18:00Z docs(ops): add session warm-up note & surface index — Added `docs/PROGRAM-NOTES.md` (orientation quick start), linked it from `README.md`, and indexed in `docs/ops/doc-index.md`. Pending commit.
- 2025-10-22T02:35:00Z feat(backend): snapshot retry backoff logging — Snapshot task now uses BaseAdInsightsTask retry_with_backoff with structured logging; tests updated; commit 5d4903e.
- 2025-10-22T02:40:00Z feat(frontend): snapshot freshness tooltip + adapter reload fixes — Added absolute timestamp formatting/tooltips for snapshot indicators, refined dataset adapter reload per tenant, removed duplicate status roles; tests/lint/build passing; commits c30546a, 128ee33.
- 2025-10-22T13:42:00Z feat(dbt/docs): parameterize freshness SLA and document overrides — Tightened Meta/Google freshness to hourly SLA via vars (`freshness_warn_hours`/`freshness_error_hours`), added dev override note in operations runbook; dbt runs green except local freshness (stale seeds). Commit pending.

## 2025-10-17 (prior session summary)

- feat(analytics): export metrics CSV from warehouse (replaced fake adapter), tests updated; commit b82f7c2.
- fix(airbyte): normalise millisecond timestamps in telemetry; commit db07a91.
- fix(health): surface Airbyte sync_failed / pending states in `/api/health/airbyte/` + tests; commit c607e6a.
- chore(dbt): DuckDB dev harness runs marts with full-refresh to avoid merge strategy issues; commit 1373afe.
- chore/docs/ops: added harness docs, Airbyte runbook updates, and archived 200+ legacy `codex/*` branches (see `docs/ops/branch-archive-log.md`).

## Operational actions (no code delta)

- Pruned all remote legacy branches on origin to reduce notification noise; only `origin/main` remains.
- Deleted stray local branch `feat/frontend-admin-bootstrap` and refreshed local remotes (`git remote prune origin`).
