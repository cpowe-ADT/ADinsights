# Content Operations Implementation Backlog

Status: active implementation
Related:

- `docs/project/content-operations-meta-publishing-spec.md`
- `docs/project/content-operations-architecture-sprint-plan.md`
- `docs/project/content-operations-sprint0-decisions.md`
- `docs/project/api-contract-changelog.md`
- `docs/project/integration-data-contract-matrix.md`

Timezone baseline: `America/Jamaica`
Last updated: 2026-06-06

## Purpose

Convert the Content Operations architecture into concrete, owner-routed work tickets that coding
agents can execute one slice at a time.

This backlog is implementation-ready and now active for bounded backend/docs/frontend slices. Keep
external Meta App Review, full frontend rollout, live AI provider calls, live provider adapters,
and live publishing runtime behind explicit follow-up tickets and reviewer signoff.

## Audit Summary

The previous docs covered product scope, API proposals, data models, state machines, evals,
architecture, reviewers, and sprint sequencing. The missing implementation layer was:

- ticket IDs and dependency order
- exact owner/reviewer routing per feature
- Definition of Ready by scope
- acceptance criteria that coding agents can test
- feature flags and rollout gates per ticket
- clear separation between repo-ready work and external/App Review blockers
- first-code ticket recommendation

This document fills those gaps.

## Implementation Status

| Ticket          | Status  | Date       | Notes                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| --------------- | ------- | ---------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| CO-SPEC-AUDIT   | Done    | 2026-06-06 | Reconciled docs/spec/ticket/prompt planning, added build control sheet, next-slice order, reviewer scorecards, gap audit, and ticket prompt pack. Docs-only; no runtime behavior changed.                                                                                                                                                                                                                                                                                                                        |
| CO-1A           | Done    | 2026-06-05 | Added backend `content_ops` Django app, tenant-scoped model foundation, initial migration, and focused model tests. No API, frontend, AI provider, Meta publishing, scheduler, or runtime OAuth scope changes were added.                                                                                                                                                                                                                                                                                        |
| CO-1B           | Done    | 2026-06-10 | Added tenant-scoped serializers, DRF viewsets, `/api/content-ops/` router, draft version/approval/schedule workflow actions, inert publish/retry/metric-refresh stubs, focused API tests, and OpenAPI path/action/enum regression coverage. Full custom response schema fidelity remains follow-up for readiness/reporting actions. No Meta calls, AI provider calls, scheduler tasks, frontend clients, OAuth scope changes, or dbt models were added in the original slice.                                    |
| CO-1C           | Done    | 2026-06-05 | Added module-local role gates for read, edit, internal approval, client approval, publishing actions, and publishing identity mutation, with focused permission tests.                                                                                                                                                                                                                                                                                                                                           |
| CO-1D           | Done    | 2026-06-05 | Added `GET /api/content-ops/readiness/` with separate Meta auth, Page selection, Instagram linkage, Facebook publishing, Instagram publishing, and reporting axes. No existing Meta/social/dataset readiness payload changed.                                                                                                                                                                                                                                                                                    |
| CO-1E           | Partial | 2026-06-05 | Added safe audit events for version creation, active-version changes, approval requests/decisions, scheduling, unscheduling, and generation-job cancellation. Role-specific audit coverage and full event catalog tests remain follow-up work.                                                                                                                                                                                                                                                                   |
| CO-3A           | Done    | 2026-06-06 | Added queued caption-generation endpoint, schema validator, disabled-by-default provider boundary, injected fake-provider processor, generated draft/version creation, and task wrapper. No live OpenAI/API provider call, graphic generation, approval, schedule, publish, frontend, or dbt work was added.                                                                                                                                                                                                     |
| CO-3B           | Done    | 2026-06-06 | Added prompt and tone override redaction before queued job storage/provider payload handoff, direct generation summary redaction, safe failure details, and no-secret tests.                                                                                                                                                                                                                                                                                                                                     |
| CO-3E           | Done    | 2026-06-06 | Added deterministic caption schema, redaction, blocked-term, required-term, disabled-provider, no-side-effect backend tests, plus a tenant-safe golden fixture harness that runs without network/provider calls. Remote model/provider quality scoring remains a later provider-tuning concern.                                                                                                                                                                                                                  |
| CO-4C           | Done    | 2026-06-10 | Added client-safe JSON content-plan export at `/api/content-ops/exports/content-plan/` plus persisted export artifact create/list/retrieve/download paths. Frontend export history and richer PDF/CSV/ZIP packet formats remain follow-up.                                                                                                                                                                                                                                                                       |
| CO-5B           | Done    | 2026-06-05 | Added Facebook Page publish preflight service with tenant, channel, state, active-version, client-approval snapshot, publishing identity, readiness, and content checks plus safe failure-code tests. No token decryption, Graph publishing, provider adapter, attempt mutation, Instagram container flow, Celery beat activation, or metric refresh added.                                                                                                                                                      |
| CO-5C           | Partial | 2026-06-10 | Added fakeable Facebook Page attempt processor and disabled-by-default publisher boundary. Injected publisher success creates `PublishedPost` and updates attempt/schedule/draft state; retryable/terminal failures are sanitized. A due queued-attempt processor scan is active. Live Graph provider adapter, token decryption, and App Review evidence remain blocked.                                                                                                                                         |
| CO-5D           | Done    | 2026-06-10 | Added safe app-owned due-schedule dispatcher, due-dispatch Celery task, single-attempt processor task, requeue-only retry endpoint, due-retry requeue scanner/task, queue filters for schedule window/retry due attempts, and every-minute due/retry/process Celery beat scans. Provider boundaries remain disabled by default; no live Graph publishing is active.                                                                                                                                              |
| CO-5D-hardening | Partial | 2026-06-10 | Hardened public asset updates so storage/runtime metadata stays server-owned, made publishing readiness fail closed unless selected publishing identities are explicitly `ready`, froze schedule targets in `approval_snapshot.target_channels` so dispatch uses snapshotted Page/IG destinations rather than mutable workspace defaults, and added OpenAPI path/action/enum assertions. Client approval assignment scoping, full custom response schema fidelity, and observability hardening remain follow-up. |
| CO-5F           | Blocked | 2026-06-10 | Goal R read-only staging-readiness check captured a blocked evidence artifact. Live Facebook publishing is disabled, `pages_manage_posts` is absent from runtime OAuth scopes, and no credentialed staging Page publish proof exists yet.                                                                                                                                                                                                                                                                        |
| CO-6B           | Done    | 2026-06-10 | Added aggregate-only overview/post report endpoints plus backend organic metric refresh from already-synced Meta post insight rows. dbt marts and target-tenant release evidence remain follow-up.                                                                                                                                                                                                                                                                                                               |
| CO-7F           | Blocked | 2026-06-10 | Goal S read-only staging-readiness check captured a blocked evidence artifact. Instagram beta publishing is disabled, `CONTENT_OPS_PUBLIC_MEDIA_BASE_URL` is unset, Instagram publishing scopes are absent from runtime OAuth scopes, and no credentialed staging Instagram feed publish proof exists yet.                                                                                                                                                                                                       |
| CO-8A-lite      | Done    | 2026-06-06 | Added tenant-scoped caption-generation active job, rolling 24-hour job, and rolling 24-hour candidate quota guardrails with safe `400` reason payloads. No live provider calls or quota billing integration added.                                                                                                                                                                                                                                                                                               |
| CO-8A           | Partial | 2026-06-06 | Caption quotas are implemented through CO-8A-lite; graphic-generation quotas, tenant cost budgets, and provider billing attribution remain follow-up.                                                                                                                                                                                                                                                                                                                                                            |
| CO-8D           | Blocked | 2026-06-10 | Goal T final release-readiness pass captured a no-go evidence artifact. ADinsights preflight remains `GATE_BLOCK`; required staging proof, App Review evidence, security/contract follow-up, and approver signoff are missing.                                                                                                                                                                                                                                                                                   |
| Docs pack       | Done    | 2026-06-05 | Added planned API contract, eval plan, publishing runbook, failure triage runbook, App Review runbook, and validation evidence template. These are documentation only and do not make endpoints or publishing live.                                                                                                                                                                                                                                                                                              |

