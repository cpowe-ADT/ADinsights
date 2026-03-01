# Program Notes (Orientation)

Use this as a quick-start reminder for cold sessions. For the full map and hygiene rules, see `docs/ops/doc-index.md`; for recent changes, check `docs/ops/agent-activity-log.md`.

## Quick Orientation

1. Skim in order: `AGENTS.md`, `README.md`, `docs/workstreams.md`, `docs/project/phase1-execution-backlog.md`, `docs/task_breakdown.md`, `docs/project/vertical_slice_plan.md`, `docs/security/uac-spec.md`, `docs/orchestration.md`, a relevant `docs/runbooks/*`, `docs/ops/agent-activity-log.md`, frontend design docs, deploy/BI docs.
2. Owners/streams: Airbyte (Maya/Leo), dbt (Priya/Martin), backend metrics (Sofia/Andre), frontend (Lina/Joel), secrets/KMS (Nina/Victor), observability (Omar/Hannah), BI/deploy (Carlos/Mei), cross-stream (Raj/Mira).
3. Tests per folder: backend `ruff check backend && pytest -q backend`; frontend `cd frontend && npm ci && npm test -- --run && npm run build`; dbt `make dbt-deps && ./scripts/dbt-wrapper.sh 'dbt' 'dbt' 'dbt' run --select staging && ./scripts/dbt-wrapper.sh 'dbt' 'dbt' 'dbt' snapshot && ./scripts/dbt-wrapper.sh 'dbt' 'dbt' 'dbt' run --select marts`; Airbyte `cd infrastructure/airbyte && docker compose config`.
4. Rules: one top-level folder per change unless Raj/Mira sign off; keep RLS/tenant isolation and secrets hygiene; required health endpoints stay; retries use exponential backoff (base 2, max 5, jitter); structured JSON logs with tenant_id/task_id/correlation_id; update runbooks/orchestration when behavior changes.
5. Doc hygiene: index new/updated docs in `docs/ops/doc-index.md` and log a one-liner in `docs/ops/agent-activity-log.md` with timestamp + summary + commit hash (if any). Add redirects when moving docs.
6. Planning: pull P1s from `docs/project/phase1-execution-backlog.md`, respect dependencies (1→2→3→4; 5–7 parallel), define scope/criteria/tests/observability/docs/reviewers before coding.
