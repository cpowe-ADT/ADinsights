# ADinsights Content Operations for Meta Publishing

Status: proposal
Owner routing: Raj coordinates implementation split across backend, frontend, docs, scheduler/ops, and reporting slices.
Timezone baseline: `America/Jamaica`
Last updated: 2026-06-05

## Purpose

Add a Content Operations module that lets agencies generate, store, approve, schedule, publish,
export, and report on organic Facebook Page and Instagram professional-account content from
ADinsights.

This is product and contract design only. It does not create runtime endpoints, database tables,
scheduler tasks, OAuth scopes, or frontend routes by itself.

The business thesis is that agencies are being squeezed by higher labor costs, client pricing
pressure, and hard-to-retain creative talent. ADinsights can reduce production drag by combining
reporting, AI-assisted content creation, approvals, scheduling, publishing, exports, and aggregate
performance feedback in one tenant-safe workflow. This should be built as an agency operating
system module, not as a one-off "post to Instagram" button.

## Canonical Planning Prompt

Use this prompt to start any implementation-planning or reviewer session. It forces the right
sequence, avoids scope collapse, and makes the reviewer produce testable outputs.

```text
You are designing the ADinsights Content Operations module for organic Meta publishing.

Goal:
Build a tenant-safe agency workflow that lets users create content plans, generate AI captions,
generate AI graphic batches, store assets, route internal approval, route client approval, schedule
approved content, publish to Facebook Pages and linked Instagram professional accounts, export
client-facing content plans, and report on aggregate organic post performance.

ADinsights constraints:
- Preserve Django/DRF/Celery backend and React/Vite frontend.
- Preserve tenant isolation, RLS assumptions, encrypted OAuth tokens, structured JSON logs, and no
  secret logging.
- Do not collapse Meta auth, Page selection, Instagram linkage, Facebook publishing readiness,
  Instagram publishing readiness, and reporting readiness into one state.
- Use ADinsights-owned scheduling. For Instagram, create media containers only near publish time
  because containers expire.
- Store only aggregate reporting metrics. Never store user-level engagement, viewer, commenter, or
  reaction identity data.
- Split backend, frontend, docs, scheduler/ops, and reporting work unless Raj coordinates a
  cross-stream PR.

Work step by step:
1. Explain the target agency workflow and the MVP/beta/production cuts.
2. Design the data model and state machines.
3. Design the additive DRF API contracts.
4. Explain exactly how Facebook Page publishing and Instagram container publishing should work.
5. List required Meta permissions and App Review evidence, separating current verified permissions
   from permissions that must be rechecked before implementation.
6. Design AI caption and graphic generation with structured outputs, redaction, human approval, and
   repeatable evals.
7. Design scheduler behavior, retries, idempotency, locks, expiry handling, and observability.
8. Design export and reporting linkage with aggregate-only metrics.
9. Produce eval datasets, test cases, and release gates.
10. Identify missing decisions, owners, risks, and reviewer signoffs.

Return:
- PRD
- API contract proposal
- data model proposal
- Meta permission/App Review checklist
- AI generation workflow
- approval workflow
- scheduler/publishing state machine
- reporting integration plan
- eval/test plan
- rollout plan
- risk register
- reviewer scorecards
- implementation slice plan
```

## Scope Principles

- Preserve the stack: Django, DRF, Celery, React, Vite, existing tenant middleware, encrypted
  credentials, structured JSON logs, and existing health endpoints.
- Keep every record tenant-scoped. Backend queries must continue to run under tenant context and
  RLS assumptions.
- Store reversible Meta tokens only through the existing AES-GCM per-tenant DEK/KMS pattern. Never
  log raw tokens, AI prompts that include secrets, signed asset URLs, or upstream request payloads
  containing credentials.
- Keep publishing state separate from existing reporting state. Do not collapse Meta auth, Page
  selection, Instagram linkage, Facebook publishing readiness, Instagram publishing readiness, and
  reporting readiness into one generic status.
- Use app-owned scheduling. ADinsights owns scheduled-at times, approval gates, retries, and queue
  state. For Instagram, create media containers only near the publish attempt because containers
  expire after 24 hours.
- Store only aggregated reporting metrics. Do not ingest or expose user-level engagement records,
  commenters, viewer identities, or per-user reactions.
- Split implementation into separate PR slices unless Raj coordinates a cross-stream PR.

## Deep Design Findings

This module needs more than CRUD screens and a publish endpoint. The product must solve seven
separate problems:

1. Content operating model: briefs, versions, calendars, approvals, exports, and client-visible
   packets.
2. AI production: structured caption variants, graphic batches, redaction, brand constraints,
   version lineage, and quality evals.
3. Asset hosting: durable private storage for ADinsights plus temporary public HTTPS URLs that Meta
   can fetch at publish time.
4. Meta publishing: Page publishing and Instagram container publishing are different workflows and
   need different retry/expiry handling.
5. Approval governance: approval snapshots must bind to exact draft versions and media assets.
6. Reporting takeover: published organic content needs aggregate metrics linked to the originating
   draft, but paid and organic metrics must remain labeled and separate.
7. Operations: permission drift, revoked tokens, Meta API changes, media validation failures, rate
   limits, queue delays, and App Review evidence all need first-class states.

## Missing Decisions and Gaps

These are the main unresolved items that must be closed before backend implementation.

| Area | Missing decision | Why it matters | Proposed default |
| ---- | ---------------- | -------------- | ---------------- |
| Meta permission family | Whether production should use legacy Instagram Graph permissions or newer business permission names | App Review may reject the wrong family or scopes may not appear for the app type | Reverify in Meta developer console before implementation; keep feature flag disabled until confirmed |
| Facebook Page endpoint path | Exact Page publishing endpoint and scheduling fields for current pinned Graph API version | Meta Pages docs can be login-gated and behavior changes by API version | Implement publish-at-due-time first; treat native Meta scheduling as later optimization |
| Asset URL strategy | How Meta fetches media generated/stored privately in ADinsights | Instagram publishing requires Meta to fetch media by URL; private app storage is not enough | Generate short-lived public HTTPS asset URLs at publish time, with content type and size headers validated |
| Media validation | Supported image/video/reel/story/carousel formats per phase | Invalid media creates late publish failures and bad client experience | MVP supports single-image Facebook Page and Instagram feed posts; beta adds reels/carousels after staging proof |
| Client approval identity | Whether clients are ADinsights users or external approval-link users | Affects auth, audit, tenant access, and notifications | MVP uses invited client users with restricted tenant role; external approval links are later |
| Brand governance | Where brand voice, visual rules, disclaimers, and banned claims live | AI output quality depends on structured constraints | Add `brand_profile` on workspace and version it later if needed |
| Reporting source of truth | Whether content metrics are direct API snapshots, dbt marts, or both | Affects data freshness and dashboard consistency | API snapshots first; dbt marts only after beta contract proves stable |
| Human override | Whether operators can bypass approvals for urgent posts | Affects agency governance and audit | Disabled by default; tenant admin override only with required audit reason |
| Failure notifications | Who gets notified for failed scheduled posts | Affects SLA and client trust | Notify draft owner plus operators; client notifications only after internal review |
| AI provider costs | How tenants control batch generation spend | Batch graphics can get expensive quickly | Add tenant quotas, job estimates, and admin limits before beta |