## Scope Readiness Matrix

| Scope                    | Status                                                                                                        | Ready now? | Blocker                                                                                                                        | First action                                                                     |
| ------------------------ | ------------------------------------------------------------------------------------------------------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------- |
| Product/docs             | Ready                                                                                                         | Yes        | None                                                                                                                           | Keep spec/backlog current                                                        |
| Backend data model       | Foundation implemented                                                                                        | Yes        | Follow-up review/signoff                                                                                                       | Review `backend/content_ops/` app and CO-1A model invariants                     |
| Backend API contracts    | Skeleton implemented                                                                                          | Mostly     | Custom response schema fidelity and client approval scoping                                                                    | Expand readiness/reporting response schemas and write-contract coverage          |
| AI captions              | Backend foundation, golden eval harness, and caption quota guardrails implemented                             | Mostly     | Live provider/model cost policy and adapter review                                                                             | Add approved provider adapter only behind config gate and after reviewer signoff |
| AI graphics              | Needs decision                                                                                                | Partial    | Asset storage/CDN and cost controls                                                                                            | Confirm asset URL/storage strategy                                               |
| Frontend mocked UX       | Foundation and live-readiness polish implemented                                                              | Mostly     | Staging proof, final visual QA, and post-review polish                                                                         | Preserve exact backend states/blockers before staging evidence                   |
| Approval/export          | JSON plan export and persisted artifact API implemented                                                       | Mostly     | Notification routing, frontend export history, and richer packet formats                                                       | Add client review UI/API hardening and frontend artifact history                 |
| Facebook Page publishing | Fakeable processor, queue scans, and disabled-by-default live Graph adapter implemented; live runtime blocked | No         | `pages_manage_posts` App Review, credentialed staging proof, observability, rollback, and live adapter activation plan         | Meta Test App evidence and Goal R rerun                                          |
| Instagram publishing     | Fakeable container lifecycle and disabled-by-default live Graph adapter implemented; live runtime blocked     | No         | IG permission family/App Review, staging account proof, deployed HTTPS public media proof, security signoff, and release gates | Confirm permission family, staging account, and Goal S rerun                     |
| Aggregate reporting API  | API and backend refresh worker implemented                                                                    | Mostly     | dbt marts and target-tenant evidence                                                                                           | Add dbt mart criteria after publishing proof                                     |
| dbt organic marts        | Not ready                                                                                                     | No         | API snapshot contract not stable                                                                                               | Defer until beta                                                                 |
| Production rollout       | Blocked / no-go                                                                                               | No         | Goal T `GATE_BLOCK`, missing R/S staging evidence, App Review evidence, and approver signoff                                   | Resolve blockers and rerun Goal T                                                |

