# Meta App Review Submission Checklist (Lean)

Timezone baseline: `America/Jamaica`.

Use this checklist to prepare Meta App Review artifacts for the ADinsights permission set defined in `docs/project/meta-permissions-catalog.yaml`.

## 0) Quality Bar For Reviewer Acceptance

Every permission submission should include:

- Complete login flow language: "Demonstrate the complete Facebook login process..."
- Delegation language: "on behalf of onboarded business customers."
- Product evidence language: "shown in ADinsights at <page/step>."
- Outcome language: "enables <specific business workflow>."

## 1) Inputs To Prepare

- Latest permission catalog: `docs/project/meta-permissions-catalog.yaml`
- Permission policy/profile: `docs/project/meta-permission-profile.md`
- Copy pack: `docs/runbooks/meta-app-review-copy-pack.md`
- Validation runbook: `docs/runbooks/meta-app-review-validation.md`
- Runtime gate reference: `backend/integrations/views.py`

## 2) Required-Now Submission Items

Complete all rows below before submission.

| Permission              | Use case text must include                                                                                                            | Screencast proof must include                                                                                          |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| `ads_read`              | ADinsights reads ad performance data on behalf of onboarded business customers for tenant-scoped dashboards and analytics.            | Complete Facebook login and permission grant, then impressions/conversions/spend/clicks/reach displayed in ADinsights. |
| `ads_management`        | ADinsights uses ad-management access on behalf of business customers to support campaign/account operations and reporting continuity. | Complete Facebook login and permission grant, then post-grant ad performance access in ADinsights.                     |
| `business_management`   | ADinsights reads/manages Business Manager assets on behalf of businesses to bind ad accounts during onboarding.                       | Complete Facebook login and permission grant, then successful business asset selection with ad performance access.     |
| `pages_read_engagement` | ADinsights reads Page context on behalf of businesses for onboarding verification and account linkage.                                | Complete Facebook login and permission grant, then Page-linked content/metadata shown in ADinsights.                   |
| `pages_show_list`       | ADinsights lists managed Pages so business users can verify ownership and connect the correct Page.                                   | Complete Facebook login and permission grant, then managed Page list shown and selected in ADinsights setup.           |

## 3) Release-Gate Rule: Scope Changes

Any modification to the following backend constants **MUST** be reflected in the `docs/project/meta-permissions-catalog.yaml` and this checklist before the PR is merged:
- `DEFAULT_META_OAUTH_SCOPES`
- `DEFAULT_META_PAGE_INSIGHTS_OAUTH_SCOPES`
- `DEFAULT_META_REQUIRED_SCOPES`
- `REQUIRED_INSIGHTS_SCOPES`

Failure to update the catalog triggers a release-gate block during security review.

## 4) Optional Near-Term Submission Items

Only submit permissions below when the corresponding feature is active in ADinsights.
These are not part of the current baseline Facebook Login authorize request and should not appear in
the default screencast unless the active feature path explicitly requires them.

| Permission                  | Feature gate condition                       | Use case text must include                                                                                                     | Screencast proof must include                                                              |
| --------------------------- | -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------ |
| `instagram_basic`           | Instagram account discovery is enabled.      | Specific profile fields required on behalf of business customers (for example username, ID) and where displayed in ADinsights. | Complete Facebook login with Instagram selection, then metadata displayed in ADinsights.   |
| `instagram_manage_insights` | Instagram insights are shown in product.     | How ADinsights retrieves and uses Instagram insights on behalf of businesses for reporting workflows.                          | Complete Facebook login, then Instagram insights retrieval and display in ADinsights.      |
| `catalog_management`        | Catalog workflows are enabled.               | Why ADinsights must manage product catalogs for client businesses.                                                             | Login + catalog create/update/delete flow in ADinsights.                                   |
| `pages_manage_ads`          | Page ad-management flow is enabled.          | Why ADinsights creates/manages ads for business Pages.                                                                         | Login + Page ad creation/management success in ADinsights.                                 |
| `pages_manage_metadata`     | Page webhook/settings management is enabled. | Why ADinsights needs webhook/settings access for Page administration.                                                          | Login + webhook subscription or settings update flow in ADinsights.                        |
| `pages_messaging`           | Messenger integration is enabled.            | Messaging functions offered to onboarded business users.                                                                       | Login + message send from ADinsights + receipt in Messenger client + cURL generation flow. |

