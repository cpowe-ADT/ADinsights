# Task Breakdown and Next Actions

This document translates the roadmap into concrete implementation slices. Each section lists the
recommended order of execution, key deliverables, and pointers to where code/configuration should
live in the repository.

## 1. Backend Foundations (Sprint 1 Focus)

### 1.1 Choose Framework & Bootstrap Service
- **Decision**: Select FastAPI (async, lightweight) or Django (batteries included).
- **Actions**:
  - Create a `backend/` service (e.g., FastAPI app) with poetry/pipenv requirements.
  - Configure `.env` loading and secrets (see §4.1).
  - Add initial healthcheck endpoint and run instructions.

### 1.2 Database Schema & Migrations
- **Models**: `Tenant`, `User`, `Role`, `UserRole`, `PlatformCredential`, `AuditLog`.
- **Actions**:
  - Define SQLAlchemy/ORM models and Alembic migrations (FastAPI) or Django models/migrations.
  - Ensure `PlatformCredential` stores encrypted refresh tokens; use a KMS/Secrets Manager key.
  - Implement row-level scoping (tenant_id foreign keys on business tables).

### 1.3 Authentication & RBAC
- **Actions**:
  - Implement JWT-based session tokens with tenant context.
  - Add endpoints for tenant onboarding, user invite, role assignment.
  - Provide guard middleware ensuring requests are scoped to tenant permissions.

## 2. Data Ingestion Layer

### 2.1 Airbyte Deployment & Configuration
- **Actions**:
  - Create `infrastructure/airbyte/` with `docker-compose` or helm manifests.
  - Check in configuration templates for Meta & Google Ads sources (mask secrets with placeholders).
  - Document sync schedules (hourly metrics, daily dimensions).

### 2.2 Optional Connectors
- **Actions**:
  - Stub custom source connectors for LinkedIn and TikTok within `airbyte/custom-sources/`.
  - Define interface for injecting optional tenants/platforms.

### 2.3 Sync Orchestration
- **Actions**:
  - Decide orchestrator (Airbyte scheduler, Temporal, Dagster, etc.).
  - Draft cron examples for rolling 30-day backfill.

## 3. dbt Transformation Layer

### 3.1 Project Skeleton
- **Actions**:
  - Initialize `dbt/` project with profiles for local & production.
  - Create staging models (`stg_meta_*`, `stg_google_ads_*`).

### 3.2 Core Models
- **Actions**:
  - Build `dim_campaign`, `dim_adset`, `dim_ad`, `dim_geo`, `fact_performance`.
  - Implement SCD2 for campaign/adset/ad with `dbt_utils`. Ensure tests for uniqueness/not_null.
  - Seed `parish_geojson` and `geo_lookup` tables.

### 3.3 Metrics Layer
- **Actions**:
  - Define metrics dictionary macros (spend, impressions, CTR, CPC, CPM, conversions, ROAS, etc.).
  - Materialize aggregated views for dashboards (`vw_campaign_daily`, `vw_creative_daily`, `vw_pacing`).

## 4. Platform Services & Ops

### 4.1 Secrets & Config Management
- **Actions**:
  - Standardize environment variables (document in `backend/.env.example`).
  - Choose secret store (AWS Secrets Manager, Vault) and create access pattern.

### 4.2 Observability
- **Actions**:
  - Plan logging/metrics stack (e.g., OpenTelemetry + Prometheus).
  - Ensure audit logs are written for login/data access events.

## 5. Analytics Experience

### 5.1 Frontend Scaffold
- **Actions**:
  - Initialize `frontend/` React app with Vite/Next.js.
  - Integrate TanStack Table for grids and Leaflet for parish map (use placeholder data until APIs ready).

### 5.2 BI Tool Configuration
- **Actions**:
  - Create `bi/metabase/` or `bi/superset/` directory with exported dashboard JSONs.
  - Document dashboard filters, KPIs, and refresh cadence.

### 5.3 Alerts & Summaries
- **Actions**:
  - Define SQL alert templates and schedule definitions.
  - Draft LLM prompt templates and safety guardrails; note dependency on metrics layer.

## 6. Prioritized Immediate Next Steps
1. Decide on backend framework and secret management approach (blocks auth work).
2. Bootstrap backend service with database migrations (enable tenant onboarding).
3. Stand up Airbyte in infrastructure code and commit configuration templates.
4. Initialize dbt project with staging models (allows early data validation).
5. Create frontend skeleton to unblock UX iterations.

Track progress via the project management tool (Jira/Linear) linked to these workstreams.