## Build Control Sheet

Use this table before starting any Content Ops coding session. If a ticket needs more than one
top-level folder, split it or route it to Raj/Mira before implementation.

| Priority | Ticket        | Status                         | Owner         | Reviewers             | Scope       | Dependencies                                | Feature flag / activation                 | External blocker                                | Acceptance                                                                                                                      | Tests                                                                                                                                                               | Docs                                                                                | Prompt                 |
| -------- | ------------- | ------------------------------ | ------------- | --------------------- | ----------- | ------------------------------------------- | ----------------------------------------- | ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- | ---------------------- |
| 1        | CO-SPEC-AUDIT | Done                           | Raj + Sofia   | Mira, Hannah          | `docs/`     | Current implementation inventory            | No runtime activation                     | None                                            | Docs agree on current state, next tickets, review routing, prompts, eval gaps, and release gates                                | `git diff --check`; `make adinsights-preflight PROMPT="Content Operations spec, ticket, eval, and prompt audit; docs-first planning update; no runtime activation"` | backlog, architecture, eval plan, Sprint 0 decisions, feature catalog, activity log | `PROMPT-CO-SPEC-AUDIT` |
| 2        | CO-3E         | Done                           | Omar + Sofia  | Nina, Raj             | `backend/`  | CO-3A, CO-3B                                | Live provider remains disabled            | None                                            | Golden caption fixtures run locally; schema, blocked terms, required terms, redaction, and no-side-effect checks are repeatable | focused generation/eval tests; `make backend-lint && make backend-test`                                                                                             | eval plan, backlog, activity log                                                    | `PROMPT-CO-3E`         |
| 3        | CO-8A-lite    | Done                           | Nina + Sofia  | Omar, Raj             | `backend/`  | CO-3A, CO-3E                                | Provider still disabled by default        | None                                            | Caption job quotas/cost counters block excess queued work with safe reasons before any provider call                            | backend quota tests; `make backend-lint && make backend-test`                                                                                                       | API contract if payload changes, backlog, runbook, activity log                     | `PROMPT-CO-8A-LITE`    |
| 4        | CO-3C         | Blocked until asset URL proof  | Sofia + Joel  | Nina, Omar, Raj       | `backend/`  | CO-0C, CO-3A, CO-8A-lite                    | Graphic provider disabled by default      | Asset URL/storage decision proof                | Graphic jobs validate schema and create quarantinable assets only through injected fake provider                                | asset/generation tests; `make backend-lint && make backend-test`                                                                                                    | eval plan, API contract, backlog, runbook                                           | `PROMPT-CO-3C`         |
| 5        | CO-2A/CO-2B   | Repo-ready next                | Lina + Joel   | Sofia, Maya, Raj      | `frontend/` | API contract and mocked fixture names       | UI hidden unless entitlement/flag enabled | None                                            | `/content` calendar plus brief/draft editor render mocked workflow and separated readiness blockers                             | frontend guardrails/lint/test/build                                                                                                                                 | frontend spec, backlog, activity log                                                | `PROMPT-CO-2A-2B`      |
| 6        | CO-5A/CO-5F   | External-blocked docs/evidence | Maya + Hannah | Raj, Nina             | `docs/`     | Meta Test App access                        | No runtime OAuth scope change             | Meta App Review/test Page access                | Permission/app-review copy and staging evidence path are complete without secrets                                               | docs guardrails; preflight                                                                                                                                          | App Review runbook, evidence template, permission profile                           | `PROMPT-CO-5A-5F`      |
| 7        | CO-5C-live    | Blocked until evidence gates   | Maya + Leo    | Nina, Sofia, Raj/Mira | `backend/`  | CO-5A/CO-5F, live credential handling proof | Feature-gated; disabled by default        | Meta App Review approval and staging Page proof | Live Graph adapter can be enabled per tenant only after App Review evidence; tests fake network                                 | backend publisher tests; preflight                                                                                                                                  | API contract, publishing/failure runbooks, changelog                                | `PROMPT-CO-5C-LIVE`    |

