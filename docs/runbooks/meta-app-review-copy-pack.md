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

### `instagram_basic` Use Case

`ADinsights requests instagram_basic to retrieve basic Instagram Business account metadata (for example account ID and username) on behalf of onboarded business customers for account selection and identity mapping in analytics setup.`

### `instagram_manage_insights` Use Case

`ADinsights requests instagram_manage_insights to retrieve Instagram Business performance insights on behalf of onboarded business customers and display those insights in tenant-scoped reporting workflows.`

### `catalog_management` Use Case

`ADinsights requests catalog_management only for customers using active catalog-based workflows, to manage product catalog assets on behalf of onboarded business customers.`

### `pages_manage_ads` Use Case

`ADinsights requests pages_manage_ads only for customers using active Page ad-management workflows, to create or manage ads associated with authorized Pages on behalf of onboarded business customers.`

### `pages_manage_metadata` Use Case

`ADinsights requests pages_manage_metadata only for customers using active Page webhook/settings workflows, to configure subscriptions or settings on behalf of onboarded business customers.`

### `pages_messaging` Use Case

`ADinsights requests pages_messaging only for customers using active Messenger workflows, to manage customer messaging interactions on behalf of onboarded business customers.`

## 4) Screencast Script (Required-Now Baseline)

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

## 5) Optional Feature Screencast Add-Ons

Attach only when relevant permission is requested.

- Instagram add-on:
  - Show Instagram account selection and profile metadata retrieval.
  - Show Instagram insights displayed in ADinsights.
- Catalog add-on:
  - Show catalog create/update/delete flow.
- Page ads add-on:
  - Show Page ad creation/management success.
- Page metadata add-on:
  - Show webhook subscription or settings update.
- Messaging add-on:
  - Show message send flow and receipt in client.

## 6) Final Copy QA (Before Submission)

- Includes phrase: `on behalf of onboarded business customers`.
- Includes phrase: `complete Facebook login process`.
- References concrete ADinsights product surface where data/action is shown.
- Matches active permission set in `docs/project/meta-permissions-catalog.yaml`.
- Optional permissions are included only when feature is active.