## 5) Evidence Packet Requirements

For each review run, save one artifact in `docs/project/evidence/meta-validation/` including:

- Run timestamp (local + UTC)
- Operator name
- Redacted app/ad-account identifiers
- Permission list requested and granted
- Endpoint request/response statuses from validation flow
- Screencast links or references
- Final decision (`pass`/`fail`) and remediation notes

Never include raw access tokens.

## 6) Remediation Pointers

- Missing required permissions in OAuth exchange/page connect:
  - Re-run OAuth with `auth_type=rerequest` and re-complete connect flow.
- Invalid Facebook Login scope in setup docs or env:
  - Do not request `read_insights`; Page Insights now relies on `pages_show_list`, `pages_read_engagement`, and `pages_manage_metadata`.
- Instagram permissions added to the baseline login plan:
  - Remove them unless an active Instagram feature explicitly requires them and the reviewer copy,
    screencast, and product path all match.
- Missing ad account visibility:
  - Confirm Business Manager access for the selected account, then repeat connect.
- Optional permission requested without active feature:
  - Remove from submission scope until feature activation.

## 7) Content Ops Publishing Submission Items

Use this section only for the Content Ops live-publishing submission. Do not add these permissions
to the baseline Facebook Login evidence unless Content Ops publishing is the active review scope.

| Permission | Feature gate condition | Use case text must include | Screencast proof must include |
| --- | --- | --- | --- |
| `pages_manage_posts` | Facebook Page organic publishing adapter is implemented behind a disabled-by-default flag and staging proof exists. | ADinsights publishes approved organic Facebook Page posts on behalf of onboarded business customers after internal/client approval and operator confirmation. | Complete Facebook login process, Page selection, approved draft/version, schedule or publish confirmation, Production Queue lifecycle, and visible Facebook Page post. |
| `instagram_business_basic` | Instagram publishing uses the current Instagram API with Instagram Login product path. | ADinsights identifies the Instagram professional account selected for approved Content Ops publishing on behalf of onboarded business customers. | Instagram professional account connection, selected account identity/readiness in ADinsights, and blocked state when the account is unavailable. |
| `instagram_business_content_publish` | Instagram publishing adapter is implemented behind a disabled-by-default flag, public media URL proof exists, and staging proof exists. | ADinsights publishes approved organic Instagram feed media on behalf of onboarded business customers after media validation, internal/client approval, and operator confirmation. | Approved media asset, public-media readiness proof, approval snapshot, schedule or publish confirmation, container lifecycle, published Instagram media, and aggregate reporting link. |
| `instagram_basic` + `instagram_content_publish` | Legacy fallback only when the Meta app console and implementation path explicitly use the older Facebook Login / Instagram Graph API publishing flow. | Same Content Ops approval and publishing narrative, but tied to the confirmed legacy Instagram Graph API product path. | Complete Facebook login process with the legacy permission family, linked Instagram professional account, container lifecycle, and published media. |

Content Ops submission packet must also include:

- Meta product path selected: `facebook_login_pages_api`, `instagram_business_login`, or documented
  legacy fallback.
- Redacted app ID, tenant ID, Page ID, IG user ID, post ID, and media ID.
- Feature flags and rollback flags proving live publishing can be disabled.
- Public media URL proof for Instagram before requesting Instagram publishing review.
- Log/evidence review confirming no raw access tokens, app secrets, credential refs, private storage
  keys, signed URL secrets, or user-level engagement identities.

## 8) Final QA Gate Before Submit

- `required_now` permissions are complete and justified.
- Optional permissions are requested only for active features.
- Content Ops publishing permissions are requested only after the matching adapter, staging proof,
  public media proof, and redacted evidence packet exist.
- Runtime gate in backend matches runbook/profile wording.
- Use-case and screencast wording is pulled from `docs/runbooks/meta-app-review-copy-pack.md` (or intentionally justified as custom text).
- Evidence artifact is stored and redacted.
- Use-case text explicitly states "on behalf of onboarded business customers."
- Screencast script includes the words "complete Facebook login process."
- Baseline Facebook Login evidence does not claim `read_insights` or imply a standalone Instagram OAuth flow.
