# Content Operations Current State

Status: Goal A checkpoint
Timezone baseline: `America/Jamaica`
Last updated: 2026-06-10

Related:

- `docs/project/content-operations-api-contract.md`
- `docs/project/content-operations-implementation-backlog.md`
- `docs/project/content-operations-meta-publishing-spec.md`
- `docs/project/api-contract-changelog.md`
- `docs/runbooks/content-operations-publishing.md`
- `docs/runbooks/content-operations-app-review.md`

## Purpose

Lock the current Content Ops / Instagram posting implementation state before the next bounded
coding session. This file is a status checkpoint only; it does not authorize live Meta publishing,
OAuth scope expansion, production rollout, or a wider multi-folder implementation session.

## Goal Checkpoint

| Goal                                              | Current state                                                                                                                                                                                                                                                                                                               | Evidence                                                                                                                                                                                                                                                                                                                                                          | Remaining work                                                                                                                                                                                                                                                             |
| ------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A. Lock implementation state                      | Done in docs as of this checkpoint.                                                                                                                                                                                                                                                                                         | This file, doc index entry, activity log entry.                                                                                                                                                                                                                                                                                                                   | Keep this file current whenever Content Ops scope changes.                                                                                                                                                                                                                 |
| B. Frontend generated-candidate selection         | Implemented. Users can inspect generated caption candidates and create drafts from a selected candidate.                                                                                                                                                                                                                    | `frontend/src/routes/ContentOpsPage.tsx`, `frontend/src/lib/contentOps.ts`, `frontend/src/routes/__tests__/ContentOpsPage.test.tsx`; recorded full frontend guardrails/lint/test/build pass.                                                                                                                                                                      | No remaining work for this bounded goal.                                                                                                                                                                                                                                   |
| C. Backend publish queue processor scan           | Implemented. Due queued attempts are processed by `content-publish-process-scan` on the sync queue.                                                                                                                                                                                                                         | `backend/content_ops/tasks.py`, `backend/content_ops/publisher.py`, `backend/core/settings.py`, `backend/tests/test_content_ops_publisher.py`, `backend/tests/test_tasks.py`.                                                                                                                                                                                     | Live Graph provider adapters remain external-gated and must stay disabled until release gates pass.                                                                                                                                                                        |
| D. Backend asset URL proof and media validation   | Implemented for publish-bound backend validation. Public/fetchable media URL checks run before publishing paths and scheduled/publishing draft activation.                                                                                                                                                                  | `backend/content_ops/assets.py`, `backend/content_ops/serializers.py`, `backend/tests/test_content_ops_api.py`.                                                                                                                                                                                                                                                   | Deployable CDN/object-store proof and signed/public URL operations still need release evidence.                                                                                                                                                                            |
| E. Instagram container lifecycle                  | Implemented behind a fakeable/disabled provider boundary plus a real disabled-by-default Instagram Graph adapter behind `CONTENT_OPS_META_INSTAGRAM_BETA`. Create, poll, ready/pending, publish, expire, retryable, and terminal failure paths are covered without live Graph calls by default.                             | `backend/content_ops/publisher.py`, `backend/content_ops/instagram_graph.py`, `backend/tests/test_content_ops_publisher.py`.                                                                                                                                                                                                                                      | App Review evidence, staging proof, security signoff, and scope approval remain blocked before production enablement.                                                                                                                                                      |
| F. Persisted export artifacts                     | Implemented in backend. Content-plan exports can be created, listed, retrieved, and downloaded as stored client-safe JSON artifacts; frontend history was added in Goal H.                                                                                                                                                  | `backend/content_ops/models.py`, `backend/content_ops/exports.py`, `backend/content_ops/views.py`, `backend/content_ops/serializers.py`, `backend/tests/test_content_ops_api.py`, `backend/tests/test_schema_regressions.py`, `frontend/src/lib/contentOps.ts`, `frontend/src/routes/ContentOpsPage.tsx`.                                                         | Richer PDF/CSV/ZIP packet formats remain a future enhancement outside this bounded goal.                                                                                                                                                                                   |
| G. Organic metrics refresh worker                 | Implemented in backend. Published posts refresh aggregate-only metrics from already-synced Meta post insight rows.                                                                                                                                                                                                          | `backend/content_ops/metrics.py`, `backend/content_ops/tasks.py`, `backend/content_ops/views.py`, `backend/core/settings.py`, `backend/tests/test_content_ops_api.py`, `backend/tests/test_tasks.py`.                                                                                                                                                             | dbt organic marts and live proof against target tenant data remain follow-up/release evidence.                                                                                                                                                                             |
| H/Q. Frontend route and live-readiness polish     | Implemented. The `/content` route renders readiness, briefs, generation, media library, calendar, client review, export history, reports, Production Queue lifecycle states, retryable-only retry controls, a live publishing readiness summary, and schedule confirmation before queue entry.                              | `frontend/src/routes/ContentOpsPage.tsx`, `frontend/src/lib/contentOps.ts`, `frontend/src/lib/contentOpsMock.ts`, `frontend/src/styles/contentOps.css`, `frontend/src/routes/__tests__/ContentOpsPage.test.tsx`, `frontend/src/lib/contentOps.test.ts`; Goal Q evidence: `docs/project/evidence/content-operations/2026-06-10-goal-q-frontend-live-readiness.md`. | Staging publish proof and final release readiness remain blocked.                                                                                                                                                                                                          |
| I. Release readiness and Meta App Review evidence | Completed as an evidence pass; release remains blocked.                                                                                                                                                                                                                                                                     | `docs/project/evidence/content-operations/2026-06-10-goal-i-release-readiness.md`; persisted packets under `docs/project/evidence/content-operations/preflight-2026-06-10-goal-i/`; `release_status=GATE_BLOCK`.                                                                                                                                                  | Resolve architecture-scope, contract, security/PII, App Review, staging, and approver blockers before live publishing.                                                                                                                                                     |
| R. Facebook staging publish proof                 | Blocked. A read-only Goal R staging-readiness check confirmed no safe Facebook Page publish proof can be captured in this workspace because live publishing is disabled and `pages_manage_posts` is absent from runtime OAuth scopes.                                                                                       | `docs/project/evidence/content-operations/2026-06-10-goal-r-facebook-staging-proof.md`; `docs/runbooks/content-operations-publishing.md`.                                                                                                                                                                                                                         | Rerun Goal R only in a controlled staging environment with approved/test `pages_manage_posts`, selected tenant-local Page token, temporary staging flag activation, redacted logs/metrics, and rollback proof.                                                             |
| S. Instagram staging publish proof                | Blocked. A read-only Goal S staging-readiness check confirmed no safe Instagram feed publish proof can be captured in this workspace because the Instagram beta flag is disabled, public media base URL is unset, and Instagram publishing permissions are absent from runtime OAuth scopes.                                | `docs/project/evidence/content-operations/2026-06-10-goal-s-instagram-staging-proof.md`; `docs/runbooks/content-operations-publishing.md`.                                                                                                                                                                                                                        | Rerun Goal S only in a controlled staging environment with selected Instagram permission family, linked professional IG account, deployed HTTPS public media URL proof, temporary beta flag activation, redacted container/media/log/metrics evidence, and rollback proof. |
| T. Final release readiness pass                   | Completed as a no-go evidence pass. Final ADinsights preflight returned `GATE_BLOCK`, so live Facebook/Instagram publishing must remain disabled.                                                                                                                                                                           | `docs/project/evidence/content-operations/2026-06-10-goal-t-final-release-readiness.md`; persisted packets under `docs/project/evidence/content-operations/preflight-2026-06-10-goal-t-final-release-readiness/`.                                                                                                                                                 | Resolve external staging/App Review blockers, capture successful R/S proof, collect required approver signoff, and rerun Goal T before any live activation.                                                                                                                |
| U. Local Meta OAuth proof                         | Partially proven and blocked before callback. Local HTTPS stack runs, backend runtime uses app `2921903668150890`, OAuth start URL uses `https://localhost:5173/dashboards/data-sources`, and setup is `ready_for_oauth`; Safari is stopped on the local certificate warning before the Data Sources UI can complete OAuth. | `docs/project/evidence/content-operations/2026-06-11-local-meta-oauth-proof.md`.                                                                                                                                                                                                                                                                                  | Human must accept/trust the local `https://localhost:5173` development certificate in Safari, then rerun Data Sources Meta OAuth and recapture callback/readiness evidence.                                                                                                |

