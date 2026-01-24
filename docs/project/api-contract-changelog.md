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
