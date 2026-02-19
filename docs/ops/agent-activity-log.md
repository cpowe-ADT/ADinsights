# Agent Activity Log

One-line, timestamped notes of agent-driven changes to help preserve context between sessions. Newest entries at the top.

## 2026-02-19

- 2026-02-19T15:31:40-0500 docs(meta): add reusable App Review copy pack to reduce rewrite cycles — Added `docs/runbooks/meta-app-review-copy-pack.md` with paste-ready permission use-case blocks and a fixed screencast storyboard; linked pack in submission checklist/validation runbook/profile/doc-index for repeatable future submissions. Pending commit.
- 2026-02-19T15:28:54-0500 docs(meta): tighten App Review reviewer-ready language — Strengthened use-case and screencast phrasing across Meta permission docs to explicitly include "on behalf of onboarded business customers" and "complete Facebook login process"; updated `docs/project/meta-permissions-catalog.yaml`, `docs/project/meta-permission-profile.md`, `docs/runbooks/meta-app-review-submission-checklist.md`, and `docs/runbooks/meta-app-review-validation.md`. Pending commit.
- 2026-02-19T15:20:35-0500 docs(meta): add lean Meta permission intelligence pack — Added `docs/project/meta-permissions-catalog.yaml` (active/near-term canonical scope model), `docs/project/meta-permission-profile.md` (runtime-gate precedence and deferred/out-of-scope policy), and `docs/runbooks/meta-app-review-submission-checklist.md`; updated `docs/runbooks/meta-app-review-validation.md`, `docs/project/phase1-execution-backlog.md` (DOC-META-1..4), and `docs/ops/doc-index.md`. Pending commit.

## 2026-02-17

- 2026-02-17T03:25:57-0500 docs(ops/skills): ship documentation signal quality pass across router/scope/contract/release — Added contract strict mode levels (`breaking_only`, `breaking_or_missing_docs`) with CI wired to fail on missing required contract docs, removed scope-owned contract doc prescriptions, introduced release `INFO` pending semantics + `pending_items`, added shared `contract-signal-patterns.yaml` used by router/scope with fallback behavior, updated golden cases/validators/workflow summaries, and refreshed ops docs/checklists. Pending commit.
- 2026-02-17T01:35:08-0500 ci(ops): harden contract/release workflows + lock gate policy docs — Added workflow-level `permissions`/`concurrency` and job timeouts in contract + release advisory workflows, tightened advisory path triggers to high-signal readiness surfaces, documented required-vs-advisory gate model in `docs/ops/doc-index.md`, and added weekly metrics loop in `docs/ops/ci-gate-review.md`. Pending commit.
- 2026-02-17T01:23:43-0500 ci(ops): add release readiness advisory workflow — Added `.github/workflows/release-readiness-advisory.yml` to run packet-chain preflight and publish advisory gate summaries on PRs, with artifacts for router/scope/contract/release packets. Pending commit.
- 2026-02-17T01:19:46-0500 docs(ops/ci): add contract-guard PR workflow + one-command preflight skillchain — Added `.github/workflows/contract-guard.yml` (strict CI contract gate on contract surfaces), created `run_preflight_skillchain.py` to chain router->scope->contract->release, added `make adinsights-preflight`, and updated `docs/ops/doc-index.md`. Pending commit.
- 2026-02-17T01:10:16-0500 docs(ops): ship skills wave 2 (router/gatekeeper stabilization + contract guard + release readiness) — Added router/gatekeeper schema-versioned packets with evidence and handoff fields, introduced `adinsights-contract-guard` and `adinsights-release-readiness` skills (rules, schemas, evaluators, validators, golden tests, sync scripts), and updated `docs/ops/doc-index.md`. Pending commit.
- 2026-02-17T00:42:10-0500 docs(ops): upgrade persona router to v2 + add scope gatekeeper skill — Added decision-packet router engine (`persona_router.py`), catalog stream/alias/confidence policy extensions, schema + golden tests, and created separate `adinsights-scope-gatekeeper` skill with rules engine, validators, golden tests, and sync script; updated `docs/ops/doc-index.md`. Pending commit.
- 2026-02-17T00:05:29-0500 docs(ops): add ADinsights persona router skill scaffold + references/scripts — Added `docs/ops/skills/adinsights-persona-router/` with `SKILL.md`, UI metadata, persona catalog, source map, report templates, sync/catalog-validation scripts, and `smoke_resolve_persona.py`; indexed skill in `docs/ops/doc-index.md`. Pending commit.

## 2026-02-05

