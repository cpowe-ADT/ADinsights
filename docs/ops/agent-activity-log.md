# Agent Activity Log

One-line, timestamped notes of agent-driven changes to help preserve context between sessions. Newest entries at the top.

## 2025-10-21

- 2025-10-21T14:38:25Z chore(tasks): propagate tenant context in background jobs — Ensure Celery tasks set/clear tenant context; add tests; commit 9e97840.
- 2025-10-21T14:32:39Z chore(tasks): schedule weekly DEK rotation — Add `rotate-tenant-deks` Celery beat entry (Sun 01:30 America/Jamaica) and docs; commit 5b3e695.
- 2025-10-21T14:28:39Z feat(core): correlation IDs + configurable KMS — Add `X-Correlation-ID` middleware, logging filter, Celery task correlation; introduce `KMS_PROVIDER=local` for dev/tests and keep AWS provider for prod; tests added; commit 1ddf0e2.

## 2025-10-17 (prior session summary)

- feat(analytics): export metrics CSV from warehouse (replaced fake adapter), tests updated; commit b82f7c2.
- fix(airbyte): normalise millisecond timestamps in telemetry; commit db07a91.
- fix(health): surface Airbyte sync_failed / pending states in `/api/health/airbyte/` + tests; commit c607e6a.
- chore(dbt): DuckDB dev harness runs marts with full-refresh to avoid merge strategy issues; commit 1373afe.
- chore/docs/ops: added harness docs, Airbyte runbook updates, and archived 200+ legacy `codex/*` branches (see `docs/ops/branch-archive-log.md`).

## Operational actions (no code delta)

- Pruned all remote legacy branches on origin to reduce notification noise; only `origin/main` remains.
- Deleted stray local branch `feat/frontend-admin-bootstrap` and refreshed local remotes (`git remote prune origin`).
