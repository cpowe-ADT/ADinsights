# Content Operations Sprint 0 Decisions

Status: partially accepted decisions with active implementation
Related:

- `docs/project/content-operations-meta-publishing-spec.md`
- `docs/project/content-operations-architecture-sprint-plan.md`
- `docs/project/content-operations-implementation-backlog.md`

Timezone baseline: `America/Jamaica`
Last updated: 2026-06-06

## Purpose

Track the minimum Sprint 0 decisions needed to keep Content Operations implementation safe and
agent-ready.

This document is intentionally short and decision-oriented. Some decisions are now implemented in
the backend foundation; external/App Review items remain blocked until evidence exists.

## Decision Summary

| ID      | Decision                   | Recommendation                                                               | Status                                                                                | Owners              |
| ------- | -------------------------- | ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- | ------------------- |
| CO-D0-1 | Backend app boundary       | Create a new `backend/content_ops/` Django app                               | Accepted/implemented; still needs Raj/Mira architecture review before release         | Sofia + Mira + Raj  |
| CO-D0-2 | First code ticket          | Start with `CO-1A` backend data model only                                   | Superseded by completion of CO-1A                                                     | Sofia               |
| CO-D0-3 | Meta publishing scope      | Do not add runtime publish scopes until Meta permission family is reverified | Accepted; external evidence still blocked                                             | Maya + Raj          |
| CO-D0-4 | Scheduling source of truth | ADinsights owns scheduling; publish at due time                              | Accepted/partially implemented; due/retry beat scans active, live publishing inactive | Leo + Raj           |
| CO-D0-5 | Instagram container timing | Create containers only near publish time                                     | Accepted; implementation not started                                                  | Leo + Maya          |
| CO-D0-6 | Asset hosting              | Private storage plus short-lived public HTTPS publish URLs                   | Proposed; deployment proof still needed                                               | Nina + Victor       |
| CO-D0-7 | Reporting source of truth  | API aggregate snapshots first; dbt marts later                               | Accepted/partially implemented                                                        | Sofia + Priya       |
| CO-D0-8 | Frontend start mode        | Build mocked frontend after backend contract skeleton is named               | Accepted/partially implemented; state mapping and workflow depth need hardening       | Lina + Joel         |
| CO-D0-9 | AI safety                  | Structured outputs, redaction, evals, human approval before scheduling       | Accepted/partially implemented                                                        | Sofia + Nina + Omar |

Status meanings:

- `Accepted/implemented`: the repo now follows the decision, but release review may still be
  required.
- `Accepted/partially implemented`: the direction is locked, but a bounded follow-up ticket remains.
- `Accepted`: the rule is active even if implementation has not begun.
- `Proposed`: the recommendation still needs proof or owner confirmation.
- `Superseded`: the decision was valid for first implementation but is no longer a future gate.

## CO-D0-1: Backend App Boundary

Recommendation: create a new Django app at `backend/content_ops/`.

Rationale:

- Content Operations is a distinct domain from existing Meta onboarding and paid reporting.
- It owns drafts, versions, approvals, AI jobs, schedules, publish attempts, published posts, and
  organic reporting snapshots.
- Keeping it separate reduces the chance that Meta auth, Page selection, Instagram linkage,
  publishing readiness, and reporting readiness collapse into one state.

Implementation note:

- `backend/content_ops/` should import existing integration services only through narrow service
  interfaces.
- Existing `backend/integrations/` remains source-of-truth for Meta OAuth, Page discovery, and
  credential lifecycle.
- Existing `backend/analytics/` remains source-of-truth for paid/warehouse dashboard reporting until
  organic reporting contracts prove stable.

Current disposition: implemented. Keep future provider, scheduler, frontend, and reporting work
inside this app or a clearly documented adjacent boundary.

## CO-D0-2: First Code Ticket

Recommendation: start with `CO-1A` only after this decision record is accepted.

First code ticket:

- Add backend app and models.
- Add migrations and model tests.
- Do not add Meta calls.
- Do not add AI provider calls.
- Do not add frontend routes.
- Do not change runtime OAuth scopes.

Acceptance:

- Tenant-scoped models exist.
- Approval/version/schedule/publish-attempt primitives can be tested without external credentials.
- `make backend-lint && make backend-test` passes or unrelated failures are documented.

Current disposition: complete. Future first-choice tickets are listed in the build control sheet in
`docs/project/content-operations-implementation-backlog.md`.

## CO-D0-3: Meta Publishing Scope

Recommendation: keep all publish scopes out of runtime OAuth until Sprint 0 confirms current Meta
permission names and App Review requirements.

Goal M locked the planning target, but the selected app console path must still be verified before
runtime OAuth changes:

- Facebook Page publish permission: `pages_manage_posts`.
- Instagram primary current permission family: `instagram_business_basic` plus
  `instagram_business_content_publish`.
- Instagram legacy fallback: `instagram_basic` plus `instagram_content_publish` only if the Meta app
  console and implementation path explicitly use the older Facebook Login / Instagram Graph API
  publishing flow.
- Confirm selected app type and Graph API version.
- Confirm test Page and linked Instagram professional account are available.

