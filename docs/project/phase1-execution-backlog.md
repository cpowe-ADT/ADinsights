# Phase 1 Execution Backlog (Single-Engineer Edition)

All Phase 0 review items have been mapped to concrete tasks below. Even though
each track has an owner persona, Codex executes every item sequentially while
mirroring the persona’s standards (tests, docs, reviewers). Keep work scoped to
the folder(s) listed for the stream and involve Raj/Mira only if a task must
touch multiple top-level folders.
External production actions must be tracked in `docs/runbooks/external-actions-aws.md`.

| ID | Stream | Acting Persona | Task | Priority | Dependencies | Tests / Commands | Status |
|----|--------|----------------|------|----------|--------------|------------------|--------|
| S1-A | Airbyte | Codex → Maya | Implement tenant-aware `BaseAdInsightsTask` + metrics emitters in `backend/integrations` + `backend/core/tasks.py`. | P1 | None; inform Priya before schema changes. | `ruff check backend`, `pytest backend/tests/test_airbyte_*.py` | Done (2025-01-05) |
| S1-B | Airbyte | Codex → Leo | Add telemetry API contract tests, pagination/auth coverage, refresh OpenAPI docs. | P1 | Depends on S1-A for consistent context IDs. | Same as above + `scripts/openapi.sh` if exists. | Done (2025-01-05) |
| S1-C | Airbyte | Codex → Maya | Document webhook runbook, rotate signing-secret sample in `.env.sample`. | P2 | After S1-A/B to capture final behavior. | Docs build (none). | Done (2025-01-05) |
| S2-A | dbt | Codex → Priya | Add tenant_id filters + schema tests to staging models; ensure `/api/metrics/combined/` columns stable. | P1 | Needs raw tables from Stream 1; start once S1-A/B complete. | `make dbt-deps && dbt run --select staging && dbt test` | Done (2025-12-23) |
| S2-B | dbt | Codex → Martin | Integrate dbt source freshness alerts + update runbook appendix. | P1 | After S2-A seeds success metrics. | `dbt source freshness`, update docs. | Done (2025-10-22) |
| S2-C | dbt | Codex → Priya | Maintain metrics column change log for backend/frontend consumers. | P2 (ongoing) | Parallel with S2-A/B. | Update `docs/project/vertical_slice_plan.md`/changelog. | Done (2026-01-22) |
| S3-A | Backend Metrics | Codex → Sofia | Ensure `snapshot_generated_at` timezone-aware; update serializers/tests. | P1 | Requires S2-A done; coordinate with Stream 4 for schema. | `ruff check backend && pytest backend/tests/test_metrics_api.py backend/tests/test_snapshot_task.py` | Done (2025-10-22) |
| S3-B | Backend Metrics | Codex → Andre | Add Celery retry/backoff with jitter + observability hooks for snapshot task. | P1 | After S3-A ensures schema stable; align with Leo for Celery base. | Same as above. | Done (2025-10-22) |
| S3-C | Backend Metrics | Codex → Sofia | Draft stale snapshot monitoring spec for Omar; update runbooks. | P2 | After S3-B instrumentation. | Docs update. | Done (2026-01-22) |
| S4-A | Frontend | Codex → Lina | Implement snapshot freshness banner tied to backend timestamp + QA notes. | P1 | Wait for S3-A payload finalization. | `npm run lint && npm test -- --run && npm run build` | Done (2025-10-22) |
| S4-B | Frontend | Codex → Joel | Add Playwright (or Cypress) smoke test for tenant switch + API fallback; wire into CI. | P1 | After S4-A baseline UI ready. | `npx playwright test` (or chosen runner). | Done (2025-12-23) |
| S4-C | Frontend | Codex → Lina | Update design-system plan & Storybook entries for dataset toggle + freshness states. | P2 | After S4-A/B. | `npm run storybook` (manual) + docs. | Done (2026-01-22) |
| S5-A | Secrets/KMS | Codex → Nina | Build rotation CLI/script + unit tests in `scripts/rotate_deks.py`. | P1 | None. | `ruff check backend`, `pytest backend/tests/test_dek_manager.py scripts/tests/test_rotate_deks.py` (if exists). | Done (2025-01-05) |
| S5-B | Secrets/KMS | Codex → Victor | Update `.env.sample`, docs, add detect-secrets rule for new vars. | P1 | After S5-A so variables finalized. | `detect-secrets scan` (if configured). | Done (2025-01-05) |
| S5-C | Secrets/KMS | Codex → Nina | Draft outage/alert runbook; coordinate thresholds with Omar. | P2 | After S5-A instrumentation and Stream 6 metrics available. | Docs update. | Done (2025-01-05) |
| S6-A | Observability | Codex → Omar | Implement Celery/dbt/Airbyte latency metrics + `/metrics/app/` smoke test. | P1 | Needs hooks from Streams 1–3; schedule accordingly. | `curl localhost:<port>/metrics/app/` + backend tests. | Done (2025-12-23) |
| S6-B | Observability | Codex → Hannah | Document alert thresholds, escalation contacts, link dashboards. | P2 | After S6-A metrics exist. | Docs update. | Done (2026-01-22) |
| S6-C | Observability | Codex → Omar | Add structured logging unit test validating tenant/task correlation IDs + schema doc. | P1 | Can run parallel with S6-A. | `pytest backend/core/tests/test_observability.py`. | Done (2025-01-05) |
| S7-A | BI/Deployment | Codex → Carlos | Export Superset/Metabase configs with redacted creds into `docs/BI/`. | P2 | After Streams 2–3 finalize models/metrics. | `docker compose config`, BI export scripts. | Done (2026-01-22) |
| S7-B | BI/Deployment | Codex → Mei | Add `docker compose config` + smoke job to CI; document. | P1 | Independent; ensure no cross-folder edits beyond deploy/docs. | `docker compose config`, CI pipeline run. | Done (2025-12-23) |
| S7-C | BI/Deployment | Codex → Carlos | Expand deployment runbook with rollback + health checklist. | P2 | After S7-B ensures smoke tests defined. | Docs update. | Done (2026-01-22) |
| S7-D | BI/Deployment | Codex → Mei | Verify SES sender identity + DMARC/DKIM for `adtelligent.net`, confirm final "from" address, and update runbook/env defaults. | P1 | Before production launch. | Manual SES checks + docs update. | Pending External Action (owner: Mei, deadline: 2026-02-10 EST, evidence: `docs/project/evidence/phase1-closeout/external/ses-verification-<date>-est.md`) |