## Gap Audit

| Gap                                | Severity                    | Owner         | Current state                                                                                                                             | Required next action                                                                                            |
| ---------------------------------- | --------------------------- | ------------- | ----------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| Spec drift                         | Should-fix-before-next-code | Raj + Sofia   | Architecture doc lagged implementation names and current statuses.                                                                        | Keep architecture, backlog, API contract, eval plan, feature catalog, and runbooks synchronized in every slice. |
| Golden eval harness missing        | Done                        | Omar + Sofia  | Deterministic caption fixture harness exists and runs without network access.                                                             | Keep fixtures current when provider schema or policy changes.                                                   |
| Frontend contract fixtures missing | Should-fix-before-frontend  | Lina + Sofia  | API contract exists; frontend fixture/type names are not locked.                                                                          | Add mocked fixture pack in CO-2A/CO-2B before real API integration.                                             |
| App Review evidence missing        | External blocker            | Maya + Hannah | App Review runbook/template exist; credentialed evidence is not captured.                                                                 | Complete CO-5A/CO-5F before live Graph adapter.                                                                 |
| Quota/cost controls missing        | Partial                     | Nina + Sofia  | Caption job quotas exist; graphic/provider billing budgets do not.                                                                        | Keep live providers disabled until remaining budget controls are reviewed.                                      |
| Asset URL proof missing            | Partial                     | Nina + Victor | Backend validation blocks publish-bound assets without safe public/fetchable URLs; deployable CDN/object-store evidence is still missing. | Prove deployable HTTPS fetch path before graphic/IG live publish activation.                                    |
| Release/rollback gates incomplete  | Follow-up before production | Mei + Hannah  | General runbooks exist; Content Ops activation rollback is not complete.                                                                  | Add rollback/support checklist before production tenant rollout.                                                |
| Live publisher adapter blocked     | External blocker            | Maya + Leo    | Fakeable processor persists injected post IDs; no Graph adapter.                                                                          | Wait for App Review/evidence and implement behind disabled feature gate.                                        |

## Feature Map

| Feature                   | MVP                 | Beta                    | Production                  |
| ------------------------- | ------------------- | ----------------------- | --------------------------- |
| Content workspaces/briefs | Yes                 | Yes                     | Yes                         |
| Brand profile constraints | Basic JSON          | Versioned rules         | Tenant templates            |
| AI caption generation     | Yes                 | Yes                     | Yes                         |
| AI graphic generation     | Basic batch         | Multi-format batch      | Quotas and templates        |
| Asset library             | Basic               | Renditions              | Reuse/search                |
| Internal approval         | Yes                 | Yes                     | Yes                         |
| Client approval           | Tenant users        | External links optional | SLA reporting               |
| Calendar export           | Yes                 | Yes                     | Yes                         |
| Approval packet export    | Yes                 | Yes                     | Yes                         |
| Facebook Page publishing  | Single post         | More formats            | Tenant rollout              |
| Instagram publishing      | No                  | Single image feed       | Reels/carousels after proof |
| Publish queue             | Facebook only       | Facebook + Instagram    | Alerts/SLOs                 |
| Aggregate reporting       | Facebook Page posts | IG media insights       | Optional dbt marts          |
| Paid + organic comparison | Labeled only        | Labeled only            | Combined executive view     |

## Ticket Index

Ticket IDs use `CO-<sprint>-<letter>`. Keep every implementation ticket scoped to one top-level
folder unless Raj coordinates the exception.

### Sprint 0: Governance and Architecture

| ID    | Ticket                                    | Owner         | Scope   | Dependencies                  | Acceptance                                                          |
| ----- | ----------------------------------------- | ------------- | ------- | ----------------------------- | ------------------------------------------------------------------- |
| CO-0A | Confirm Meta publishing permission family | Maya + Raj    | `docs/` | Meta developer console access | Permission family documented; catalog/profile update ticket created |
| CO-0B | Decide backend app boundary               | Sofia + Mira  | `docs/` | None                          | Decision recorded: `backend/content_ops/` vs existing module        |
| CO-0C | Decide asset URL strategy                 | Nina + Victor | `docs/` | Storage/CDN capability known  | Public fetch URL design has security review                         |
| CO-0D | Create eval fixture plan                  | Sofia + Omar  | `docs/` | Spec golden set               | Fixture names, owners, and pass gates documented                    |
| CO-0E | Confirm frontend route map                | Lina + Joel   | `docs/` | Architecture plan             | Route/component map approved                                        |