## 1. Product Requirements

### Users

- Agency strategist: creates content briefs, generates captions/graphics, edits drafts, and exports
  calendars.
- Internal approver: checks brand, legal, platform fit, and scheduling readiness before client
  review.
- Client approver: approves, rejects, or requests changes on draft posts and campaign calendars.
- Scheduler/operator: monitors queue health, publish failures, permission drift, and post-publication
  metrics.
- Analyst: links published organic posts to reporting dashboards and exports aggregate performance.

### Core Jobs

- Create a content campaign for a tenant/client, target Facebook Pages and linked Instagram
  professional accounts, and define brand/platform constraints.
- Generate captions and graphic batches with AI, then store generated assets as versioned drafts.
- Route drafts through internal approval and client approval before scheduling.
- Schedule approved posts by platform and channel, with per-channel copy/media variations.
- Publish Facebook Page posts and Instagram content using Meta Graph API credentials that are already
  separated by auth, Page selection, Instagram linkage, and readiness state.
- Export content calendars, approval packets, and aggregate performance summaries.
- Connect published organic content to existing Meta Page/Post Insights reporting and dashboard
  surfaces without storing user-level data.

### Non-Goals for MVP

- Direct messages, comments moderation, inbox workflows, UGC rights management, social listening, and
  paid boosting.
- Cross-network publishing outside Meta/Facebook/Instagram.
- Native Meta scheduled publishing as the source of truth. ADinsights remains the scheduler.
- Instagram container pre-creation days ahead of time.
- Per-user engagement or identity storage.

### Success Metrics

- 95% of approved scheduled posts enter a publish attempt within two minutes of scheduled time.
- 99% of scheduler decisions include `tenant_id`, `task_id`, `correlation_id`, `content_id`, and
  `channel` in structured logs.
- 90% of Meta permission/readiness failures produce actionable reason codes rather than generic
  failures.
- Client approval turnaround and rejection reasons are reportable by aggregate counts.
- Published-post reporting links resolve for at least Facebook Page post insights in MVP, then
  Instagram aggregate media insights in beta.

### User Experience Requirements

- The first screen should be the content calendar and production queue, not a marketing page.
- Users must be able to create a brief, generate drafts, approve, schedule, and export without a live
  Meta connection. Publishing controls stay disabled until readiness passes.
- Readiness UI must show separate blockers: Meta auth, Page selection, Instagram linkage, Facebook
  publish permission, Instagram publish permission, and reporting readiness.
- Draft editor must keep platform variants side by side so Facebook and Instagram copy/media
  differences are visible.
- The approval view must show exactly what version the client approved and what will publish.
- The schedule view must show local `America/Jamaica` time by default and preserve selected tenant or
  workspace timezone.
- The published-post report must link back to the originating draft/version and approval trail.

## 2. API Contract Proposal

All endpoints are additive and live under `/api/content-ops/`. Responses must be tenant-scoped and
paginated where lists can grow.

### Readiness

`GET /api/content-ops/readiness/`

Returns separate readiness axes:

```json
{
  "meta_auth": {"state": "connected", "reason": null},
  "page_selection": {"state": "complete", "page_count": 2, "reason": null},
  "instagram_linkage": {"state": "partial", "linked_count": 1, "reason": "some_pages_without_ig"},
  "facebook_page_publishing": {"state": "ready", "missing_permissions": []},
  "instagram_publishing": {
    "state": "blocked",
    "missing_permissions": ["instagram_content_publish"],
    "business_permission_variant": "needs_review"
  },
  "reporting_readiness": {"state": "ready", "dataset_live_reason": "ready"}
}
```

Do not replace or reinterpret existing `/api/integrations/social/status/`,
`/api/meta/pages/`, `GET /api/meta/accounts/`, or `/api/datasets/status/`. This endpoint composes
their truths and adds publishing-specific readiness only.

Readiness reason codes:

- `not_authenticated`
- `missing_required_permissions`
- `no_page_selected`
- `page_token_missing`
- `page_not_administered`
- `instagram_not_linked`
- `instagram_not_professional`
- `instagram_publish_permission_missing`
- `reporting_not_ready`
- `app_review_required`
- `rate_limit_risk`

### Meta API Mechanics

Treat these as design assumptions to validate in the backend slice against the pinned
`META_GRAPH_API_VERSION`.

Facebook Page publishing path:

1. User completes Meta OAuth.
2. ADinsights lists/selects Facebook Pages separately from ad accounts.
3. ADinsights stores the selected Page publishing identity and encrypted token reference.
4. Preflight verifies Page selection, token validity, Page role, `pages_manage_posts`, and
   `pages_read_engagement`.
5. At due time, Celery calls the Page publishing endpoint with the Page token.
6. ADinsights stores the returned post ID as `PublishedPost.meta_post_id`.
7. A separate reporting job links aggregate Page/Post Insights when available.

Implementation note: do not rely on native Meta scheduling for MVP. Publish at due time from
ADinsights so Facebook and Instagram share one scheduler, retry model, approval snapshot, and audit
trail. Native Page scheduling can be evaluated later only after current Graph API behavior is proven
in staging.

Instagram publishing path:

1. User completes Meta OAuth and Page selection.
2. ADinsights discovers the Instagram professional account linked to the selected Facebook Page.
3. Preflight verifies Instagram linkage, professional-account eligibility, publish permission, media
   type, caption length, and asset URL readiness.
4. At due time, ADinsights creates an Instagram media container with
   `POST /{ig-user-id}/media`.
5. For videos/reels and any async media, ADinsights polls `GET /{container-id}?fields=status_code,status`
   until `FINISHED`, `ERROR`, or expiry/timeout.
6. ADinsights publishes with `POST /{ig-user-id}/media_publish` and stores the returned media ID.
7. A separate reporting job links aggregate media insights when permissions and metric availability
   allow it.

Instagram-specific constraints:

- Instagram consumer accounts are not publishable through this flow; the destination must be a
  Business or Creator/professional account.
- Text-only Instagram posts are out of scope; Instagram publishing requires media.
- Containers are temporary. Do not store them as durable schedule objects and do not create them days
  before publish time.
- Track container status values as operational states. At minimum handle `IN_PROGRESS`, `FINISHED`,
  `ERROR`, `EXPIRED`, and unknown status values safely.
- Carousels require child media containers and a parent carousel container. Keep this out of MVP.
- Reels/video require longer processing windows and stricter media validation. Keep this in beta
  unless staging proof is complete.

Asset serving path:

