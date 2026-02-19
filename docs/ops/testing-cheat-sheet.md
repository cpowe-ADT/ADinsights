# Testing Cheat Sheet (v0.1)

Purpose: quick test commands per workstream.

## Backend
- `ruff check backend`
- `pytest -q backend`
- `pytest -q backend/tests/test_social_status_api.py`
- `pytest -q backend/tests/test_meta_oauth_api.py`
- `pytest -q backend/tests/test_schema_regressions.py::test_openapi_schema_operation_ids_are_unique`

## Launcher / Local Stack
- `bash -n scripts/dev-launch.sh scripts/dev-healthcheck.sh`
- `scripts/dev-launch.sh --list-profiles`
- `scripts/dev-launch.sh --profile 2 --non-interactive --no-update --no-pull --no-open --no-healthcheck`
- `scripts/dev-launch.sh --profile 2 --non-interactive --no-update --no-pull --no-open` (includes demo-adapter verification)
- `scripts/dev-healthcheck.sh`
- `cat .dev-launch.active.env`

## Frontend
- `cd frontend && npm run lint`
- `cd frontend && npm test -- --run`
- `cd frontend && npm run build`
- `cd frontend && npm test -- --run src/pages/Home.test.tsx src/routes/__tests__/DataSources.test.tsx`

## dbt
- `make dbt-deps`
- `./scripts/dbt-wrapper.sh 'dbt' 'dbt' 'dbt' run --select staging`
- `./scripts/dbt-wrapper.sh 'dbt' 'dbt' 'dbt' snapshot`
- `./scripts/dbt-wrapper.sh 'dbt' 'dbt' 'dbt' run --select marts`

## Airbyte
- `docker login ghcr.io` (token with `read:packages`)
- `cd infrastructure/airbyte && docker compose config`

## AI Skills (Ops)
- `python3 docs/ops/skills/adinsights-persona-router/scripts/run_router_golden_tests.py`
- `python3 docs/ops/skills/adinsights-scope-gatekeeper/scripts/run_scope_golden_tests.py`
- `python3 docs/ops/skills/adinsights-contract-guard/scripts/run_contract_golden_tests.py`
- `python3 docs/ops/skills/adinsights-release-readiness/scripts/run_release_golden_tests.py`
- `python3 docs/ops/skills/adinsights-contract-guard/scripts/evaluate_contract.py --prompt "CI strict contract check" --changed-file backend/integrations/serializers.py --ci-strict-level breaking_or_missing_docs --format json`
- `make adinsights-preflight PROMPT="Assess release readiness for backend serializer changes"`

## CI Gate Model (main)
- Required: `Contract guard strict check`
- Advisory: `Release readiness advisory summary`
- Required strictness: `--ci-strict-level breaking_or_missing_docs`
- Advisory docs/tests semantics: pending items are `INFO`, not release warnings by default.
