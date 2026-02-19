# Human Onboarding Guide (v0.1)

Purpose: give a new human engineer everything needed to understand, run, and extend ADinsights safely.

## 1) What this system does
ADinsights is a multi-tenant marketing analytics platform for Jamaican agencies.
It ingests paid media data (Meta/Google; LinkedIn/TikTok optional), models it in dbt,
serves aggregated metrics via a Django API, and renders dashboards in React.

## 2) Architecture at a glance
- **Backend**: Django + DRF + Celery (`backend/`)
- **Frontend**: React + Vite + TanStack Table + Leaflet (`frontend/`)
- **Ingestion**: Airbyte OSS templates + scripts (`infrastructure/airbyte/`)
- **Modeling**: dbt models/macros/tests (`dbt/`)
- **QA**: Playwright tests (`qa/`)

Key flow: Airbyte → dbt → Backend `/api/metrics/combined/` → Frontend dashboards.

## 3) Guardrails you must follow
- Preserve stack and health endpoints (see `AGENTS.md`).
- Maintain tenant isolation: backend must set `SET app.tenant_id` per request.
- Do not log secrets; tokens are AES-GCM encrypted with per-tenant DEKs.
- Keep analytics aggregated; no user-level data (PII policy).
- Keep changes isolated to a single top-level folder per PR unless approved.

## 4) Where to look first (doc map)
Read in this order:
1) `AGENTS.md`
2) `docs/ops/doc-index.md`
3) `docs/workstreams.md`
4) `docs/project/feature-catalog.md`
5) `docs/project/phase1-execution-backlog.md`
6) `docs/task_breakdown.md`
7) `docs/project/vertical_slice_plan.md`

## 5) Running the system locally
Use the dev launcher:
```bash
scripts/dev-launch.sh
```
Default ports:
- Backend: 8000
- Frontend: 5173

For profile selection, fallback behavior, and port-conflict recovery, see `docs/DEVELOPMENT.md`.
Quick setup/check commands:
- `scripts/dev-launch.sh --list-profiles`
- `scripts/dev-launch.sh --profile 2`
- `cat .dev-launch.active.env`
- `scripts/dev-healthcheck.sh`
- `docker compose -f docker-compose.dev.yml ps`

Health endpoints:
- `/api/health/`
- `/api/health/airbyte/`
- `/api/health/dbt/`
- `/api/timezone/`

## 6) Testing matrix (per folder)
- **Backend**: `ruff check backend && pytest -q backend`
- **Frontend**: `cd frontend && npm test -- --run && npm run build`
- **dbt**: `make dbt-deps && dbt run --select staging && dbt snapshot && dbt run --select marts`
- **Airbyte**: `cd infrastructure/airbyte && docker compose config`

## 7) Key files by domain
### Backend
- Core settings/observability: `backend/core/`
- Metrics API + snapshots: `backend/analytics/`
- Tenant auth/RLS: `backend/accounts/`, `backend/middleware/tenant.py`

### Frontend
- Dashboards: `frontend/src/routes/`
- Data fetching: `frontend/src/lib/`
- UI components: `frontend/src/components/`
- Design system: `frontend/DESIGN_SYSTEM.md`

### dbt
- Staging/marts/snapshots: `dbt/models/`, `dbt/snapshots/`
- Macros/tests: `dbt/macros/`, `dbt/tests/`

### Airbyte
- Templates: `infrastructure/airbyte/*.yaml`
- Scripts: `infrastructure/airbyte/scripts/`
- Compose images are pinned to Airbyte OSS `v1.8.0` in `infrastructure/airbyte/docker-compose.yml`.
- GHCR auth is required to pull images: `docker login ghcr.io` (token with `read:packages`).

## 8) Common questions (and answers)
**Q: Where are API schemas documented?**  
A: `docs/project/api-contract-changelog.md` and backend serializers/tests.

**Q: How do we track features?**  
A: `docs/project/feature-catalog.md` + `docs/project/phase1-execution-backlog.md`.

**Q: Where are the UX standards?**  
A: `frontend/DESIGN_SYSTEM.md` and `docs/design-system.md`.

**Q: What if I need to touch multiple folders?**  
A: Stop and consult Raj (Integration) and Mira (Architecture).

## 9) Delivery checklist
- Stay within one top-level folder.
- Run the canonical tests for the folder.
- Update the feature catalog/runbooks if behavior changes.

## 10) Simulated peer review (iteration notes)
This section captures a “human review pass” to ensure clarity.

**Release Train Manager**: Missing a release checklist → see `docs/runbooks/release-checklist.md`.  
**Project Manager**: Needs owners & dependencies → see `docs/workstreams.md` + `feature-ownership-map.md`.  
**Sprint Lead**: Needs backlog and scope → see `docs/project/phase1-execution-backlog.md`.  
**Tech Lead**: Needs guardrails and tests → see `AGENTS.md` + testing matrix.  
**Senior Engineer**: Needs data flow and schemas → see `data-lineage-map.md` + dbt models.  

If any of these links are unclear, update this guide and the doc index.
