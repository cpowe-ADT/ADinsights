# Content Operations Publishing Runbook

Status: partially implemented operations runbook
Timezone baseline: `America/Jamaica`

## Purpose

Operate ADinsights-owned scheduled publishing for organic Facebook Page and Instagram professional
account content.

Live Graph publishing is implemented behind explicit disabled-by-default flags. The backend includes
safe dispatch and processor tasks that can create durable publish-attempt queue records without
calling Meta, and live Facebook/Instagram adapters only run when their rollout flags are enabled in
a gated environment.

## Readiness Checks

Before enabling publishing for a tenant:

1. Confirm `GET /api/content-ops/readiness/` reports separate axes.
2. Confirm Meta auth is connected.
3. Confirm Page selection is complete.
4. Confirm Facebook Page publishing permission is approved.
5. Confirm Instagram linkage and publish permission only for Instagram beta tenants.
6. Confirm asset URL strategy is deployed and tested.
7. Confirm approval workflow is enabled.

## Public Media URL / CDN Boundary

Goal N adds the public media proof boundary required before Instagram live publishing:

- `CONTENT_OPS_PUBLIC_MEDIA_BASE_URL` must be an HTTPS origin/path that resolves to
  `/api/content-ops/public-media/<asset_id>/` through the deployed app, CDN, or equivalent edge
  route.
- The generated Meta fetch URL uses only the opaque media asset UUID. It must not include tenant
  IDs, workspace IDs, `storage_key`, local filesystem paths, raw signed URL query parameters, or
  credential material.
- `GET /api/content-ops/public-media/<asset_id>/` is intentionally unauthenticated for Meta fetches,
  but it serves only available assets attached to the active version of a client-approved or later
  draft.
- `GET /api/content-ops/assets/<asset_id>/public-media-proof/` is authenticated and returns redacted
  proof: readiness, safe failure code, scheme, host, redacted URL, approval state, MIME type, content
  length, and `storage_key_exposed=false`.
- Do not use authenticated `download_url` values for Instagram container creation. Meta cannot fetch
  tenant-authenticated media URLs.
- Public media proof is not App Review approval or staging proof by itself. It is the prerequisite
  for Goal P and Goal S.

Operator checks before Instagram adapter work:

1. Set `CONTENT_OPS_PUBLIC_MEDIA_BASE_URL` to the deployed HTTPS route.
2. Upload or generate an approved image/video asset.
3. Confirm the active draft version has internal and client approval.
4. Call `GET /api/content-ops/assets/<asset_id>/public-media-proof/`.
5. Confirm `ready=true`, `public_url_is_https=true`, content type is `image/*` or `video/*`, and
   content length is greater than zero.
6. Fetch the corresponding public URL from a clean session without ADinsights auth cookies.
7. Confirm the response has the expected `Content-Type`, `Content-Length`, and no storage-key or
   tenant-private path in headers.

## Queue Dispatch Boundary

Implemented task:

- `content_ops.tasks.dispatch_due_content_schedules`

Current behavior:

- scans one tenant when `tenant_id` is provided, otherwise all tenants
- selects due `scheduled` schedules whose drafts are still `scheduled`
- validates the scheduled version is still the active draft version
- validates the approval snapshot still includes a client approval for that version
- creates one idempotent `PublishAttempt` per workspace target channel
- marks attempts `queued` only when the matching readiness axis is ready
- marks attempts `blocked` with client-safe failure codes when publishing identity or readiness is
  incomplete

Current non-behavior:

- no Facebook Page Graph publish call is made
- no Instagram media container is created unless the processor is running with
  `CONTENT_OPS_META_INSTAGRAM_BETA=true`
- schedule dispatch itself does not refresh metrics; the separate
  `content-organic-metrics-refresh` worker handles aggregate metric snapshots

## Facebook Page Preflight Boundary

Implemented services:

- `content_ops.publisher.preflight_facebook_page_attempt`
- `content_ops.publisher.process_facebook_page_publish_attempt`
- `content_ops.tasks.process_content_publish_attempt`
- `content_ops.publisher.requeue_due_retryable_attempts`
- `content_ops.tasks.requeue_due_content_publish_attempts`
- `POST /api/content-ops/publishing/attempts/{attempt_id}/retry/`

Current behavior:

- validates the publish attempt belongs to the tenant being processed
- accepts only Facebook Page attempts in publishable states
- validates schedule, draft, version, active version, and client approval snapshot alignment
- validates the attached publishing identity is tenant-local, selected, and not blocked
- validates the Facebook Page publishing readiness axis is ready
- validates the approved version has caption text for MVP Page publishing
- returns stable client-safe failure codes/details
- accepts an injected publisher boundary for deterministic processing
- fails closed with `provider_not_configured` when `CONTENT_OPS_LIVE_FACEBOOK_PUBLISHING` is false
- when `CONTENT_OPS_LIVE_FACEBOOK_PUBLISHING` is true, resolves a tenant-local `MetaPage` by the
  selected `meta_page_id`, decrypts the Page token inside the adapter, and posts approved caption
  text to the configured Graph API Page feed endpoint
- creates `PublishedPost` and marks attempts `published` only when an injected or live publisher
  returns a post ID
- marks retryable provider errors `failed_retryable` with deterministic retry time
- marks terminal provider errors `failed_terminal`
- updates schedule/draft state after attempt outcomes
- requeues only `failed_retryable` attempts through the retry API
- clears retry timestamps and safe failure fields during requeue
- requeues tenant-scoped failed retryable attempts when `next_retry_at` is due through the scanner
- filters publish attempts by `state`, `channel`, schedule window, and `retry_due`

Current non-behavior:

- no token decryption or live Facebook Page Graph call while `CONTENT_OPS_LIVE_FACEBOOK_PUBLISHING`
  is false
- no live provider adapter is enabled by default
- no metric refresh is performed by retry requeue; the separate organic metrics worker owns it

## Scheduled Jobs

Implemented jobs:

- `content-publish-due-scan`: every minute on the `sync` queue; runs
  `content_ops.tasks.dispatch_due_content_schedules`.
- `content-publish-retry-scan`: every minute on the `sync` queue; runs
  `content_ops.tasks.requeue_due_content_publish_attempts`.
- `content-publish-process-scan`: every minute on the `sync` queue; runs
  `content_ops.tasks.process_due_content_publish_attempts` through disabled-by-default/fakeable
  provider boundaries. It scans due queued attempts and due Instagram attempts already waiting in
  `container_pending` or `container_ready` so container polling and media-publish completion do not
  stall between worker ticks.
- `content-organic-metrics-refresh`: hourly at minute 35 from `06:00-22:00 America/Jamaica`;
  runs `content_ops.tasks.refresh_content_published_post_metrics` over already-synced aggregate
  Meta post insight rows.

Planned/remaining jobs:

- `content-readiness-refresh`: hourly `06:00-22:00 America/Jamaica`.

## Facebook Page Publish Flow

1. Scheduler locks due schedule.
2. Preflight checks approval snapshot, Page identity, token status, and publish permission.
3. If `CONTENT_OPS_LIVE_FACEBOOK_PUBLISHING=true`, publisher calls current Graph API Page feed
   endpoint with the tenant-local encrypted Page token.
4. Publisher stores returned post ID in `PublishedPost`.
5. Metrics refresh links aggregate Page/Post Insights later.

Operator success signal:

- publish attempt state `published`
- `PublishedPost.meta_post_id` populated
- no secret-bearing details in logs

## Facebook Staging Proof Checklist

Goal R requires a credentialed staging publish before Facebook Page publishing can be considered
release-ready. Do not treat adapter tests, fake publisher success, or a configured Meta app as a
substitute for this proof.

Required preconditions:

1. Meta test/staging app has the `pages_manage_posts` path approved or otherwise available for the
   controlled test user and Page.
