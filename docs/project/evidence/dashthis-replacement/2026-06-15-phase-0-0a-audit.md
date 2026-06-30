# Phase 0/0A DashThis Replacement Audit

Evidence timestamp: 2026-06-15T18:29:45-0500
Timezone: America/Jamaica
Plan: `docs/project/dashthis-replacement-reporting-plan.md`
Status: started; Gmail evidence and attachment review added; SLB recommended as first proof target
pending operator confirmation.

## Scope Decision

This pass is docs-only and stays in `docs/`. It does not change runtime code, API contracts, dbt
models, Airbyte configuration, frontend behavior, OAuth scopes, KMS, SES, Slack, or webhook
delivery.

Scope-gate advisory:

- `scope_status`: `PASS_SINGLE_SCOPE`
- `touched_top_level_folders`: `docs/`
- `required_reviewers`: Raj before cross-folder activation; Raj plus Mira for shared runtime or
  architecture changes.
- `contract_risk_signal`: false for this docs-only artifact. Re-evaluate if later phases alter API
  payloads, dbt columns, connector schemas, OAuth scopes, setup/status payloads, or readiness
  semantics.

## Phase 0 Inventory Status

| Requirement                     | Current status    | Notes                                                                                                                                                                                               |
| ------------------------------- | ----------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| DashThis report names           | Partially known   | Gmail evidence identified `SLB Marketing Campaign Status Report, May 2026`; exact DashThis dashboard names still need confirmation.                                                                 |
| First proof tenant/client       | Recommended       | Use SLB first unless the operator overrides it. Gmail has the clearest report-plus-Meta-activity evidence.                                                                                          |
| Required paid media sources     | Partially known   | Meta Ads is proven for SLB, JDIC, and BOJ/Common Cents. Google Ads was not proven in the Gmail pass.                                                                                                |
| GA4/Search Console requirement  | Partially known   | Required if Grace is in cancellation scope; Gmail shows Grace Foods GA4 and Search Console performance emails.                                                                                      |
| Required date ranges            | Partially known   | May 2026 is recommended for SLB because Gmail shows a May 2026 campaign status report and nearby Meta activity.                                                                                     |
| Required outputs                | Partially assumed | Dashboard view, CSV, PDF, PNG, scheduled email, and daily summary are in scope; Slack/webhook only if DashThis currently provides equivalent delivery.                                              |
| Required recipients             | Blocked           | Need scheduled-report and daily-summary recipient list.                                                                                                                                             |
| Source-platform comparison data | Blocked           | Need aggregated Meta/Google source totals or screenshots/exports for the fixed parity range. Do not commit sensitive exports.                                                                       |
| SLB full-report parity          | Blocked           | Gmail attachments show the SLB deliverable includes organic social metrics, top performers, narrative work completed, and recommendations. Operator must decide full parity vs paid-media-only MVP. |

## Working Replacement Bar

Until operator input narrows it, use this default bar for paid media reporting:

- Sources: Meta Ads and Google Ads.
- Dashboard: live ADinsights dashboard with `VITE_MOCK_MODE=false` and
  `/api/metrics/combined/?source=warehouse`.
- KPIs: spend, impressions, clicks, CTR, CPC, CPM, conversions, conversion rate, CPA, ROAS where
  source data supports it, reach where source data supports it, pacing, campaign split, creative
  split, channel/platform split, and parish/map split where available.
- Outputs: dashboard view, CSV export, PDF export, PNG export, scheduled email, and daily summary.
- Tolerances: spend drift <= 1.0%; clicks, conversions, and impressions drift <= 2.0%;
  conversions remain subject to attribution lag and conversion-window differences.

This is not enough to cancel DashThis until the actual DashThis report list and first proof tenant
are confirmed.

## Operator Questions

1. Which DashThis dashboard/report names must ADinsights replace before cancellation?
2. Which tenant/client is the first proof target?
3. Are GA4, Search Console, LinkedIn, TikTok, or organic social required for the DashThis
   cancellation decision, or can they stay deferred?