- 2026-02-05T21:56:12-0500 docs(project): brand and upgrade stakeholder PPTX - Rebuilt `docs/project/adinsights-stakeholder-deck.pptx` with ADtelligent orange theme, enforced Calibri/Arial typography, generated branded chart/image assets, and added `docs/project/adinsights-deck-review.md` with consulting-style feedback and applied improvements. Pending commit.
- 2026-02-05T21:33:12-0500 docs(project): add stakeholder value slide deck - Added `docs/project/adinsights-stakeholder-deck.md` with a 16-slide narrative covering audience mapping, role-specific benefits, reliability/security posture, rollout, and decision asks; indexed in doc index. Pending commit.
- 2026-02-05T14:04:15-0500 docs(project): reconcile README + backlog status + frontend punch list — Updated README status text, marked frontend expansion backlog items done, and added MVP/Post-MVP punch list. Pending commit.

## 2026-02-04

- 2026-02-04T16:19:38-0500 docs(project): reconcile feature catalog + task breakdown — Updated built/in-progress/planned status and refreshed task breakdown current state/next steps after code audit. Pending commit.
- 2026-02-04T15:53:51-0500 feat(frontend/backend): add CSV upload templates + OpenAPI path check — Added downloadable CSV templates and UI links; added OpenAPI path test for uploads and schema serializers. Pending commit.
- 2026-02-04T15:44:14-0500 docs(runbooks): add CSV upload formats — Added `docs/runbooks/csv-uploads.md` and indexed it in doc index. Pending commit.
- 2026-02-04T15:14:10-0500 docs(runbooks): add quick demo + smoke checklist — Added `docs/runbooks/quick-demo.md` and `docs/runbooks/demo-smoke-checklist.md`, updated doc index. Pending commit.

## 2026-02-01

- 2026-02-01T04:01:41-0500 docs(project): refine finished frontend spec layout + module inventory — Added IA + module→route map, non-duplicative module feature inventory (roles/screens/components/data deps/acceptance), contract artifact index, and global non-happy-path UX standards. Pending commit.
- 2026-02-01T03:28:12-0500 docs(project): add integration API validation checklist + backlog rows — Added checklist template, linked to roadmap/task breakdown/doc index, and added Phase 1 connector backlog rows. Pending commit.
- 2026-02-01T03:23:48-0500 docs(project): add integration roadmap + prioritize connectors — Added `docs/project/integration-roadmap.md`, linked it in doc index/task breakdown/feature catalog. Pending commit.
- 2026-02-01T03:18:02-0500 docs(project): record frontend spec approval + add review checklist — Marked spec approved, added review checklist template, expanded Post-MVP sprint picks, and updated backlog/ownership map. Pending commit.
- 2026-02-01T03:06:54-0500 docs(project): add finished frontend spec + sprint picks — Added `docs/project/frontend-finished-product-spec.md`, wired into task/workstream/backlog docs, updated doc index, and logged review request for Lina/Joel. Pending commit.

## 2026-02-07

- 2026-02-07T19:08:27-0500 docs(runbooks): add external execution command pack — Added `docs/runbooks/external-actions-execution-checklist.md` with copy/paste commands for `S7-D`, `P1-X1`, `P1-X2`, `P1-X4`, `P1-X9`, and `P1-X5-signoff`; linked from `docs/runbooks/external-actions-aws.md` and indexed in `docs/ops/doc-index.md`. Pending commit.

## 2026-02-19

- 2026-02-19T20:30:00-0500 feat(meta-stabilization): fixed dbt Meta staging/snapshot blockers and hardened snapshot naming — Reworked `stg_meta_insights` JSON handling for DuckDB/Postgres compatibility, added reach fallback, renamed Meta snapshots to `meta_*_snapshot`, updated marts ref, and validated staging/snapshot/marts runs via dbt wrapper. Pending commit.
- 2026-02-19T20:30:00-0500 feat(frontend-meta): added resilient Meta Zustand states and UI handling — Added error classification for 401/403/429, stale data fallback, and actionable error messaging across Meta accounts/campaigns/insights screens with unit-test coverage. Pending commit.
- 2026-02-19T20:30:00-0500 test(qa): expanded Meta Playwright scenarios — Added OAuth callback success case plus explicit 403 permission-error coverage for insights dashboard. Pending commit.
- 2026-02-19T20:30:00-0500 docs(meta): added PR-track plan + validation evidence template and updated command contracts — Added Meta V3 PR tracks doc, evidence template path, and updated dbt command references to wrapper-based invocation in core docs. Pending commit.
- 2026-02-19T20:45:00-0500 docs(meta): added PR execution manifests + cross-stream sign-off checklist — Added per-track pathspec manifests, execution guide for folder-isolated PR staging, persisted preflight packets, and Raj/Mira sign-off checklist artifact. Pending commit.

## 2026-01-20