Canonical checks: docs-only guardrails, contract guard if permission docs change.

### Sprint 1: Backend Data and API Skeleton

| ID    | Ticket                                          | Owner        | Scope      | Dependencies | Acceptance                                                                                                                         | Tests                                    |
| ----- | ----------------------------------------------- | ------------ | ---------- | ------------ | ---------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------- |
| CO-1A | Add backend `content_ops` app and models        | Sofia        | `backend/` | CO-0B        | Done: tenant-scoped models/migrations exist                                                                                        | `make backend-lint && make backend-test` |
| CO-1B | Add serializers and OpenAPI contract tests      | Sofia        | `backend/` | CO-1A        | Done: tenant-scoped serializers/viewsets and workflow skeleton exist; OpenAPI path/action/enum assertions cover Content Ops routes | Backend tests + OpenAPI path tests       |
| CO-1C | Add role permissions and tenant isolation tests | Nina + Sofia | `backend/` | CO-1A        | Done: read/edit/internal/client/publish role gates enforced in focused tests                                                       | Backend permission tests                 |
| CO-1D | Add readiness composition endpoint              | Maya + Sofia | `backend/` | CO-1B        | Done: readiness axes remain separate and do not mutate existing Meta readiness payloads                                            | readiness separation tests               |
| CO-1E | Add audit event hooks                           | Omar + Sofia | `backend/` | CO-1A        | Partial: workflow actions create safe audit events; event catalog tests remain                                                     | audit tests                              |

Feature flag: `CONTENT_OPS_META_MVP=false` by default.

### Sprint 2: Frontend Mocked Workspace

| ID    | Ticket                              | Owner       | Scope       | Dependencies | Acceptance                                                 | Tests                               |
| ----- | ----------------------------------- | ----------- | ----------- | ------------ | ---------------------------------------------------------- | ----------------------------------- |
| CO-2A | Add content shell/calendar route    | Lina        | `frontend/` | CO-0E        | `/content` shows calendar/queue with mocks                 | frontend guardrails/lint/test/build |
| CO-2B | Add brief and draft editor          | Lina + Joel | `frontend/` | CO-2A        | platform variants visible side by side                     | component tests                     |
| CO-2C | Add asset library UI                | Joel        | `frontend/` | CO-2A        | generated/uploaded assets render with stable aspect ratios | component tests                     |
| CO-2D | Add approval queue/client review UI | Lina        | `frontend/` | CO-2B        | exact version/media shown for approval                     | integration tests                   |
| CO-2E | Add readiness panel UI              | Lina + Maya | `frontend/` | CO-2A        | six readiness blockers render independently                | mocked matrix tests                 |

Feature flag: UI hidden unless `CONTENT_OPS_META_MVP` entitlement enabled.

### Sprint 3: AI Production

| ID    | Ticket                               | Owner        | Scope       | Dependencies | Acceptance                                                                                                                                  | Tests                       |
| ----- | ------------------------------------ | ------------ | ----------- | ------------ | ------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------- |
| CO-3A | Implement caption generation adapter | Sofia        | `backend/`  | CO-1A        | Done: queued endpoint plus fakeable disabled-by-default caption processor create generated draft versions from schema-valid provider output | schema/no-side-effect tests |
| CO-3B | Implement prompt redaction           | Nina         | `backend/`  | CO-3A        | Done: secret-like values redacted before storage/provider handoff and safe failure details enforced                                         | no-secret tests             |
| CO-3C | Implement graphic generation job     | Sofia + Joel | `backend/`  | CO-0C, CO-1A | images stored as assets with lineage                                                                                                        | asset/dimension tests       |
| CO-3D | Add AI job UI states                 | Lina         | `frontend/` | CO-2B        | queued/running/succeeded/failed/cancelled visible                                                                                           | frontend tests              |
| CO-3E | Add local eval harness               | Omar + Sofia | `backend/`  | CO-0D        | Done: deterministic schema/redaction/policy tests and golden caption fixture harness exist; remote model/provider scoring remains later     | eval tests                  |

Do not allow generated output to schedule or publish without approval.

### Sprint 4: Approval and Export

| ID    | Ticket                                 | Owner | Scope       | Dependencies | Acceptance                                    | Tests               |
| ----- | -------------------------------------- | ----- | ----------- | ------------ | --------------------------------------------- | ------------------- |
| CO-4A | Implement immutable approval snapshots | Sofia | `backend/`  | CO-1A        | edits after approval invalidate approval      | version drift tests |
| CO-4B | Implement approval endpoints           | Sofia | `backend/`  | CO-4A        | decisions are tenant/role scoped              | backend tests       |
| CO-4C | Wire approval UI to API                | Lina  | `frontend/` | CO-4B        | internal/client review flow works             | frontend tests      |
| CO-4D | Add content calendar/approval exports  | Sofia | `backend/`  | CO-4A        | CSV/PDF/ZIP artifacts match approved versions | export tests        |
| CO-4E | Add export UI                          | Lina  | `frontend/` | CO-4D        | users can download client-safe packets        | frontend tests      |

