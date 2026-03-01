# Phase 0 – Simulated Workstream Reviews (2025-01-05)

Each section below captures the Phase 0 backlog validation outcome for the
corresponding workstream using the persona prompt from
`docs/project/phase0-backlog-validation.md`. Format: Status, Gaps, Actions,
Dependencies.

## 1. Airbyte Ingestion & Telemetry (Maya, backup Leo)

- **Status** – KPIs/DoD remain accurate. Base Celery task still lacks tenant
  context guarantees and telemetry endpoint is not recording per-tenant metrics.
- **Gaps**
  - No ticket yet for tenant-aware `BaseAdInsightsTask` that propagates tracing
    IDs to Airbyte syncs.
  - Telemetry API missing pagination + auth tests; OpenAPI docs outdated.
  - Lacks integration test covering webhook signature validation + retry path.
- **Actions**
  1. Maya: Spec & implement tenant-aware base task + metrics emitters
     (`backend/integrations`/`backend/core/tasks.py`) – ETA 2025-01-12.
  2. Leo: Add telemetry API contract tests + OpenAPI refresh – ETA 2025-01-10.
  3. Maya: Author webhook runbook + rotate signing secret sample in `.env.sample`
     – ETA 2025-01-11.
- **Dependencies**
  - Coordinate with Priya (dbt) before altering raw table schema; Raj to
    co-review if schema migration required.
  - Observability hooks need Omar to expose new metrics dashboards.

## 2. dbt Modeling & Warehouse Views (Priya, backup Martin)

- **Status** – KPIs valid; backlog covers mart build but not tenant isolation nor
  freshness alerting.
- **Gaps**
  - Missing ticket for auditing tenant filters in staging models (row-level
    enforcement).
  - Freshness alerts not wired to monitoring; no action items logged.
  - Need documentation updates for any new columns consumed by
    `/api/metrics/combined/`.
- **Actions**
  1. Priya: Create task to add tenant_id filters + schema tests for raw/stg
     models – ETA 2025-01-13.
  2. Martin: Implement dbt source freshness alert integration + runbook
     appendix – ETA 2025-01-15.
  3. Priya: Maintain change log for metrics columns, syncing with Sofia/Lina –
     ongoing, reviewed weekly.
- **Dependencies**
  - Requires Airbyte raw schemas (stream 1). Raj to coordinate release order.
  - Alerting pieces depend on Omar/Hannah once metrics defined.

## 3. Backend Metrics & Snapshots (Sofia, backup Andre)

- **Status** – KPIs still relevant; backlog partially covers snapshot success but
  not secrets isolation or regression tests.
- **Gaps**
  - Need ticket to ensure `snapshot_generated_at` is timezone-aware and exposed
    in serializers/tests.
  - No automated test for stale snapshot alert (<1% SLA).
  - Celery task lacks retry with jitter; tenant context not enforced.
- **Actions**
  1. Sofia: Patch serializers + API tests for `snapshot_generated_at` +
     timezone handling – ETA 2025-01-09.
  2. Andre: Add Celery retry/backoff + observability hooks; coordinate with Leo –
     ETA 2025-01-12.
  3. Sofia: Write stale snapshot monitoring spec for Omar – ETA 2025-01-10.
- **Dependencies**
  - Must wait for dbt marts (stream 2) before releasing schema changes.
  - Cross-stream PR touching Celery + analytics needs Raj + Mira review.

## 4. Frontend Experience (Lina, backup Joel)

- **Status** – KPIs accurate. Backlog has design system work but lacks tasks for
  new snapshot banner + tenant switch integration tests.
- **Gaps**
  - No ticket aligning dataset toggle with backend dataset naming contract.
  - Missing Cypress/Playwright smoke covering tenant switch + API fallback.
  - Storybook/docs not tracking freshness banner states.
- **Actions**
  1. Lina: Implement snapshot freshness banner + QA notes – ETA 2025-01-17.
  2. Joel: Add Playwright smoke test + update CI config – ETA 2025-01-18.
  3. Lina: Update design-system plan & Storybook entries for dataset toggle
     behavior – ETA 2025-01-16.
- **Dependencies**
  - Requires backend metrics endpoint final schema; Sofia to provide contract.
  - Needs Raj sign-off if frontend touches shared dataset contract docs.

## 5. Secrets & KMS (Nina, backup Victor)

- **Status** – KPIs stand; backlog missing DEK rotation automation + failure
  drills.
- **Gaps**
  - No scripted rotation workflow or CI smoke for encryption helpers.
  - `.env.sample` lacks placeholders for new KMS credentials.
  - Missing runbook for KMS outage handling.
- **Actions**
  1. Nina: Build rotation CLI + unit tests in `scripts/rotate_deks.py` – ETA
     2025-01-11.
  2. Victor: Update `.env.sample`, docs, and add detect-secrets rule – ETA
     2025-01-10.
  3. Nina: Draft outage runbook and alert thresholds with Omar – ETA
     2025-01-12.
- **Dependencies**
  - Observability (Omar) for alert routing.
  - Cross-stream review only if crypto helpers touched by other folders (Raj to
    confirm).

## 6. Observability & Alerts (Omar, backup Hannah)

- **Status** – KPIs valid; backlog includes log normalization but not full
  metrics coverage or alert escalation matrix.
- **Gaps**
  - No task for exposing Celery/dbt latency metrics under `/metrics/app/`.
  - Alert thresholds + escalation owners undocumented.
  - Missing structured logging test to assert tenant/task correlation IDs.
- **Actions**
  1. Omar: Implement metrics emitters + `/metrics/app/` smoke test – ETA
     2025-01-13.
  2. Hannah: Document alert thresholds + pager escalation and link dashboards –
     ETA 2025-01-14.
  3. Omar: Add structured logging unit test + log schema doc – ETA 2025-01-12.
- **Dependencies**
  - Needs hooks from streams 1–5; Raj to ensure instrumentation PRs get
    co-review.
  - Coordinates with Carlos/Mei to surface metrics in deployment dashboards.

## 7. BI & Deployment (Carlos, backup Mei)

- **Status** – KPIs accurate; backlog lacks reproducible Superset configs and
  deployment smoke automation.
- **Gaps**
  - No version-controlled BI dashboards or seed data for CI.
  - Docker compose smoke test not wired into CI.
  - Deployment runbook missing rollback + health verification steps.
- **Actions**
  1. Carlos: Export Superset/Metabase configs to `docs/BI/` with redacted creds –
     ETA 2025-01-15.
  2. Mei: Add `docker compose config` + smoke job to CI, document results – ETA
     2025-01-12.
  3. Carlos: Expand deployment runbook with rollback + health checklist – ETA
     2025-01-16.
- **Dependencies**
  - Requires stable backend/dbt schemas; coordinate release notes with Sofia &
    Priya.
  - Cross-stream involvement minimal unless docker compose spans frontend +
    backend simultaneously (Raj to review if multi-folder PR).
