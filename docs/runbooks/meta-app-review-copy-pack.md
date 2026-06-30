# Meta App Review Copy Pack (Reusable)

Timezone baseline: `America/Jamaica`.

Purpose: provide reusable, reviewer-ready text and screencast scripts so ADinsights does not rewrite App Review copy each cycle.

Use with:

- `docs/project/meta-permissions-catalog.yaml`
- `docs/project/meta-permission-profile.md`
- `docs/runbooks/meta-app-review-submission-checklist.md`
- `docs/runbooks/meta-app-review-validation.md`

## 1) Global Use-Case Intro (Paste-Ready)

Use this as the opening context in App Review:

`ADinsights is a multi-tenant analytics and reporting platform that connects business advertising accounts and retrieves aggregated performance metrics on behalf of onboarded business customers. Business users connect their Facebook assets in ADinsights, select authorized Pages and ad accounts, and then view reporting metrics (for example impressions, clicks, spend, reach, and conversions) inside tenant-scoped dashboards.`

## 2) Required-Now Permission Copy Blocks

### `ads_read` Use Case

`ADinsights requires ads_read to retrieve ad performance reporting data on behalf of onboarded business customers and display these metrics in tenant-scoped analytics dashboards. This permission is used only for business reporting workflows after the customer explicitly connects authorized assets.`

### `ads_management` Use Case

`ADinsights requests ads_management to support business ad-account management compatibility in customer environments where this scope is required, while maintaining reporting continuity for authorized assets. The permission is used on behalf of onboarded business customers to enable permitted campaign/account operations and corresponding analytics workflows.`

### `business_management` Use Case

`ADinsights requires business_management to access Business Manager assets on behalf of onboarded business customers, so the platform can bind authorized ad accounts to the correct tenant and retrieve reporting data only for approved business assets.`

### `pages_read_engagement` Use Case

`ADinsights requires pages_read_engagement to read Page-level context and metadata needed during onboarding and asset verification on behalf of onboarded business customers. This enables accurate Page-to-account linkage for reporting setup.`

### `pages_show_list` Use Case

`ADinsights requires pages_show_list so business users can view and select the Pages they manage during onboarding. This permission is used to verify ownership and connect the correct Page assets on behalf of onboarded business customers.`

## 3) Optional Near-Term Copy Blocks

Use only when the related feature is active in product.
These permissions are optional. They are not part of the baseline ADinsights Facebook Login
authorize request today, and Instagram linkage does not use a standalone Instagram OAuth flow.

### `instagram_basic` Use Case

`ADinsights requests instagram_basic only when an active Instagram-linked product flow needs basic Instagram Business account metadata (for example account ID and username) on behalf of onboarded business customers for account selection and identity mapping during Meta asset setup.`

### `instagram_manage_insights` Use Case

`ADinsights requests instagram_manage_insights only when an active Instagram reporting feature needs Instagram Business performance insights on behalf of onboarded business customers and displays those insights in tenant-scoped reporting workflows.`

### `catalog_management` Use Case

`ADinsights requests catalog_management only for customers using active catalog-based workflows, to manage product catalog assets on behalf of onboarded business customers.`

### `pages_manage_ads` Use Case

`ADinsights requests pages_manage_ads only for customers using active Page ad-management workflows, to create or manage ads associated with authorized Pages on behalf of onboarded business customers.`

### `pages_manage_metadata` Use Case

`ADinsights requests pages_manage_metadata only for customers using active Page webhook/settings workflows, to configure subscriptions or settings on behalf of onboarded business customers.`

### `pages_messaging` Use Case

`ADinsights requests pages_messaging only for customers using active Messenger workflows, to manage customer messaging interactions on behalf of onboarded business customers.`

## 4) Content Ops Publishing Copy Blocks

Use only for the Content Ops live-publishing App Review submission. Do not paste these into the
baseline reporting submission.

### `pages_manage_posts` Use Case

`ADinsights uses pages_manage_posts to publish approved organic Facebook Page posts on behalf of onboarded business customers. In the Content Ops workflow, the business creates a draft, internal and client reviewers approve the exact content version, and a publish-capable operator schedules or confirms publishing to the selected Facebook Page. ADinsights tracks the publish attempt in a tenant-scoped queue and can disable live publishing through feature flags.`