## Phase 1 Closeout Roadmap (Master List)

Use this checklist to close Phase 1 end-to-end. It includes backlog items already tracked above plus
additional closeout items required for production launch readiness.

### A) Roadmap items already defined in Phase 1 backlog

1. **Airbyte connectors**
   - `S1-D` Complete Phase 1 API validation checklist for Microsoft/LinkedIn/TikTok.
   - `S1-E` Microsoft Ads connector plan.
   - `S1-F` LinkedIn Ads connector plan.
   - `S1-G` TikTok Ads connector plan.
2. **Production email readiness**
   - `S7-D` SES sender identity + DKIM/SPF/DMARC + sandbox exit + final from-address approval.

### B) Additional Phase 1 closeout items (recommended)

| ID | Stream | Task | Priority | Owner | Tests / Validation | Status |
|----|--------|------|----------|-------|--------------------|--------|
| P1-X1 | Secrets/KMS | Provision production AWS KMS key/alias and wire env in secret manager (`KMS_PROVIDER=aws`, real `KMS_KEY_ID`, `AWS_REGION`). | P1 | Nina + Victor | Backend boot with prod env; `python scripts/rotate_deks.py --dry-run`; `pytest backend/tests/test_dek_manager.py` | Pending External Action (deadline: 2026-02-10 EST, evidence: `docs/project/evidence/phase1-closeout/external/kms-provisioning-<date>-est.md`) |
| P1-X2 | Airbyte | Load real production Meta/Google credentials and run readiness sequence (`validate_tenant_config.py`, `verify_production_readiness.py`, `airbyte_health_check.py`). | P1 | Maya + Leo | `cd infrastructure/airbyte && docker compose config`; readiness scripts return success | Pending External Action (deadline: 2026-02-10 EST, evidence: `docs/project/evidence/phase1-closeout/external/airbyte-prod-readiness-<date>-est.md`) |
| P1-X3 | Backend | Execute prod smoke checks for CORS and throttles in staging/prod (`/api/token/`, `/api/auth/login/`, `/api/auth/password-reset/`), confirm expected `429`. | P1 | Sofia + Nina | `ruff check backend && pytest -q backend`; runtime smoke evidence in release notes | In Progress (automated tests green; staging runtime smoke pending) |
| P1-X4 | Observability | Confirm alerts for consecutive sync failures, unexpectedly empty syncs, and stale airbyte/dbt health. | P1 | Omar + Hannah | Alert simulation + dashboard evidence in `docs/ops/dashboard-links.md`; `python3 infrastructure/airbyte/scripts/verify_observability_prereqs.py` | Done (repo-side 2026-02-06); Pending External Action (deadline: 2026-02-11 EST, evidence: `docs/project/evidence/phase1-closeout/external/observability-simulation-<date>-est.md`) |
| P1-X5 | Release | Run production release checklist gate and capture sign-offs for Raj/Mira on cross-stream PRs. | P1 | Mei + Raj + Mira | `docs/runbooks/release-checklist.md` fully checked; links to merged PRs | Ready |
| P1-X6 | Security | Refresh `detect-secrets` baseline after final env placeholder changes and confirm no real credentials in repo. | P2 | Nina | `detect-secrets scan` (if configured), manual review | Done (2026-02-05 EST, baseline refreshed + changed-files hook check) |
| P1-X7 | Airbyte | Remove obsolete `version` key from `infrastructure/airbyte/docker-compose.yml` to keep compose output warning-free. | P3 | Maya | `cd infrastructure/airbyte && docker compose config` without warning | Done (2026-02-06) |
| P1-X8 | Governance | Enforce merge sequence for split Phase 1 branches and require Raj/Mira cross-stream review notes. | P1 | Mei + Raj | Branch governance + PR metadata validation | Done (2026-02-06) |
| P1-X9 | Release | Execute staging go/no-go rehearsal and archive evidence bundle. | P1 | Mei + Raj | Full checklist rehearsal in staging | Pending External Action (deadline: 2026-02-11 EST, evidence: `docs/project/evidence/phase1-closeout/external/staging-rehearsal-<date>-est.md`; local dry run completed 2026-02-05 EST) |
| P1-X10 | Cross-stream Contracts | Validate and lock Meta/Google/GA4/Search Console/CSV data contracts (matrix + automated checks + runbook parity). | P1 | Maya + Priya + Sofia + Raj + Mira | `python3 infrastructure/airbyte/scripts/check_data_contracts.py`; `pytest -q backend/tests/test_data_contract_checks.py`; folder test matrix | Done (2026-02-06, Phase 2 pilot paths added for GA4/Search Console) |

