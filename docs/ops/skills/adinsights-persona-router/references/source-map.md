# ADinsights Persona Source Map

Use this map to keep persona simulation anchored to canonical repo sources.

## Canonical Context Sequence

1. `AGENTS.md`
2. `docs/ops/doc-index.md`
3. `docs/workstreams.md`
4. `docs/project/phase0-backlog-validation.md`
5. `docs/project/phase0-simulated-reviews.md`
6. `docs/project/feature-ownership-map.md`
7. `docs/project/phase1-execution-backlog.md`

## Domain Routing Map

| Domain                          | Primary personas | Backup personas | Scope hints                                                                 | Canonical tests                                                                                                                                         |
| ------------------------------- | ---------------- | --------------- | --------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Airbyte ingestion and telemetry | Maya             | Leo             | `backend/integrations/`, `backend/core/tasks.py`, `infrastructure/airbyte/` | `ruff check backend`, `pytest backend/tests/test_airbyte_*.py`, `cd infrastructure/airbyte && docker compose config`                                    |
| dbt modeling and marts          | Priya            | Martin          | `dbt/`                                                                      | `make dbt-deps`, `dbt --project-dir dbt run --select staging`, `dbt snapshot`, `dbt --project-dir dbt run --select marts`, `dbt --project-dir dbt test` |
| Backend metrics and snapshots   | Sofia            | Andre           | `backend/analytics/`, `backend/adapters/`                                   | `ruff check backend`, `pytest backend/tests/test_metrics_api.py backend/tests/test_snapshot_task.py backend/tests/test_analytics_endpoints.py`          |
| Frontend UX and design system   | Lina             | Joel            | `frontend/src/`                                                             | `cd frontend && npm test -- --run`, `cd frontend && npm run build`                                                                                      |
| Secrets and KMS                 | Nina             | Victor          | `backend/core/crypto/`, `scripts/`                                          | `ruff check backend`, `pytest backend/tests/test_dek_manager.py scripts/tests/test_rotate_deks.py`                                                      |
| Observability and alerts        | Omar             | Hannah          | `backend/core/observability.py`, `docs/runbooks/`                           | `ruff check backend`, `pytest backend/core/tests/test_observability.py`                                                                                 |
| BI and deployment               | Carlos           | Mei             | `deploy/`, `docs/BI/`, `docs/runbooks/deployment.md`                        | `docker compose config`                                                                                                                                 |

## Escalation Routing

- Route to Raj for any change touching more than one top-level folder.
- Route to Raj for API-contract changes consumed by another stream.
- Route to Mira for cross-cutting refactors, architecture shifts, or stack-level decisions.

## Folder to Persona Hints

- `backend/integrations/` -> Maya/Leo
- `backend/analytics/` or `backend/adapters/` -> Sofia/Andre
- `frontend/src/` -> Lina/Joel
- `dbt/` -> Priya/Martin
- `backend/core/crypto/` or `scripts/rotate_deks.py` -> Nina/Victor
- `backend/core/observability.py` or `docs/runbooks/alerting.md` -> Omar/Hannah
- `deploy/` or `docs/BI/` -> Carlos/Mei

When hints match multiple domains, choose the highest-risk domain first and state assumptions.