1. ADinsights stores original and generated assets privately.
2. Before publish, the scheduler creates a short-lived public HTTPS URL or proxy URL that Meta can
   fetch without ADinsights auth.
3. The URL must serve the correct `Content-Type`, `Content-Length`, and final media bytes without
   requiring cookies or bearer tokens.
4. The URL lifetime must exceed the expected Meta fetch/polling window but should expire after the
   publish attempt.
5. The asset service must log safe asset IDs and response metadata, not signed URL secrets.

### API Contract Gaps to Close Before Code

- Decide exact pagination defaults and max page sizes for every list endpoint.
- Define OpenAPI schemas for every enum before frontend work starts.
- Decide whether `workspace_id` is required for all drafts/assets or whether tenant-level library
  assets can be reused across workspaces.
- Define notification endpoints or reuse existing notification-channel contracts for approval and
  failed-publish alerts.
- Define whether exports reuse generic report export jobs or get content-ops-specific export jobs.
- Define event/audit API shape for approval and publishing history.
- Define whether client approval comments are editable, deletable, or immutable audit records.

### Workspaces and Briefs

- `GET /api/content-ops/workspaces/`
- `POST /api/content-ops/workspaces/`
- `GET|PATCH|DELETE /api/content-ops/workspaces/{workspace_id}/`
- `POST /api/content-ops/workspaces/{workspace_id}/briefs/`
- `GET|PATCH /api/content-ops/briefs/{brief_id}/`

Workspace fields: `id`, `tenant_id`, `client_id`, `name`, `objective`, `brand_profile`,
`target_channels`, `timezone`, `created_by`, `created_at`, `updated_at`, `archived_at`.

Brief fields: `id`, `workspace_id`, `campaign_theme`, `audience`, `offer`, `tone`,
`required_terms`, `blocked_terms`, `landing_url`, `date_range`, `status`.

### AI Generation

- `POST /api/content-ops/briefs/{brief_id}/captions/generate/`
- `POST /api/content-ops/briefs/{brief_id}/graphics/generate-batch/`
- `GET /api/content-ops/generation-jobs/{job_id}/`
- `POST /api/content-ops/generation-jobs/{job_id}/cancel/`

Caption generation request:

```json
{
  "platforms": ["facebook_page", "instagram"],
  "count": 12,
  "language": "en",
  "constraints": {
    "max_caption_chars": 1800,
    "include_hashtags": true,
    "include_call_to_action": true
  }
}
```

Graphic generation request:

```json
{
  "count": 8,
  "formats": ["instagram_square", "instagram_portrait", "facebook_landscape"],
  "style_reference_asset_ids": ["uuid"],
  "copy_source": "approved_caption_candidates"
}
```

Generation job response:

```json
{
  "id": "uuid",
  "status": "queued",
  "provider": "openai",
  "input_fingerprint": "sha256:...",
  "prompt_redaction_status": "checked",
  "result_asset_ids": [],
  "created_at": "2026-06-05T10:00:00-05:00"
}
```

### Drafts, Versions, and Assets

- `GET /api/content-ops/drafts/?workspace_id=&status=&channel=&scheduled_from=&scheduled_to=`
- `POST /api/content-ops/drafts/`
- `GET|PATCH|DELETE /api/content-ops/drafts/{draft_id}/`
- `POST /api/content-ops/drafts/{draft_id}/versions/`
- `GET /api/content-ops/drafts/{draft_id}/versions/`
- `POST /api/content-ops/assets/`
- `GET|PATCH|DELETE /api/content-ops/assets/{asset_id}/`

Draft response:

```json
{
  "id": "uuid",
  "workspace_id": "uuid",
  "title": "June promo post",
  "channels": ["facebook_page", "instagram"],
  "state": "client_approved",
  "active_version": {
    "caption": "Caption text",
    "media_asset_ids": ["uuid"],
    "platform_overrides": {
      "instagram": {"caption": "IG caption", "first_comment": "#tags"}
    }
  },
  "approval_summary": {
    "internal": "approved",
    "client": "approved"
  },
  "schedule_summary": {
    "scheduled_at": "2026-06-12T09:30:00-05:00",
    "timezone": "America/Jamaica"
  }
}
```

### Approvals

- `POST /api/content-ops/drafts/{draft_id}/submit-internal-review/`
- `POST /api/content-ops/drafts/{draft_id}/submit-client-review/`
- `POST /api/content-ops/approval-requests/{approval_id}/decisions/`
- `GET /api/content-ops/approval-requests/?workspace_id=&status=&reviewer_type=`

Decision request:

```json
{
  "decision": "approved",
  "comment": "Approved for Friday morning.",
  "approved_version_id": "uuid"
}
```

Approval states: `not_requested`, `pending`, `approved`, `changes_requested`, `rejected`,
`expired`, `superseded`.

### Scheduling and Publishing

- `POST /api/content-ops/drafts/{draft_id}/schedule/`
- `POST /api/content-ops/drafts/{draft_id}/unschedule/`
- `POST /api/content-ops/drafts/{draft_id}/publish-now/`
- `GET /api/content-ops/publishing/queue/?state=&channel=&scheduled_from=&scheduled_to=`
- `GET /api/content-ops/publishing/attempts/{attempt_id}/`
- `POST /api/content-ops/publishing/attempts/{attempt_id}/retry/`

Schedule request:

```json
{
  "scheduled_at": "2026-06-12T09:30:00-05:00",
  "timezone": "America/Jamaica",
  "channels": [
    {"type": "facebook_page", "page_id": "123"},
    {"type": "instagram", "ig_user_id": "1784..."}
  ]
}
```

Scheduling contract:

- `channels` freezes the publish destinations into the schedule approval snapshot as
  `target_channels`.
- If `channels` is omitted, ADinsights snapshots the workspace target channels at schedule time.
- Later workspace channel edits must not change already scheduled destinations.
- When `page_id` or `ig_user_id` is present, dispatch must select the matching publishing identity
  instead of silently using the first selected identity for that platform.

Publish attempt response:

```json
{
  "id": "uuid",
  "draft_id": "uuid",
  "channel": "instagram",
  "state": "container_pending",
  "scheduled_at": "2026-06-12T09:30:00-05:00",
  "attempt_count": 1,
  "meta_container_id": null,
  "published_post_id": null,
  "failure": null,
  "correlation_id": "..."
}
```

### Exports and Reporting

- `POST /api/content-ops/exports/`
- `GET /api/content-ops/exports/{export_id}/`
- `GET /api/content-ops/exports/{export_id}/download/`
- `GET /api/content-ops/reports/overview/?workspace_id=&start_date=&end_date=`
- `GET /api/content-ops/reports/posts/?workspace_id=&start_date=&end_date=&channel=`
- `POST /api/content-ops/published-posts/{post_id}/refresh-metrics/`

Exports support content calendar CSV/PDF, approval packet PDF, platform-ready caption/media ZIP,
and aggregate performance CSV/PDF.

Reporting overview response stores and returns aggregate metrics only:

```json
{
  "workspace_id": "uuid",
  "date_range": {"start_date": "2026-06-01", "end_date": "2026-06-30"},
  "totals": {
    "posts_published": 18,
    "impressions": 120000,
    "reach": 82000,
    "engagements": 5100,
    "clicks": 740
  },
  "by_channel": [
    {"channel": "facebook_page", "posts": 10, "impressions": 70000, "engagements": 3000},
    {"channel": "instagram", "posts": 8, "impressions": 50000, "engagements": 2100}
  ]
}
```

## 3. Data Model Proposal

All tenant-owned models include `tenant_id`, `created_at`, `updated_at`, and audit metadata.

### ContentWorkspace

- `tenant`, optional `client`, `name`, `objective`, `brand_profile`, `target_channels`, `timezone`,
  `archived_at`.

### PublishingIdentity

Represents a publishable Meta destination, separate from reporting readiness.

- `tenant`
- `platform`: `facebook_page` or `instagram`
- `meta_page_id` nullable
- `ig_user_id` nullable
- `display_name`
- `credential_ref` FK to encrypted credential/token record
- `selection_state`: `selected`, `revoked`, `not_selected`
- `publish_readiness_state`: `unknown`, `ready`, `blocked`, `needs_reauth`, `needs_review`
- `publish_readiness_reason`
- `last_checked_at`

### ContentBrief

- `workspace`, `campaign_theme`, `audience`, `offer`, `tone`, `required_terms`, `blocked_terms`,
  `landing_url`, `date_start`, `date_end`, `status`.

### GenerationJob

- `tenant`, `workspace`, `brief`
- `job_type`: `caption`, `graphic_batch`, `variation`, `resize`
- `provider`, `model`
- `status`: `queued`, `running`, `succeeded`, `failed`, `cancelled`
- `input_fingerprint`, `redacted_prompt_summary`, `prompt_policy_result`, `result_summary`,
  `error_code`, `created_by`

Do not store raw prompts when they contain sensitive client data unless they pass redaction and
tenant storage policy. Store prompt fingerprints and summaries for audit.

### MediaAsset

- `tenant`, `workspace`
- `source`: `uploaded`, `ai_generated`, `imported`
- `storage_key`, `mime_type`, `width`, `height`, `duration_seconds`, `alt_text`, `renditions`
- `ai_lineage` JSON with generation job IDs and prompt fingerprint, not secrets
- `status`: `available`, `quarantined`, `deleted`

### ContentDraft

- `tenant`, `workspace`, `brief`, `title`, `state`, `active_version`, `created_by`, `owner`,
  `locked_at`, `locked_by`

Draft states: `draft`, `generated`, `internal_review`, `internal_changes_requested`,
`internal_approved`, `client_review`, `client_changes_requested`, `client_approved`, `scheduled`,
`publishing`, `published`, `partially_published`, `failed`, `cancelled`, `archived`.

### ContentDraftVersion

- `draft`, `version_number`, `caption`, `platform_overrides`, `media_assets`, `created_by`,
  `change_note`, nullable `source_generation_job`.

### ApprovalRequest and ApprovalDecision

ApprovalRequest:

- `draft`, `version`, `reviewer_type`, `status`, `requested_by`, `requested_at`, `due_at`,
  `superseded_at`

ApprovalDecision:

- `approval_request`, `decision`, `comment`, `decided_by`, `decided_at`

### ContentSchedule

- `draft`, `version`, `scheduled_at`, `timezone`
- `state`: `scheduled`, `locked`, `dispatching`, `published`, `partial`, `failed`, `cancelled`
- `scheduled_by`, `approval_snapshot`

### PublishAttempt

- `schedule`, `draft`, `version`, `publishing_identity`, `channel`, `state`, `attempt_count`,
  `idempotency_key`, `correlation_id`, nullable `meta_container_id`, `meta_container_created_at`,
  `meta_post_id`, `failure_code`, `failure_detail_safe`, `next_retry_at`, `started_at`,
  `finished_at`

### PublishedPost

- `tenant`, `workspace`, `draft`, `version`, `publishing_identity`, `channel`, `meta_post_id`,
  `permalink`, `published_at`, `reporting_link_state`, `last_metrics_refresh_at`

### OrganicPostMetricSnapshot

Stores aggregate metrics only.

- `tenant`, `published_post`, `metric_date`, `channel`, `impressions`, `reach`, `engagements`,
  `clicks`, `saves`, `shares`, `video_views`, `source`, `fetched_at`

Unique grain: `(tenant, published_post, metric_date, channel, source)`.

## 4. Meta Permissions and App Review Checklist

### Existing Baseline to Preserve

Current ADinsights Meta onboarding/reporting baseline remains:

- `(ads_read OR ads_management)`
- `business_management`
- `pages_read_engagement`
- `pages_show_list`

The Content Operations module must add publishing permissions only behind feature flags and App
Review readiness. Publishing readiness must not imply reporting readiness.

### Proposed Publishing Permissions

Facebook Page publishing:

- `pages_manage_posts` for creating Page posts.
- `pages_read_engagement` and `pages_show_list` to preserve selected Page discovery and post insight
  reads.
- `pages_manage_metadata` only if the implementation needs Page settings/webhook metadata beyond
  current flows.

Instagram publishing:

- Primary current App Review planning family: `instagram_business_basic` plus
  `instagram_business_content_publish`.
- Legacy fallback only if the Meta app console and implementation path explicitly use the older
  Facebook Login / Instagram Graph API publishing flow: `instagram_basic` plus
  `instagram_content_publish`.

Because Meta permission naming and App Review surfaces change, adapter implementation kickoff must
still confirm the selected product path in the Meta developer console before runtime scopes are
enabled. Goal M locks the App Review planning target and updates:

- `docs/project/meta-permission-profile.md`
- `docs/project/api-contract-changelog.md`
- `docs/runbooks/meta-app-review-validation.md`
- `docs/runbooks/meta-app-review-submission-checklist.md`
- `docs/runbooks/content-operations-app-review.md`

Checklist:

1. Confirm app type, Graph API version, and permission family before code work.
2. Add publish scopes to configuration only under a disabled-by-default feature flag.
3. Keep current reporting runtime gate unchanged.
4. Extend readiness payloads with publishing-specific reason codes rather than changing existing
   Meta reporting contracts.
5. Capture reviewer screencasts showing Facebook Login, Page selection, Instagram linkage check, AI
   draft creation, internal/client approval, scheduled publish or publish-now, and aggregate
   reporting linkage.
6. Explain every permission with the ADinsights wording standard: ADinsights acts on behalf of
   onboarded business customers in a named product surface.
7. Use a Meta Test App and test assets before production App Review submission.
8. Never include raw access tokens, app secrets, or client secrets in evidence.

## 5. AI Generation Workflow

Caption flow:

1. User creates a brief with audience, offer, tone, channels, required terms, and blocked terms.
2. Backend normalizes brief input, strips secrets, and records a prompt fingerprint.
3. Celery starts `content_ops.generate_captions`.
4. AI returns candidate captions with platform-specific variants.
5. Backend runs policy checks for blocked terms, required disclosures, character limits, duplicate
   content, and unsafe claim heuristics.
6. Candidates become draft versions, not scheduled posts.
7. User selects or edits versions before approval.

Batch graphic flow:

1. User selects brief, approved/candidate captions, brand style, and output formats.
2. Celery starts `content_ops.generate_graphics_batch`.
3. Generated images are stored as `MediaAsset` rows with renditions and AI lineage.
4. Asset moderation checks run before assets can be attached to a publishable version.
5. Users can regenerate, crop, resize, or replace assets.
6. Only approved draft versions can be scheduled.

AI guardrails:

- Do not pass OAuth tokens, API keys, raw customer lists, or secrets to AI providers.
- Store prompt fingerprints and redacted summaries by default.
- Record generation provider/model for audit and reproducibility.
- Require human approval before schedule/publish.
- Keep AI generation failure isolated from publishing queues.

### Caption Structured Output Schema

Caption generation should use schema-constrained output so the backend can validate and store
candidates deterministically.

```json
{
  "type": "object",
  "required": ["candidates", "warnings", "input_summary"],
  "properties": {
    "input_summary": {
      "type": "object",
      "required": ["brief_id", "platforms", "tone", "audience"],
      "properties": {
        "brief_id": {"type": "string"},
        "platforms": {"type": "array", "items": {"type": "string"}},
        "tone": {"type": "string"},
        "audience": {"type": "string"}
      }
    },
    "candidates": {
      "type": "array",
      "items": {
        "type": "object",
        "required": [
          "platform",
          "caption",
          "hashtags",
          "cta",
          "alt_text",
          "risk_flags",
          "quality_score"
        ],
        "properties": {
          "platform": {"type": "string", "enum": ["facebook_page", "instagram"]},
          "caption": {"type": "string"},
          "hashtags": {"type": "array", "items": {"type": "string"}},
          "cta": {"type": "string"},
          "alt_text": {"type": "string"},
          "risk_flags": {"type": "array", "items": {"type": "string"}},
          "quality_score": {"type": "number"}
        }
      }
    },
    "warnings": {"type": "array", "items": {"type": "string"}}
  }
}
```

Backend validation still owns final acceptance. The model score is advisory only and cannot approve a
post.

### Graphic Generation Controls

- Generate graphics from sanitized creative briefs, selected captions, brand colors, format targets,
  and optional reference assets.
- Store generated image bytes in ADinsights storage immediately; never depend on temporary provider
  URLs for draft state.
- Save provider, model, prompt fingerprint, revised prompt when available, dimensions, and source
  caption IDs in `ai_lineage`.
- Create deterministic renditions for target formats:
  - `instagram_square`: 1:1
  - `instagram_portrait`: 4:5
  - `facebook_landscape`: 1.91:1
  - `story_reel_vertical`: 9:16, beta only
- Run visual QA before assets can enter approval:
  - non-blank image
  - expected dimensions/aspect ratio
  - text readability threshold
  - blocked logo/claim checks where brand policy defines them
  - moderation result present
- Batch jobs must have explicit count, formats, cost estimate, timeout, and cancellation path.

### Prompt Redaction Pipeline

1. Normalize the brief and remove OAuth tokens, API keys, emails not needed for the creative task,
   URLs with credentials, phone numbers unless explicitly allowed, and raw customer identifiers.
2. Replace sensitive values with stable placeholders before sending to the AI provider.
3. Store a prompt fingerprint and redacted prompt summary.
4. Store raw prompt only if tenant policy allows it and redaction status is `passed`.
5. Include `tenant_id`, `generation_job_id`, and `correlation_id` in structured logs, but never log
   prompt text by default.

### AI Failure States

- `provider_unavailable`
- `rate_limited`
- `quota_exceeded`
- `schema_invalid`
- `policy_blocked`
- `asset_moderation_failed`
- `image_decode_failed`
- `dimension_validation_failed`
- `cancelled_by_user`

These failure states should be visible in the generation job UI and safe to export in support
evidence.

## 6. Approval Workflow

Internal approval:

1. Draft owner submits an active version to internal review.
2. Draft locks for review. New edits create a new version and supersede pending requests.
3. Internal approver can approve, request changes, or reject.
4. Internal approval is required before client review unless a tenant policy explicitly allows direct
   client review.

Client approval:

1. Internal-approved version is sent to client review.
2. Client can approve, request changes, or reject.
3. Changes requested creates a new draft version and returns to internal review.
4. Client approval snapshot is copied into `ContentSchedule` when scheduled.
5. Any post-approval content/media edit invalidates client approval and requires resubmission.

Permission model:

- Strategist: create/edit drafts and submit review.
- Internal approver: approve internal reviews and schedule approved content.
- Client approver: approve/reject assigned client review requests only.
- Operator/admin: retry/cancel publishing attempts and manage identities.
- Viewer: read/export only.

## 7. Scheduler and Publishing State Machine

Schedule state:

```text
draft -> internal_review -> internal_approved -> client_review -> client_approved
client_approved -> scheduled -> locked -> dispatching -> published
dispatching -> partial
dispatching -> failed
scheduled -> cancelled
```

Publish attempt states:

- Common: `queued`, `preflight`, `blocked`, `publishing`, `published`, `failed_retryable`,
  `failed_terminal`, `cancelled`.
- Facebook Page: `queued`, `preflight`, `publishing`, `published`, `failed_retryable`,
  `failed_terminal`.
- Instagram: `queued`, `preflight`, `container_creating`, `container_pending`, `container_ready`,
  `publishing`, `published`, `failed_retryable`, `failed_terminal`, `container_expired`.

Scheduler rules:

- Celery beat scans due `ContentSchedule` rows in a short rolling window.
- The scanner locks due schedules with `select_for_update(skip_locked=True)` or equivalent safe
  locking to avoid duplicate dispatch.
- Each channel creates a separate `PublishAttempt` with an idempotency key.
- Facebook Page posts can publish directly after preflight.
- Instagram attempts create containers only within a near-publish window, recommended 5 to 15
  minutes before scheduled time.
- Instagram container IDs are never treated as durable schedule artifacts. If a container expires or
  the attempt is retried after expiry, create a fresh container.
- Retry with exponential backoff, base 2, max five attempts, with jitter.
- Terminal failures require human action when caused by permissions, revoked tokens, missing Page,
  missing Instagram linkage, unsupported media, or App Review rejection.
- Structured logs include `tenant_id`, `task_id`, `correlation_id`, `schedule_id`, `attempt_id`,
  `draft_id`, `channel`, `state`, and safe `failure_code`.

Preflight checks:

- Tenant and client ownership.
- Draft state is `client_approved`.
- Scheduled version matches approval snapshot.
- Media assets are available and platform-valid.
- Publishing identity is selected and active.
- Meta auth is connected.
- Page selection is complete for Facebook Page publishing.
- Instagram linkage is complete for Instagram publishing.
- Required publishing permissions are granted.
- Reporting readiness is checked separately but does not block publishing unless tenant policy says
  reporting linkage is mandatory.

## 8. Reporting Integration Plan

Linkage:

- Persist `PublishedPost.meta_post_id` and channel after publish.
- For Facebook Page posts, link to existing Page/Post Insights flows where possible.
- For Instagram, link aggregate media insights only after permission and App Review readiness are
  confirmed.
- Populate `reporting_link_state` independently from publishing state.

Metrics:

- MVP aggregate fields: `posts_published`, `impressions`, `reach`, `engagements`, `clicks`,
  `shares`, `saves`, `video_views`.
- Do not store user IDs, commenters, viewer lists, reaction identities, follower-level data, or
  person-level data.

Refresh cadence:

- Refresh recent published posts daily at 06:10 `America/Jamaica`.
- Refresh posts from the last seven days with a rolling lookback.
- Allow manual refresh per post with throttling and structured audit logs.
- Aggregate into a content-ops reporting API first. dbt mart integration is a beta/production slice
  after raw contract validation.

Dashboard fit:

- Add an organic content report page with calendar, approval funnel, publishing status, and aggregate
  post performance.
- Add optional links from Meta Pages reporting to the originating ADinsights draft.
- Keep paid ads metrics and organic post metrics separate, with combined summaries only after
  explicit labeling.

## 9. Test and Eval Plan

Backend:

- Serializer tests for optional/null fields, approval decisions, schedule validation, readiness
  reason codes, and tenant scoping.
- Model tests for approval invalidation, schedule locks, idempotency keys, and published-post metric
  aggregate grain.
- Celery task tests for due schedule scan, per-channel attempts, retry/backoff, Instagram container
  expiry recreation, and terminal failures.
- Permission tests for strategist, internal approver, client approver, operator, and viewer roles.
- Contract tests for OpenAPI paths and additive readiness shape.
- Commands: `make backend-lint && make backend-test`; run `backend/.venv/bin/python backend/manage.py backend_release_preflight` before release handoff.

Frontend:

- Unit tests for calendar, approval queue, draft editor, asset picker, readiness banners, and publish
  queue states.
- Integration tests with mocked readiness axes so UI does not collapse statuses.
- Accessibility checks for approval actions and calendar keyboard navigation.
- Command: `make frontend-guardrails && make frontend-lint && make frontend-test && make frontend-build`.

Scheduler/Ops:

- Scheduler duplicate-dispatch tests under concurrent workers.
- Observability tests for required structured log keys.
- Runbook dry-run for permission drift, revoked token, Instagram linkage missing, expired container,
  and rate-limit failures.
- Commands: `docker compose -f docker-compose.dev.yml config` and `python3 backend/manage.py backend_release_smoke --strict-observability`.

Reporting/dbt:

- API aggregate metric tests prove only aggregate metrics are returned.
- dbt mart tests added only when organic content marts are introduced.
- Contract guard preflight for reporting contract changes.

AI evaluation:

- Caption quality rubric: relevance, platform fit, brand adherence, CTA clarity, policy safety,
  duplication risk.
- Graphic quality rubric: brand fit, text legibility, safe content, correct dimensions, non-blank
  output, media policy fit.
- Golden brief set per tenant-safe fixture data.
- Regression checks for blocked terms and required disclosures.
- Human approval remains mandatory before scheduling.

### Eval Suites

The module needs product evals, model evals, API contract evals, and operations evals. Treat these as
separate gates.

| Suite | What it proves | Primary owner | Minimum pass gate |
| ----- | -------------- | ------------- | ----------------- |
| `caption_schema_eval` | AI caption output matches the JSON schema and backend can deserialize it | Backend AI slice | 100% valid schema on golden set |
| `caption_brand_eval` | Captions match brand voice, include required terms, avoid blocked terms, and fit platform limits | Strategy/product + backend | >=90% reviewer pass, 0 blocked-term leaks |
| `caption_safety_eval` | Captions avoid unsupported claims, sensitive targeting language, and unsafe regulated claims | Product + security | 0 critical policy failures |
| `graphic_asset_eval` | Generated graphics are non-blank, correct aspect ratio, readable, and pass moderation | Frontend/design + backend AI | >=95% technical pass, 0 moderation criticals |
| `approval_integrity_eval` | Approved version is exactly the scheduled/published version | Backend + QA | 100% invariant pass |
| `scheduler_due_time_eval` | Due posts dispatch on time without duplicate attempts | Scheduler | P95 dispatch <=2 minutes, 0 duplicate publishes |
| `instagram_container_eval` | Container creation, polling, expiry, and recreation behave correctly | Scheduler/integrations | 100% deterministic state transitions in tests |
| `readiness_separation_eval` | UI/API never collapses auth, Page, Instagram, publishing, and reporting readiness | Backend + frontend | 100% mocked-state coverage |
| `aggregate_reporting_eval` | Reports expose only aggregate metrics and link to published posts | Backend/reporting | 0 user-level fields, 100% tenant isolation |
| `export_packet_eval` | Calendar/export artifacts are complete, client-safe, and match approved versions | Frontend/export | 100% fixture snapshot match |

### Golden Eval Dataset

Create tenant-safe fixtures under the eventual backend/frontend test fixture folders. The first eval
set should include at least these cases:

- Jamaican retail weekend promotion with required offer terms.
- B2B service thought-leadership post with no discount language.
- Restaurant event announcement with date/time and address.
- Political or regulated-adjacent prompt that must be blocked or flagged.
- Healthcare-like claim prompt that must avoid unsupported outcomes.
- Brand profile with banned words and required disclaimer.
- Short Instagram caption with hashtags.
- Longer Facebook Page caption with link and CTA.
- Single-image graphic batch in three aspect ratios.
- Failed image generation result.
- Missing Meta auth.
- Meta auth connected but no Page selected.
- Page selected but Instagram not linked.
- Instagram linked but publish permission missing.
- Client-approved post edited after approval.
- Due schedule already locked by another worker.
- Instagram container expires before publish.
- Meta returns retryable rate-limit error.
- Meta returns terminal permission error.
- Reporting linked but no metrics available yet.

### Model Evals With OpenAI Evals

Use OpenAI platform evals for caption generation where possible, and keep deterministic local tests
for backend invariants. The eval item schema should include:

```json
{
  "brief": {
    "audience": "string",
    "offer": "string",
    "tone": "string",
    "platform": "facebook_page|instagram",
    "required_terms": ["string"],
    "blocked_terms": ["string"]
  },
  "expected": {
    "must_include": ["string"],
    "must_not_include": ["string"],
    "max_chars": 2200,
    "needs_refusal_or_flag": false
  }
}
```

Recommended graders:

