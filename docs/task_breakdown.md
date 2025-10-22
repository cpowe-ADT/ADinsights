# Task Breakdown and Next Actions

This document translates the roadmap into concrete implementation slices. Each section lists the
recommended order of execution, key deliverables, and pointers to where code/configuration should
live in the repository.

## 1. Backend Foundations (Sprint 1 Focus)

### 1.1 Harden Django Service

- **Current State**: Django + DRF project with tenant-aware models, JWT auth, Celery wiring, and
  encryption helpers is in place.
- **Next Actions**:
  - Implement admin and onboarding flows to invite tenants and assign roles through the API.
  - Extend permission classes so every endpoint enforces tenant scoping by default.
  - Integrate a secrets backend (AWS KMS/Secrets Manager or Vault) behind the `KmsClient` interface.

### 1.2 Database Schema & Migrations

- **Models**: `Tenant`, `User`, `Role`, `UserRole`, `PlatformCredential`, `AuditLog`, `TenantKey` exist.
- **Next Actions**:
  - Add business tables for campaign/adset/ad metadata and metrics landing zones.
  - Wire the `enable_rls` command into deployment scripts and document Postgres grants.
  - Create fixtures to bootstrap default roles/permissions for new installations.

### 1.3 Authentication & RBAC

- **Current State**: JWT login and `/api/me` endpoints exist with middleware that sets
  `app.tenant_id`.
- **Next Actions**:
  - Add password reset/onboarding flows (email invite, tenant switch UI considerations).
  - Implement API keys or service accounts for automated integrations.
  - Surface audit log endpoints and hook key actions (login, credential changes) into the log.

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

- **Next Actions**:
  - Decide on owning orchestration (Airbyte scheduler vs. external orchestrator) and codify cron
    expressions in infrastructure-as-code.
  - Integrate sync status callbacks with the backend (store last-sync timestamps per tenant).

## 3. dbt Transformation Layer

### 3.1 Project Skeleton

- **Current State**: dbt project with staging models, macros, and parish lookup seed committed.
- **Next Actions**:
  - Add source freshness checks and contracts to validate Airbyte output schemas.
  - Document environment-specific targets (dev/staging/prod) and add invocation scripts.

### 3.2 Core Models

- **Next Actions**:
  - Build `dim_campaign`, `dim_adset`, `dim_ad`, `dim_geo`, and `fact_performance` with SCD2 support.
  - Add macros to align attribution windows (Meta unified attribution, Google conversion windows).
  - Expand the parish lookup to cover Google GeoTarget IDs and Meta region strings comprehensively.

### 3.3 Metrics Layer

- **Next Actions**:
  - Define metrics dictionary macros (spend, impressions, CTR, CPC, CPM, conversions, ROAS, etc.).
  - Materialize aggregated views for dashboards (`vw_campaign_daily`, `vw_creative_daily`,
    `vw_pacing`).
  - Document attribution nuances (Meta 13-month reach limitation, Google conversion lag) alongside
    calculations.

## 4. Platform Services & Ops

### 4.1 Secrets & Config Management

- **Current State**: `.env.sample` enumerates required variables and a pluggable `KmsClient` exists.
- **Next Actions**:
  - Implement the AWS KMS client or alternative and wire it to environment-specific keys.
  - Decide how tenants manage credential rotation (UI vs. CLI) and log these events.

### 4.2 Observability

- **Next Actions**:
  - Plan logging/metrics stack (e.g., OpenTelemetry + Prometheus) and add instrumentation to Celery
    tasks and API endpoints.
  - Ensure audit logs are written for login/data access events and exposed via API for compliance.

## 5. Analytics Experience

### 5.1 Frontend Scaffold

- **Current State**: React + Vite shell renders TanStack Table and Leaflet map with mock data.
- **Next Actions**:
  - Replace mock fetches with authenticated API calls once endpoints land.
  - Add routing for campaign/creative detail pages and integrate Superset/Metabase embeds if used.

### 5.2 BI Tool Configuration

- **Next Actions**:
  - Export baseline dashboards from Metabase/Superset into version control.
  - Configure email/Slack subscriptions and alert thresholds tied to metrics.

### 5.3 Alerts & Summaries

- **Next Actions**:
  - Define SQL alert templates and schedule definitions.
  - Draft LLM prompt templates and safety guardrails; note dependency on metrics layer.
  - Prototype Canva integration workflow for shareable summaries.

## 6. Prioritized Immediate Next Steps

1. Connect Airbyte Meta/Google sources to a development warehouse and verify incremental syncs.
2. Extend the backend with tenant onboarding and credential CRUD endpoints surfaced via DRF viewsets.
3. Build first-pass dbt fact/dimension models and expose them through lightweight API endpoints.
4. Replace frontend mock fetches with live API calls for campaign listings and parish metrics.
5. Document monitoring expectations (alerts for Airbyte failures, Celery retries, dbt freshness).

Track progress via the project management tool (Jira/Linear) linked to these workstreams.

---

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
