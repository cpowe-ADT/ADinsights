# Vertical Slice Execution Plan for ADinsights

## Purpose
Deliver a working end-to-end analytics slice that ingests advertising data through Airbyte, models it with dbt, exposes it via the Django API, and visualizes it in the React frontend. This plan sequences the work to maximize learning, preserve tenant isolation, and keep the build green at each step.

## Guiding Principles
- **Iterative Milestones:** Complete and validate one subsystem at a time before layering the next to maintain a shippable state.
- **Tenant Safety & Secrets Hygiene:** Reuse the existing encryption and row-level security patterns; no credentials in logs or commits.
- **Test-First Cadence:** Run the canonical commands for each folder after changes, capture outputs, and fix regressions immediately.
- **Incremental PRs:** Scope work per top-level folder with conventional commit messages and short-lived branches.

## Phase 1 – Data Ingestion (Airbyte)
1. **Source Configuration**
   - Finalize declarative templates for Meta Ads and Google Ads with placeholder credentials.
   - Document required environment variables in `infrastructure/airbyte/README`.
2. **Connection & Sync Strategy**
   - Configure incremental syncs with lookback windows aligned to the `sync_*` schedules.
   - Validate transforms for currency micros and timezone normalization (America/Jamaica).
3. **Smoke Tests**
   - Run `docker compose config` to ensure manifests are syntactically valid.
   - Execute a dry-run sync against a sandbox to verify schema mapping.
4. **Outputs**
   - Committed configs (redacted), runbook entry, and log excerpts showing successful incremental sync.

## Phase 2 – Warehouse & Staging (dbt)
1. **Warehouse Targets**
   - Ensure Airbyte lands raw tables in the staging schema with tenant-safe naming.
   - Update dbt profiles to reference the warehouse credentials via environment variables.
2. **Model Extensions**
   - Build `stg_meta_ads__*` and `stg_google_ads__*` models covering metrics and dimensions required for dashboards.
   - Apply SCD2 snapshots for mutable dimensions using `dbt_valid_from`/`dbt_valid_to`.
3. **Testing & Docs**
   - Add schema tests for unique keys and non-null fields.
   - Generate dbt docs to confirm lineage.
4. **Commands**
   - `make dbt-deps`
   - `dbt --project-dir dbt run --select staging`
   - `dbt snapshot`
   - `dbt --project-dir dbt run --select marts`
5. **Outputs**
   - Updated models, tests, and docs; sample run logs with timings.

## Phase 3 – Backend API Integration
1. **Credential & Tenant CRUD**
   - Extend existing endpoints to onboard Airbyte credentials per tenant using encrypted fields.
   - Ensure Celery tasks set `tenant_id` before triggering syncs.
2. **Metrics Endpoints**
   - Implement DRF viewsets/serializers to surface aggregated metrics from dbt marts.
   - Include filters for date ranges, platforms, and geographic rollups.
3. **Health & Observability**
   - Wire health checks to report Airbyte sync status and dbt freshness.
   - Emit structured logs with `tenant_id`, `task_id`, `correlation_id`.
4. **Tests**
   - Expand pytest coverage for new endpoints, credential flows, and Celery orchestration.
   - Commands: `ruff check backend && pytest -q backend`.

## Phase 4 – Frontend Live Data
1. **API Client Wiring**
   - Replace mock data with calls to the new metrics endpoints; handle loading/error states.
   - Maintain TanStack Table controlled sorting and Leaflet choropleth safeguards.
2. **UI Validation**
   - Ensure tenant context is respected across views.
   - Update copy/labels to reflect live data.
3. **Tests & Build**
   - `cd frontend && npm ci && npm test -- --run && npm run build`.
   - Add unit tests for data hooks and components receiving live payloads.

## Phase 5 – Monitoring & Documentation
1. **Runbooks & Alerts**
   - Update runbooks with end-to-end flow, alert thresholds, and escalation paths.
   - Ensure observability dashboards cover task latency, success rate, and cost units.
2. **Operational Docs**
   - Record setup steps, environment variables, and smoke-test procedures in `docs/runbooks/`.
3. **Go/No-Go Checklist**
   - All canonical commands pass.
   - Sample tenant walkthrough documented with screenshots and metric validation.
4. **Warehouse Snapshots**
   - Automate `TenantMetricsSnapshot` generation via Celery + management command so
     `/api/metrics/combined/` always serves fresh warehouse data.

## Iterative Workflow Prompt for Codex
```
You are shipping a vertical slice of the ADinsights platform that moves advertising data from Airbyte through dbt into the Django API and React frontend. Work from the repo root and follow these phases sequentially, committing after each folder-scoped milestone.

1. Airbyte ingestion (infrastructure/airbyte/)
   - Finalize declarative source/connection configs with redacted placeholders.
   - Run `docker compose config` and capture output.
   - Dry-run a sandbox sync; record schema alignment notes.
   - Commit configs + docs (`chore(airbyte): finalize declarative sources`).
2. dbt modeling (dbt/)
   - Ensure raw tables land correctly, extend staging + marts, add schema tests.
   - Run `make dbt-deps`, `dbt run --select staging`, `dbt snapshot`, `dbt run --select marts`.
   - Attach run logs and model docs updates (`feat(dbt): add paid media staging models`).
3. Backend integration (backend/)
   - Wire tenant credential CRUD, Celery sync triggers, and aggregated metrics endpoints.
   - Maintain AES-GCM secret handling and tenant `SET app.tenant_id`.
   - Run `ruff check backend && pytest -q backend`; fix failures.
   - Commit with `feat(backend): expose paid media metrics`.
4. Frontend live dashboards (frontend/)
   - Replace mocks with API calls, preserve TanStack + Leaflet safety.
   - Run `npm ci`, `npm test -- --run`, `npm run build`.
   - Commit with `feat(frontend): consume live metrics slice`.
5. Monitoring & docs (docs/)
   - Update runbooks, alert thresholds, and go-live checklist.
   - Summarize smoke-test results and tenant walkthrough.
   - Commit with `docs(runbook): document vertical slice operations`.

After each phase, stop to summarize what changed, the exact commands run, and whether the suite is green before proceeding. Do not touch the next folder until the current phase is committed and passing.
```

## Success Criteria
- Functional, tenant-safe ingestion → modeling → API → UI path using redacted sample data.
- All canonical tests pass per folder.
- Runbooks updated with operations and monitoring expectations.
- Incremental commits with clear conventional messages and recorded command outputs.
