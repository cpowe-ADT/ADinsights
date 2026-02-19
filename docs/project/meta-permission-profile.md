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

## Active And Near-Term Permission Set

| Permission | Status | Runtime gate required | Requested in default OAuth | Why it exists now |
| --- | --- | --- | --- | --- |
| `ads_read` | `required_now` | Yes | Yes | Core ad-metrics read path for dashboards and sync validation. |
| `ads_management` | `required_now` | Yes (OR with `ads_read`) | Yes | Alternate acceptable ad scope in runtime gate; supports ad-management readiness. |
| `business_management` | `required_now` | Yes | Yes | Business asset access needed for ad account binding. |
| `pages_read_engagement` | `required_now` | Yes | Yes | Page-level context required by connect flow and dependencies. |
| `pages_show_list` | `required_now` | Yes | Yes | Page ownership/selection required during onboarding. |
| `instagram_basic` | `optional_near_term` | No | Yes | Optional Instagram account discovery and identity mapping. |
| `instagram_manage_insights` | `optional_near_term` | No | Yes | Optional Instagram insights enrichment. |
| `catalog_management` | `optional_near_term` | No | Yes | Reserved for potential catalog-linked workflows. |
| `pages_manage_ads` | `optional_near_term` | No | Yes | Reserved for future Page ad management features. |
| `pages_manage_metadata` | `optional_near_term` | No | Yes | Reserved for webhook/settings control features. |
| `pages_messaging` | `optional_near_term` | No | Yes | Reserved for future messaging/CRM support flows. |

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
