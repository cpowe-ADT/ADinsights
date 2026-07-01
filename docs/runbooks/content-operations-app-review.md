# Content Operations Meta App Review Runbook

Status: release blocked / evidence pending
Timezone baseline: `America/Jamaica`

## Purpose

Prepare Meta App Review evidence for Content Operations publishing permissions without changing the
existing ADinsights reporting permission baseline.

## Baseline Rule

Do not add publishing scopes to default runtime OAuth until the active Content Operations feature
requires them and App Review evidence is ready.

The runtime mechanism is the `META_ENABLE_PUBLISH_SCOPES` flag (default off; see
`docs/project/feature-flags-reference.md`). When off, the authorize request is exactly today's
reporting baseline. When on, `pages_manage_posts` / `instagram_basic` / `instagram_content_publish`
(overridable via `META_PUBLISH_SCOPES`) are appended to the authorize request and `instagram_basic`
is exempted from the login-ignored filter. Enabling the flag only changes what is _requested_ — the
permissions are still granted only after App Review approval or for an approved test user, and live
publishing remains separately gated by the `CONTENT_OPS_LIVE_*` flags.

Existing reporting/onboarding permissions remain governed by:

- `docs/project/meta-permission-profile.md`
- `docs/project/api-contract-changelog.md`
- `docs/runbooks/meta-app-review-validation.md`
- `docs/runbooks/meta-app-review-submission-checklist.md`

## Publishing Permissions to Validate

Facebook Page publishing:

- locked additive permission: `pages_manage_posts`
- preserve existing Page selection/context permissions: `pages_show_list`, `pages_read_engagement`,
  and current Page setup dependencies such as `pages_manage_metadata` where already required by the
  Page connection flow
- do not request deprecated Page publishing scopes such as `publish_pages`

Instagram publishing:

- primary current App Review planning family: `instagram_business_basic` plus
  `instagram_business_content_publish`
- legacy fallback only if the Meta app console and implementation path explicitly use the older
  Instagram Graph API flow: `instagram_basic` plus `instagram_content_publish`
- do not request Instagram publishing permissions until the exact Meta product path is confirmed,
  the app console exposes the permission family, and the screencast shows the corresponding account
  connection flow

## Evidence Flow

Screencast should show:

1. Complete Facebook login process.
2. Permission grant screen.
3. ADinsights Page selection.
4. Instagram professional account linkage check, if IG scope is requested.
5. Content brief creation.
6. AI caption/graphic draft creation.
7. Internal approval.
8. Client approval.
9. Schedule or publish-now action.
10. Published post visible on Facebook Page or Instagram.
11. Aggregate reporting link in ADinsights.

Use wording:

- "ADinsights performs this action on behalf of onboarded business customers."
- "The user approves the exact content version before scheduling."
- "ADinsights stores only aggregate reporting metrics."

## Reviewer Copy

### `pages_manage_posts`

Use-case text:

`ADinsights uses pages_manage_posts to publish approved organic Facebook Page posts on behalf of onboarded business customers. In Content Ops, an agency user creates a post draft, an internal reviewer approves it, the client approves the exact version, and a publish-capable operator schedules or confirms publishing to the selected Facebook Page. The permission is used only for tenant-scoped Pages selected by the business user and only after approval evidence is stored in ADinsights.`

Screencast proof:

- Complete Facebook login process and permission grant.
- ADinsights Page selection/readiness screen for the selected tenant.
- Content brief and draft version.
- Internal approval and client approval of the exact version.
- Schedule or publish confirmation for Facebook Page.
- Production Queue row showing publish attempt lifecycle.
- Published Facebook Page post and ADinsights published-post record.

### `instagram_business_basic`

Use-case text:

`ADinsights uses instagram_business_basic to identify the Instagram professional account selected for Content Ops publishing on behalf of onboarded business customers. The selected account identity is used to verify readiness before publishing approved Instagram media from ADinsights.`

Screencast proof:

- Instagram professional account connection for the selected Meta product path.
- Selected Instagram account visible in ADinsights readiness or publishing identity state.
- Blocked state when no linked/selected Instagram professional account is available.

### `instagram_business_content_publish`

Use-case text:

`ADinsights uses instagram_business_content_publish to publish approved organic Instagram feed media on behalf of onboarded business customers. In Content Ops, a user creates or uploads media, validates that the media is approved and fetchable, obtains internal and client approval for the exact post version, then schedules or confirms publishing. ADinsights tracks container creation, processing, publishing, retry, and terminal states without exposing tokens or private storage keys.`

Screencast proof:

- Instagram professional account connection for the selected Meta product path.
- Approved image/video asset with public-media readiness proof.
- Internal approval and client approval of the exact Instagram version.
- Schedule or publish confirmation for Instagram.
- Production Queue row showing container creation, pending/ready state, publish state, and final
  published media ID.
- Published Instagram media visible externally and aggregate reporting link in ADinsights.

### Legacy Fallback: `instagram_basic` + `instagram_content_publish`

Use this copy only if the app uses the older Facebook Login / Instagram Graph API route and the
Meta app console exposes these permissions for the app. Do not mix this fallback with the primary
business permission family in the same submission unless Meta explicitly requires both for the
chosen product path.

## Submission Packet

Include:

- app ID redacted
- Graph API version
- permission list requested
- Meta product path selected (`facebook_login_pages_api`, `instagram_business_login`, or documented
  legacy fallback)
- feature flag name
- tenant/test user
- Page ID redacted
- IG user ID redacted
- endpoint/status evidence
- screencast links
- final pass/fail

Never include raw tokens.

## Reviewer Copy Requirements

For each permission:

- name the ADinsights screen
- name the user action
- say "on behalf of onboarded business customers"
- describe the business outcome
- avoid vague "analytics purposes" language

## Release Gate

Content publishing cannot be enabled for production tenants until:

- permission family is confirmed
- Meta app console screenshot/evidence proves the requested permissions are available for the app
- App Review evidence exists
- staging publish proof exists
- runbooks are linked
- Raj/Maya/Hannah sign off

## Current Readiness Result

Latest local release-readiness pass:

- Date: 2026-06-10
- Evidence report:
  `docs/project/evidence/content-operations/2026-06-10-goal-i-release-readiness.md`
- Packet directory:
  `docs/project/evidence/content-operations/preflight-2026-06-10-goal-i/`
- Release status: `GATE_BLOCK`
- Blocking issue: scope control gate blocked by architecture-level scope risk.
- Warnings:
  - contract integrity requires follow-up before release
  - security/PII gate requires verification due to sensitive signals
- Required approvers from packet: Raj, Mira, Sofia, Hannah, Lina.

Live Facebook Page or Instagram publishing must remain disabled until this gate is rerun and no
release blockers remain.

## Remaining Evidence Before Submission

- Confirm the exact Meta permission family in the developer console for Facebook Page publishing and
  Instagram publishing, including the primary Instagram business family or the documented legacy
  fallback.
- Capture reviewer copy for each requested permission using the wording in this runbook.
- Capture a screencast from login through exact content approval, schedule/publish action, visible
  Facebook/Instagram post, and aggregate reporting link.
- Capture staging API/task evidence for:
  - readiness axes
  - selected Page and linked Instagram professional account
  - approved draft version and immutable approval snapshot
  - safe media asset URL validation
  - publish attempt state transitions
  - provider result with redacted post/media ID
  - aggregate metric refresh
- Capture logs/metrics for queue delay, publish duration, retry count, and safe failure codes.
- Verify no raw tokens, credential refs, signed URLs, user-level engagement data, or unredacted Page
  or IG identifiers are present in evidence.