### C) Phase 1 final gate

Phase 1 can be considered complete only when all are true:

1. `S1-D`, `S1-E`, `S1-F`, `S1-G`, and `S7-D` are closed (or explicitly de-scoped with approval).
2. Additional closeout items `P1-X1` through `P1-X5` are complete.
3. Folder-level test matrix is green for touched areas:
   - Backend: `ruff check backend && pytest -q backend`
   - dbt: `make dbt-deps && DBT_PROFILES_DIR=dbt dbt run --project-dir dbt --select staging && DBT_PROFILES_DIR=dbt dbt snapshot --project-dir dbt && DBT_PROFILES_DIR=dbt dbt run --project-dir dbt --select marts`
   - Airbyte: `cd infrastructure/airbyte && docker compose config`
4. Release checklist is fully checked and linked to evidence.

### D) Phase 1 closeout tracker (live)

#### Merge sequence and reviewer assignments

1. `feat/phase1-dbt-demo-seeds`
2. `feat/phase1-backend-hardening`
3. `feat/phase1-airbyte-readiness`
4. `docs/phase1-readiness-updates`

Cross-stream requirement:
- Raj review required for sequencing/integration.
- Mira review required for architecture and cross-folder changes.

#### Evidence structure

- `docs/project/evidence/phase1-closeout/backend/`
- `docs/project/evidence/phase1-closeout/dbt/`
- `docs/project/evidence/phase1-closeout/airbyte/`
- `docs/project/evidence/phase1-closeout/external/`
- `docs/project/evidence/phase1-closeout/release/`

#### Step status (2026-02-06)

