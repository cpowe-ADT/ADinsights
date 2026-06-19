# DashThis Replacement Reporting Plan

Status: Phase 0/0A started; operator input required before Phase 1
Created: 2026-06-15
Timezone: America/Jamaica

## Purpose

Make ADinsights a practical replacement for DashThis, starting with paid Meta/Google Ads reporting
and expanding into a governed custom dashboard/report builder that can support SLB-style monthly
social reports, combined paid/organic dashboards, and future external users.

This plan converts the existing usable-pilot work into a phase-by-phase operating checklist. Use it
as the control document for agentic execution: one phase at a time, explicit acceptance gates, no
vague "reporting is broken" diagnoses, and no code changes until the evidence shows exactly where
the failure is.

See also:

- `docs/project/usable-pilot-delivery-spec.md`
- `docs/project/reporting-builder-architecture-plan.md`
- `docs/project/reporting-builder-catalog-contract.md`
- `docs/project/current-priority-todo.md`
- `docs/workstreams.md`
- `docs/project/feature-catalog.md`
- `docs/project/integration-data-contract-matrix.md`
- `docs/runbooks/release-checklist.md`
- `docs/runbooks/operations.md`
- `docs/DEVELOPMENT.md`

## Replacement Goal

The first replacement gate is paid-media reporting. A real tenant can stop using DashThis for paid
media reporting when ADinsights can:

1. Pull live Meta Ads and Google Ads data.
2. Populate the warehouse and dbt marts for that tenant.
3. Serve live dashboard data through `/api/metrics/combined/?source=warehouse`.
4. Render the dashboard/reporting UI with `VITE_MOCK_MODE=false`.
5. Generate non-empty CSV, PDF, and PNG report artifacts.
6. Send scheduled report/daily summary email through the configured delivery path.
7. Keep sync/freshness/empty-data alerts visible enough that failures are operationally obvious.
8. Continue rendering historical reports from retained ADinsights data when an upstream source is
   disconnected, as long as the requested date range was previously synced and retained.

GA4, Search Console, LinkedIn, TikTok, organic Content Operations, and enterprise UAC are not part
of the paid-media cancellation gate unless the current DashThis subscription depends on them.

The second replacement gate is full monthly report parity for reports like SLB. That gate is broader
than paid media because the audited SLB reports include organic Facebook/Instagram performance, top
posts, content activity, recommendations, and narrative sections. Full SLB parity should be built on
the reporting builder architecture in `docs/project/reporting-builder-architecture-plan.md`, not as a
one-off hardcoded report.

## Current Audit Summary

As of 2026-06-15, the repository evidence says the reporting implementation is mostly built, but
live activation evidence is still missing.

Built or verified in code and intended to be reused:

- Tenant auth, dashboard shell, saved dashboards, reports UI, alerts UI, summaries UI, sync health,
  and operations pages.
- Meta and Google Ads ingestion/runtime paths.
- dbt staging/marts for paid media reporting, including dashboard aggregate views.
- `/api/metrics/combined/` warehouse-backed reporting path.
- Generic report exports for CSV, PDF, and PNG.
- Scheduled daily summaries through active email notification channels.
- Encrypted Slack/webhook notification destinations.
- Local launcher support for warehouse reporting and shared report export artifacts.
- `DashboardDefinition` tenant-scoped saved dashboards with `template_key`, `filters`, `layout`,
  `default_metric`, ownership fields, and audit events.
- `ReportDefinition` and `ReportExportJob` tenant-scoped report/export models with schedule and
  delivery fields.
- Dashboard create flow in `frontend/src/routes/DashboardCreate.tsx`, currently built around
  approved templates, widget toggles, filters, and live preview.
- `frontend/src/lib/dashboardTemplates.ts` with existing typed slot kinds for KPI strips, trend
  lines, bar charts, pie charts, scatter charts, data tables, maps, and custom slots.
- Meta Page Insights backend/frontend surfaces for Facebook Page/Post insights.
- Content Operations metrics/export scaffolding that can support organic content activity sections.

Known remaining blockers:

- Real Meta and Google Ads sync evidence for the target tenant.
- Staging or production-equivalent KMS and SES evidence.
- One alert delivery proof and one scheduled summary delivery proof.
- 24-48 hour sync/freshness monitoring proof.
- Final Raj/Mira cross-stream release review before treating this as replacement-ready.
- A governed reporting catalog and dashboard schema before custom chart/table creation is exposed
  to users.
- Backend validation for custom widget configs so invalid metric/dimension/chart combinations cannot
  be saved.