- Exact match or regex grader for required/blocked terms.
- JSON schema grader for structure.
- Label/model grader for brand fit and CTA clarity.
- Custom Python grader for character limits, hashtag count, duplicate similarity, and required
  disclaimer checks.

Do not use model eval scores as publish approval. They are regression gates for the generator and
signals for human reviewers.

### Local Deterministic Evals

Backend deterministic evals:

- `test_caption_schema_rejects_missing_required_keys`
- `test_caption_generation_redacts_secret_like_values`
- `test_blocked_terms_never_create_publishable_version`
- `test_approval_snapshot_invalidates_after_caption_edit`
- `test_schedule_rejects_unapproved_version`
- `test_instagram_container_recreated_after_expiry`
- `test_publish_attempt_idempotency_prevents_duplicate_post`
- `test_reporting_snapshot_rejects_user_level_fields`
- `test_readiness_payload_keeps_states_separate`
- `test_asset_public_url_metadata_is_safe_to_log`

Frontend deterministic evals:

- Readiness matrix renders six separate blockers.
- Approval queue shows exact version and media assets.
- Schedule button disabled until approval and publishing readiness pass.
- Client export matches approved version snapshot.
- Publishing queue displays retryable versus terminal failures.
- Calendar preserves timezone and avoids date drift.

Visual evals:

- Render generated graphic thumbnails in all supported aspect ratios.
- Prove text does not overflow approval cards, calendar cells, or export packets.
- Verify generated assets render nonblank and downloadable.

### Release Eval Gates

MVP cannot ship unless:

- Readiness separation tests pass.
- No secrets appear in generation, scheduler, or Meta error logs.
- Client-approved version invariants pass.
- Export packet fixture snapshots match approved versions.
- Facebook Page publish flow has credentialed staging evidence.
- Reporting aggregate-only tests pass.

Instagram beta cannot ship unless:

- Container create/poll/publish/expiry tests pass.
- Container creation happens only inside the near-publish window.
- Media URL fetch validation passes in staging.
- Rate-limit and terminal permission error states are visible in UI.
- App Review evidence exists for the active Instagram publishing permission family.

Production cannot ship unless:

- Raj signs off on cross-stream readiness.
- Mira signs off if shared architecture or reusable scheduler abstractions changed.
- Backend, frontend, scheduler/ops, and reporting owners sign their scorecards.
- `make adinsights-preflight PROMPT="Content Operations Meta publishing production readiness"`
  passes or accepted advisory exceptions are documented.

### Reviewer Scorecards

Raj, cross-stream integration:

- Confirms PRs are split by top-level folder or explicitly coordinated.
- Confirms contract docs, runbooks, and test evidence match implementation.
- Confirms Meta auth/Page/Instagram/publishing/reporting states remain separate.

Mira, architecture:

- Confirms no framework replacement or cross-cutting refactor without approved plan.
- Confirms scheduler abstractions are reusable but not over-generalized.
- Confirms data model avoids state duplication that will drift.

Sofia, backend API:

- Confirms DRF serializers handle omission versus explicit null correctly.
- Confirms tenant scoping and OpenAPI contracts.
- Confirms error shapes are safe and actionable.

Maya/Leo, integrations and scheduler:

- Confirms Meta calls use encrypted credentials and no token logging.
- Confirms Celery tasks set tenant context and correlation IDs.
- Confirms backoff, idempotency, skip-locked scheduling, and expiry handling.

Lina/Joel, frontend:

- Confirms UX separates readiness blockers.
- Confirms editor, approvals, calendar, and queue states are usable and accessible.
- Confirms exports are client-safe and match approved versions.

Omar/Hannah, observability/ops:

- Confirms structured logs and metrics cover queue latency, success/failure rate, rows processed or
  posts processed, upstream API cost units, and consecutive failures.
- Confirms runbooks cover revoked token, permission drift, expired container, rate limit, failed
  asset fetch, and reporting lag.

Priya/Martin, dbt/reporting:

- Confirms aggregate metric grain is stable before mart work.
- Confirms no user-level metrics are modeled.
- Confirms organic and paid Meta metrics are labeled distinctly.

## 10. Rollout Plan

### MVP

Feature flag: `CONTENT_OPS_META_MVP`

Scope:

- Content workspaces and briefs.
- AI caption generation.
- AI graphic batch generation with stored assets.
- Draft/version management.
- Internal and client approval.
- Calendar export and approval packet export.
- Manual publish-ready checklist.
- Facebook Page publishing only after `pages_manage_posts` App Review is approved.
- Facebook Page aggregate post reporting linkage.

Exit criteria:

- Backend and frontend tests pass for touched slices.
- Meta App Review evidence packet is complete for Page publishing.
- Readiness endpoint separates all required states.
- No user-level engagement storage.

### Beta

Feature flag: `CONTENT_OPS_META_INSTAGRAM_BETA`

Scope:

- App-owned scheduling.
- Instagram publishing using near-publish container creation.
- Publish queue UI and retry/cancel operations.
- Aggregate Instagram media insights when permissions are approved.
- Content performance report and scheduled PDF/CSV exports.
- Permission drift and publish failure runbooks.

Exit criteria:

- Scheduler concurrency tests pass.
- Instagram container expiry and retry behavior verified in staging.
- App Review approval captured for the current Instagram publishing permission family.
- Structured logs and metrics are visible in ops dashboards.

### Production

Feature flag default can move to enabled per eligible tenant after signoff.

Scope:

- Multi-client content calendar.
- Approval SLA reporting.
- Organic content dbt marts, if needed for BI.
- Rollback-safe release runbook.
- Tenant-level entitlement controls.
- Production support playbook and alert thresholds.

Exit criteria:

- Raj coordinates cross-stream signoff.
- Contract docs and runbooks are updated.
- `make adinsights-preflight PROMPT="Content Operations Meta publishing production readiness"` passes
  or any advisory findings are explicitly accepted.
- Credentialed staging evidence exists for Facebook and Instagram publishing flows.

## Implementation Slice Plan

1. Docs slice: this proposal, contract matrix/changelog notes, doc index, activity log.
2. Backend API/data slice: models, serializers, viewsets, OpenAPI, tenant isolation tests.
3. Backend AI slice: generation jobs, provider adapter, prompt redaction, asset persistence.
4. Backend scheduler slice: Celery beat tasks, publish attempts, Meta publisher service, structured
   logs.
5. Frontend slice: routes, editor, approval queue, calendar, readiness and publish queue UI.
6. Reporting slice: published-post metric snapshots, aggregate APIs, optional dbt marts.
7. Meta governance slice: permission catalog/profile, App Review copy, validation runbook.

Any slice that crosses more than one top-level folder needs Raj coordination. Cross-cutting
architecture changes need Mira review.

## Step-by-Step Wiring Plan

### Step 0: Governance and Proof

- Reconfirm Meta Graph API version, Page publishing endpoint behavior, Instagram publishing
  permission family, and App Review requirements.
