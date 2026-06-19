# Content Operations Live Publishing Audit Spec

Status: Goal J cross-stream review / build audit
Timezone baseline: `America/Jamaica`
Last updated: 2026-06-10
Scope: docs/review only; no runtime code changes; no live publishing activation

Related:

- `docs/project/content-operations-current-state.md`
- `docs/project/content-operations-api-contract.md`
- `docs/project/content-operations-meta-publishing-spec.md`
- `docs/project/evidence/content-operations/2026-06-10-goal-i-release-readiness.md`
- `docs/runbooks/content-operations-app-review.md`
- `docs/runbooks/content-operations-publishing.md`
- `docs/project/feature-flags-reference.md`

## Executive Decision

Content Ops is repo-ready for local planning, approvals, scheduling, queue simulation, fakeable
publishing boundaries, export history, and aggregate metric refresh. It is not ready for live
Facebook Page or Instagram publishing.

Do not begin live Graph adapter work until the debug/test-hardening, contract/security, App Review
evidence, public media URL/CDN, and cross-stream review gates below are complete. The next coding
goal should be Goal K, not Goal O or Goal P.

## Review Evidence Used

- Current worktree inspection: Content Ops touches `backend/`, `frontend/`, and `docs/`, with
  runtime code still uncommitted/untracked in the local tree.
- Current-state checkpoint: A-I are recorded as implemented/evidenced, with release still blocked.
- Goal I evidence: `release_status=GATE_BLOCK`; scope gate blocked by architecture-level risk;
  contract and security/PII warnings remain.
- Goal J preflight evidence:
  `docs/project/evidence/content-operations/preflight-2026-06-10-goal-j/`; result remains
  `GATE_BLOCK` with architecture-scope, contract, and security/PII follow-up required.
- Persona router:
  - Explicit reviewer prompt resolved to Hannah because multiple explicit names were present.
  - Cross-stream path prompt resolved to Lina with `cross_stream=True`, `invoke_scope_gatekeeper=True`,
    `invoke_release_readiness=True`, and required reviewers Raj and Mira.
- Scope-gatekeeper guidance: cross-folder runtime work requires Raj; architecture-sensitive or
  refactor work requires Raj plus Mira; contract-risk signals require contract guard follow-up.

## 1. Current State

### Built

- Tenant-scoped `backend/content_ops/` Django app with models, migrations, serializers, DRF routes,
  local role gates, readiness axes, audit hooks, draft workflows, approvals, schedules, publish
  attempts, published posts, metric snapshots, and export artifacts.
- Caption-generation foundation with redaction, quota guards, deterministic eval fixtures, safe
  failure codes, and an injected provider boundary.
- Backend schedule dispatcher that creates durable publish attempts from approved schedules.
- Retry scanner and queued-attempt processor running through Celery beat on the sync queue.
- Facebook Page preflight and fakeable Page publishing processor.
- Instagram preflight and fakeable media-container lifecycle: create, pending, ready, publish,
  retryable failure, terminal failure, and expiry paths.
- Asset upload/download boundary and publish-bound media validation.
- Persisted content-plan JSON export artifacts with frontend export history.
- Aggregate-only organic metric refresh from already-synced Meta post insight rows.
- Frontend `/content` route with readiness, briefs, generation, media upload, drafts, approvals,
  scheduling, calendar summary, client review queue, export history, production queue, and reports.

### Partially Built

- Readiness is separated into Meta auth, Page selection, Instagram linkage, Facebook publishing,
  Instagram publishing, and reporting axes, but live permission validation still needs review
  against the active Meta app and target Graph API version.
- Publish queue processing exists, but the default providers fail closed and do not call Meta.
- Instagram container lifecycle exists behind a fakeable boundary, but not a live Graph adapter.
- Organic reporting exists from stored snapshots, but dbt organic marts and production reporting
  promotion criteria are still follow-up work.
- App Review runbook and Goal I evidence exist, but the App Review submission packet is incomplete.

### Disabled / Fakeable

- Live Facebook Page publishing provider is disabled by default.
- Live Instagram publishing provider is disabled by default.
- Live AI caption/graphic provider calls are disabled by default.
- Publishing feature flags are rollout controls only; they do not grant OAuth scopes, configure live
  providers, or prove App Review readiness by themselves.
- Current queue processors can exercise injected fake providers for tests, but must not be treated as
  live Meta behavior.

### Missing

