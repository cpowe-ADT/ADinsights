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

| Permission | Use case text must include | Screencast proof must include |
| --- | --- | --- |
| `ads_read` | ADinsights reads ad performance data on behalf of onboarded business customers for tenant-scoped dashboards and analytics. | Complete Facebook login and permission grant, then impressions/conversions/spend/clicks/reach displayed in ADinsights. |
| `ads_management` | ADinsights uses ad-management access on behalf of business customers to support campaign/account operations and reporting continuity. | Complete Facebook login and permission grant, then post-grant ad performance access in ADinsights. |
| `business_management` | ADinsights reads/manages Business Manager assets on behalf of businesses to bind ad accounts during onboarding. | Complete Facebook login and permission grant, then successful business asset selection with ad performance access. |
| `pages_read_engagement` | ADinsights reads Page context on behalf of businesses for onboarding verification and account linkage. | Complete Facebook login and permission grant, then Page-linked content/metadata shown in ADinsights. |
| `pages_show_list` | ADinsights lists managed Pages so business users can verify ownership and connect the correct Page. | Complete Facebook login and permission grant, then managed Page list shown and selected in ADinsights setup. |

## 3) Optional Near-Term Submission Items

Only submit permissions below when the corresponding feature is active in ADinsights.

| Permission | Feature gate condition | Use case text must include | Screencast proof must include |
| --- | --- | --- | --- |
| `instagram_basic` | Instagram account discovery is enabled. | Specific profile fields required on behalf of business customers (for example username, ID) and where displayed in ADinsights. | Complete Facebook login with Instagram selection, then metadata displayed in ADinsights. |
| `instagram_manage_insights` | Instagram insights are shown in product. | How ADinsights retrieves and uses Instagram insights on behalf of businesses for reporting workflows. | Complete Facebook login, then Instagram insights retrieval and display in ADinsights. |
| `catalog_management` | Catalog workflows are enabled. | Why ADinsights must manage product catalogs for client businesses. | Login + catalog create/update/delete flow in ADinsights. |
| `pages_manage_ads` | Page ad-management flow is enabled. | Why ADinsights creates/manages ads for business Pages. | Login + Page ad creation/management success in ADinsights. |
| `pages_manage_metadata` | Page webhook/settings management is enabled. | Why ADinsights needs webhook/settings access for Page administration. | Login + webhook subscription or settings update flow in ADinsights. |
| `pages_messaging` | Messenger integration is enabled. | Messaging functions offered to onboarded business users. | Login + message send from ADinsights + receipt in Messenger client + cURL generation flow. |

## 4) Evidence Packet Requirements

For each review run, save one artifact in `docs/project/evidence/meta-validation/` including:

- Run timestamp (local + UTC)
- Operator name
- Redacted app/ad-account identifiers
- Permission list requested and granted
- Endpoint request/response statuses from validation flow
- Screencast links or references
- Final decision (`pass`/`fail`) and remediation notes

Never include raw access tokens.

## 5) Remediation Pointers

- Missing required permissions in OAuth exchange/page connect:
  - Re-run OAuth with `auth_type=rerequest` and re-complete connect flow.
- Missing ad account visibility:
  - Confirm Business Manager access for the selected account, then repeat connect.
- Optional permission requested without active feature:
  - Remove from submission scope until feature activation.

## 6) Final QA Gate Before Submit

- `required_now` permissions are complete and justified.
- Optional permissions are requested only for active features.
- Runtime gate in backend matches runbook/profile wording.
- Use-case and screencast wording is pulled from `docs/runbooks/meta-app-review-copy-pack.md` (or intentionally justified as custom text).
- Evidence artifact is stored and redacted.
- Use-case text explicitly states "on behalf of onboarded business customers."
- Screencast script includes the words "complete Facebook login process."
