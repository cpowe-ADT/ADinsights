# Workstream Coding Guides

This note captures the coding scope and day-to-day instructions for each active
workstream so engineers can pick up a track independently without blocking
others. Every track maps to a single top-level folder per AGENTS.md so PRs stay
isolated.

## 1. Airbyte Ingestion & Telemetry (`backend/integrations/`, `backend/core/tasks.py`)
- **Owner / Effort** – Primary: Maya (Integrations); Backup: Leo (Celery). Effort: Medium.
- **Success criteria / KPIs**
  - CRUD + schedule APIs deployed with OpenAPI docs updated.
  - Celery sync tasks emit success/failure metrics (<1% failure rate weekly).
  - Ops can see latest sync per tenant in `/api/airbyte/telemetry/`.
- **Dependencies**
  - Execute before dbt modeling (stream #2) relies on stable raw tables.
  - Coordinate with backend metrics (stream #3) if payload structure changes.
- **Coding standards / Testing / Contracts**
  - Commands: `ruff check backend`, `pytest backend/tests/test_airbyte_*.py`.
  - Use `black` formatting for touched files; keep `/api/airbyte/telemetry/` schema intact.
  - Webhook secrets/edge cases documented in PR (missing signature, retries).
  - Traceability: `docs/task_breakdown.md` §2.1–2.3, `docs/orchestration.md`.
- **Definition of Done**
  - Code limited to integrations + core tasks; Celery wiring uses `tenant_context`.
  - Tests + docs updated (`docs/runbooks/operations.md`).
  - Observability (metrics/logs) confirmed.
  - PR reviewed by Maya/Leo.
  - Cross-stream sync: weekly touchpoint with dbt lead for schema changes.

## 2. dbt Modeling & Warehouse Views (`dbt/`)
- **Owner / Effort** – Primary: Priya; Backup: Martin. Effort: Large.
- **Success criteria / KPIs**
  - Staging + mart models pass `dbt test` (no warnings).
  - Freshness SLA (<60m) monitored via dbt sources.
  - dbt docs/exposures updated with new fields.
- **Dependencies**
  - Blocks frontend/backend updates that depend on new aggregates (streams #3 & #4).
- **Coding standards / Testing / Contracts**
  - Commands: `make dbt-deps`, `dbt run --select staging`, `dbt snapshot`, `dbt run --select marts`, `dbt test`.
  - Follow dbt style guide (macros documented, `yml` schema tests).
  - Keep columns consumed by `/api/metrics/combined/` stable; note breaking changes in PR.
  - References: `docs/task_breakdown.md` §3, `docs/project/vertical_slice_plan.md` Phase 2.
- **Definition of Done**
  - Code scoped to `dbt/**`; exposures + docs updated.
  - Artifacts attached (dbt docs, run logs).
  - Cross-stream sync with backend metrics + frontend if new fields added.

## 3. Backend Metrics + Snapshots (`backend/analytics/`, `backend/adapters/`)
- **Owner / Effort** – Primary: Sofia; Backup: Andre. Effort: Medium.
- **Success criteria / KPIs**
  - `/api/metrics/combined/` responds with `snapshot_generated_at`.
  - Snapshot task ≥99% success; stale snapshots <1%.
  - Ops runbook updated with troubleshooting.
- **Dependencies**
  - Requires latest dbt marts (stream #2) before adapter changes release.
  - Coordinate with frontend (stream #4) when payload format adjusts.
- **Coding standards / Testing / Contracts**
  - Commands: `ruff check backend`, `pytest backend/tests/test_metrics_api.py backend/tests/test_snapshot_task.py backend/tests/test_analytics_endpoints.py`.
  - Document schemas for `/api/metrics/**`; mention backwards-compat constraints.
  - When touching Celery, ensure `tenant_context` used and `core.metrics.observe_task`.
  - References: `docs/task_breakdown.md` §6.1, `docs/project/vertical_slice_plan.md` Phase 5.
- **Definition of Done**
  - Code scoped to analytics/adapters.
  - Tests + docs updated; observability verified.
  - Cross-stream sync: notify frontend when endpoints change.

## 4. Frontend Experience (`frontend/src/`)
- **Owner / Effort** – Primary: Lina; Backup: Joel. Effort: Large.
- **Success criteria / KPIs**
  - Dashboard defaults to warehouse data; demo mode opt-in.
  - Snapshot freshness banner matches backend timestamp.
  - Design system docs updated when components change.
  - Finished frontend spec adopted (`docs/project/frontend-finished-product-spec.md`) with MVP
    page-level empty/stale states implemented.
  - Post-MVP and Enterprise slices tracked with clear API dependencies and acceptance checks.
- **Dependencies**
  - Requires backend API contracts from streams #1 & #3.
  - Post-MVP and Enterprise work depends on Airbyte connection APIs, reporting/alerts endpoints, and
    UAC workflow endpoints.
- **Coding standards / Testing / Contracts**
  - Commands: `npm run lint`, `npm test -- --run`, `npm run build`.
  - Run Prettier; ensure TypeScript strictness passes.
  - Validate `/api/metrics/combined/` schema integration; update `src/lib/apiClient` types.
  - References: `docs/design-system.md`, `docs/task_breakdown.md` §5,
    `docs/project/frontend-finished-product-spec.md`.
- **Definition of Done**
  - Code limited to `frontend/src/**`; Storybook/UX docs updated.
  - Tests (unit + integration) green.
  - Finished frontend spec reviewed by Lina (senior web dev) and Joel, with any gaps logged.
  - Cross-stream sync with backend metrics for payload shifts.

## 5. Secrets & KMS (`backend/core/crypto/`, `scripts/`)
- **Owner / Effort** – Primary: Nina; Backup: Victor. Effort: Medium.
- **Success criteria / KPIs**
  - Production KMS client functional; rotation command documented.
  - No secrets leak in logs; `.env.sample` synced.
- **Dependencies**
  - Independent; coordinate with observability if logging changes.
- **Coding standards / Testing / Contracts**
  - Commands: `ruff check backend`, `pytest backend/tests/test_dek_manager.py`.
  - Document failover edge cases (KMS unreachable, rotation errors).
  - Update `README`/`.env` for new vars.
- **Definition of Done**
  - Code scoped to crypto/scrips; docs updated.
  - Observability hooks show rotation success/failure.
  - Cross-stream sync: notify ops if rotation schedule changes.

## 6. Observability & Alerts (`backend/core/observability.py`, `docs/runbooks/`)
- **Owner / Effort** – Primary: Omar; Backup: Hannah. Effort: Medium.
- **Success criteria / KPIs**
  - Structured logs capture tenant/task IDs.
  - Prometheus metrics cover Celery/dbt/Airbyte latencies.
  - Alert runbooks list thresholds + escalation contacts.
- **Dependencies**
  - Coordinate with every stream when adding instrumentation.
- **Coding standards / Testing / Contracts**
  - Commands: `ruff check backend`; manual curl to `/metrics/app/`.
  - Document alert thresholds + dashboards in runbooks.
  - Edge cases: log volume, metric cardinality, alert dedupe.
  - References: `docs/ops/alerts-runbook.md`, `docs/runbooks/operations.md`.
- **Definition of Done**
  - Code limited to observability modules; docs updated.
  - Alert configs stored (Terraform/GitHub, if applicable).
  - Cross-stream sync via weekly ops standup.
  - Detailed checklist: `docs/ops/stream6-definition-of-done.md`.

## 7. BI & Deployment (`deploy/`, `docs/BI`, `docs/runbooks/deployment.md`)
- **Owner / Effort** – Primary: Carlos; Backup: Mei. Effort: Medium.
- **Success criteria / KPIs**
  - Superset/Metabase configs reproducible via git.
  - Deployment runbooks list end-to-end steps with health checks.
  - Docker compose profile stays green (`docker compose config` + smoke run).
- **Dependencies**
  - Requires stable backend/dbt outputs; coordinate when metrics change.
- **Coding standards / Testing / Contracts**
  - Commands: `docker compose config`, optional smoke `docker compose up`.
  - Ensure BI auth placeholders remain redacted.
  - References: `docs/runbooks/deployment.md`, `docs/BI/*`.
- **Definition of Done**
  - Configs + docs updated; deployment checklist refreshed.
  - Cross-stream sync with backend/dbt when new metrics appear.

### General Instructions
1. Stay within the assigned folder per workstream; no cross-folder edits unless
reviewed with the owning engineer.
2. Follow AGENTS testing matrix: backend (`ruff`, `pytest`), frontend (`npm test`
+ `npm run build`), dbt (`dbt run/test`), docs (no code yet).
3. Update the relevant docs/runbooks whenever a contract changes.
4. For PRs: describe which workstream the change belongs to and link to the
corresponding plan section.

### Cross-Stream Pending Items
- Verify SES sender identity + DMARC/DKIM for `adtelligent.net`, confirm the final "from" address,
  and update the runbooks/env defaults before production launch.
- Define a production CORS policy and implement API rate limiting/throttling for public endpoints.

### Reviewer Personas & Skills
- **Maya (Integrations Lead)** – Backend engineer specializing in Airbyte/Celery orchestration. Focuses on API stability, scheduling logic, and retry semantics. Expects `ruff` + unit tests before review and examines OpenAPI/contract updates.
- **Leo (Celery/Scheduler Specialist)** – Deep knowledge of async task tuning and observability. Looks for proper `tenant_context` usage, metrics instrumentation, and failure handling paths.
- **Priya (dbt Architect)** – Owns warehouse models; scrutinizes macro reuse, incremental strategies, and freshness enforcement. Requires dbt logs and docs for every change.
- **Martin (dbt Ops)** – Ensures deployment reproducibility, dev vs prod targets, and manifest/exposure hygiene. Checks selectors and metrics compatibility with BI tooling.
- **Sofia (Backend API Owner)** – Guards `/api/metrics/**` schemas, serializer validation, and caching logic. Demands regression tests for API payloads.
- **Andre (Metrics Infrastructure)** – Focuses on snapshot Celery tasks, adapter performance, and backwards compatibility for dashboards. Reviews monitoring hooks and payload normalization.
- **Lina (Frontend Architect)** – Leads UI/UX; enforces TypeScript strictness, design tokens, and integration tests. Looks for accessibility and responsive behavior.
- **Joel (Design System Engineer)** – Reviews component abstraction, Storybook coverage, and theme consistency. Ensures changes follow the design-system plan.
- **Nina (Security Engineer)** – Covers secrets/KMS changes, env validation, and rotation workflows. Checks for secret leakage and encryption compatibility.
- **Victor (Infra/DevOps)** – Validates scripting, env setup, and CI hooks tied to security features. Ensures automation works across environments.
- **Omar (Platform SRE)** – Oversees logging/metrics/alerts. Reviews Prometheus schemas, log context, and alert thresholds.
- **Hannah (Ops Tooling)** – Ensures runbooks are actionable, dashboards linked, and alert routing configured.
- **Carlos (Deploy/BI Lead)** – Owns Superset/Metabase configs and deployment automation. Looks for reproducibility and config hygiene.
- **Mei (Release Engineer)** – Focuses on release scripts, smoke tests, and rollback instructions. Validates docker-compose and deployment docs.
- **Raj (Cross-Stream Integration Lead)** – Coordinates work that must touch multiple top-level folders. Ensures both stream leads co-own the PR, verifies every folder’s tests/docs/contracts run, and hosts the weekly integration sync.
- **Mira (Architecture/Refactor Engineer)** – Leads cross-cutting refactors and performance improvements. Drafts refactor plans, confirms alignment with the roadmap, and shepherds approvals from affected streams before touching multiple folders.
