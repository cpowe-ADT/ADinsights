# Content Operations API Contract

Status: partially implemented contract
Related:

- `docs/project/content-operations-meta-publishing-spec.md`
- `docs/project/content-operations-implementation-backlog.md`
- `backend/content_ops/models.py`
- `backend/content_ops/serializers.py`
- `backend/content_ops/views.py`

Timezone baseline: `America/Jamaica`
Last updated: 2026-06-10

## Purpose

Define the additive DRF contract for `/api/content-ops/*`.

The backend API skeleton is partially live as of 2026-06-06. Safe scheduler and retry dispatchers
can create durable publish-attempt queue records, caption-generation jobs can create editable
generated draft versions through an injected provider boundary, and Celery beat now runs the due
schedule, retryable-attempt, queued-attempt processor, and organic metric refresh scans on the sync
queue. Live Meta Graph publishing and live AI provider calls remain planned. Frontend export
history is implemented through the persisted export-artifact surfaces; richer PDF/CSV/ZIP packets
remain future work.

## Runtime Implementation Status

Implemented:

- Authenticated tenant-scoped DRF routes under `/api/content-ops/`.
- Role-gated mutation/workflow actions using the existing ADinsights role catalog.
- Readiness composition at `GET /api/content-ops/readiness/` with separate Meta auth, Page
  selection, Instagram linkage, Facebook publishing, Instagram publishing, and reporting axes.
- CRUD/list surfaces for workspaces, publishing identities, briefs, generation jobs, assets, and
  drafts.
- Read-only list/detail surfaces for draft versions, approval requests, approval decisions,
  schedules, publish attempts, published posts, and aggregate organic metric snapshots.
- Draft `state` is read-only through the public serializer; workflow actions own state changes.
- Draft workflow actions:
  - `POST /api/content-ops/drafts/{draft_id}/versions/`
  - `POST /api/content-ops/drafts/{draft_id}/submit-internal-review/`
  - `POST /api/content-ops/drafts/{draft_id}/submit-client-review/`
  - `POST /api/content-ops/drafts/{draft_id}/schedule/`
  - `POST /api/content-ops/drafts/{draft_id}/unschedule/`
  - `POST /api/content-ops/drafts/{draft_id}/publish-now/` returns `501 not_implemented`.
- Approval decision action:
  - `POST /api/content-ops/approval-requests/{approval_id}/decisions/`
  - rejects decisions unless the approval request is still `pending`, the request version is still
    the draft active version, and the draft remains in the expected internal/client review state
- Generation job cancellation action:
  - `POST /api/content-ops/generation-jobs/{job_id}/cancel/`
- Public serializer hardening:
  - `PublishingIdentity.credential_ref` is write-only and is not returned in API responses
  - publishing readiness fields are server-owned/read-only on public identity writes
  - `GenerationJob.input_fingerprint`, `prompt_policy_result`, `result_summary`, and `error_code`
    are server-owned/read-only through the public generation-job serializer
  - `MediaAsset.storage_key` is write-only, `MediaAsset.ai_lineage` is omitted from public asset
    responses, and asset storage/runtime metadata such as `source`, `storage_key`, `mime_type`,
    dimensions, `renditions`, and `status` are server-owned through public writes
- Asset upload/download boundary:
  - `POST /api/content-ops/assets/upload/` accepts tenant-scoped image/video uploads for a
    workspace and generates the storage key server-side
  - `GET /api/content-ops/assets/{asset_id}/download/` serves available assets through an
    authenticated, tenant-scoped endpoint
  - `GET /api/content-ops/assets/{asset_id}/public-media-proof/` returns authenticated, redacted
    proof that an approved asset has an HTTPS Meta-fetch URL, safe content type, and content length
  - `GET /api/content-ops/public-media/{asset_id}/` is an unauthenticated opaque UUID fetch path for
    Meta/CDN use and serves only assets attached to the active version of a client-approved or later
    draft
  - direct public `POST /api/content-ops/assets/` returns `405 asset_upload_required`
  - asset path resolution rejects invalid prefixes and traversal segments before file access