- Live Facebook Page Graph adapter.
- Live Instagram create-container, poll-status, and media-publish adapter.
- Token retrieval/decryption path for publish providers with proof that secrets never appear in
  logs, persisted failure details, screenshots, or evidence artifacts.
- Current verified Meta publishing permission family for the production app type and Graph API
  version.
- Public HTTPS media URL/CDN strategy that Meta can fetch without exposing private storage keys.
- App Review reviewer copy, screencast script, test users, redaction checklist, and submission
  packet.
- Staging Facebook Page publish proof.
- Staging Instagram professional account publish proof.
- Full dry-run/debug evidence for queue, retry, container expiry, asset validation, export history,
  metric refresh, and UI blocked/ready states.
- dbt organic marts and production reporting rollout criteria.
- External client approval links and notification routing.
- Runtime observability proof for queue delay, publish duration, retry counts, failure codes, and
  Meta rate-limit handling.

### Risky

- The local package spans backend, frontend, and docs; this violates the default single-folder PR
  rule unless Raj coordinates the split and Mira reviews architecture risk.
- The API contract doc has likely drift: it still says live frontend export history is planned even
  though the current-state checkpoint records Goal H export history as implemented.
- The live adapter boundary is not yet proven against tenant isolation, credential boundaries, safe
  provider errors, and no-secret logging.
- App Review wording and permissions are not locked; using stale permission names can waste a review
  cycle.
- Public media URL behavior is a launch blocker for Instagram because Meta must fetch approved media
  over HTTPS.

## 2. Product Scope For Live Facebook/Instagram Posting

MVP live scope:

- Agency user creates or selects a Content Ops workspace.
- User creates a brief, generates or manually writes platform variants, uploads approved media, and
  creates draft versions.
- Internal approver approves the exact draft version.
- Client approver approves the exact draft version.
- Publish-capable user schedules or queues a publish attempt.
- Backend dispatches approved schedules and publishes:
  - Facebook Page single-image/text Page posts.
  - Instagram feed single-image posts for linked professional accounts.
- Backend stores returned post/media IDs as `PublishedPost` records.
- Aggregate metric refresh links existing post-insight rows to published posts.
- Operators can retry retryable failures and disable live publishing via flags/config.

Out of MVP:

- Reels, Stories, carousels, direct messages, comment moderation, social listening, paid boosting,
  native Meta scheduled publishing as source of truth, and user-level engagement identity storage.

## 3. Backend Requirements

- Keep all Content Ops records tenant-scoped and processed inside tenant context.
- Keep provider interfaces isolated in publisher/provider modules; do not put Graph calls directly
  in serializers, views, or generic Celery task bodies.
- Live provider adapters must be disabled by default and separately gated for Facebook and
  Instagram.
- Provider errors must persist only client-safe failure codes and sanitized details.
- Token access must use existing encrypted credential storage patterns; no raw tokens in logs,
  exceptions, test fixtures, docs, or evidence packets.
- Publishing identity readiness must remain separate for Page selection, Instagram linkage,
  Facebook publish permission, Instagram publish permission, and reporting readiness.
- Schedule dispatch must keep idempotent attempt creation from immutable approval snapshots.
- Attempt processing must use row locks, bounded retries, jittered exponential backoff, and terminal
  failure after the configured maximum.
- Instagram must create containers near publish time, poll status, publish only ready containers,
  and recreate or fail expired containers safely.
- Asset validation must check channel-specific media, content type, size, dimensions/duration where
  available, public fetchability, and immutable approval snapshot linkage.

## 4. Frontend Requirements

- Keep `/content` usable without live Meta posting; planning/export remains valuable while
  publishing is blocked.
- Show separate readiness axes instead of a single "connected" state.
- Disable publish controls unless every required axis and approval condition is ready.
- Add explicit publish-now confirmation before any live adapter is enabled.
- Show queue lifecycle states accurately: queued, preflight, blocked, container creating, container
  pending, container ready, publishing, published, failed retryable, failed terminal, container
  expired, cancelled.
- Show retry affordances only for retryable failures.
- Preserve local time display in `America/Jamaica` unless the workspace timezone overrides it.
- Make the approval screen clearly show the exact version and media that will publish.
- Keep export history and reporting surfaces aggregate-only and client-safe.

## 5. Meta App Review And Permission Requirements

Before implementation or submission, verify the selected permission family in the Meta developer
console for the target app and Graph API version. Goal M locks the App Review planning target, but
runtime scopes still must not be enabled until the console path, adapters, staging proof, and release
gates pass.

Locked planning target:

- Facebook Page publishing permission for Page posts: `pages_manage_posts`.
- Page listing/context permissions already used by reporting and setup flows, such as Page list and
  engagement/readiness permissions.
- Instagram professional-account publishing primary current family:
  `instagram_business_basic` plus `instagram_business_content_publish`.
- Legacy Instagram fallback: `instagram_basic` plus `instagram_content_publish` only if the Meta app
  console and implementation path explicitly use the older Facebook Login / Instagram Graph API
  publishing flow.
- Test user, test Page, and linked Instagram professional account setup.
- Screencast from login to permission grant to content approval to publish result to aggregate
  reporting.
- Reviewer copy that says ADinsights performs posting on behalf of onboarded business customers and
  only after exact content approval.

## 6. Public Media URL / CDN Requirements

- Meta-fetchable media URLs must be HTTPS.
- URLs must not expose private storage keys, internal filesystem paths, bearer tokens, raw signed URL
  secrets, or tenant identifiers that are not already public.
- URLs must be valid long enough for the publish attempt and Instagram container creation/polling
  lifecycle.
- The fetch endpoint/CDN must return correct content type, content length where possible, and no
  authentication challenge to Meta fetchers.
- Approved media must be immutable for the approval snapshot or versioned so the approved asset
  cannot change after client approval.
- Evidence must include redacted fetch proof and failure behavior for missing, expired, oversized,
  unsupported, and non-public assets.

## 7. State Machines

### Approval

| State | Enters when | Leaves when | Live-posting rule |
| ---- | ---- | ---- | ---- |
| `draft` / `generated` | User or generation job creates a draft/version | submitted for internal review | Cannot publish |
| `internal_review` | User submits exact active version | internal approve/change/reject | Cannot publish |
| `internal_approved` | Internal approver approves active version | submitted for client review | Cannot publish |
| `client_review` | User submits approved version to client | client approve/change/reject | Cannot publish |
| `client_approved` | Client approves active version | scheduled/publish-now | Only approved version may be queued |
| `scheduled` | Publish-capable user schedules approved version | dispatcher queues attempts | Must use approval snapshot |

### Scheduling

| State | Meaning | Required checks |
| ---- | ---- | ---- |
| `scheduled` | Waiting for scheduled time | active version, client approval, target channels, identity readiness |
| `dispatching` | Attempts created or being processed | idempotent attempts per channel |
| `published` | All attempts published | published post IDs present |
| `partially_published` | Some channels published and some blocked/failed | operator triage required |
| `failed` | All attempts blocked/failed terminal | no automatic retry without root-cause fix |
| `cancelled` | User/operator cancelled schedule | no queue processing |

### Publishing

| State | Meaning | Retry rule |
| ---- | ---- | ---- |
| `queued` | Durable attempt ready for processor | process once with lock |
| `preflight` | Validating tenant, schedule, approval, identity, media | failure becomes blocked or retryable depending cause |
| `blocked` | Missing readiness or non-retryable precondition | no automatic retry |
| `publishing` | Provider call in flight | provider result decides next state |
| `published` | Provider returned post/media ID | terminal success |
| `failed_retryable` | Rate limit/transient/provider retryable failure | requeue with jittered backoff up to max attempts |
| `failed_terminal` | Permanent provider or validation failure | terminal until operator fix |
| `cancelled` | Operator/user cancelled | terminal unless new schedule/attempt |

### Instagram Container

| State | Meaning | Rule |
| ---- | ---- | ---- |
| `container_creating` | Preparing media container payload | create only near publish time |
| `container_pending` | Meta accepted container but media not ready | poll status; do not publish yet |
| `container_ready` | Container can be published | call media publish promptly |
| `container_expired` | Container TTL exceeded | recreate only if still retryable and approval/media remain valid |
| `failed_retryable` | transient container/status/publish failure | backoff and retry |
| `failed_terminal` | unsupported media, permission, invalid account, policy failure | operator fix required |

### Metrics

| State | Meaning | Rule |
| ---- | ---- | ---- |
| no snapshot | Published post has no linked metric row yet | show zero/empty aggregate state |
| refresh requested | User/task triggered aggregate metric refresh | read already-synced post insight rows |
| refreshed | Snapshot rows updated | aggregate-only display/export |
| stale/failed | Missing upstream row or task failure | safe operator message; no user-level data |

## 8. Security, PII, Tenant Isolation, And Secrets Rules

- Never log or persist raw OAuth tokens, signed URL secrets, credential refs, provider request
  payloads containing secrets, or unredacted Page/IG IDs in public evidence.
