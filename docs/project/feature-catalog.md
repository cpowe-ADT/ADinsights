# ADinsights Feature Catalog (v0.1)

Purpose: single source of truth for what is built, in progress, and planned.
This catalog consolidates the roadmap, backlog, and workstream docs into one view.

## Status legend
- **Built**: implemented and available in code.
- **In Progress**: active or partially implemented work.
- **Planned**: defined but not yet implemented.

## Built (by domain)
### Platform/Core
- Multi-tenant auth scaffolding, tenant context middleware, RLS enforcement.
- Tenant onboarding: signup, invites, role assignment, password reset, tenant switch.
- Service account API keys + audit log endpoints for key actions (with pagination, date-range filtering, CSV export).
- Core health endpoints: `/api/health/`, `/api/health/airbyte/`, `/api/health/dbt/`, `/api/timezone/`.
- Celery task wiring with observability hooks and test coverage.
- AES-GCM secrets encryption with per-tenant DEKs + rotation script.
- Production-ready API edge controls: explicit CORS allowlist middleware + auth/public endpoint throttling.

### Data/Analytics
- dbt staging + marts for campaigns/creatives/pacing/parish aggregates.
- SCD2 snapshots for mutable dimensions.
- Metrics aggregation views, metrics macros + glossary, and contract tests.
- Warehouse snapshot persistence (`TenantMetricsSnapshot`) + aggregate snapshot API.

### Frontend
- Dashboard shell (campaigns/creatives/budget pacing).
- KPI cards, chart cards, data tables, choropleth map.
- Dataset toggle (default live), snapshot freshness banner, tenant switcher, global filters.
- Campaign/creative detail routes with saved layout + share links.
- Data sources management UI and CSV upload wizard.
- Dashboard library (API-backed with saved dashboards CRUD).
- Frontend design system tokens + docs.
- Profile page (`/me`) with user, tenant, theme, and session controls.
- Report inline editing (name/description) and report scheduling.
- Audit log view with pagination, date-range filtering, and CSV export.
- Sync health/telemetry view with connection detail page (`/ops/sync-health/:connectionId`).
- Health overview with auto-refresh (30s interval).
- Global error boundary and 404 catch-all page.
- Skeleton loader components for loading states.
- Unified toast notification system (Zustand `useToastStore`).
- Google Ads workspace pages with error states via shared component.
- Alerts CRUD and notification channel management UI.
- Alert history/runs view and alert pause/resume controls.
- AI summary badges on dashboard cards.
- CSV upload detail page with summary and preview tables.

### Integrations
- Airbyte infrastructure and declarative source templates.
- Airbyte telemetry endpoints and health checks.
- Airbyte connection lifecycle APIs (list/create/update/sync) + summary endpoint.
- Airbyte trigger-sync endpoint (full integration with audit logging).
- Production readiness verifier for Meta/Google connection credentials and tenant config sanity.
- Meta Marketing API + Page Insights OAuth flows with scope validation.
- Google Ads SDK migration (SDK with Airbyte fallback).
- GA4 tenant-scoped OAuth setup, property discovery, and KPI fetch.
- Search Console pilot integration endpoints.
- Provider-generic connector lifecycle for Airbyte-managed Google providers.

### Observability/Runbooks
- Stale snapshot monitoring spec, alert thresholds/escalation runbook.
- Deployment runbook rollback + health checklist.

### BI/Deployment
- Superset exports in version control (`docs/BI/`).
- Release checklist + demo smoke checklists.

## In Progress
### Frontend
- Sync health filters (advanced filtering).
- Report editing beyond inline metadata fields.

### Data/Analytics
- Attribution window documentation expansion.

## Planned (short list)
### Airbyte
- LinkedIn and TikTok connector implementations (replace placeholders).
- Improved Airbyte cron parsing in health check script.
- Connector roadmap beyond Meta/Google (see `docs/project/integration-roadmap.md`).

### Backend
- SES sender identity + DMARC/DKIM verification for outbound email.
- Postgres grants + `seed_roles` command/fixtures for new installs.

### Frontend/UX
- Enhanced export workflows and reporting UX.
- Enterprise UAC UX (agency admin, approvals, MFA, impersonation).

### Security/UAC
- UAC rollout phases U0–U4 (agency admin, approvals, MFA, impersonation).

## Sources of truth
- Workstreams + owners: `docs/workstreams.md`
- Roadmap phases: `README.md`
- Task sequencing + gaps: `docs/task_breakdown.md`
- Finished frontend scope: `docs/project/frontend-finished-product-spec.md`
- Integration roadmap: `docs/project/integration-roadmap.md`
- Live backlog: `docs/project/phase1-execution-backlog.md`
- UAC epics: `docs/project/uac-epics.md`
- Vertical slice: `docs/project/vertical_slice_plan.md`

## Update rules
- Update this catalog when a feature moves between Built/In Progress/Planned.
- Keep owners and dependencies in the workstream/backlog docs; this catalog remains high-level.