- AI caption generation foundation:
  - `POST /api/content-ops/briefs/{brief_id}/captions/generate/`
  - creates a queued tenant-scoped `GenerationJob` with default `candidate_count=3` and max `5`
  - supports `facebook_page` and `instagram` caption platforms
  - defaults platforms from `workspace.target_channels`; falls back to `facebook_page`
  - stores only redacted prompt summary/policy metadata
  - default provider boundary fails closed with `provider_not_configured`
  - `content_ops.generation.process_content_caption_generation_job(...)` accepts injected fake or
    future provider boundaries
  - `content_ops.tasks.process_content_caption_generation_job` processes one job only, resolves
    tenant context from the stored `GenerationJob`, and has no activated beat schedule
  - valid injected provider output creates editable `generated` drafts and active version records
    linked by `source_generation_job`
  - generated output does not create approvals, schedules, publish attempts, published posts, or
    metrics
  - blocked terms, required terms, schema validation, and secret-like output checks fail safely with
    stable error codes
- Aggregate reporting and export surfaces:
  - `GET /api/content-ops/reports/overview/`
  - `GET /api/content-ops/reports/posts/`
  - `POST /api/content-ops/exports/content-plan/`
- Safe app-owned schedule dispatcher:
  - `content_ops.scheduler.dispatch_due_schedules(...)`
  - `content_ops.tasks.dispatch_due_content_schedules`
  - scans due, approved schedules for one tenant or all tenants
  - skips locked schedule rows so parallel workers do not wait on the same schedule
  - creates one idempotent `PublishAttempt` per target channel
  - dispatches from `approval_snapshot.target_channels` so workspace channel edits after
    scheduling do not change the destinations queued for that schedule
  - narrows selected publishing identity lookup by snapshotted `page_id` or `ig_user_id` when the
    schedule target provides one
  - validates the scheduled version is still active and the approval snapshot includes a client
    approval
  - blocks attempts with client-safe readiness failure codes when identity or permission readiness
    is incomplete
  - requires selected publishing identities to be explicitly `ready`; `unknown` readiness blocks
    publishing axes until identity validation runs
  - does not call Meta, create Instagram containers, publish posts, or fetch metrics
- Facebook Page publish preflight:
  - `content_ops.publisher.preflight_facebook_page_attempt(...)`
  - validates tenant ownership, supported channel, attempt state, active scheduled version, client
    approval snapshot, selected publishing identity, Facebook Page publishing readiness, and caption
    presence
  - returns stable client-safe failure codes and details
  - does not decrypt tokens, call Meta, create posts, mutate attempts, or fetch metrics
- Facebook Page attempt processor with fakeable provider boundary:
  - `content_ops.publisher.process_facebook_page_publish_attempt(...)`
  - `content_ops.facebook_graph.FacebookGraphPagePublisher`
  - `content_ops.tasks.process_content_publish_attempt`
  - skips locked publish-attempt rows so parallel workers do not process the same attempt
  - accepts an injected publisher boundary for deterministic tests
  - default publisher fails closed with `provider_not_configured` unless
    `CONTENT_OPS_LIVE_FACEBOOK_PUBLISHING=true`
  - when the live flag is enabled, resolves a tenant-local `MetaPage` by selected `meta_page_id`,
    decrypts the stored Page token inside the adapter, and posts to the configured Graph API Page
    feed endpoint
  - successful injected or live publish creates `PublishedPost`, marks the attempt `published`,
    stores the returned post ID, and updates schedule/draft state
  - retryable provider errors mark attempts `failed_retryable` with jittered exponential
    `next_retry_at`
  - retryable provider errors become terminal after five failed publish attempts
  - terminal provider errors mark attempts `failed_terminal`
  - provider failure details are sanitized before persistence
  - does not call Meta by default, expose tokens, create Instagram containers, schedule itself
    through beat, or fetch metrics
- Publish-attempt retry action:
  - `POST /api/content-ops/publishing/attempts/{attempt_id}/retry/`
  - requeues only `failed_retryable` attempts
  - clears safe failure fields and retry timestamps
  - does not immediately call the processor or Meta