MVP value gate: agencies can generate, approve, and export content plans before live publishing.

### Sprint 5: Facebook Page Publishing MVP

| ID    | Ticket                                          | Owner         | Scope       | Dependencies | Acceptance                                                                                                                                                                          | Tests               |
| ----- | ----------------------------------------------- | ------------- | ----------- | ------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------- |
| CO-5A | Update Meta permission docs for Page publishing | Maya + Hannah | `docs/`     | CO-0A        | App Review copy/checklist ready                                                                                                                                                     | docs guardrails     |
| CO-5B | Add Page publish preflight service              | Maya          | `backend/`  | CO-1D        | Done: Page readiness reason codes safe/actionable, with no provider side effects                                                                                                    | backend tests       |
| CO-5C | Add Page publisher service                      | Maya + Leo    | `backend/`  | CO-5B        | Done: fakeable processor persists injected post IDs, live Graph adapter is disabled by default, tenant-scoped token lookup is covered, and errors are sanitized                     | publisher tests     |
| CO-5D | Add publish scheduler for Page posts            | Leo           | `backend/`  | CO-5C        | Done: queue dispatch, single-attempt task, retry requeue, due retry scanner, queue filters, and due/retry/process beat scans are implemented; live provider handoff remains blocked | scheduler/API tests |
| CO-5E | Add publish queue UI/retry actions              | Lina          | `frontend/` | CO-5D        | Done: retryable vs terminal states visible and retry action remains retryable-only                                                                                                  | frontend tests      |
| CO-5F | Capture Facebook staging evidence               | Hannah + Maya | `docs/`     | CO-5D        | Blocked: evidence artifact stored without secrets, but no successful staging Page publish captured yet because runtime lacks gated `pages_manage_posts` and live flag activation    | evidence checklist  |

External blocker: Meta App Review approval and test Page credentials.

### Sprint 6: Aggregate Organic Reporting

| ID    | Ticket                              | Owner          | Scope       | Dependencies | Acceptance                                 | Tests                   |
| ----- | ----------------------------------- | -------------- | ----------- | ------------ | ------------------------------------------ | ----------------------- |
| CO-6A | Add published-post metric snapshots | Sofia          | `backend/`  | CO-5D        | aggregate grain enforced                   | backend reporting tests |
| CO-6B | Add overview/posts report endpoints | Sofia          | `backend/`  | CO-6A        | no user-level fields returned              | aggregate-only tests    |
| CO-6C | Add content reporting UI            | Lina           | `frontend/` | CO-6B        | reports link to drafts and published posts | frontend tests          |
| CO-6D | Draft dbt mart promotion criteria   | Priya + Martin | `docs/`     | CO-6B        | mart readiness criteria documented         | docs guardrails         |

Do not add dbt marts until aggregate API snapshots have beta evidence.

### Sprint 7: Instagram Beta

| ID    | Ticket                                        | Owner         | Scope       | Dependencies | Acceptance                                                                                                                                                                                                                    | Tests              |
| ----- | --------------------------------------------- | ------------- | ----------- | ------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------ |
| CO-7A | Update Meta permission docs for IG publishing | Maya + Hannah | `docs/`     | CO-0A        | current IG permission family documented                                                                                                                                                                                       | docs guardrails    |
| CO-7B | Add Instagram readiness preflight             | Maya          | `backend/`  | CO-1D        | Done: linkage/professional/permission states remain separated with client-safe blockers                                                                                                                                       | backend tests      |
| CO-7C | Add media URL validation                      | Nina + Maya   | `backend/`  | CO-0C        | Done: publish-bound assets require safe public/fetchable image or video URLs                                                                                                                                                  | asset tests        |
| CO-7D | Add IG container create/poll/publish          | Leo + Maya    | `backend/`  | CO-7B, CO-7C | Done behind fakeable disabled provider boundary and `CONTENT_OPS_META_INSTAGRAM_BETA` live Graph adapter; production enablement remains blocked                                                                               | scheduler tests    |
| CO-7E | Add IG queue states UI                        | Lina          | `frontend/` | CO-7D        | Done: container lifecycle states render clearly with live-readiness summary and schedule confirmation                                                                                                                         | frontend tests     |
| CO-7F | Capture Instagram staging evidence            | Hannah + Maya | `docs/`     | CO-7D        | Blocked: evidence artifact stored without secrets, but no successful staging Instagram feed publish captured yet because runtime lacks gated Instagram publishing scopes, deployed public media URL, and beta flag activation | evidence checklist |