| Step | Status | Notes |
|------|--------|-------|
| Step 1 Governance and branch integration | Done | Merge order documented; Raj/Mira requirement recorded. |
| Step 2 Connector validation (`S1-D`) | Done | Checklist fields completed for Microsoft/LinkedIn/TikTok. |
| Step 3 Connector plans (`S1-E/F/G`) | Done (planning deliverables) | Decisions, schedules, retries, test matrix documented. |
| Step 4 External prereqs (`S7-D`, `P1-X1`, `P1-X2`) | Pending External Action | Requires AWS/SES/Airbyte production credentials and operator execution; track in `docs/runbooks/external-actions-aws.md`. |
| Step 5 Runtime hardening verification (`P1-X3`) | In Progress | `ruff` + `pytest -q backend` green on 2026-02-06; staging smoke still required for final close. |
| Step 6 Observability and alert gates (`P1-X4`) | Done (repo-side); Pending External Action | Local verifier + runbook/templates added; external monitor firing evidence still required. |
| Step 7 Security and compose hygiene (`P1-X6`, `P1-X7`) | Done | `P1-X7` complete (compose warning removed); `P1-X6` baseline refreshed and validated on changed files. |
| Step 8 Staging rehearsal (`P1-X9`) | Pending External Action | Local dry run executed with evidence; final staging run needs environment access and production-like credentials. |
| Step 9 Final release gate (`P1-X5`) | Pending | Can only close after external blockers resolve or approved de-scope recorded. |
| Step 10 Data-contract validation (`P1-X10`) | Done | Cross-stream contract matrix, API/dbt/airbyte alignment, and pilot GA4/Search Console paths updated; Raj/Mira review notes required at PR time. |

#### External de-scope / sign-off log (strict finish policy)

| Item | Current state | Required approvers | Status |
|------|---------------|--------------------|--------|
| `S7-D` SES production sender verification | Pending operator execution in AWS SES + DNS | Mei + Raj + Mira + Security owner | Pending External Action (deadline: 2026-02-10 EST) |
| `P1-X1` KMS production key provisioning | Pending operator execution in AWS KMS + secret manager | Nina + Victor + Raj | Pending External Action (deadline: 2026-02-10 EST) |
| `P1-X2` Airbyte production credential readiness | Pending operator execution in Airbyte target env | Maya + Leo + Raj | Pending External Action (deadline: 2026-02-10 EST) |
| `P1-X4` Alert simulation in production observability stack | Repo-side complete; monitor firing proof pending | Omar + Hannah + Raj | Pending External Action (deadline: 2026-02-11 EST) |
| `P1-X9` Staging go/no-go rehearsal | Pending operator execution in staging | Mei + Raj + Mira | Pending External Action (deadline: 2026-02-11 EST) |

#### Daily closeout tracker

| ID | owner | last update | next action | risk |
|----|-------|-------------|-------------|------|
| `S7-D` | Mei | 2026-02-06 EST | Complete SES identity/DKIM/SPF/DMARC and sandbox exit; attach template evidence. | Email sending blocked for production launch. |
| `P1-X1` | Nina + Victor | 2026-02-06 EST | Provision KMS key/alias, wire env vars in secret manager, run rotation dry run evidence. | Credential encryption path not production-ready. |
| `P1-X2` | Maya + Leo | 2026-02-06 EST | Inject production Meta/Google credentials and run readiness scripts. | No live ad data ingestion in production. |
| `P1-X4` | Omar + Hannah | 2026-02-06 EST | Run staging alert simulations using new runbook and attach evidence. | Alerting SLA unverified in real stack. |
| `P1-X9` | Mei + Raj | 2026-02-06 EST | Execute full staging go/no-go rehearsal and rollback check. | Release gate cannot move to READY. |

## Meta Permission Governance Backlog (Docs-Only)

| ID | Stream | Acting Persona | Task | Priority | Dependencies | Tests / Commands | Status |
|----|--------|----------------|------|----------|--------------|------------------|--------|
| DOC-META-1 | Docs Governance | Codex -> Maya | Baseline and maintain `docs/project/meta-permissions-catalog.yaml` as canonical active/near-term Meta permission source. | P2 | Keep aligned with runtime gate and default OAuth scope docs. | Docs-only consistency check against `backend/integrations/views.py`, `backend/core/settings.py`, and `backend/.env.sample`. | Planned (2026-02-19) |
| DOC-META-2 | Docs Governance | Codex -> Omar | Maintain App Review use-case and screencast checklist for all `required_now` and active `optional_near_term` permissions. | P2 | Depends on DOC-META-1 schema stability. | Runbook review: `docs/runbooks/meta-app-review-submission-checklist.md` completeness and evidence fields. | Planned (2026-02-19) |
| DOC-META-3 | Docs Governance | Codex -> Sofia | Run quarterly permission drift review across runtime gate, requested default scopes, and runbooks. | P2 | Depends on DOC-META-1 and DOC-META-2. | Manual drift audit of `backend/integrations/views.py`, `backend/core/settings.py`, `.env.sample`, and linked docs. | Planned (2026-02-19) |
| DOC-META-4 | Docs Governance | Codex -> Mei | Enforce release gate rule: when Meta scopes/gates change, update catalog + profile + submission checklist in same PR. | P1 | Depends on DOC-META-1..3 process adoption. | PR checklist validation using `docs/runbooks/release-checklist.md` plus docs diff audit. | Planned (2026-02-19) |

