# Task Breakdown and Next Actions

This document translates the roadmap into concrete implementation slices. Each section lists the
recommended order of execution, key deliverables, and pointers to where code/configuration should
live in the repository.

## 1. Backend Foundations (Sprint 1 Focus)

### 1.1 Harden Django Service

- **Current State**: Django + DRF with tenant-aware models, JWT auth, Celery wiring, encryption
  helpers, tenant onboarding (signup/invite/roles), password reset, service accounts, and audit
  log endpoints.
- **Next Actions**:
  - Audit tenant scoping coverage and default permission classes across endpoints.

### 1.2 Database Schema & Migrations

- **Models**: `Tenant`, `User`, `Role`, `UserRole`, `PlatformCredential`, `AuditLog`, `TenantKey` exist.
- **Next Actions**:
  - Document Postgres grants for RLS and confirm `enable_rls` is part of the deploy pipeline.
  - Create fixtures or a `seed_roles` command to bootstrap default roles/permissions.

### 1.3 Authentication & RBAC

- **Current State**: JWT login, `/api/me`, tenant switch, invite acceptance, password reset,
  service account auth, and audit log endpoints are live.
- **Next Actions**:
  - Verify SES sender identity + DMARC/DKIM for `adtelligent.net` and confirm final "from" address
    before production launch (external AWS/domain dependency).
  - Keep production CORS allowlist and auth/public throttles aligned with release checklist values.

## 2. Data Ingestion Layer

### 2.1 Airbyte Deployment & Configuration

- **Current State**: Docker Compose stack with redacted source templates and scheduling guidance.
- **Next Actions**:
  - Parameterise connections via environment variables or Terraform for repeatable deployments.
  - Define destination configurations that push raw data into the warehouse selected for each tenant.
  - Capture monitoring/alerting hooks for failed syncs (e.g., Slack webhook, email).

### 2.2 Optional Connectors

- **Next Actions**:
  - Flesh out the custom Python connectors for LinkedIn and TikTok, aligning with the PRD field set.
  - Establish acceptance tests (Airbyte connector test harness) so schema drift is caught quickly.

### 2.3 Sync Orchestration

- **Current State**: Airbyte webhook updates tenant sync status/telemetry in the backend.
- **Next Actions**:
  - Decide on owning orchestration (Airbyte scheduler vs. external orchestrator) and codify cron
    expressions in infrastructure-as-code.

### 2.4 Integration Roadmap (Connectors + APIs)

- **Reference**: `docs/project/integration-roadmap.md` (prioritized connector list, API requirements,
  and phased build order).
- **Next Actions**:
  - Validate OAuth and partner approval requirements for Phase 1 connectors.
  - Use `docs/project/integration-api-validation-checklist.md` to log scopes, limits, and risks.
  - Identify which sources are covered by Airbyte vs. custom connectors.
  - Confirm metrics parity needed for dashboard KPIs before adding new sources.

## 3. dbt Transformation Layer

### 3.1 Project Skeleton

- **Current State**: dbt project with staging models, macros, parish lookup seed, and source
  freshness checks committed.
- **Next Actions**:
  - Document environment-specific targets (dev/staging/prod) and add invocation scripts.

### 3.2 Core Models

- **Current State**: `dim_campaign`, `dim_adset`, `dim_ad`, `dim_geo`, and `fact_performance`
  implemented with SCD2 support.
- **Next Actions**:
  - Expand the parish lookup to cover Google GeoTarget IDs and Meta region strings comprehensively.

### 3.3 Metrics Layer

- **Current State**: Metrics dictionary macros and aggregated views for dashboards
  (`vw_campaign_daily`, `vw_creative_daily`, `vw_pacing`) are in place.
- **Next Actions**:
  - Document attribution nuances (Meta 13-month reach limitation, Google conversion lag) alongside
    calculations.

## 4. Platform Services & Ops

### 4.1 Secrets & Config Management

- **Current State**: `.env.sample` enumerates required variables; `KmsClient` supports local and
  AWS KMS; DEK rotation CLI + Celery schedule exist.
- **Next Actions**:
  - Provision production KMS keys and wire Secrets Manager/SSM in deploy environments (code path and
    validation are ready; environment provisioning remains external).
  - Decide how tenants manage credential rotation (UI vs. CLI) and log these events.

### 4.2 Observability

- **Current State**: Structured JSON logs include tenant/task correlation; `/metrics/app` is
  instrumented; alert thresholds and stale snapshot monitoring runbooks are in place.
- **Next Actions**:
  - Wire logs/metrics to the production observability stack (Prometheus/OpenTelemetry + alerts).

## 5. Analytics Experience

### 5.1 Frontend Scaffold