External blocker: Instagram App Review approval, linked professional account, staging proof,
security/release signoff, and deployable HTTPS asset URL proof.

### Sprint 8: Production Hardening

| ID    | Ticket                                         | Owner         | Scope                          | Dependencies | Acceptance                                                                                                                                    | Tests                       |
| ----- | ---------------------------------------------- | ------------- | ------------------------------ | ------------ | --------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------- |
| CO-8A | Add tenant quotas and generation cost controls | Nina + Sofia  | `backend/`                     | CO-3A, CO-3C | Partial: caption quotas enforced and visible; graphic/provider billing budgets remain                                                         | backend tests               |
| CO-8B | Add content ops alerts and dashboards          | Omar + Hannah | `docs/` then backend as needed | CO-5D, CO-7D | SLOs/runbooks documented                                                                                                                      | observability checks        |
| CO-8C | Add rollback and support runbooks              | Hannah + Mei  | `docs/`                        | CO-5F, CO-7F | operator actions documented                                                                                                                   | docs review                 |
| CO-8D | Run cross-stream release preflight             | Raj + Mei     | all touched scopes             | CO-8A-C      | Blocked: Goal T archived final no-go preflight evidence with `GATE_BLOCK`; rerun only after successful R/S staging proof and required signoff | `make adinsights-preflight` |

## First Code Ticket Recommendation

Start with CO-1A only after CO-0B and `CO-D0-1`/`CO-D0-2` are accepted. It is the safest first code
ticket because it creates the durable domain model without external Meta credentials, AI provider
calls, or frontend coupling.

Do not start CO-5 or CO-7 before:

- permission docs are updated
- App Review evidence path exists
- encrypted credential handling is confirmed
- readiness endpoint tests prove state separation

## Agent Handoff Rules

Every coding-agent handoff must include:

- ticket ID
- exact top-level folder scope
- owner/reviewer
- feature flag behavior
- acceptance criteria
- canonical tests
- docs/runbooks to update
- explicit "do not touch" list

If a ticket needs more than one top-level folder, split it or route to Raj/Mira.

## Ticket Prompt Pack

Use these prompts as the starting point for future agentic sessions. Keep the `Do not` lists intact
unless Raj explicitly coordinates a broader slice.

### PROMPT-CO-SPEC-AUDIT

```text
You are working in /Users/thristannewman/ADinsights.
Implement only a docs-first Content Operations spec/ticket/prompt audit.
Read AGENTS.md, docs/workstreams.md, docs/project/content-operations-architecture-sprint-plan.md,
docs/project/content-operations-implementation-backlog.md, docs/project/content-operations-api-contract.md,
docs/project/content-operations-eval-plan.md, docs/project/content-operations-sprint0-decisions.md,
docs/project/feature-catalog.md, and the Content Operations runbooks.
Do:
- reconcile docs to current implementation reality
- update stale module names, statuses, next-ticket order, reviewer routing, prompts, eval gaps, and release gates
- update docs/ops/agent-activity-log.md
Do not:
- edit backend/frontend/dbt code
- enable live OpenAI, Meta Graph, Instagram, Celery beat, or dbt behavior
- touch unrelated AGENTS.md changes
Verify:
- git diff --check
- make adinsights-preflight PROMPT="Content Operations spec, ticket, eval, and prompt audit; docs-first planning update; no runtime activation"
Final response:
- summarize docs changed, ticket/status changes, validation results, and required reviewers.
```

### PROMPT-CO-3E

```text
You are working in /Users/thristannewman/ADinsights.
Implement only the Content Ops golden caption eval harness.
Scope: backend/ plus required docs updates.
Inspect backend/content_ops/generation.py, backend/tests/test_content_ops_generation.py, and docs/project/content-operations-eval-plan.md.
Do:
- add tenant-safe caption eval fixtures with no real secrets or PII
- add a local deterministic harness that runs schema, blocked-term, required-term, redaction, and no-side-effect checks against fixture outputs
- keep live provider calls disabled; tests must use fake/inert providers only
- update eval plan/backlog/activity log
Do not:
- call OpenAI or any network provider
- generate graphics
- approve, schedule, publish, or refresh metrics
- add frontend or dbt work
Verify:
- focused generation/eval tests
- make backend-lint && make backend-test
- git diff --check
Stop before:
- adding live provider configuration, quota models, or frontend screens.
```

### PROMPT-CO-8A-LITE

```text
You are working in /Users/thristannewman/ADinsights.
Implement only caption-generation quota and cost guardrails.
Scope: backend/ plus required docs updates.
Do:
- enforce tenant-safe limits for queued/running caption jobs before provider handoff
- return stable safe failure codes when quotas block work
- avoid secret-bearing logs and raw prompt/provider payloads
- add focused tests for quota allow/block behavior and tenant isolation
Do not:
- enable live providers
- add graphic generation
- add frontend/dbt
- change Meta publishing behavior
Verify:
- focused content_ops generation tests
- make backend-lint && make backend-test
- git diff --check
```

