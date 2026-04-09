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

Supported local live-Meta recipe:

```bash
ENABLE_WAREHOUSE_ADAPTER=1 \
ENABLE_DEMO_ADAPTER=1 \
ENABLE_FAKE_ADAPTER=0 \
FRONTEND_BASE_URL=http://localhost:5173 \
scripts/dev-launch.sh --profile 1 --strict-profile --non-interactive --no-update --no-pull --no-open
```

Notes:

- Use `http://localhost:5173` as the canonical local OAuth host unless you have updated the Meta app
  domains and valid redirect URIs for a different host/port.
- `GET /api/datasets/status/` is the source of truth for live dashboard readiness.
- `GET /api/integrations/social/status/` is the source of truth for connection/auth state.
- Meta triage order:
  - `GET /api/integrations/social/status/`
  - `GET /api/datasets/status/`
  - `GET /api/meta/accounts/`
  - `GET /api/meta/pages/`
  - `GET /api/metrics/combined/`
- Use exactly one primary diagnosis:
  - `auth/setup failure`
  - `permission failure`
  - `asset discovery failure`
  - `direct sync failure`
  - `warehouse adapter disabled`
  - `missing/stale/default snapshot`

## Frontend

- `cd frontend && npm run lint`
- `cd frontend && npm test -- --run`
- `cd frontend && npm run build`
- `cd frontend && npm test -- --run src/pages/Home.test.tsx src/routes/__tests__/DataSources.test.tsx`

## dbt

- `make dbt-deps`
- `./scripts/dbt-wrapper.sh 'dbt' 'dbt' 'dbt' run --select staging`
- `./scripts/dbt-wrapper.sh 'dbt' 'dbt' 'dbt' snapshot`
- `./scripts/dbt-wrapper.sh 'dbt' 'dbt' 'dbt' run --select all_ad_performance dim_campaign fact_performance`
- `./scripts/dbt-wrapper.sh 'dbt' 'dbt' 'dbt' run --select marts`
- `./scripts/dbt-wrapper.sh 'dbt' 'dbt' 'dbt' test --select all_ad_performance dim_campaign fact_performance vw_campaign_daily`

When a dbt change adds or propagates mart-facing columns through the reference layer, rebuild the
reference models before `run --select marts` so incremental marts do not read stale upstream schemas.

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