- Retryable-attempt scanner:
  - `content_ops.publisher.requeue_due_retryable_attempts(...)`
  - `content_ops.tasks.requeue_due_content_publish_attempts`
  - requeues tenant-scoped `failed_retryable` attempts whose `next_retry_at` has arrived
  - runs every minute through the `content-publish-retry-scan` Celery beat entry
  - does not call the processor, decrypt tokens, call Meta, or create provider side effects
- Active Celery beat scans:
  - `content-publish-due-scan` runs `content_ops.tasks.dispatch_due_content_schedules` every
    minute on the sync queue
  - `content-publish-retry-scan` runs `content_ops.tasks.requeue_due_content_publish_attempts`
    every minute on the sync queue
  - `content-publish-process-scan` runs `content_ops.tasks.process_due_content_publish_attempts`
    every minute on the sync queue
  - due/retry scans create or requeue durable queue records; the processor scan advances queued
    attempts plus due Instagram `container_pending`/`container_ready` attempts through
    disabled-by-default/fakeable provider boundaries and does not call Meta unless a live provider
    adapter is explicitly configured later
- Content Ops Celery tasks use a maximum of five retries.
- Organic metric refresh:
  - `POST /api/content-ops/published-posts/{post_id}/refresh-metrics/` refreshes one published
    post from already-synced Meta post insight rows into aggregate-only
    `OrganicPostMetricSnapshot` records.
  - `content-organic-metrics-refresh` runs
    `content_ops.tasks.refresh_content_published_post_metrics` hourly from 06:35-22:35 Jamaica
    time on the sync queue.

Not implemented:

- live AI caption or graphic generation provider calls
- external object-store signed URL generation
- client external approval links
- Instagram Graph publishing calls
- dbt organic marts
- richer export packet formats beyond the persisted JSON content-plan artifact
- frontend live-publishing confirmation polish for live adapter readiness and provider-backed
  staging proof

## Runtime Role Gates

Read operations require authenticated tenant context. Mutating operations are additionally role
gated:

- Content editing: agency/admin/analyst-style roles can create and edit planning records.
- Draft versions, approval requests, and schedules must be created through draft workflow actions,
  not by direct collection writes.
- Internal approval decisions: agency/admin/internal reviewer roles only.
- Client approval decisions: client lead/senior lead/admin roles only.
- Schedule, unschedule, publish-now, publish retry, and metric refresh actions: publish-capable
  roles only.
- Publishing identity mutation: publish-capable or admin roles only.

These role gates are module-local and do not change the global role catalog.

## Contract Rules

- All endpoints require authenticated tenant context.
- All list endpoints are paginated with the repo default pagination contract.
- All records are tenant-scoped.
- Omitted optional fields mean "leave unchanged" on PATCH.
- Explicit `null` is accepted only where the serializer declares `allow_null=True`.
- Response errors must use client-safe reason codes and must not include raw Meta, AI provider, or
  signed URL secrets.
- Publishing readiness remains separate from Meta auth, Page selection, Instagram linkage, and
  reporting readiness.

## Versioning

Initial path namespace:

- `/api/content-ops/`

Do not add a versioned path until the first production-breaking change is unavoidable. Additive
fields are preferred.

## Shared Enums

Channels:

- `facebook_page`
- `instagram`

Approval statuses:

- `not_requested`
- `pending`
- `approved`
- `changes_requested`
- `rejected`
- `expired`
- `superseded`

Draft states:

- `draft`
- `generated`
- `internal_review`
- `internal_changes_requested`
- `internal_approved`
- `client_review`
- `client_changes_requested`
- `client_approved`
- `scheduled`
- `publishing`
- `published`
- `partially_published`
- `failed`
- `cancelled`
- `archived`

Publish attempt states:

- `queued`
- `preflight`
- `blocked`
- `container_creating`
- `container_pending`
- `container_ready`
- `publishing`
- `published`
- `failed_retryable`
- `failed_terminal`
- `container_expired`
- `cancelled`

## Endpoints

### Readiness

`GET /api/content-ops/readiness/`

Purpose: compose existing Meta/reporting state with publishing-specific readiness.

Response:

```json
{
  "generated_at": "2026-06-05T10:00:00-05:00",
  "meta_auth": {
    "state": "connected",
    "reason": null,
    "credential_count": 1,
    "usable_credential_count": 1,
    "active_page_connection_count": 1
  },
  "page_selection": {
    "state": "complete",
    "reason": null,
    "page_count": 1,
    "selected_page_count": 1,
    "default_page_id": "page_123"
  },
  "instagram_linkage": {
    "state": "blocked",
    "reason": "instagram_not_linked",
    "linked_count": 0
  },
  "facebook_page_publishing": {
    "state": "blocked",
    "reason": "missing_publishing_permissions",
    "identity_count": 1,
    "missing_permissions": ["pages_manage_posts"],
    "required_permissions": ["pages_manage_posts"],
    "upstream_blockers": [],
    "identity_blockers": []
  },
  "instagram_publishing": {
    "state": "blocked",
    "reason": "missing_publishing_permissions",
    "identity_count": 1,
    "missing_permissions": ["instagram_content_publish"],
    "required_permissions": ["instagram_basic", "instagram_content_publish"],
    "upstream_blockers": [],
    "identity_blockers": []
  },
  "reporting_readiness": {
    "state": "ready",
    "reason": null,
    "dataset_live_reason": "ready",
    "dataset_status": {}
  }
}
```

Acceptance:

- Tests cover every axis independently.
- UI can display six separate blockers.
- No existing `/api/integrations/social/status/` or `/api/datasets/status/` payload semantics change.

### Workspaces

- `GET /api/content-ops/workspaces/`
- `POST /api/content-ops/workspaces/`
- `GET /api/content-ops/workspaces/{workspace_id}/`
- `PATCH /api/content-ops/workspaces/{workspace_id}/`
- `DELETE /api/content-ops/workspaces/{workspace_id}/`

Create request:

```json
{
  "name": "June SLB content",
  "client_id": "uuid",
  "objective": "Drive awareness and quote requests.",
  "target_channels": ["facebook_page", "instagram"],
  "timezone": "America/Jamaica",
  "brand_profile": {
    "voice": "clear, premium, practical",
    "required_terms": ["Terms apply"],
    "blocked_terms": ["guaranteed"]
  }
}
```

Response fields:

- `id`, `name`, `client_id`, `objective`, `target_channels`, `timezone`, `brand_profile`,
  `archived_at`, `created_by`, `created_at`, `updated_at`

### Briefs

- `GET /api/content-ops/briefs/?workspace_id=`
- `POST /api/content-ops/workspaces/{workspace_id}/briefs/`
- `GET /api/content-ops/briefs/{brief_id}/`
- `PATCH /api/content-ops/briefs/{brief_id}/`

Briefs drive AI generation and calendar organization. They do not publish directly.

### Generation Jobs

- `POST /api/content-ops/briefs/{brief_id}/captions/generate/`
- `POST /api/content-ops/briefs/{brief_id}/graphics/generate-batch/`
- `GET /api/content-ops/generation-jobs/{job_id}/`
- `POST /api/content-ops/generation-jobs/{job_id}/cancel/`

Caption generate request:

```json
{
  "candidate_count": 3,
  "platforms": ["facebook_page", "instagram"],
  "tone_override": "clear, premium, practical"
}
```

Caption generate response:

```json
{
  "id": "uuid",
  "workspace": "uuid",
  "brief": "uuid",
  "job_type": "caption",
  "status": "queued",
  "provider": "disabled",
  "model_name": "",
  "redacted_prompt_summary": "Caption generation for workspace=...",
  "prompt_policy_result": {
    "candidate_count": 3,
    "platforms": ["facebook_page", "instagram"],
    "provider_configured": false,
    "redacted": false,
    "required_term_count": 1,
    "blocked_term_count": 1,
    "tone_override": "clear, premium, practical",
    "tone_override_present": true
  },
  "result_summary": {},
  "error_code": "",
  "created_at": "2026-06-05T09:00:00-05:00"
}
```

Direct `POST/PATCH /api/content-ops/generation-jobs/` calls are allowed only for planning/job
metadata fields. Runtime fields are server-owned: client-supplied `input_fingerprint`,
`prompt_policy_result`, `result_summary`, `error_code`, or `status` values are ignored by public
serializer writes.

