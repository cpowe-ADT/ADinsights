# Meta Permission Profile (Lean Governance)

Timezone baseline: `America/Jamaica`.

## Purpose

This document defines the ADinsights Meta permission strategy for active and near-term features. It is the human-readable companion to `docs/project/meta-permissions-catalog.yaml`.

## Scope For This Pass

- Included: `required_now` and `optional_near_term` permissions.
- Excluded: full A-Z Meta permission expansion.
- No runtime behavior changes are introduced by this profile.

## Authoritative Sources And Precedence

1. Runtime gate in `backend/integrations/views.py` is authoritative for onboarding/provisioning readiness:
   - `(ads_read OR ads_management)` AND `business_management` AND `pages_read_engagement` AND `pages_show_list`.
2. Default requested OAuth scopes are configured in:
   - `backend/core/settings.py` (`META_OAUTH_SCOPES` default list)
   - `backend/.env.sample` (`META_OAUTH_SCOPES` example list)
3. If scope examples drift from runtime enforcement, runtime enforcement is the source of truth.
4. For the Page Insights Facebook Login flow, do not request `read_insights`; current runtime behavior
   depends on Page-scoped permissions instead.
5. Instagram business linking is optional and is handled through the Meta asset-selection flow in
   ADinsights; there is no standalone Instagram OAuth contract in the product today.
6. Meta's public changelog is ahead of the repo pin. As of `2026-04-04`, the official
   Graph/Marketing API changelog exposes `v25.0`, but ADinsights intentionally remains pinned to
   `META_GRAPH_API_VERSION=v24.0` until an explicit compatibility migration is completed.
7. Goal M App Review planning checked Meta's current public docs on 2026-06-10. The current
   Instagram publishing family for new App Review planning is `instagram_business_basic` plus
   `instagram_business_content_publish`. The older `instagram_basic` plus
   `instagram_content_publish` path remains documented as a fallback only if the app console and
   implementation path explicitly use the legacy Instagram Graph API flow.

## Product-State Separation

Do not collapse these into one generic “Meta connected” state:

- Meta auth/setup state
- Meta asset selection state
- Meta marketing credential state
- Page Insights state
- Instagram linkage state
- direct sync state
- live warehouse reporting readiness

Repo facts:

- `GET /api/meta/accounts/` is ad-account state.
- `GET /api/meta/pages/` is Facebook Page state.
- `GET /api/datasets/status/` is live-reporting readiness.
- direct sync and warehouse snapshot generation are separate stages.

## Active And Near-Term Permission Set

| Permission                           | Status                       | Runtime gate required    | Requested in marketing OAuth | Requested in Page Insights OAuth | Why it exists now                                                                           |
| ------------------------------------ | ---------------------------- | ------------------------ | ---------------------------- | -------------------------------- | ------------------------------------------------------------------------------------------- |
| `ads_read`                           | `required_now`               | Yes                      | Yes                          | No                               | Core ad-metrics read path for dashboards and sync validation.                               |
| `ads_management`                     | `required_now`               | Yes (OR with `ads_read`) | Yes                          | No                               | Alternate acceptable ad scope in runtime gate; supports ad-management readiness.            |
| `business_management`                | `required_now`               | Yes                      | Yes                          | No                               | Business asset access needed for ad account binding.                                        |
| `pages_read_engagement`              | `required_now`               | Yes                      | Yes                          | Yes                              | Page-level context required by connect flow and dependencies.                               |
| `pages_show_list`                    | `required_now`               | Yes                      | Yes                          | Yes                              | Page ownership/selection required during onboarding.                                        |
| `read_insights`                      | not requested                | No                       | No                           | No                               | Invalid for the current Facebook Login flow; keep it out of runtime scope lists.            |
| `instagram_basic`                    | `optional_near_term`         | No                       | No                           | No                               | Optional legacy Instagram account discovery and identity mapping.                           |
| `instagram_manage_insights`          | `optional_near_term`         | No                       | No                           | No                               | Optional Instagram insights enrichment.                                                     |
| `pages_manage_posts`                 | `content_ops_gated`          | No                       | No                           | No                               | Locked additive permission for future Facebook Page organic publishing.                     |
| `instagram_content_publish`          | `content_ops_gated_fallback` | No                       | No                           | No                               | Legacy fallback only if the app uses the older Instagram Graph API flow.                    |
| `instagram_business_basic`           | `content_ops_gated`          | No                       | No                           | No                               | Current primary Instagram professional-account identity permission for publishing planning. |
| `instagram_business_content_publish` | `content_ops_gated`          | No                       | No                           | No                               | Current primary permission for future Instagram organic publishing.                         |
| `catalog_management`                 | `optional_near_term`         | No                       | Yes                          | No                               | Reserved for potential catalog-linked workflows.                                            |
| `pages_manage_ads`                   | `optional_near_term`         | No                       | Yes                          | No                               | Reserved for future Page ad management features.                                            |
| `pages_manage_metadata`              | `optional_near_term`         | No                       | Yes                          | Yes                              | Reserved for webhook/settings control features and Page Insights setup.                     |
| `pages_messaging`                    | `optional_near_term`         | No                       | Yes                          | No                               | Reserved for future messaging/CRM support flows.                                            |