- A clear paid-vs-organic source-labeling rule before combined social dashboards are shown.
- A historical reporting fallback policy that defines when 90-day/monthly reports can render from
  stored rows, when they render with partial-coverage warnings, and when they must block because the
  requested range was never synced or retained.

## Integration With Reporting Builder Architecture

Treat this DashThis replacement plan as the business driver and
`docs/project/reporting-builder-architecture-plan.md` as the technical architecture spine.

Use this mapping:

| Existing plan area      | How the reporting builder plan integrates                                                                          |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------ |
| Phase 0/0A audit        | Add required report pages, datasets, metrics, dimensions, widgets, and invalid combinations to the audit.          |
| Paid-media replacement  | Keep the current Meta/Google Ads proof path for the first cancellation gate.                                       |
| SLB full monthly parity | Build the SLB report as the first reusable report template on top of the dashboard/report schema.                  |
| Dashboard UI proof      | Evolve from approved templates to catalog-driven widget creation only after backend validation exists.             |
| Report artifact proof   | Use `ReportDefinition` and export jobs, but define report pages/sections through the same governed schema.         |
| Combined dashboards     | Require explicit source labels and backend-approved blended metrics before paid and organic data are mixed.        |
| Future SaaS users       | Add sharing, role permissions, audit events, quotas, versioning, and support/debug states before external rollout. |

Do not replace existing scaffolding. Extend it:

- `DashboardDefinition.layout` becomes a versioned `dashboard.v1` config.
- `ReportDefinition.layout` becomes the report-page equivalent of the same governed schema.
- `dashboardTemplates.ts` becomes the frontend quick-start/template layer.
- The backend reporting catalog becomes the source of truth for allowed datasets, metrics,
  dimensions, chart types, filters, and comparison modes.
- Meta Ads, Meta Page Insights, and Content Ops remain separate data sources until a documented
  combined metric says otherwise.

## Historical Reporting Fallback Requirement

DashThis cancellation should not mean ADinsights becomes unusable the moment Facebook, Instagram,
Google, Airbyte, or an OAuth token has a temporary outage. The product needs a deliberate distinction
between fresh data and historical data.

Required behavior:

- If Meta/Facebook/Google is disconnected today, a user should still be able to generate a 90-day or
  monthly report from ADinsights if those dates were already synced and retained.
- The report must show a clear coverage note, such as: "Meta is disconnected. This report uses
  stored data through 2026-06-14."
- If only part of the requested period exists, the report should either render as partial with a
  warning or block based on the report template's policy.
- If the date range was never synced, the UI should say `not_previously_synced` or
  `missing_history`, not just "Facebook error."

Planning prompt:

```text
Design the historical reporting fallback for ADinsights.

Goal:
Make sure 90-day and monthly reports can render from stored ADinsights data when Facebook,
Instagram, Google, or another upstream source is disconnected, without pretending the data is fresh.

Consultant lenses:
- Maya/Leo: ingestion outage, backfill, retry, disconnected source behavior.
- Priya/Martin: raw retention, dbt marts, rebuilds, data freshness.
- Sofia/Andre: metrics API, snapshots, coverage metadata, backward compatibility.
- Omar/Hannah: alerts, support diagnosis, stale/partial states.
- Lina/Joel: UI labels and user trust.
- Raj/Mira: cross-stream architecture.

Produce:
- retention windows for raw rows, marts, report snapshots, artifacts, and sync telemetry
- dataset coverage statuses: fresh, stale, partial, source_disconnected, missing_history,
  not_previously_synced
- rules for render, render-with-warning, or block
- API/backend acceptance criteria
- dbt/data-quality tests
- frontend states and copy rules
- runbook and alert updates
```

## Updated Build Sequence

Use this sequence when moving from plan to implementation:

1. Finish Phase 0/0A for the paid-media DashThis cancellation gate.
2. Create the v1 reporting catalog contract in `docs/`:
   - datasets
   - metrics
   - dimensions
   - widget schema
   - chart/table compatibility matrix
   - invalid combinations
   - historical coverage and disconnected-source fallback states
   - backend validation acceptance criteria
3. Implement backend validation for `DashboardDefinition.layout` and, later, `ReportDefinition.layout`.
4. Update the frontend builder to create valid catalog-driven widgets instead of arbitrary configs.
5. Build the SLB monthly report template using the same schema.
6. Add paid/organic combined dashboards with source labels and approved blended metrics only.
7. Harden for SaaS: sharing, roles, audit, quotas, schema migration, export history, and support
   debugging states.

This keeps the immediate DashThis replacement practical while preventing the custom dashboard
builder from becoming an unsafe freeform query tool.

## Scope And Review Route

This document is docs-only. Future implementation can quickly become cross-stream:

- `infrastructure/airbyte/` for connector provisioning and Airbyte health.
- `dbt/` for mart or snapshot fixes.
- `backend/` for integration, metrics, exports, notification, or summary fixes.
- `frontend/` for dashboard/reporting UI fixes.
- `docs/` for runbooks, evidence, and release decisions.

If a phase requires code changes outside one top-level folder, stop and route to Raj. If it changes
shared architecture, runtime behavior, or cross-cutting reporting semantics, route to Raj and Mira.
If it changes API payloads, dbt columns, connector schemas, OAuth scopes, setup/status payloads, or
live-readiness contracts, invoke the contract guard and update the required contract docs.

## Working Rules

- Work one phase at a time.
- Start each phase with an audit, then decide whether code is needed.
- Never commit secrets, OAuth tokens, webhook URLs, or raw client credentials.
- Keep outputs aggregated; do not expose user-level data.
- Use exact failure classes:
  - `auth/setup failure`
  - `permission failure`
  - `asset discovery failure`
  - `direct sync failure`
  - `warehouse adapter disabled`
  - `missing/stale/default snapshot`
  - `export artifact failure`
  - `delivery configuration failure`
- Use `America/Jamaica` for schedules and evidence timestamps unless an upstream system forces UTC.
- After any behavior change, update the relevant runbook and activity log.

## Testing Methodology

Use a test ladder. Do not jump straight to broad suites before the failing layer is isolated.

1. **Static/config gate** - prove the runtime can be started and configured:
   - env flag review
   - `bash -n scripts/dev-launch.sh scripts/dev-healthcheck.sh`
   - `scripts/dev-launch.sh --list-profiles`
   - `docker compose -f docker-compose.dev.yml config` when compose changes are involved
2. **Contract gate** - prove API/data/integration contracts still match consumers:
   - `python3 infrastructure/airbyte/scripts/check_data_contracts.py`
   - `python3 infrastructure/airbyte/scripts/verify_observability_prereqs.py`
   - contract guard or `make adinsights-preflight PROMPT="..."` for contract-sensitive changes
3. **Layer-focused gate** - run the narrow suite for the touched layer:
   - backend: `make backend-lint && make backend-test`
   - frontend: `make frontend-guardrails && make frontend-lint && make frontend-test && make frontend-build`
   - dbt: staging, snapshot, marts, and targeted mart tests from AGENTS
   - Airbyte: readiness scripts and health checks
4. **End-to-end live gate** - prove the reporting user journey:
   - source sync succeeds
   - dbt snapshot/marts are fresh
   - `/api/metrics/combined/?source=warehouse` returns live non-empty data
   - frontend renders with `VITE_MOCK_MODE=false`
   - CSV/PDF/PNG exports complete and download
   - scheduled email/daily summary delivery records success
5. **Regression capture gate** - if a defect is found, add the smallest durable check that would
   catch it next time before broadening the phase.

Testing rules:

- Every phase must record commands run, pass/fail result, and whether failures are repo defects or
  operator/environment blockers.
- A phase cannot be marked complete on a mocked/demo path unless the phase explicitly says it is
  a local-only rehearsal.
- If a phase touches runtime code, run the canonical tests for that folder and update any required
  contract/runbook docs before handoff.

## Debugging Methodology

Debug from the source of truth outward. Do not patch UI symptoms before proving whether the data
exists and which layer lost it.

1. **Classify the failure**
   - `auth/setup failure`
   - `permission failure`
   - `asset discovery failure`
   - `direct sync failure`
   - `warehouse adapter disabled`
   - `missing/stale/default snapshot`
   - `export artifact failure`
   - `delivery configuration failure`
   - `frontend state/rendering failure`
2. **Check the canonical endpoints in order**
   - `GET /api/integrations/social/status/`
   - `GET /api/datasets/status/`
   - `GET /api/meta/accounts/`
   - `GET /api/meta/pages/`
   - `GET /api/integrations/google_ads/status/`
   - `GET /api/health/airbyte/`
   - `GET /api/health/dbt/`
   - `GET /api/metrics/combined/?source=warehouse`
3. **Preserve tenant boundaries**
   - verify the active tenant/client
   - verify account IDs selected for that tenant
   - verify no demo/fake/upload source is masking missing warehouse data
4. **Inspect logs and metrics without exposing secrets**
   - correlate by `tenant_id`, `task_id`, and `correlation_id`
   - inspect sync, snapshot, summary, export, and dbt task status
   - inspect `/metrics/app/` only after real queue activity exists
5. **Patch only the failing layer**
   - integration issue: stay in integration/Airbyte scope
   - dbt issue: stay in dbt scope
   - API issue: stay in backend metrics/export scope
   - UI issue: stay in frontend scope
   - cross-layer contract issue: stop and route to Raj plus contract guard

