# Meta Integration V3 PR Tracks (Stabilize-First)

Scope date: 2026-02-19 (America/Jamaica).

## Reviewer matrix

- Cross-stream integration: Raj
- Architecture risk and refactor oversight: Mira
- Backend API + OAuth/sync: Sofia
- Integrations/Airbyte provisioning: Maya
- dbt models/snapshots/marts: Priya
- Frontend UX/state handling: Lina

## Folder-isolated PR tracks

1. `backend/`
- Purpose: stabilize `/api/meta/*`, OAuth scope gating, sync lifecycle, retry/backoff, and tenant-safe persistence.
- Required checks: `ruff check backend && pytest -q backend`.
- Owner review: Sofia + Maya.

2. `dbt/`
- Purpose: fix staging/snapshot compatibility and harden Meta marts (`campaign history`, `daily performance`, `ad performance`).
- Required checks:
  - `make dbt-deps`
  - `./scripts/dbt-wrapper.sh 'dbt' 'dbt' 'dbt' run --select staging`
  - `./scripts/dbt-wrapper.sh 'dbt' 'dbt' 'dbt' snapshot`
  - `./scripts/dbt-wrapper.sh 'dbt' 'dbt' 'dbt' run --select marts`
- Owner review: Priya.

3. `frontend/`
- Purpose: resilient Meta state handling (`loading`, `stale`, `retry`, `permission`, `token-expired`) and route integration.
- Required checks: `cd frontend && npm ci && npm test -- --run && npm run build`.
- Owner review: Lina.

4. `infrastructure/airbyte/`
- Purpose: template/provisioning parity and contract checks without secret leakage.
- Required checks:
  - `cd infrastructure/airbyte && docker compose config`
  - `python3 infrastructure/airbyte/scripts/check_data_contracts.py`
- Owner review: Maya.

5. `qa/`
- Purpose: Playwright coverage for OAuth callback success/missing-scope paths and 429/403 UI behavior.
- Required checks: `cd qa && npx playwright test tests/meta-integration.spec.ts`.
- Owner review: Lina + Sofia.

6. `docs/`
- Purpose: contract log, matrix, operations runbook, and app-review validation evidence pack.
- Required docs:
  - `docs/project/api-contract-changelog.md`
  - `docs/project/integration-data-contract-matrix.md`
  - `docs/runbooks/operations.md`
  - `docs/runbooks/meta-app-review-validation.md`
- Owner review: Raj + Mira.

## Cross-stream gate

Before release sign-off:

1. All folder tracks merged with their folder-specific checks green.
2. Staging operator validation completed against a fresh Meta Test App.
3. Evidence artifact committed under `docs/project/evidence/meta-validation/<timestamp>.md`.
4. Raj and Mira confirm cross-stream contract freeze and rollout readiness.
