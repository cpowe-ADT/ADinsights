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