- 2026-01-20T23:31:00-0500 docs(ops): add observability runbooks + log schema guidance — Added alert thresholds/escalation runbook, metrics scrape validation steps, observability stability tests checklist, and log schema/cardinality guidance; updated doc index and alerting runbook links. Pending commit.
- 2026-01-20T23:36:28-0500 docs(ops): add Stream 6 definition of done — Documented completion checklist for observability & alerts; linked from workstreams and doc index. Pending commit.
- 2026-01-20T23:38:36-0500 feat(backend): add required log fields to JSON formatter — Ensure component, tenant_id, correlation_id, and task_id are always present; added log schema test. Pending commit.

## 2026-01-21

- 2026-01-21T00:29:54-0500 chore(backend): align dev Airbyte/Prometheus host access — Added AIRBYTE_API_URL/TOKEN and host.docker.internal to ALLOWED_HOSTS in backend dev env to support local Airbyte health checks and Prometheus scraping. Pending commit.

## 2025-12-23

- 2025-12-23T13:55:33-0500 ci(deploy): add docker compose smoke workflow — Added `.github/workflows/deploy-smoke.yml` to validate deploy compose and smoke-check `/api/health/` + `/api/timezone/` in CI; commit 32fd468.
- 2025-12-23T13:55:33-0500 test(qa): assert tenant switch fixture fallback — Strengthened Playwright smoke to confirm tenant switching works using `/mock/tenants.json` + `/sample_metrics.json` when APIs are unavailable; commit 7b03433.
- 2025-12-23T13:55:33-0500 feat(dbt): add tenant_id to meta/google staging — Added `tenant_id` columns + schema tests for Airbyte-shaped staging models; ran `dbt run/test --select staging`; commit ef8b7da.

## 2025-10-21

- 2025-10-21T14:38:25Z chore(tasks): propagate tenant context in background jobs — Ensure Celery tasks set/clear tenant context; add tests; commit 9e97840.
- 2025-10-21T14:32:39Z chore(tasks): schedule weekly DEK rotation — Add `rotate-tenant-deks` Celery beat entry (Sun 01:30 America/Jamaica) and docs; commit 5b3e695.
- 2025-10-21T14:28:39Z feat(core): correlation IDs + configurable KMS — Add `X-Correlation-ID` middleware, logging filter, Celery task correlation; introduce `KMS_PROVIDER=local` for dev/tests and keep AWS provider for prod; tests added; commit 1ddf0e2.
- 2025-10-21T15:10:00Z docs(ops): add doc index + link component READMEs — Created `docs/ops/doc-index.md` with cold-start prompt, doc map, and hygiene rules; indexed backend/frontend/dbt/Airbyte/deploy/QA/exporter/BI READMEs for quick navigation. Pending commit.
- 2025-10-21T15:18:00Z docs(ops): add session warm-up note & surface index — Added `docs/PROGRAM-NOTES.md` (orientation quick start), linked it from `README.md`, and indexed in `docs/ops/doc-index.md`. Pending commit.
- 2025-10-22T02:35:00Z feat(backend): snapshot retry backoff logging — Snapshot task now uses BaseAdInsightsTask retry_with_backoff with structured logging; tests updated; commit 5d4903e.
- 2025-10-22T02:40:00Z feat(frontend): snapshot freshness tooltip + adapter reload fixes — Added absolute timestamp formatting/tooltips for snapshot indicators, refined dataset adapter reload per tenant, removed duplicate status roles; tests/lint/build passing; commits c30546a, 128ee33.
- 2025-10-22T13:42:00Z feat(dbt/docs): parameterize freshness SLA and document overrides — Tightened Meta/Google freshness to hourly SLA via vars (`freshness_warn_hours`/`freshness_error_hours`), added dev override note in operations runbook; dbt runs green except local freshness (stale seeds). Commit pending.

## 2025-10-17 (prior session summary)

- feat(analytics): export metrics CSV from warehouse (replaced fake adapter), tests updated; commit b82f7c2.
- fix(airbyte): normalise millisecond timestamps in telemetry; commit db07a91.
- fix(health): surface Airbyte sync_failed / pending states in `/api/health/airbyte/` + tests; commit c607e6a.
- chore(dbt): DuckDB dev harness runs marts with full-refresh to avoid merge strategy issues; commit 1373afe.
- chore/docs/ops: added harness docs, Airbyte runbook updates, and archived 200+ legacy `codex/*` branches (see `docs/ops/branch-archive-log.md`).

## Operational actions (no code delta)

- Pruned all remote legacy branches on origin to reduce notification noise; only `origin/main` remains.
- Deleted stray local branch `feat/frontend-admin-bootstrap` and refreshed local remotes (`git remote prune origin`).
