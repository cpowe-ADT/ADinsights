# Definition of Done (v0.1)

Purpose: consistent completion criteria for AI and humans.

## All work
- Scoped to one top-level folder (unless Raj/Mira approve).
- Tests for the touched folder are green.
- Docs/runbooks updated if behavior changes.
- Feature catalog status updated if needed.

## Frontend
- No accessibility regressions (focus-visible preserved).
- `npm test -- --run` and `npm run build` passed.

## Backend
- `ruff check backend` and `pytest -q backend` passed.
- Tenant isolation preserved (`SET app.tenant_id`).

## dbt
- Staging + marts built; tests pass.

## Airbyte
- `docker compose config` passes.