Notes:

- Marketing OAuth means `POST /api/integrations/meta/oauth/start/`.
- Page Insights OAuth means `POST /api/meta/connect/start/`.
- Current Facebook Login authorize requests ignore `read_insights`, `instagram_basic`, and
  `instagram_manage_insights`.
- Optional Instagram reporting permissions should appear only when the active feature explicitly
  depends on Instagram discovery or Instagram insights.
- Content Ops publishing permissions are readiness/App Review candidates only. Do not add them to
  default OAuth scope lists until the publishing runtime is enabled behind feature flags, the app
  console permission family is confirmed, and App Review evidence is accepted.
- For Goal M, the locked Content Ops publishing set is:
  - Facebook Page publishing: `pages_manage_posts`, while preserving existing Page selection/context
    permissions `pages_show_list`, `pages_read_engagement`, and current Page setup dependencies.
  - Instagram publishing: primary current family `instagram_business_basic` plus
    `instagram_business_content_publish`.
  - Legacy Instagram fallback: `instagram_basic` plus `instagram_content_publish` only if the Meta
    app console and adapter implementation prove the older Instagram Graph API route is the active
    product path.

## Reviewer-Ready Wording Standard

Use this pattern in Meta App Review submissions:

- Subject: "ADinsights" (not generic "the app").
- Actor: "on behalf of onboarded business customers."
- Action: concrete verb (`read`, `manage`, `list`, `retrieve`) tied to the permission.
- Surface: exact in-product location where data or action is shown.
- Outcome: concrete business value (for example reporting, onboarding verification, campaign operations).

Avoid vague phrasing like "for analytics purposes" without naming the user action and app surface.

## Deferred And Out-Of-Scope Summary

This lean pass intentionally does not expand all permissions from the compiled Meta reference.

- `deferred` examples:
  - Creator marketplace and branded-content permissions (`facebook_creator_marketplace_*`, `instagram_creator_marketplace_*`, branded content scopes).
  - Commerce-account order/reporting scopes.
  - Leads and event-management families not tied to active ADinsights workflows.
- `out_of_scope` examples:
  - Consumer `user_*` profile permissions.
  - Gaming and non-business social permissions.
  - Threads and WhatsApp permission families for this phase.

Rationale: these are not required for current Meta onboarding, sync, and reporting operations in ADinsights.

The `POST /api/integrations/meta/sync/` reporting action now attempts a bounded organic
Facebook Page/Post reporting bundle after paid Meta direct sync. That bundle still relies on the
existing Page-scoped permissions (`pages_show_list`, `pages_read_engagement`, and stored Page
tokens from the asset-selection flow). It does not require `read_insights`, and it must not be used
as a reason to reintroduce `read_insights` into Facebook Login.

## Local OAuth Reminder

Launcher-backed local Meta OAuth now follows the selected frontend origin and uses
`/dashboards/data-sources` as the redirect path. `http://localhost:5173/dashboards/data-sources`
remains the default checked-in local recipe. If you run another launcher profile locally, treat it
as supported only after the Meta app redirect configuration includes that exact host/port/path.

Explicit redirect URIs are authoritative. Do not silently override them to match a different local
runtime host or port.

## Required Troubleshooting Workflow

Check these endpoints in order:

1. `GET /api/integrations/social/status/`
2. `GET /api/datasets/status/`
3. `GET /api/meta/accounts/`
4. `GET /api/meta/pages/`
5. `GET /api/metrics/combined/`

Classify the issue as exactly one of:

- `auth/setup failure`
- `permission failure`
- `asset discovery failure`
- `direct sync failure`
- `warehouse adapter disabled`
- `missing/stale/default snapshot`

Do not report a generic “Meta broken” diagnosis without this classification.

## Owner Checkpoints (Hypothetical Consult Criteria)

- Maya: `required_now` must match practical onboarding and sync path.
- Sofia: runtime gate wording must match backend enforcement exactly.
- Omar/Hannah: checklist and evidence instructions must be operator-actionable.
- Mei: release and backlog references must make status auditable.
- Raj: change remains single top-level folder (`docs`).
- Mira: structure stays minimal and maintainable (no over-modeling).

## Maintenance Workflow

1. Update `docs/project/meta-permissions-catalog.yaml` first.
2. Update `docs/runbooks/meta-app-review-copy-pack.md` when reviewer-facing language needs revision.
3. Update `docs/runbooks/meta-app-review-submission-checklist.md` if submission evidence requirements changed.
4. Update `docs/runbooks/meta-app-review-validation.md` if runtime flow or scope gating changed.
5. Update `docs/project/phase1-execution-backlog.md` governance tasks and `docs/ops/doc-index.md`.
6. Log the update in `docs/ops/agent-activity-log.md`.