- **Current State**: React + Vite dashboards load live combined metrics with demo/upload fallback,
  and include global filters, dataset toggle, snapshot freshness, tenant switcher, detail routes,
  data sources UI, CSV upload wizard, and dashboard library shell.
- **Next Actions**:
  - Replace remaining mock-backed screens (dashboard library) with API data.
  - Align remaining routes, empty states, and snapshot freshness UX with the finished frontend
    spec in `docs/project/frontend-finished-product-spec.md` and review with Lina/Joel.

### 5.2 BI Tool Configuration

- **Next Actions**:
  - Export baseline dashboards from Metabase/Superset into version control.
  - Configure email/Slack subscriptions and alert thresholds tied to metrics.

### 5.3 Alerts & Summaries

- **Next Actions**:
  - Define SQL alert templates and schedule definitions.
  - Draft LLM prompt templates and safety guardrails; note dependency on metrics layer.
  - Prototype Canva integration workflow for shareable summaries.

### 5.4 Finished Frontend Scope (MVP -> Post-MVP -> Enterprise)

- **Reference**: `docs/project/frontend-finished-product-spec.md` (source of truth for pages,
  filters, drill paths, exports, empty states, and stale data handling).
- **MVP completion goals**:
  - Home, Create dashboard, Campaigns, Creatives, Budget pacing, Map detail, and Profile flows
    match the page-level requirements in the spec.
  - Global filters and snapshot freshness indicators applied consistently across dashboards.
  - Acceptance checklist (MVP section) verified before widening Post-MVP scope.
- **Post-MVP expansion**:
  - Data sources management UI and CSV upload wizard are now implemented.
  - Report builder and exports (PDF/PNG), alerts, AI summaries, and admin/sync health views.
- **Enterprise rollout**:
  - UAC-driven approvals, board packs, impersonation, access review, and "why denied" UI tied to
    `docs/security/uac-spec.md`.
  - Require senior frontend review (Lina) and design system review (Joel) before shipping UAC UX.

## 6. Prioritized Immediate Next Steps

1. Complete Phase 1 connector API validation (Microsoft, LinkedIn, TikTok) and confirm OAuth scopes/limits.
2. Configure Airbyte Meta/Google connections with real credentials and verify incremental syncs.
3. Provision production KMS keys + Secrets Manager/SSM wiring; verify rotation reminders in prod.
4. Verify SES sender identity + DMARC/DKIM and confirm final "from" address.
5. Confirm production env values for CORS/throttles match runbook and perform `429` smoke checks.

Track progress via the project management tool (Jira/Linear) linked to these workstreams.

---

## 6.1 Corrections & Follow-Up Tasks

The vertical slice surfaced a handful of outstanding gaps. Document them here so they can be
scheduled deliberately instead of rediscovered during reviews:

- **Secrets production wiring** – code/config validation is complete; remaining work is external
  provisioning of KMS keys and secrets manager bindings in production.
- **Email deliverability** – runbook/env are ready; remaining work is external SES identity
  verification + sandbox exit for `adtelligent.net`.
- **RLS/roles bootstrap** – document Postgres grants and add a `seed_roles` fixture/command.

---

## 6.2 Post-MVP Frontend Sprint Picks (Approved 2026-02-01)

Goal: ship the first Post-MVP frontend features that are fully backed by existing APIs.
Review basis: `docs/project/frontend-finished-product-spec.md` and
`docs/project/frontend-spec-review-checklist.md`.

- **Pick A: Data sources management UI (Estimate: M)** — Done
  - Sub-tasks: list + summary cards; connection detail view; schedule display; status pills; empty
    and error states; "run now" control when available.
  - API deps: `GET /api/airbyte/connections/`, `GET /api/airbyte/connections/summary/`.
  - Acceptance: supports empty/error/loading; last sync timestamp; stale warning; clear CTA to docs.
  - Owner/tests: Lina; `npm run lint && npm test -- --run && npm run build`.
- **Pick B: Sync health + telemetry view (Estimate: S-M)**
  - Sub-tasks: telemetry table with pagination; job detail panel; API cost summaries; error banner
    for failed syncs; health endpoint cross-link.
  - API deps: `GET /api/airbyte/telemetry/`, `GET /api/health/airbyte/`.
  - Acceptance: paginated job list, status pills, error details, stale banner tied to last sync.
  - Owner/tests: Lina; `npm run lint && npm test -- --run && npm run build`.
- **Pick C: Health checks overview (Estimate: S)**
  - Sub-tasks: cards for /health, /health/airbyte, /health/dbt, /timezone; timestamps; runbook
    links for failures.
  - API deps: `GET /api/health/`, `GET /api/health/airbyte/`, `GET /api/health/dbt/`,
    `GET /api/timezone/`.
  - Acceptance: clear success/failure states with timestamps; links to runbooks.
  - Owner/tests: Lina; `npm run lint && npm test -- --run && npm run build`.