Caption provider candidate schema accepted by the processor:

```json
{
  "platform": "facebook_page",
  "caption": "string",
  "hashtags": ["string"],
  "cta": "string",
  "alt_text": "string",
  "risk_flags": ["string"],
  "quality_score": 0.0
}
```

Stable caption failure codes:

- `provider_not_configured`
- `caption_schema_invalid`
- `caption_policy_blocked`
- `required_terms_missing`
- `caption_active_limit_exceeded`
- `caption_daily_limit_exceeded`
- `caption_candidate_limit_exceeded`
- `generation_job_cancelled`
- `generation_job_wrong_type`
- `brief_missing`

Quota block response:

```json
{
  "detail": "Caption generation active job limit has been reached.",
  "reason": "caption_active_limit_exceeded",
  "quota": {
    "active_job_count": 25,
    "rolling_24h_job_count": 42,
    "rolling_24h_candidate_count": 126,
    "limits": {
      "active_job_limit": 25,
      "daily_job_limit": 100,
      "daily_candidate_limit": 300
    }
  }
}
```

Quota defaults are intentionally conservative and can be overridden by settings:

- `CONTENT_OPS_CAPTION_ACTIVE_JOB_LIMIT`
- `CONTENT_OPS_CAPTION_DAILY_JOB_LIMIT`
- `CONTENT_OPS_CAPTION_DAILY_CANDIDATE_LIMIT`

Acceptance:

- Raw prompt text and secret-like values are not returned.
- Runtime result and policy fields are not client-mutable through direct generation-job writes.
- Provider errors are mapped to safe `error_code` values.
- Generated captions create draft versions only after validation.
- Generated captions do not approve, schedule, publish, or create reporting rows.
- Graphic generation remains planned and is not implemented by this endpoint.

### Drafts and Versions

- `GET /api/content-ops/drafts/?workspace_id=&state=&channel=`
- `POST /api/content-ops/drafts/`
- `GET /api/content-ops/drafts/{draft_id}/`
- `PATCH /api/content-ops/drafts/{draft_id}/`
- `POST /api/content-ops/drafts/{draft_id}/versions/`
- `GET /api/content-ops/drafts/{draft_id}/versions/`

Draft response includes `active_version`, `approval_summary`, and `schedule_summary`.

Acceptance:

- Edits after approval supersede affected approval requests.
- Active version changes are audit logged.
- Versions are never silently overwritten.

### Assets

- `GET /api/content-ops/assets/?workspace_id=&status=&source=`
- `POST /api/content-ops/assets/` returns `405 asset_upload_required`
- `POST /api/content-ops/assets/upload/`
- `GET /api/content-ops/assets/{asset_id}/`
- `PATCH /api/content-ops/assets/{asset_id}/`
- `DELETE /api/content-ops/assets/{asset_id}/`
- `GET /api/content-ops/assets/{asset_id}/download/`
- `GET /api/content-ops/assets/{asset_id}/public-media-proof/`
- `GET /api/content-ops/public-media/{asset_id}/`

Upload request is multipart form data:

- `workspace`: workspace UUID
- `file`: image/video file
- `alt_text`: optional client-safe alt text

Upload response includes safe metadata plus `download_url`; it does not include `storage_key` or
`ai_lineage`.

Acceptance:

- API returns asset metadata and safe preview/download URLs only.
- `storage_key` is generated server-side and is never returned by the public asset serializer.
- `ai_lineage` is not exposed by the public asset serializer.
- Asset `status` is server-owned through public writes.
- Signed publish URLs are not exposed through normal asset read endpoints.
- Public Meta fetch URLs use `CONTENT_OPS_PUBLIC_MEDIA_BASE_URL` plus an opaque asset UUID and do
  not include the tenant storage path.
- The public media endpoint serves only assets attached to the active version of a client-approved,
  scheduled, publishing, published, or partially published draft.
- Public media proof responses include scheme, host, redacted URL, content type, byte length,
  approval state, and safe failure code; they do not include `storage_key`, filesystem paths, signed
  query strings, or raw CDN secrets.