### PROMPT-CO-3C

```text
You are working in /Users/thristannewman/ADinsights.
Implement only the disabled-by-default AI graphic generation foundation.
Scope: backend/ plus required docs updates.
Prerequisites: CO-0C asset URL decision proof and CO-8A-lite quota/cost guardrails.
Do:
- add fakeable graphic provider boundary that fails closed by default
- validate requested formats/dimensions and safe asset metadata
- create MediaAsset records only from injected fake provider output
- quarantine invalid assets and never publish generated media directly
Do not:
- call live image APIs
- expose signed URLs through normal read APIs
- schedule/publish/approve generated assets
- add frontend/dbt work
Verify:
- asset/generation tests
- make backend-lint && make backend-test
- git diff --check
```

### PROMPT-CO-2A-2B

```text
You are working in /Users/thristannewman/ADinsights.
Implement only mocked frontend Content Ops shell, calendar, brief builder, and draft editor.
Scope: frontend/ only.
Do:
- build /content as the operational first screen with calendar/queue/readiness areas
- use mocked fixtures matching docs/project/content-operations-api-contract.md
- keep readiness blockers separate: Meta auth, Page selection, Instagram linkage, Facebook publishing, Instagram publishing, reporting
- show generation job states but do not call live backend if fixture mode is active
Do not:
- edit backend/dbt
- add real Meta or AI calls
- hide blockers behind generic "Meta connected"
Verify:
- make frontend-guardrails && make frontend-lint && make frontend-test && make frontend-build
- visual/browser verification if a dev server is started
```

### PROMPT-CO-5A-5F

```text
You are working in /Users/thristannewman/ADinsights.
Implement only Meta App Review docs and staging evidence readiness for Facebook Page publishing.
Scope: docs/ only unless Raj approves otherwise.
Do:
- update permission/profile/runbook copy for pages_manage_posts and current Graph/App Review requirements
- define exact staging evidence checklist and redacted artifact paths
- keep OAuth runtime scopes unchanged
- update backlog/activity log
Do not:
- edit backend OAuth scopes or provider code
- decrypt/log tokens
- add live publishing behavior
Verify:
- git diff --check
- make adinsights-preflight PROMPT="Content Operations Facebook Page App Review evidence docs; no runtime scope change"
```

### PROMPT-CO-5C-LIVE

```text
You are working in /Users/thristannewman/ADinsights.
Implement live Facebook Page publisher adapter only after CO-5A/CO-5F evidence gates are complete.
Scope: backend/ plus required docs updates.
Do:
- keep the adapter behind a disabled-by-default feature/config gate
- decrypt tokens only inside the provider boundary and never include tokens in payload reprs, logs, exceptions, snapshots, or tests
- use fake network tests by default and explicit staging evidence for real calls
- preserve preflight/readiness separation and app-owned scheduling
Do not:
- add Instagram containers
- activate Celery beat
- enable tenant rollout by default
- add frontend/dbt work
Verify:
- publisher tests with fake adapter
- make backend-lint && make backend-test
- data contract check if API docs change
- make adinsights-preflight PROMPT="Content Operations live Facebook Page adapter behind disabled feature gate"
```

## Feature Documentation Needed Before Activation

| Doc                                                     | Required before               | Owner         |
| ------------------------------------------------------- | ----------------------------- | ------------- |
| `docs/project/content-operations-api-contract.md`       | frontend real API integration | Sofia + Lina  |
| `docs/project/content-operations-eval-plan.md`          | AI provider tuning            | Sofia + Omar  |
| `docs/runbooks/content-operations-publishing.md`        | Facebook MVP publishing       | Maya + Hannah |
| `docs/runbooks/content-operations-failures.md`          | scheduler beta                | Leo + Hannah  |
| `docs/runbooks/content-operations-app-review.md`        | Meta App Review submission    | Maya + Hannah |
| `docs/project/evidence/content-operations/_TEMPLATE.md` | staging proof                 | Hannah        |

## Program-Level Definition of Ready

The program is ready for implementation when:

- CO-0A through CO-0E are complete.
- Raj approves the cross-stream slice map.
- Mira approves the backend app boundary if a new backend app is created.
- Feature flags are named and default-off.
- App Review blockers are separated from repo-ready work.
- First code ticket is scoped to one top-level folder.

## Program-Level Definition of Done

The program is done when:

- MVP, beta, and production exit criteria in the product spec are satisfied.
- Facebook and Instagram publishing have credentialed staging evidence.
- AI evals and deterministic local tests are green.
- Reporting remains aggregate-only.
- Runbooks and rollback docs are complete.
- Raj/Mira and stream owners sign off.