- Create a Meta Test App evidence folder.
- Update permission catalog/profile and App Review runbooks before enabling runtime scopes.
- Define feature flags and tenant entitlements.
- Confirm asset storage/CDN/proxy strategy for Meta-fetchable media URLs.

Exit artifact: Raj-approved implementation ticket set with backend/frontend/scheduler/reporting/docs
slices.

### Step 1: Backend Data Foundation

- Add models and migrations for workspace, brief, generation job, media asset, draft/version,
  approval request/decision, schedule, publish attempt, published post, and metric snapshot.
- Add tenant-scoped managers/querysets and RLS-aware tests.
- Add audit event emission for draft creation, version changes, approvals, scheduling, cancellation,
  publish attempts, and retries.

Exit artifact: data model tests pass and no public endpoints are required yet.

### Step 2: Backend API Foundation

- Add DRF serializers and viewsets for workspaces, briefs, drafts, versions, assets, approvals,
  schedules, exports, readiness, and publish queue.
- Add OpenAPI path tests.
- Use additive response contracts only.
- Add role permissions for strategist, internal approver, client approver, operator, and viewer.

Exit artifact: API contract can power frontend mocks and fixture screens.

### Step 3: AI Generation

- Add provider adapter for captions using structured outputs.
- Add provider adapter for image generation or image generation tool usage.
- Add prompt redaction, schema validation, moderation/quality gates, cost estimates, job cancellation,
  and asset persistence.
- Add eval fixtures and model eval scripts/configuration.

Exit artifact: users can create AI draft versions and graphics, but nothing can publish without
approval.

### Step 4: Frontend Production Workspace

- Add content calendar, brief form, draft editor, platform variants, asset library, generation job
  status, approval queue, client review view, export actions, readiness panel, and publish queue.
- Use mocked API states until backend slice is ready.
- Ensure controls are disabled based on exact readiness blockers rather than generic connection
  state.

Exit artifact: frontend can run end-to-end against mocks and then real backend contracts.

### Step 5: Approval and Export

- Enforce version-bound approval snapshots.
- Add approval notifications through existing notification patterns or a content-ops-specific
  notification slice.
- Add calendar CSV/PDF, approval packet PDF, and platform-ready media ZIP exports.
- Verify exported content matches approved versions.

Exit artifact: the module is useful for client planning before live publishing is enabled.

### Step 6: Facebook Page Publishing MVP

- Add publishing identity preflight for selected Pages.
- Add Page publishing service with encrypted token lookup, safe error mapping, idempotency key, and
  published post persistence.
- Add scheduler scan/lock/dispatch for Facebook Page only.
- Add failed-publish operator UI and retry path.

Exit artifact: staging proof for one Facebook Page single-image/text/link post flow.

### Step 7: Aggregate Facebook Reporting

- Link published Page post IDs to existing Page/Post Insights where available.
- Add aggregate metric snapshots and content-ops reporting endpoints.
- Keep organic reports separate from paid Meta reports.

Exit artifact: published posts show aggregate performance and link back to drafts.

### Step 8: Instagram Publishing Beta

- Add Instagram publishing identity readiness and media validation.
- Add container creation near publish time, status polling, expiry recreation, and `media_publish`.
- Add beta support for single-image feed posts first.
- Add reels/carousels only after separate media validation and App Review proof.

Exit artifact: staging proof for Instagram professional account single-image post flow.

### Step 9: Production Hardening

- Add quota controls for AI generation and Meta publish attempts.
- Add SLOs, alert thresholds, dashboards, and support runbooks.
- Add optional dbt marts for organic content reporting after the API snapshot contract stabilizes.
- Run full release readiness preflight and signoff.

Exit artifact: tenant-by-tenant rollout with rollback plan.

## Risk Register

| Risk | Impact | Mitigation |
| ---- | ------ | ---------- |
| Meta App Review rejects publishing permissions | Publishing cannot go live | Build planning/export/approval first; keep publishing behind flags; create reviewer evidence early |
| Meta permission names or app type requirements change | OAuth implementation may drift | Reverify before code and before submission; document exact permission family in catalog/profile |
| Instagram containers expire before publish | Scheduled posts fail late | Create containers only near due time; recreate expired containers; track expiry state |
| Meta cannot fetch media URL | Publish fails after approval | Validate public HTTPS URL, content type, content length, and no-auth fetch before container creation |
| Duplicate publish attempts | Client-facing duplicate posts | Use DB locks, idempotency keys, per-channel attempts, and duplicate post detection |
| AI produces off-brand or unsafe content | Client trust and compliance risk | Human approval required; brand constraints; blocked-term checks; eval gates |
| Generated graphics have unreadable text | Client-facing quality issue | Visual QA, aspect-ratio checks, and human approval |
| Approval version drift | Wrong content publishes | Approval snapshot bound to exact version and media asset IDs; edits invalidate approval |
| Reporting stores user-level data by accident | PII/privacy violation | Aggregate-only serializers, tests that reject user-level fields, dbt review before marts |
| Paid and organic metrics blur | Misleading reports | Separate channels and labels; combined summaries only with explicit organic/paid split |
| Token revocation or permission drift | Scheduled posts fail | Readiness checks before scheduling and again before publishing; operator alerts |
| Batch AI cost spike | Tenant cost surprise | Quotas, estimates, admin limits, and cancellation |
| Cross-stream PR grows too large | Review/release risk | Raj-managed slice plan and per-folder tests |

## Source Notes Checked

- Meta developer docs direct URL for Instagram content publishing:
  `https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/content-publishing/`
- Meta developer docs direct URL for IG User media:
  `https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media/`
- Meta developer docs direct URL for Page feed/posts:
  `https://developers.facebook.com/docs/graph-api/reference/page/feed/`
- Indexed mirror of Meta IG User media docs, crawled with v24.0 examples, states that Instagram
  containers expire after 24 hours and that accounts can create 400 containers in a rolling 24-hour
  period:
  `https://archive.ph/2025.12.31-074218/https%3A/developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media`
- Public Meta Postman Instagram collection notes that Instagram API with Facebook Login cannot
  access consumer accounts, content publishing is for Instagram professional accounts, and Reels
  publishing uses container status polling before `media_publish`:
  `https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api`
- OpenAI image generation guide documents Image API and Responses API image-generation options,
  including multi-step image workflows and output customization:
  `https://developers.openai.com/api/docs/guides/image-generation`
- OpenAI structured outputs guide documents schema-constrained model output for predictable JSON:
  `https://developers.openai.com/api/docs/guides/structured-outputs`
- OpenAI Evals API reference documents creating and running evals:
  `https://developers.openai.com/api/reference/resources/evals`
- Current ADinsights source-of-truth docs:
  - `docs/project/meta-permission-profile.md`
  - `docs/runbooks/meta-app-review-validation.md`
  - `docs/project/integration-data-contract-matrix.md`
  - `docs/project/api-contract-changelog.md`
