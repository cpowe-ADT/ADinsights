# Testing Cheat Sheet (v0.1)

Purpose: quick test commands per workstream.

## Backend
- `ruff check backend`
- `pytest -q backend`

## Frontend
- `cd frontend && npm test -- --run`
- `cd frontend && npm run build`

## dbt
- `make dbt-deps`
- `dbt --project-dir dbt run --select staging`
- `dbt snapshot`
- `dbt --project-dir dbt run --select marts`

## Airbyte
- `docker login ghcr.io` (token with `read:packages`)
- `cd infrastructure/airbyte && docker compose config`