- Keep reversible OAuth tokens in the existing AES-GCM per-tenant DEK/KMS pattern.
- All API reads and writes must require authenticated tenant context.
- Celery tasks must resolve tenant context before reading Content Ops records.
- Evidence and reports must stay aggregate-only; no viewer, commenter, reactor, follower, or
  per-user engagement identity may be stored or exported.
- Provider exceptions must be mapped to stable safe codes before persistence.
- Public media URL proof must not reveal internal storage keys or tenant-private paths.
- Cross-tenant publish attempts, schedules, identities, assets, and published posts must be covered
  by regression tests before live adapters.

## 9. Required Tests Before Live Adapter Work

Goal K must add or re-run focused tests before Goals O/P:

- Backend dry-run approval tests for stale version, non-pending approval, wrong reviewer role,
  missing client approval, and exact approval snapshot binding.
- Scheduler tests for due schedule dispatch, idempotency, frozen target channels, target-specific
  identity lookup, locked rows, cancellation, and timezone handling.
- Publish queue tests for single-attempt processing, due scan processing, safe failure details,
  max attempts, jittered retry, retry API, and terminal transitions.
- Instagram lifecycle tests for create, pending, ready, publish, not-ready, expired, retryable
  provider error, terminal provider error, missing media, and invalid public URL.
- Asset validation tests for unsupported type, oversized media, non-public URL, expired URL, missing
  approved asset, and tenant mismatch.
- Export history tests for create/list/retrieve/download, tenant isolation, failed/missing artifact,
  and frontend rendering.
- Metric refresh tests for aggregate-only snapshots, missing upstream rows, tenant isolation, and
  safe empty state.
- Frontend tests for blocked readiness, ready readiness, retryable queue action, terminal failure,
  container lifecycle labels, publish confirmation, export history, and aggregate report rendering.
- Schema/contract tests for `/api/content-ops/*` OpenAPI stability and serializer redaction.

Minimum matrix before live adapter work:

- `make backend-lint && make backend-test`
- `make frontend-guardrails && make frontend-lint && make frontend-test && make frontend-build`
- `make adinsights-preflight PROMPT="Content Ops pre-live adapter readiness"`

## 10. Debugging / Dry-Run Checklist

- Confirm all live publishing flags are off by default.
- Confirm disabled providers fail closed with `provider_not_configured`.
- Create a tenant-local workspace, publishing identities, brief, draft, asset, active version,
  internal approval, client approval, and schedule.
- Dispatch due schedule and verify exactly one attempt per approved target channel.
- Process attempt with disabled provider and verify safe blocked/failure behavior.
- Process attempt with fake success provider and verify `PublishedPost`, schedule, draft, and queue
  states.
- Process fake retryable and terminal errors and verify safe failure details.
- Exercise Instagram fake container pending, ready, expired, retry, and publish paths.
- Verify media validation blocks non-public or invalid media before publish-bound activation.
- Verify export artifacts can be created, listed, and downloaded without leaking storage internals.
- Refresh metrics from aggregate source rows and verify no user-level metrics are returned.
- Inspect logs for `tenant_id`, `task_id`, `correlation_id`, schedule ID, attempt ID, channel, state,
  and safe failure code.

## 11. Review Gates And Required Reviewers

| Gate | Required reviewers | Must happen before |
| ---- | ---- | ---- |
| Goal J audit accepted | Raj, Mira, Sofia, Lina, Maya, Nina, Leo, Hannah as reviewer lenses | Goal K execution |
| Goal K debug/test hardening | Raj, Mira, Sofia, Lina, Leo, Hannah | Contract/security signoff |
| Goal L contract/security review | Sofia, Nina, Raj, Mira | App Review packet and live adapters |
| Goal M App Review evidence spec | Maya, Hannah, Raj | OAuth scope expansion or live adapter activation |
| Goal N media URL/CDN proof | Nina, Maya, Hannah, Raj | Instagram live adapter |
| Goal O Facebook adapter | Sofia, Maya, Nina, Leo, Raj, Mira | Facebook staging proof |
| Goal P Instagram adapter | Sofia, Maya, Nina, Leo, Raj, Mira | Instagram staging proof |
| Goal Q frontend live readiness | Lina, Sofia, Hannah | staging publish proof |
| Goals R/S staging proof | Maya, Nina, Leo, Hannah, Raj | final release pass |
| Goal T release readiness | Raj, Mira, Sofia, Lina, Maya, Nina, Leo, Hannah | production enablement |