2. Runtime OAuth scopes include `pages_manage_posts` only in the gated staging environment: set
   `META_ENABLE_PUBLISH_SCOPES=true` and have the test user reconnect Meta so the granted token
   carries the scope.
3. `CONTENT_OPS_LIVE_FACEBOOK_PUBLISHING=true` is enabled only for the staging validation window.
4. The selected staging tenant has a tenant-local selected `MetaPage` with a decryptable Page token
   and valid Page task access.
5. The exact draft version has internal approval, client approval, and immutable approval snapshot
   evidence.
6. Operators have a rollback step ready to set `CONTENT_OPS_LIVE_FACEBOOK_PUBLISHING=false` and
   verify the processor fails closed with `provider_not_configured`.

Required evidence:

- redacted readiness output showing Facebook Page publishing ready
- redacted approval snapshot for the exact version
- redacted schedule and publish attempt identifiers
- publish attempt lifecycle through `published`
- redacted Meta post ID suffix only
- visible staging Facebook Page post reference
- structured logs with `tenant_id`, `task_id`, `correlation_id`, `schedule_id`, `attempt_id`,
  `draft_id`, `channel`, `state`, and no secrets
- queue delay, publish duration, retry count, and terminal failure count
- rollback proof showing the disabled flag and fail-closed behavior
- completed redaction review proving no raw tokens, app secrets, authorization headers, Page tokens,
  credential refs, private URLs, or user-level engagement data are present

Current Goal R status:

- Evidence file:
  `docs/project/evidence/content-operations/2026-06-10-goal-r-facebook-staging-proof.md`
- Result: blocked; local/staging-readiness check found the live flag off and `pages_manage_posts`
  absent from runtime OAuth scopes.

## Instagram Publish Flow

1. Scheduler locks due schedule.
2. Preflight checks linked professional IG account, permission, media validation, caption length, and
   public asset URL.
3. If `CONTENT_OPS_META_INSTAGRAM_BETA=true`, the publisher resolves the tenant-local selected
   `MetaPage` from the Instagram identity's linked `meta_page_id`, decrypts the active Meta
   connection token or Page token inside the provider boundary, and creates a media container near
   publish time through `POST /{ig-user-id}/media`.
4. Publisher polls container status until ready, failed, or expired. The process scan continues
   polling due attempts in `container_pending` and publishes due attempts in `container_ready`
   through `GET /{container-id}?fields=status_code,status`.
5. Publisher calls `POST /{ig-user-id}/media_publish` with `creation_id`.
6. Publisher stores returned media ID in `PublishedPost`.

Rules:

- Do not create containers days ahead.
- Recreate expired containers for retryable attempts.
- Keep carousels/Reels out of MVP unless beta evidence exists.
- Keep `CONTENT_OPS_META_INSTAGRAM_BETA` off for production tenants until App Review, staging proof,
  security review, and release gates pass.
- Do not put tokens in URLs, request bodies, logs, persisted failure details, or evidence packets.

## Instagram Staging Proof Checklist

Goal S requires a credentialed staging Instagram feed publish before Instagram publishing can be
considered beta-ready. Do not treat adapter tests, fake publisher success, or local public-media
proof as a substitute for this proof.

Required preconditions:

1. Meta test/staging app exposes the selected Instagram publishing permission family for the
   controlled test user and professional Instagram account.
2. The selected product path is documented as either the primary current family
   `instagram_business_basic` plus `instagram_business_content_publish`, or the legacy fallback
   `instagram_basic` plus `instagram_content_publish`.
3. Runtime OAuth scopes include only the selected gated Instagram publishing permissions in staging.
4. `CONTENT_OPS_PUBLIC_MEDIA_BASE_URL` is set to a deployed HTTPS route that maps to
   `/api/content-ops/public-media/<asset_id>/`.
5. `CONTENT_OPS_META_INSTAGRAM_BETA=true` is enabled only for the staging validation window.
6. The selected staging tenant has a linked professional Instagram account and tenant-local selected
   `MetaPage` with a decryptable token usable inside the provider boundary.