- Quarantined assets cannot be attached to publishable versions.

### Approvals

- `POST /api/content-ops/drafts/{draft_id}/submit-internal-review/`
- `POST /api/content-ops/drafts/{draft_id}/submit-client-review/`
- `GET /api/content-ops/approval-requests/?workspace_id=&status=&reviewer_type=`
- `POST /api/content-ops/approval-requests/{approval_id}/decisions/`

Acceptance:

- Client approval binds exact `version_id` and media asset IDs.
- New edits supersede pending/approved requests.
- Decisions are accepted only for pending approval requests whose version is still the draft active
  version and whose draft remains in the expected internal/client review state.
- Client reviewers can access only assigned tenant/client approvals.

### Scheduling and Publishing Queue

- `POST /api/content-ops/drafts/{draft_id}/schedule/`
- `POST /api/content-ops/drafts/{draft_id}/unschedule/`
- `POST /api/content-ops/drafts/{draft_id}/publish-now/`
- `GET /api/content-ops/publishing/attempts/?state=&channel=&scheduled_from=&scheduled_to=&retry_due=`
- `GET /api/content-ops/publishing/attempts/{attempt_id}/`
- `POST /api/content-ops/publishing/attempts/{attempt_id}/retry/`

Acceptance:

- Schedule is rejected unless active version is client-approved.
- Schedule stores an approval snapshot with frozen `target_channels`. If `channels` is omitted from
  the schedule request, the current workspace `target_channels` are normalized and snapshotted.
- Dispatch uses the frozen schedule targets, not mutable workspace defaults. Existing schedules
  without `approval_snapshot.target_channels` fall back to workspace channels for compatibility.
- Schedule targets may be strings such as `"facebook_page"` or objects such as
  `{"type": "facebook_page", "page_id": "123"}` and
  `{"type": "instagram", "ig_user_id": "1784..."}`.
- Retry is rejected for terminal failure codes that require reauth/App Review/user action.
- Retryable provider failures use exponential backoff with bounded jitter and stop after five
  failed attempts.

### Reports and Exports

- `GET /api/content-ops/reports/overview/?workspace_id=&start_date=&end_date=`
- `GET /api/content-ops/reports/posts/?workspace_id=&start_date=&end_date=&channel=`
- `POST /api/content-ops/exports/content-plan/`
- `POST /api/content-ops/published-posts/{post_id}/refresh-metrics/`
- `POST /api/content-ops/exports/`
- `GET /api/content-ops/exports/{export_id}/`
- `GET /api/content-ops/exports/{export_id}/download/`

Acceptance:

- Reports expose aggregate metrics only.
- Organic and paid Meta metrics are labeled separately.
- Published-post metric refresh stores aggregate-only snapshots and updates
  `reporting_link_state` to `linked` or `unavailable`; it does not expose user-level reaction,
  commenter, viewer, or profile identifiers.
- Content plan exports omit private storage keys, provider prompts, and AI lineage.
- `POST /api/content-ops/exports/` persists a JSON content-plan artifact for repeat
  downloads. Supported request fields are `workspace_id`, optional `states`, `export_type`
  (`content_plan`), and `export_format`/`format` (`json`).
- Persisted export responses expose server-safe metadata, `item_count`, `metadata`, timestamps,
  and `download_url`; they do not expose the server `artifact_path`.
- `GET /api/content-ops/exports/{export_id}/download/` serves the saved JSON packet only after
  validating that the stored path remains under the configured export artifact root.

## Test Requirements

Backend ticket `CO-1B` has added:

- serializer tests for optional/null handling
- OpenAPI path/action/enum tests for Content Ops routes and state-bearing components
- tenant isolation tests for every list/retrieve endpoint
- readiness separation tests
- safe error-shape tests

Remaining schema follow-up:

- add custom response serializers for readiness/reporting/export payloads so OpenAPI no longer
  falls back to generic object or array shapes for those non-model actions
- add deeper write-contract assertions for schedule target objects, asset upload multipart payloads,
  and caption generation quota errors

Frontend can consume real endpoints only where the OpenAPI tests and focused API tests cover the
specific path/action/enum contract being integrated.