Debugging output must include:

- primary failure class
- evidence endpoint or command
- first failing layer
- whether it is a repo defect, external blocker, or expected data lag
- smallest proposed fix or scaffolding update

## Scaffolding Update Methodology

Update scaffolding when a bug would otherwise be rediscovered manually. Scaffolding means test
fixtures, schema checks, docs templates, runbook steps, helper scripts, launcher checks, dashboard
empty-state fixtures, or evidence templates.

Update scaffolding when any of these happen:

- The same class of bug appears twice.
- A manual validation step is required in two or more phases.
- A bug crosses a contract boundary: source schema, dbt column, API payload, frontend type, report
  artifact shape, notification payload, or readiness status.
- A local/demo path masks a live-data failure.
- An operator cannot distinguish an external blocker from a repo defect.
- A failure required more than one session to re-diagnose.

Preferred scaffolding updates:

- Add or update a focused unit/integration test in the owning folder.
- Add a dbt schema/source/mart test when the bug is data-shape related.
- Add a data-contract check when a source field, alias, or env-name expectation drifts.
- Add a frontend fixture/test when a readiness, empty, stale, or export state is misrendered.
- Add a launcher or health-check assertion when environment flags or shared volumes are the issue.
- Add a runbook/evidence-template step when the fix is operational rather than code.
- Add an entry to `docs/project/api-contract-changelog.md` or
  `docs/project/integration-data-contract-matrix.md` when the contract changes.

Common bugs that should trigger scaffolding review:

- Warehouse adapter disabled while Meta/Google appear connected.
- Demo/fake/upload source hides missing live warehouse data.
- Meta ad account state is confused with Facebook Page state.
- Meta OAuth redirect host/port does not match the active launcher profile.
- Required Meta permissions are missing or `read_insights` is reintroduced incorrectly.
- Google Ads SDK fallback/parity state is unclear.
- Airbyte connection IDs or source definition IDs are placeholders.
- Empty syncs are treated as success without row-count evidence.
- dbt raw relation names, tenant IDs, or column aliases drift from source data.
- `vw_dashboard_aggregate_snapshot` exists but has no row for the target tenant.
- `TenantMetricsSnapshot` is stale, default, or generated from the wrong source.
- Frontend is running with `VITE_MOCK_MODE=true` or stale cached demo data.
- Dataset toggle, client selection, or platform filters widen data beyond the target scope.
- Report export artifacts are empty, missing, outside the artifact root, or not shared with the API
  container.
- PDF/PNG rendering fails because Chromium/exporter runtime is missing.
- CSV export allows formula-leading cells or unsafe paths.
- Scheduled report or daily summary has no active recipients.
- SES, KMS, Slack, or webhook configuration fails but exposes unsafe details.

## Adversarial Review Methodology

Run an adversarial review before Phase 1 and again before the cancellation decision. The point is
to actively try to disprove that ADinsights is ready to replace DashThis.

Adversarial reviewer stance:

- Assume every green status is stale until there is current evidence.
- Assume demo/fake/upload data can accidentally mask a broken live path.
- Assume "connected" does not mean "reporting ready."
- Assume totals can match while filters, tenants, exports, or schedules are wrong.
- Assume operator-only blockers are real blockers unless the owner and evidence path are named.

Adversarial checks:

- **Scope challenge** - Which DashThis report, stakeholder, or delivery channel is not represented
  in the replacement gate?
- **Source challenge** - Can Meta and Google Ads be independently proven from source platform rows,
  not only from ADinsights UI output?
- **Tenant challenge** - Can the same dashboard/export accidentally include another tenant, client,
  ad account, platform, or demo/upload source?
- **Freshness challenge** - Can stale, default, or missing snapshots look visually acceptable?
- **Permission challenge** - Can Meta setup pass while ad-account reporting is blocked by scopes,
  Page/ad-account confusion, or App Review state?
- **Warehouse challenge** - Can dbt pass with seeded or old rows while the target tenant has no live
  aggregate snapshot?
- **Export challenge** - Can a completed report job point to an empty, missing, unsafe, or
  non-downloadable artifact?
- **Delivery challenge** - Can a scheduled report or daily summary be marked successful without a
  real recipient receiving it?
- **Security challenge** - Can evidence, logs, exports, failures, or screenshots expose secrets,
  webhook URLs, tokens, or user-level data?
- **Operational challenge** - Can the team detect and recover from stale syncs, empty syncs, failed
  exports, failed SES delivery, or upstream token expiration after DashThis is cancelled?

Adversarial output must classify each finding:

- `blocker` - must be fixed or proven before continuing.
- `plan update` - plan/runbook/checklist needs a sharper step.
- `scaffolding update` - add a test, fixture, script, evidence template, or health check.
- `known risk` - acceptable for replacement only with an owner and follow-up date.
- `non-issue` - disproven by current evidence.

## Plan Update Rules

Update this plan during execution when evidence changes the work, not only after the whole project
finishes.

Update the plan when:

- A phase discovers a new blocker.
- A test command is wrong, too broad, too narrow, or cannot run in the target environment.
- A debugging step finds a better source of truth than the current checklist.
- A scaffold update is added to prevent repeat bugs.
- DashThis parity requirements change.
- A deferred source becomes required.
- External ownership changes for Meta, Google Ads, Airbyte, KMS, SES, DNS, or staging.
- A phase exit gate is too weak to justify cancellation.

Each update should include:

- what changed
- why the old plan was insufficient
- the phase affected
- whether the change is docs-only, repo-ready, or blocked-external
- any required reviewer or contract guard route

## Preparation Backlog

Prepare these before Phase 1 so activation work does not stall on missing context:

- [ ] DashThis report inventory and owner signoff.
- [ ] First tenant/client proof target.
- [x] Source-platform comparison worksheet for Meta and Google Ads totals.
- [x] Evidence folder and template under `docs/project/evidence/dashthis-replacement/`.
- [x] External prerequisite checklist for Meta app, Google Ads developer token/OAuth, Airbyte,
      KMS, SES, DNS, Slack/webhook, and staging access.
- [ ] Redacted credential ownership map: who can provide each secret without pasting it into chat
      or committing it.
- [ ] Expected report delivery list: who should receive scheduled reports and daily summaries.
- [ ] Rollback/cancellation hold rule: keep DashThis active until Phase 7 passes.
- [ ] Known acceptable differences list: attribution lag, timezone, currency, conversion windows,
      and source platform reporting delays.
- [ ] "No-go" criteria list: any condition that blocks cancellation regardless of partial success.

## Phase Map

| Phase | Name                               | Primary owner route       | Status                            | Exit gate                                                                     |
| ----- | ---------------------------------- | ------------------------- | --------------------------------- | ----------------------------------------------------------------------------- |
| 0     | DashThis parity audit              | Raj + Sofia + Lina        | Ready                             | Required DashThis reports and KPIs are listed with acceptance thresholds.     |
| 0A    | Adversarial plan review            | Raj + stream owners       | Ready after Phase 0               | Blockers, weak gates, and scaffolding needs are classified before activation. |
| 1     | Activation readiness audit         | Maya + Nina + Omar        | Ready                             | Required env, credentials, Airbyte, KMS, SES, and staging blockers are known. |
| 2     | Live source sync proof             | Maya + Leo                | Blocked until credentials/runtime | Meta and Google Ads syncs complete with non-empty tenant rows.                |
| 3     | Warehouse and snapshot proof       | Priya + Sofia             | Blocked until Phase 2 rows exist  | dbt marts and warehouse snapshot produce live combined metrics.               |
| 4     | Dashboard UI proof                 | Lina + Joel               | Blocked until Phase 3             | Frontend renders live paid-media dashboards with honest empty/stale states.   |
| 5     | Report artifact and delivery proof | Sofia + Nina + Omar       | Blocked until Phase 3             | CSV/PDF/PNG exports and scheduled email delivery are proven.                  |
| 6     | DashThis parity decision           | Raj + Sofia + stakeholder | Blocked until Phase 5             | ADinsights totals match accepted thresholds for a fixed range.                |
| 7     | Replacement hardening window       | Omar + Hannah + Mei       | Blocked until Phase 6             | 24-48 hour monitor passes and cancellation decision is recorded.              |

## Phase Testing And Debugging Matrix