4. Which exact widgets are required: KPI cards, campaign table, creative table, pacing,
   parish/map, channel split, budget section, or another view?
5. Which date range should be used for parity proof?
6. Who receives scheduled reports and daily summaries?
7. Are Slack or webhook deliveries required, or is email sufficient?
8. Who can provide redacted source-platform totals/screenshots for Meta and Google Ads without
   sharing credentials or raw user-level data?
9. Who owns the external prerequisites: Meta app, Google Ads OAuth/developer token, Airbyte
   workspace, KMS, SES, DNS, Slack/webhook destination, and staging access?

## Phase 0A Adversarial Findings

| Finding                                                                                                       | Classification     | Owner                     | Required action                                                                                     |
| ------------------------------------------------------------------------------------------------------------- | ------------------ | ------------------------- | --------------------------------------------------------------------------------------------------- |
| No actual DashThis report inventory exists in repo evidence.                                                  | blocker            | Operator + Raj/Sofia/Lina | Provide active DashThis report names, widgets, recipients, and date ranges.                         |
| No first proof tenant/client is selected.                                                                     | blocker            | Operator + Raj            | Select one target tenant/client before Phase 1 runtime validation.                                  |
| GA4/Search Console dependency is unknown.                                                                     | blocker            | Operator + Raj            | Explicitly mark each non-paid-media source required or deferred.                                    |
| Source-platform comparison evidence is absent.                                                                | blocker            | Operator + Sofia/Priya    | Provide aggregated Meta/Google totals for the fixed date range.                                     |
| Phase gates could pass with demo, stale, default, upload, or wrong-tenant data if evidence is not structured. | scaffolding update | Raj/Omar                  | Use the new evidence template and require source, tenant, date range, and artifact proof per phase. |
| Report delivery could look complete without proof of actual recipient delivery.                               | plan update        | Nina/Omar                 | Record scheduled report recipients and delivery audit evidence before Phase 5 exit.                 |
| Meta "connected" state can be confused with ad-account reporting readiness.                                   | known risk         | Maya/Sofia                | Phase 2 must prove ad account selection and non-empty reporting rows, not only social status.       |
| Attribution lag, timezone, currency, and conversion-window differences can create false parity failures.      | known risk         | Sofia/Priya               | Maintain an acceptable-differences list before Phase 6.                                             |
| Secrets or webhook URLs could leak through evidence artifacts.                                                | blocker            | Nina/Omar                 | Evidence must stay redacted and aggregated; never paste credentials, tokens, or webhook URLs.       |

## No-Go Criteria Before DashThis Cancellation

DashThis stays active if any of these are true:

- The first proof tenant/client is not selected.
- Actual DashThis reports, widgets, recipients, and required sources are not listed.
- Meta Ads or Google Ads live sync evidence is missing, empty, stale, or from the wrong tenant.
- `/api/metrics/combined/?source=warehouse` does not return non-empty live data for the target
  tenant.
- The dashboard proof relies on demo, fake, upload, default, or stale snapshot data.
- CSV, PDF, or PNG report artifacts are empty, missing, unsafe, or non-downloadable.
- Scheduled email or daily summary delivery is not proven to the real recipient path.
- Source-platform parity cannot be compared for a fixed date range.
- Evidence exposes secrets, tokens, webhook URLs, or user-level data.

## Scaffolding Added

- Created `docs/project/evidence/dashthis-replacement/_TEMPLATE.md`.
- Created this Phase 0/0A audit artifact.
- Created `docs/project/evidence/dashthis-replacement/2026-06-15-report-inventory-from-gmail.md`.
- Created `docs/project/evidence/dashthis-replacement/2026-06-15-email-attachment-review.md`.

## Decision

Phase 0 and Phase 0A have started but cannot exit yet. The repo now has the evidence scaffold,
Gmail-derived report inventory, and an adversarial finding list. Phase 1 may start around SLB only
after the operator confirms SLB as the proof target, confirms whether Google Ads and organic/social
metrics and narrative report sections are required, names recipients, and provides or authorizes
source-platform comparison totals.
