# AGENTS Guidelines

## Scope
These instructions apply to the entire repository unless a more specific `AGENTS.md` overrides them.

## Architecture Guardrails
- Respect the existing stack: Django + DRF + Celery for `backend/`, React + Vite + TanStack Table + Leaflet for `frontend/`, Airbyte OSS configs under `infrastructure/airbyte/`, and dbt models under `dbt/`.
- Do not introduce alternative frameworks (e.g., FastAPI) or break existing health endpoints: `/api/health/`, `/api/health/airbyte/`, `/api/health/dbt/`, `/api/timezone/`.
- Preserve row-level security and tenant isolation semantics when touching backend logic.

## Workflow Expectations
- Keep work isolated to a single top-level folder per change to avoid merge conflicts between parallel tracks.
- Use short-lived feature branches and prefer squash merges.
- Follow conventional commit messages (e.g., `feat(backend): ...`).

## Testing Matrix
Run the canonical checks for the folder you touch:
- Backend: `ruff check backend && pytest -q backend`
- Frontend: `cd frontend && npm ci && npm test -- --run && npm run build`
- dbt: `make dbt-deps && dbt --project-dir dbt run --select staging && dbt snapshot && dbt --project-dir dbt run --select marts`
- Airbyte: `cd infrastructure/airbyte && docker compose config`

## Secrets & Data Handling
- Never commit real credentials. Only update `.env.sample`, `.example`, or documented placeholders.
- Keep all reported analytics aggregated; avoid exposing per-user or raw identifiable data.

## Timezone
- Use the `America/Jamaica` timezone for schedules, examples, and documentation.

