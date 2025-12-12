# Phase 1 Execution Backlog (Single-Engineer Edition)

All Phase 0 review items have been mapped to concrete tasks below. Even though
each track has an owner persona, Codex executes every item sequentially while
mirroring the persona’s standards (tests, docs, reviewers). Keep work scoped to
the folder(s) listed for the stream and involve Raj/Mira only if a task must
touch multiple top-level folders.

| ID | Stream | Acting Persona | Task | Priority | Dependencies | Tests / Commands | Status |
|----|--------|----------------|------|----------|--------------|------------------|--------|
| S1-A | Airbyte | Codex → Maya | Implement tenant-aware `BaseAdInsightsTask` + metrics emitters in `backend/integrations` + `backend/core/tasks.py`. | P1 | None; inform Priya before schema changes. | `ruff check backend`, `pytest backend/tests/test_airbyte_*.py` | Done (2025-01-05) |
| S1-B | Airbyte | Codex → Leo | Add telemetry API contract tests, pagination/auth coverage, refresh OpenAPI docs. | P1 | Depends on S1-A for consistent context IDs. | Same as above + `scripts/openapi.sh` if exists. | Done (2025-01-05) |
| S1-C | Airbyte | Codex → Maya | Document webhook runbook, rotate signing-secret sample in `.env.sample`. | P2 | After S1-A/B to capture final behavior. | Docs build (none). | Done (2025-01-05) |
| S2-A | dbt | Codex → Priya | Add tenant_id filters + schema tests to staging models; ensure `/api/metrics/combined/` columns stable. | P1 | Needs raw tables from Stream 1; start once S1-A/B complete. | `make dbt-deps && dbt run --select staging && dbt test` | TODO |
| S2-B | dbt | Codex → Martin | Integrate dbt source freshness alerts + update runbook appendix. | P1 | After S2-A seeds success metrics. | `dbt source freshness`, update docs. | TODO |
| S2-C | dbt | Codex → Priya | Maintain metrics column change log for backend/frontend consumers. | P2 (ongoing) | Parallel with S2-A/B. | Update `docs/project/vertical_slice_plan.md`/changelog. | TODO |
| S3-A | Backend Metrics | Codex → Sofia | Ensure `snapshot_generated_at` timezone-aware; update serializers/tests. | P1 | Requires S2-A done; coordinate with Stream 4 for schema. | `ruff check backend && pytest backend/tests/test_metrics_api.py backend/tests/test_snapshot_task.py` | Done (2025-10-22) |
| S3-B | Backend Metrics | Codex → Andre | Add Celery retry/backoff with jitter + observability hooks for snapshot task. | P1 | After S3-A ensures schema stable; align with Leo for Celery base. | Same as above. | Done (2025-10-22) |
| S3-C | Backend Metrics | Codex → Sofia | Draft stale snapshot monitoring spec for Omar; update runbooks. | P2 | After S3-B instrumentation. | Docs update. | TODO |
| S4-A | Frontend | Codex → Lina | Implement snapshot freshness banner tied to backend timestamp + QA notes. | P1 | Wait for S3-A payload finalization. | `npm run lint && npm test -- --run && npm run build` | Done (2025-10-22) |
| S4-B | Frontend | Codex → Joel | Add Playwright (or Cypress) smoke test for tenant switch + API fallback; wire into CI. | P1 | After S4-A baseline UI ready. | `npx playwright test` (or chosen runner). | TODO |
| S4-C | Frontend | Codex → Lina | Update design-system plan & Storybook entries for dataset toggle + freshness states. | P2 | After S4-A/B. | `npm run storybook` (manual) + docs. | TODO |
| S5-A | Secrets/KMS | Codex → Nina | Build rotation CLI/script + unit tests in `scripts/rotate_deks.py`. | P1 | None. | `ruff check backend`, `pytest backend/tests/test_dek_manager.py scripts/tests/test_rotate_deks.py` (if exists). | Done (2025-01-05) |
| S5-B | Secrets/KMS | Codex → Victor | Update `.env.sample`, docs, add detect-secrets rule for new vars. | P1 | After S5-A so variables finalized. | `detect-secrets scan` (if configured). | Done (2025-01-05) |
| S5-C | Secrets/KMS | Codex → Nina | Draft outage/alert runbook; coordinate thresholds with Omar. | P2 | After S5-A instrumentation and Stream 6 metrics available. | Docs update. | Done (2025-01-05) |
| S6-A | Observability | Codex → Omar | Implement Celery/dbt/Airbyte latency metrics + `/metrics/app/` smoke test. | P1 | Needs hooks from Streams 1–3; schedule accordingly. | `curl localhost:<port>/metrics/app/` + backend tests. | TODO |
| S6-B | Observability | Codex → Hannah | Document alert thresholds, escalation contacts, link dashboards. | P2 | After S6-A metrics exist. | Docs update. | TODO |
| S6-C | Observability | Codex → Omar | Add structured logging unit test validating tenant/task correlation IDs + schema doc. | P1 | Can run parallel with S6-A. | `pytest backend/core/tests/test_observability.py`. | Done (2025-01-05) |
| S7-A | BI/Deployment | Codex → Carlos | Export Superset/Metabase configs with redacted creds into `docs/BI/`. | P2 | After Streams 2–3 finalize models/metrics. | `docker compose config`, BI export scripts. | TODO |
| S7-B | BI/Deployment | Codex → Mei | Add `docker compose config` + smoke job to CI; document. | P1 | Independent; ensure no cross-folder edits beyond deploy/docs. | `docker compose config`, CI pipeline run. | TODO |
| S7-C | BI/Deployment | Codex → Carlos | Expand deployment runbook with rollback + health checklist. | P2 | After S7-B ensures smoke tests defined. | Docs update. | TODO |

**Execution Notes**
- Work roughly follows the dependency chain: Stream 1 → Stream 2 → Stream 3 → Stream 4, while Streams 5–7 run in parallel when they don’t block others.
- For each item, update the relevant log (e.g., `docs/logs/project-worklog.md` or stream-specific log) when started/completed to preserve historical context.
- If a task must modify more than one top-level folder, treat that as a cross-stream change: loop in Raj (integration) and Mira (architecture) for review, even if Codex performs the work.
- Keep status fields updated (TODO → In Progress → Done) as work proceeds to maintain a live backlog without needing an external tracker.