### `instagram_business_basic` Use Case

`ADinsights uses instagram_business_basic to identify the Instagram professional account selected for approved Content Ops publishing on behalf of onboarded business customers. This account identity is shown in ADinsights readiness and publishing screens so users can confirm the correct Instagram account before any media is published.`

### `instagram_business_content_publish` Use Case

`ADinsights uses instagram_business_content_publish to publish approved organic Instagram feed media on behalf of onboarded business customers. The permission is used only after media validation, internal approval, client approval, and operator confirmation in Content Ops. ADinsights records container creation, processing, publishing, retry, and terminal states without exposing tokens or private storage keys.`

### Legacy Fallback: `instagram_basic` + `instagram_content_publish`

`ADinsights uses instagram_basic and instagram_content_publish only if the Meta app uses the older Facebook Login / Instagram Graph API publishing flow. The use case remains approved Content Ops publishing on behalf of onboarded business customers, with linked Instagram professional account selection, media validation, approval evidence, and publish lifecycle evidence shown in ADinsights.`

## 5) Screencast Script (Required-Now Baseline)

Use this storyboard as default review recording sequence.

1. Start at ADinsights Data Sources page.
2. Narrate that the user is a business admin connecting assets for reporting.
3. Click "Connect with Facebook" and show the complete Facebook login process.
4. Show permission grant screen and confirm required permissions.
5. Return to ADinsights and select Page + ad account.
6. Trigger provisioning/sync.
7. Open ADinsights reporting view and show impressions, clicks, spend, reach, conversions.
8. Show that data is visible in tenant-scoped business dashboard context.
9. Close by stating permission usage is on behalf of onboarded business customers.

## 6) Content Ops Publishing Screencast Script

Use this storyboard for Goal M and later App Review submission evidence.

1. Start at ADinsights Data Sources or Content Ops readiness screen.
2. Demonstrate the complete Facebook login process or the selected Instagram professional account
   connection flow required by the Meta product path.
3. Show the permission grant screen for only the requested publishing permissions.
4. Select or confirm the Facebook Page and/or Instagram professional account in ADinsights.
5. Create a Content Ops brief and draft.
6. Attach or generate the media asset, then show media readiness and public-media URL proof for
   Instagram.
7. Submit the exact draft version for internal approval and record the internal approval.
8. Submit the exact draft version for client approval and record the client approval.
9. Schedule or confirm publishing for the requested channel.
10. Show the Production Queue lifecycle:
    - Facebook Page: queued, preflight, publishing, published or safe failure.
    - Instagram: queued, preflight, container creating, container pending, container ready,
      publishing, published or safe failure.
11. Show the published Facebook Page post or Instagram media externally.
12. Return to ADinsights and show the published-post record plus aggregate-only reporting link.
13. Show redacted logs/evidence proving no raw tokens, credential refs, private storage keys, signed
    URL secrets, or user-level engagement identities are exposed.

## 7) Optional Feature Screencast Add-Ons

Attach only when relevant permission is requested.

- Instagram add-on:
  - Show Instagram account selection through the Meta asset-selection flow, not a standalone Instagram OAuth screen.
  - Show Instagram profile metadata retrieval or Instagram insights displayed in ADinsights only when that feature is active.
- Catalog add-on:
  - Show catalog create/update/delete flow.
- Page ads add-on:
  - Show Page ad creation/management success.
- Page metadata add-on:
  - Show webhook subscription or settings update.
- Messaging add-on:
  - Show message send flow and receipt in client.

## 8) Final Copy QA (Before Submission)

- Includes phrase: `on behalf of onboarded business customers`.
- Includes phrase: `complete Facebook login process`.
- References concrete ADinsights product surface where data/action is shown.
- Matches active permission set in `docs/project/meta-permissions-catalog.yaml`.
- Optional permissions are included only when feature is active.
- Does not mention `read_insights` for the current Facebook Login Page Insights flow.
- For Content Ops, mentions internal approval, client approval, operator confirmation, and
  aggregate-only reporting.
