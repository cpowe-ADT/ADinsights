# Content Operations Goal M Meta App Review Evidence Spec

Date: 2026-06-10
Timezone: America/Jamaica
Scope: docs/runbooks/evidence
Status: App Review evidence spec locked; live publishing remains disabled

## Source Check

Official Meta sources checked on 2026-06-10:

- Meta Permissions Reference: `https://developers.facebook.com/docs/permissions/`
- Meta App Review screen recordings guide:
  `https://developers.facebook.com/docs/app-review/submission-guide/screen-recordings/`
- Meta Pages API: `https://developers.facebook.com/docs/pages-api/`
- Meta Pages API posts guide: `https://developers.facebook.com/docs/pages-api/posts/`
- Instagram content publishing guide:
  `https://developers.facebook.com/docs/instagram-platform/content-publishing/`
- Instagram media publish reference:
  `https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media_publish/`
- Instagram Platform App Review:
  `https://developers.facebook.com/docs/instagram-platform/app-review/`

Interpretation used for ADinsights:

- `pages_manage_posts` is the locked additive Facebook Page publishing permission.
- `pages_show_list` and `pages_read_engagement` remain required for existing Page selection/context
  and should not be removed from the Page publishing path.
- `instagram_business_basic` plus `instagram_business_content_publish` is the primary current
  Instagram publishing App Review planning family.
- `instagram_basic` plus `instagram_content_publish` is a legacy fallback only if the Meta app
  console and implementation path explicitly use the older Facebook Login / Instagram Graph API
  publishing flow.
- Meta screen-recording guidance requires the submission video to demonstrate how reviewers can test
  every requested permission and feature. ADinsights must show complete login/account connection,
  exact approval flow, publish action, and resulting post/media.

## Locked Permission Scope

| Channel | Permission | Status | Submission rule |
| --- | --- | --- | --- |
| Facebook Page | `pages_manage_posts` | `content_ops_gated` | Request only after Goal O adapter, staging proof, and reviewer screencast are ready. |
| Facebook Page | `pages_show_list` | existing baseline | Preserve for managed Page listing/selection. |
| Facebook Page | `pages_read_engagement` | existing baseline | Preserve for Page context/readiness and post context. |
| Facebook Page | `pages_manage_metadata` | existing optional/Page setup dependency | Include only if the current Page connection flow still requires it in the selected submission path. |
| Instagram | `instagram_business_basic` | `content_ops_gated` | Primary current account identity/readiness permission for Instagram publishing planning. |
| Instagram | `instagram_business_content_publish` | `content_ops_gated` | Primary current Instagram organic feed publishing permission for App Review planning. |
| Instagram | `instagram_basic` + `instagram_content_publish` | `content_ops_gated_fallback` | Use only for confirmed legacy Facebook Login / Instagram Graph API path. |

No Content Ops publishing permission is added to default runtime OAuth by Goal M.

## Reviewer Copy

### `pages_manage_posts`

ADinsights uses `pages_manage_posts` to publish approved organic Facebook Page posts on behalf of
onboarded business customers. In Content Ops, an agency user creates a post draft, an internal
reviewer approves it, the client approves the exact version, and a publish-capable operator
schedules or confirms publishing to the selected Facebook Page. The permission is used only for
tenant-scoped Pages selected by the business user and only after approval evidence is stored in
ADinsights.

### `instagram_business_basic`

ADinsights uses `instagram_business_basic` to identify the Instagram professional account selected
for Content Ops publishing on behalf of onboarded business customers. The selected account identity
is shown in ADinsights readiness and publishing screens so users can confirm the correct Instagram
account before any media is published.

### `instagram_business_content_publish`

ADinsights uses `instagram_business_content_publish` to publish approved organic Instagram feed
media on behalf of onboarded business customers. The permission is used only after media validation,
internal approval, client approval, and operator confirmation in Content Ops. ADinsights records
container creation, processing, publishing, retry, and terminal states without exposing tokens or
private storage keys.

## Screencast Script

1. Start at ADinsights Data Sources or Content Ops readiness.
2. Demonstrate the complete Facebook login process for Facebook Page publishing, or the selected
   Instagram professional account connection flow for Instagram publishing.
3. Show the permission grant screen with only the requested publishing permissions.
4. Select or confirm the Facebook Page and/or Instagram professional account.
5. Create a Content Ops brief.
6. Create or select the draft version that will be published.
7. Attach or generate the media asset.
8. For Instagram, show public-media URL readiness proof before publishing.
9. Submit the exact version for internal approval and record approval.
10. Submit the exact version for client approval and record approval.
11. Schedule or confirm publishing for the requested channel.
12. Show Production Queue lifecycle:
    - Facebook Page: queued, preflight, publishing, published or safe failure.
    - Instagram: queued, preflight, container creating, container pending, container ready,
      publishing, published or safe failure.
