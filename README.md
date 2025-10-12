# ADinsights

## Project Overview
ADinsights will be a self-hosted, multi-tenant marketing analytics platform for Jamaican agencies. It will ingest performance data from Meta, Google Ads, and optional LinkedIn/TikTok sources, normalize it with dbt, and deliver dashboards, grids, maps, alerts, and AI-generated summaries tailored to Jamaica's parishes.

## Repository Structure
- **backend/**: Django + DRF API with multi-tenant auth, Celery tasks, and encrypted credential storage.
- **infrastructure/airbyte/**: Docker Compose stack and redacted source templates for Airbyte.
- **dbt/**: dbt project with staging models, macros, and parish lookup seed.
- **frontend/**: React + Vite shell featuring TanStack Table and Leaflet choropleth with mock data.
- **docs/**: Planning artifacts including the roadmap breakdown.

## Implementation Roadmap

### Phase 0 – Foundations
1. **Repository & Documentation**
   - Establish coding standards, environment variables management, and secrets handling guidelines.
   - Document data protection compliance requirements (Jamaica Data Protection Act) and platform-specific terms of service.
2. **Infrastructure Planning**
   - Decide on target cloud (e.g., AWS) and baseline services (VPC, networking, storage, container orchestration).
   - Select database engine (PostgreSQL + PostGIS or cloud warehouse) and sizing assumptions.

### Phase 1 – Core Platform Setup (Sprint 1)
1. **Identity & Multi-Tenancy**
   - Scaffold backend service (FastAPI/Django) with database migrations.
   - Create Tenant, User, Role, PlatformCredential models with encryption for stored tokens.
   - Implement RBAC and tenant-scoped API authentication.
2. **Connector Bootstrapping**
   - Deploy Airbyte and configure Meta & Google Ads sources with incremental sync and geo breakdowns.
   - Define custom connector stubs for LinkedIn Ads and TikTok transparency (even if optional).
3. **Warehouse & dbt Skeleton**
   - Create staging models (stg_*), core fact/dim tables without SCD2, and geo lookup scaffolding.
   - Load Jamaica parish GeoJSON and seed initial mappings.
4. **Initial Analytics UX**
   - Stand up Metabase (or Superset) and publish a basic campaign dashboard.
   - Scaffold React frontend with TanStack Table and Leaflet map components wired to mocked data.

### Phase 2 – Data Modeling & Metrics (Sprint 2)
1. **SCD2 & Metrics Layer**
   - Extend dbt models for SCD2 on campaign/adset/ad dimensions and implement metrics dictionary/macros.
   - Materialize aggregated views for campaign, creative, and pacing use cases.
2. **Enhanced Visualizations**
   - Add creative analysis and budget pacing dashboards with cross-filters.
   - Implement parish choropleth interactions and deck.gl custom tooltips (if using Superset).
3. **Operational Automation**
   - Configure dashboard subscriptions (email/Slack), SQL alerts, and orchestrated dbt runs (dbt Cloud/Cron/Celery).
   - Implement hourly Airbyte syncs with rolling 30-day backfill; nightly dbt transformations.

### Phase 3 – Advanced Features (Sprint 3)
1. **AI Summaries & Integrations**
   - Integrate LLM provider for summary generation with guardrailed prompts.
   - Explore Canva SDK automation for templated report exports.
2. **Audit, Security & Compliance**
   - Implement audit logging (logins, data access, report generation) and retention policies.
   - Document OIC registration, data minimization, storage limitation, and cross-border transfer safeguards.
3. **Admin & Monitoring**
   - Build admin console for credential rotation, quota monitoring, and sync health status.
   - Add observability (metrics/logging/alerts) for connectors and transformations.

### Phase 4 – Polish & Launch
1. **User Acceptance Testing**
   - Run pilot with representative clients; collect feedback and iterate on geo mappings and dashboards.
2. **Performance & Hardening**
   - Optimize queries, cache heavy dashboards, and simplify GeoJSON for faster rendering.
   - Conduct penetration testing and fix findings.
3. **Documentation & Training**
   - Produce runbooks, onboarding guides, privacy notices, and SLA definitions.
   - Provide training sessions for analysts and admins.

## Next Steps Checklist
- [x] Choose backend framework and initialize service.
- [x] Provision infrastructure scaffolds for Airbyte, dbt, and frontend shell.
- [ ] Configure Airbyte connections with production credentials and schedule hourly metric syncs.
- [ ] Extend dbt models beyond staging to deliver fact tables, metrics dictionary, and parish mapping logic.
- [ ] Secure secrets management integration (e.g., AWS Secrets Manager or Vault) for runtime keys.
- [ ] Stand up Metabase/Superset dashboards connected to the API once metrics are available.
- [ ] Use [`docs/task_breakdown.md`](docs/task_breakdown.md) to track sprint assignments and validation.