Stretch items (CSV upload wizard and dashboard library shell) are delivered; ensure QA before
adding new picks.

---

## 6.3 Sprint Checklist: Dashboard Live Data + Filters (Completed)

Delivered:

- API contract alignment for `/api/metrics/combined/` and typed dashboard data flow.
- Live data default with demo opt-in only.
- FilterBar wiring + URL state + drill-down routes.
- Consistent loading/empty/error/stale states across dashboards.

## 6.4 Frontend Spec Punch List (MVP/Post-MVP)

### MVP gaps

- [ ] Home page: replace static recent dashboards with API-driven data + true empty state logic.

### Post-MVP gaps

- [x] Dashboard library: replace mock data with real API listing + error/empty states.
- [x] Sync health/telemetry view (`/ops/sync-health`).
- [x] Health checks overview (`/ops/health`).
- [x] Reports/report builder + exports (`/reports`, `/reports/new`, `/reports/:id`).
- [x] Alerts + AI summaries UI (`/alerts`, `/summaries`).
- [x] Admin audit log view + export.

## 7. User Access Control (UAC) Rollout Plan

See `docs/security/uac-spec.md` for the authoritative privilege model. This section breaks the rollout into sequenced engineering/ops slices. Each slice maps to one or more GitHub milestones and should be executed in order; individual tasks should stay within a single top-level folder per AGENTS guidelines.

### Phase U0 – Schema & Plumbing (Weeks 1–2)

- Backend (`backend/`)
  - Add `Agency`, `RoleBinding` (supports agency/tenant/workspace scope), `EntitlementPlan` models + migrations.
  - Extend JWT claims/session storage (`current_tenant_id`, `managed_tenants[]`).
  - Implement `ScopeFilterBackend` and `HasPrivilege` DRF permission scaffold.
- Frontend (`frontend/`)
  - Introduce global tenant context store with placeholders for tenant switcher.
- Docs/DevOps (`docs/`, `scripts/`)
  - Publish migration runbook for role binding changes.
  - Update seed fixtures with new roles and entitlements.

### Phase U1 – Agency Delegated Admin (Weeks 3–4)

- Backend
  - CRUD APIs for agencies & managed tenants; RBAC enforcement linking agency admins to tenants.
  - Portfolio KPI endpoint (aggregate-only, PDF export stub).
  - Audit events for agency admin operations.
- Frontend
  - Tenant/agency switcher UI (searchable, keyboard shortcuts).
  - Portfolio dashboard shell (no drill-through).
- Infrastructure/Docs
  - Update SCIM integration guide for new group-to-role mappings.
  - Document support playbook for delegated admin escalations.

### Phase U2 – Client Controls & Approvals (Weeks 5–7)

- Backend
  - Workflow engine for Draft → Review → Publish and budget proposals (dual approval states).
  - Board Pack generator service (PDF with watermarks, SLA tracking).
  - Blackout window enforcement for publish operations.
- Frontend
  - Draft/review UI with approval states, comments, embargo banners.
  - Board Pack scheduling interface for TL roles.
- dbt / Analytics
  - Data marts supporting Board Pack KPIs, plan-versus-actual logic, anomaly detection.

### Phase U3 – Security Hardening (Weeks 8–9)

- Backend
  - Step-up MFA enforcement decorator for high-risk endpoints (CSV enablement, secret rotation, destructive ops).
  - Impersonation session API (consent, duration, audit log).
  - Export watermarking service + registry.
- Frontend
  - Impersonation banners, export confirmation dialogs, reason capture modals.
- Ops
  - Audit log retention policy enforcement; integration with SIEM.
  - Update incident/break-glass runbooks.

### Phase U4 – Compliance & UX Polish (Weeks 10–12)

- Backend/Frontend
  - “Why denied?” trace endpoint/UI for privilege decisions.
  - Access review exports for quarterly attestation.
  - Persona-based onboarding tours, role badges, context banners.
- Docs
  - Finalize enterprise onboarding guide (agencies + clients).
  - Add privacy/PII handling appendix.

### Acceptance & Regression Checklist

- Execute UAT scenarios defined in `docs/security/uac-spec.md` §12.
- Pen-test focus on tenant isolation, impersonation, export leaks.
- Sign-off from security, product, and support prior to enabling CSV or Board Pack entitlements for production tenants.

Track UAC tasks under the `MVP-ops-observability`, `MVP-backend-api`, and new `MVP-security-uac` milestones. Update this plan as we refine scope or add future personas (e.g., privacy reviewer, read-only service accounts).