## Built Runtime Surface

- Tenant-scoped `backend/content_ops/` Django app with models, migrations, serializers, DRF
  routes, local permissions, readiness axes, audit hooks, draft workflow actions, approval
  decisions, scheduling, publishing queue, published posts, aggregate metrics, and exports.
- Caption generation foundation with redaction, quota guards, deterministic eval fixtures, schema
  validation, safe failure codes, and generated draft/version creation through an injected provider
  boundary. Live provider calls remain disabled.
- Publishing scheduler and queue:
  - due schedule dispatch every minute
  - due retry requeue every minute
  - queued attempt processor every minute
  - provider boundaries disabled by default unless explicitly injected/configured
- Facebook Page publish preflight, fakeable attempt processor, and disabled-by-default live Graph
  adapter behind `CONTENT_OPS_LIVE_FACEBOOK_PUBLISHING`.
- Instagram publish preflight and fakeable container lifecycle.
- Asset upload/download boundary, server-owned storage metadata, and public URL validation before
  publish-bound activation.
- Persisted content-plan export artifacts for repeat JSON downloads.
- Aggregate-only organic metric refresh from synced Meta post insight rows.
- Frontend `/content` route foundation with readiness, briefs, generated candidates, draft
  creation, approval actions, scheduling, calendar summary, client review queue, publish queue,
  reports, immediate export download, and persisted export history.