## 12. Staging Evidence Checklist

- Redacted tenant ID or tenant alias.
- Redacted Meta app ID, Page ID, IG user ID, post ID, and media ID.
- Feature flag/config snapshot showing live posting explicitly enabled only for staging target.
- Readiness response with separate axes.
- Approved draft version and immutable approval snapshot.
- Public media URL proof, including fetchability and redaction.
- Publish attempt state transitions with timestamps.
- Provider response summary with raw response/token redacted.
- Structured logs with correlation ID and no secrets.
- Queue delay, publish duration, retry count, and failure-code metrics.
- Published Facebook Page post visible in staging proof.
- Published Instagram media visible in staging proof.
- Aggregate metric refresh proof.
- Rollback proof showing live publishing can be disabled without disabling planning/export.

## 13. Launch Blockers

- `GATE_BLOCK` from Goal I has not been resolved.
- Raj/Mira architecture-scope review has not accepted the cross-stream package or PR split.
- Contract warning has not been resolved or explicitly accepted.
- Nina security/secrets/PII review has not signed off.
- Meta permission family is not locked for the current production app and Graph API version.
- App Review reviewer copy, screencast, test accounts, and redaction packet are incomplete.
- Public media URL/CDN proof is missing.
- Live Facebook and Instagram adapters do not exist.
- Staging Facebook and Instagram publish proof does not exist.
- Frontend live-publish confirmation and blocked/ready polish are not complete.
- Required backend/frontend/preflight matrices have not been rerun after the next code changes.

## 14. Task Breakdown Ordered By Dependency

### Waterfall Dependencies

1. Goal J: accept this cross-stream audit/spec and launch blocker list.
2. Goal K backend: harden dry-run tests for approval, scheduling, queue, retry, Instagram lifecycle,
   asset validation, export history, and metric refresh.
3. Goal K frontend: harden Content Ops tests for blocked/ready states, lifecycle labels, retry,
   export history, and reports.
4. Goal L: contract/security review; resolve doc drift and prove tenant/secrets boundaries.
5. Goal M: App Review evidence spec; lock permission family after current verification.
6. Goal N: public media URL/CDN proof.
7. Goal O: live Facebook Page adapter behind disabled-by-default config.
8. Goal P: live Instagram adapter behind beta flag with container lifecycle handling.
9. Goal Q: frontend live-publishing readiness polish.
10. Goal R: Facebook staging publish proof.
11. Goal S: Instagram staging publish proof.
12. Goal T: final release readiness pass and go/no-go.

### Parallelizable After Goal J

- K backend and K frontend can be split into separate bounded sessions after Raj confirms the split.
- Goal M App Review copy/spec can proceed in docs while Goal K tests are being hardened, as long as
  permission claims remain marked "must verify" until Maya confirms them.
- Goal N media URL design/proof can proceed in parallel with Goal M, but live adapter work must wait
  for both.
- Hannah can prepare evidence templates/runbook proof while Sofia/Nina review contract and security.

### Required Resources

- Staging Meta app or test app.
- Test Facebook Page with publish-capable test user.
- Linked Instagram professional account for the test Page.
- Redaction-safe evidence storage under `docs/project/evidence/content-operations/`.
- Public HTTPS media host/CDN or equivalent staging endpoint.
- Operator account with publish-capable ADinsights role.
- Access to structured task logs and metrics for staging validation.
- Reviewer time from Raj, Mira, Sofia, Lina, Maya, Nina, Leo, and Hannah.

## 15. Proposed Next Smaller `/goal` Structure

Start here:

```text
/goal Goal K1: Backend Content Ops dry-run and test-hardening pass.

Scope: backend/ only unless a docs note is required.
Do not implement live Graph adapters and do not enable live publishing.

Inspect the current worktree first. Harden tests and fix bugs for approval snapshots, due scheduling,
publish queue processing, retry behavior, Instagram fake container lifecycle, asset validation,
export artifacts, and aggregate metric refresh. Verify tenant isolation, safe failure details,
bounded retry attempts, and disabled-provider fail-closed behavior.

Run: make backend-lint && make backend-test
Also run ADinsights preflight with a Content Ops pre-live backend hardening prompt.
```

Then:

```text
/goal Goal K2: Frontend Content Ops dry-run and live-readiness test-hardening pass.

Scope: frontend/ only unless a docs note is required.
Do not enable live publishing.

Inspect the current worktree first. Harden tests and fix UI bugs for blocked/ready readiness axes,
publish attempt lifecycle states, retryable vs terminal failures, Instagram container labels,
export history, calendar/client review views, aggregate reports, and publish confirmation behavior.

Run: make frontend-guardrails && make frontend-lint && make frontend-test && make frontend-build
```

