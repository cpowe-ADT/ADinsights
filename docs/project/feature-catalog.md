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
- Core health endpoints: `/api/health/`, `/api/health/airbyte/`, `/api/health/dbt/`, `/api/timezone/`.
- Celery task wiring with observability hooks and test coverage.
- AES-GCM secrets encryption with per-tenant DEKs + rotation script.

### Data/Analytics
- dbt staging + marts for campaigns/creatives/pacing/parish aggregates.
- SCD2 snapshots for mutable dimensions.
- Metrics aggregation views and contract tests.

### Frontend
- Dashboard shell (campaigns/creatives/budget pacing).
- KPI cards, chart cards, data tables, choropleth map.
- Dataset toggle, snapshot freshness banner, tenant switcher.
- Frontend design system tokens + docs.

### Integrations
- Airbyte infrastructure and declarative source templates.
- Airbyte telemetry endpoints and health checks.

## In Progress
### Frontend
- Wire FilterBar → API parameters for live filtering.
- Expand Storybook coverage for dataset toggle/freshness states (S4-C).

### Backend
- Stale snapshot monitoring spec for observability (S3-C).

### Data/BI
- Metrics change log for downstream consumers (S2-C).

### Observability/Runbooks
- Alert thresholds + escalation docs (S6-B).
- Deployment runbook rollback + health checklist (S7-C).

## Planned (short list)
### Airbyte
- LinkedIn and TikTok connector implementations (replace placeholders).
- Improved Airbyte cron parsing in health check script.

### Backend
- Tenant onboarding + credential CRUD improvements.
- Airbyte connection lifecycle APIs.
- Warehouse snapshot task to persist `TenantMetricsSnapshot`.

### Data/Analytics
- Add tenant_id to incremental keys in marts for stronger isolation.
- Formal metrics dictionary + attribution window docs.

### Frontend/UX
- Default to live data, demo mode opt-in only.
- Enhanced export workflows and reporting UX.

### Security/UAC
- UAC rollout phases U0–U4 (agency admin, approvals, MFA, impersonation).

### BI/Deployment
- Superset/Metabase export configs in version control.
- End-to-end release checklist and smoke tests.

## Sources of truth
- Workstreams + owners: `docs/workstreams.md`
- Roadmap phases: `README.md`
- Task sequencing + gaps: `docs/task_breakdown.md`
- Live backlog: `docs/project/phase1-execution-backlog.md`
- UAC epics: `docs/project/uac-epics.md`
- Vertical slice: `docs/project/vertical_slice_plan.md`

## Update rules
- Update this catalog when a feature moves between Built/In Progress/Planned.
- Keep owners and dependencies in the workstream/backlog docs; this catalog remains high-level.