| Phase | Test focus                                                                                 | Debug focus                                                                                | Scaffolding update trigger                                                              |
| ----- | ------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------- |
| 0     | Docs-only audit; no runtime tests unless a proof artifact is created.                      | Missing or ambiguous replacement requirements.                                             | Add/update evidence template if the same report inventory questions recur.              |
| 0A    | Adversarial review; no runtime tests unless evidence claims need verification.             | Weak assumptions, missing source proof, weak cancellation gates, hidden external blockers. | Add templates, checklists, tests, or runbook gates for any blocker/plan-update finding. |
| 1     | Launcher syntax, profile list, healthcheck, data-contract, observability prereq checks.    | Env flags, OAuth redirect, Airbyte IDs, KMS/SES readiness, shared artifact volume.         | Add launcher/healthcheck/runbook checks for recurring config mistakes.                  |
| 2     | Integration readiness scripts, provider status endpoints, sync telemetry, row-count proof. | Auth, permission, asset selection, empty syncs, ad account vs Page confusion.              | Add connector/status tests or contract checks for repeated setup/sync bugs.             |
| 3     | dbt staging, snapshot, mart, and targeted mart tests plus combined metrics API proof.      | Raw relation drift, tenant_id issues, stale/missing/default snapshots.                     | Add dbt schema tests, seed fixtures, or snapshot health checks.                         |
| 4     | Frontend guardrails, lint, tests, build, plus live UI smoke with `VITE_MOCK_MODE=false`.   | Dataset toggle, stale cache, empty/stale UI states, tenant/client scoping.                 | Add frontend fixtures/tests for any readiness or render state bug.                      |
| 5     | Backend/frontend suites, preflight, export downloads, delivery audit records.              | Artifact storage, renderer runtime, sanitized failures, email/channel config.              | Add export/download tests, renderer checks, or delivery runbook steps.                  |
| 6     | Fixed-range parity comparison against DashThis/source platforms.                           | Attribution lag, timezone, currency, platform filter, account selection differences.       | Add parity worksheet/template if comparisons require repeated manual structure.         |
| 7     | Strict observability smoke after real queue activity and 24-48 hour monitor evidence.      | Missing metrics, stale syncs, empty syncs, alert noise, rollback readiness.                | Add alert simulation or dashboard evidence template for repeated operational gaps.      |

## Phase 0 - DashThis Parity Audit

Goal: define the actual replacement bar before making code changes.

Inputs to collect:

- Which DashThis dashboards are still used.
- Which clients/tenants must be covered first.
- Which date ranges matter: yesterday, last 7 days, month to date, last month.
- Required widgets: KPI cards, campaign table, creative table, pacing, parish/map, channel split,
  PDF, CSV, scheduled email.
- Required tolerances against source platforms or DashThis.

Audit checklist:

- [ ] List current DashThis report names.
- [ ] List required paid media sources.
- [ ] Mark GA4/Search Console as required or deferred.
- [ ] Define metric tolerances:
  - Spend: target drift <= 1.0%.
  - Clicks: target drift <= 2.0%.
  - Conversions: target drift <= 2.0%, subject to attribution lag.
  - Impressions: target drift <= 2.0%.
- [ ] Define output requirements for CSV, PDF, PNG, and scheduled email.
- [ ] Name the first tenant/client used for proof.

Evidence to produce:

- A short markdown artifact under `docs/project/evidence/dashthis-replacement/`.
- Screenshots or exported values from DashThis/source platforms may be referenced, but do not commit
  sensitive customer data.

Reusable prompt:

```text
You are resuming ADinsights from /Users/thristannewman/ADinsights.

Goal: complete Phase 0 of docs/project/dashthis-replacement-reporting-plan.md.

Do not change runtime code. Audit the current DashThis replacement requirements and produce:
- required reports
- required sources
- required KPIs
- required outputs
- accepted drift thresholds
- first tenant/client proof target
- blockers that require operator input
- testing/debugging risks for Phase 1
- scaffolding updates needed before Phase 1

Follow AGENTS.md. Keep all data aggregated and do not write secrets.
```

Exit gate:

- Phase 0 is complete when the replacement report list and metric thresholds are written down and
  the first tenant/client proof target is selected.

## Phase 0A - Adversarial Plan Review

Goal: try to invalidate the plan before live activation work starts.

Adversarial checklist:

- [ ] Name the top five ways this replacement could fail after DashThis is cancelled.
- [ ] Identify every unstated assumption in Phase 0 and Phase 1.
- [ ] Identify any report/KPI/output that cannot be proven with the current code or evidence.
- [ ] Identify any required proof that depends on an external owner.
- [ ] Identify any phase gate that could pass with demo, stale, default, or wrong-tenant data.
- [ ] Identify any common bug that lacks a test, fixture, runbook step, or evidence template.
- [ ] Decide which findings are blockers, plan updates, scaffolding updates, known risks, or
      non-issues.

Reusable prompt:

```text
You are resuming ADinsights from /Users/thristannewman/ADinsights.

Goal: complete Phase 0A of docs/project/dashthis-replacement-reporting-plan.md.

Act as an adversarial reviewer. Try to prove the plan is not enough to safely replace DashThis.
Do not change runtime code.

Produce:
- top failure modes after cancellation
- unstated assumptions
- weak or gameable phase gates
- missing evidence templates or scaffolding
- blockers versus known risks
- exact plan updates needed before Phase 1

Keep all data aggregated. Do not write secrets.
```

Exit gate:

- Phase 0A is complete when every adversarial finding is classified and the plan/scaffolding updates
  required before Phase 1 are either completed or assigned.

## Phase 1 - Activation Readiness Audit

Goal: prove whether the environment can even run live reporting.

Audit checklist:

- [ ] Confirm local/staging runtime target.
- [ ] Confirm `VITE_MOCK_MODE=false`.
- [ ] Confirm intended backend flags:
  - `ENABLE_WAREHOUSE_ADAPTER=1`
  - `ENABLE_FAKE_ADAPTER=0`
  - `ENABLE_DEMO_ADAPTER=1` allowed only as fallback/demo, not replacement proof.
- [ ] Confirm Airbyte settings exist without exposing values:
  - `AIRBYTE_API_URL`
  - `AIRBYTE_DEFAULT_WORKSPACE_ID`
  - `AIRBYTE_DEFAULT_DESTINATION_ID`
  - Meta and Google source definition IDs where required.
- [ ] Confirm Meta app settings and redirect URI are aligned with the runtime.
- [ ] Confirm Google Ads OAuth/developer token prerequisites.
- [ ] Confirm KMS provider is production-equivalent for staging proof.
- [ ] Confirm SES sender/domain readiness for scheduled delivery proof.
- [ ] Confirm report export artifact root is shared by API and summary worker.

Commands:

```bash
scripts/dev-launch.sh --list-profiles
bash -n scripts/dev-launch.sh scripts/dev-healthcheck.sh
ENABLE_WAREHOUSE_ADAPTER=1 ENABLE_DEMO_ADAPTER=1 ENABLE_FAKE_ADAPTER=0 scripts/dev-launch.sh --profile 1 --strict-profile --non-interactive --no-update --no-pull --no-open
scripts/dev-healthcheck.sh
cat .dev-launch.active.env
python3 infrastructure/airbyte/scripts/check_data_contracts.py
python3 infrastructure/airbyte/scripts/verify_observability_prereqs.py
```

Exit gate:

- Phase 1 is complete when each required external dependency is either verified or explicitly
  marked blocked with owner, required action, and evidence path.

## Phase 2 - Live Source Sync Proof

Goal: prove that live Meta and Google Ads data can be pulled for the target tenant.

Audit checklist:

- [ ] Meta OAuth/setup succeeds.
- [ ] Meta ad account selection is present and not confused with Facebook Page selection.
- [ ] `GET /api/meta/accounts/` returns at least one target ad account.
- [ ] Meta sync runs and records non-empty telemetry.
- [ ] Google Ads setup/status is valid.
- [ ] Google Ads sync runs and records non-empty telemetry.
- [ ] Empty syncs are classified as account/date/permission issues, not ignored.

Commands and endpoints:

```bash
python3 infrastructure/airbyte/scripts/validate_tenant_config.py
python3 infrastructure/airbyte/scripts/verify_production_readiness.py
python3 infrastructure/airbyte/scripts/airbyte_health_check.py
```

- `GET /api/integrations/social/status/`
- `GET /api/meta/accounts/`
- `GET /api/integrations/google_ads/status/`
- `GET /api/health/airbyte/`
- `GET /api/airbyte/telemetry/`

Exit gate:

- Phase 2 is complete when both Meta and Google Ads have successful, non-empty sync evidence for
  the target tenant.

## Phase 3 - Warehouse And Snapshot Proof

Goal: prove that synced rows become dashboard-ready warehouse metrics.

Audit checklist:

- [ ] dbt staging builds against the live source data.
- [ ] snapshots run.
- [ ] marts build.
- [ ] `fact_performance`, `dim_campaign`, and `vw_campaign_daily` pass targeted tests.
- [ ] `vw_dashboard_aggregate_snapshot` returns a row for the target tenant.
- [ ] `TenantMetricsSnapshot` source `warehouse` is fresh.
- [ ] `/api/datasets/status/` reports `ready`, not `adapter_disabled`, `missing_snapshot`,
      `stale_snapshot`, or `default_snapshot`.

Commands:

```bash
make dbt-deps
./scripts/dbt-wrapper.sh 'dbt' 'dbt' 'dbt' run --select staging
./scripts/dbt-wrapper.sh 'dbt' 'dbt' 'dbt' snapshot
./scripts/dbt-wrapper.sh 'dbt' 'dbt' 'dbt' run --select all_ad_performance dim_campaign fact_performance
./scripts/dbt-wrapper.sh 'dbt' 'dbt' 'dbt' run --select marts
./scripts/dbt-wrapper.sh 'dbt' 'dbt' 'dbt' test --select all_ad_performance dim_campaign fact_performance vw_campaign_daily
```

