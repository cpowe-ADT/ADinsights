# Staging Go/No-Go Rehearsal (Local Dry Run)

Timestamp: 2026-02-05 23:19 EST (America/Jamaica)

## Objective

Execute Phase 1 release rehearsal sequence in dependency order and capture readiness state.

## Sequence and outcomes

1. Backend checks
- Command: `ruff check backend && pytest -q backend`
- Result: PASS

2. dbt checks
- Commands:
  - `make dbt-deps`
  - `DBT_PROFILES_DIR=dbt dbt run --project-dir dbt --select staging`
  - `DBT_PROFILES_DIR=dbt dbt snapshot --project-dir dbt`
  - `DBT_PROFILES_DIR=dbt dbt run --project-dir dbt --select marts`
- Result: PASS

3. Airbyte compose readiness
- Command: `cd infrastructure/airbyte && docker compose config`
- Result: PASS

4. API health smoke probe
- Probed endpoints:
  - `/api/health/`
  - `/api/health/airbyte/`
  - `/api/health/dbt/`
  - `/api/timezone/`
- Result: BLOCKED (local backend service not running; connection refused on `localhost:8000`)

## Rehearsal verdict

- Local dry run: COMPLETE
- Staging go/no-go: BLOCKED external (requires staging environment access + credentials + running services)

## Remaining to close P1-X9

1. Run this same sequence in staging.
2. Capture health endpoint 200 responses.
3. Attach Raj/Mira sign-off note to release evidence.
