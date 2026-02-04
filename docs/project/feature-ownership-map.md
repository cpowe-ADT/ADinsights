# Feature Ownership Map (v0.1)

Purpose: quick reference for who owns which feature domains, and which tests/runbooks must be updated.
Use this to assign sprint tasks and route reviews.

## Domains → Owners
### Airbyte Ingestion
- Owner: Maya (Primary), Leo (Backup)
- Scope: `backend/integrations/`, `infrastructure/airbyte/`
- Tests: `ruff check backend`, `pytest backend/tests/test_airbyte_*.py`, `docker compose config`
- Runbooks: `docs/runbooks/operations.md`, `docs/runbooks/alerting.md`

### dbt Modeling
- Owner: Priya (Primary), Martin (Backup)
- Scope: `dbt/`
- Tests: `make dbt-deps`, `dbt run --select staging`, `dbt snapshot`, `dbt run --select marts`, `dbt test`
- Runbooks: `docs/runbooks/operations.md`

### Backend Metrics + Snapshots
- Owner: Sofia (Primary), Andre (Backup)
- Scope: `backend/analytics/`, `backend/adapters/`
- Tests: `ruff check backend`, `pytest backend/tests/test_metrics_api.py backend/tests/test_snapshot_task.py backend/tests/test_analytics_endpoints.py`
- Runbooks: `docs/runbooks/operations.md`, `docs/runbooks/alerting.md`

### Frontend Experience
- Owner: Lina (Primary), Joel (Backup)
- Scope: `frontend/src/`
- Tests: `npm test -- --run`, `npm run build`
- Runbooks: `docs/design-system.md`, `frontend/DESIGN_SYSTEM.md`,
  `docs/project/frontend-finished-product-spec.md`, `docs/project/frontend-spec-review-checklist.md`

### Secrets & KMS
- Owner: Nina (Primary), Victor (Backup)
- Scope: `backend/core/crypto/`, `scripts/`
- Tests: `ruff check backend`, `pytest backend/tests/test_dek_manager.py scripts/tests/test_rotate_deks.py`
- Runbooks: `docs/runbooks/operations.md`

### Observability & Alerts
- Owner: Omar (Primary), Hannah (Backup)
- Scope: `backend/core/observability.py`, `docs/runbooks/`
- Tests: `pytest backend/core/tests/test_observability.py`
- Runbooks: `docs/runbooks/alerting.md`, `docs/runbooks/operations.md`

### BI & Deployment
- Owner: Carlos (Primary), Mei (Backup)
- Scope: `deploy/`, `bi/`, `docs/runbooks/deployment.md`
- Tests: `docker compose config`
- Runbooks: `docs/runbooks/deployment.md`

## Review Routing
- Cross-folder changes require Raj (Integration) + Mira (Architecture).
- Always update the relevant runbook when behavior changes.