Exit gate:

- Phase 3 is complete when `GET /api/metrics/combined/?source=warehouse` returns non-empty live
  paid media data for the target tenant with a fresh `snapshot_generated_at`.

## Phase 4 - Dashboard UI Proof

Goal: prove the user-facing dashboard can replace daily DashThis viewing.

Audit checklist:

- [ ] Frontend is running with `VITE_MOCK_MODE=false`.
- [ ] Dashboard pages render live paid media data.
- [ ] Dataset toggle does not hide that proof behind demo data.
- [ ] Campaign, creative, budget pacing, platform, and parish/map sections render.
- [ ] Empty/stale states are truthful and actionable.
- [ ] Tenant switch does not leak data across tenants.

Commands:

```bash
make frontend-guardrails
make frontend-lint
make frontend-test
make frontend-build
```

Manual proof:

- Open the active frontend URL from `.dev-launch.active.env`.
- Login as the target user.
- Check dashboard routes and capture pass/fail notes.

Exit gate:

- Phase 4 is complete when a stakeholder can view the target tenant's paid media reporting in the
  ADinsights UI without relying on DashThis for the same daily checks.

## Phase 5 - Report Artifact And Delivery Proof

Goal: prove that reports can be exported and delivered.

Audit checklist:

- [ ] `/reports` loads with live API responses.
- [ ] A target report definition exists or is created.
- [ ] CSV export completes and downloads a non-empty file.
- [ ] PDF export completes and downloads a non-empty file.
- [ ] PNG export completes and downloads a non-empty file.
- [ ] Scheduled report email path is configured and sends successfully.
- [ ] Daily summary sends through active tenant email notification channels.
- [ ] Slack or webhook destination proof is captured if required for replacement.
- [ ] Failed jobs expose sanitized errors only.

Commands:

```bash
make backend-lint
make backend-test
make frontend-guardrails
make frontend-lint
make frontend-test
make frontend-build
backend/.venv/bin/python backend/manage.py backend_release_preflight
```

Exit gate:

- Phase 5 is complete when CSV/PDF/PNG artifacts and scheduled email delivery are proven against
  the target tenant.

## Phase 6 - DashThis Parity Decision

Goal: decide whether ADinsights is good enough to replace DashThis.

Audit checklist:

- [ ] Pick one fixed date range.
- [ ] Compare ADinsights against DashThis and/or source platforms.
- [ ] Record metric drift.
- [ ] Explain expected differences from attribution windows, conversion lag, timezone, or source
      currency.
- [ ] Classify every gap as:
  - blocker before cancellation
  - acceptable known difference
  - post-cancellation enhancement

Exit gate:

- Phase 6 is complete when the replacement decision is recorded as `go`, `conditional go`, or
  `no-go`, with exact blockers for anything not accepted.

## Phase 7 - Replacement Hardening Window

Goal: avoid cancelling DashThis on a one-time happy path.

Audit checklist:

- [ ] Monitor 24-48 hours of syncs.
- [ ] Confirm stale snapshot alerts.
- [ ] Confirm empty sync alerts.
- [ ] Confirm `/metrics/app/` includes combined metrics, Airbyte, dbt, sync, snapshot, and summary
      activity.
- [ ] Run strict live smoke after real task activity exists.
- [ ] Record rollback plan: keep DashThis active until the monitor window passes.

Commands:

```bash
python3 backend/manage.py backend_release_smoke --strict-observability
make adinsights-preflight PROMPT="DashThis replacement reporting readiness"
```

Exit gate:

- Phase 7 is complete when the monitor window passes and the final cancellation recommendation is
  documented.

## First Session Prompt

Use this to start:

```text
You are resuming ADinsights from /Users/thristannewman/ADinsights.

Read:
- AGENTS.md
- docs/project/dashthis-replacement-reporting-plan.md
- docs/project/usable-pilot-delivery-spec.md
- docs/project/current-priority-todo.md
- docs/workstreams.md

Start Phase 0 only. Do not change runtime code.

Produce:
- DashThis report inventory template
- required KPI/output checklist
- first tenant/client proof target decision
- blocked operator questions
- exact next phase recommendation
- whether Phase 0A can run immediately

Keep all data aggregated. Do not write secrets. If implementation would cross folders, stop and
route to Raj/Mira before editing.
```

## Cancellation Bar

Do not cancel DashThis until all of these are true:

- Phase 0 through Phase 6 are complete, including Phase 0A adversarial review.
- Phase 7 monitoring has run for at least 24 hours, preferably 48 hours.
- No required DashThis report remains unmatched without a documented workaround.
- The final replacement decision is recorded with owner, date, and evidence links.
