# Orchestration Plan

This document defines the behavior-preserving Celery orchestration profile used by ADinsights in `America/Jamaica`.

## Source of truth

- Runtime and beat schedule config live in `backend/core/settings.py`.
- Queue routing uses `CELERY_TASK_ROUTES` and `CELERY_BEAT_SCHEDULE` without changing API response contracts.
- Tenant isolation remains enforced through the existing `tenant_context` + `SET app.tenant_id` flow in task execution paths.

## Queue classes

- `sync` queue: ingestion and provider sync workloads (`core.tasks.sync_*`, `integrations.tasks.sync_*`, `integrations.tasks.refresh_*`, parity checks, and scheduled Airbyte triggers).
- `snapshot` queue: metrics snapshot generation (`analytics.sync_metrics_snapshots`).
- `summary` queue: async summaries/exports (`analytics.ai_daily_summary`, `analytics.run_report_export_job`).
- `default` queue: fallback for tasks that are not explicitly routed.

## Local worker profile (`docker-compose.dev.yml`)

Development runs dedicated workers per queue class with conservative defaults:

- `celery_worker` (sync/default queues): `default,sync`, concurrency `4`
- `celery_worker_snapshot` (snapshot queue): `snapshot`, concurrency `2`
- `celery_worker_summary` (summary queue): `summary`, concurrency `1`

Each worker uses prefetch `1` and bounded task recycling (`--max-tasks-per-child`) to reduce long-lived worker drift.

Tune via `backend/.env.dev` / `backend/.env.sample`:

- Global task safety: `CELERY_TASK_ACKS_LATE`, `CELERY_TASK_REJECT_ON_WORKER_LOST`, `CELERY_TASK_TRACK_STARTED`
- Sync worker: `CELERY_WORKER_SYNC_QUEUES`, `CELERY_WORKER_SYNC_CONCURRENCY`, `CELERY_WORKER_SYNC_PREFETCH_MULTIPLIER`, `CELERY_WORKER_SYNC_MAX_TASKS_PER_CHILD`
- Snapshot worker: `CELERY_WORKER_SNAPSHOT_QUEUES`, `CELERY_WORKER_SNAPSHOT_CONCURRENCY`, `CELERY_WORKER_SNAPSHOT_PREFETCH_MULTIPLIER`, `CELERY_WORKER_SNAPSHOT_MAX_TASKS_PER_CHILD`
- Summary worker: `CELERY_WORKER_SUMMARY_QUEUES`, `CELERY_WORKER_SUMMARY_CONCURRENCY`, `CELERY_WORKER_SUMMARY_PREFETCH_MULTIPLIER`, `CELERY_WORKER_SUMMARY_MAX_TASKS_PER_CHILD`

## Schedule windows

- Hourly sync window: 06:00–22:00 (`airbyte-scheduled-syncs-hourly`, Meta and Google sync tasks).
- Daily dimension/maintenance window: 02:15+ (hierarchy and credential lifecycle tasks).
- Snapshot cadence: every 30 minutes (`metrics-snapshot-sync`).
- Daily summary cadence: 06:10 (`ai-daily-summary`).
- Weekly DEK rotation: Sundays 01:30 (`rotate-tenant-deks`).

## Validation and observability checks

- Validate compose rendering:
  - `docker compose -f docker-compose.dev.yml config`
- Validate backend checks after orchestration changes:
  - `ruff check backend && pytest -q backend`
- Verify health and metrics endpoints:
  - `curl -fsS http://localhost:8000/api/health/`
  - `curl -fsS http://localhost:8000/api/health/airbyte/`
  - `curl -fsS http://localhost:8000/api/health/dbt/`
  - `curl -fsS http://localhost:8000/api/timezone/`
  - `curl -fsS http://localhost:8000/metrics/app/ | rg 'celery_task_executions_total|celery_task_duration_seconds|airbyte_sync_latency_seconds|dbt_run_duration_seconds'`
- Run release-readiness smoke command (strict observability profile):
  - `python3 backend/manage.py backend_release_smoke --strict-observability`