7. The exact draft version has internal approval, client approval, immutable approval snapshot,
   caption, and approved image/video media.
8. Operators have a rollback step ready to set `CONTENT_OPS_META_INSTAGRAM_BETA=false` and verify
   the processor fails closed with `provider_not_configured`.

Required evidence:

- redacted readiness output showing Instagram publishing ready
- redacted public-media proof showing HTTPS URL, approved active version, image/video MIME type,
  non-zero content length, and `storage_key_exposed=false`
- unauthenticated public media fetch proof with safe headers and no tenant/private storage data
- redacted approval snapshot for the exact version and media
- redacted schedule and publish attempt identifiers
- container creation evidence with redacted container ID suffix
- container polling lifecycle through ready, retryable, expired, or terminal state
- publish lifecycle through `published` with redacted Instagram media ID suffix
- visible staging Instagram feed media reference
- structured logs with `tenant_id`, `task_id`, `correlation_id`, `schedule_id`, `attempt_id`,
  `draft_id`, `channel`, `state`, and no secrets
- queue delay, container processing duration, publish duration, retry count, and terminal failure
  count
- rollback proof showing the disabled beta flag and fail-closed behavior
- completed redaction review proving no raw tokens, app secrets, authorization headers, Page/IG
  tokens, credential refs, signed URL secrets, private URLs, storage keys, or user-level engagement
  data are present

Current Goal S status:

- Evidence file:
  `docs/project/evidence/content-operations/2026-06-10-goal-s-instagram-staging-proof.md`
- Result: blocked; local/staging-readiness check found the Instagram beta flag off, public media base
  URL unset, and Instagram publishing permissions absent from runtime OAuth scopes.

## Logs and Metrics

Required log fields:

- `tenant_id`
- `task_id`
- `correlation_id`
- `schedule_id`
- `attempt_id`
- `draft_id`
- `channel`
- `state`
- `failure_code`

Required metrics:

- publish attempts by state/channel
- queue delay
- publish duration
- retry count
- terminal failure count
- Meta rate-limit count
- AI generation cost/usage where applicable

## Manual Retry

Retry only when failure state is `failed_retryable`.

Current retry behavior:

- `POST /api/content-ops/publishing/attempts/{attempt_id}/retry/` changes the attempt back to
  `queued`
- retry clears `failure_code`, `failure_detail_safe`, `next_retry_at`, `started_at`, and
  `finished_at`
- retry does not immediately call Meta or the processor task
- retry requires a publish-capable role

Do not retry terminal failures until the root cause is fixed:

- missing permission
- revoked token
- missing Page role
- Instagram not linked
- App Review missing
- invalid media

## Evidence

Store validation evidence in:

- `docs/project/evidence/content-operations/<timestamp>.md`

Use:

- `docs/project/evidence/content-operations/_TEMPLATE.md`

## Final Release Readiness Status

Current final live-publishing decision:

- Evidence file:
  `docs/project/evidence/content-operations/2026-06-10-goal-t-final-release-readiness.md`
- Result: **NO-GO**
- Preflight status: `GATE_BLOCK`
- Live publishing flags must remain disabled:
  - `CONTENT_OPS_LIVE_FACEBOOK_PUBLISHING=false`
  - `CONTENT_OPS_META_INSTAGRAM_BETA=false`

Do not enable live Facebook or Instagram publishing until a later release-readiness pass records:

1. Successful Goal R Facebook staging publish proof.
2. Successful Goal S Instagram staging feed publish proof.
3. Meta App Review permission approval/evidence for `pages_manage_posts` and the selected Instagram
   publishing family.
4. Deployed HTTPS public media proof for the exact Instagram staging asset.
5. Raj, Mira, Sofia, Hannah, Lina, Maya, Nina, and Leo signoff as applicable.
6. ADinsights preflight no longer reports `GATE_BLOCK`.
