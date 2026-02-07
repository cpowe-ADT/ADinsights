# API Contract Changelog (v0.1)

Purpose: track API payload changes that affect frontend, BI, or integrations.
Keep this brief and link to PRs or commits when available.

## Format
- **Date**
- **Endpoint**
- **Change**
- **Impact**
- **Owner**

## Entries
- **2026-02-06**
  - Endpoint: `GET /api/dashboards/library/`
  - Change: Added dashboard library API endpoint to replace frontend mock data and include saved report-backed items.
  - Impact: Frontend dashboard library now relies on backend response shape (`id`, `name`, `type`, `owner`, `updatedAt`, `tags`, `description`, `route`).
  - Owner: Lina (Frontend) + Sofia (Backend)
- **2026-02-06**
  - Endpoint: `GET|POST /api/reports/`, `GET|PATCH|DELETE /api/reports/{id}/`, `GET|POST /api/reports/{id}/exports/`
  - Change: Added report definition CRUD + export-job request/listing contracts.
  - Impact: Enables Post-MVP report surfaces and export lifecycle UI; clients should handle queued/running/completed/failed job statuses.
  - Owner: Sofia (Backend Metrics)
- **2026-02-06**
  - Endpoint: `GET /api/alerts/`, `GET /api/alerts/{id}/`
  - Change: Added tenant-facing alert rule routes (mirroring admin rule definitions) for frontend alerts management pages.
  - Impact: Post-MVP alerts list/detail pages can consume tenant-scoped rule definitions directly.
  - Owner: Sofia (Backend Metrics)
- **2026-02-06**
  - Endpoint: `GET /api/summaries/`, `GET /api/summaries/{id}/`, `POST /api/summaries/refresh/`
  - Change: Added persisted AI summary list/detail contracts and manual refresh endpoint.
  - Impact: Frontend summaries views can render generated/fallback status and payload snapshots.
  - Owner: Sofia (Backend Metrics)
- **2026-02-06**
  - Endpoint: `GET /api/ops/sync-health/`, `GET /api/ops/health-overview/`
  - Change: Added operational aggregation endpoints for sync-health counts/rows and consolidated health cards.
  - Impact: Powers Post-MVP `/ops/sync-health` and `/ops/health` pages with unified status semantics.
  - Owner: Omar (SRE) + Sofia (Backend Metrics)
- **2026-02-06**
  - Endpoint: `GET /api/analytics/web/ga4/`, `GET /api/analytics/web/search-console/`
  - Change: Added Phase 2 pilot web analytics endpoints for GA4/Search Console marts.
  - Impact: Provides API exposure path for GA4/Search Console pilot ingestion without changing `/api/metrics/combined/`.
  - Owner: Priya (dbt) + Sofia (Backend Metrics)
- **2026-02-06**
  - Endpoint: `POST /api/token/`, `POST /api/token/refresh/`, `POST /api/auth/login/`, `POST /api/auth/password-reset/`, `POST /api/auth/password-reset/confirm/`, `POST /api/tenants/`, `POST /api/users/accept-invite/`
  - Change: Added DRF rate limiting for unauthenticated/auth flows; clients may now receive `429` when thresholds are exceeded.
  - Impact: API clients and smoke tests should handle throttled responses and retry/backoff accordingly.
  - Owner: Sofia (Backend Metrics) + Nina (Security)
- **2026-02-06**
  - Endpoint: Cross-origin responses on API routes
  - Change: Added explicit environment-driven CORS policy (`CORS_ALLOWED_ORIGINS`, preflight handling, allow-method/header controls).
  - Impact: Browser callers must originate from configured allowlist entries in production.
  - Owner: Sofia (Backend Metrics) + Victor (Infra/DevOps)
- **2025-01-05**
  - Endpoint: `/api/metrics/combined/`
  - Change: Added `snapshot_generated_at` for freshness banner.
  - Impact: Frontend snapshot freshness UI and monitoring.
  - Owner: Sofia (Backend Metrics)
- **2026-01-22**
  - Endpoint: `/api/metrics/combined/`
  - Change: Warehouse-backed `budget` array now populated from Meta ad set daily budgets with pacing fields (`monthlyBudget`, `spendToDate`, `projectedSpend`, `pacingPercent`, optional `parishes`, `startDate`, `endDate`).
  - Impact: Budget pacing widgets can rely on live data; consumers should handle non-empty arrays and parse ISO date fields.
  - Owner: Priya (dbt)

## Update Rules
- Update this file whenever an endpoint schema or payload changes.
- Coordinate with frontend + BI when fields are added/removed.