13. Show the published Facebook Page post or Instagram media externally.
14. Return to ADinsights and show the published-post record and aggregate-only reporting link.
15. Show redacted evidence/logs proving no raw access tokens, app secrets, credential refs, private
    storage keys, signed URL secrets, or user-level engagement identities are exposed.

## Test Account And Asset Needs

- Meta test app or staging app with the selected permission family visible in App Review.
- Business Manager test business controlled by ADinsights.
- Test Facebook user with sufficient Page task access to create content.
- Test Facebook Page with Page Publishing Authorization completed if required by Meta.
- Instagram professional account connected to the test business/product path.
- At least one approved square image and one video candidate hosted through the Goal N public media
  URL/CDN proof.
- ADinsights staging tenant with agency/admin, internal reviewer, client approver, publish-capable
  operator, and viewer roles.
- Feature flags showing live publishing disabled by default and rollback available.

## Redaction Checklist

Never include:

- raw access tokens, refresh tokens, app secret, client secret, or authorization headers
- `credential_ref` values
- private storage keys or local filesystem paths
- signed URL secrets or full CDN URLs if they contain sensitive query parameters
- unredacted app ID, tenant ID, Page ID, IG user ID, post ID, or media ID
- provider raw responses
- viewer, commenter, reactor, follower, or other user-level engagement identities

Required evidence may include redacted/summarized:

- app ID suffix/prefix
- tenant alias
- Page/IG/post/media ID last four characters
- safe provider status code/reason
- publish attempt ID
- correlation ID
- aggregate metrics totals

## Submission Packet

Store the packet under `docs/project/evidence/content-operations/app-review-<date>/` after staging
evidence exists. Required files:

- `README.md`: run summary, requested permissions, selected Meta product path, final decision.
- `permission-copy.md`: reviewer copy per requested permission.
- `screencast-script.md`: exact script and recording links.
- `test-accounts.md`: redacted test users, roles, Page/IG assets, and setup notes.
- `readiness-evidence.md`: readiness endpoint/state screenshots or redacted API output.
- `approval-evidence.md`: internal/client approval snapshot.
- `publishing-evidence.md`: publish attempt lifecycle and provider result.
- `media-url-evidence.md`: public media URL/CDN proof for Instagram.
- `redaction-checklist.md`: completed redaction review.
- `rollback-proof.md`: feature flag and rollback confirmation.

## Review Gates

- Maya: verifies selected Meta product path, permission family, reviewer copy, and screencast.
- Nina: verifies redaction, secrets handling, and PII/aggregate-only boundaries.
- Hannah: verifies evidence packet completeness and runbook links.
- Raj: verifies release sequencing and no runtime scope activation before gates pass.
- Sofia: verifies API/readiness contract implications and no payload drift.

## Launch Blockers After Goal M

- Meta app console evidence for permission availability is still required.
- Goal N public media URL/CDN proof is still required before Instagram App Review submission.
- Goal O/P live adapters are not implemented.
- Goal R/S staging publish evidence does not exist.
- Final release preflight remains expected to report `GATE_BLOCK` until App Review, staging proof,
  and release approvals are complete.

## Validation Results

- `git diff --check -- docs/project/meta-permissions-catalog.yaml docs/project/meta-permission-profile.md docs/runbooks/content-operations-app-review.md docs/runbooks/meta-app-review-submission-checklist.md docs/runbooks/meta-app-review-copy-pack.md docs/project/content-operations-meta-publishing-spec.md docs/project/content-operations-live-publishing-audit-spec.md docs/project/content-operations-sprint0-decisions.md docs/project/evidence/content-operations/2026-06-10-goal-m-app-review-evidence-spec.md docs/ops/doc-index.md docs/ops/agent-activity-log.md` passed.
- `docs/project/meta-permissions-catalog.yaml` parsed successfully and contains `pages_manage_posts`, `instagram_content_publish`, `instagram_business_basic`, and `instagram_business_content_publish`.
- Stale permission scan found no remaining `likely pages_manage_posts`, `likely legacy`, `Business API family to verify`, or `Current Graph API family` wording. The remaining `publish_pages` reference is an intentional warning not to request the deprecated Page publishing scope.
- Scope gatekeeper advisory packet: `PASS_SINGLE_SCOPE` for docs-only Goal M scope.
- Contract guard advisory packet: `PASS_NO_CONTRACT_CHANGE`; no breaking contract change detected because Goal M did not alter runtime OAuth, serializers, or setup/status payloads.
- ADinsights preflight packet persisted at `docs/project/evidence/content-operations/preflight-2026-06-10-goal-m-app-review/`.
- ADinsights preflight result: `GATE_BLOCK`, expected until later goals provide public media URL proof, live adapters, staging publish evidence, App Review approval, security sign-off, and final release approval.