No production OAuth scope changes should ship from Sprint 0.

Current disposition: accepted. No live publishing scopes should be enabled until CO-5A/CO-5F evidence
exists and Raj/Maya sign off.

## CO-D0-4: Scheduling Source of Truth

Recommendation: ADinsights owns scheduling.

Rationale:

- One scheduler can govern Facebook and Instagram consistently.
- Approval snapshots, retries, audit logs, and queue observability stay in ADinsights.
- Instagram media containers expire, so native long-range scheduling is not a good common model.

MVP behavior:

- Store approved schedule in ADinsights.
- At due time, Celery locks and dispatches the schedule.
- Publish attempts are per-channel and idempotent.

Current disposition: implemented for disabled-by-default queue processing. Queue records, retry
requeue, fakeable processing, and every-minute due/retry/process beat scans exist. Live provider
handoff remains blocked behind App Review, credential, and release evidence.

## CO-D0-5: Instagram Container Timing

Recommendation: create Instagram media containers only inside the near-publish window.

Default near-publish window:

- 5 to 15 minutes before scheduled time.

Required states:

- `container_creating`
- `container_pending`
- `container_ready`
- `container_expired`
- `failed_retryable`
- `failed_terminal`

Required behavior:

- Expired containers are recreated for retryable attempts.
- Container IDs are not durable schedule artifacts.
- Video/Reels/carousel support is beta or later.

Current disposition: implemented behind a fakeable/disabled provider boundary. Live Instagram work
remains blocked behind App Review, live provider adapter, staging account proof, and beta scope.

## CO-D0-6: Asset Hosting

Recommendation: store assets privately and generate short-lived public HTTPS URLs for Meta fetches.

Required design:

- Private durable storage for originals and generated assets.
- Short-lived no-auth URL/proxy for publish attempts.
- Correct `Content-Type` and `Content-Length`.
- No redirects that Meta cannot fetch.
- URL lifetime long enough for Meta fetch/polling, short enough to limit exposure.
- Signed URL secrets never logged.

MVP supported media:

- Single-image Facebook Page post.
- Single-image Instagram feed post after beta permission proof.

Current disposition: proposed. Do not start CO-3C/CO-7C activation until the URL strategy is proven
in staging or through a deployment-equivalent test.

## CO-D0-7: Reporting Source of Truth

Recommendation: use API aggregate metric snapshots first.

Rationale:

- Organic publishing contract needs real staging proof before dbt mart promotion.
- API snapshots can enforce aggregate-only guarantees early.
- Paid Meta and organic Meta reporting stay labeled separately.

Do not create dbt organic marts until:

- published-post ID linkage is stable
- aggregate metric snapshots pass tenant isolation tests
- no user-level fields are present
- beta reporting evidence exists

Current disposition: partially implemented. API aggregate endpoints exist over stored rows; refresh
workers and dbt marts remain deferred.

## CO-D0-8: Frontend Start Mode

Recommendation: frontend starts with mocked fixtures after backend endpoint names and enum contracts
are stable.

Required first screens:

- `/content`: calendar and production queue
- draft editor
- approval queue
- readiness panel
- asset library
- content reports

UX rule:

- Publishing controls must be disabled by exact readiness blocker, not by one generic Meta connected
  state.

Current disposition: partially implemented. `/content` exists with mock fallback and partial live API
wiring. Before deeper workflow or publish controls, it must preserve exact backend state, approval,
readiness, and queue reason codes instead of collapsing them into simplified UI states.

## CO-D0-9: AI Safety and Evals

Recommendation: AI generation must use structured outputs, prompt redaction, local evals, and human
approval before scheduling.

Required before provider tuning:

- caption schema eval
- blocked-term eval
- required-disclaimer eval
- prompt redaction tests
- asset dimension/nonblank checks
- moderation result capture

Human approval remains mandatory. AI output can create draft versions, not publishable schedules.

Current disposition: partially implemented. Caption generation has structured schema, redaction,
fakeable provider processing, no-side-effect tests, a golden fixture harness, and caption quota
guardrails; graphics and live provider tuning remain follow-up.

## Sprint 0 Checklist

- [ ] Raj confirms cross-stream slice plan before release.
- [ ] Mira confirms backend app boundary before release.
- [ ] Maya confirms Meta permission validation path.
- [ ] Nina/Victor confirm asset URL strategy.
- [ ] Lina/Joel confirm frontend route map.
- [x] Sofia/Omar confirm and implement golden eval fixture harness.
- [x] First code ticket `CO-1A` completed as backend-only.

## Open Risks

- Meta App Review may require different permission names or app type setup than expected.
- Asset URL strategy may require deployment/CDN work before Instagram can be proven.
- Backend app creation touches settings/routing/migrations and needs Raj/Mira review.
- Frontend can overbuild against mock contracts if backend enum names are not stabilized first.

## Next Recommended Action

Use the build control sheet in `docs/project/content-operations-implementation-backlog.md`. The next
repo-ready code ticket is `CO-2A`/`CO-2B` mocked frontend workspace unless Raj chooses to hold for
architecture review first.
