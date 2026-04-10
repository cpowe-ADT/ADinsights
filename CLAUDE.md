# Claude Code Project Instructions

## What This Is

ADinsights is a self-hosted, multi-tenant marketing analytics platform for Jamaican agencies. It ingests data from Meta and Google Ads (optional LinkedIn/TikTok), normalizes with dbt, and delivers dashboards, grids, maps, alerts, and AI summaries by Jamaica parish.

## Before You Touch Code

1. Read `AGENTS.md` — it is the authoritative guardrails document.
2. Follow the recontextualization order in AGENTS.md when context is unclear.
3. Keep changes scoped to a single top-level folder unless Raj (integration) + Mira (architecture) approve.
4. Use conventional commits: `feat(backend):`, `fix(frontend):`, `docs(runbooks):`, etc.

## Stack

- **Backend**: Django 5 + DRF + Celery + Redis, Python 3.11+ (`backend/`)
- **Frontend**: React 18 + Vite + TanStack Table + Leaflet + Recharts + Zustand (`frontend/`)
- **Data pipeline**: PostgreSQL + Airbyte OSS + dbt (`dbt/`, `infrastructure/airbyte/`)
- **Testing**: pytest (backend), vitest (frontend unit), Playwright (e2e in `qa/`), Storybook
- **Infra**: Docker Compose (`docker-compose.dev.yml`), AWS (boto3)

## Runtime Topology

| Service | Local URL | Notes |
|---------|-----------|-------|
| Frontend dev | `http://localhost:5173` | Vite dev server |
| Backend dev | `http://localhost:8000` | Django runserver (or 8010 via launcher) |
| API proxy | `/api` on frontend → backend | Configured in `frontend/vite.config.ts` |
| Meta OAuth redirect | `http://localhost:5173/dashboards/data-sources` | Pinned in `backend/.env` |

## Auth

- JWT Bearer tokens via SimpleJWT (`Authorization: Bearer <token>`)
- `apiClient.ts` handles token refresh and 401 → logout
- Tests use SQLite in-memory with `config.settings.test`

## Adapter System (Critical for Dashboard Work)

The combined metrics endpoint `/api/metrics/combined/` dispatches to an adapter selected by environment flags:

| Adapter | Env Flag | What It Does |
|---------|----------|-------------|
| `warehouse` | `ENABLE_WAREHOUSE_ADAPTER` | Reads dbt mart views via SQL |
| `meta_direct` | `ENABLE_META_DIRECT_ADAPTER` | Reads synced Meta ORM tables directly (bypasses dbt) |
| `demo` | `ENABLE_DEMO_ADAPTER` | Seeded demo data |
| `fake` | `ENABLE_FAKE_ADAPTER` | Generated fake data |
| `upload` | `ENABLE_UPLOAD_ADAPTER` | CSV upload snapshots |

Priority: warehouse > meta_direct > demo > fake. Default local dev has all disabled except what `.env` sets.

Key files:
- `backend/adapters/meta_direct.py` — MetaDirectAdapter
- `backend/analytics/combined_metrics_service.py` — orchestrator
- `backend/analytics/views.py` — CombinedMetricsView
- `backend/analytics/dataset_status.py` — live-readiness logic

## Frontend State Architecture

- `useDatasetStore` (Zustand) — adapter selection, dataset mode (live/dummy), live reason
- `useDashboardStore` (Zustand) — filters, metrics data, `loadAll()` dispatch
- `DashboardLayout.tsx` — master shell, wires filters → URL → data loading
- `liveAccountSelection.ts` — localStorage-backed account persistence per tenant
- `apiClient.ts` — `API_BASE_URL` defaults to `/api`, Vite proxies to backend

## Meta Integration Key Concepts

- **Two OAuth flows**: Marketing API (ad accounts) vs Page Insights (pages only)
- **Social status**: `GET /api/integrations/social/status/` — auth/connection truth
- **Dataset status**: `GET /api/datasets/status/` — live dashboard readiness truth
- **Triage order**: social status → dataset status → meta accounts → meta pages → combined metrics
- **Connection states**: `not_connected`, `started_not_complete`, `complete`, `active`, `orphaned_marketing_access`

## Test Commands

```bash
# Backend
ruff check backend
cd backend && pytest -q
cd backend && pytest -q tests/test_metrics_api.py

# Frontend
cd frontend && npm test -- --run
cd frontend && npm run build
cd frontend && npm run lint

# E2E
npm run test:e2e

# Full stack (launcher)
scripts/dev-launch.sh --profile 1 --non-interactive --no-update --no-pull --no-open
```

## Key Guardrails

- Preserve tenant isolation — `SET app.tenant_id` per request, never weaken RLS
- Never commit real secrets — only `.env.sample`/`.example` placeholders
- Timezone: `America/Jamaica` for all schedules and docs
- Do not introduce alternative frameworks (no FastAPI, no Next.js)
- Do not remove health endpoints: `/api/health/`, `/api/health/airbyte/`, `/api/health/dbt/`, `/api/timezone/`
- PII: only aggregated advertising metrics, never user-level data

## Key Doc References

- `AGENTS.md` — guardrails, schedules, testing matrix
- `docs/workstreams.md` — folder owners, KPIs, DoD
- `docs/project/api-contract-changelog.md` — API payload changes
- `docs/project/integration-data-contract-matrix.md` — source-to-API field mapping
- `docs/runbooks/meta-app-review-validation.md` — Meta validation + triage
- `docs/runbooks/meta-page-insights-operations.md` — Page Insights ops
- `docs/ops/testing-cheat-sheet.md` — all test commands
- `docs/project/definition-of-done.md` — completion criteria
- `docs/ops/escalation-rules.md` — when to escalate to Raj/Mira

## Current State (April 2026)

- Phase 1 execution backlog: nearly all items Done
- Active work area: stabilizing live Meta/direct-sync dashboard behavior
- Google Ads SDK migration in progress (SDK with Airbyte fallback)
- GA4 and Search Console are Phase 2 pilot contracts
- Frontend spec punch list has remaining MVP/Post-MVP gaps