## Verified State

Latest recorded validation in this worktree:

- Goal B: `make frontend-guardrails && make frontend-lint && make frontend-test && make frontend-build` passed.
- Goals C-G: focused backend tests passed for each slice, followed by `make backend-lint && make backend-test`.
- Goal H: focused Content Ops frontend tests passed; full
  `make frontend-guardrails && make frontend-lint && make frontend-test && make frontend-build`
  passed; Playwright smoke rendered the Content Ops route panels.
- Goal I: ADinsights preflight ran and persisted packets under
  `docs/project/evidence/content-operations/preflight-2026-06-10-goal-i/`; release status is
  `GATE_BLOCK`, which is the expected evidence outcome until launch blockers are resolved.
- Goal U: local HTTPS stack and backend OAuth runtime were proven with app `2921903668150890` and
  redirect `https://localhost:5173/dashboards/data-sources`; OAuth callback remains unproven
  because Safari requires a human action on the local certificate warning.
- Contract-sensitive backend slices ran the ADinsights contract guard/preflight path; no breaking
  change was reported, but Raj review and release gate follow-up remain required.

Re-run the relevant matrix before handing off any new code slice. This checkpoint records prior
evidence; it is not a substitute for validation after future edits.

## Still Missing

- Credentialed staging proof for the disabled-by-default Instagram Graph provider adapter.
- Facebook Page live adapter staging proof and production release approval. Goal R has a blocked
  evidence artifact; no real Facebook Page publish proof has been captured.
- Instagram live adapter staging proof and production release approval. Goal S has a blocked
  evidence artifact; no real Instagram feed publish proof has been captured.
- Meta App Review evidence, staging Page/IG proof, reviewer copy, and operator-controlled credential
  evidence for live posting.
- Completed local Meta OAuth callback proof from the Data Sources UI after Safari trusts the local
  `https://localhost:5173` development certificate.
- OAuth scope activation for publishing; current implementation must remain disabled until approval.
- Live AI provider adapter and cost/billing controls beyond local caption quota guards.
- AI graphic generation and asset/CDN operational proof.
- External client approval links and notification routing.
- dbt organic marts and production reporting promotion criteria.
- Architecture-scope, contract, security/PII, App Review, staging, and approver evidence resolving
  the current `GATE_BLOCK`.
- Final Goal T no-go evidence exists, but it does not authorize live publishing.

## Next Bounded Session

The bounded A-I implementation/evidence sequence is complete. Next work should be a new goal for
release blocker remediation, not live publishing activation. Start with Raj/Mira architecture review,
then contract/security follow-up, then Meta App Review/staging evidence capture.