## Frontend Expansion Backlog (Post-Phase 1 Draft)

| ID | Stream | Acting Persona | Task | Priority | Dependencies | Tests / Commands | Status |
|----|--------|----------------|------|----------|--------------|------------------|--------|
| S4-D | Frontend | Codex -> Lina | Publish finished frontend product spec and review gate (Lina/Joel sign-off). | P1 | None; align with `docs/workstreams.md` and `docs/task_breakdown.md`. | Docs update. | Approved (2026-02-01) |
| S4-E | Frontend | Codex -> Lina | Pick A: build data sources management UI (connections list + summary + detail). | P2 | Requires Airbyte connection APIs. | `npm run lint && npm test -- --run && npm run build` | Done (2026-02-04) |
| S4-F | Frontend | Codex -> Lina | Implement dashboard library, report builder, exports, alerts, AI summaries UI. | P2 | Requires report/alert endpoints and export tooling. | `npm run lint && npm test -- --run && npm run build` | Done (2026-02-06, API-backed routes shipped) |
| S4-G | Frontend | Codex -> Lina | Pick B: deliver sync health + telemetry view. | P2 | Requires `/api/airbyte/telemetry/` + `/api/health/airbyte/`. | `npm run lint && npm test -- --run && npm run build` | Done (2026-02-06) |
| S4-H | Frontend | Codex -> Lina | Pick C: health checks overview (API/airbyte/dbt/timezone). | P2 | Requires health endpoints. | `npm run lint && npm test -- --run && npm run build` | Done (2026-02-06) |
| S4-I | Frontend | Codex -> Lina | CSV upload wizard (mapping, validation, job status). | P2 | Requires CSV upload + job status endpoints. | `npm run lint && npm test -- --run && npm run build` | Done (2026-02-04) |
| S4-J | Frontend | Codex -> Lina | Admin audit log view (filters + export). | P2 | Requires audit log endpoints. | `npm run lint && npm test -- --run && npm run build` | Done (2026-02-06) |
| S4-K | Frontend | Codex -> Lina | Enterprise UAC UX (approvals, board packs, impersonation, access review, why denied). | P3 | Requires UAC workflow endpoints and entitlements. | `npm run lint && npm test -- --run && npm run build` | Planned |

## Integrations Expansion Backlog (Phase 1 Connectors)

| ID | Stream | Acting Persona | Task | Priority | Dependencies | Tests / Commands | Status |
|----|--------|----------------|------|----------|--------------|------------------|--------|
| S1-D | Airbyte | Codex -> Maya | Complete Phase 1 API validation checklist (Microsoft Ads, LinkedIn Ads, TikTok Ads). | P1 | Use `docs/project/integration-api-validation-checklist.md`. | Docs update. | Done (2026-02-06) |
| S1-E | Airbyte | Codex -> Maya | Microsoft Advertising connector plan (Airbyte vs custom) + schedule metadata. | P2 | Depends on S1-D; coordinate with Priya/Sofia for schema impact. | `ruff check backend`, `pytest backend/tests/test_airbyte_*.py`, `docker compose config` | Done (2026-02-06, planning) |
| S1-F | Airbyte | Codex -> Maya | LinkedIn Ads connector plan (approval + limits) + schedule metadata. | P2 | Depends on S1-D; partner approval may gate build. | `ruff check backend`, `pytest backend/tests/test_airbyte_*.py`, `docker compose config` | Done (2026-02-06, planning) |
| S1-G | Airbyte | Codex -> Maya | TikTok Ads connector plan (token lifecycle) + schedule metadata. | P2 | Depends on S1-D; confirm refresh token behavior. | `ruff check backend`, `pytest backend/tests/test_airbyte_*.py`, `docker compose config` | Done (2026-02-06, planning) |

**Execution Notes**
- Work roughly follows the dependency chain: Stream 1 → Stream 2 → Stream 3 → Stream 4, while Streams 5–7 run in parallel when they don’t block others.
- For each item, update the relevant log (e.g., `docs/logs/project-worklog.md` or stream-specific log) when started/completed to preserve historical context.
- If a task must modify more than one top-level folder, treat that as a cross-stream change: loop in Raj (integration) and Mira (architecture) for review, even if Codex performs the work.
- Keep status fields updated (TODO → In Progress → Done) as work proceeds to maintain a live backlog without needing an external tracker.
