# Orchestration Plan

This document defines the behavior-preserving Celery orchestration profile used by ADinsights in `America/Jamaica`.

## Source of truth

- Runtime and beat schedule config live in `backend/core/settings.py`.
- Queue routing uses `CELERY_TASK_ROUTES` and `CELERY_BEAT_SCHEDULE` without changing API response contracts.
- Tenant isolation remains enforced through the existing `tenant_context` + `SET app.tenant_id` flow in task execution paths.

## Queue classes

- `sync` queue: ingestion and provider sync workloads (`core.tasks.sync_*`, `integrations.tasks.sync_*`, `integrations.tasks.refresh_*`, `content_ops.tasks.*`, parity checks, and scheduled Airbyte triggers).
- `snapshot` queue: metrics snapshot generation (`analytics.sync_metrics_snapshots`).
- `summary` queue: async summaries/exports (`analytics.ai_daily_summary`, `analytics.run_report_export_job`).
- `default` queue: fallback for tasks that are not explicitly routed.

## Local worker profile (`docker-compose.dev.yml`)

Development runs dedicated workers per queue class with conservative defaults:

- `celery_worker` (sync/default queues): `default,sync`, concurrency `4`
- `celery_worker_snapshot` (snapshot queue): `snapshot`, concurrency `2`
- `celery_worker_summary` (summary queue): `summary`, concurrency `1`

Each worker uses prefetch `1` and bounded task recycling (`--max-tasks-per-child`) to reduce long-lived worker drift.
The backend image includes the Node report exporter and native Chromium used by the summary
worker for PDF/PNG exports. `backend` and `celery_worker_summary` mount the same
`report_export_artifacts` volume so an export is downloadable only after the worker's non-empty
artifact is visible to the API process.
The backend and all task workers also mount `prometheus_multiprocess` and set
`PROMETHEUS_MULTIPROC_DIR`; this lets `/metrics/app/` aggregate samples emitted inside worker
processes. Task publishing stamps `published_at` so queue-wait histograms represent real broker
latency, and the common task lifecycle records one completion outcome per executed task.

Tune via `backend/.env.dev` / `backend/.env.sample`:

- Global task safety: `CELERY_TASK_ACKS_LATE`, `CELERY_TASK_REJECT_ON_WORKER_LOST`, `CELERY_TASK_TRACK_STARTED`
- Sync worker: `CELERY_WORKER_SYNC_QUEUES`, `CELERY_WORKER_SYNC_CONCURRENCY`, `CELERY_WORKER_SYNC_PREFETCH_MULTIPLIER`, `CELERY_WORKER_SYNC_MAX_TASKS_PER_CHILD`
- Snapshot worker: `CELERY_WORKER_SNAPSHOT_QUEUES`, `CELERY_WORKER_SNAPSHOT_CONCURRENCY`, `CELERY_WORKER_SNAPSHOT_PREFETCH_MULTIPLIER`, `CELERY_WORKER_SNAPSHOT_MAX_TASKS_PER_CHILD`
- Summary worker: `CELERY_WORKER_SUMMARY_QUEUES`, `CELERY_WORKER_SUMMARY_CONCURRENCY`, `CELERY_WORKER_SUMMARY_PREFETCH_MULTIPLIER`, `CELERY_WORKER_SUMMARY_MAX_TASKS_PER_CHILD`

## Schedule windows

- Hourly sync window: 06:00–22:00 (`airbyte-scheduled-syncs-hourly`, Meta and Google sync tasks).
- Content Ops publishing scans: every minute (`content-publish-due-scan`,
  `content-publish-retry-scan`, and `content-publish-process-scan`) on the `sync` queue. The
  processor advances due queued attempts and due Instagram container-pending/ready attempts through
  disabled-by-default/fakeable provider boundaries unless provider adapters and permission evidence
  are explicitly activated.
- Content Ops organic metric refresh: hourly at minute 35 from 06:00-22:00
  (`content-organic-metrics-refresh`) on the `sync` queue. It bridges already-synced Meta post
  insight rows into aggregate-only Content Ops metric snapshots.
- Daily dimension/maintenance window: 02:15+ (hierarchy and credential lifecycle tasks).
- Snapshot cadence: every 30 minutes (`metrics-snapshot-sync`).
- Daily summary cadence: 06:10 (`ai-daily-summary`); generated aggregate summaries are delivered
  to each tenant's active email notification channels. A repeated attempt for the same already
  delivered snapshot records its state without issuing a duplicate email.
- Weekly DEK rotation: Sundays 01:30 (`rotate-tenant-deks`).

## Validation and observability checks

- Validate compose rendering:
  - `docker compose -f docker-compose.dev.yml config`
- After launching the local profile, request generic CSV/PDF/PNG exports in `/reports` and verify
  each completed job downloads successfully through the API.
- Validate backend checks after orchestration changes:
  - `ruff check backend && pytest -q backend`
- Verify health and metrics endpoints:
  - `curl -fsS http://localhost:8000/api/health/`
  - `curl -fsS http://localhost:8000/api/health/airbyte/`
  - `curl -fsS http://localhost:8000/api/health/dbt/`
  - `curl -fsS http://localhost:8000/api/timezone/`
  - `curl -fsS http://localhost:8000/metrics/app/ | rg 'celery_task_executions_total|celery_task_duration_seconds|airbyte_sync_latency_seconds|dbt_run_duration_seconds'`
- Run deterministic release preflight for local/staging preparation:
  - `backend/.venv/bin/python backend/manage.py backend_release_preflight`
- After live workers have emitted queue metrics, capture strict observability evidence:
  - `python3 backend/manage.py backend_release_smoke --strict-observability`
  - This requires real `sync`, `snapshot`, `summary`, combined-metrics, Airbyte, dbt, and retry
    samples to have occurred in the observed runtime.