Then:

```text
/goal Goal L: Content Ops contract and security review.

Scope: docs/tests only unless a required fix is discovered.
Do not enable live publishing.

Review tenant isolation, API contracts, token boundaries, secret logging, provider error sanitization,
credential handling, public media URL leakage risk, and aggregate-only reporting. Resolve or log API
contract doc drift, including frontend export history status.

Run the relevant focused tests and make adinsights-preflight with a contract/security prompt.
```

## Reviewer Findings

### Raj: Cross-Stream / Release Architecture

Good: The current package has clear docs, evidence, and separate readiness axes. Queue and UI work
are staged rather than live-enabled.

Bad/risky: The work spans backend, frontend, and docs. This must not move as one unreviewed bundle.
The Goal I `GATE_BLOCK` is valid and should stay blocking.

Missing: A PR split or release track map that proves each top-level folder gets its owner tests and
reviewers.

Improve: Treat K1, K2, L, M, and N as release-blocker remediation before live adapters.

### Mira: Architecture / Refactor Risk

Good: Provider boundaries and disabled defaults reduce blast radius.

Bad/risky: Live provider implementation could easily leak into views/tasks or collapse Facebook and
Instagram workflows if not constrained.

Missing: Explicit adapter interface acceptance rules, rollback notes, and no-refactor boundaries for
Goals O/P.

Improve: Keep Facebook and Instagram adapters separate. Do not refactor the whole Content Ops app
while adding live Graph calls.

### Sofia: Backend / API Contracts

Good: The API contract is additive and has role gates, read-only workflow fields, and safe error
codes.

Bad/risky: Contract doc drift exists around frontend export history. Publish-now still returns a
non-live implementation path and must not be treated as ready.

Missing: Pre-live OpenAPI/schema coverage for the final live adapter response shapes and safe error
codes.

Improve: Fix doc drift in Goal L and add contract tests before live adapter work.

### Lina: Frontend / UX Workflow

Good: The `/content` route covers the core operating workflow and remains useful without live
publishing.

Bad/risky: Live publishing needs stronger blocked/ready messaging, lifecycle state labels, and
confirmation behavior before users can safely press publish.

Missing: UI proof for retryable vs terminal failures, container lifecycle labels, and final
publish-now confirmation.

Improve: Split frontend hardening into K2/Q rather than coupling it to backend live adapter work.

### Maya: Meta Integration / App Review

Good: The docs correctly avoid enabling scopes before evidence and App Review readiness.

Bad/risky: Before Goal M, the permission family was not locked. Do not enable runtime scopes until
the Goal M packet, Meta app console evidence, staging proof, and release gates agree.

Missing: Meta app console evidence, recorded screencast, test account execution, staging app/Page/IG
proof, and current Graph API version confirmation.

Improve: Goal M should produce a submission packet before any OAuth scope expansion or production
credential path is used.

### Nina: Security / Secrets / PII

Good: The current design says aggregate-only reporting and write-only credential/storage internals.

Bad/risky: Live providers introduce token retrieval, provider payloads, signed/public URLs, and
evidence redaction risks.

Missing: Proof that provider errors, logs, screenshots, and artifacts never include raw tokens,
signed URL secrets, storage keys, or user-level engagement identities.

Improve: Goal L must include negative tests and evidence redaction checks before live adapter work.

### Leo: Celery / Scheduler / Retry Behavior

Good: Due scan, retry scan, and process scan exist and use durable attempts with bounded retries.

Bad/risky: Live Graph calls will add real rate limits, timeouts, duplicate-post risk, and container
expiry timing pressure.

Missing: Dry-run evidence for concurrent processors, skip-locked behavior, retry jitter, max-attempt
terminal transition, and Instagram container expiry/recreate behavior.

Improve: Goal K1 should stress failure paths before provider adapters are introduced.

### Hannah: Evidence / Runbooks / Release Proof

Good: Goal I evidence and runbooks already document the blocked release state.

Bad/risky: Evidence is currently local and dry-run oriented; it does not prove staging publishing,
App Review readiness, or rollback.

Missing: Redacted staging proof packets for Facebook and Instagram, plus final preflight evidence
after blockers are closed.

Improve: Standardize evidence templates now so Goals R/S/T can be reviewed without reconstructing
the story later.
